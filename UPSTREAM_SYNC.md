# Stable upstream synchronization

Treat the subscription fork as a small extension to TradingAgents stable releases.
Do not blindly track upstream main. Current accepted code baseline is v0.6.0.

Recommended flow: inspect upstream stable tag → update fork main to a reviewed
stable baseline → `sync/<version>` integration branch → regression and provider
compatibility review → custom feature branch. Use PR review for every integration;
do not overwrite subscription code or merge the current Draft PR as a sync step.

Patch releases usually sync after regressions. Minor releases require review of
factory, configuration, model catalogs, CLI, graph/tool loops and structured
schemas. Major/breaking releases require a migration design and acceptance plan.
Record new baseline/version in STATUS.md and append decisions when contracts change.

Example future workflow (replace the example tag only after stable-release review):

```bash
git fetch origin
git fetch upstream --tags
git status --short
git show v0.6.1 --stat
git diff v0.6.0..v0.6.1 -- tradingagents/llm_clients tradingagents/default_config.py cli tradingagents/graph tradingagents/agents
git switch -c sync/v0.6.1 origin/main
git merge --no-ff v0.6.1
# Resolve conflicts, run the complete suite, and push the integration branch.
git push -u origin sync/v0.6.1
# Open a reviewed fork-only sync PR; update fork main only after separate approval.
# Once fork main is intentionally updated, integrate it into the custom branch:
git switch feat/subscription-providers
git merge origin/main
python -m pytest
ruff check .
git diff --check
git push origin feat/subscription-providers
```

These are future instructions, not actions authorized for this migration.
Never push to upstream. Never use hard reset/force push to replace custom work.
Review CLI protocol changes and subscription isolation independently of upstream
API regressions; live smoke acceptance is required when their contracts change.
