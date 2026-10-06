"""Text-only adapter for official Gemini CLI cached personal Google sign-in.

The CLI's JSON envelope is not native structured output or LangChain tool calls.
TradingAgents therefore permits this provider in its deep tier only.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from contextlib import suppress
from functools import lru_cache
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from .base_client import BaseLLMClient
from .chatgpt_plan_client import _text
from .subscription_errors import SubscriptionError

_OAUTH = "oauth-personal"
_BILLING_ENV = frozenset({
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_GCA",
    "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_ACCESS_TOKEN", "GOOGLE_GEMINI_BASE_URL",
    "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT", "CLOUD_SHELL",
})


def _child_environment() -> dict:
    env = {key: value for key, value in os.environ.items() if key not in _BILLING_ENV}
    env.update(CI="true", NO_BROWSER="true")
    return env


@lru_cache(maxsize=8)
def _probe_cli(executable: str) -> str:
    """Probe documented flags/version without authenticating or consuming quota."""
    try:
        version = subprocess.run([executable, "--version"], stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=15, env=_child_environment(), check=False)
        match = re.search(r"(?m)^\s*(0\.62\.\d+)\s*$", version.stdout)
        if version.returncode != 0 or not match:
            raise SubscriptionError("gemini_cli requires the verified Gemini CLI 0.62.x protocol. "
                                    "Install @google/gemini-cli@0.62.0.", kind="configuration")
        help_ = subprocess.run([executable, "--help"], stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=15, env=_child_environment(), check=False)
        if help_.returncode or not all(flag in help_.stdout for flag in (
            "--prompt", "--output-format", "--model", "--skip-trust", "--approval-mode",
            "--extensions", "--allowed-mcp-server-names"
        )):
            raise SubscriptionError("Gemini CLI does not expose the required headless flags.", kind="configuration")
        return match[1]
    except (OSError, subprocess.TimeoutExpired):
        raise SubscriptionError("Cannot run Gemini CLI. Check its executable and Node.js >=20 installation.",
                                kind="configuration") from None


def detect_cli(executable: str | None = None) -> tuple[str, str]:
    executable = executable or os.environ.get("TRADINGAGENTS_GEMINI_CLI_BIN") or "gemini"
    resolved = shutil.which(executable)
    if not resolved:
        raise SubscriptionError("Gemini CLI is not installed. Install @google/gemini-cli@0.62.0 "
                                "and put gemini on PATH.", kind="configuration")
    return resolved, _probe_cli(resolved)


def preflight(executable: str | None = None) -> tuple[str, str]:
    cli = detect_cli(executable)
    home = Path(os.environ.get("GEMINI_CLI_HOME") or Path.home()) / ".gemini"
    try:
        settings = json.loads((home / "settings.json").read_text(encoding="utf-8"))
        auth = settings.get("security", {}).get("auth", {})
        if not isinstance(auth, dict):
            raise ValueError("Invalid authentication settings.")
    except (OSError, ValueError, AttributeError):
        raise SubscriptionError("No readable Gemini CLI authentication settings. Run gemini interactively "
                                "and select Sign in with Google using your Google AI Pro account.", kind="auth") from None
    if auth.get("selectedType") != _OAUTH or (auth.get("enforcedType") or _OAUTH) != _OAUTH or auth.get("useExternal"):
        raise SubscriptionError("gemini_cli requires cached Sign in with Google (oauth-personal), "
                                "not an API key, Vertex AI or external authentication.", kind="auth")
    # The CLI owns and refreshes its credentials. Never read or copy its tokens.
    # Encrypted/keyring storage has no oauth_creds.json; an account marker is
    # sufficient for a local preflight, with validity checked by the CLI itself.
    cached = (home / "oauth_creds.json").is_file()
    if os.environ.get("GEMINI_FORCE_ENCRYPTED_FILE_STORAGE") == "true":
        try:
            cached = bool(json.loads((home / "google_accounts.json").read_text(encoding="utf-8")).get("active"))
        except (OSError, ValueError, AttributeError):
            cached = False
    if not cached:
        raise SubscriptionError("No cached Google sign-in was detected. Run gemini interactively first. "
                                "Analysis never starts an interactive sign-in.", kind="auth")
    return cli


def model_options():
    # These are CLI selection aliases, not a claim of account entitlement.
    return [("Gemini CLI automatic model selection", "auto")]


def _conversation(messages) -> tuple[str, str]:
    instructions, history = [], []
    for message in messages:
        if isinstance(message, ToolMessage) or (isinstance(message, AIMessage) and (
            message.tool_calls or message.invalid_tool_calls
        )):
            raise ValueError("Gemini CLI text adapter cannot continue native tool calls.")
        role = "developer" if isinstance(message, SystemMessage) else (
            "user" if isinstance(message, HumanMessage) else "assistant" if isinstance(message, AIMessage)
            else message.role if isinstance(message, ChatMessage) else None
        )
        if role in {"system", "developer"}:
            instructions.append(_text(message.content))
        elif role in {"user", "assistant"}:
            history.append({"role": role, "content": _text(message.content)})
        else:
            raise ValueError("Unsupported Gemini CLI conversation role.")
    system = "You are a text-only TradingAgents assistant. Use only the supplied conversation and evidence. " \
             "Return the next assistant answer. Do not use external tools, files, shell, agents or web search.\n\n"
    system += "\n\n".join(instructions)
    # CLI accepts one headless prompt; preserve roles as explicit JSON history
    # rather than pretending its output envelope is a native chat protocol.
    # Escaped @ remains ordinary JSON text to the model, and cannot become a
    # CLI @file import while processing the supplied conversation.
    history_json = json.dumps(history, ensure_ascii=False).replace("@", "\\u0040")
    prompt = "Return the next assistant response to this conversation:\n" + history_json
    return system, prompt


def _cli_error(stdout: str, stderr: str, returncode: int) -> SubscriptionError:
    """Classify diagnostics internally; never expose untrusted CLI credential text."""
    diagnostic = (stdout + "\n" + stderr).lower()
    if any(term in diagnostic for term in ("terminalquotaerror", "daily quota", "daily limit", "quota exceeded",
                                          "quota exhausted", "exhausted your", "no quota remaining")):
        kind, message = "quota", "Google subscription quota is exhausted. Check Gemini CLI /stats and wait for the documented reset."
    elif any(term in diagnostic for term in ("fatalauthenticationerror", "invalid_grant", "manual authorization",
                                            "re-authenticate", "sign in", "authentication", "unauthenticated")):
        kind, message = "auth", "Gemini CLI cached sign-in is unavailable or expired. Run gemini interactively and select Sign in with Google."
    elif any(term in diagnostic for term in ("rate limit", "ratelimit", "retryablequotaerror", "429")):
        kind, message = "rate_limit", "Gemini CLI is rate limited; bounded retries were exhausted."
    elif any(term in diagnostic for term in ("resource_exhausted", "resourceexhausted")):
        kind, message = "quota", "Google subscription resources are exhausted. Review Gemini CLI quota before retrying."
    elif any(term in diagnostic for term in ("503", "502", "unavailable", "econnreset", "etimedout")):
        kind, message = "transient", "Gemini CLI service is temporarily unavailable."
    else:
        kind, message = "cli_failure", "Gemini CLI failed. Check its installation and Google subscription eligibility interactively."
    return SubscriptionError(message, kind=kind, details={"exit_code": returncode})


def _parse_output(stdout: str, stderr: str, returncode: int) -> str:
    if returncode:
        raise _cli_error(stdout, stderr, returncode)
    try:
        body = json.loads(stdout)
    except (ValueError, TypeError):
        raise SubscriptionError("Gemini CLI returned malformed JSON; no partial output was accepted.", kind="malformed_output") from None
    if not isinstance(body, dict):
        raise SubscriptionError("Gemini CLI returned an unexpected JSON envelope.", kind="malformed_output")
    if body.get("error"):
        raise _cli_error(stdout, stderr, returncode)
    response = body.get("response")
    try:
        tool_calls = body.get("stats", {}).get("tools", {}).get("totalCalls", 0)
    except AttributeError:
        raise SubscriptionError("Gemini CLI returned malformed statistics.", kind="malformed_output") from None
    if tool_calls:
        raise SubscriptionError("Gemini CLI unexpectedly executed internal tools; the text-only response was rejected.", kind="capability")
    if not isinstance(response, str) or not response.strip():
        raise SubscriptionError("Gemini CLI returned no completed text response.", kind="malformed_output")
    return response


def _terminate(process):
    if process.poll() is None:
        if os.name == "posix":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        try:
            process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.communicate()


def _run_process(command: list[str], prompt: str, *, cwd: str, env: dict,
                 timeout: float, cancellation: threading.Event) -> tuple[str, str, int]:
    if cancellation.is_set():
        raise SubscriptionError("Gemini CLI request cancelled.", kind="cancelled")
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env,
                                   start_new_session=os.name == "posix")
    except OSError:
        raise SubscriptionError("Cannot start Gemini CLI.", kind="configuration") from None
    deadline, input_ = time.monotonic() + timeout, prompt
    try:
        while True:
            if cancellation.is_set():
                raise SubscriptionError("Gemini CLI request cancelled.", kind="cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SubscriptionError("Gemini CLI request timed out.", kind="timeout")
            try:
                stdout, stderr = process.communicate(input=input_, timeout=min(remaining, 0.25))
                return stdout, stderr, process.returncode
            except subprocess.TimeoutExpired:
                input_ = None
    finally:
        _terminate(process)


_WORKSPACE_SETTINGS = {
    "security": {"auth": {"selectedType": _OAUTH, "enforcedType": _OAUTH, "useExternal": False},
                 "folderTrust": {"enabled": False}},
    "tools": {"core": [], "discoveryCommand": "", "callCommand": ""},
    "mcp": {"serverCommand": ""},
    "hooksConfig": {"enabled": False}, "skills": {"enabled": False},
    "experimental": {"enableAgents": False}, "ide": {"enabled": False},
    "context": {"fileName": "TRADINGAGENTS_NO_CONTEXT.md", "includeDirectoryTree": False, "includeDirectories": []},
    "model": {"maxSessionTurns": 1},
    "advanced": {"ignoreLocalEnv": True, "excludedEnvVars": sorted(_BILLING_ENV)},
    "privacy": {"usageStatisticsEnabled": False}, "telemetry": {"enabled": False},
    "billing": {"overageStrategy": "never"},
    "general": {"enableAutoUpdate": False, "enableAutoUpdateNotification": False},
}


class GeminiCLIChatModel(BaseChatModel):
    model_name: str = "auto"
    executable: str | None = None
    max_retries: int = Field(default=1, ge=0)
    timeout: float = Field(default=600, gt=0)

    @property
    def _llm_type(self):
        return "gemini_cli"

    @property
    def _identifying_params(self):
        return {"model_name": self.model_name}

    def bind_tools(self, tools, **kwargs):
        raise NotImplementedError("Gemini CLI JSON does not expose native bind_tools/ToolMessage continuation. Use gemini_cli in the deep tier.")

    def with_structured_output(self, schema, **kwargs):
        raise NotImplementedError("Gemini CLI JSON wraps plain text; native structured output is unavailable. TradingAgents uses its existing free-text fallback.")

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        cancellation = kwargs.pop("cancellation_event", None) or threading.Event()
        if stop or kwargs:
            raise ValueError("Unsupported Gemini CLI generation parameters.")
        executable, version = preflight(self.executable)
        system, prompt = _conversation(messages)
        with tempfile.TemporaryDirectory(prefix="tradingagents-gemini-") as workdir:
            root = Path(workdir)
            (root / ".gemini").mkdir(mode=0o700)
            (root / ".gemini" / "settings.json").write_text(json.dumps(_WORKSPACE_SETTINGS), encoding="utf-8")
            # Stop the CLI walking up to a home/repository .env and restoring
            # an API/ADC override that was removed from the child environment.
            (root / ".gemini" / ".env").touch(mode=0o600)
            system_path = root / "system.md"
            system_path.write_text(system, encoding="utf-8")
            system_path.chmod(0o600)
            env = _child_environment()
            env["GEMINI_SYSTEM_MD"] = str(system_path)
            # Keep caller-wide overrides out of this isolated personal-account
            # invocation. CLI 0.62 ignores insecure system files and overwrites
            # local admin.* fields with remote admin defaults; neither can be
            # used to disable extensions/MCP. Use the documented flags below.
            defaults_path = root / "defaults.json"
            defaults_path.write_text("{}", encoding="utf-8")
            env["GEMINI_CLI_SYSTEM_SETTINGS_PATH"] = str(defaults_path)
            env["GEMINI_CLI_SYSTEM_DEFAULTS_PATH"] = str(defaults_path)
            command = [executable, "--prompt", "Answer the supplied conversation.", "--output-format", "json",
                       "--model", self.model_name, "--skip-trust", "--approval-mode", "default",
                       "--extensions", "none", "--allowed-mcp-server-names", root.name]
            # A nonempty allowlist containing this unique, unconfigured workspace
            # name blocks discovery/startup of every cached MCP server. An empty
            # allowlist means allow all in CLI 0.62 and must not be used here.
            for attempt in range(self.max_retries + 1):
                try:
                    stdout, stderr, code = _run_process(command, prompt, cwd=workdir, env=env,
                                                       timeout=self.timeout, cancellation=cancellation)
                    answer = _parse_output(stdout, stderr, code)
                    message = AIMessage(content=answer, response_metadata={"provider": "gemini_cli", "model_name": self.model_name, "cli_version": version})
                    return ChatResult(generations=[ChatGeneration(message=message)])
                except SubscriptionError as exc:
                    if not exc.retryable or attempt == self.max_retries:
                        raise
                if cancellation.wait(min(2 ** attempt, 30)):
                    raise SubscriptionError("Gemini CLI request cancelled.", kind="cancelled")
        raise AssertionError("unreachable")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        cancellation = kwargs.pop("cancellation_event", None) or threading.Event()
        task = asyncio.create_task(asyncio.to_thread(self._generate, messages, stop, None,
                                                    cancellation_event=cancellation, **kwargs))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            cancellation.set()
            with suppress(SubscriptionError):
                await asyncio.shield(task)
            raise


class GeminiCLIClient(BaseLLMClient):
    provider = "gemini_cli"

    def get_llm(self):
        if self.base_url:
            raise ValueError("gemini_cli uses the official CLI; a backend URL is not accepted.")
        if set(self.kwargs) - {"max_retries", "timeout", "executable", "callbacks"}:
            raise ValueError("Gemini CLI does not accept API keys, sampling settings or output caps.")
        if not self.validate_model():
            raise ValueError("Choose auto or a model supported by your signed-in Gemini CLI account.")
        return GeminiCLIChatModel(model_name=self.model, **self.kwargs)

    def validate_model(self):
        return bool(self.model and re.fullmatch(r"[A-Za-z0-9._:/-]+", self.model) and not self.model.startswith("-") and self.model != "custom")
