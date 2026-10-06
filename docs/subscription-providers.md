# Subscription-backed providers

This fork extends TradingAgents **v0.6.0** (`1394a3f72aa4393e1a98f51b382434c4b4c2d972`)
using the existing independent quick/deep providers. Work remains on
`feat/subscription-providers`, [Draft PR #1](https://github.com/bugu-robot/TradingAgents/pull/1).
**Do not merge. No live subscription functionality or production acceptance has
been verified.** See [STATUS](../STATUS.md) for current offline evidence.

## Provider matrix

| Provider | Official transport | Quick | Deep | Native TradingAgents tools | Native schema |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | App-specific Sign in with ChatGPT, public Responses API | Yes | Yes | Yes, ToolMessage and sequential/parallel continuation | Responses JSON Schema |
| `antigravity_cli` | Official Linux `agy` 1.2.17, CLI-owned Google sign-in | No | Yes, subject to safety gates | No | CLI JSON Schema and local validation |
| Existing API providers | Existing API clients | Existing behavior | Existing behavior | Existing behavior | Existing behavior |

Initial subscription routing: `chatgpt_plan` quick, `antigravity_cli` deep.
ChatGPT Plan for both tiers also works at the adapter level. Antigravity quick
is rejected before authentication or inference. The former Gemini CLI
subscription adapter has been removed; the upstream `google` Gemini API provider
is unchanged. API providers remain explicitly available and bill as before.

## ChatGPT Plan

TradingAgents registers its own public OAuth client and asks the user to approve
plan usage. Codex credentials or an OpenAI API key are not substituted for this
grant. PKCE, state, nonce and verified OIDC claims protect sign-in. Server-issued
client IDs and rotating tokens live in owner-only, atomically written, locked
profiles under `~/.config/tradingagents/chatgpt_plan`. Analysis never launches
login, reads browser cookies or prints credentials.

```bash
tradingagents auth login chatgpt_plan --profile plus
tradingagents auth use plus
tradingagents auth status chatgpt_plan
tradingagents auth models chatgpt_plan
```

If prior consent omitted plan usage, repeat login with `--enable-plan-usage`.
`auth accounts` lists profiles; `auth logout --profile plus` attempts remote
revocation before removing local tokens. A catalog slug is required; model names
are not treated as entitlement proof. ChatGPT connected-app allowance and any
optional credits remain controlled by the account's settings.

The Responses adapter sends complete stateless text history, developer
instructions, native namespaced functions and matching function-call outputs.
Reasoning items are preserved between turns. Only a validated completed SSE
response is accepted. Duplicate/replayed call IDs, partial streams, quota and
auth failures stop the run without API or free-text retry fallback.

For an Ubuntu VM, the primary official OpenAI procedure is **local OAuth followed
by secure transfer of this app's issued profile**, preserving the VM's separate
host ID. Optional SSH loopback forwarding is our deployment convenience, not
described as an official OpenAI method. Exact commands and source links are in
[VERIFICATION](../VERIFICATION.md).

## Antigravity and Google AI Pro

Antigravity owns Google OAuth, keyring storage and refresh. Use the official
interactive `agy` sign-in; over SSH, open its authorization URL in a local
browser, then paste the browser's code back into the SSH CLI. TradingAgents never
reads, copies or implements Google tokens. Public `agy` headless, stream-json,
model, effort and JSON Schema interfaces are the only transport.

```bash
tradingagents auth status antigravity_cli
tradingagents auth models antigravity_cli
```

These commands check the real global configuration and reviewed executable, then
return the current official-interface blocker. Version 1.2.17 has no documented
non-inference headless personal Pro preflight; `/help` is a TUI panel. The adapter
**always blocks inference** until a supported official preflight is implemented
and reviewed. Login alone cannot fix this. Init-before-input ordering is also
unverified. A model-authored identity report or local attestation is never used.

Subscription-only operation requires explicit `useG1Credits=false`, strict
permissions, sandbox enabled, non-workspace access disabled and all action
namespaces denied. API/provider modes, custom endpoints/models, ADC, unmanaged
policy, shared hooks/MCP/plugins/skills/agents and unknown routing settings fail
before starting a CLI process. TradingAgents does not edit global settings or
substitute empty system policy files. A dedicated OS account may be necessary.

Child processes inherit only reviewed OS/keyring environment variables. Google,
Gemini, Vertex, gateway, API credential and custom routing variables cannot reach
them. A private temporary workspace contains an explicitly scoped tool-free
main agent; no arbitrary evidence file import, slash/skill expansion or unsafe
permission flag is enabled. The prompt is sent only after zero-tool strict init
matches the workspace, agent, model and schema. Autonomous action metadata,
unknown steps and incomplete responses cause rejection and process-group cleanup.

Deep manager Pydantic schemas become native CLI JSON Schema arguments. Complete
terminal output must echo the schema and contain matching JSON/structured value.
Draft 2020-12 validation precedes strict Pydantic validation. Malformed schema,
auth, quota and policy errors are terminal; Research/Portfolio Manager cannot
issue a second billed free-text fallback. Bounded retries apply only to temporary
rate/service failures. Raw CLI diagnostics are classified internally and discarded.

## Configuration

```python
from copy import deepcopy
from tradingagents.default_config import DEFAULT_CONFIG

config = deepcopy(DEFAULT_CONFIG)
config.update({
    "llm_provider": "chatgpt_plan",
    "quick_think_provider": "chatgpt_plan",
    "quick_think_llm": "<slug from ChatGPT account catalog>",
    "deep_think_provider": "antigravity_cli",
    "deep_think_llm": "<gemini slug from agy models>",
    "backend_url": None,
    "quick_think_backend_url": None,
    "deep_think_backend_url": None,
    "temperature": None,
    "max_tokens": None,
    "antigravity_effort": "high",
    "llm_max_retries": 1,
})
```

CLI equivalents use `TRADINGAGENTS_QUICK_THINK_PROVIDER`,
`TRADINGAGENTS_DEEP_THINK_PROVIDER` and existing tier-model settings. Optional
`TRADINGAGENTS_ANTIGRAVITY_EFFORT` accepts documented `low`, `medium`, `high`.
`TRADINGAGENTS_ANTIGRAVITY_CLI_BIN` selects the executable (reviewed version still
required). Subscription providers reject custom URLs, sampling settings and
output-token caps. A centralized registry admits capabilities; no hybrid router
or scattered agent-name conditionals are needed.

## Verification and maintenance

- [STATUS](../STATUS.md): current checkpoint, evidence and blockers.
- [DESIGN](../DESIGN.md): architecture and security boundaries.
- [DECISIONS](../DECISIONS.md): dated decisions and changes.
- [VERIFICATION](../VERIFICATION.md): offline checks and the single Ubuntu session.
- [UPSTREAM_SYNC](../UPSTREAM_SYNC.md): stable upstream integration workflow.
- [Official references](antigravity-official-review.md): accessed 2026-10-06,
  actual Linux binary/help and documented limitations.
- [Security/code review](subscription-code-review.md): findings and regression evidence.

Mocked transport, fake executable lifecycle tests and the real mocked Market
Analyst ToolNode loop prove offline behavior only. All live checks are opt-in and
skip by default. Neither Plus/Pro entitlement nor the complete AAPL graph has
been live verified. Production acceptance requires both in the consolidated
session; keep Draft PR #1 unmerged.
