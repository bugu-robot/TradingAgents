"""Official Antigravity CLI transport; signed-in personal allowance only.

The CLI owns credentials. Configuration ambiguity is an error, never permission
to use API billing or to replace an administrator's configuration.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .subscription_errors import SubscriptionError

VERIFIED_VERSION = "1.2.17"
REQUIRED_FLAGS = (
    "--print", "--input-format", "--output-format", "--json-schema", "--model",
    "--effort", "--agent", "--sandbox", "--print-timeout", "--log-file",
    "--disable-slash-commands",
)
DENY_ACTIONS = frozenset({
    "read_file(*)", "write_file(*)", "read_url(*)", "execute_url(*)",
    "command(*)", "unsandboxed(*)", "mcp(*)",
})
REQUIRED_SETTINGS = {
    "useG1Credits": False,
    "toolPermission": "strict",
    "allowNonWorkspaceAccess": False,
    "enableTerminalSandbox": True,
    "permissions": {"allow": [], "ask": [], "deny": sorted(DENY_ACTIONS)},
}
# Keep only reviewed non-routing OS/keyring variables. A denylist alone cannot
# cover future AGY gateway/ADC/provider switches. Never rewrite HOME/XDG paths.
_OS_ENV = frozenset({
    "HOME", "PATH", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR",
})
_DISPLAY_SETTINGS = frozenset({
    "colorScheme", "altScreenMode", "notifications", "editor", "editorMode",
    "vimInsertFirst", "verbosity", "runningLightSpeed", "showTips",
    "showFeedbackSurvey", "enableTelemetry", "copyOnSelect", "queuedMessages",
})
_ALLOWED_SETTINGS = frozenset(REQUIRED_SETTINGS) | _DISPLAY_SETTINGS


def _failure(message: str, kind: str = "configuration") -> SubscriptionError:
    return SubscriptionError(message, kind=kind)


def _child_environment() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in _OS_ENV}
    env.update(AGY_CLI_DISABLE_AUTO_UPDATE="true", CI="true", NO_BROWSER="true")
    return env


def _json_object(text: str) -> dict:
    """Strict JSON: duplicate keys and NaN/Infinity are protocol failures."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite JSON number")

    result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError("expected JSON object")
    return result


def _read_settings(path: Path) -> dict:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError("untrusted settings")
        # Reject writable config; another user must not be able to redirect an
        # inference after preflight. Values and paths never enter diagnostics.
        if os.name == "posix" and (path.stat().st_mode & 0o022 or path.stat().st_uid != os.getuid()):
            raise ValueError("untrusted owner/permissions")
        return _json_object(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise _failure("Antigravity settings are missing, malformed or unsafe. Review the subscription-only "
                       "settings in VERIFICATION.md; TradingAgents will not change global configuration.") from None


def _configuration_preflight() -> dict:
    """Validate real global settings before any auth/catalog/inference process."""
    home = Path.home()
    if os.environ.get("XDG_CONFIG_HOME") not in {None, "", str(home / ".config")}:
        raise _failure("Custom XDG configuration roots require a separate safety review.", "policy")
    settings_path = home / ".gemini/antigravity-cli/settings.json"
    settings = _read_settings(settings_path)
    if settings.get("modelProvider"):
        raise _failure("antigravity_cli requires signed-in Google personal subscription authentication; "
                       "API-key/Vertex/provider modes are prohibited. Remove the conflicting provider "
                       "yourself using the official CLI settings.", "auth")
    if set(settings) - _ALLOWED_SETTINGS:
        raise _failure("Unreviewed Antigravity routing, custom-model, hook or policy settings were detected. "
                       "Use a dedicated personal subscription account environment; no settings were changed.", "policy")
    for key, expected in REQUIRED_SETTINGS.items():
        if key == "permissions":
            continue
        value = settings.get(key)
        if value != expected or type(value) is not type(expected):
            raise _failure("Antigravity subscription-only mode requires explicit credits-overage off, "
                           "strict permissions, sandbox on and non-workspace access off. See VERIFICATION.md.", "policy")
    permissions = settings.get("permissions")
    if (not isinstance(permissions, dict) or set(permissions) != {"allow", "ask", "deny"}
            or permissions["allow"] != [] or permissions["ask"] != []
            or not isinstance(permissions["deny"], list)
            or not all(isinstance(v, str) for v in permissions["deny"])
            or not set(permissions["deny"]) >= DENY_ACTIONS):
        raise _failure("Antigravity must deny all files, commands, URLs, unsandboxed actions and MCP, "
                       "with no allow/ask grants. TradingAgents will not override policy.", "policy")

    # Shared customizations are loaded at startup, before model tools can be
    # denied. Reject them before spawning a process, including disabled entries.
    # Do not hide them by redirecting official configuration paths to temp files.
    for relative in (
        ".gemini/config", ".gemini/antigravity-cli/hooks.json",
        ".gemini/antigravity-cli/mcp_config.json", ".gemini/antigravity-cli/plugins",
        ".gemini/antigravity-cli/plugins.json", ".gemini/antigravity-cli/agents",
        ".gemini/antigravity-cli/skills", ".gemini/antigravity-cli/agent.json",
    ):
        path = home / relative
        try:
            present = path.is_symlink() or (path.is_dir() and any(path.iterdir())) or path.is_file()
        except OSError:
            present = True
        if present:
            raise _failure("Antigravity global customizations/MCP/plugins/hooks are present or unreadable. "
                           "A clean dedicated OS account is required; global files were not modified.", "policy")
    # Conservatively refuse credential/policy locations that could introduce
    # enterprise/provider routing. Only existence is checked; no tokens are read.
    for path in (
        home / ".config/gcloud/application_default_credentials.json",
        home / ".gemini/antigravity-cli/managed-settings.json",
        home / ".gemini/antigravity-cli/policy.json",
        Path("/etc/antigravity-cli"), Path("/etc/antigravity"),
    ):
        if path.exists() or path.is_symlink():
            raise _failure("ADC or unmanaged administrator-policy configuration is present. "
                           "Subscription-only safety cannot be established; no policy was bypassed.", "policy")
    return settings


def _diagnostic_error(stdout: str, stderr: str, code: int) -> SubscriptionError:
    """Classify locally, then discard raw diagnostics (including opaque tokens)."""
    text = (stdout + "\n" + stderr).lower()
    if any(x in text for x in ("quota exhausted", "quota exceeded", "out of credits", "no quota", "weekly limit", "resource_exhausted", "resourceexhausted")):
        kind, message = "quota", "Antigravity subscription quota is exhausted. Check official /usage; wait for reset. Credit/API fallback is disabled."
    elif any(x in text for x in ("not eligible", "ineligible", "subscription required", "plan required", "not entitled", "entitlement")):
        kind, message = "eligibility", "This Google account/model is not entitled to the required Antigravity subscription usage."
    elif any(x in text for x in ("authentication", "unauthenticated", "invalid_grant", "not signed in", "sign in", "login required", "401")):
        kind, message = "auth", "Antigravity cached Google sign-in is unavailable. Run agy interactively using the official SSH sign-in procedure."
    elif any(x in text for x in ("rate limit", "ratelimit", "429", "model_capacity_exhausted")):
        kind, message = "rate_limit", "Antigravity is temporarily rate limited."
    elif any(x in text for x in ("permission denied", "policy", "403")):
        kind, message = "permission", "Antigravity account or administrator policy denied this operation."
    elif any(x in text for x in ("unavailable", "503", "502", "connection reset")):
        kind, message = "transient", "Antigravity service is temporarily unavailable."
    else:
        kind, message = "cli_failure", "Antigravity failed; inspect authentication/configuration in its interactive CLI. Raw diagnostics were discarded."
    return SubscriptionError(message, kind=kind, details={"exit_code": code})


def _command(executable: str, args: list[str], *, timeout: float = 15) -> subprocess.CompletedProcess:
    try:
        with tempfile.TemporaryDirectory(prefix="tradingagents-agy-probe-") as cwd:
            return subprocess.run([executable, *args], stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, encoding="utf-8", errors="strict", timeout=timeout,
                                  env=_child_environment(), cwd=cwd, check=False)
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        raise _failure("Antigravity CLI probe timed out or could not start/decode. No inference was requested.") from None


def detect_cli(executable: str | None = None) -> tuple[str, str]:
    requested = executable or os.environ.get("TRADINGAGENTS_ANTIGRAVITY_CLI_BIN") or "agy"
    resolved = shutil.which(requested)
    if not resolved:
        raise _failure("Install the verified official Antigravity CLI 1.2.17 and put agy on PATH.")
    version = _command(resolved, ["--version"])
    if version.returncode or version.stdout.strip() != VERIFIED_VERSION:
        raise _failure("antigravity_cli requires the reviewed official CLI version 1.2.17. Unverified versions are refused.")
    help_ = _command(resolved, ["--help"])
    if help_.returncode or not all(re.search(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])", help_.stdout) for flag in REQUIRED_FLAGS):
        raise _failure("Antigravity CLI is missing required public headless/isolation/schema flags.")
    return resolved, VERIFIED_VERSION


def preflight(executable: str | None = None) -> tuple[str, str]:
    _configuration_preflight()
    return detect_cli(executable)


def model_options():
    """Official CLI catalog, not a claim of Google AI Pro model entitlement."""
    executable, _ = preflight()
    result = _command(executable, ["models"], timeout=30)
    if result.returncode:
        raise _diagnostic_error(result.stdout, result.stderr, result.returncode)
    options = []
    for line in result.stdout.splitlines():
        match = re.fullmatch(r"\s*(gemini-[a-z0-9][a-z0-9.-]*)\s+(.+?)\s*", line)
        if match:
            options.append((f"Antigravity {match[1]} (CLI catalog; verify plan access)", match[1]))
    if not options:
        raise _failure("Antigravity returned no readable Gemini model catalog. Authenticate interactively and check agy models.", "auth")
    return options
