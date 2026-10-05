"""Subscription providers reuse the upstream quick/deep factory and graph."""

import json

import pytest
import typer

from cli import selections
from cli.prompts import _llm_provider_table, ensure_api_key
from tradingagents import default_config
from tradingagents.agents.managers.research_manager import create_research_manager
from tradingagents.llm_clients import factory, gemini_cli_client
from tradingagents.llm_clients.chatgpt_plan_client import ChatGPTPlanChatModel
from tradingagents.llm_clients.gemini_cli_client import GeminiCLIChatModel
from tradingagents.llm_clients.subscription_registry import SUBSCRIPTION_PROVIDERS


def config(**overrides):
    return {**default_config.DEFAULT_CONFIG, "llm_provider": "openai", "backend_url": "https://api.openai.com/v1",
            "quick_think_provider": "chatgpt_plan", "quick_think_llm": "account-model",
            "deep_think_provider": "gemini_cli", "deep_think_llm": "auto", **overrides}


def test_supported_subscription_pair_uses_existing_tier_factory():
    quick = factory.create_tier_client(config(), "quick").get_llm()
    deep = factory.create_tier_client(config(), "deep").get_llm()
    assert isinstance(quick, ChatGPTPlanChatModel) and isinstance(deep, GeminiCLIChatModel)


@pytest.mark.parametrize("deep", ["chatgpt_plan", "gemini_cli", "google"])
def test_unsupported_quick_tier_fails_before_a_client_is_created(deep, monkeypatch):
    monkeypatch.setattr(factory, "create_llm_client", lambda *a, **k: pytest.fail("must reject before construction"))
    with pytest.raises(ValueError, match="native bind_tools/ToolMessage"):
        factory.create_tier_client(config(quick_think_provider="gemini_cli", deep_think_provider=deep), "quick")


def test_same_subscription_provider_can_serve_both_tiers():
    conf = config(llm_provider="chatgpt_plan", backend_url=None, quick_think_provider=None,
                  deep_think_provider=None, deep_think_llm="account-model")
    assert all(isinstance(factory.create_tier_client(conf, tier).get_llm(), ChatGPTPlanChatModel) for tier in ("quick", "deep"))


@pytest.mark.parametrize("quick,deep", [("openai", "gemini_cli"), ("chatgpt_plan", "google"),
                                      ("google", "chatgpt_plan"), ("chatgpt_plan", "anthropic")])
def test_api_providers_remain_available_in_mixed_tiers(quick, deep, monkeypatch):
    made = []
    monkeypatch.setattr(factory, "create_llm_client", lambda **kw: made.append(kw))
    conf = config(quick_think_provider=quick, deep_think_provider=deep)
    for tier in ("quick", "deep"):
        factory.create_tier_client(conf, tier)
    assert [m["provider"] for m in made] == [quick, deep]
    assert all(m["base_url"] is None for m in made if m["provider"] != "openai")


def test_transport_capabilities_and_cli_choices_have_one_definition():
    assert SUBSCRIPTION_PROVIDERS["chatgpt_plan"].tool_calls
    assert SUBSCRIPTION_PROVIDERS["chatgpt_plan"].structured_output == "native_json_schema"
    assert not SUBSCRIPTION_PROVIDERS["gemini_cli"].tool_calls
    assert SUBSCRIPTION_PROVIDERS["gemini_cli"].structured_output == "none"
    choices = {name for _, name, _ in _llm_provider_table()}
    assert SUBSCRIPTION_PROVIDERS.keys() <= choices


def test_cli_rejects_quick_gemini_before_any_authentication(monkeypatch, capsys):
    monkeypatch.setitem(selections.DEFAULT_CONFIG, "quick_think_provider", "gemini_cli")
    monkeypatch.setattr(selections, "ensure_api_key", lambda *a: pytest.fail("should reject first"))
    with pytest.raises(typer.Exit):
        selections._check_tier_providers("gemini_cli")
    assert "cannot serve the quick tier" in capsys.readouterr().out


def test_cli_preflights_each_used_subscription_once_without_api_keys(monkeypatch):
    checked = []
    monkeypatch.setitem(selections.DEFAULT_CONFIG, "quick_think_provider", "chatgpt_plan")
    monkeypatch.setitem(selections.DEFAULT_CONFIG, "deep_think_provider", "gemini_cli")
    monkeypatch.setenv("TRADINGAGENTS_QUICK_THINK_LLM", "account-model")
    monkeypatch.setenv("TRADINGAGENTS_DEEP_THINK_LLM", "auto")
    monkeypatch.setattr(selections, "ensure_api_key", lambda p: checked.append(p))
    selections._check_tier_providers("openai")
    assert checked == ["chatgpt_plan", "gemini_cli"]


def test_gemini_cli_key_preflight_does_not_prompt_for_google_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(gemini_cli_client, "preflight", lambda: None)
    assert ensure_api_key("gemini_cli") is None


def test_deep_research_manager_uses_upstream_freetext_fallback(monkeypatch):
    model = factory.create_tier_client(config(), "deep").get_llm()
    monkeypatch.setattr(gemini_cli_client, "preflight", lambda *a: ("/gemini", "0.62.0"))
    monkeypatch.setattr(gemini_cli_client, "_run_process", lambda *a, **k: (
        json.dumps({"response": "**Recommendation**: Hold\n**Rationale**: Evidence is balanced."}), "", 0))
    node = create_research_manager(model)
    result = node({"company_of_interest": "AAPL", "trade_date": "2026-10-02",
                   "investment_debate_state": {"history": "bull and bear evidence", "count": 2}})
    assert result["investment_plan"].startswith("**Recommendation**: Hold")


def test_subscription_config_overlay_and_run_settings_preserve_tier_names(monkeypatch):
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    monkeypatch.setenv("TRADINGAGENTS_QUICK_THINK_PROVIDER", "chatgpt_plan")
    monkeypatch.setenv("TRADINGAGENTS_DEEP_THINK_PROVIDER", "gemini_cli")
    conf = default_config.build_default_config()
    graph = object.__new__(TradingAgentsGraph)
    graph.config, graph.selected_analysts = conf, ("market",)
    settings = graph.run_settings()
    assert settings["quick_think_provider"] == "chatgpt_plan"
    assert settings["deep_think_provider"] == "gemini_cli"
