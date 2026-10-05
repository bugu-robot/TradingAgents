"""Offline OAuth identity, rotation and credential-isolation coverage."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from tradingagents.llm_clients import chatgpt_plan_auth as auth
from tradingagents.llm_clients.subscription_errors import SubscriptionError, redact


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
