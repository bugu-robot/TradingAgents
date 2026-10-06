"""Offline safety checks; these never prove live Google AI Pro entitlement."""

import asyncio
import copy
import json
import os
import subprocess
import sys
import threading

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
    ("503 service unavailable", "transient"), ("unclassified", "cli_failure"),
])
def test_diagnostic_classification_discards_opaque_secrets(diagnostic, kind):
    error = cli._diagnostic_error(diagnostic+' opaqueSecretWithoutLabel', 'refresh_token=raw-secret', 1)
    assert error.kind == kind
    assert 'opaqueSecret' not in str(error) and 'raw-secret' not in str(error.details)


@pytest.mark.parametrize("report,kind", [
    ('', 'auth'), ('Account: somebody\nPlan: Free', 'eligibility'),
    ('Account: somebody\nPlan: Pro\nCredential: Gemini API key', 'auth'),
    ('Plan: Pro\nCredential: ADC', 'auth'), ('Plan: Pro\nLicense: Enterprise', 'auth'),
    ('{"status":"ERROR","error":"authentication required"}', 'auth'),
    ('unrecognized informational output opaqueSecret', 'eligibility'),
])
def test_auth_preflight_requires_positive_cli_pro_evidence(monkeypatch, report, kind):
    monkeypatch.setattr(cli, '_command', lambda *a, **k: subprocess.CompletedProcess([], 0, report, ''))
    with pytest.raises(SubscriptionError) as exc:
        cli._authentication_preflight('/agy')
    assert exc.value.kind == kind and 'opaqueSecret' not in str(exc.value)


def test_mocked_cli_pro_information_passes_preflight_but_is_not_live_proof(monkeypatch):
    monkeypatch.setattr(cli, '_command', lambda *a, **k: subprocess.CompletedProcess([], 0, 'Account: test@example.invalid\nPlan: Google AI Pro', ''))
    cli._authentication_preflight('/agy')


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
    ('tools', None), ('permission_mode', 'always-proceed'), ('permission_mode', 'request-review'),
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


def native_script(answer='"訂閱推理完成"', *, init_overrides=None, extra=''):
    return '''import json, os, sys
args=sys.argv[1:]
def option(flag): return args[args.index(flag)+1] if flag in args else None
schema=json.loads(option('--json-schema')) if option('--json-schema') else None
init={'cwd':os.getcwd(),'model':option('--model'),'agent':option('--agent'),'tools':[],'permission_mode':'strict','json_schema':schema}
init.update(''' + repr(init_overrides or {}) + ''')
print(json.dumps({'event':'init','conversation_id':'conversation-1','init':init}),flush=True)
line=sys.stdin.readline()
assert json.loads(line)['event']=='user'
answer=''' + answer + '''
body={'conversation_id':'conversation-1','status':'SUCCESS','response':json.dumps(answer,ensure_ascii=False) if schema else answer,'num_turns':1,'usage':{}}
if schema: body.update(structured_output=answer,json_schema=schema)
''' + extra + '''
print(json.dumps({'event':'result','result':body},ensure_ascii=False),flush=True)
'''


@pytest.fixture
def model(safe_home, tmp_path, monkeypatch):
    executable = fake_executable(tmp_path, native_script())
    monkeypatch.setattr(cli, 'preflight', lambda *a: (executable, cli.VERIFIED_VERSION))
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


def test_unsafe_init_kills_child_without_sending_prompt(model, tmp_path, monkeypatch):
    marker = tmp_path / 'prompt-was-received'
    script = native_script(init_overrides={'tools': ['run_command']}, extra='open('+repr(str(marker))+', "w").write("bad")')
    exe = fake_executable(tmp_path, script)
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    with pytest.raises(SubscriptionError) as exc:
        model.invoke('must not be submitted')
    assert exc.value.kind == 'capability' and not marker.exists()


def test_init_not_emitted_until_prompt_fails_before_inference(model, tmp_path, monkeypatch):
    marker = tmp_path / 'received'
    exe = fake_executable(tmp_path, 'import sys\nsys.stdin.readline()\nopen('+repr(str(marker))+', "w").write("bad")\n')
    monkeypatch.setattr(cli, 'preflight', lambda *a: (exe, cli.VERIFIED_VERSION))
    model.timeout = .15
    with pytest.raises(SubscriptionError) as exc:
        model.invoke('must not be submitted')
    assert exc.value.kind == 'timeout' and not marker.exists()


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
