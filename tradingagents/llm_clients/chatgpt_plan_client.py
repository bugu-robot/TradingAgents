"""LangChain chat adapter for the official ChatGPT plan Responses route."""

from __future__ import annotations

import json
import random
import re
import time
from collections.abc import Sequence
from copy import deepcopy
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field, PrivateAttr

from .base_client import BaseLLMClient
from .chatgpt_plan_auth import RESOURCE, ChatGPTAuthStore
from .subscription_errors import SubscriptionError, redact, response_error

_TOOL_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_NAMESPACE = "tradingagents"


def _without_schema_defaults(schema: dict) -> dict:
    """Strict Responses schemas require explicit values, including nullable fields.

    Keep the upstream tool/model defaults in Python, rather than forwarding
    schema annotations that aren't needed by constrained generation.
    """
    schema = deepcopy(schema)
    schema.pop("default", None)
    for key in ("properties", "$defs", "definitions", "patternProperties"):
        if isinstance(schema.get(key), dict):
            schema[key] = {name: _without_schema_defaults(value) for name, value in schema[key].items()}
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            schema[key] = _without_schema_defaults(schema[key])
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        if isinstance(schema.get(key), list):
            schema[key] = [_without_schema_defaults(value) for value in schema[key]]
    return schema


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(isinstance(c, str) or (
        isinstance(c, dict) and c.get("type") in {"text", "input_text", "output_text"}
    ) for c in content):
        return "\n".join(c if isinstance(c, str) else c["text"] for c in content)
    raise ValueError("Subscription chat adapters currently accept text message content only.")


def responses_input(messages: list[BaseMessage]) -> list[dict]:
    """Replay all history, including native reasoning/function-call items."""
    items = []
    pending = set()
    seen = set()
    for message in messages:
        if isinstance(message, ToolMessage):
            if message.tool_call_id not in pending:
                raise ValueError("ToolMessage has no preceding matching tool call.")
            pending.remove(message.tool_call_id)
            items.append({"type": "function_call_output", "call_id": message.tool_call_id,
                          "output": _text(message.content)})
        elif isinstance(message, AIMessage):
            if message.invalid_tool_calls:
                raise ValueError("Cannot continue invalid tool calls.")
            native = message.additional_kwargs.get("responses_output")
            if native is not None:
                items.extend(deepcopy(native))
            else:
                if message.content:
                    items.append({"role": "assistant", "content": _text(message.content)})
                for call in message.tool_calls:
                    items.append({"type": "function_call", "call_id": call["id"],
                                  "namespace": _NAMESPACE, "name": call["name"],
                                  "arguments": json.dumps(call["args"])})
            for call in message.tool_calls:
                if not call.get("id") or call["id"] in seen:
                    raise ValueError("Tool call IDs must be present and unique.")
                pending.add(call["id"])
                seen.add(call["id"])
        elif isinstance(message, (SystemMessage, HumanMessage, ChatMessage)):
            role = "developer" if isinstance(message, SystemMessage) else (
                "user" if isinstance(message, HumanMessage) else message.role
            )
            if role == "system":
                role = "developer"
            if role not in {"developer", "user", "assistant"}:
                raise ValueError("Unsupported conversation role for ChatGPT plan usage.")
            items.append({"role": role, "content": _text(message.content)})
        else:
            raise ValueError("Unsupported message type for ChatGPT plan usage.")
    if pending:
        raise ValueError("Every tool call must have a ToolMessage result before the next model turn.")
    return items


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (TypeError, ValueError):
            return None
    return max(0.0, min(seconds, 60.0))


def _events(response):
    """SSE data records, including multiline records and error terminal events."""
    data = []
    # SSE is UTF-8. Requests otherwise defaults text/event-stream without an
    # explicit charset to Latin-1, corrupting non-ASCII reports and tool args.
    for line in response.iter_lines(decode_unicode=False):
        if isinstance(line, bytes):
            try:
                line = line.decode("utf-8")
            except UnicodeDecodeError:
                raise SubscriptionError("Malformed UTF-8 in ChatGPT Responses stream.", kind="malformed_output") from None
        if not line:
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield "\n".join(data)


def _completed_response(response, access_token: str) -> dict:
    request_id = redact(response.headers.get("x-request-id"), (access_token,))
    retry_after = _retry_after(response.headers.get("retry-after"))
    if response.status_code != 200:
        try:
            body = response.json()
        except ValueError:
            body = {"detail": "Non-JSON admission error."}
        raise response_error(body, status=response.status_code, request_id=request_id,
                             retry_after=retry_after, secrets=(access_token,))
    for data in _events(response):
        if data == "[DONE]":
            continue
        try:
            event = json.loads(data)
            event_type = event["type"]
            if not isinstance(event_type, str):
                raise ValueError("Invalid event type.")
        except (ValueError, KeyError, TypeError):
            raise SubscriptionError("Malformed ChatGPT Responses event.", kind="malformed_output", request_id=request_id) from None
        if event_type in {"response.failed", "error"}:
            failed = event.get("response")
            if event_type == "response.failed" and not isinstance(failed, dict):
                raise SubscriptionError("Malformed ChatGPT failure event.", kind="malformed_output", request_id=request_id)
            error = (failed.get("error") if isinstance(failed, dict) else None) or event.get("error") or event
            raise response_error({"error": error}, request_id=request_id,
                                 retry_after=retry_after, secrets=(access_token,))
        if event_type == "response.incomplete":
            raise SubscriptionError("ChatGPT response was incomplete; no partial report was accepted.",
                                    kind="incomplete", request_id=request_id)
        if event_type == "response.completed":
            completed = event.get("response")
            if not isinstance(completed, dict) or completed.get("status") != "completed":
                raise SubscriptionError("Malformed ChatGPT completion event.", kind="malformed_output", request_id=request_id)
            return completed  # completed is terminal; do not wait for socket EOF
    raise SubscriptionError("ChatGPT stream ended without a completed response.", kind="interrupted", request_id=request_id)


def response_message(response: dict, tool_names: set[str], *, previous_call_ids: set[str] | None = None) -> AIMessage:
    output = response.get("output")
    if not isinstance(output, list):
        raise SubscriptionError("ChatGPT response has no output array.", kind="malformed_output")
    texts, calls, ids = [], [], set(previous_call_ids or ())
    try:
        for item in output:
            if item["type"] == "message":
                if not isinstance(item["content"], list) or item.get("role", "assistant") != "assistant":
                    raise ValueError("Invalid assistant content.")
                for block in item["content"]:
                    if block["type"] == "refusal":
                        raise SubscriptionError("ChatGPT declined the request.", kind="refusal")
                    if block["type"] == "output_text":
                        if not isinstance(block["text"], str):
                            raise ValueError("Invalid output text.")
                        texts.append(block["text"])
                    else:
                        raise ValueError("Unexpected content block.")
            elif item["type"] == "function_call":
                name, call_id = item["name"], item["call_id"]
                if name not in tool_names or item.get("namespace", _NAMESPACE) != _NAMESPACE:
                    raise ValueError("Unknown function.")
                if not isinstance(call_id, str) or not call_id or call_id in ids:
                    raise ValueError("Missing or duplicate call ID.")
                arguments = json.loads(item["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("Function arguments must be an object.")
                calls.append({"type": "tool_call", "name": name, "args": arguments, "id": call_id})
                ids.add(call_id)
            elif item["type"] != "reasoning":
                raise ValueError("Unexpected output item.")
    except (KeyError, TypeError, ValueError):
        raise SubscriptionError("ChatGPT returned malformed or unbound tool calls.", kind="malformed_output") from None
    if not texts and not calls:
        raise SubscriptionError("ChatGPT completed with no text or tool calls.", kind="malformed_output")
    usage = response.get("usage")
    usage = {} if usage is None else usage
    if not isinstance(usage, dict) or any(
        not isinstance(usage.get(key, 0), int) or isinstance(usage.get(key, 0), bool) or usage.get(key, 0) < 0
        for key in ("input_tokens", "output_tokens", "total_tokens")
    ):
        raise SubscriptionError("ChatGPT returned malformed usage metadata.", kind="malformed_output")
    return AIMessage(content="\n".join(texts), tool_calls=calls,
                     additional_kwargs={"responses_output": deepcopy(output)},
                     response_metadata={"provider": "chatgpt_plan", "model_name": response.get("model"),
                                        "response_id": response.get("id")},
                     usage_metadata={"input_tokens": usage.get("input_tokens", 0),
                                     "output_tokens": usage.get("output_tokens", 0),
                                     "total_tokens": usage.get("total_tokens", 0)})


class ChatGPTPlanChatModel(BaseChatModel):
    model_name: str
    max_retries: int = Field(default=2, ge=0)
    timeout: float = Field(default=600, gt=0)
    reasoning_effort: str | None = None
    _auth: ChatGPTAuthStore = PrivateAttr(default_factory=ChatGPTAuthStore)

    @property
    def _llm_type(self) -> str:
        return "chatgpt_plan"

    @property
    def _identifying_params(self) -> dict:
        return {"model_name": self.model_name}

    def bind_tools(self, tools: Sequence, *, tool_choice: Any = None, strict: bool = True, **kwargs):
        definitions = []
        for tool in tools:
            converted = convert_to_openai_tool(tool, strict=strict)
            if converted.get("type") != "function" or "function" not in converted:
                raise ValueError("ChatGPT plan supports locally executed function tools only.")
            function = converted["function"]
            function["parameters"] = _without_schema_defaults(function["parameters"])
            if not _TOOL_NAME.fullmatch(function["name"]):
                raise ValueError("Function names must follow Responses naming constraints.")
            definitions.append({"type": "function", **function})
        names = [f["name"] for f in definitions]
        if len(set(names)) != len(names):
            raise ValueError("Bound function names must be unique.")
        bound = {"tools": [{"type": "namespace", "name": _NAMESPACE,
                            "description": "TradingAgents tools executed by the calling application.",
                            "tools": definitions}] if definitions else []}
        if tool_choice is not None:
            if tool_choice is True or tool_choice == "any":
                tool_choice = "required"
            if isinstance(tool_choice, str) and tool_choice in names:
                tool_choice = {"type": "function", "namespace": _NAMESPACE, "name": tool_choice}
            if tool_choice not in ("auto", "none", "required") and not isinstance(tool_choice, dict):
                raise ValueError("Unsupported tool_choice for ChatGPT plan usage.")
            bound["tool_choice"] = tool_choice
        return self.bind(**bound, **kwargs)

    def with_structured_output(self, schema, *, include_raw: bool = False,
                               method: str | None = None, strict: bool = True, **kwargs):
        if method not in {None, "json_schema"} or not strict or kwargs:
            raise NotImplementedError("ChatGPT plan structured output uses strict native json_schema.")
        definition = convert_to_openai_tool(schema, strict=True)["function"]
        structured = self.bind(text={"format": {"type": "json_schema", "name": definition["name"],
                                               "schema": _without_schema_defaults(definition["parameters"]), "strict": True}})

        def parse(message):
            if message.tool_calls:
                raise ValueError("Structured response unexpectedly contains tool calls.")
            value = json.loads(message.content)
            if isinstance(schema, type) and issubclass(schema, BaseModel):
                return schema.model_validate(value)
            return value

        if not include_raw:
            return structured | RunnableLambda(parse)

        def parse_with_raw(message):
            try:
                return {"raw": message, "parsed": parse(message), "parsing_error": None}
            except (ValueError, TypeError) as exc:
                return {"raw": message, "parsed": None, "parsing_error": exc}

        return structured | RunnableLambda(parse_with_raw)

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        allowed = {"tools", "tool_choice", "text", "parallel_tool_calls"}
        if stop or set(kwargs) - allowed:
            raise ValueError("Unsupported ChatGPT plan request parameters; see preview limitations.")
        payload = {"model": self.model_name, "input": responses_input(messages),
                   "store": False, "stream": True, "include": ["reasoning.encrypted_content"], **kwargs}
        if self.reasoning_effort:
            payload["reasoning"] = {"effort": self.reasoning_effort}
        tools = {t["name"] for namespace in payload.get("tools", []) for t in namespace["tools"]}
        previous_call_ids = {call["id"] for message in messages if isinstance(message, AIMessage)
                             for call in message.tool_calls}
        for attempt in range(self.max_retries + 1):
            try:
                access_token = self._auth.access_token()
                with requests.post(f"{RESOURCE}/responses", json=payload,
                                   headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                                   stream=True, timeout=(15, self.timeout), allow_redirects=False) as response:
                    completed = _completed_response(response, access_token)
                message = response_message(completed, tools, previous_call_ids=previous_call_ids)
                return ChatResult(generations=[ChatGeneration(message=message)])
            except requests.Timeout:
                error = SubscriptionError("ChatGPT plan request timed out.", kind="timeout")
            except requests.RequestException:
                error = SubscriptionError("ChatGPT plan connection was interrupted.", kind="interrupted")
            except SubscriptionError as exc:
                error = exc
            if not error.retryable or attempt == self.max_retries:
                raise error from None
            time.sleep(error.retry_after if error.retry_after is not None else min(2 ** attempt + random.uniform(0, 0.25), 30))
        raise AssertionError("unreachable")


class ChatGPTPlanClient(BaseLLMClient):
    provider = "chatgpt_plan"

    def get_llm(self) -> ChatGPTPlanChatModel:
        if self.base_url and self.base_url.rstrip("/") != RESOURCE:
            raise ValueError("ChatGPT plan credentials may only be sent to the official https://api.openai.com/v1 route.")
        allowed = {"max_retries", "timeout", "reasoning_effort", "callbacks"}
        if set(self.kwargs) - allowed:
            raise ValueError("Unsupported ChatGPT plan settings; API keys, temperature and output caps are not accepted.")
        if not self.validate_model():
            raise ValueError("Select a model slug from tradingagents auth models chatgpt_plan.")
        return ChatGPTPlanChatModel(model_name=self.model, **self.kwargs)

    def validate_model(self) -> bool:
        # Account-specific models are discovered through the authorized catalog.
        return bool(self.model and self.model.strip() and self.model != "custom")


def preflight():
    ChatGPTAuthStore().preflight()


def model_options():
    auth = ChatGPTAuthStore()
    access_token = auth.access_token()
    try:
        with requests.get(f"{RESOURCE}/models", headers={"Authorization": f"Bearer {access_token}"},
                          timeout=30, allow_redirects=False) as response:
            try:
                body = response.json()
            except ValueError:
                if response.status_code == 200:
                    raise
                body = {"detail": "Non-JSON catalog admission error."}
            if response.status_code != 200:
                raise response_error(body, status=response.status_code, secrets=(access_token,))
        if not isinstance(body, dict) or not isinstance(body.get("models"), list):
            raise ValueError("Invalid catalog envelope.")
        options = []
        for model in body["models"]:
            if not isinstance(model, dict):
                raise ValueError("Invalid catalog entry.")
            if model.get("visibility") == "list":
                if not all(isinstance(model.get(k), str) and model[k].strip() for k in ("display_name", "slug")):
                    raise ValueError("Invalid catalog label.")
                options.append((model["display_name"], model["slug"]))
        return options
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise SubscriptionError("Cannot read the selected ChatGPT account's model catalog.", kind="transient") from None
