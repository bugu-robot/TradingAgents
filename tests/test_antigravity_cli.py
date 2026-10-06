"""Offline safety checks; these never prove live Google AI Pro entitlement."""

import copy
import json
import os
import subprocess

import pytest

from tradingagents.llm_clients import antigravity_cli_client as cli
from tradingagents.llm_clients.subscription_errors import SubscriptionError


@pytest.fixture
def safe_home(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.Path, "home", lambda: tmp_path)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    path = tmp_path / ".gemini/antigravity-cli/settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(cli.REQUIRED_SETTINGS))
    path.chmod(0o600)
    return path


def write_settings(path, **updates):
    settings = copy.deepcopy(cli.REQUIRED_SETTINGS)
    settings.update(updates)
    path.write_text(json.dumps(settings))


def test_readonly_subscription_settings_preflight(safe_home):
    before = safe_home.read_bytes()
    assert cli._configuration_preflight() == cli.REQUIRED_SETTINGS
    assert safe_home.read_bytes() == before


@pytest.mark.parametrize("provider", ["gemini", "vertex", "openai", "google", "unknown"])
def test_api_provider_rejected_before_any_child_process(safe_home, monkeypatch, provider):
    write_settings(safe_home, modelProvider=provider)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must fail before CLI startup"))
    with pytest.raises(SubscriptionError, match="subscription authentication"):
        cli.preflight()


@pytest.mark.parametrize("setting,value", [
    ("customModels", [{"endpoint": "https://paid.invalid", "apiKey": "opaque-secret"}]),
    ("customModelsConfig", {"provider": "vertex"}), ("modelProvider", ""),
    ("apiKey", "secret"), ("baseUrl", "https://paid.invalid"),
    ("auth", {"type": "service_account"}), ("projectId", "billing-project"),
    ("hooks", {}), ("statusLine", {"command": "touch bad"}),
    ("futurePolicy", {"force": "vertex"}),
])
def test_unreviewed_settings_fail_closed(safe_home, setting, value):
    write_settings(safe_home, **{setting: value})
    with pytest.raises(SubscriptionError) as error:
        cli._configuration_preflight()
    assert error.value.kind == "policy" and "secret" not in str(error.value)


@pytest.mark.parametrize("setting,value", [
    ("useG1Credits", True), ("useG1Credits", 0), ("useG1Credits", None),
    ("toolPermission", "always-proceed"), ("toolPermission", "request-review"),
    ("allowNonWorkspaceAccess", True), ("enableTerminalSandbox", False),
])
def test_unsafe_credit_or_permission_preset_rejected(safe_home, setting, value):
    write_settings(safe_home, **{setting: value})
    with pytest.raises(SubscriptionError):
        cli._configuration_preflight()


@pytest.mark.parametrize("permissions", [None, [], {"allow": ["command(*)"], "ask": [], "deny": []},
                                         {"allow": [], "ask": [], "deny": ["read_file(*)"]},
                                         {"allow": [], "ask": [], "deny": [None]}])
def test_no_implicit_workspace_file_or_command_grants(safe_home, permissions):
    write_settings(safe_home, permissions=permissions)
    with pytest.raises(SubscriptionError):
        cli._configuration_preflight()


@pytest.mark.parametrize("relative", [
    ".gemini/config/hooks.json", ".gemini/config/mcp_config.json", ".gemini/config/plugins/x/agent.md",
    ".gemini/config/agents/x.md", ".gemini/config/skills/x/SKILL.md",
    ".gemini/antigravity-cli/plugins.json", ".gemini/antigravity-cli/hooks.json",
    ".gemini/antigravity-cli/policy.json", ".gemini/antigravity-cli/managed-settings.json",
    ".config/gcloud/application_default_credentials.json",
])
def test_global_customizations_adc_or_policy_never_overridden(safe_home, relative, monkeypatch):
    target = safe_home.parents[2] / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('secret policy or credential data')
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must fail before any child"))
    with pytest.raises(SubscriptionError) as exc:
        cli.preflight()
    assert exc.value.kind == "policy" and target.read_text() == 'secret policy or credential data'


@pytest.mark.parametrize("raw", ["", "[]", "null", '{"useG1Credits": false, "useG1Credits": true}', '{"a": NaN}', '\xff'])
def test_malformed_settings_are_safe_errors(safe_home, raw):
    safe_home.write_bytes(raw.encode('latin1'))
    with pytest.raises(SubscriptionError):
        cli._configuration_preflight()


def test_executable_discovery_and_actual_required_flags(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/bin/agy")
    seen = []
    def run(exe, args, **kwargs):
        seen.append(args)
        return subprocess.CompletedProcess(args, 0, cli.VERIFIED_VERSION if args == ['--version'] else '\n'.join(cli.REQUIRED_FLAGS), '')
    monkeypatch.setattr(cli, "_command", run)
    assert cli.detect_cli() == ("/bin/agy", "1.2.17")
    assert seen == [['--version'], ['--help']]


def test_missing_executable_and_unknown_version(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    with pytest.raises(SubscriptionError, match="Install"):
        cli.detect_cli()
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/agy")
    monkeypatch.setattr(cli, "_command", lambda *a, **k: subprocess.CompletedProcess([], 0, '1.2.18', ''))
    with pytest.raises(SubscriptionError, match="Unverified"):
        cli.detect_cli()


@pytest.mark.parametrize("missing", cli.REQUIRED_FLAGS)
def test_missing_public_flag_rejected(monkeypatch, missing):
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/agy")
    def run(exe, args, **kwargs):
        return subprocess.CompletedProcess(args, 0, cli.VERIFIED_VERSION if args == ['--version'] else '\n'.join(f for f in cli.REQUIRED_FLAGS if f != missing), '')
    monkeypatch.setattr(cli, "_command", run)
    with pytest.raises(SubscriptionError, match="flags"):
        cli.detect_cli()


@pytest.mark.parametrize("variable", [
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_GENAI_USE_GCA",
    "GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_ACCESS_TOKEN", "GOOGLE_GEMINI_BASE_URL",
    "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_PROJECT_ID", "GOOGLE_CLOUD_QUOTA_PROJECT", "GOOGLE_CLOUD_LOCATION",
    "GCLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT", "AGY_ADC_AUTH", "GOOGLE_GENAI_USE_ENTERPRISE",
    "AGY_LLM_GATEWAY_URL", "AGY_LLM_GATEWAY_API_KEY", "ANTIGRAVITY_AGENT", "ANTIGRAVITY_APP_DATA_DIR",
    "ANTIGRAVITY_LS_ADDRESS", "GEMINI_CLI_SYSTEM_SETTINGS_PATH", "GEMINI_CLI_SYSTEM_DEFAULTS_PATH",
    "ANTIGRAVITY_PERM_GRANTS", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HTTPS_PROXY", "LD_PRELOAD",
    "AGY_FUTURE_API_PROVIDER_OVERRIDE",
])
def test_conflicting_environment_cannot_reach_child(monkeypatch, variable):
    monkeypatch.setenv(variable, "untrusted-secret-routing-value")
    before = dict(os.environ)
    env = cli._child_environment()
    assert variable not in env and dict(os.environ) == before
    assert env['AGY_CLI_DISABLE_AUTO_UPDATE'] == 'true'


@pytest.mark.parametrize("diagnostic,kind", [
    ("weekly limit exceeded", "quota"), ("resource_exhausted", "quota"),
    ("rate limit 429", "rate_limit"), ("authentication required", "auth"),
    ("not entitled subscription required", "eligibility"), ("administrator policy 403", "permission"),
    ("503 service unavailable", "transient"), ("unclassified", "cli_failure"),
])
def test_diagnostic_classification_discards_opaque_secrets(diagnostic, kind):
    error = cli._diagnostic_error(diagnostic+' opaqueSecretWithoutLabel', 'refresh_token=raw-secret', 1)
    assert error.kind == kind
    assert 'opaqueSecret' not in str(error) and 'raw-secret' not in str(error.details)
