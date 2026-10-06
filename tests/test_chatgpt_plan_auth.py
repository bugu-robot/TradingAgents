"""Offline OAuth identity, rotation and credential-isolation coverage."""

import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlparse

import jwt
import pytest
import requests
from cryptography.hazmat.primitives.asymmetric import rsa

from tradingagents.llm_clients import chatgpt_plan_auth as auth
from tradingagents.llm_clients.subscription_errors import SubscriptionError, redact

_LOOPBACK_CONNECT = socket.socket.connect


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_CHATGPT_AUTH_DIR", str(tmp_path / "auth"))
    return auth.ChatGPTAuthStore()


def connect(store, **overrides):
    store._prepare_directory()
    record = {"issuer": auth.AUTH_ORIGIN, "subject": "user-a", "email": "a@example.invalid",
              "client_id": "oaiapp_a", "access_token": "access-secret", "refresh_token": "refresh-secret",
              "id_token": "id-secret", "expires_at": time.time() + 3600,
              "scopes": auth.SCOPES.split()}
    record.update(overrides)
    auth._write_json(store.path, record)
    return record


def token(**overrides):
    return {"access_token": "renewed-access", "refresh_token": "renewed-refresh",
            "id_token": "new-id", "expires_in": 3600, "token_type": "Bearer",
            "scope": auth.SCOPES, **overrides}


def test_missing_login_is_actionable_and_never_uses_api_key(store, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "api-key-must-not-be-used")
    with pytest.raises(SubscriptionError, match="tradingagents auth login"):
        store.preflight()
    assert "api-key-must-not-be-used" not in repr(store)


def test_pending_registration_reuses_client_without_becoming_active(store):
    store.remember_registration("oaiapp_a")
    parameters, _ = auth.authorization_parameters(store, "http://127.0.0.1:1455/auth/callback")
    assert parameters["client_id"] == "oaiapp_a" and "agent_name_hint" not in parameters
    assert not store.status()["connected"] and not (store.directory / "active.json").exists()
    with pytest.raises(SubscriptionError):
        store.preflight()
    store.save_login(token(), "oaiapp_a", "nonce", {"nonce": "nonce", "sub": "user-a"})
    assert store.preflight()["subject"] == "user-a"


def test_pending_registration_cannot_replace_existing_account(store):
    record = connect(store)
    with pytest.raises(SubscriptionError):
        store.remember_registration("oaiapp_other")
    assert store.read() == record


def test_reconsent_only_after_explicit_enable_plan_usage(store):
    connect(store, scopes=["openid", "profile", "email"])
    plain, _ = auth.authorization_parameters(store, "http://127.0.0.1:1455/auth/callback")
    consent, _ = auth.authorization_parameters(store, "http://127.0.0.1:1455/auth/callback", enable_plan_usage=True)
    assert "prompt" not in plain and consent["prompt"] == "consent"
    assert "force_reconsent" not in consent and consent["client_id"] == "oaiapp_a"


@pytest.mark.parametrize("status,confirmed", [(200, True), (503, False)])
def test_logout_revoke_then_clear_tokens_and_keep_registration(store, monkeypatch, status, confirmed):
    record = connect(store)
    calls = []
    from .test_chatgpt_plan import Response

    monkeypatch.setattr(auth, "_get_json", lambda *a: {"revocation_endpoint": auth.AUTH_ORIGIN + "/oauth/revoke"})
    monkeypatch.setattr(auth.time, "sleep", lambda *a: None)

    def post(url, **kwargs):
        calls.append((url, kwargs))
        assert store.read()["refresh_token"] == record["refresh_token"]
        return Response(status=status)

    monkeypatch.setattr(auth.requests, "post", post)
    assert store.logout() is confirmed
    assert store.read()["client_id"] == record["client_id"]
    assert "access_token" not in store.read() and "refresh_token" not in store.read()
    assert calls[0][1]["data"]["token_type_hint"] == "refresh_token"
    assert len(calls) == (1 if confirmed else 3)


@pytest.mark.parametrize("overrides", [
    {"scopes": ["openid"]}, {"client_id": "dynamic_agent_client"},
    {"issuer": "https://evil.invalid"}, {"subject": ""},
    {"expires_at": "invalid"}, {"expires_at": 0, "refresh_token": ""},
])
def test_preflight_rejects_invalid_or_unconsented_credentials(store, overrides):
    connect(store, **overrides)
    with pytest.raises(SubscriptionError):
        store.preflight()


def test_unexpired_token_no_network_and_status_has_no_secrets(store):
    connect(store)
    assert store.access_token() == "access-secret"
    assert "secret" not in json.dumps(store.status())
    assert store.status()["plan_usage_enabled"]


def test_host_id_stable_and_file_permissions_owner_only(store):
    connect(store)
    assert store.host_id() == auth.ChatGPTAuthStore().host_id()
    assert store.path.stat().st_mode & 0o777 == 0o600
    assert store.directory.stat().st_mode & 0o777 == 0o700
    store.path.chmod(0o644)
    with pytest.raises(SubscriptionError, match="permissions"):
        store.read()


def test_storage_symlink_is_rejected_without_changing_target(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir(mode=0o755)
    link = tmp_path / "linked-auth"
    link.symlink_to(target, target_is_directory=True)
    monkeypatch.setenv("TRADINGAGENTS_CHATGPT_AUTH_DIR", str(link))
    with pytest.raises(SubscriptionError, match="symbolic"):
        auth.ChatGPTAuthStore().host_id()
    assert target.stat().st_mode & 0o777 == 0o755 and list(target.iterdir()) == []


def test_rotation_lock_symlink_cannot_modify_another_file(store, tmp_path):
    connect(store)
    target = tmp_path / "untouched"
    target.write_text("sentinel")
    (store.directory / (store.profile + ".lock")).symlink_to(target)
    with pytest.raises(SubscriptionError, match="symbolic"):
        store.access_token()
    assert target.read_text() == "sentinel"


def test_shared_storage_directory_is_rejected_before_token_write(store):
    connect(store)
    before = store.path.read_bytes()
    store.directory.chmod(0o755)
    with pytest.raises(SubscriptionError, match="permissions"):
        store.logout()
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("raw", ['{"access_token":"a","access_token":"b"}',
                                 '{"expires_at":NaN}', '{"expires_at":1e999}'])
def test_ambiguous_credential_json_has_no_token_request(store, raw, monkeypatch):
    connect(store)
    store.path.write_text(raw)
    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: pytest.fail("no token request"))
    with pytest.raises(SubscriptionError):
        store.access_token()


def test_concurrent_refresh_rotates_once_and_preserves_registration(store, monkeypatch):
    connect(store, expires_at=0)
    posted = []

    def renew(data):
        posted.append(data)
        return token()

    monkeypatch.setattr(auth, "_token_request", renew)
    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(lambda _: store.access_token(), range(2)))
    assert result == ["renewed-access"] * 2
    assert len(posted) == 1
    assert posted[0] == {"grant_type": "refresh_token", "client_id": "oaiapp_a",
                          "refresh_token": "refresh-secret", "resource": auth.RESOURCE}
    assert "scope" not in posted[0]
    assert store.read()["refresh_token"] == "renewed-refresh"
    assert store.read()["subject"] == "user-a"


def test_refresh_scope_revocation_is_saved_but_never_sent_to_inference(store, monkeypatch):
    from tradingagents.llm_clients.factory import create_llm_client

    connect(store, expires_at=0)
    monkeypatch.setattr(auth, "_token_request", lambda _: token(scope="openid profile email"))
    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: pytest.fail("revoked grant must not reach inference"))
    model = create_llm_client("chatgpt_plan", "account-model").get_llm()
    with pytest.raises(SubscriptionError, match="plan-use permission"):
        model.invoke("hello")
    assert store.read()["refresh_token"] == "renewed-refresh"
    assert store.read()["scopes"] == ["openid", "profile", "email"]


@pytest.mark.parametrize("lifetime", [float("nan"), float("inf"), -1])
def test_invalid_token_lifetime_cannot_become_an_unexpiring_connection(lifetime):
    with pytest.raises(SubscriptionError):
        auth._token_record({}, token(expires_in=lifetime))


@pytest.mark.parametrize("field", ["expires_at", "earliest_refresh_at"])
def test_nonfinite_saved_renewal_metadata_is_rejected(store, field):
    connect(store, expires_at=0, **({field: float("inf")} if field != "expires_at" else {}))
    if field == "expires_at":
        connect(store, expires_at=float("nan"))
    with pytest.raises(SubscriptionError, match="invalid"):
        store.access_token()


def test_temporary_refresh_failure_preserves_tokens(store, monkeypatch):
    old = connect(store, expires_at=0)

    def fail(_):
        raise SubscriptionError("Temporary failure", kind="transient")

    monkeypatch.setattr(auth, "_token_request", fail)
    with pytest.raises(SubscriptionError):
        store.access_token()
    assert store.read() == old


def test_terminal_refresh_clears_tokens_but_keeps_client_and_host(store, monkeypatch):
    connect(store, expires_at=0)
    host = store.host_id()

    def fail(_):
        raise SubscriptionError("Invalid grant", kind="auth", code="invalid_grant")

    monkeypatch.setattr(auth, "_token_request", fail)
    with pytest.raises(SubscriptionError):
        store.access_token()
    assert store.read()["client_id"] == "oaiapp_a"
    assert "access_token" not in store.read()
    assert store.host_id() == host


def test_pkce_registration_and_returning_login_do_not_expose_id_tokens(store):
    params, verifier = auth.authorization_parameters(store, "http://127.0.0.1:1455/auth/callback")
    assert params["client_id"] == "dynamic_agent_client"
    assert params["agent_name_hint"] == "TradingAgents"
    assert params["code_challenge_method"] == "S256"
    assert verifier not in json.dumps(params)
    connect(store)
    returning, _ = auth.authorization_parameters(store, params["redirect_uri"])
    assert returning["client_id"] == "oaiapp_a"
    assert "id_token_hint" not in returning and "agent_name_hint" not in returning
    assert returning["state"] != params["state"]


@pytest.mark.parametrize("query", [
    {"state": "wrong", "code": "one", "client_id": "oaiapp_a"},
    {"state": "state", "code": "one"},
    {"state": "state", "error": "access_denied"},
    {"state": "state", "client_id": "oaiapp_a"},
])
def test_callback_rejects_csrf_decline_or_missing_registration(query):
    with pytest.raises(SubscriptionError):
        auth.parse_callback("/auth/callback?" + urlencode(query),
                            {"state": "state", "client_id": "dynamic_agent_client"})


def test_callback_accepts_new_and_returning_registration():
    assert auth.parse_callback("/auth/callback?state=s&code=c&client_id=oaiapp_a",
                               {"state": "s", "client_id": "dynamic_agent_client"}) == ("oaiapp_a", "c")
    assert auth.parse_callback("/auth/callback?state=s&code=c",
                               {"state": "s", "client_id": "oaiapp_a"}) == ("oaiapp_a", "c")
    with pytest.raises(SubscriptionError):
        auth.parse_callback("/auth/callback?state=s&code=c&client_id=oaiapp_b",
                            {"state": "s", "client_id": "oaiapp_a"})


@pytest.fixture
def identity_key(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk["kid"] = "test-key"
    monkeypatch.setattr(auth, "_get_json", lambda url: (
        {"issuer": auth.AUTH_ORIGIN, "jwks_uri": auth.AUTH_ORIGIN + "/jwks"}
        if url == auth.DISCOVERY_URL else {"keys": [jwk]}
    ))
    return key


def signed_id(key, **overrides):
    claims = {"iss": auth.AUTH_ORIGIN, "aud": "oaiapp_a", "sub": "user-a",
              "iat": int(time.time()), "exp": int(time.time()) + 600, "nonce": "nonce", **overrides}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def test_identity_validates_signature_and_claims(identity_key):
    assert auth.validate_identity(signed_id(identity_key), "oaiapp_a", "nonce")["sub"] == "user-a"


@pytest.mark.parametrize("overrides", [{"iss": "https://evil.invalid"}, {"aud": "other-client"},
                                        {"exp": 0}, {"nonce": "wrong"}, {"sub": ""}])
def test_identity_rejects_wrong_claims(identity_key, overrides):
    with pytest.raises(SubscriptionError):
        auth.validate_identity(signed_id(identity_key, **overrides), "oaiapp_a", "nonce")


def test_identity_rejects_forged_signature(identity_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(SubscriptionError):
        auth.validate_identity(signed_id(other), "oaiapp_a", "nonce")


def test_returning_login_preserves_selected_account_and_scope(store):
    old = connect(store)
    with pytest.raises(SubscriptionError, match="selected account"):
        store.save_login(token(), "oaiapp_a", "nonce", {"nonce": "nonce", "sub": "other-user"})
    assert store.read() == old
    store.save_login(token(scope="openid email profile"), "oaiapp_a", "nonce",
                     {"nonce": "nonce", "sub": "user-a"})
    assert not store.status()["plan_usage_enabled"]
    with pytest.raises(SubscriptionError):
        store.preflight()


def test_profile_isolation_and_active_selection(store):
    connect(store)
    second = auth.ChatGPTAuthStore(profile="second")
    connect(second, client_id="oaiapp_b", subject="user-b")
    second.activate()
    assert auth.ChatGPTAuthStore().profile == "second"
    assert store.read()["client_id"] == "oaiapp_a"


@pytest.mark.parametrize("label", ["active", "host", "ACTIVE", "Host", "active.", "plus."])
def test_profile_names_cannot_overwrite_internal_registration_metadata(store, label):
    connect(store)
    store.activate()
    store.host_id()
    before = {path.name: path.read_bytes() for path in store.directory.glob("*.json")}
    with pytest.raises(ValueError, match="reserved"):
        auth.ChatGPTAuthStore(profile=label)
    assert {path.name: path.read_bytes() for path in store.directory.glob("*.json")} == before


def test_loopback_login_deadline_survives_a_stalled_http_peer(store):
    peers = []

    def stalled_peer(message):
        authorization = urlparse(message.split("Continue with ChatGPT: ", 1)[1])
        redirect = urlparse(parse_qs(authorization.query)["redirect_uri"][0])
        peer = socket.socket()
        peers.append(peer)
        _LOOPBACK_CONNECT(peer, ("127.0.0.1", redirect.port))
        peer.sendall(b"GET /auth/callback HTTP/1.1\r\n")  # never finishes headers

    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(auth.login, store, port=0, open_browser=False, timeout=0.2, announce=stalled_peer)
        try:
            with pytest.raises(SubscriptionError, match="timed out"):
                future.result(timeout=2)
        finally:
            for peer in peers:
                peer.close()
    assert not store.status()["connected"]


@pytest.mark.parametrize("query", ["state=%E9%8C%AF&code=c", "state=s&state=&code=c"])
def test_callback_rejects_unicode_and_blank_duplicate_state_safely(query):
    with pytest.raises(SubscriptionError, match="state"):
        auth.parse_callback("/auth/callback?" + query, {"state": "s", "client_id": "oaiapp_a"})


def test_logout_retries_network_failures_before_clearing_rotating_session(store, monkeypatch):
    connect(store)
    from .test_chatgpt_plan import Response

    calls = []
    monkeypatch.setattr(auth, "_get_json", lambda _: {"revocation_endpoint": auth.AUTH_ORIGIN + "/revoke"})
    monkeypatch.setattr(auth.time, "sleep", lambda _: None)

    def post(*args, **kwargs):
        calls.append(kwargs)
        assert store.read()["refresh_token"] == "refresh-secret"
        if len(calls) < 3:
            raise requests.ConnectionError("untrusted diagnostic refresh-secret")
        return Response(status=200)

    monkeypatch.setattr(auth.requests, "post", post)
    assert store.logout() and len(calls) == 3
    assert "refresh_token" not in store.read()


def test_token_admission_request_id_redacts_known_code_and_refresh_token(monkeypatch):
    from .test_chatgpt_plan import Response

    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: Response(
        status=401, body={"error": "invalid_grant"}, headers={"x-request-id": "opaque-renewal-secret"}))
    with pytest.raises(SubscriptionError) as error:
        auth._token_request({"grant_type": "refresh_token", "refresh_token": "opaque-renewal-secret"})
    assert error.value.request_id == "[REDACTED]"


def test_non_json_token_admission_keeps_auth_classification(monkeypatch):
    from .test_chatgpt_plan import Response

    class Admission(Response):
        def json(self):
            raise ValueError("opaque-renewal-secret")

    monkeypatch.setattr(auth.requests, "post", lambda *a, **k: Admission(status=401))
    with pytest.raises(SubscriptionError) as error:
        auth._token_request({"grant_type": "refresh_token", "refresh_token": "opaque-renewal-secret"})
    assert error.value.kind == "auth" and "opaque-renewal-secret" not in str(error.value)


@pytest.mark.parametrize("scopes", [None, auth.SCOPES, [{"scope": auth.DIRECT_SCOPE}], [auth.DIRECT_SCOPE]])
def test_status_and_activation_require_both_valid_granted_permissions(store, scopes):
    connect(store, scopes=scopes)
    assert not store.status()["plan_usage_enabled"]
    store.activate_if_enabled()
    assert not (store.directory / "active.json").exists()
    with pytest.raises(SubscriptionError, match="plan-use permission"):
        store.preflight()


def test_malformed_discovery_response_does_not_crash_identity_validation(monkeypatch):
    from .test_chatgpt_plan import Response

    monkeypatch.setattr(auth.requests, "get", lambda *a, **k: Response(body=[]))
    with pytest.raises(SubscriptionError) as error:
        auth.validate_identity("untrusted-identity-data", "oaiapp_a", "nonce")
    assert error.value.kind == "malformed_output" and "untrusted-identity-data" not in str(error.value)


@pytest.mark.parametrize("label", ["../auth", "..", "a/b", "", "a" * 65])
def test_invalid_profile_labels(store, label):
    if not label:  # empty means use the current default, not a path component
        return
    with pytest.raises(ValueError):
        auth.ChatGPTAuthStore(profile=label)


def test_diagnostics_redact_secrets():
    raw = {"access_token": "secret", "detail": "Bearer secret refresh_token=opaque",
           "nested": [{"id_token": "secret"}]}
    result = redact(raw, ("secret", "opaque"))
    assert "opaque" not in json.dumps(result) and '"secret"' not in json.dumps(result)
