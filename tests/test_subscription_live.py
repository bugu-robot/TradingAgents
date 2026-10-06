"""Opt-in subscription checks; never enabled by the default upstream test run.

RUN_SUBSCRIPTION_LIVE=1 python -m pytest -o addopts='' -m integration
tests/test_subscription_live.py -q --tb=short

These use real plan allowance. They never launch login or use an API key.
"""

import os
from typing import Literal

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from pydantic import BaseModel

from tradingagents.llm_clients.chatgpt_plan_auth import ChatGPTAuthStore
from tradingagents.llm_clients.factory import create_llm_client

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.environ.get("RUN_SUBSCRIPTION_LIVE") != "1", reason="Set RUN_SUBSCRIPTION_LIVE=1 after explicit subscription sign-in.")]


@pytest.fixture
def plan():
    model = os.environ.get("CHATGPT_PLAN_LIVE_MODEL")
    if not model:
        pytest.fail("Set CHATGPT_PLAN_LIVE_MODEL to a slug from tradingagents auth models chatgpt_plan.")
    llm = create_llm_client("chatgpt_plan", model, max_retries=1, timeout=180).get_llm()
    # tests/conftest blanks config overlays. Optional dedicated live variables
    # preserve an explicitly chosen credential profile without changing it.
    llm._auth = ChatGPTAuthStore(directory=os.environ.get("CHATGPT_PLAN_LIVE_AUTH_DIR"),
                                profile=os.environ.get("CHATGPT_PLAN_LIVE_PROFILE"))
    llm._auth.preflight()
    return llm


def test_chatgpt_plan_live_multi_message_invoke(plan):
    result = plan.invoke([SystemMessage("Follow the supplied conversation. Return only the requested marker."),
                          HumanMessage("The marker is SUBSCRIPTION_SMOKE_OK."), AIMessage("Understood."),
                          HumanMessage("Return the marker now.")])
    assert "SUBSCRIPTION_SMOKE_OK" in result.content


class SmokeResult(BaseModel):
    marker: Literal["SUBSCRIPTION_SMOKE_OK"]
    evidence: str


def test_chatgpt_plan_live_native_structured_output(plan):
    result = plan.with_structured_output(SmokeResult).invoke(
        "Return marker SUBSCRIPTION_SMOKE_OK and evidence 'subscription structured output test'.")
    assert isinstance(result, SmokeResult) and result.marker == "SUBSCRIPTION_SMOKE_OK"


@tool
def smoke_lookup(stage: Literal["first", "second"]) -> str:
    """Return the offline verification value for the requested sequential stage."""
    return "value-1" if stage == "first" else "value-2"


def test_chatgpt_plan_live_sequential_tool_continuation(plan):
    bound = plan.bind_tools([smoke_lookup])
    history = [SystemMessage("Call smoke_lookup for first, wait for its result, then call it for second. "
                             "After both results, answer with both values. Do not call both in one turn."),
               HumanMessage("Run the two sequential verification stages.")]
    executed, rounds = [], 0
    for _ in range(5):
        answer = bound.invoke(history)
        history.append(answer)
        if not answer.tool_calls:
            break
        rounds += 1
        for call in answer.tool_calls:
            assert call["name"] == "smoke_lookup"
            executed.append(call["args"]["stage"])
            history.append(ToolMessage(content=smoke_lookup.invoke(call["args"]), tool_call_id=call["id"]))
    assert executed == ["first", "second"] and rounds == 2
    assert not answer.tool_calls and "value-1" in answer.content and "value-2" in answer.content


def test_gemini_cli_live_cached_google_signin_and_json():
    llm = create_llm_client("gemini_cli", os.environ.get("GEMINI_CLI_LIVE_MODEL", "auto"),
                            max_retries=1, timeout=180).get_llm()
    result = llm.invoke([SystemMessage("Use only supplied text. Return the marker requested in the latest message."),
                         HumanMessage("Marker SUBSCRIPTION_SMOKE_OK"), AIMessage("Understood."),
                         HumanMessage("Return that marker now, without other text.")])
    assert "SUBSCRIPTION_SMOKE_OK" in result.content
    assert not result.tool_calls and result.response_metadata["provider"] == "gemini_cli"
