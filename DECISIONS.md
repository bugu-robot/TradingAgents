# Architecture decisions

Append dated decisions when behavior changes. Earlier entries describe the
decision at that date; they are not silently replaced with new architecture.

## 2026-10-06 — Preserve v0.6.0 tier routing

Use the existing independent quick/deep providers. No separate
`hybrid_subscription` router: it duplicates upstream configuration and increases
merge conflicts. Capability admission lives in a centralized registry.

## 2026-10-06 — ChatGPT Plan owns Quick Think

The existing SIWC/Responses adapter supports TradingAgents-controlled tools,
ToolMessage continuation and strict schema output. Quick analysts require this
protocol; a CLI coding agent's autonomous tools do not satisfy it. ChatGPT Plan
also remains available for both tiers. Retain existing working OAuth code unless
a protocol/security issue is demonstrated.

## 2026-10-06 — Replace the Gemini CLI subscription path

The earlier Gemini CLI adapter was implemented and tested offline, never accepted
as a live Google AI Pro verification. The user explicitly replaced that design
with official Antigravity CLI, whose current documentation ties Pro allowance to
Antigravity and exposes headless native schema output. Remove the old adapter
and its subscription tests/catalog/examples; Git history preserves that work.
Upstream's ordinary `google` API provider remains untouched.

## 2026-10-06 — Antigravity starts deep-only and reasoning-only

Use Antigravity as a transport for deep manager reasoning and native schemas.
Do not expose it for Quick Think without a separately proven and tested native
TradingAgents tool protocol. Disable autonomous filesystem, command, web, MCP,
plugin, skill and subagent actions and reject action metadata. Do not use
dangerously-skip-permissions or bypass administrator policy.

## 2026-10-06 — Fail closed on billing and configuration ambiguity

Subscription means signed-in personal plan allowance. API keys, Vertex, ADC,
service accounts, custom endpoints and purchased AI-credit overage are prohibited
for `antigravity_cli`. Strip routing environment variables and reject unsafe real
configuration before inference. Never automatically modify the user's global
settings or replace official system configuration paths with empty files.

## 2026-10-06 — Acceptance requires real entitlement and a full run

Mocked responses cannot establish Google AI Pro/ChatGPT Plus identity, available
models, quota accounting or absence of billing. Keep offline and live results
separate; skipped live tests are not successes. Draft PR #1 stays unmerged until
the consolidated live checks and full AAPL graph/report validation pass. Only
the user can subsequently authorize production acceptance/merge.

## 2026-10-06 — Follow OpenAI's self-hosted VM guidance

The primary documented flow completes OAuth locally and securely transfers this
tool's protected profile to the VM, preserving its independently generated host
ID. SSH loopback forwarding can remain an optional convenience, clearly labelled
as our deployment alternative rather than OpenAI's official method.

## 2026-10-06 — Require a dedicated, reviewed Antigravity environment

The adapter reads the real global settings and requires explicit no-overage,
strict/sandbox permission policy with all action namespaces denied. It refuses
unknown routing/policy fields and shared customizations before starting any CLI
process. A minimal OS/keyring child environment avoids both known and future
gateway/ADC/API switches. Use a dedicated OS account if existing general-purpose
Antigravity settings conflict; do not automatically mutate or hide them.
