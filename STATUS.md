# Subscription provider status

Updated: 2026-10-06. **Draft; do not merge. Not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents **v0.6.0**, `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; [Draft PR #1](https://github.com/bugu-robot/TradingAgents/pull/1), unmerged.
- Latest published checkpoint before this update: `ed7a3f9687c08e70a8c0f1d53c8fffe328cc8490`.
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
- Focused review fixes passed **346 subscription offline tests**, including
  Antigravity, ChatGPT auth/transport/tools and centralized routing.
  Six opt-in LIVE cases replace the previous four; all remain skipped by default.
- Focused review A1–A7 corrected: process/probe cleanup, no external schema
  resolution, strict JSON, storage/lock ownership, terminal schema failures,
  safe exit classification and action metadata. No open P1/P2 code finding.
- Full final regression, additional deep-manager coverage and final verification
  command documentation pending.
- Last completed regression before migration: 1,440 passed, 5 integration tests
  deselected, 20 existing warnings; 177 subscription offline tests. These counts
  apply to the old checkpoint, not the pending Antigravity implementation.

| Provider | Quick | Deep | Native TradingAgents tools | Native schema | Status |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | Yes | Yes | Yes | Yes | Existing offline implementation retained |
| `antigravity_cli` | No | Yes | No | Native schema + independent validation | Registered; safety gates live-pending |
| Existing API providers | Existing behavior | Existing behavior | Existing behavior | Existing behavior | Retained |

All subscription live checks and the complete AAPL run remain **LIVE PENDING**.
Offline tests cannot prove Plus/Pro entitlement, quota, identity or actual billing.
Next: full regressions and focused review, finish the consolidated verification
commands and update Draft PR #1.
Known **live blockers**: official headless docs do not guarantee a machine-readable
Pro account field or init-before-input ordering. The adapter requires positive
personal Pro identification from CLI informational output and safe empty-tool init
before sending a prompt. If the actual CLI cannot provide either, it fails before
inference. Do not relax these gates based on mocked success or manual attestation.

Read [DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md),
[VERIFICATION.md](VERIFICATION.md) and [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md)
before continuing another session.
