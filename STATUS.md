# Subscription provider status

Updated: 2026-10-06. **Draft; do not merge. Not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents **v0.6.0**, `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; [Draft PR #1](https://github.com/bugu-robot/TradingAgents/pull/1), unmerged.
- Latest published checkpoint before this update: `10329285af613b74d9d0c68fd12184af708eaa91`.
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
- Registry/CLI/routing replacement and focused final review pending.
- Last completed regression before migration: 1,440 passed, 5 integration tests
  deselected, 20 existing warnings; 177 subscription offline tests. These counts
  apply to the old checkpoint, not the pending Antigravity implementation.

| Provider | Quick | Deep | Native TradingAgents tools | Native schema | Status |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | Yes | Yes | Yes | Yes | Existing offline implementation retained |
| `antigravity_cli` | No | Yes | No | Adapter implemented | Not yet registered; safety gates live-pending |
| Existing API providers | Existing behavior | Existing behavior | Existing behavior | Existing behavior | Retained |

All subscription live checks and the complete AAPL run remain **LIVE PENDING**.
Offline tests cannot prove Plus/Pro entitlement, quota, identity or actual billing.
Next: replace Gemini CLI registration/examples/tests, run regressions and focused
review, complete the consolidated verification commands and update Draft PR #1.
Known **live blockers**: official headless docs do not guarantee a machine-readable
Pro account field or init-before-input ordering. The adapter requires positive
personal Pro identification from CLI informational output and safe empty-tool init
before sending a prompt. If the actual CLI cannot provide either, it fails before
inference. Do not relax these gates based on mocked success or manual attestation.

Read [DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md),
[VERIFICATION.md](VERIFICATION.md) and [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md)
before continuing another session.
