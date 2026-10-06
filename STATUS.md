# Subscription provider status

Updated: 2026-10-06. **Draft; do not merge. Not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents **v0.6.0**, `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; [Draft PR #1](https://github.com/bugu-robot/TradingAgents/pull/1), unmerged.
- Latest published checkpoint before this update: `769f8c198612c792fc2b866bab601695906d5881`.
  Resolve the current tip with `git rev-parse origin/feat/subscription-providers`.
- Phase 0: fetched both remotes, confirmed clean worktree and baseline; no work discarded.
- Phase 1: official documentation rechecked; official Linux `agy` **1.2.17**
  downloaded, release SHA-512 verified, real `--version`/`--help` inspected.
- Migration implementation, replacement tests and focused review: in progress.
- Last completed regression before migration: 1,440 passed, 5 integration tests
  deselected, 20 existing warnings; 177 subscription offline tests. These counts
  apply to the old checkpoint, not the pending Antigravity implementation.

| Provider | Quick | Deep | Native TradingAgents tools | Native schema | Status |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | Yes | Yes | Yes | Yes | Existing offline implementation retained |
| `antigravity_cli` | No | Yes | No | Planned | Migration in progress |
| Existing API providers | Existing behavior | Existing behavior | Existing behavior | Existing behavior | Retained |

All subscription live checks and the complete AAPL run remain **LIVE PENDING**.
Offline tests cannot prove Plus/Pro entitlement, quota, identity or actual billing.
Next: implement fail-closed configuration/auth preflight and a tool-free native
headless/schema transport, remove the Gemini CLI subscription path, test and push.
Known checks to resolve: native custom-agent empty tool scoping; real settings
precedence/policy; cached CLI authentication without handling Google tokens.

Read [DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md),
[VERIFICATION.md](VERIFICATION.md) and [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md)
before continuing another session.
