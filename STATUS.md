# Subscription provider status

Updated: 2026-10-06. **Draft, do not merge, not production accepted.**

- Fork: `bugu-robot/TradingAgents`; upstream: `TauricResearch/TradingAgents`.
- Baseline: TradingAgents v0.6.0, upstream/fork-base SHA
  `1394a3f72aa4393e1a98f51b382434c4b4c2d972`.
- Branch: `feat/subscription-providers`; existing Draft PR #1 remains open and
  unmerged. This correction starts from reviewed HEAD
  `b1ed6f3929cca1ba52fb7c59f8663bdbd1894c26`.
- Published implementation/test checkpoint:
  `0c75c8600ccb1397e582a4383600e24310a6fd3e`; documentation/status checkpoint
  follows on this branch.
- Provider matrix: `chatgpt_plan` supports Quick and Deep, TradingAgents tools
  and native JSON Schema. `antigravity_cli` is Deep-only, reasoning-only, and
  uses Antigravity's native schema interface. Existing API providers remain.
- Independent model/effort selection is retained. ChatGPT models come from its
  signed-in account catalog; Antigravity uses the official global-flag command
  `agy --output-format json models`, with family-neutral safe slugs and fresh
  membership before inference. Catalog contents do not prove plan entitlement.
- `tradingagents auth status antigravity_cli` checks safe local configuration,
  verified CLI, then official print-mode `/usage` JSON. It requires a successful
  zero-turn response and reports local readiness separately from cached-account
  backend readiness. It never reads tokens or infers plan/quota fields absent
  from the official response.
- Reviewed adapter pin: official Antigravity CLI **1.2.17**. Newer stable
  **1.3.0** was observed/reported after the previous review but has not been
  adapter-reviewed; retain 1.2.17 through current live acceptance and handle
  1.3.0 in a separate compatibility task afterward.
- The former catalog blocker was caused by incorrect argument order. Official
  issue #777 confirms `--output-format` is global and the working invocation is
  `agy --output-format json models`. The parser now validates the complete
  zero-turn `SUCCESS`/`command.name=models` envelope. No model turn is consumed.
- `/config` and `/permissions` JSON are not used as automatic policy gates:
  release notes promise structured output, but stable field schemas are not
  documented. Existing local settings/policy checks remain authoritative.
- Offline tests after this correction: full repository **1,693 passed, 7
  integration deselected, 20 existing warnings, 100 subtests passed**; dedicated
  subscription suite **430 passed**; focused Antigravity suite **266 passed**.
  The 7 deselections include 6 opt-in subscription live cases and one existing
  live provider case. Explicit live collection: **6 skipped, 0 executed**.
- Ruff, `git diff --check`, compile/import and `uv pip check` (102 packages)
  passed. OAuth loopback regression was rerun with local-only loopback access;
  no external service or credentials were used.
- Focused security review completed: no open P1/P2 credential/isolation code
  finding. No API-key, Vertex, ADC, custom endpoint or G1-credit fallback is
  permitted.
- Next: run the consolidated LIVE acceptance with the reviewed 1.2.17 adapter,
  including ChatGPT login/conversation/schema/tools, Antigravity catalog,
  `/usage`, text/schema requests and full AAPL run. Keep 1.3.0 out of scope until
  a separate compatibility review. Do not merge.

Current mode/status:

| Quick Think | Deep Think | Status |
| --- | --- | --- |
| `chatgpt_plan` | `chatgpt_plan` | Offline implementation available; live pending |
| `chatgpt_plan` | `antigravity_cli` | Offline-tested; ready for the consolidated live acceptance |
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
unmerged until all live acceptance checks have passed.
