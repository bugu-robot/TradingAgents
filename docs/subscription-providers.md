# Subscription-backed providers

This fork extends TradingAgents **v0.6.0**, based on fork/upstream/tag commit
`1394a3f72aa4393e1a98f51b382434c4b4c2d972`. Work is on
`feat/subscription-providers`. It reuses `quick_think_provider` and
`deep_think_provider`; the graph and analyst routing are unchanged. Existing
OpenAI, Google and other API providers retain their API-key behavior.

## Supported capabilities

| Provider | Official authentication/transport | Quick tier | Deep tier | Native JSON schema | Native tools and ToolMessage continuation |
| --- | --- | --- | --- | --- | --- |
| `chatgpt_plan` | App-specific Sign in with ChatGPT OAuth; public `/v1/responses` | Yes | Yes | Yes | Yes, including sequential and parallel calls |
| `gemini_cli` | Official CLI 0.62.x cached personal Google sign-in; headless JSON | No | Yes | No; existing free-text fallback | No |

`chatgpt_plan` forwards complete text-message history, translates system
instructions to developer instructions, and preserves native function-call and
encrypted reasoning items between turns. Bound functions use the documented
Responses namespace `tradingagents`. Tool results become native
`function_call_output` items using their matching call IDs. Strict schemas use
required fields, including nullable fields used by the existing decision agents.
Pydantic schemas are validated locally after constrained generation.

Gemini CLI's JSON envelope contains plain text and statistics. It does not
provide a reliable native LangChain function-call/ToolMessage or constrained
JSON-schema interface. The adapter cannot serve the quick tier, whose analysts
need these capabilities. Deep research/portfolio managers use the existing
free-text fallback, with its existing parsing and validation limits.

| Quick provider | Deep provider | Result |
| --- | --- | --- |
| `chatgpt_plan` | `gemini_cli` | Supported; ChatGPT analysts/tools, Gemini text managers |
| `chatgpt_plan` | `chatgpt_plan` | Supported; native structured output in both tiers |
| An existing tool-capable API provider | `gemini_cli` | Supported; quick tier still has ordinary API billing |
| `gemini_cli` | `chatgpt_plan` | Rejected before authentication/inference |
| `gemini_cli` | `gemini_cli` | Rejected before authentication/inference |

Capabilities are declared once in `llm_clients/subscription_registry.py` and
checked at the factory and CLI boundary. There is no separate hybrid router.

## Allowance and billing

The ChatGPT adapter uses the official direct plan-use grant. An ordinary API
key or a Codex login alone is insufficient: TradingAgents registers its own
public client and obtains explicit consent to use the signed-in plan. Available
models are discovered from the authorized account's official catalog; model
slugs are not guessed or treated as proof of entitlement.

Plan allowance is shared with other eligible usage. Availability, limits and
any optional additional credits remain controlled by OpenAI and the account's
connected-app settings. Check those settings when authorizing plan usage. This
adapter does not use `OPENAI_API_KEY` or fall back to pay-per-token API billing.

Google AI Pro is not Gemini REST API credit. The CLI adapter forces personal
Google OAuth, removes API/Vertex/ADC billing overrides from its child process,
and sets the documented `billing.overageStrategy="never"` to disable AI-credit
overage. The signed-in Google account and CLI service determine eligibility and
quota. No Google REST API key is used. Neither provider silently changes
providers when quota is exhausted.

## Authentication

ChatGPT commands:

```bash
tradingagents auth login chatgpt_plan --profile plus
tradingagents auth status chatgpt_plan
tradingagents auth models chatgpt_plan
tradingagents auth accounts
tradingagents auth use plus
tradingagents auth logout --profile plus
```

Approve plan usage on the official sign-in page. If a previous sign-in completed
without this permission, request consent explicitly:

```bash
tradingagents auth login chatgpt_plan --profile plus --enable-plan-usage
```

Sign-in uses PKCE, state and nonce with an IPv4 loopback callback. Verified OIDC
identity binds each connection's server-issued client ID to its account.
Profiles default to `~/.config/tradingagents/chatgpt_plan`, with owner-only files,
atomic updates and a lock around rotating refresh tokens. `TRADINGAGENTS_CHATGPT_AUTH_DIR`
and `TRADINGAGENTS_CHATGPT_PROFILE` select storage/profile explicitly. Each
profile is a separate renewable connection. Analysis never launches sign-in,
reads browser cookies or reuses another application's credential cache.

Logout attempts official session revocation before removing local tokens. If
remote revocation cannot be confirmed, disconnect TradingAgents in ChatGPT
Settings. Registration metadata is retained for later sign-in. Credential values
are omitted from representations, status, errors and tool metadata.

For Google, install the verified official CLI and run `gemini` interactively
once, selecting **Sign in with Google** with the personal Google AI Pro account.
Then run `tradingagents auth status gemini_cli`. Preflight checks configured auth
and cache presence without reading/copying tokens; the CLI owns refresh and
validates the cached credentials during a live request. Encrypted cache mode is
supported through the CLI's account marker. `GEMINI_CLI_HOME`, if used, is the
base home directory containing `.gemini`, not the `.gemini` directory itself.

Headless analysis never opens a browser or asks for an authorization code. An
expired/revoked cache requiring interaction produces an actionable auth error.
Gemini CLI version/help must expose the verified headless and isolation flags;
unverified minor versions are rejected. Node.js 20 or later is required.

## Configuration

After authentication, use a slug printed by `tradingagents auth models chatgpt_plan`:

```python
from copy import deepcopy
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

config = deepcopy(DEFAULT_CONFIG)
config.update({
    "llm_provider": "chatgpt_plan",
    "quick_think_provider": "chatgpt_plan",
    "quick_think_llm": "<account-visible-chatgpt-model-slug>",
    "deep_think_provider": "gemini_cli",
    "deep_think_llm": "auto",
    "backend_url": None,
    "quick_think_backend_url": None,
    "deep_think_backend_url": None,
    "temperature": None,
    "max_tokens": None,
    "llm_max_retries": 1,
})
graph = TradingAgentsGraph(config=config)
state, decision = graph.propagate("AAPL", "<YYYY-MM-DD>")
```

The CLI uses the existing `TRADINGAGENTS_QUICK_THINK_PROVIDER`,
`TRADINGAGENTS_DEEP_THINK_PROVIDER` and tier model variables. Neither subscription
provider accepts backend URLs, temperature or output-token caps. Unsupported
settings fail before inference. ChatGPT accepts the existing optional OpenAI
reasoning-effort knob where the selected model supports it. Gemini uses `auto`
or a model actually supported by the signed-in CLI account. The default
per-attempt timeout is 600 seconds; direct factory callers can pass `timeout`.
`llm_max_retries` controls bounded retries. CLI-internal retries remain bounded
by the enclosing timeout.

ChatGPT accepts only a completed terminal Responses event. HTTP admission
errors, failed/incomplete/interrupted streams and quota failures after partial
text are rejected. Only rate limits and transient errors receive bounded
retries; exhausted quota, ineligible accounts and disabled plan permission do
not. Invalid/orphan/duplicate tool calls are rejected. These service errors do
not trigger the decision agents' free-text fallback and repeat quota usage.

Each Gemini invocation has an isolated temporary workspace, a system prompt
file and stdin conversation history. It disables core tools, extensions, MCP
discovery, hooks, agents and skills; conversation `@` characters cannot become
CLI file imports. API billing overrides and caller-wide settings are isolated
in the child only. The user's settings/credential files are not changed. Raw
CLI diagnostics are classified internally and discarded, including on malformed
JSON and nonzero exits. Timeout/cancellation terminates the process group and
waits for cleanup. Unexpected internal tool execution causes rejection.

## Offline evidence and pending live checks

Validation on 2026-10-06, Python 3.12.14:

| Check | Result |
| --- | --- |
| Full upstream suite plus new offline tests, including optional Bedrock dependency | **1,440 passed; 0 failed; 5 integration tests deselected; 20 upstream warnings** |
| Subscription auth/transport/tool/routing tests | **177 passed** |
| Explicit live-test collection with default guards | **4 skipped**; no sign-in or inference performed |
| Ruff across repository | Passed |
| Actual official Gemini CLI 0.62.0 version/help and settings merge | Passed without auth/inference; conflicting API, shell, hook and credit settings were overridden |
| Actual Market Analyst + existing LangGraph ToolNode, mocked transport/data | Passed: stock-data tool → ToolMessage → indicator tool → ToolMessage → verified snapshot → final report; wrap-up budget also covered |
| Subscription-backed live invoke/schema/two tool rounds/Gemini JSON | Pending user sign-in and entitlement verification |
| Full AAPL run using both subscriptions | Pending consolidated live session |

The [2026-10-06 code review](subscription-code-review.md) records the corrected
registration, permission, loopback, tool-ID, SSE and malformed-protocol issues,
with 47 additional offline regression cases. Live verification remains pending.

The default pytest configuration excludes `integration`: the five deselected
tests are the four new subscription live checks and one existing DeepSeek live
check. The full suite used dummy AWS credentials only to construct an offline
Bedrock client without contacting EC2 metadata. No AWS service was called.

Reproduce offline checks:

```bash
uv pip install --python .venv/bin/python -e '.[dev,bedrock]'
AWS_ACCESS_KEY_ID=offline-placeholder AWS_SECRET_ACCESS_KEY=offline-placeholder \
AWS_EC2_METADATA_DISABLED=true .venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest tests/test_subscription_live.py -o addopts='' -m integration -ra
```

## One consolidated Ubuntu verification session

Prerequisites: `git`, `uv`, Node.js >=20 with `npm`, and a browser usable for
the two official sign-in flows. Start a fresh checkout to keep any existing
installation and its API settings intact:

```bash
git clone --branch feat/subscription-providers --single-branch \
  https://github.com/bugu-robot/TradingAgents.git TradingAgents-subscriptions
cd TradingAgents-subscriptions
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[dev]'
source .venv/bin/activate
node --version
npm install --prefix "$HOME/.local/share/tradingagents-gemini" @google/gemini-cli@0.62.0
export PATH="$HOME/.local/share/tradingagents-gemini/node_modules/.bin:$PATH"
export TRADINGAGENTS_GEMINI_CLI_BIN="$(command -v gemini)"
gemini --version
```

If Ubuntu is accessed through SSH, establish this forwarding connection from
the computer running the browser **before ChatGPT sign-in**, and keep it open:

```bash
ssh -L 1455:127.0.0.1:1455 <user>@<ubuntu-host>
```

On Ubuntu, run the following in the checkout's activated virtual environment.
Open the printed ChatGPT URL in that browser and approve plan usage. Select
**Sign in with Google** in Gemini, authenticate the AI Pro personal account and
exit the interactive CLI with `/quit` once authentication is cached. The Google
sign-in below removes API/Vertex overrides only for that invocation.

```bash
export TRADINGAGENTS_CHATGPT_PROFILE=plus
tradingagents auth login chatgpt_plan --profile plus --no-browser --port 1455

gemini_signin_dir=$(mktemp -d)
(
  cd "$gemini_signin_dir"
  env -u CI -u GEMINI_API_KEY -u GOOGLE_API_KEY \
    -u GOOGLE_GENAI_USE_VERTEXAI -u GOOGLE_GENAI_USE_GCA \
    -u GOOGLE_APPLICATION_CREDENTIALS -u GOOGLE_CLOUD_ACCESS_TOKEN \
    -u GOOGLE_GEMINI_BASE_URL -u GOOGLE_CLOUD_PROJECT -u GCLOUD_PROJECT \
    -u CLOUDSDK_CORE_PROJECT -u CLOUD_SHELL NO_BROWSER=true gemini
)
rm -rf -- "$gemini_signin_dir"

tradingagents auth status chatgpt_plan
tradingagents auth status gemini_cli
tradingagents auth models chatgpt_plan
read -r -p 'ChatGPT model slug from the catalog above: ' CHATGPT_PLAN_LIVE_MODEL
export CHATGPT_PLAN_LIVE_MODEL CHATGPT_PLAN_LIVE_PROFILE=plus GEMINI_CLI_LIVE_MODEL=auto
RUN_SUBSCRIPTION_LIVE=1 python -m pytest tests/test_subscription_live.py \
  -o addopts='' -m integration -q --tb=short
```

All four smoke tests must pass before continuing. They use real subscription
allowance; the ChatGPT checks cover conversation, native structured output and
two sequential tool/result turns. No login is triggered by the tests. If plan
permission was declined, rerun the explicit `--enable-plan-usage` command above.
If OpenAI preview access/eligibility or Google account entitlement is unavailable,
stop here and retain the error classification; do not switch to another endpoint
or an API key to label the subscription smoke test a success.

Run one full four-analyst AAPL graph, including research, trader, risk debate and
portfolio manager, using the supported quick/deep combination:

```bash
export TRADINGAGENTS_LLM_PROVIDER=chatgpt_plan
export TRADINGAGENTS_QUICK_THINK_PROVIDER=chatgpt_plan
export TRADINGAGENTS_QUICK_THINK_LLM="$CHATGPT_PLAN_LIVE_MODEL"
export TRADINGAGENTS_DEEP_THINK_PROVIDER=gemini_cli TRADINGAGENTS_DEEP_THINK_LLM=auto
export TRADINGAGENTS_LLM_BACKEND_URL='' TRADINGAGENTS_QUICK_THINK_BACKEND_URL=''
export TRADINGAGENTS_DEEP_THINK_BACKEND_URL='' TRADINGAGENTS_TEMPERATURE='' TRADINGAGENTS_MAX_TOKENS=''
export TRADINGAGENTS_OPENAI_REASONING_EFFORT='' TRADINGAGENTS_GOOGLE_THINKING_LEVEL=''
export TRADINGAGENTS_OUTPUT_LANGUAGE=English
export TRADINGAGENTS_MAX_DEBATE_ROUNDS=1 TRADINGAGENTS_MAX_RISK_ROUNDS=1
export TRADINGAGENTS_MAX_TOOL_ROUNDS=6 TRADINGAGENTS_LLM_MAX_RETRIES=1
export TRADINGAGENTS_RESULTS_DIR="$PWD/results-subscription-verification"
export TRADINGAGENTS_CACHE_DIR="$PWD/cache-subscription-verification"
tradingagents --ticker AAPL --date "$(date -u +%F)" \
  --analysts market,social,news,fundamentals --save --no-show --html --checkpoint
```

The existing graph saves reports and supports resuming a failed node with the
same command. A complete run requires a final portfolio decision and saved
report, with the report's configuration recording the two subscription provider
names. Market/news/fundamental data availability is independent of LLM
authentication. There is no claim of a completed live AAPL run until this session
has actually finished.

## Official references

Checked 2026-10-05/06. The architecture and historical PR review are recorded in
[subscription-architecture-review.md](subscription-architecture-review.md).

- [OpenAI: token sharing for open-source tools](https://developers.openai.com/siwc/token-sharing-open-source)
- [OpenAI: sign-in and registration](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI: profiles and sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [OpenAI: models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [OpenAI: preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [OpenAI: errors and recovery](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [OpenAI: Responses function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI: structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Gemini CLI: authentication](https://geminicli.com/docs/get-started/authentication/)
- [Gemini CLI: headless mode](https://geminicli.com/docs/cli/headless/)
- [Gemini CLI: quota and pricing](https://geminicli.com/docs/resources/quota-and-pricing/)
- [Gemini CLI: configuration, extension flags and credit overage](https://geminicli.com/docs/reference/configuration/)
- [Gemini CLI: custom system prompt](https://geminicli.com/docs/cli/system-prompt/)
