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

The adapter additionally requires CLI-owned positive personal Pro identification
and validates a zero-tool, strict, isolated init **before writing stdin**. Public
docs do not guarantee these two output contracts. If the installed CLI cannot
supply them, transport is blocked before inference; this is an explicit pending
compatibility gate, not a claimed verified subscription feature.

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
