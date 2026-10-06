"""Offline safety checks; these never prove live Google AI Pro entitlement."""

import asyncio
import copy
import json
import os
import subprocess
import sys
import threading
import time

import pytest
from langchain_core.messages import AIMessage, ChatMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field

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
    ("invalid model selection unknown model", "configuration"),
    ("503 service unavailable", "transient"), ("unclassified", "cli_failure"),
])
def test_diagnostic_classification_discards_opaque_secrets(diagnostic, kind):
    error = cli._diagnostic_error(diagnostic+' opaqueSecretWithoutLabel', 'refresh_token=raw-secret', 1)
    assert error.kind == kind
    assert 'opaqueSecret' not in str(error) and 'raw-secret' not in str(error.details)


def test_configured_reviewed_cli_never_sends_speculative_account_prompt(safe_home, monkeypatch):
    calls = []
    monkeypatch.setattr(cli.shutil, 'which', lambda _: '/agy')
    def probe(exe, args, **kwargs):
        calls.append(args)
        if args == ['--version']:
            return subprocess.CompletedProcess([], 0, cli.VERIFIED_VERSION, '')
        if args == ['--help']:
            return subprocess.CompletedProcess([], 0, '\n'.join(cli.REQUIRED_FLAGS), '')
        pytest.fail('no speculative CLI/model account probe')
    monkeypatch.setattr(cli, '_command', probe)
    assert cli.preflight('/agy') == ('/agy', cli.VERIFIED_VERSION)
    assert calls == [['--version'], ['--help']]


CATALOG = ('gemini-3.1-pro-high', 'claude-sonnet-4-6-thinking', 'gpt-oss-120b')


def catalog_json(slugs=CATALOG, **overrides):
    # Maintainer-confirmed global --output-format JSON result envelope.
    payload = {
        "conversation_id": "",
        "status": "SUCCESS",
        "response": "",
        "duration_seconds": 0,
        "num_turns": 0,
        "usage": {},
        "command": {"name": "models", "data": {"models": [
            {"id": slug, "label": f"Official label for {slug}"} for slug in slugs
        ]}},
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_catalog_discovery_uses_only_official_non_inference_command(safe_home, monkeypatch):
    calls = []
    monkeypatch.setattr(cli.shutil, 'which', lambda _: '/agy')
    monkeypatch.setattr(cli, 'preflight', lambda *a: pytest.fail('catalog must not call inference preflight'))
    monkeypatch.setattr(cli, '_run_process', lambda *a, **k: pytest.fail('no model request'))
    def probe(exe, args, **kwargs):
        calls.append(args)
        output = {('--version',): cli.VERIFIED_VERSION, ('--help',): '\n'.join(cli.REQUIRED_FLAGS),
                  ('--output-format', 'json', 'models'): catalog_json()}[tuple(args)]
        return subprocess.CompletedProcess(args, 0, output, '')
    monkeypatch.setattr(cli, '_command', probe)
    options = cli.model_options()
    assert [slug for _, slug in options] == list(CATALOG)
    assert calls == [['--version'], ['--help'], ['--output-format', 'json', 'models']]
    assert all('verify plan access' in label for label, _ in options)


@pytest.mark.parametrize('stdout', [
    '', '   \n', 'model-without-label', '[]', 'null',
    '{"status":"SUCCESS","num_turns":0}',
    catalog_json(status='ERROR'),
    catalog_json(status='SUCCESS', num_turns=1),
    catalog_json(status='SUCCESS', num_turns=0.0),
    catalog_json(command={'name': 'agents', 'data': {'models': [{'id': 'gemini-pro'}]}}),
    catalog_json(error={'message': 'model catalog failed'}),
    catalog_json(command={"name": "models"}),
    catalog_json(command={"name": "models", "data": {}}),
    catalog_json(command={"name": "models", "data": {"models": "gemini-pro"}}),
    catalog_json(slugs=()),
    catalog_json(slugs=('../custom',)),
    catalog_json(slugs=('gemini-pro', 'gemini-pro')),
    catalog_json(command={"name": "models", "data": {"models": ["gemini-pro"]}}),
    catalog_json(command={"name": "models", "data": {"models": [{}]}}),
    catalog_json(command={"name": "models", "data": {"models": [{"id": 7}]}}),
    catalog_json(command={"name": "models", "data": {"models": [
        {"id": "gemini-pro", "label": 7}
    ]}}),
    catalog_json(command={"name": "models", "data": {"models": [
        {"id": "gemini-pro", "label": "x" * 161}
    ]}}),
    '{"status":"SUCCESS","num_turns":0,"command":{"name":"models","data":{"models":[{"id":"gemini-pro","label":"x"},{"id":"gemini-pro","label":"duplicate"}]}}}',
    catalog_json(command={"name": "models", "data": {"models": [
        {"id": "claude-sonnet-4-6", "label": "\x1b[31munsafe"}
    ]}}),
    '{"status":"SUCCESS","num_turns":0,"command":{"name":"models","data":{"models":[{"id":"gemini-pro","label":"x","id":"claude-sonnet-4-6"}]}}}',
])
def test_unreadable_or_unsafe_catalog_is_terminal(safe_home, monkeypatch, stdout):
    monkeypatch.setattr(cli, '_command', lambda *a, **k: subprocess.CompletedProcess([], 0, stdout, ''))
    with pytest.raises(SubscriptionError) as exc:
        cli._catalog_models('/agy')
    assert exc.value.kind == 'malformed_output'


def test_catalog_never_falls_back_to_human_text(safe_home, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, '_command', lambda exe, args, **kwargs: (
        calls.append(args) or subprocess.CompletedProcess(args, 0,
            'gemini-3.1-pro-high  Gemini 3.1 Pro High', '')))
    with pytest.raises(SubscriptionError, match='malformed JSON model-catalog'):
        cli._catalog_models('/agy')
    assert calls == [['--output-format', 'json', 'models']]


def test_global_json_flag_rejection_fails_without_text_fallback(safe_home, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, '_command', lambda exe, args, **kwargs: (
        calls.append(args) or subprocess.CompletedProcess(args, 1, '',
            'Error: flags provided but not defined: -output-format')))
    with pytest.raises(SubscriptionError, match='rejected the global JSON output flag') as exc:
        cli._catalog_models('/agy')
    assert exc.value.kind == 'unsupported_cli'
    assert calls == [['--output-format', 'json', 'models']]


@pytest.mark.parametrize('slug', CATALOG + ('future-family-v2.1', 'other_model-3'))
def test_safe_slug_is_independent_of_model_family(slug):
    assert cli._valid_model(slug)


@pytest.mark.parametrize('slug', ['', ' auto', 'model\n--provider=gemini', '-model', 'model-',
                                'model..id', 'custom/model', 'provider:model', 'MODEL', '$(id)',
                                '`id`', 'x' * 129, None, 123])
def test_unsafe_or_custom_api_slug_rejected(slug):
    assert not cli._valid_model(slug)


def test_catalog_auth_error_is_not_plan_entitlement_evidence(safe_home, monkeypatch):
    monkeypatch.setattr(cli, '_command', lambda *a, **k: subprocess.CompletedProcess(
        [], 1, '', 'authentication required opaque-secret'))
    with pytest.raises(SubscriptionError) as exc:
        cli._catalog_models('/agy')
    assert exc.value.kind == 'auth' and 'opaque-secret' not in str(exc.value)


def test_catalog_preflight_rejects_billed_configuration_before_cli(safe_home, monkeypatch):
    write_settings(safe_home, modelProvider='gemini')
    monkeypatch.setattr(cli, '_command', lambda *a, **k: pytest.fail('no catalog child'))
    with pytest.raises(SubscriptionError) as exc:
        cli.model_options()
    assert exc.value.kind == 'auth'


def test_auth_models_command_runs_catalog_without_inference_or_entitlement_claim(safe_home, monkeypatch):
    from typer.testing import CliRunner

    from cli.subscription_auth import app

    calls = []
    monkeypatch.setattr(cli, 'detect_cli', lambda *a: ('/agy', cli.VERIFIED_VERSION))
    def probe(exe, args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, catalog_json(), '')
    monkeypatch.setattr(cli, '_command', probe)
    monkeypatch.setattr(cli, '_run_process', lambda *a, **k: pytest.fail('no inference'))
    response = CliRunner().invoke(app, ['models', 'antigravity_cli'])
    assert response.exit_code == 0 and calls == [['--output-format', 'json', 'models']]
    assert all(slug in response.stdout for slug in CATALOG)
    assert 'alone does not prove subscription entitlement' in response.stderr


def test_auth_status_uses_official_non_inference_usage_and_never_model_transport(safe_home, monkeypatch):
    from typer.testing import CliRunner

    from cli.subscription_auth import app

    detected = []
    monkeypatch.setattr(cli, 'detect_cli', lambda *a: (detected.append(a) or ('/agy', cli.VERIFIED_VERSION)))
    calls = []
    monkeypatch.setattr(cli, '_command', lambda exe, args, **kwargs: (
        calls.append(args) or subprocess.CompletedProcess(args, 0,
            json.dumps({'status': 'SUCCESS', 'num_turns': 0,
                        'response': 'Models quota: private account details'}), '')))
    monkeypatch.setattr(cli, '_run_process', lambda *a, **k: pytest.fail('auth status must not infer'))
    monkeypatch.setattr(cli, '_catalog_models', lambda *a, **k: pytest.fail('auth status must not list models'))
    response = CliRunner().invoke(app, ['status', 'antigravity_cli'])
    assert response.exit_code == 0
    status = json.loads(response.stdout)
    assert status['local_configuration_ready'] is True
    assert status['cached_account_backend_usage_ready'] is True
    assert status['model_turns_consumed'] == 0
    assert status['plan_entitlement'] == 'not_verified'
    assert detected == [(None,)]
    assert calls == [['-p', '/usage', '--output-format', 'json']]
    assert 'private account details' not in response.stdout


@pytest.mark.parametrize(('stdout', 'stderr', 'code', 'kind'), [
    ('', 'authentication required opaque-secret', 1, 'auth'),
    ('{"status":"ERROR","error":"quota exhausted opaque-secret"}', '', 0, 'quota'),
    ('{"status":"ERROR","error":"rate limit opaque-secret"}', '', 0, 'rate_limit'),
    ('{"status":"SUCCESS","num_turns":1}', '', 0, 'malformed_output'),
    ('{"status":"SUCCESS"}', '', 0, 'malformed_output'),
    ('{"status":"SUCCESS","num_turns":0}', '', 0, 'malformed_output'),
    ('not-json opaque-secret', '', 0, 'malformed_output'),
    ('{"status":"SUCCESS","status":"ERROR"}', '', 0, 'malformed_output'),
])
def test_auth_status_safely_classifies_usage_failures(safe_home, monkeypatch, stdout, stderr, code, kind):
    from typer.testing import CliRunner

    from cli.subscription_auth import app

    monkeypatch.setattr(cli, 'detect_cli', lambda *a: ('/agy', cli.VERIFIED_VERSION))
    monkeypatch.setattr(cli, '_command', lambda *a, **k: subprocess.CompletedProcess([], code, stdout, stderr))
    monkeypatch.setattr(cli, '_run_process', lambda *a, **k: pytest.fail('auth status must not infer'))
    response = CliRunner().invoke(app, ['status', 'antigravity_cli'])
    assert response.exit_code == 1
    report = json.loads(response.stdout)
    assert report['local_configuration_ready'] is True
    assert report['cached_account_backend_usage_ready'] is False
    assert report['failure_kind'] == kind
    assert 'opaque-secret' not in response.stdout + response.stderr


def test_auth_status_fails_before_usage_if_subscription_settings_are_unsafe(safe_home, monkeypatch):
    write_settings(safe_home, modelProvider='gemini')
    monkeypatch.setattr(cli, 'detect_cli', lambda *a: pytest.fail('config gate first'))
    monkeypatch.setattr(cli, '_command', lambda *a, **k: pytest.fail('no usage request'))
    status = cli.account_status()
    assert status['local_configuration_ready'] is False
    assert status['cached_account_backend_usage_ready'] is False
    assert status['usage_check'] == 'not_attempted'


def result(response='訂閱推理完成', **overrides):
    return {'conversation_id': 'conversation-1', 'status': 'SUCCESS', 'response': response,
            'num_turns': 1, 'usage': {'input_tokens': 10, 'output_tokens': 3}, **overrides}


def stream(schema=None):
    s = cli._Stream(cwd='/private', model='gemini-3.1-pro-high', agent='private-agent', schema=schema)
    return s


def feed(s, event, payload, **extras):
    s.feed(json.dumps({'event': event, event: payload, **extras}, ensure_ascii=False).encode('utf-8'))


def initialized(schema=None):
    s = stream(schema)
    feed(s, 'init', {'cwd': '/private', 'model': 'gemini-3.1-pro-high', 'agent': 'private-agent',
                    'tools': [], 'permission_mode': 'strict', 'json_schema': schema}, conversation_id='conversation-1')
    return s


def test_stream_completion_with_utf8_and_multiple_text_deltas():
    s = initialized()
    for state in ('ACTIVE', 'DONE'):
        feed(s, 'step_update', {'conversation_id': 'conversation-1', 'step_type': 'agent_response', 'state': state, 'text_delta': '訂閱'})
    feed(s, 'result', result())
    assert s.finish('', 0)['response'] == '訂閱推理完成'


@pytest.mark.parametrize('raw', [b'', b'[]', b'null', b'{}', b'not json secret', b'\xff', b'{"event":"init","event":"result"}', b'{"event": NaN}'])
def test_malformed_json_stream_is_rejected_and_redacted(raw):
    with pytest.raises(SubscriptionError) as exc:
        stream().feed(raw)
    assert exc.value.kind == 'malformed_output' and 'secret' not in str(exc.value)


@pytest.mark.parametrize('step', ['tool', 'command', 'mcp', 'invoke_subagent', 'plugin', 'skill', 'unknown'])
def test_all_autonomous_step_types_rejected(step):
    with pytest.raises(SubscriptionError) as exc:
        feed(initialized(), 'step_update', {'conversation_id': 'conversation-1', 'state': 'DONE', 'step_type': step})
    assert exc.value.kind == 'capability'


@pytest.mark.parametrize('field', ['tool_info', 'tool_name', 'subagent_info', 'mcp_calls', 'agent_calls', 'skill_calls', 'plugin_calls', 'commands', 'side_effects'])
def test_nested_action_metadata_rejected_even_on_text_step(field):
    with pytest.raises(SubscriptionError):
        feed(initialized(), 'step_update', {'conversation_id': 'conversation-1', 'step_type': 'agent_response', 'state': 'DONE',
                                           'nested': {field: {'name': 'unsafe', 'token': 'opaque'}}})


@pytest.mark.parametrize('field,value', [
    ('tools', ['view_file']), ('tools', ['invoke_subagent']), ('tools', ['mcp/tool']),
    ('tools', None), ('permission_mode', 'always-proceed'), ('permission_mode', 'unknown'),
    ('cwd', '/user/project'), ('model', 'custom-api-model'), ('agent', 'default'),
])
def test_unsafe_initialization_rejected_before_input(field, value):
    body = {'cwd': '/private', 'model': 'gemini-3.1-pro-high', 'agent': 'private-agent', 'tools': [], 'permission_mode': 'strict'}
    body[field] = value
    with pytest.raises(SubscriptionError):
        feed(stream(), 'init', body, conversation_id='conversation-1')


@pytest.mark.parametrize('overrides', [
    {'response': ''}, {'response': None}, {'response': []}, {'num_turns': True}, {'num_turns': 2},
    {'conversation_id': None}, {'usage': None}, {'usage': {'output_tokens': -1}}, {'usage': {'input_tokens': False}},
    {'status': 'WAITING'}, {'status': 'RUNNING'},
])
def test_incomplete_or_malformed_terminal_result_rejected(overrides):
    with pytest.raises(SubscriptionError):
        cli._parse_result(result(**overrides))


def test_stream_requires_init_one_identity_and_one_terminal():
    with pytest.raises(SubscriptionError):
        feed(stream(), 'result', result())
    s = initialized()
    with pytest.raises(SubscriptionError):
        feed(s, 'result', result(conversation_id='other'))
    s = initialized()
    with pytest.raises(SubscriptionError):
        s.finish('', 0)
    s = initialized()
    feed(s, 'result', result())
    with pytest.raises(SubscriptionError):
        feed(s, 'result', result())


@pytest.mark.parametrize('status', ['ERROR', 'CANCELED', 'INTERRUPTED', 'INVALID', 'WAITING'])
def test_error_before_init_is_terminal_and_not_a_fallback(status):
    with pytest.raises(SubscriptionError):
        feed(stream(), 'result', {'status': status, 'error': 'authentication required secret'})


class SchemaResult(BaseModel):
    model_config = ConfigDict(extra='forbid')
    marker: str
    count: int = Field(ge=1)


@pytest.mark.parametrize('structured', [{'marker': 'ok'}, {'marker': 'ok', 'count': '2'}, {'marker': 'ok', 'count': 0}, {'marker': 'ok', 'count': 2, 'extra': True}, {'marker': 123, 'count': 2}])
def test_native_schema_violations_never_accepted(structured):
    with pytest.raises(SubscriptionError, match='JSON Schema'):
        cli._parse_result(result(json.dumps(structured), structured_output=structured, json_schema=SchemaResult.model_json_schema()), SchemaResult.model_json_schema())


def test_native_schema_requires_enforced_schema_and_identical_complete_json():
    schema = SchemaResult.model_json_schema()
    for body in [result('{"marker":"ok","count":2}'),
                 result('{"marker":"ok","count":2}', structured_output={'marker':'changed','count':2}, json_schema=schema),
                 result('partial {', structured_output={'marker':'ok','count':2}, json_schema=schema)]:
        with pytest.raises(SubscriptionError):
            cli._parse_result(body, schema)


def fake_executable(tmp_path, script):
    p = tmp_path / 'fake-agy'
    p.write_text('#!' + sys.executable + '\n' + script)
    p.chmod(0o700)
    return str(p)


def native_script(answer='"訂閱推理完成"', *, init_overrides=None, extra='', input_first=False):
    return '''import json, os, sys
args=sys.argv[1:]
def option(flag): return args[args.index(flag)+1] if flag in args else None
schema=json.loads(option('--json-schema')) if option('--json-schema') else None
init={'cwd':os.getcwd(),'model':option('--model'),'agent':option('--agent'),'tools':[],'permission_mode':'strict','json_schema':schema}
init.update(''' + repr(init_overrides or {}) + ''')
''' + ("line=sys.stdin.readline()\nassert json.loads(line)['event']=='user'\n" if input_first else '') + '''
print(json.dumps({'event':'init','conversation_id':'conversation-1','init':init}),flush=True)
''' + ("line=sys.stdin.readline()\nassert json.loads(line)['event']=='user'\n" if not input_first else '') + '''
answer=''' + answer + '''
body={'conversation_id':'conversation-1','status':'SUCCESS','response':json.dumps(answer,ensure_ascii=False) if schema else answer,'num_turns':1,'usage':{}}
if schema: body.update(structured_output=answer,json_schema=schema)
''' + extra + '''
print(json.dumps({'event':'result','result':body},ensure_ascii=False),flush=True)
'''


@pytest.mark.parametrize('slug', CATALOG)
def test_complete_admission_catalog_and_stream_without_auth_attestation(safe_home, tmp_path, slug):
    calls = tmp_path / 'commands.jsonl'
    probes = '''import json, sys
with open(''' + repr(str(calls)) + ''', 'a') as log: log.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1:] == ['--version']:
 print(''' + repr(cli.VERIFIED_VERSION) + '''); sys.exit(0)
if sys.argv[1:] == ['--help']:
 print(''' + repr('\n'.join(cli.REQUIRED_FLAGS)) + '''); sys.exit(0)
if sys.argv[1:] == ['--output-format', 'json', 'models']:
 print(''' + repr(catalog_json()) + '''); sys.exit(0)
'''
    executable = fake_executable(tmp_path, probes + native_script(input_first=True))
    model = cli.AntigravityCLIChatModel(model_name=slug, executable=executable, max_retries=0, timeout=2)
    assert model.invoke('Supplied evidence').response_metadata['model_name'] == slug
    invocations = [json.loads(line) for line in calls.read_text().splitlines()]
    assert invocations[:3] == [['--version'], ['--help'], ['--output-format', 'json', 'models']]
    assert len(invocations) == 4 and invocations[3][invocations[3].index('--model') + 1] == slug


def test_documented_request_review_init_with_strict_settings_and_no_tools(safe_home, tmp_path):
    probes = '''import sys
if sys.argv[1:] == ['--version']:
 print(''' + repr(cli.VERIFIED_VERSION) + '''); sys.exit(0)
if sys.argv[1:] == ['--help']:
 print(''' + repr('\n'.join(cli.REQUIRED_FLAGS)) + '''); sys.exit(0)
if sys.argv[1:] == ['--output-format', 'json', 'models']:
 print(''' + repr(catalog_json(('gemini-3.1-pro-high',))) + '''); sys.exit(0)
'''
    executable = fake_executable(tmp_path, probes + native_script(input_first=True, init_overrides={'permission_mode': 'request-review'}))
    model = cli.AntigravityCLIChatModel(model_name='gemini-3.1-pro-high', executable=executable, max_retries=0, timeout=2)
    assert model.invoke('Supplied evidence').content == '訂閱推理完成'


@pytest.fixture
def model(safe_home, tmp_path, monkeypatch):
    executable = fake_executable(tmp_path, native_script())
    monkeypatch.setattr(cli, 'preflight', lambda *a: (executable, cli.VERIFIED_VERSION))
    monkeypatch.setattr(cli, '_catalog_models', lambda *a: list(CATALOG))
    return cli.AntigravityCLIChatModel(model_name='gemini-3.1-pro-high', max_retries=0, timeout=2)


def test_real_subprocess_invokes_noninteractively_and_preserves_conversation(model):
    answer = model.invoke([SystemMessage('Reason only from evidence'), HumanMessage('Marker'), AIMessage('Acknowledged'), ChatMessage(role='developer', content='More instructions'), HumanMessage('Answer')])
    assert answer.content == '訂閱推理完成' and not answer.tool_calls
    assert answer.response_metadata['provider'] == 'antigravity_cli'


def test_real_subprocess_native_schema_validation_and_raw_result(model, tmp_path, monkeypatch):
    executable = fake_executable(tmp_path, native_script("{'marker': 'ok', 'count': 2}"))
    monkeypatch.setattr(cli, 'preflight', lambda *a: (executable, cli.VERIFIED_VERSION))
    parsed = model.with_structured_output(SchemaResult).invoke('Return schema')
    assert parsed == SchemaResult(marker='ok', count=2)
    raw = model.with_structured_output(SchemaResult, include_raw=True).invoke('Return schema')
    assert isinstance(raw['raw'], AIMessage) and raw['parsing_error'] is None


def test_invalid_native_schema_stops_manager_without_plain_retry(model, tmp_path, monkeypatch):
    from tradingagents.agents.structured import invoke_structured_or_freetext
    executable = fake_executable(tmp_path, native_script("{'marker': 'ok', 'count': 'two'}"))
    monkeypatch.setattr(cli, 'preflight', lambda *a: (executable, cli.VERIFIED_VERSION))
    class Plain:
        def invoke(self, *a): pytest.fail('no plain fallback request')
    with pytest.raises(SubscriptionError):
        invoke_structured_or_freetext(model.with_structured_output(SchemaResult), Plain(), 'prompt', str, 'Manager')


@pytest.mark.parametrize('kind', ['auth','quota','eligibility','permission','malformed_output'])
def test_terminal_subscription_errors_do_not_retry_or_fallback(model, monkeypatch, kind):
    calls = []
    def run(*a, **k):
        calls.append(1)
        raise SubscriptionError('safe error', kind=kind)
    monkeypatch.setattr(cli, '_run_process', run)
    model.max_retries = 3
    with pytest.raises(SubscriptionError):
        model.invoke('prompt')
    assert calls == [1]


def test_rate_limit_retry_is_bounded_and_uses_fresh_workspace(model, monkeypatch):
    calls = []
    def run(*a, **k):
        calls.append(k['cwd'])
        if len(calls) == 1:
            raise SubscriptionError('limit', kind='rate_limit')
        return result()
    monkeypatch.setattr(cli, '_run_process', run)
    model.max_retries = 1
    assert model.invoke('prompt').content == '訂閱推理完成'
    assert len(calls) == 2 and calls[0] != calls[1]


def test_workspace_agent_and_environment_are_private_and_reasoning_only(model, monkeypatch):
    seen = []
    def run(command, prompt, **kw):
        root = cli.Path(kw['cwd'])
        agent = next((root / '.agents/agents').glob('*.md'))
        content = agent.read_text()
        assert '"tools": []' in content and '"inheritCustomizations": false' in content and '"subagent": false' in content
        assert 'Never browse' in content and 'supplied conversation and evidence' in content
        assert root.stat().st_mode & 0o077 == 0 and agent.stat().st_mode & 0o077 == 0
        assert '--dangerously-skip-permissions' not in command and '--sandbox' in command and '--disable-slash-commands' in command
        assert '--input-format' in command and '--print-timeout' in command
        assert not any(k.startswith(('GOOGLE_', 'GEMINI_', 'AGY_LLM_', 'ANTIGRAVITY_')) for k in kw['env'])
        assert '@' not in prompt and '\\u0040' in prompt
        seen.append(root)
        return result()
    monkeypatch.setattr(cli, '_run_process', run)
    model.invoke('Only supplied data @/etc/passwd, /boost and $(touch danger)')
    assert seen and all(not p.exists() for p in seen)


def test_unsafe_init_rejected_even_when_input_precedes_init(model, tmp_path, monkeypatch):
    script = native_script(init_overrides={'tools': ['run_command']}, input_first=True)
    exe = fake_executable(tmp_path, script)
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    with pytest.raises(SubscriptionError) as exc:
        model.invoke('supplied evidence only')
    assert exc.value.kind == 'capability'


def test_documented_input_before_init_accepts_only_validated_completion(model, tmp_path, monkeypatch):
    exe = fake_executable(tmp_path, native_script(input_first=True))
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    assert model.invoke('supplied evidence only').content == '訂閱推理完成'


@pytest.mark.parametrize('slug', CATALOG)
@pytest.mark.parametrize('effort', ['low', 'medium', 'high'])
def test_exact_listed_model_and_effort_passed_without_fallback(model, monkeypatch, slug, effort):
    model.model_name, model.effort = slug, effort
    def run(command, prompt, **kwargs):
        assert command[command.index('--model') + 1] == slug
        assert command[command.index('--effort') + 1] == effort
        assert kwargs['stream'].model == slug
        return result()
    monkeypatch.setattr(cli, '_run_process', run)
    answer = model.invoke('Supplied evidence')
    assert answer.response_metadata['model_name'] == slug and answer.response_metadata['effort'] == effort


def test_unlisted_safe_slug_fails_before_inference_without_fallback(model, monkeypatch):
    model.model_name = 'unknown-custom-model'
    monkeypatch.setattr(cli, '_run_process', lambda *a, **k: pytest.fail('no inference for unlisted model'))
    with pytest.raises(SubscriptionError, match='not in the current official'):
        model.invoke('blocked')


def test_inference_rechecks_subscription_settings_after_catalog(model, safe_home, monkeypatch):
    def catalog(*args):
        write_settings(safe_home, useG1Credits=True)
        return list(CATALOG)
    monkeypatch.setattr(cli, '_catalog_models', catalog)
    monkeypatch.setattr(cli, '_run_process', lambda *a, **k: pytest.fail('no unsafe inference'))
    with pytest.raises(SubscriptionError) as exc:
        model.invoke('blocked')
    assert exc.value.kind == 'policy'


def test_timeout_terminates_and_reaps_child(model, tmp_path, monkeypatch):
    pidfile = tmp_path / 'pid'
    exe = fake_executable(tmp_path, 'import os,time\nopen('+repr(str(pidfile))+', "w").write(str(os.getpid()))\ntime.sleep(30)\n')
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    model.timeout = .2
    with pytest.raises(SubscriptionError):
        model.invoke('timeout')
    assert not cli.Path('/proc/'+pidfile.read_text()).exists()


def test_async_cancellation_waits_for_child_cleanup(model, tmp_path, monkeypatch):
    pidfile = tmp_path / 'pid'
    exe = fake_executable(tmp_path, 'import os,time\nopen('+repr(str(pidfile))+', "w").write(str(os.getpid()))\ntime.sleep(30)\n')
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    async def exercise():
        task = asyncio.create_task(model.ainvoke('cancel'))
        for _ in range(100):
            if pidfile.exists():
                break
            await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(exercise())
    assert not cli.Path('/proc/'+pidfile.read_text()).exists()


def test_pre_cancelled_request_does_not_spawn(model, monkeypatch):
    event = threading.Event()
    event.set()
    monkeypatch.setattr(cli.subprocess, 'Popen', lambda *a, **k: pytest.fail('no spawn'))
    with pytest.raises(SubscriptionError) as exc:
        model.invoke('cancelled', cancellation_event=event)
    assert exc.value.kind == 'cancelled'


def test_native_tool_messages_and_bind_tools_are_explicitly_unsupported(model):
    for message in [ToolMessage(content='evidence', tool_call_id='call-1'), AIMessage(content='', tool_calls=[{'name':'stock','args':{},'id':'call-1'}])]:
        with pytest.raises(ValueError):
            cli._conversation([message])
    with pytest.raises(NotImplementedError):
        model.bind_tools([])


def test_schema_and_prompt_are_arguments_without_shell_interpolation(model, monkeypatch):
    class Unusual(BaseModel):
        marker: str = Field(description='`echo secret` $(touch /tmp/should-not-exist)')
    def run(command, prompt, **kw):
        schema = json.loads(command[command.index('--json-schema')+1])
        assert '$(touch ' in schema['properties']['marker']['description']
        assert command.count('--json-schema') == 1
        return result('{"marker":"safe"}', structured_output={'marker':'safe'}, json_schema=schema)
    monkeypatch.setattr(cli, '_run_process', run)
    assert model.with_structured_output(Unusual).invoke('schema').marker == 'safe'


@pytest.mark.parametrize('key,value', [('$ref', 'https://remote.invalid/schema'),
                                      ('$dynamicRef', 'https://remote.invalid/schema'),
                                      ('$id', 'https://remote.invalid/'),
                                      ('$schema', 'https://remote.invalid/dialect')])
def test_external_schema_resources_fail_before_any_process(model, monkeypatch, key, value):
    schema = {'type': 'object', 'properties': {'field': {key: value}}}
    monkeypatch.setattr(cli, 'preflight', lambda *a: pytest.fail('no CLI preflight for invalid schema'))
    with pytest.raises(SubscriptionError) as exc:
        model.bind(native_schema=schema).invoke('blocked')
    assert exc.value.kind == 'capability' and 'remote.invalid' not in str(exc.value)


def test_unresolved_local_schema_reference_is_terminal_without_network():
    schema = {'type': 'object', 'properties': {'field': {'$ref': '#/$defs/missing'}}}
    body = result('{"field":"secret"}', structured_output={'field': 'secret'}, json_schema=schema)
    with pytest.raises(SubscriptionError) as exc:
        cli._parse_result(body, schema)
    assert exc.value.kind == 'malformed_output' and 'secret' not in str(exc.value)


@pytest.mark.parametrize('field', ['toolInfo', 'mcpServers', 'plugin_info', 'skills', 'subagents', 'commandExecution'])
def test_new_action_metadata_spellings_are_rejected(field):
    s = initialized()
    with pytest.raises(SubscriptionError) as exc:
        feed(s, 'result', result(**{field: ['unexpected action']}))
    assert exc.value.kind == 'capability'


def test_structured_data_property_names_are_not_execution_metadata():
    data = {'commands': ['hold'], 'tool_calls': 'evidence', 'plugins': ['portfolio category']}
    schema = {'type': 'object', 'properties': {k: {} for k in data}}
    body = result(json.dumps(data), structured_output=data, json_schema=schema)
    assert cli._parse_result(body, schema)['structured_output'] == data


@pytest.mark.parametrize('raw', [b'{"number":1e999}', b'{"nested":{"value":NaN}}'])
def test_overflow_and_nonfinite_json_are_rejected(raw):
    with pytest.raises(ValueError):
        cli._json_object(raw.decode())


@pytest.mark.parametrize('directory', ['.gemini', '.gemini/antigravity-cli'])
def test_writable_settings_ancestors_fail_before_any_child(safe_home, directory, monkeypatch):
    (safe_home.parents[2] / directory).chmod(0o777)
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('no CLI startup'))
    with pytest.raises(SubscriptionError):
        cli.preflight()


def test_probe_output_is_bounded_and_child_reaped(tmp_path):
    pidfile = tmp_path / 'probe-pid'
    exe = fake_executable(tmp_path, 'import os,sys\nopen('+repr(str(pidfile))+', "w").write(str(os.getpid()))\nsys.stdout.write("x"*2000000)\n')
    with pytest.raises(SubscriptionError):
        cli._command(exe, ['--help'])
    assert not cli.Path('/proc/'+pidfile.read_text()).exists()


def test_probe_timeout_kills_descendant_retaining_output(tmp_path):
    childfile = tmp_path / 'descendant-pid'
    exe = fake_executable(tmp_path, 'import os,time\nchild=os.fork()\nif child == 0:\n open('+repr(str(childfile))+', "w").write(str(os.getpid()))\n time.sleep(30)\nelse:\n os._exit(0)\n')
    with pytest.raises(SubscriptionError):
        cli._command(exe, ['--version'], timeout=.3)
    state = cli.Path('/proc/'+childfile.read_text()+'/stat')
    for _ in range(100):
        if not state.exists() or state.read_text().split()[2] == 'Z':
            break
        time.sleep(.01)
    assert not state.exists() or state.read_text().split()[2] == 'Z'


def test_probe_cancellation_kills_and_reaps_child(tmp_path):
    pidfile = tmp_path / 'cancel-probe-pid'
    exe = fake_executable(tmp_path, 'import os,time\nopen('+repr(str(pidfile))+', "w").write(str(os.getpid()))\ntime.sleep(30)\n')
    cancel = threading.Event()
    timer = threading.Timer(.15, cancel.set)
    timer.start()
    try:
        with pytest.raises(SubscriptionError) as exc:
            cli._command(exe, ['--help'], cancellation=cancel)
        assert exc.value.kind == 'cancelled'
    finally:
        timer.cancel()
    assert not cli.Path('/proc/'+pidfile.read_text()).exists()


def test_nonzero_exit_before_init_retains_safe_auth_classification(model, tmp_path, monkeypatch):
    exe = fake_executable(tmp_path, 'import sys\nsys.stderr.write("authentication required opaque-secret")\nsys.exit(1)\n')
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    with pytest.raises(SubscriptionError) as exc:
        model.invoke('unused')
    assert exc.value.kind == 'auth' and 'opaque-secret' not in str(exc.value)


def test_closed_output_pipes_still_allow_cancellation_and_cleanup(tmp_path):
    pidfile = tmp_path / 'closed-pipes-pid'
    exe = fake_executable(tmp_path, 'import os,time\nopen('+repr(str(pidfile))+', "w").write(str(os.getpid()))\nos.close(1)\nos.close(2)\ntime.sleep(30)\n')
    cancel = threading.Event()
    timer = threading.Timer(.15, cancel.set)
    timer.start()
    try:
        with pytest.raises(SubscriptionError) as exc:
            cli._command(exe, ['--help'], cancellation=cancel)
        assert exc.value.kind == 'cancelled'
    finally:
        timer.cancel()
    assert not cli.Path('/proc/'+pidfile.read_text()).exists()


def test_extremely_nested_json_is_a_safe_protocol_error():
    with pytest.raises(ValueError):
        cli._json_object('{"value":' + '[' * 2000 + '1' + ']' * 2000 + '}')
