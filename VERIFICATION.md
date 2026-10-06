# Subscription verification and acceptance

Updated **2026-10-06 UTC**. **OFFLINE VERIFIED is not LIVE VERIFIED.** Draft PR #1
remains unmerged. No subscription inference, user OAuth login or complete AAPL
run has been live verified.

**Current admission:** safe real settings, the reviewed binary, sanitized child
environment and an isolated zero-tool agent admit official cached-account
execution. Authentication is checked by the CLI during the actual request; no
separate Pro-attestation endpoint or secure-token reading is required. Input
follows the documented stdin-first protocol; init must validate before accepting
terminal SUCCESS. Catalog discovery executes only `agy models`, never inference.
Local readiness/catalog is not plan entitlement proof. The remaining acceptance
checks are actual CLI scoping/init/schema compatibility, Plus/Pro entitlement,
official interactive `/usage` quota after smokes and the full AAPL run.

## Offline results

Python **3.12.14**, UTC, optional Bedrock installed. No AWS/provider service used.

| Check | Actual result |
| --- | --- |
| Clean upstream v0.6.0/tag `1394a3f72aa4393e1a98f51b382434c4b4c2d972`, detached test worktree | **1,263 passed**, 1 upstream integration deselected, 99 subtests passed |
| Full feature branch suite | **1,665 passed**, 7 integration deselected, 100 subtests passed |
| Subscription offline modules | **402 cases** passed in both the full suite and dedicated run |
| Explicit subscription LIVE collection, default guards | **6 skipped**, 0 executed |
| Warnings | The same **20 upstream unknown-model RuntimeWarnings** in both full suites; not suppressed |
| Ruff across repository / `git diff --check` | Passed / passed |
| Compile/package and CLI imports, fresh non-dev install/import | Passed |
| CI type/static requirements | CI has pytest, full Ruff and clean-install import; no additional type checker configured |

Subtests are reported separately, not added to pytest's main passed total. The
seven deselections are six subscription tests plus the existing DeepSeek live
test. Skips/deselections are never counted as successful live checks. Other
Python versions and the remote GitHub CI matrix are not claimed locally verified.

```bash
python -m pip install -e '.[dev,bedrock]'
AWS_ACCESS_KEY_ID=offline-placeholder AWS_SECRET_ACCESS_KEY=offline-placeholder \
AWS_EC2_METADATA_DISABLED=true python -m pytest -q
python -m pytest tests/test_chatgpt_plan_auth.py tests/test_chatgpt_plan.py \
  tests/test_chatgpt_plan_tools.py tests/test_antigravity_cli.py \
  tests/test_subscription_routing.py -q
python -m pytest tests/test_subscription_live.py -o addopts='' -m integration -q
ruff check .
git diff --check
python -m compileall -q tradingagents cli
python -c 'import tradingagents, cli.main; print("package/CLI import OK")'
```

Dummy AWS variables prevent EC2 credential discovery in optional construction
tests. Normal pytest forbids service sockets and excludes integration tests.

| Coverage | Offline evidence |
| --- | --- |
| CLI discovery/version/public headless flags | `test_antigravity_cli.py`: missing executable, unverified version, each required flag; actual official Linux version/help also inspected |
| Subscription admission/API/Vertex/custom endpoint/policy | Real settings parsed read-only; conflicting config fails before child startup. Cached-account requests proceed without invented attestation; documented CLI auth errors remain terminal |
| Catalog/models/effort | Official non-inference `agy models` only; Gemini/Claude/other safe catalog families, unknown/custom rejection, independent tier menus/env models and low/medium/high effort with saved settings |
| Environment isolation | All requested Gemini/Google/Vertex/project/ADC variables plus gateway, enterprise, custom-agent, proxy and future routing switches excluded; parent environment unchanged |
| JSON/stream/schema/malformed/no output | Strict UTF-8, duplicate/nonfinite/depth rejection; init/identity/terminal order; native schema, independent Draft 2020-12 plus strict Pydantic; no remote resolution/fallback |
| Timeout/cancellation/cleanup | Real fake-executable pipes, group descendants, bounded probe/output, closed-pipe cancellation, reaping and private workspace deletion |
| Quota/rate/auth/entitlement/redaction | Safe classification; terminal failures never retry as plain calls; bounded rate/service retries; opaque raw diagnostics discarded |
| Files/commands/MCP/plugins/skills/subagents | All deny namespaces and empty agent lists checked before startup; init mismatch prevents accepting any response; strict real settings plus strict/request-review init; action metadata terminates/rejects; no unsafe permission switch |
| Tier admission/graph integration | Antigravity quick rejected before auth, deep constructed, ChatGPT quick/Antigravity deep routed; Research and Portfolio Manager native schema, terminal errors; saved run settings |
| ChatGPT native analyst tools | Real Market Analyst + LangGraph ToolNode: stock data → ToolMessage → indicator → ToolMessage → report; sequential/parallel calls and duplicate-ID prevention |
| OAuth/security review | State/nonce/PKCE, OIDC signature/issuer/audience/expiry/subject, loopback bounds, locked refresh, no-follow owner-only storage, redaction and terminal UTF-8 SSE |

All details and corrected A/B findings are in
[subscription-code-review.md](docs/subscription-code-review.md). Mocked account
responses and real fake-executable lifecycle tests verify control flow only;
complete admission/catalog/stdin-first tests do not bypass the actual code gate,
but also do not prove real cached credentials, entitlement or effective sandboxing.

## Live checks — all pending

| LIVE test | Acceptance |
| --- | --- |
| 1 | ChatGPT Plus multi-message conversation |
| 2 | ChatGPT Plan native JSON Schema/Pydantic output |
| 3 | Two sequential TradingAgents-controlled tool rounds and ToolMessage continuation |
| 4 | Antigravity Google AI Pro cached sign-in/headless text, no autonomous tools |
| 5 | Antigravity native JSON Schema and validated response |
| 6 (optional) | Dummy API/Vertex/gateway variables cannot switch provider or cause API requests |

Also require account catalogs, actual Pro/Plus quota/credit inspection and one
complete AAPL graph with all four analysts, bull/bear researchers, Research
Manager, trader, aggressive/neutral/conservative risk analysts and Portfolio
Manager. Save Markdown/HTML and settings recording the exact provider pair,
independently selected models and Antigravity effort. Test 6
cannot independently prove billing: inspect official account usage as well.

## One consolidated Ubuntu/SSH session — final acceptance pending

Use Ubuntu amd64, Python 3.12, a dedicated personal account environment and an
accessible Linux Secret Service/D-Bus keyring. Existing admin policy is never
bypassed. Run inside an interactive SSH terminal with a controlling TTY (use
`ssh -t ubuntu@your-vm-host` if needed), so the helper can open `/dev/tty`.
If keyring access is unavailable, follow the
[official troubleshooting](https://www.antigravity.google/docs/cli/troubleshooting/);
do not export/copy secure Google tokens. These steps use one verification session
with a local OAuth/browser companion, not separate repeated user tests.

### 1. Checkout and dependencies, then preserve the VM host ID

```bash
set -euo pipefail
umask 077
export TA_VERIFY_CHECKOUT="$HOME/TradingAgents-subscription-verification"
if [ ! -d "$TA_VERIFY_CHECKOUT/.git" ]; then
  git clone --branch feat/subscription-providers --single-branch \
    https://github.com/bugu-robot/TradingAgents.git "$TA_VERIFY_CHECKOUT"
fi
cd "$TA_VERIFY_CHECKOUT"
test -z "$(git status --porcelain)"
git fetch origin
git switch feat/subscription-providers
git pull --ff-only origin feat/subscription-providers
git rev-parse HEAD
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,bedrock]'
export LANGSMITH_TRACING=false LANGCHAIN_TRACING_V2=false
export TRADINGAGENTS_CHATGPT_PROFILE=plus
python - <<'PY'
from tradingagents.llm_clients.chatgpt_plan_auth import ChatGPTAuthStore
print("VM host ID:", ChatGPTAuthStore(profile="plus").host_id())
PY
```

### 2. Pinned official Antigravity installation

Do not assume the website's installer skip flags exist: the inspected installer
differs. Download the same official manifest release, verify SHA-512, extract
only its native executable, and install without modifying shell profiles:

```bash
test "$(uname -s)" = Linux
test "$(uname -m)" = x86_64
AGY_VERIFY_PACKAGE="$(mktemp -d)"
curl --fail --silent --show-error --location \
  https://storage.googleapis.com/antigravity-public/antigravity-cli/1.2.17-6683332533157888/linux-x64/cli_linux_x64.tar.gz \
  --output "$AGY_VERIFY_PACKAGE/agy.tar.gz"
python - "$AGY_VERIFY_PACKAGE/agy.tar.gz" <<'PY'
import hashlib, pathlib, sys
expected = "d0ebe612f7cfc21c8de9e7a7a62964b2245d89ddb570d5e27e83e61a2cc76cb38e80b6eb3bdd71bef683eba027c4a97dcce4ced81f47f827763234d0cd3ec592"
assert hashlib.sha512(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest() == expected
PY
tar -xzf "$AGY_VERIFY_PACKAGE/agy.tar.gz" -C "$AGY_VERIFY_PACKAGE" antigravity
mkdir -p "$HOME/.local/bin"
install -m 755 "$AGY_VERIFY_PACKAGE/antigravity" "$HOME/.local/bin/agy"
rm -rf -- "$AGY_VERIFY_PACKAGE"
unset AGY_VERIFY_PACKAGE
export PATH="$HOME/.local/bin:$PATH"
export AGY_CLI_DISABLE_AUTO_UPDATE=true
export TRADINGAGENTS_ANTIGRAVITY_CLI_BIN="$HOME/.local/bin/agy"
test "$(agy --version)" = 1.2.17
agy --help
```

### 3. Official OpenAI self-hosted flow: local OAuth and protected profile transfer

[OpenAI self-hosted VMs](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms)
requires a distinct VM host ID, local OAuth with the same tool/user/workspace,
secure transfer of the selected registration and VM-owned subsequent refreshes.
On your **local computer**, in this same fork/branch with its environment installed:

```bash
source .venv/bin/activate
tradingagents auth login chatgpt_plan --profile plus
tradingagents auth use plus
tradingagents auth status chatgpt_plan
tradingagents auth models chatgpt_plan
# Set your actual SSH destination; never paste credential contents into chat.
VM_VERIFY_TARGET='ubuntu@your-vm-host'
scp "$HOME/.config/tradingagents/chatgpt_plan/plus.json" \
  "$VM_VERIFY_TARGET:.config/tradingagents/chatgpt_plan/plus.json"
```

Transfer **only plus.json**, not host.json/host.lock/active.json or another app's
credential cache. On Ubuntu, continue in the original activated shell:

```bash
chmod 600 "$HOME/.config/tradingagents/chatgpt_plan/plus.json"
tradingagents auth use plus
tradingagents auth status chatgpt_plan
tradingagents auth models chatgpt_plan
read -r -p 'ChatGPT catalog slug: ' CHATGPT_PLAN_LIVE_MODEL
export CHATGPT_PLAN_LIVE_MODEL CHATGPT_PLAN_LIVE_PROFILE=plus
```

Let the VM own later refreshes; stop using the transferred connection locally
to avoid rotation races. If plan consent was omitted, repeat local login with
`--enable-plan-usage` before transfer. Review connected-app allowance/credits.

**Optional deployment alternative**, not OpenAI's official primary procedure:
keep `ssh -L 1455:127.0.0.1:1455 ubuntu@your-vm-host` open locally, run
`tradingagents auth login chatgpt_plan --profile plus --no-browser --port 1455`
on the VM and open the emitted URL locally. Choose one method; do not sign in
twice or copy browser/Codex credentials.

### 4. Review real Google settings, then use official remote sign-in

Manually review/create `~/.gemini/antigravity-cli/settings.json` in this dedicated
account. Do not overwrite unrelated settings, delete admin policy or move global
customizations to hide them. If they conflict, stop or use a separately authorized
dedicated OS account. Required settings (no modelProvider/API/custom endpoints):

```json
{
  "useG1Credits": false,
  "toolPermission": "strict",
  "allowNonWorkspaceAccess": false,
  "enableTerminalSandbox": true,
  "permissions": {
    "allow": [],
    "ask": [],
    "deny": ["read_file(*)", "write_file(*)", "read_url(*)", "execute_url(*)",
             "command(*)", "unsandboxed(*)", "mcp(*)"]
  }
}
```

Edit these yourself; TradingAgents never rewrites them. Keep the file owner-only
and its real parent directories owned by you and not group/world writable.
Before launching the interactive CLI, validate configuration without model use:

```bash
python - <<'PY'
from tradingagents.llm_clients.antigravity_cli_client import _configuration_preflight
_configuration_preflight()
print("Actual subscription-only settings passed; Google sign-in still separate.")
PY
# This helper launches the official TUI, retaining only OS/keyring/SSH variables.
# Unbuffered /dev/tty keeps login interactive despite the Python heredoc;
# terminals are not seekable. No tokens are read.
agy_verified_account_ui() {
python - <<'PY'
import os, subprocess, tempfile
from tradingagents.llm_clients.antigravity_cli_client import catalog_preflight, _child_environment
executable, _ = catalog_preflight()
env = _child_environment()
env.pop("CI", None)
env.pop("NO_BROWSER", None)
for key in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY"):
    if key in os.environ:
        env[key] = os.environ[key]
with tempfile.TemporaryDirectory(prefix="tradingagents-agy-account-") as cwd, open("/dev/tty", "r+b", buffering=0) as terminal:
    subprocess.run([executable], cwd=cwd, env=env, stdin=terminal,
                   stdout=terminal, stderr=terminal, check=True)
PY
}
agy_verified_account_ui
# Complete the CLI's URL -> local browser -> authorization code -> SSH prompt flow.
# Use the personal Google AI Pro account. Inspect account/plan, /usage, /credits
# and /config (Use G1 Credits off), then /exit. Do not submit a model prompt here.
```

This is the exact remote URL/code procedure in
[official installation/auth](https://www.antigravity.google/docs/cli/install/).
No Google tokens are transferred. The helper preserves SSH detection without
inheriting API/Vertex/gateway/custom routing. Both catalogs may change over time;
Antigravity is not restricted to Gemini names. Catalog presence is not Pro proof.

### 5. Mandatory admission/status gate, then all live smokes

Status checks readiness only. All catalog discovery below is non-inference.
Select each model independently from its own catalog; no fixed GPT/Antigravity
model is forced. Unknown, unavailable or mismatched models fail without fallback.

```bash
tradingagents auth status chatgpt_plan
tradingagents auth status antigravity_cli
tradingagents auth models antigravity_cli
read -r -p 'Antigravity catalog slug (any listed safe family): ' ANTIGRAVITY_LIVE_MODEL
read -r -p 'Antigravity effort (low/medium/high): ' ANTIGRAVITY_LIVE_EFFORT
case "$ANTIGRAVITY_LIVE_EFFORT" in low|medium|high) ;; *) exit 1 ;; esac
export ANTIGRAVITY_LIVE_MODEL ANTIGRAVITY_LIVE_EFFORT
export ANTIGRAVITY_LIVE_BIN="$HOME/.local/bin/agy"
export TRADINGAGENTS_LLM_PROVIDER=chatgpt_plan
export TRADINGAGENTS_QUICK_THINK_PROVIDER=chatgpt_plan
export TRADINGAGENTS_QUICK_THINK_LLM="$CHATGPT_PLAN_LIVE_MODEL"
export TRADINGAGENTS_DEEP_THINK_PROVIDER=antigravity_cli
export TRADINGAGENTS_DEEP_THINK_LLM="$ANTIGRAVITY_LIVE_MODEL"
export TRADINGAGENTS_ANTIGRAVITY_EFFORT="$ANTIGRAVITY_LIVE_EFFORT"
mkdir -p results
export TA_VERIFY_EVIDENCE_DIR="$(mktemp -d "$TA_VERIFY_CHECKOUT/results/subscription-acceptance.XXXXXXXX")"
python - <<'PY'
import json, os, subprocess
from pathlib import Path
from tradingagents.llm_clients.antigravity_cli_client import _configuration_preflight, VERIFIED_VERSION
from tradingagents.llm_clients.subscription_registry import subscription_model_options
quick, deep, effort = (os.environ[key] for key in
                       ("CHATGPT_PLAN_LIVE_MODEL", "ANTIGRAVITY_LIVE_MODEL", "ANTIGRAVITY_LIVE_EFFORT"))
for provider, model in (("chatgpt_plan", quick), ("antigravity_cli", deep)):
    assert model in {slug for _, slug in subscription_model_options(provider)}, "Choose a current listed model"
settings = _configuration_preflight()  # Checks no API/Vertex/custom routing or policy bypass.
assert settings["useG1Credits"] is False and "modelProvider" not in settings
evidence = {"tested_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "quick_think_provider": "chatgpt_plan", "quick_think_llm": quick,
            "deep_think_provider": "antigravity_cli", "deep_think_llm": deep,
            "antigravity_effort": effort, "cli_version": VERIFIED_VERSION,
            "useG1Credits": False, "billed_routing_preflight": "passed",
            "live_entitlement": "PENDING official /usage and live requests"}
Path(os.environ["TA_VERIFY_EVIDENCE_DIR"], "selected-settings.json").write_text(json.dumps(evidence, indent=2))
print(json.dumps(evidence, indent=2))  # Safe selection data only, no credentials.
PY
RUN_SUBSCRIPTION_LIVE=1 RUN_SUBSCRIPTION_ISOLATION_LIVE=1 \
  python -m pytest tests/test_subscription_live.py -o addopts='' -m integration -v --tb=short \
  --junitxml="$TA_VERIFY_EVIDENCE_DIR/live-smokes.xml"
# Mandatory quota/account evidence AFTER the headless and native schema requests:
agy_verified_account_ui
# In the official TUI use /usage (alias /quota), inspect authenticated personal
# Google AI Pro plan/account plus selected model-family quotas and /config credits
# off, then /exit. Record that panel evidence privately alongside selected-settings.json.
# Do not send /usage as a model prompt, parse model-authored identity or read tokens.
tradingagents auth status antigravity_cli
```

With both opt-ins, require **6 actually executed/passed**, zero unexpected skips.
To omit optional test 6, omit its flag and record **5 passed, 1 skipped** explicitly.
Live model/profile variables deliberately do not use the TRADINGAGENTS prefix:
the upstream offline fixture blanks that prefix. Review official quota/credits
before and after; record entitlement/account/billing evidence privately without
tokens or authorization codes. The [official /usage panel](https://www.antigravity.google/docs/cli/commands/usage)
refreshes model quotas; confirm the signed-in Google AI Pro account/plan in the
official UI as well. Record chosen ChatGPT model, chosen Antigravity model,
effort, headless/schema successes, no API/Vertex/custom provider settings and
`useG1Credits=false`. Dummy-key success or catalog presence alone proves neither
plan entitlement nor actual billing. If any live check fails, stop the full run.

### 6. Full AAPL graph and saved Markdown/HTML/settings acceptance

After all preceding gates pass, run this once in the same shell. It uses the
existing graph, all analysts and report writer; no hybrid routing or autonomous
CLI tools. A fresh run directory prevents stale checkpoints from proving success.

```bash
export VERIFY_TRADE_DATE="$(date -u +%F)"
python - <<'PY'
import json, os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.subscription_registry import preflight_subscription, subscription_model_options

# Recheck safe setup and current catalog membership before spending model allowance.
preflight_subscription("antigravity_cli")
preflight_subscription("chatgpt_plan")
for provider, variable in (("chatgpt_plan", "CHATGPT_PLAN_LIVE_MODEL"), ("antigravity_cli", "ANTIGRAVITY_LIVE_MODEL")):
    assert os.environ[variable] in {slug for _, slug in subscription_model_options(provider)}
assert os.environ["ANTIGRAVITY_LIVE_EFFORT"] in {"low", "medium", "high"}

output = Path("results/subscription-live") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
output.mkdir(parents=True, mode=0o700)
config = deepcopy(DEFAULT_CONFIG)
config.update({
    "llm_provider": "chatgpt_plan", "quick_think_provider": "chatgpt_plan",
    "quick_think_llm": os.environ["CHATGPT_PLAN_LIVE_MODEL"],
    "deep_think_provider": "antigravity_cli", "deep_think_llm": os.environ["ANTIGRAVITY_LIVE_MODEL"],
    "backend_url": None, "quick_think_backend_url": None, "deep_think_backend_url": None,
    "temperature": None, "max_tokens": None, "llm_max_retries": 1,
    "antigravity_effort": os.environ["ANTIGRAVITY_LIVE_EFFORT"],
    "max_debate_rounds": 1, "max_risk_discuss_rounds": 1, "checkpoint_enabled": True,
    "results_dir": str(output), "data_cache_dir": str(output / "cache"),
    "memory_log_path": str(output / "memory.md"),
})
graph = TradingAgentsGraph(selected_analysts=["market", "social", "news", "fundamentals"], config=config)
state, signal = graph.propagate("AAPL", os.environ["VERIFY_TRADE_DATE"])
for key in ("market_report", "sentiment_report", "news_report", "fundamentals_report",
            "investment_plan", "trader_investment_plan", "final_trade_decision"):
    assert state.get(key), f"Missing completed node output: {key}"
for key in ("bull_history", "bear_history"):
    assert state["investment_debate_state"].get(key), key
for key in ("aggressive_history", "neutral_history", "conservative_history"):
    assert state["risk_debate_state"].get(key), key
assert state.get("final_rating") in {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
assert signal == state["final_rating"]
settings = graph.run_settings()
assert settings["quick_think_provider"] == "chatgpt_plan"
assert settings["deep_think_provider"] == "antigravity_cli"
assert settings["quick_think_llm"] == os.environ["CHATGPT_PLAN_LIVE_MODEL"]
assert settings["deep_think_llm"] == os.environ["ANTIGRAVITY_LIVE_MODEL"]
assert settings["antigravity_effort"] == os.environ["ANTIGRAVITY_LIVE_EFFORT"]
assert set(settings["analysts"]) == {"market", "social", "news", "fundamentals"}
report = graph.save_reports(state, "AAPL", save_path=output / "report", html=True)
assert report.is_file() and report.with_suffix(".html").is_file()
(output / "verification.json").write_text(json.dumps({
    "trade_date": os.environ["VERIFY_TRADE_DATE"], "final_rating": state["final_rating"],
    "signal": signal, "run_settings": settings, "markdown": str(report),
    "html": str(report.with_suffix(".html")),
    "smoke_quota_evidence": os.environ["TA_VERIFY_EVIDENCE_DIR"],
}, indent=2), encoding="utf-8")
print("Final rating:", state["final_rating"])
print("Saved report:", report)
print("HTML report:", report.with_suffix(".html"))
print("Acceptance settings:", output / "verification.json")
PY
agy_verified_account_ui
# Inspect /usage again after the full AAPL run and save private quota evidence.
# Exit with /exit; do not send any additional model request.
```

Review all saved sections and actual usage, not just process exit. Only mark
**LIVE VERIFIED** after all mandatory smokes and the full graph/report acceptance
pass. Update STATUS.md/this file with date, tested SHA, exact CLI version, passed
and skipped counts plus any failures, then commit/push. Keep PR #1 Draft and
unmerged until a separate user instruction authorizes anything further.
