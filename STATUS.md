# Subscription provider status

Updated: 2026-10-06. **Draft, do not merge, not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents v0.6.0, upstream/fork-base SHA
  `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; existing Draft PR #1 remains open and
  unmerged. Correction started from reviewed SHA
  `9549c45a271f3a8629395b813cb7885c1373a1ec`.
- Published implementation/test checkpoint:
  `4a2569efcab5b492fe3f59cc5b0159443eec8e7a`; the final documentation checkpoint
  follows this code checkpoint on the same feature branch.
- Provider matrix: `chatgpt_plan` supports Quick and Deep, TradingAgents tools
  and native JSON Schema. `antigravity_cli` is Deep-only, reasoning-only, and
  uses Antigravity's native schema interface. Existing API providers remain.
- Independent model/effort selection is retained. ChatGPT models come from its
  signed-in account catalog; Antigravity must use its official `agy models
  --output-format json` catalog, with family-neutral safe slugs and fresh
  membership before inference. Catalog contents do not prove plan entitlement.
- `tradingagents auth status antigravity_cli` checks safe local configuration,
  verified CLI, then official print-mode `/usage` JSON. It requires a successful
  zero-turn response and reports local readiness separately from cached-account
  backend readiness. It never reads tokens or infers plan/quota fields absent
  from the official response.
- **Current CLI blocker:** downloaded, SHA-512-verified official Linux `agy`
  1.2.17 rejects `agy models --output-format json` with `flags provided but not
  defined: -output-format`; its `models --help` has no output-format flag.
  Official changelog advertises this option, but the official issue tracker
  reports the same mismatch. Code fails closed; human text parsing is disabled.
  Model selection and any Antigravity inference therefore remain blocked until
  an official compatible build and its actual JSON envelope can be verified.
- `/config` and `/permissions` JSON are not used as automatic policy gates:
  release notes promise structured output, but stable field schemas are not
  documented. Existing local settings/policy checks remain authoritative.
- Offline tests: full repository **1,678 passed, 7 integration deselected,
  20 existing warnings, 100 subtests passed**; dedicated subscription suite
  **415 passed**. The 7 deselections include 6 opt-in subscription live cases
  and one existing live provider case. Explicit live collection: **6 skipped,
  0 executed**.
- Ruff, `git diff --check`, compile/import and `uv pip check` (102 packages)
  passed. OAuth loopback regression was rerun with local-only loopback access;
  no external service or credentials were used.
- Focused security review completed: no open P1/P2 credential/isolation code
  finding. External P2 compatibility blocker remains: the verified 1.2.17 CLI
  rejects the documented JSON model-list flag. No API-key, Vertex, ADC, custom
  endpoint or G1-credit fallback is permitted.
- Next: wait for an official Antigravity CLI build whose documented
  `agy models --output-format json` command works and whose actual JSON envelope
  can be verified; then rerun catalog/inference tests, update the admission
  review, and prepare the single consolidated live acceptance. Do not merge.

Current mode/status:

| Quick Think | Deep Think | Status |
| --- | --- | --- |
| `chatgpt_plan` | `chatgpt_plan` | Offline implementation available; live pending |
| `chatgpt_plan` | `antigravity_cli` | Transport offline-tested; blocked by `agy models` JSON support mismatch |
| Existing API provider | Existing API provider | Existing upstream behavior retained |

Read [DESIGN.md](DESIGN.md), [DECISIONS.md](DECISIONS.md),
[VERIFICATION.md](VERIFICATION.md), [UPSTREAM_SYNC.md](UPSTREAM_SYNC.md),
[official-interface review](docs/antigravity-official-review.md) and
[code review](docs/subscription-code-review.md) before continuing this work.

Neither successful `/usage` reachability nor catalog presence proves Google AI
Pro entitlement or no-charge accounting. Live acceptance must record official
before/after `/usage` evidence, the exact tested SHA/models/effort, successful
text/schema requests, no API/Vertex/custom provider routing,
`useG1Credits=false`, and the full AAPL graph/report. Keep PR #1 Draft and
unmerged until a compatible official catalog interface and all live acceptance
checks have passed.
