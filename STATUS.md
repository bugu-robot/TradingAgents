# Subscription provider status

Updated: 2026-10-06. **Draft; do not merge. Not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents **v0.6.0**, `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; [Draft PR #1](https://github.com/bugu-robot/TradingAgents/pull/1), unmerged.
- Latest published checkpoint before this update: `1391c605d2b76cbf66cbe804f443ac4128dcc466`.
  Resolve the current tip with `git rev-parse origin/feat/subscription-providers`.
- Phase 0: fetched both remotes, confirmed clean worktree and baseline; no work discarded.
- Phase 1: official documentation rechecked; official Linux `agy` **1.2.17**
  downloaded, release SHA-512 verified, real `--version`/`--help` inspected.
- Antigravity foundation: real-settings preflight, API/custom endpoint/policy
  rejection, OS/keyring environment allowlist, verified CLI detection, strict JSON
  parsing and safe error classification implemented.
- Antigravity transport/schema: isolated scoped agent, NDJSON parser, native
  schema plus independent JSON Schema/Pydantic validation, early action rejection,
  bounded subprocess timeout/cancellation and terminal failure handling implemented.
  **175 Antigravity offline cases pass**, including real fake-executable process
  lifecycle tests; these are not live CLI/account verification.
- Registry/model catalog/CLI/auth/examples now use `antigravity_cli`, with
  centralized deep-only admission and effort configuration. Gemini CLI adapter
  and subscription tests removed; existing `google` API client preserved.
- Final focused review passed **342 subscription offline tests**, including
  Antigravity, ChatGPT auth/transport/tools and centralized routing.
  Six opt-in LIVE cases replace the previous four; all remain skipped by default.
- Focused review A1–A8 corrected: process/probe cleanup, no external schema
  resolution, strict JSON, storage/lock ownership, terminal schema failures,
  safe exit classification and action metadata. No open P1/P2 code finding.
- Full fork regression: **1,605 passed, 7 integration deselected, 20 upstream
  warnings, 101 subtests passed**. Clean v0.6.0 baseline: **1,263 passed,
  1 integration deselected, the same 20 warnings, 99 subtests passed**.
- Research/Portfolio Manager schema integration, terminal failures and real
  mocked Market Analyst ToolNode loop passed. Ruff, diff-check, compile/import
  and clean installed runtime/CLI import passed. No extra type checker in CI.
- Final consolidated verification command documentation and PR update pending.

| Provider | Quick | Deep | Native TradingAgents tools | Native schema | Status |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | Yes | Yes | Yes | Yes | Existing offline implementation retained |
| `antigravity_cli` | No | Prepared | No | Offline native schema + validation | Activation blocked by official interface |
| Existing API providers | Existing behavior | Existing behavior | Existing behavior | Existing behavior | Retained |

All subscription live checks and the complete AAPL run remain **LIVE PENDING**.
Offline tests cannot prove Plus/Pro entitlement, quota, identity or actual billing.
Next: finish the consolidated verification commands and update Draft PR #1.
**Activation blocker**: reviewed 1.2.17 docs provide no supported non-inference
headless personal Pro account preflight; `/help` is TUI-only documentation. The
adapter always refuses inference at authentication. No speculative model probe,
token inspection, local attestation or bypass is provided. Login cannot unlock
it. Implement/review a future supported official preflight first, then verify
init-before-input ordering and the complete live session. Do not ask the user to
perform login-only tests against this blocked checkpoint.

Read [DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md),
[VERIFICATION.md](VERIFICATION.md) and [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md)
before continuing another session.
