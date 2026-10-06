# Subscription providers: v0.6.0 review

Baseline: fork and upstream `main`, tag `v0.6.0`,
`1394a3f72aa4393e1a98f51b382434c4b4c2d972` (checked 2026-10-05).
`feat/subscription-providers` was created remotely at this commit before implementation.

## Existing extension points

- `llm_clients/factory.py`: lazy provider construction and `create_tier_client`.
  `tier_provider` already routes quick/deep independently. No hybrid router is needed.
- `openai_client.py`: registry for OpenAI-compatible API clients; native clients
  are selected separately. Subscription transports belong alongside native clients.
- `model_catalog.py` and `api_key_env.py`: shared CLI choices/validation and key lookup.
- `capabilities.py`: per-model API quirks. Subscription transport capabilities will
  be declared centrally and consulted at factory/CLI boundaries.
- `graph/trading_graph.py`: quick model drives analysts, researchers, risk debate,
  trader and signal processing; deep model drives research/portfolio managers.
- `agents/analysts/turn.py`: `bind_tools` returns `AIMessage.tool_calls`; existing
  LangGraph tool nodes produce `ToolMessage` and call the analyst again. Wrap-up
  removes tool bindings and renders prior calls/results as text.
- `agents/structured.py`: schemas used by decision agents and sentiment finalization;
  providers without structured output use the existing free-text fallback.
- `factory.build_llm_kwargs`: retries, temperature, output limits and provider knobs.
  A subscription route must reject unsupported settings before sending a request.
- `cli/prompts.py`, `selections.py`, `main.py`: choices, tier preflight, unattended
  environment configuration, and commands. Subscription auth must not prompt for keys.
- Existing credential handling is API-key environment based; OAuth profile storage
  must be separate, protected, atomically replaced and serialized during rotation.

## Official paths checked

OpenAI now documents public-client dynamic registration with PKCE, nonce, state,
issued client IDs, verified OIDC identity, direct plan-use scope and rotating tokens.
Use the public `/v1/responses` endpoint with `store=false`, `stream=true`, full
history, developer instructions and namespaced function tools. Only a completed
stream is success; quota failures may arrive after text deltas. Ordinary Codex
login credentials are not substituted for this app-specific plan-use authorization.

Google documents personal Google sign-in, Google AI Pro entitlement, cached auth
and headless use. Gemini CLI's JSON shell output is not by itself a native
LangChain tool-call or JSON-schema interface. Inspect the installed official CLI
before declaring those capabilities; unsupported tiers must fail explicitly.

References (official, accessed 2026-10-05):

- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
- https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery
- https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms
- https://developers.openai.com/codex/auth
- https://developers.openai.com/codex/app-server
- https://developers.openai.com/api/docs/guides/function-calling
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://geminicli.com/docs/get-started/authentication/
- https://geminicli.com/docs/cli/headless/
- https://geminicli.com/docs/resources/quota-and-pricing/
- https://geminicli.com/docs/reference/configuration/
- https://geminicli.com/docs/cli/system-prompt/

## Historical PR #1195

Read for reference only; not merged or cherry-picked. Its base was
`a33fd4c0f134485a43553a2c23a63cb14adbd88f`, head
`0ced629003d9bd32bceca8f0874c96201b215cf1`, with an older `cli/utils.py` layout.
It modifies Codex auth-file refresh, OpenAI payload normalization, model/key
registration, graph kwargs, CLI and README. Its own description identifies
`chatgpt.com/backend-api/codex` as undocumented. That endpoint and direct writes
to Codex's auth cache are not used here. Relevant lessons are system-to-developer
normalization, terminal stream validation and serialized refresh-token rotation.

## Checkpoints and acceptance

Every meaningful phase is tested and saved on the feature branch. Existing API
providers and graph execution remain intact. No upstream writes or PR merges.
Live OAuth, entitlement and AAPL verification are opt-in and consolidated after
offline development; mocked transport tests are not evidence of live entitlement.

Final offline CLI verification (2026-10-06): installed official
`@google/gemini-cli@0.62.0`; ran its real version/help probes without inference.
Loaded its actual settings implementation with a temporary home containing
conflicting API auth, shell-tool, hook and credit-overage preferences. With the
documented `--skip-trust` behavior, the isolated workspace correctly selects
`oauth-personal`, has an empty core-tool list, disables hooks/agents/skills and
sets `billing.overageStrategy=never`. Local `admin.*` fields are overwritten by
remote admin defaults in 0.62.0, so they cannot disable MCP/extensions. The
adapter instead uses documented `--extensions none` and a nonempty allowlist
containing only its unique, unconfigured temporary workspace name; native MCP
discovery rejects every other server. An empty MCP allowlist would allow all
servers and is deliberately avoided. No real credentials or model quota were
used in this verification.
