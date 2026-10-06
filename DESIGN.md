# Subscription provider design

This fork lets a personal TradingAgents installation use existing ChatGPT Plus
and Google AI Pro allowance through supported official interfaces. API providers
remain available by explicit selection. Subscription providers never fall back
to API keys, Vertex, ADC, service accounts, custom endpoints or purchased overage.

## Upstream architecture

The fork starts at TradingAgents v0.6.0. Its existing `quick_think_provider` and
`deep_think_provider` select independent clients through the upstream factory.
There is no architectural need for a `hybrid_subscription` router. A centralized
subscription capability registry controls tier admission, model selection and
unsupported generation parameters. Ordinary provider modules are preserved.

Quick models serve analysts, researchers, trader, risk analysts and the final
signal extraction. Analyst native `bind_tools` responses become
`AIMessage.tool_calls`; LangGraph ToolNode executes TradingAgents tools and
returns ToolMessage for the next model turn. Deep models serve Research Manager
and Portfolio Manager. Antigravity's autonomous tools cannot replace this loop.

| Provider | Quick | Deep | Native tools | Native structured output |
| --- | --- | --- | --- | --- |
| `chatgpt_plan` | Yes | Yes | Yes | Responses JSON Schema |
| `antigravity_cli` | No | Yes | No | CLI JSON Schema, subject to safety preflight |

## ChatGPT Plan

TradingAgents owns an app-specific public OAuth registration using official
Sign in with ChatGPT: loopback, PKCE, state, nonce and verified ID-token claims.
Each account profile retains its issued client ID and rotating credentials.
Host IDs remain distinct on laptops and VMs. Credentials use owner-only files,
atomic writes and rotation locks. Calls use OAuth bearer access to the public
Responses API, `store=false`, `stream=true`, complete stateless conversation
history and native namespaced tools. Only validated terminal SSE output is
accepted; duplicate/replayed call IDs are rejected before ToolNode execution.

The primary self-hosted flow is official local OAuth plus secure credential
transfer while preserving the VM host ID. SSH loopback forwarding is an optional
deployment convenience, not an official OpenAI procedure.

## Antigravity CLI

Antigravity owns Google sign-in, secure credential storage and token refresh.
The adapter uses the official executable `agy` and public print/stream-json,
model, effort and JSON-schema interfaces. No Google tokens are read or copied.
Only the verified CLI protocol is admitted; automatic updates are disabled for
adapter children. An isolated private workspace and custom main agent scope the
run to supplied evidence. The exact executable/configuration safety contract
will be documented alongside the implementation, not inferred from a prompt.

Before inference, inspect actual user/global configuration. Explicit API
providers, custom models/endpoints, credits overage, conflicting policy,
MCP/plugins/hooks or unsafe permission grants must fail closed. Do not rewrite
global configuration or substitute empty files for administrator/system policy.
Sanitize the child environment, including newer ADC/gateway/agent overrides.
Require tool-free agent configuration and reject tools, subagents or side effects
in stream metadata. Prompts alone are insufficient isolation.

Admission combines real configuration checks, the reviewed executable, an
allowlisted child environment, credits-overage off and an isolated zero-tool
agent. The official CLI uses its cached account sign-in; an unauthenticated
noninteractive request returns an authentication-required error. Read-only
`tradingagents auth status antigravity_cli` additionally calls the documented
`agy -p "/usage" --output-format json`, accepts only a SUCCESS, zero-turn
envelope, and reports local configuration readiness separately from successful
cached-account/backend usage access. It discards raw output, reads no tokens,
and does not infer plan/quota values absent from the stable payload. This check
does not prove Google AI Pro entitlement. No separate attestation endpoint or
speculative account/model prompt is needed.

The official changelog advertises `agy models --output-format json`, but the
SHA-512-verified official Linux 1.2.17 binary rejects the flag and its help omits
it. The adapter uses that exact JSON-only command and never falls back to human
text; consequently Antigravity model discovery and inference fail closed on
that build. Parser fixtures exercise the expected `command.data.models` envelope
with `id`/optional `label`, but that shape is **not verified against a successful
official 1.2.17 response** because the command cannot produce one. Do not claim
the shape is official until a fixed official binary emits it. Model catalog
presence is not entitlement evidence.

`/config` and `/permissions` are also advertised as non-inference JSON commands,
but their stable machine field schemas are not published. They are not parsed
as effective policy gates. Retain the existing local settings/policy checks and
validated zero-tool stream init; document `/config` and `/permissions` evidence
as optional manual review only.

The stream follows the documented stdin-first protocol. Validate the exact
isolated cwd, selected model/agent/schema, strict/request-review mode and empty tool list
as soon as init arrives; reject any unexpected action or terminal status. Accept
only a complete `SUCCESS` result after validated init and exit 0. The protocol
does not promise init before stdin, so startup configuration and permissions
provide the preventive boundary; rejecting metadata cannot undo earlier actions.
Actual CLI scoping and init/schema compatibility remain live acceptance checks.

Real settings always require strict permissions with universal denies. Init may
report strict or the documented request-review mode; neither permits any tools
or bypasses those settings. Always-proceed and unknown modes are rejected.

## Independent model selection

Quick and Deep model selections are independent. ChatGPT slugs come from the
official signed-in account catalog. When the official Antigravity JSON catalog
command works, accept safe slugs from any returned family; do not restrict the
catalog to Gemini. Require conservative slug syntax plus fresh catalog
membership before each inference; reject custom provider/model settings and
unlisted IDs. Pass the exact selected slug using `--model`; mismatched init and
unknown/unavailable models fail without fallback. Availability changes and does
not guarantee plan entitlement. Current official CLI 1.2.17 lacks the
documented models JSON flag, so its Antigravity catalog/model selection is
currently unavailable rather than parsed from human text.
Antigravity effort is independently selected as low, medium or high through
`TRADINGAGENTS_ANTIGRAVITY_EFFORT`; provider/model values use existing tier env
variables. OpenAI authentication and API-provider behavior remain unchanged.

## Structured output and failure boundaries

Deep Pydantic schemas become JSON Schema, passed as an argument without shell
interpolation. Require successful terminal CLI output, the enforced schema and
complete structured value; independently validate it before agent rendering.
Malformed schema/output, auth, quota and policy failures raise SubscriptionError
so upstream structured fallback cannot issue an extra request. Explicitly
unsupported capabilities may use the existing free-text path only when documented.

Retries are bounded for temporary transport/rate failures. Quota, auth,
entitlement, policy and malformed output are terminal. No billing fallback,
partial output, automatic login or hidden credential migration is allowed.
Diagnostics are classified internally and discarded or redacted; tokens, keys,
auth codes and untrusted CLI error text must never reach logs or reports.
Timeout/cancellation must terminate and reap child process groups.

## Maintenance

Keep subscriptions in small adapter modules and the shared capability registry.
Reuse v0.6.0 configuration, graph, schemas and reporting. Avoid provider-name
branches in agent nodes. See [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md) for stable-release
integration and [VERIFICATION.md](VERIFICATION.md) for the acceptance gate.
