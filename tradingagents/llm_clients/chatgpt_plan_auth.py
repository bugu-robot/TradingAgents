"""Official Sign in with ChatGPT public-client OAuth and protected profiles.

This owns app-specific SIWC credentials; it does not read Codex/browser caches.
See docs/subscription-architecture-review.md for the official protocol sources.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import math
import os
import re
import secrets
import stat
import tempfile
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .subscription_errors import SubscriptionError, response_error
from .subscription_json import json_object

AUTH_ORIGIN = "https://auth.openai.com"
AUTHORIZE_URL = f"{AUTH_ORIGIN}/api/accounts/authorize"
TOKEN_URL = f"{AUTH_ORIGIN}/api/accounts/oauth/token"
DISCOVERY_URL = f"{AUTH_ORIGIN}/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
DIRECT_SCOPE = "chatgpt.tokens.use.direct"
_PROFILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_TOKEN_KEYS = {"access_token", "refresh_token", "id_token", "expires_at", "scopes"}
_TERMINAL_REFRESH = {"invalid_grant", "invalid_refresh_token", "token_expired",
                     "refresh_token_expired", "refresh_token_invalidated", "refresh_token_reused"}


def _auth_error(message: str) -> SubscriptionError:
    return SubscriptionError(message, kind="auth")


def _has_plan_permission(scopes) -> bool:
    return (isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes)
            and {DIRECT_SCOPE, "resource.invoke"} <= set(scopes))


def _read_json(path: Path) -> dict:
    _protected_directory(path.parent)
    if path.is_symlink():
        raise _auth_error("Subscription credential files must not be symbolic links.")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024
                    or (os.name != "nt" and (info.st_mode & 0o077 or info.st_uid != os.getuid()))):
                raise _auth_error("Credential file ownership/permissions must be owner-only (chmod 600).")
            value = json_object(handle.read(1024 * 1024 + 1))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise _auth_error("Subscription credential data is invalid or unreadable; run tradingagents auth login chatgpt_plan.") from None
    if not isinstance(value, dict):
        raise _auth_error("Subscription credential record must be a JSON object.")
    return value


def _protected_directory(path: Path, *, create: bool = False) -> None:
    try:
        if create:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink():
            raise _auth_error("Subscription storage directories must not be symbolic links.")
        if path.exists():
            info = path.stat()
            if (not stat.S_ISDIR(info.st_mode)
                    or (os.name != "nt" and (info.st_mode & 0o077 or info.st_uid != os.getuid()))):
                raise _auth_error("Subscription storage ownership/permissions must be owner-only (chmod 700).")
    except OSError:
        raise _auth_error("Cannot access protected subscription storage.") from None


def _write_json(path: Path, value: dict) -> None:
    _protected_directory(path.parent, create=True)
    fd, temporary = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def _file_lock(path: Path):
    """Serialize rotating-token reads/writes across threads and processes."""
    _protected_directory(path.parent)
    if path.is_symlink():
        raise _auth_error("Subscription rotation locks must not be symbolic links.")
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        raise _auth_error("Cannot safely open subscription rotation lock.") from None
    with os.fdopen(fd, "r+b") as handle:
        info = os.fstat(handle.fileno())
        if (not stat.S_ISREG(info.st_mode)
                or (os.name != "nt" and (info.st_mode & 0o077 or info.st_uid != os.getuid()))):
            raise _auth_error("Subscription lock ownership/permissions must be owner-only.")
        if os.name == "nt":
            import msvcrt
            handle.write(b"\0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _trusted_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "auth.openai.com" or parsed.fragment:
        raise _auth_error("OpenAI discovery returned an unexpected authentication endpoint.")
    return url


class ChatGPTAuthStore:
    """Each profile keeps its issued client ID bound to its verified subject."""

    def __init__(self, directory: str | Path | None = None, profile: str | None = None):
        configured = directory or os.environ.get("TRADINGAGENTS_CHATGPT_AUTH_DIR")
        self.directory = Path(configured or Path.home() / ".config/tradingagents/chatgpt_plan")
        self.profile = profile or os.environ.get("TRADINGAGENTS_CHATGPT_PROFILE") or self.active_profile()
        if (not isinstance(self.profile, str) or not _PROFILE.fullmatch(self.profile)
                or ".." in self.profile or self.profile.endswith(".")
                or self.profile.casefold() in {"active", "host"}):
            raise ValueError("Profile labels must be 1-64 safe letters, digits, dots, underscores or hyphens; "
                             "active, host and trailing dots are reserved.")
        self.path = self.directory / f"{self.profile}.json"

    def __repr__(self):
        return f"ChatGPTAuthStore(profile={self.profile!r})"

    def active_profile(self) -> str:
        return _read_json(self.directory / "active.json").get("profile", "default")

    def _prepare_directory(self):
        _protected_directory(self.directory, create=True)

    @contextlib.contextmanager
    def locked(self):
        self._prepare_directory()
        with _file_lock(self.directory / f"{self.profile}.lock"):
            yield

    def host_id(self) -> str:
        self._prepare_directory()
        with _file_lock(self.directory / "host.lock"):
            host = _read_json(self.directory / "host.json")
            if not host:
                host = {"ext_agent_host_id": f"urn:uuid:{uuid.uuid4()}"}
                _write_json(self.directory / "host.json", host)
            return host["ext_agent_host_id"]

    def read(self) -> dict:
        return _read_json(self.path)

    def activate(self) -> None:
        self.preflight()
        _write_json(self.directory / "active.json", {"profile": self.profile})

    def status(self) -> dict:
        record = self.read()
        return {"profile": self.profile, "email": record.get("email"),
                "connected": bool(record.get("access_token")),
                "plan_usage_enabled": _has_plan_permission(record.get("scopes")),
                "expires_at": record.get("expires_at")}

    def preflight(self) -> dict:
        record = self.read()
        if not all(isinstance(record.get(k), str) and record[k] for k in ("client_id", "subject", "access_token")):
            raise _auth_error("No ChatGPT Plan login. Run: tradingagents auth login chatgpt_plan")
        if record["client_id"] == "dynamic_agent_client" or record.get("issuer") != AUTH_ORIGIN:
            raise _auth_error("ChatGPT credential registration is invalid; sign in again.")
        if not _has_plan_permission(record.get("scopes")):
            raise _auth_error("ChatGPT sign-in has no plan-use permission. Sign in again and enable ChatGPT plan usage.")
        try:
            expires = float(record.get("expires_at", 0))
        except (TypeError, ValueError):
            raise _auth_error("ChatGPT credential expiry is invalid; sign in again.") from None
        if not math.isfinite(expires):
            raise _auth_error("ChatGPT credential expiry is invalid; sign in again.")
        if expires <= time.time() + 60 and not record.get("refresh_token"):
            raise _auth_error("ChatGPT session expired and cannot be renewed; sign in again.")
        return record

    def access_token(self) -> str:
        with self.locked():
            record = self.preflight()
            if float(record["expires_at"]) > time.time() + 60:
                return record["access_token"]
            earliest = record.get("earliest_refresh_at", 0)
            try:
                earliest = float(earliest or 0)
            except (TypeError, ValueError):
                raise _auth_error("ChatGPT renewal metadata is invalid; sign in again.") from None
            if not math.isfinite(earliest):
                raise _auth_error("ChatGPT renewal metadata is invalid; sign in again.")
            if earliest > time.time():
                raise SubscriptionError("ChatGPT token renewal is not yet available; retry later.", kind="transient")
            try:
                token = _token_request({"grant_type": "refresh_token", "client_id": record["client_id"],
                                        "refresh_token": record["refresh_token"], "resource": RESOURCE})
            except SubscriptionError as exc:
                if exc.code in _TERMINAL_REFRESH:
                    _write_json(self.path, {k: v for k, v in record.items() if k not in _TOKEN_KEYS})
                raise
            renewed = _token_record(record, token)
            _write_json(self.path, renewed)
            # Save the rotating replacement before rejecting a revoked grant.
            # Never send inference using scopes removed by a successful refresh.
            self.preflight()
            return renewed["access_token"]

    def remember_registration(self, client_id: str) -> None:
        """Retain an issued registration if the first code exchange is interrupted.

        This pending profile has no identity or tokens and cannot be activated.
        Existing, validated account records are never replaced here.
        """
        with self.locked():
            old = self.read()
            if old.get("client_id") and old["client_id"] != client_id:
                raise _auth_error("Issued client ID did not match the selected registration.")
            if not old:
                _write_json(self.path, {"client_id": client_id, "issuer": AUTH_ORIGIN})

    def save_login(self, token: dict, client_id: str, nonce: str, identity: dict) -> None:
        """Identity is supplied only after OIDC signature/claims validation."""
        if not secrets.compare_digest(str(identity.get("nonce", "")), nonce):
            raise _auth_error("ChatGPT identity nonce did not match the authorization attempt.")
        with self.locked():
            old = self.read()
            if old and (old.get("client_id") != client_id or (
                old.get("subject") and old["subject"] != identity["sub"]
            )):
                raise _auth_error("Returning sign-in did not match the selected account. Use a new profile label.")
            record = {"client_id": client_id, "subject": identity["sub"], "issuer": AUTH_ORIGIN,
                      "email": identity.get("email")}
            _write_json(self.path, _token_record(record, token))
        self.activate_if_enabled()

    def activate_if_enabled(self):
        if _has_plan_permission(self.read().get("scopes")):
            _write_json(self.directory / "active.json", {"profile": self.profile})

    def logout(self) -> bool:
        """Revoke then clear this session; preserve registration and host ID."""
        with self.locked():
            record = self.read()
            confirmed = not record.get("refresh_token")
            if not confirmed:
                endpoint = None
                for attempt in range(3):
                    try:
                        if endpoint is None:
                            discovery = _get_json(DISCOVERY_URL)
                            endpoint = _trusted_url(discovery["revocation_endpoint"])
                        with requests.post(endpoint, data={"token": record["refresh_token"],
                                           "token_type_hint": "refresh_token", "client_id": record["client_id"]},
                                           timeout=20, allow_redirects=False) as response:
                            confirmed = response.status_code == 200
                            if confirmed or response.status_code < 500:
                                break
                    except (requests.RequestException, SubscriptionError) as exc:
                        if isinstance(exc, SubscriptionError) and not exc.retryable:
                            break
                    except KeyError:
                        break
                    if attempt < 2:
                        time.sleep(0.5 * (2 ** attempt))
            _write_json(self.path, {k: v for k, v in record.items() if k not in _TOKEN_KEYS})
            return confirmed


def _token_record(record: dict, token: dict) -> dict:
    if not all(isinstance(token.get(k), str) and token[k] for k in ("access_token", "refresh_token")):
        raise _auth_error("OpenAI did not return a complete renewable token set; sign in again.")
    try:
        lifetime = float(token["expires_in"])
    except (KeyError, TypeError, ValueError):
        raise _auth_error("OpenAI did not return a valid token lifetime.") from None
    if not math.isfinite(lifetime) or lifetime <= 0 or str(token.get("token_type", "")).lower() != "bearer":
        raise _auth_error("OpenAI returned invalid token metadata.")
    scopes = token.get("scope")
    if "scope" in token and not isinstance(scopes, str):
        raise _auth_error("OpenAI returned invalid granted scopes.")
    scopes = scopes.split() if isinstance(scopes, str) else record.get("scopes", [])
    return {**record, "access_token": token["access_token"], "refresh_token": token["refresh_token"],
            "id_token": token.get("id_token") or record.get("id_token"), "token_type": "Bearer",
            "expires_at": time.time() + lifetime, "scopes": scopes,
            "earliest_refresh_at": token.get("earliest_refresh_at", 0)}


def _get_json(url: str) -> dict:
    try:
        with requests.get(_trusted_url(url), timeout=20, allow_redirects=False) as response:
            if response.status_code != 200:
                raise SubscriptionError("OpenAI identity metadata is unavailable.", kind="transient")
            body = response.json()
            if not isinstance(body, dict):
                raise SubscriptionError("OpenAI returned malformed identity metadata.", kind="malformed_output")
            return body
    except (requests.RequestException, ValueError):
        raise SubscriptionError("Cannot retrieve OpenAI identity metadata.", kind="transient") from None


def _token_request(data: dict) -> dict:
    try:
        with requests.post(TOKEN_URL, data=data, timeout=20, allow_redirects=False) as response:
            try:
                body = response.json()
            except ValueError:
                if response.status_code == 200:
                    raise _auth_error("OpenAI returned malformed token data.") from None
                body = {"detail": "Non-JSON token admission error."}
            if response.status_code != 200:
                raise response_error(body, status=response.status_code,
                                     request_id=response.headers.get("x-request-id"),
                                     secrets=tuple(str(data[k]) for k in ("refresh_token", "code", "code_verifier") if k in data))
            if not isinstance(body, dict):
                raise _auth_error("OpenAI returned malformed token data.")
            return body
    except (requests.RequestException, ValueError):
        raise SubscriptionError("ChatGPT token exchange is temporarily unavailable.", kind="transient") from None


def validate_identity(id_token: str, client_id: str, nonce: str) -> dict:
    import jwt

    discovery = _get_json(DISCOVERY_URL)
    if discovery.get("issuer") != AUTH_ORIGIN:
        raise _auth_error("OpenAI discovery issuer did not match.")
    try:
        jwks = jwt.PyJWKSet.from_dict(_get_json(discovery["jwks_uri"]))
        header = jwt.get_unverified_header(id_token)
        key = next(k for k in jwks.keys if k.key_id == header.get("kid"))
        claims = jwt.decode(id_token, key.key, algorithms=["RS256"], audience=client_id,
                            issuer=AUTH_ORIGIN, options={"require": ["sub", "exp", "iat", "iss", "aud", "nonce"]})
        if not isinstance(claims["sub"], str) or not claims["sub"] or not secrets.compare_digest(claims["nonce"], nonce):
            raise _auth_error("ChatGPT identity did not match the authorization attempt.")
        return claims
    except (jwt.PyJWTError, KeyError, StopIteration, TypeError):
        raise _auth_error("ChatGPT ID token signature or claims failed validation.") from None


def authorization_parameters(store: ChatGPTAuthStore, redirect_uri: str, *, enable_plan_usage: bool = False):
    record = store.read()
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    parameters = {"client_id": record.get("client_id") or "dynamic_agent_client",
                  "ext_agent_host_id": store.host_id(), "response_type": "code", "redirect_uri": redirect_uri,
                  "scope": SCOPES, "resource": RESOURCE, "state": state, "nonce": nonce,
                  "code_challenge_method": "S256", "code_challenge": challenge}
    if not record.get("client_id"):
        parameters["agent_name_hint"] = "TradingAgents"
    elif enable_plan_usage:
        # Explicit user action only. The official prompt=consent path is
        # supported before per-integration force_reconsent rollout.
        parameters["prompt"] = "consent"
    # Omit id_token_hint so terminal URLs never reveal an ID token. The official
    # returning sign-in without a hint displays the account selector instead.
    return parameters, verifier


def parse_callback(path: str, parameters: dict) -> tuple[str, str]:
    parsed = urlparse(path)
    if parsed.path != "/auth/callback":
        raise _auth_error("Unexpected OAuth callback path.")
    query = parse_qs(parsed.query, keep_blank_values=True)
    if any(len(v) != 1 for v in query.values()) or not secrets.compare_digest(
        query.get("state", [""])[0].encode(), parameters["state"].encode()
    ):
        raise _auth_error("OAuth callback state did not match.")
    if "error" in query:
        raise _auth_error("ChatGPT authorization was declined or failed. Existing profiles were preserved.")
    issued = query.get("client_id", [parameters["client_id"]])[0]
    if issued == "dynamic_agent_client" or not issued or (
        parameters["client_id"] != "dynamic_agent_client" and issued != parameters["client_id"]
    ):
        raise _auth_error("OAuth callback has a missing or mismatched issued client ID.")
    code = query.get("code", [""])[0]
    if not code:
        raise _auth_error("OAuth callback did not include an authorization code.")
    return issued, code


def login(store: ChatGPTAuthStore, *, port: int = 1455, open_browser: bool = True,
          timeout: float = 300, enable_plan_usage: bool = False, announce=print) -> dict:
    """Explicit interactive step; ordinary provider invocation never calls this."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("OAuth login timeout must be finite and positive.")
    received = {}

    class LoopbackServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            # HTTPServer.timeout only bounds accept(), not a peer that connects
            # and stalls while sending headers. Bound each accepted socket too.
            connection.settimeout(max(0.001, min(1.0, deadline - time.monotonic())))
            return connection, address

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                issued, code = parse_callback(self.path, parameters)
                received.update(client_id=issued, code=code)
                status, body = 200, b"Authorization received. Return to TradingAgents."
            except SubscriptionError:
                status, body = 400, b"Authorization callback was not accepted. Return to TradingAgents."
                if urlparse(self.path).path == "/auth/callback":
                    query = parse_qs(urlparse(self.path).query)
                    if query.get("state", [""])[0] == parameters["state"]:
                        received["error"] = True
            with contextlib.suppress(OSError):
                self.send_response(status)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, *args):
            pass  # Callback URLs contain the authorization code.

    try:
        server = LoopbackServer(("127.0.0.1", port), Callback)
    except OSError:
        raise _auth_error("Cannot bind the OAuth loopback listener. Choose a free --port.") from None
    with server:
        deadline = time.monotonic() + timeout
        redirect = f"http://127.0.0.1:{server.server_port}/auth/callback"
        parameters, verifier = authorization_parameters(store, redirect, enable_plan_usage=enable_plan_usage)
        url = AUTHORIZE_URL + "?" + urlencode(parameters)
        announce("Continue with ChatGPT: " + url)
        if open_browser:
            webbrowser.open(url)
        while not received and time.monotonic() < deadline:
            server.timeout = max(0.001, min(1.0, deadline - time.monotonic()))
            server.handle_request()
        if not received:
            raise _auth_error("ChatGPT sign-in timed out; existing profiles were preserved.")
        if received.get("error"):
            raise _auth_error("ChatGPT sign-in was declined or callback validation failed.")
    store.remember_registration(received["client_id"])
    token = _token_request({"grant_type": "authorization_code", "client_id": received["client_id"],
                            "code": received["code"], "code_verifier": verifier,
                            "redirect_uri": redirect, "resource": RESOURCE})
    identity = validate_identity(token.get("id_token", ""), received["client_id"], parameters["nonce"])
    store.save_login(token, received["client_id"], parameters["nonce"], identity)
    return store.status()
