"""Exercise the Responses tool protocol through real LangChain/LangGraph nodes."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from tradingagents.agents.analysts.market_analyst import create_market_analyst
from tradingagents.agents.structured import invoke_structured_or_freetext
from tradingagents.graph.analyst_execution import ANALYST_NODE_SPECS
from tradingagents.graph.setup import _analyst_graph
from tradingagents.llm_clients.chatgpt_plan_client import responses_input
from tradingagents.llm_clients.subscription_errors import SubscriptionError

from . import test_chatgpt_plan as transport
from .test_chatgpt_plan import Response, completed

model = transport.model
posted = transport.posted


@tool
def stock_price(symbol: str) -> str:
    """Look up a stock price in the supplied offline data."""
    return f"{symbol}: 123"


def function(name="stock_price", call_id="call-1", args=None, **overrides):
    return {"type": "function_call", "namespace": "tradingagents", "name": name,
            "call_id": call_id, "arguments": json.dumps(args or {"symbol": "AAPL"}), **overrides}


def test_bind_tools_returns_native_calls_and_continues_multiple_rounds(model, posted):
    calls, outputs = posted
    reasoning = {"type": "reasoning", "id": "reason-1", "summary": [], "encrypted_content": "opaque-state"}
    outputs.extend([Response([completed(output=[reasoning, function()])]),
                    Response([completed(output=[function(call_id="call-2", args={"symbol": "MSFT"})])]),
                    Response([completed("Both stock prices retrieved")])])
    bound = model.bind_tools([stock_price])
    messages = [SystemMessage("Use only supplied data"), HumanMessage("Compare prices")]
    first = bound.invoke(messages)
    assert first.tool_calls == [{"type": "tool_call", "id": "call-1", "name": "stock_price", "args": {"symbol": "AAPL"}}]
    assert first.invalid_tool_calls == []
    messages += [first, ToolMessage(content=stock_price.invoke(first.tool_calls[0]["args"]), tool_call_id="call-1")]
    second = bound.invoke(messages)
    messages += [second, ToolMessage(content=stock_price.invoke(second.tool_calls[0]["args"]), tool_call_id="call-2")]
    assert bound.invoke(messages).content == "Both stock prices retrieved"
    inputs = [request[1]["json"]["input"] for request in calls]
    assert inputs[1][2] == reasoning
    assert [i["call_id"] for i in inputs[2] if i.get("type") == "function_call_output"] == ["call-1", "call-2"]
    assert [i["output"] for i in inputs[2] if i.get("type") == "function_call_output"] == ["AAPL: 123", "MSFT: 123"]
    definition = calls[0][1]["json"]["tools"][0]
    assert definition["type"] == "namespace"
    assert definition["tools"][0]["strict"] is True
    assert "function" not in definition["tools"][0]


def test_parallel_calls_have_distinct_tool_results(model, posted):
    calls, outputs = posted
    outputs.extend([Response([completed(output=[function(call_id="a"), function(call_id="b")])]), Response([completed()])])
    bound = model.bind_tools([stock_price])
    first = bound.invoke("Fetch twice")
    bound.invoke([HumanMessage("Fetch twice"), first, ToolMessage(content="B", tool_call_id="b"),
                  ToolMessage(content="A", tool_call_id="a")])
    assert [i["call_id"] for i in calls[1][1]["json"]["input"] if i.get("type") == "function_call_output"] == ["b", "a"]


@pytest.mark.parametrize("bad_call", [
    function(name="unbound"), function(arguments="not-json"), function(arguments="[]"),
    function(namespace="other"), function(call_id=""),
])
def test_malformed_or_unbound_calls_fail_before_tool_execution(model, posted, bad_call):
    _, outputs = posted
    outputs.append(Response([completed(output=[bad_call])]))
    with pytest.raises(SubscriptionError) as error:
        model.bind_tools([stock_price]).invoke("fetch")
    assert error.value.kind == "malformed_output"


def test_duplicate_response_call_ids_are_rejected(model, posted):
    _, outputs = posted
    outputs.append(Response([completed(output=[function(), function()])]))
    with pytest.raises(SubscriptionError, match="malformed"):
        model.bind_tools([stock_price]).invoke("fetch")


@pytest.mark.parametrize("choice,expected", [("auto", "auto"), (True, "required"),
                                            ("stock_price", {"type": "function", "namespace": "tradingagents", "name": "stock_price"})])
def test_tool_choice_uses_responses_format(model, posted, choice, expected):
    calls, outputs = posted
    outputs.append(Response([completed()]))
    model.bind_tools([stock_price], tool_choice=choice).invoke("fetch")
    assert calls[0][1]["json"]["tool_choice"] == expected


@pytest.mark.parametrize("messages", [
    [ToolMessage(content="orphan", tool_call_id="missing")],
    [AIMessage(content="", tool_calls=[{"id": "pending", "name": "stock_price", "args": {}}])],
    [AIMessage(content="", tool_calls=[{"id": "a", "name": "stock_price", "args": {}}]),
     ToolMessage(content="A", tool_call_id="a"), ToolMessage(content="again", tool_call_id="a")],
    [AIMessage(content="", tool_calls=[{"id": "a", "name": "stock_price", "args": {}}]),
     ToolMessage(content="A", tool_call_id="a"),
     AIMessage(content="", tool_calls=[{"id": "a", "name": "stock_price", "args": {}}]),
     ToolMessage(content="again", tool_call_id="a")],
])
def test_invalid_history_is_rejected_without_a_request(model, posted, messages):
    calls, _ = posted
    with pytest.raises(ValueError):
        model.bind_tools([stock_price]).invoke(messages)
    assert calls == []


def test_synthetic_langchain_history_is_converted():
    inputs = responses_input([AIMessage(content="Fetching", tool_calls=[
        {"id": "a", "name": "stock_price", "args": {"symbol": "AAPL"}}]),
        ToolMessage(content="123", tool_call_id="a")])
    assert inputs[1]["namespace"] == "tradingagents" and inputs[2]["type"] == "function_call_output"


def test_quota_error_does_not_trigger_agent_freetext_fallback(model, posted):
    calls, outputs = posted
    outputs.append(Response([{"type": "response.failed", "response": {"error": {
        "code": "subscription_sharing_usage_limit_exceeded"}}}]))
    from .test_chatgpt_plan import Decision

    with pytest.raises(SubscriptionError) as error:
        invoke_structured_or_freetext(model.with_structured_output(Decision), model, "decide", str, "Trader")
    assert error.value.kind == "quota" and len(calls) == 1


def test_real_market_analyst_stock_indicator_snapshot_and_final_report(model, posted, monkeypatch):
    """Actual analyst prompt, injected state, ToolNode and history reducer."""
    import tradingagents.agents.tools as tools_module

    calls, outputs = posted
    executed = []

    def data(name, *args):
        executed.append((name, args))
        return "date,close\n2026-10-02,123" if name == "get_stock_data" else "RSI=51"

    monkeypatch.setattr(tools_module, "route_to_vendor", data)
    monkeypatch.setattr(tools_module, "build_verified_market_snapshot", lambda *args: "Verified close=123; RSI=51")
    outputs.extend([
        Response([completed(output=[function("get_stock_data", "stock", {"start_date": "2026-09-01", "end_date": "2026-10-02"})])]),
        Response([completed(output=[function("get_indicators", "indicator", {"indicator": "rsi", "curr_date": "2026-10-02", "look_back_days": 30})])]),
        Response([completed(output=[function("get_verified_market_snapshot", "snapshot", {"curr_date": "2026-10-02", "look_back_days": 30})])]),
        Response([completed("AAPL close 123, RSI 51: neutral market report.")]),
    ])
    graph = _analyst_graph(ANALYST_NODE_SPECS["market"], create_market_analyst(model), max_tool_rounds=5)
    result = graph.invoke({"company_of_interest": "AAPL", "trade_date": "2026-10-02",
                           "messages": [HumanMessage("Analyze AAPL")]})
    assert result["market_report"].startswith("AAPL close 123")
    assert [name for name, _ in executed] == ["get_stock_data", "get_indicators"]
    assert executed[0][1][0] == "AAPL"  # Injected from state, never guessed by the model.
    assert len(calls) == 4
    for request, expected in zip(calls[1:], ["stock", "indicator", "snapshot"], strict=True):
        history = request[1]["json"]["input"]
        assert history[-1]["type"] == "function_call_output" and history[-1]["call_id"] == expected
    assert "Verified close=123" in calls[-1][1]["json"]["input"][-1]["output"]
    for definition in calls[0][1]["json"]["tools"][0]["tools"]:
        assert "symbol" not in definition["parameters"]["properties"]
        assert "trade_date" not in definition["parameters"]["properties"]


def test_market_analyst_round_budget_uses_existing_freetext_wrapup(model, posted, monkeypatch):
    import tradingagents.agents.tools as tools_module

    calls, outputs = posted
    monkeypatch.setattr(tools_module, "route_to_vendor", lambda *a: "stock data")
    outputs.extend([Response([completed(output=[function("get_stock_data", "stock", {
        "start_date": "2026-09-01", "end_date": "2026-10-02"})])]), Response([completed("Limited data report")])])
    graph = _analyst_graph(ANALYST_NODE_SPECS["market"], create_market_analyst(model), max_tool_rounds=1)
    assert graph.invoke({"company_of_interest": "AAPL", "trade_date": "2026-10-02", "messages": []})["market_report"] == "Limited data report"
    assert "tools" not in calls[1][1]["json"]
    assert all(i.get("type") != "function_call_output" for i in calls[1][1]["json"]["input"])
