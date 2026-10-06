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

## 2026-10-06 — Require positive Pro and pre-input initialization evidence

Official headless docs do not promise a machine-readable Pro identity field or
when init is emitted relative to stdin input. Require CLI-owned informational
personal Pro evidence and an exact isolated/pinned/strict/zero-tool init before
submitting the prompt. Missing evidence blocks inference. These gates are safety
requirements, not a claim that the actual CLI already satisfies them; live
validation may identify an official-interface blocker. Never invent an auth
endpoint, read secure Google tokens or replace this evidence with a user marker.

## 2026-10-06 — Independently validate native schema output

Add jsonschema for local Draft 2020-12 validation before strict Pydantic parsing.
Pydantic validators in upstream schemas can intentionally coerce strings, so
Pydantic alone does not prove the CLI respected the generated JSON Schema.
Require the echoed schema, a complete structured object and matching response
JSON. Native schema/auth/quota failures are terminal SubscriptionError values;
upstream managers must not issue another request through free-text fallback.

## 2026-10-06 — Treat malformed native protocol/schema as terminal

Focused review identified ambiguous JSON, external schema scope/reference paths
and coercive ChatGPT parsing that could escape the subscription error boundary.
Use strict shared JSON, no-fetch schema validation and terminal safe errors for
both transports. Informational probes need the same bounds/group cleanup as
model processes. Protect app storage and locks without modifying unrelated paths;
these are security corrections, not a change to the official OAuth protocol.

## 2026-10-06 — Withdraw speculative headless Pro-report admission

Final official-reference review supersedes the earlier proposed informational
Pro-report gate: `/help` is documented as a TUI panel, not a non-inference
headless account/plan report. Interactive status-line `plan_tier` does not prove
a headless account check exists. Do not send `/help` as a prompt, trust
model-generated identity, read Google tokens, accept manual/local attestations
or add a force/bypass setting. Authentication preflight now always blocks the
reviewed 1.2.17 adapter before inference. The prepared reasoning/schema transport
remains offline tested; Google activation needs a supported official preflight
and another code review, then the single live session. User login cannot fix
this interface blocker. This is an explicit limitation, not a working feature.

## 2026-10-06 — Admit documented cached-account execution, not invented attestation

Supersedes the earlier positive-Pro/pre-input and unconditional-authentication
gate decisions above. Current official headless docs explicitly support cached
account credentials and authentication-required errors without a terminal.
Require real safe settings, no API/provider/Vertex/ADC/custom routing, credits
off, sanitized environment, a scoped zero-tool agent, validated stream init and
terminal SUCCESS. Do not invent a separate machine-readable Pro attestation,
inspect Google tokens or send a speculative account prompt. Submit stdin as
documented; validate init before accepting any response rather than require an
undocumented init-before-input ordering. Official interactive /usage evidence
after live smokes is mandatory to accept actual Google AI Pro entitlement/quota.
Offline success does not prove live credentials, plan or billing.

## 2026-10-06 — Discover independent account catalogs and pin exact model slugs

Separate catalog preflight from inference admission. `agy models` is the public
non-inference Antigravity catalog command; never consume a model turn to discover
models. Accept any catalog-listed family with conservative safe slug syntax,
including Gemini, Claude and future families. Reject unlisted/custom API IDs;
refresh catalog membership before inference and pin `--model` without fallback.
ChatGPT Quick models independently come from its signed-in account catalog.
Existing Quick/Deep provider/model env variables and Antigravity low/medium/high
effort map directly to the v0.6.0 factory; no hybrid router is introduced.
