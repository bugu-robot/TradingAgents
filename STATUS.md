# Subscription provider status

Updated: 2026-10-06. **Draft; do not merge. Not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents **v0.6.0**, `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; [Draft PR #1](https://github.com/bugu-robot/TradingAgents/pull/1), open, Draft, unmerged.
- Latest published checkpoint before this phase: `1eeda4467fb609218821e06c3d4f547b0fd1fc4b`.
  Resolve the current tip with `git rev-parse origin/feat/subscription-providers`.
- Fetched origin/upstream and confirmed clean starting state, existing PR and
  v0.6.0 baseline; no work discarded and no main/upstream mutation.
- Current official Google headless/install/credits/models/permissions/agent
  documentation rechecked. Reviewed native Linux `agy` version remains **1.2.17**.
- Corrected unconditional authentication blocker: real safe configuration and
  binary admission permits documented cached-account execution. CLI owns secure
  credentials/refresh; actual auth failures remain terminal. No token reading,
  invented Pro-attestation API or speculative account prompt.
- Catalog preflight is separate from inference. Public `agy models` discovery
  requests no model turn. Safe syntax plus fresh catalog membership admits
  Gemini, Claude and other returned families; unknown/custom IDs fail closed.
- Stream input now follows official stdin-first behavior. Init must validate
  isolated cwd, exact model/agent/schema, strict/request-review mode and empty tools
  before accepting terminal SUCCESS/exit 0. Action metadata remains rejected.
- API/provider/Vertex/ADC/custom routing, credits overage, policy/customizations
  and child environment isolation remain enforced. No global settings changed.
- Independent subscription model menus now use each tier's account catalog;
  no custom API model choice is offered. A Quick env model cannot suppress Deep
  selection. Low/medium/high effort is centralized, passed to CLI and saved in
  run settings. Status/catalog commands explicitly avoid entitlement claims.
- Headless's documented request-review init is accepted only alongside required
  strict real settings, universal deny rules and empty tools; unsafe/unknown
  permission modes remain rejected.
- Targeted correction/CLI tests: **320 passed**, whole-repository Ruff and
  `git diff --check` passed. Previous first-phase Antigravity/routing count: 254.
- Full correction regression: **1,665 passed, 7 integration deselected,
  20 upstream warnings, 100 subtests passed**. Dedicated subscription offline
  suite: **402 passed**. Clean v0.6.0 baseline: **1,263 passed,
  1 integration deselected, same 20 warnings, 99 subtests passed**. No failures.
- Explicit subscription LIVE default-guard run: **6 skipped, 0 executed**;
  skipped tests are not successful live checks.
- Focused review B1–B7 corrected; no open P1/P2 code finding. Existing OpenAI
  authentication/tool/SSE/schema behavior and all ordinary API providers retained.
- Whole-repository Ruff, diff-check, compile/package/CLI imports and dependency
  check plus fresh non-dev installed runtime/CLI import passed. Ubuntu
  instructions statically checked: 8 Bash + 1 JSON blocks,
  6 Python heredocs; no login/model command executed during those checks.
- SSH account-TUI helper corrected to unbuffered terminal I/O and checked with
  a local PTY child. A controlling SSH terminal is required; this Work runtime
  has no accessible controlling `/dev/tty`, so this is not live sign-in evidence.
- VERIFICATION.md now provides one complete Ubuntu session: pinned official CLI,
  OpenAI local OAuth/VM transfer, sanitized interactive Google SSH sign-in,
  independent model/effort selection, six opt-in smokes, official /usage evidence
  after requests and full all-node AAPL Markdown/HTML/settings acceptance.
- Six subscription LIVE cases remain opt-in; **0 executed**. All login,
  entitlement, native real-CLI scoping/schema, quota/billing and full AAPL
  Markdown/HTML acceptance checks remain **LIVE PENDING**.

| Provider | Quick | Deep | Native TradingAgents tools | Native schema | Status |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | Yes | Yes | Yes | Yes | Existing offline implementation retained |
| `antigravity_cli` | No | Yes | No | Offline schema + validation | Cached-account transport admitted; live pending |
| Existing API providers | Existing behavior | Existing behavior | Existing behavior | Existing behavior | Retained |

No separate machine-readable Pro endpoint is required for documented cached
execution. Catalog presence/local preflight is not plan entitlement evidence.
Final acceptance must record selected ChatGPT model, selected Antigravity model
and effort, successful headless/schema requests, official interactive `/usage`
plan/quota after requests, no billed routing and `useG1Credits=false`.

Read [DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md),
[VERIFICATION.md](VERIFICATION.md) and [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md)
before continuing another session.

Next action: perform the single consolidated live session in VERIFICATION.md,
record tested SHA/models/effort and official Google AI Pro account/quota evidence,
then publish acceptance results. Local preflight cannot distinguish plan tiers
or prove cached login; catalog models may be unavailable to the selected plan.
Actual CLI zero-tool scoping and native schema remain to be demonstrated live.
No unconditional admission/catalog blocker or missing-attestation requirement
remains. Do not call this production-ready or merge Draft PR #1 before acceptance.
