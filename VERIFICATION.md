# Subscription verification and acceptance

**OFFLINE VERIFIED and LIVE VERIFIED are separate states.** No live subscription
request has been verified. Draft PR #1 must not be merged. This file is the
single source of truth for the final consolidated Ubuntu session.

## Offline checks

The migration must pass unit, upstream regression, routing, auth/config preflight,
environment isolation, error classification, secret handling, process cleanup,
native schema and action-rejection tests. Preserve the real Market Analyst
stock-data → ToolMessage → indicator → ToolMessage → report graph regression.

Run from the checkout after installing `.[dev,bedrock]`:

```bash
AWS_ACCESS_KEY_ID=offline-placeholder AWS_SECRET_ACCESS_KEY=offline-placeholder \
AWS_EC2_METADATA_DISABLED=true python -m pytest
python -m pytest tests/test_chatgpt_plan*.py tests/test_antigravity_cli.py tests/test_subscription_routing.py
python -m pytest tests/test_subscription_live.py -o addopts='' -m integration -q
ruff check .
git diff --check
```

The dummy AWS variables prevent EC2 credential lookup in optional offline client
construction tests. They do not invoke AWS. Normal regression excludes integration
tests; the explicit integration command must report skipped live checks unless
`RUN_SUBSCRIPTION_LIVE=1` is intentionally set. Never add skips to passed counts.

Final migration evidence (2026-10-06, Python 3.12.14): clean baseline 1,263
passed/1 integration deselected; fork 1,605 passed/7 integration deselected;
342 subscription offline cases. Both full suites have the same 20 upstream
warnings. Six subscription live cases explicitly skipped, zero executed.
Ruff, diff-check, compile/package/CLI import and fresh runtime installation pass.

Antigravity activation is blocked by the lack of a reviewed official non-inference
headless Pro account preflight. Login cannot unlock the current adapter. No live
session should start until that supported interface is implemented and reviewed.

## Live acceptance checklist — all pending

- ChatGPT Plus SIWC sign-in and account model catalog.
- ChatGPT multi-message conversation, native schema and sequential native tools.
- Antigravity remote Google AI Pro sign-in; CLI owns all Google credentials.
- Antigravity headless text, native schema, subscription-only configuration and
  no API/Vertex/ADC/custom endpoint/credit overage. Optional dummy-variable check.
- AAPL full graph: market, sentiment (`social` CLI token), news, fundamentals,
  bull/bear researchers, Research Manager, trader, aggressive/neutral/conservative
  risk analysts and Portfolio Manager; final decision plus saved Markdown/HTML
  reports and settings proving ChatGPT quick / Antigravity deep.

Exact pinned-install/auth/import/test/run commands will be completed after the
actual CLI safety contract and offline review are verified. Do not perform
partial live checks during development.
