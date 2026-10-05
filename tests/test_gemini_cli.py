"""Offline official CLI protocol, auth preflight and process-lifecycle tests."""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage

from tradingagents.llm_clients import gemini_cli_client as cli
from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.subscription_errors import SubscriptionError


@pytest.fixture
def google_home(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_CLI_HOME", str(tmp_path))
    monkeypatch.delenv("GEMINI_FORCE_ENCRYPTED_FILE_STORAGE", raising=False)
    home = tmp_path / ".gemini"
    home.mkdir()
    (home / "settings.json").write_text(json.dumps({"security": {"auth": {"selectedType": "oauth-personal"}}}))
    (home / "oauth_creds.json").write_text("SECRET CACHE MUST NOT BE READ BY ADAPTER")
    monkeypatch.setattr(cli, "detect_cli", lambda *a: ("/verified/gemini", "0.62.0"))
    return home


@pytest.fixture
def model(google_home):
    return create_llm_client("gemini_cli", "auto", max_retries=0).get_llm()


def test_registered_keyless_cli(model):
    assert model._llm_type == "gemini_cli" and get_api_key_env("gemini_cli") is None
    assert cli.preflight() == ("/verified/gemini", "0.62.0")


def test_missing_executable_is_actionable(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda *a: None)
    with pytest.raises(SubscriptionError, match="not installed"):
        cli.detect_cli()


def test_official_flags_and_version_probe_is_noninteractive(monkeypatch):
    cli._probe_cli.cache_clear()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="0.62.0\n" if command[-1] == "--version" else
                               "--prompt --output-format --model --skip-trust --approval-mode")

    monkeypatch.setattr(cli.subprocess, "run", run)
    assert cli._probe_cli("/probe/gemini") == "0.62.0"
    assert len(calls) == 2
    assert all(c[1]["stdin"] == subprocess.DEVNULL and c[1]["env"]["NO_BROWSER"] == "true" for c in calls)


@pytest.mark.parametrize("version", ["0.10.0", "0.63.0", "0.62.0-preview", "secret-value"])
def test_unverified_cli_versions_do_not_run_inference(monkeypatch, version):
    cli._probe_cli.cache_clear()
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=version))
    with pytest.raises(SubscriptionError) as error:
        cli._probe_cli("/probe/gemini")
    assert error.value.kind == "configuration" and "secret-value" not in str(error.value)


@pytest.mark.parametrize("auth", [{"selectedType": "gemini-api-key"}, {"selectedType": "vertex-ai"},
                                  {"selectedType": "oauth-personal", "enforcedType": "gemini-api-key"},
                                  {"selectedType": "oauth-personal", "useExternal": True}])
def test_api_vertex_and_external_auth_are_rejected(google_home, auth):
    (google_home / "settings.json").write_text(json.dumps({"security": {"auth": auth}}))
    with pytest.raises(SubscriptionError) as error:
        cli.preflight()
    assert error.value.kind == "auth"


def test_missing_cache_rejected_before_inference(model, google_home, monkeypatch):
    (google_home / "oauth_creds.json").unlink()
    monkeypatch.setattr(cli, "_run_process", lambda *a, **k: pytest.fail("must not start child"))
    with pytest.raises(SubscriptionError, match="cached Google"):
        model.invoke("hello")


def test_encrypted_keyring_cache_uses_account_marker_without_reading_tokens(google_home, monkeypatch):
    (google_home / "oauth_creds.json").unlink()
    monkeypatch.setenv("GEMINI_FORCE_ENCRYPTED_FILE_STORAGE", "true")
    (google_home / "google_accounts.json").write_text('{"active":"pro@example.invalid"}')
    assert cli.preflight()[1] == "0.62.0"


def test_malformed_settings_never_print_credentials(google_home):
    (google_home / "settings.json").write_text("access_token=SECRET")
    with pytest.raises(SubscriptionError) as error:
        cli.preflight()
    assert "SECRET" not in str(error.value)


def test_headless_invoke_isolated_settings_stdin_history_no_api_fallback(model, monkeypatch):
    requests = []
    for key in cli._BILLING_ENV:
        monkeypatch.setenv(key, "billing-secret")
    original = dict(os.environ)

    def run(command, prompt, **kwargs):
        root = Path(kwargs["cwd"])
        env = kwargs["env"]
        settings = json.loads((root / ".gemini" / "settings.json").read_text())
        requests.append((command, prompt, kwargs, settings, Path(env["GEMINI_SYSTEM_MD"]).read_text()))
        assert all(key not in env for key in cli._BILLING_ENV)
        assert env["CI"] == env["NO_BROWSER"] == "true"
        assert settings["tools"]["core"] == [] and settings["hooksConfig"]["enabled"] is False
        assert settings["admin"]["mcp"]["enabled"] is False
        assert settings["security"]["auth"]["enforcedType"] == "oauth-personal"
        assert (root / ".gemini" / ".env").read_text() == ""
        assert Path(env["GEMINI_CLI_SYSTEM_SETTINGS_PATH"]).is_file()
        return json.dumps({"response": "Deep review", "stats": {"tools": {"totalCalls": 0}}}), "ignored secret diagnostic", 0

    monkeypatch.setattr(cli, "_run_process", run)
    result = model.invoke([SystemMessage("system instructions"), ChatMessage(role="developer", content="developer instructions"),
                           HumanMessage("first"), AIMessage("prior"), HumanMessage("next")])
    assert result.content == "Deep review" and result.tool_calls == []
    command, prompt, options, _, system = requests[0]
    assert "first" not in command and "next" not in command and "--output-format" in command
    assert "system instructions" in system and "developer instructions" in system
    assert [m["role"] for m in json.loads(prompt.split("\n", 1)[1])] == ["user", "assistant", "user"]
    assert not Path(options["cwd"]).exists() and dict(os.environ) == original
    assert "secret" not in repr(result)


@pytest.mark.parametrize("stdout", ["not-json", "{}", "[]", '{"response":123}', '{"response":""}',
                                     'notice\n{"response":"partial"}', '{"response":"OK","stats":[]}'])
def test_malformed_output_rejected(stdout):
    with pytest.raises(SubscriptionError) as error:
        cli._parse_output(stdout, "unlabelled-refresh-secret", 0)
    assert error.value.kind == "malformed_output" and "secret" not in str(error.value)


@pytest.mark.parametrize("diagnostic,kind", [("TerminalQuotaError: daily quota exhausted", "quota"),
                                            ("429 rate limit", "rate_limit"), ("RetryableQuotaError", "rate_limit"),
                                            ("FatalAuthenticationError invalid_grant", "auth"),
                                            ("503 unavailable", "transient"), ("RESOURCE_EXHAUSTED", "quota"),
                                            ("other failure", "cli_failure")])
def test_error_classification_discards_all_raw_credential_text(diagnostic, kind):
    with pytest.raises(SubscriptionError) as error:
        cli._parse_output('{"response":"partial"}', diagnostic + "\nunlabelled-refresh-secret", 1)
    assert error.value.kind == kind and "unlabelled-refresh-secret" not in str(error.value) + repr(error.value.details)


def test_json_error_even_with_zero_exit_is_not_a_success():
    with pytest.raises(SubscriptionError) as error:
        cli._parse_output('{"error":{"message":"invalid_grant secret-token"}}', "", 0)
    assert error.value.kind == "auth" and "secret-token" not in str(error.value)


def test_unexpected_internal_tool_use_rejected():
    with pytest.raises(SubscriptionError) as error:
        cli._parse_output('{"response":"OK","stats":{"tools":{"totalCalls":1}}}', "", 0)
    assert error.value.kind == "capability"


def test_cli_retries_rate_limit_but_not_daily_quota(model, monkeypatch):
    calls = []
    model.max_retries = 1

    def run(*args, **kwargs):
        calls.append(args)
        return ("", "429 rate limit", 1) if len(calls) == 1 else ('{"response":"OK"}', "", 0)

    monkeypatch.setattr(cli, "_run_process", run)
    assert model.invoke("hello").content == "OK" and len(calls) == 2
    calls.clear()

    def quota(*args, **kwargs):
        calls.append(args)
        return "", "TerminalQuotaError daily quota exhausted", 1

    monkeypatch.setattr(cli, "_run_process", quota)
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "quota" and len(calls) == 1


def test_text_adapter_explicitly_rejects_tools_and_native_schema(model):
    with pytest.raises(NotImplementedError, match="native"):
        model.bind_tools([])
    with pytest.raises(NotImplementedError, match="structured output"):
        model.with_structured_output({})
    with pytest.raises(ValueError, match="native tool"):
        cli._conversation([ToolMessage(content="result", tool_call_id="x")])


def test_history_cannot_become_a_cli_file_import():
    _, prompt = cli._conversation([HumanMessage("Quote @/etc/passwd and user@example.invalid as text")])
    assert "@" not in prompt
    assert json.loads(prompt.split("\n", 1)[1])[0]["content"].startswith("Quote @/etc/passwd")


def test_real_process_timeout_is_killed(tmp_path):
    started = time.monotonic()
    with pytest.raises(SubscriptionError) as error:
        cli._run_process([sys.executable, "-c", "import time; time.sleep(60)"], "prompt",
                         cwd=str(tmp_path), env=dict(os.environ), timeout=0.15, cancellation=threading.Event())
    assert error.value.kind == "timeout" and time.monotonic() - started < 3


def test_real_process_cancellation_is_killed(tmp_path):
    cancelled = threading.Event()
    timer = threading.Timer(0.1, cancelled.set)
    timer.start()
    try:
        with pytest.raises(SubscriptionError) as error:
            cli._run_process([sys.executable, "-c", "import time; time.sleep(60)"], "prompt",
                             cwd=str(tmp_path), env=dict(os.environ), timeout=30, cancellation=cancelled)
        assert error.value.kind == "cancelled"
    finally:
        timer.cancel()


def test_async_cancellation_signals_worker_and_waits_for_cleanup(model, monkeypatch):
    started, ended = threading.Event(), threading.Event()

    def run(*args, cancellation, **kwargs):
        started.set()
        assert cancellation.wait(3)
        ended.set()
        raise SubscriptionError("cancelled", kind="cancelled")

    monkeypatch.setattr(cli, "_run_process", run)

    async def cancel():
        task = asyncio.create_task(model.ainvoke("hello"))
        while not started.is_set():
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert ended.is_set()

    asyncio.run(cancel())


@pytest.mark.parametrize("setting", ["api_key", "temperature", "max_tokens", "thinking_level"])
def test_unsupported_api_settings_fail_before_starting_cli(setting):
    with pytest.raises(ValueError):
        create_llm_client("gemini_cli", "auto", **{setting: "invalid"}).get_llm()
