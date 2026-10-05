"""Safe, actionable subscription failures; never switch to API billing."""

from __future__ import annotations

import re
from typing import Any

USAGE_URL = "https://chatgpt.com/#settings/Usage"
_SECRET_KEYS = re.compile(r"token|authorization|cookie|password|secret|api.?key|code_verifier|id_token_hint", re.I)
_BEARER = re.compile(r"(?i)Bearer\s+[^\s\"',;]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Redact credentials from diagnostics, including unstructured CLI errors."""
    if isinstance(value, dict):
        return {k: "[REDACTED]" if _SECRET_KEYS.search(str(k)) else redact(v, secrets)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    if not isinstance(value, str):
        return value
    for secret in secrets:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _JWT.sub("[REDACTED]", value)
    value = re.sub(r"(?i)(access_token|refresh_token|id_token|id_token_hint|api_key|authorization)"
                   r"([\s\"':=]+)([^\s\"',;&}]+)", r"\1\2[REDACTED]", value)
    return value


class SubscriptionError(RuntimeError):
    """Failure classification without credentials or raw exception strings."""

    def __init__(self, message: str, *, kind: str, code: str | None = None,
                 status: int | None = None, request_id: str | None = None,
                 retry_after: float | None = None, details: Any = None):
        super().__init__(redact(message))
        self.kind = kind
        self.code = code
        self.status = status
        self.request_id = redact(request_id)
        self.retry_after = retry_after
        self.details = redact(details)

    @property
    def retryable(self) -> bool:
        return self.kind in {"rate_limit", "transient", "timeout", "interrupted"}


_QUOTA_CODES = {"subscription_sharing_usage_limit_exceeded", "insufficient_quota"}
_AUTH_CODES = {"subscription_sharing_invalid_user", "chatpass_v2_scope_not_authorized",
               "chatpass_v2_invalid_authorization_context", "invalid_grant", "invalid_client"}


def response_error(body: Any, *, status: int | None = None,
                   request_id: str | None = None, retry_after: float | None = None,
                   secrets: tuple[str, ...] = ()) -> SubscriptionError:
    """Handle both Responses error objects and direct-admission detail bodies."""
    body = body if isinstance(body, dict) else {}
    error = body.get("error") or body
    if isinstance(error, str):
        error = {"code": error}  # OAuth errors use a string, Responses uses an object.
    error = error if isinstance(error, dict) else {}
    raw_code = error.get("code")
    code = redact(str(raw_code), secrets) if raw_code else None
    if code in _QUOTA_CODES:
        kind, message = "quota", f"ChatGPT plan usage limit reached. Manage usage: {USAGE_URL}"
    elif code == "subscription_sharing_user_not_eligible":
        kind, message = "eligibility", "This ChatGPT account/workspace is not eligible for plan usage."
    elif code == "subscription_sharing_unsupported_capability":
        kind, message = "capability", "ChatGPT plan rejected a capability; inspect the redacted error.param."
    elif code == "subscription_sharing_route_not_supported":
        kind, message = "capability", "ChatGPT plan does not support this route."
    elif code in _AUTH_CODES or status == 401:
        kind, message = "auth", "ChatGPT authorization failed. Run: tradingagents auth login chatgpt_plan"
    elif status == 403:
        kind, message = "permission", "ChatGPT plan access is restricted by account, workspace or region policy."
    elif status == 429 or code in {"rate_limit_exceeded", "rate_limit_error"}:
        kind, message = "rate_limit", "ChatGPT plan is temporarily rate limited."
    elif status and status >= 500 or code in {
        "subscription_sharing_usage_unavailable", "subscription_sharing_user_unavailable",
        "server_error", "service_unavailable",
    }:
        kind, message = "transient", "ChatGPT plan service is temporarily unavailable."
    else:
        kind, message = "request", "ChatGPT plan request failed; inspect the redacted diagnostic fields."
    return SubscriptionError(message, kind=kind, code=code, status=status,
                             request_id=request_id, retry_after=retry_after,
                             details=redact(body, secrets))
