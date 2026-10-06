"""Offline public Responses transport tests; no real credentials or model calls."""

import json

import pytest
import requests
from langchain_core.messages import ChatMessage, HumanMessage, SystemMessage
from pydantic import BaseModel
from typer.testing import CliRunner

from tradingagents.llm_clients import chatgpt_plan_client as plan
from tradingagents.llm_clients.api_key_env import get_api_key_env
from tradingagents.llm_clients.factory import build_llm_kwargs, create_llm_client
from tradingagents.llm_clients.model_catalog import get_known_models
from tradingagents.llm_clients.subscription_errors import SubscriptionError

from .test_chatgpt_plan_auth import connect


class Response:
    def __init__(self, events=(), *, status=200, body=None, headers=None):
        self.status_code, self.body = status, body
        self.events, self.headers = events, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def json(self):
        return self.body

    def iter_lines(self, **kwargs):
        for event in self.events:
            yield "data: " + json.dumps(event)
            yield ""


def completed(text="OK", output=None):
    return {"type": "response.completed", "response": {
        "status": "completed", "id": "response-one", "model": "account-model",
        "output": output if output is not None else [
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}],
        "usage": {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
    }}


@pytest.fixture
def model(tmp_path, monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_CHATGPT_AUTH_DIR", str(tmp_path / "auth"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    llm = create_llm_client("chatgpt_plan", "account-model", max_retries=0).get_llm()
    connect(llm._auth)
    return llm


@pytest.fixture
def posted(monkeypatch):
    calls, outputs = [], []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return outputs.pop(0)

    monkeypatch.setattr(plan.requests, "post", post)
    return calls, outputs


def test_registered_no_api_key_required(model):
    assert model._llm_type == "chatgpt_plan"
    assert get_api_key_env("chatgpt_plan") is None
    assert "chatgpt_plan" in get_known_models()
    assert "secret" not in repr(model) and "secret" not in json.dumps(model._identifying_params)


def test_invoke_uses_official_streaming_stateless_route(model, posted):
    calls, outputs = posted
    outputs.append(Response([completed()]))
    answer = model.invoke("hello")
    assert answer.content == "OK" and answer.usage_metadata["total_tokens"] == 10
    url, options = calls[0]
    assert url == "https://api.openai.com/v1/responses"
    assert options["headers"]["Authorization"] == "Bearer access-secret"
    assert options["json"]["stream"] is True and options["json"]["store"] is False
    assert options["allow_redirects"] is False
    assert "previous_response_id" not in options["json"]


def test_multi_message_preserves_developer_user_assistant_history(model, posted):
    calls, outputs = posted
    outputs.append(Response([completed()]))
    model.invoke([SystemMessage("system"), ChatMessage(role="developer", content="developer"),
                  HumanMessage("first"), ChatMessage(role="assistant", content="prior"), HumanMessage("next")])
    assert [item["role"] for item in calls[0][1]["json"]["input"]] == ["developer", "developer", "user", "assistant", "user"]


class Decision(BaseModel):
    action: str
    evidence: str


def test_native_structured_output_validates_pydantic_schema(model, posted):
    calls, outputs = posted
    outputs.append(Response([completed('{"action":"Hold","evidence":"Limited data"}')]))
    result = model.with_structured_output(Decision).invoke("decide")
    assert isinstance(result, Decision) and result.action == "Hold"
    format_ = calls[0][1]["json"]["text"]["format"]
    assert format_["type"] == "json_schema" and format_["strict"] is True
    assert format_["schema"]["additionalProperties"] is False


def test_include_raw_reports_parse_failure(model, posted):
    _, outputs = posted
    outputs.append(Response([completed("not-json")]))
    result = model.with_structured_output(Decision, include_raw=True).invoke("decide")
    assert result["parsed"] is None and result["parsing_error"] is not None
    assert result["raw"].content == "not-json"


@pytest.mark.parametrize("setting", ["temperature", "max_tokens"])
def test_unsupported_route_settings_fail_before_network(setting):
    with pytest.raises(ValueError, match=setting):
        build_llm_kwargs({"llm_provider": "chatgpt_plan", setting: 1})


def test_credentials_cannot_be_redirected_to_other_backend():
    with pytest.raises(ValueError, match="official"):
        create_llm_client("chatgpt_plan", "model", base_url="https://evil.invalid").get_llm()


def test_stream_quota_failure_after_partial_text_never_returns_success(model, posted):
    calls, outputs = posted
    model.max_retries = 3
    outputs.append(Response([
        {"type": "response.output_text.delta", "delta": "partial"},
        {"type": "response.failed", "response": {"error": {"code": "subscription_sharing_usage_limit_exceeded"}}},
    ]))
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "quota" and len(calls) == 1


@pytest.mark.parametrize("events,kind", [([], "interrupted"),
                                         ([{"type": "response.incomplete"}], "incomplete")])
def test_missing_or_incomplete_terminal_event_fails(model, posted, events, kind):
    _, outputs = posted
    outputs.append(Response(events))
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == kind


def test_rate_limit_retries_are_bounded(model, posted, monkeypatch):
    calls, outputs = posted
    model.max_retries = 2
    slept = []
    monkeypatch.setattr(plan.time, "sleep", slept.append)
    outputs.extend([Response(status=429, body={"error": {"code": "rate_limit_exceeded"}}, headers={"retry-after": "0"}),
                    Response(status=503, body={"detail": "unavailable"}), Response([completed()])])
    assert model.invoke("hello").content == "OK"
    assert len(calls) == 3 and len(slept) == 2


def test_admission_auth_errors_are_redacted(model, posted):
    _, outputs = posted
    outputs.append(Response(status=401, body={"detail": "Bearer access-secret", "access_token": "access-secret"},
                            headers={"x-request-id": "access-secret"}))
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "auth"
    assert "access-secret" not in str(error.value) + json.dumps(error.value.details) + error.value.request_id


def test_transport_timeout_is_safe(model, monkeypatch):
    def fail(*args, **kwargs):
        raise requests.Timeout("Bearer access-secret")

    monkeypatch.setattr(plan.requests, "post", fail)
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "timeout" and "access-secret" not in str(error.value)


def test_cli_auth_status_and_analysis_preflight_are_keyless(model, monkeypatch):
    from cli.main import app
    from cli.prompts import ensure_api_key

    assert ensure_api_key("chatgpt_plan") is None
    result = CliRunner().invoke(app, ["auth", "status", "chatgpt_plan"])
    assert result.exit_code == 0
    assert '"plan_usage_enabled": true' in result.stdout
    assert "access-secret" not in result.stdout
    monkeypatch.setattr(plan.ChatGPTAuthStore, "preflight", lambda self: (_ for _ in ()).throw(
        SubscriptionError("Please sign in", kind="auth")))
    assert CliRunner().invoke(app, ["auth", "status", "chatgpt_plan"]).exit_code == 1


def test_account_model_catalog_filters_visibility_and_uses_oauth(model, monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(body={"models": [{"slug": "one", "display_name": "One", "visibility": "list"},
                                          {"slug": "hidden", "display_name": "Hidden", "visibility": "hidden"}]})

    monkeypatch.setattr(plan.requests, "get", get)
    assert plan.model_options() == [("One", "one")]
    assert calls[0][0].endswith("/v1/models")
    assert calls[0][1]["headers"]["Authorization"] == "Bearer access-secret"


@pytest.mark.parametrize("event", [
    {"type": "response.failed", "response": None},
    {"type": "response.failed", "response": []},
    {"type": "response.completed", "response": []},
    {"type": ["response.completed"]},
])
def test_malformed_terminal_events_are_classified_without_retry_or_fallback(model, posted, event):
    calls, outputs = posted
    model.max_retries = 2
    outputs.append(Response([event]))
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "malformed_output" and len(calls) == 1


@pytest.mark.parametrize("overrides", [
    {"usage": ["opaque-untrusted-output"]},
    {"usage": {"input_tokens": "opaque-untrusted-output"}},
    {"usage": {"output_tokens": -1}},
    {"output": [{"type": "message", "content": {"type": "output_text"}}]},
    {"output": [{"type": "message", "content": [{"type": "output_text", "text": 1}]}]},
    {"output": [{"type": "message", "content": [{"type": "unknown"}]}]},
])
def test_malformed_completion_content_and_usage_have_safe_errors(model, posted, overrides):
    _, outputs = posted
    event = completed()
    event["response"].update(overrides)
    outputs.append(Response([event]))
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "malformed_output"
    assert "opaque-untrusted-output" not in str(error.value)


@pytest.mark.parametrize("body", [[], {"models": [None]}, {"models": "opaque"},
                                     {"models": [{"visibility": "list", "slug": None, "display_name": "Name"}]}])
def test_malformed_catalog_is_actionable_and_does_not_leak_raw_data(model, monkeypatch, body):
    monkeypatch.setattr(plan.requests, "get", lambda *a, **k: Response(body=body))
    with pytest.raises(SubscriptionError, match="model catalog"):
        plan.model_options()


def test_real_sse_bytes_use_utf8_regardless_of_requests_text_default(model, posted):
    import io

    _, outputs = posted
    class EventStream(Response, requests.Response):
        def iter_lines(self, **kwargs):
            yield from requests.Response.iter_lines(self, **kwargs)

    response = EventStream()
    response.encoding = "ISO-8859-1"  # Requests default for text/event-stream
    response.raw = io.BytesIO(('data: ' + json.dumps(completed("廣東話報告 ☕"), ensure_ascii=False) + '\n\n').encode())
    response._content_consumed = False
    outputs.append(response)
    assert model.invoke("hello").content == "廣東話報告 ☕"


def test_completed_terminal_event_does_not_wait_for_eof_or_repeat_inference(model, posted):
    calls, outputs = posted

    class Stream(Response):
        def iter_lines(self, **kwargs):
            yield from super().iter_lines(**kwargs)
            raise requests.ReadTimeout("peer kept the socket open after completion")

    outputs.append(Stream([completed()]))
    model.max_retries = 2
    assert model.invoke("hello").content == "OK" and len(calls) == 1


def test_invalid_utf8_is_rejected_without_raw_content(model, posted):
    _, outputs = posted

    class Stream(Response):
        def iter_lines(self, **kwargs):
            yield b'data: \xff opaque-untrusted-content'

    outputs.append(Stream())
    with pytest.raises(SubscriptionError) as error:
        model.invoke("hello")
    assert error.value.kind == "malformed_output" and "opaque-untrusted-content" not in str(error.value)


@pytest.mark.parametrize("kind,status", [("auth", 401), ("permission", 403)])
def test_non_json_catalog_admission_keeps_http_auth_classification(model, monkeypatch, kind, status):
    class Admission(Response):
        def json(self):
            raise ValueError("opaque-untrusted-diagnostic")

    monkeypatch.setattr(plan.requests, "get", lambda *a, **k: Admission(status=status))
    with pytest.raises(SubscriptionError) as error:
        plan.model_options()
    assert error.value.kind == kind and "opaque-untrusted-diagnostic" not in str(error.value)
