"""Subscription transports and capabilities, separate from API credentials."""

from __future__ import annotations

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SubscriptionProvider:
    label: str
    module: str
    client_class: str
    tool_calls: bool
    structured_output: str
    unsupported_parameters: frozenset[str]
    knob_provider: str | None = None
    configuration_parameters: tuple[tuple[str, str], ...] = ()


SUBSCRIPTION_PROVIDERS: dict[str, SubscriptionProvider] = {
    "chatgpt_plan": SubscriptionProvider(
        label="ChatGPT Plan (Sign in with ChatGPT)",
        module="chatgpt_plan_client", client_class="ChatGPTPlanClient",
        tool_calls=True, structured_output="native_json_schema",
        unsupported_parameters=frozenset({"temperature", "max_tokens", "max_output_tokens"}),
        knob_provider="openai",
    ),
    "antigravity_cli": SubscriptionProvider(
        label="Antigravity CLI (Google AI Pro; deep only; activation blocked)",
        module="antigravity_cli_client", client_class="AntigravityCLIClient",
        tool_calls=False, structured_output="native_json_schema",
        unsupported_parameters=frozenset({"temperature", "max_tokens", "max_output_tokens"}),
        configuration_parameters=(("antigravity_effort", "effort"),),
    ),
}


def subscription_spec(provider: str) -> SubscriptionProvider | None:
    return SUBSCRIPTION_PROVIDERS.get(provider.lower())


def provider_module(provider: str):
    spec = SUBSCRIPTION_PROVIDERS[provider.lower()]
    return importlib.import_module(f"tradingagents.llm_clients.{spec.module}")


def preflight_subscription(provider: str) -> str | None:
    """Read-only preflight; never launches login or asks for an API key."""
    spec = subscription_spec(provider)
    if spec is None:
        return None
    provider_module(provider).preflight()
    return spec.label


def subscription_model_options(provider: str):
    if subscription_spec(provider) is None:
        return None
    return provider_module(provider).model_options()


def validate_subscription_tier(provider: str, tier: str) -> None:
    spec = subscription_spec(provider)
    if spec is not None and tier == "quick" and not spec.tool_calls:
        raise ValueError(f"{provider} cannot serve the quick tier: TradingAgents analysts need "
                         "native bind_tools/ToolMessage continuation. Use it for deep thinking "
                         "and choose chatgpt_plan or an existing tool-capable provider for quick.")
