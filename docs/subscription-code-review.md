# Subscription provider code review — 2026-10-06

The first section below is the **historical pre-migration review**. Its Gemini
CLI implementation/counts are superseded by the Antigravity migration review at
the end of this file. Current evidence and acceptance gates are in STATUS.md and
VERIFICATION.md.

Reviewed the feature at `52d255f49eb2d648bdf328c12fce59b44954e6a3`, based on
TradingAgents v0.6.0 (`1394a3f72aa4393e1a98f51b382434c4b4c2d972`). Scope included
OAuth registration/identity/rotation/revocation, credential diagnostics, Responses
SSE and tool continuation, Gemini CLI authentication/isolation/process cleanup,
capability routing, structured-output fallback and the real analyst graph.
All findings below were fixed on `feat/subscription-providers`; existing API
providers and upstream graph routing remain intact.

## Findings and fixes

| ID | Severity | Trigger and original behavior | Correction and regression evidence |
| --- | --- | --- | --- |
| R1 | P1 | `--profile active` or `host` selects the same JSON path as internal account-selector/host metadata. Login or activation can overwrite credentials or host registration. | Reject reserved labels, case variants and trailing dots before writes. Tests confirm all existing JSON files remain byte-for-byte unchanged. |
| R2 | P1 | A successful refresh removes plan-use scopes, but `access_token()` immediately returns the refreshed token for inference. Status/activation also checked only one of the two required permissions. | Persist the rotating replacement first, then validate the full grant before returning a token. Status and activation require both direct plan use and resource invocation, with valid scope-list types. A revoked-grant invocation produces no inference HTTP request while retaining the replacement refresh token. |
| R3 | P1 | A new response reuses an earlier tool-call ID. The response parser accepts it, ToolNode executes it again, and only the next history validation notices the duplicate. | Check new call IDs against all earlier assistant turns before exposing the AIMessage. An actual Market Analyst/ToolNode regression records two model requests and exactly one stock-data execution. |
| R4 | P2 | A loopback peer connects but never finishes HTTP headers. `HTTPServer.timeout` bounds accept, not the accepted socket read, so the advertised OAuth deadline can hang. Unicode or duplicate blank state parameters also escaped strict callback handling. | Bound accepted socket reads and each accept wait by the remaining deadline. Compare encoded state bytes and retain blank query values during duplicate checking. A real stalled loopback connection exits with a timeout without login or credential changes. |
| R5 | P2 | Logout retries HTTP 5xx but a connection exception escapes the whole retry loop, clearing local tokens after one attempt even when revocation could recover. | Retry network/temporary discovery and revocation failures with bounded backoff while retaining the refresh token; clear it after success/exhaustion. A two-failure/third-success test confirms all three revocation attempts still have the token available. |
| R6 | P2 | Token endpoint request-ID diagnostics may contain an unlabelled known refresh token or authorization code. Generic pattern redaction alone leaves that value in `SubscriptionError.request_id`. | Apply the caller's known-secret redaction to request IDs centrally, alongside error codes and detail bodies. Test an opaque refresh-token value returned in the request-ID header. |
| R7 | P2 | Requests may decode `text/event-stream` without a charset as Latin-1, corrupting UTF-8 Chinese text. The parser also keeps reading after a completed terminal event and can retry a finished inference if waiting for EOF times out. | Read SSE bytes and decode explicitly as UTF-8; reject invalid UTF-8 safely. Return on the validated completed event and close the response context. Tests use actual Requests byte decoding for a Chinese report and a stream that would raise ReadTimeout if consumed after completion. |
| R8 | P2 | NaN/infinite expiry values pass ordinary numeric checks, while malformed token/scope/identity metadata can be accepted or crash authentication handling. | Validate finite expiry/renewal values, renewable token strings, returned scope types and identity-discovery envelopes. Corrupt saved grant metadata cannot activate a connection or be used for inference. |
| R9 | P2 | Null/list terminal bodies, nonstring text, malformed usage/catalog entries or Gemini auth settings cause uncategorized AttributeError/TypeError. Non-JSON 401/403 admission bodies can be reported as temporary network errors instead of auth/permission errors. | Validate protocol envelope/content types before use, fail with safe classified SubscriptionError values, and retain HTTP admission classification without logging raw bodies. Malformed response/tool failures stop before execution or structured fallback; malformed CLI auth never starts inference. |

## Validation

- **1,440 passed, 0 failed, 5 integration tests deselected, 20 existing warnings**
  in the full regression suite on Python 3.12.14, including optional Bedrock.
- **177 subscription offline tests passed**; **47 new regression cases** since
  the reviewed baseline. New tests include actual socket lifecycle, Requests
  UTF-8 decoding and real LangGraph ToolNode execution, alongside mocked service
  admission/refresh responses.
- Ruff and `git diff --check` pass.
- Four opt-in subscription live checks skipped at that historical checkpoint. No real OAuth
  login, model request, subscription quota or AWS service was used for review.

The offline Bedrock construction test uses dummy AWS credentials and disables
EC2 metadata lookup. This does not establish live AWS access. Likewise, mocked
OAuth/Responses tests do not establish the user's ChatGPT plan entitlement.

## Published implementation checkpoints

- `aa394ac5b50bb72308b5ba60cba1220795d0bf4b` — registration protection, revoked
  grants, loopback deadline, revocation retries and credential diagnostics.
- `5cd97e20a1aa9921b705017eda33efd933427661` — cross-turn call IDs, UTF-8/terminal
  SSE behavior, envelope validation and permission/status checks.

## Remaining verification and limits

ChatGPT account consent/preview eligibility, Google AI Pro cached sign-in and
quota, live structured/tool continuation and the full AAPL run remain pending
the single [Ubuntu verification session](../VERIFICATION.md). The historical
Gemini adapter has since been removed. Current Antigravity native-schema status
and compatibility blockers are recorded below. The PR remains Draft and unmerged.

Official protocol sources rechecked:

- [OpenAI registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI accounts, refresh and revocation](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [OpenAI preview transport requirements](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## Antigravity migration review — 2026-10-06

Reviewed `ed7a3f9687c08e70a8c0f1d53c8fffe328cc8490` and the subsequent corrections
on the existing feature branch. The official Linux 1.2.17 CLI version/help and
release checksum were inspected without Google tokens or model requests.
OpenAI registration/sign-in and self-hosted VM guidance were rechecked before
changing credential storage. Existing OAuth protocol, endpoints and grant scopes
are retained; changes address demonstrated storage/protocol/schema issues.

| ID | Severity | Finding | Fix and offline evidence |
| --- | --- | --- | --- |
| A1 | P2 | Informational CLI probes used unbounded capture and killed only the leader on timeout, leaving language-server descendants or inherited pipes alive. | Bounded nonblocking capture, deadlines, cancellation, group termination and reaping for probes and inference. Fake executable tests cover excess output, descendants retaining pipes, closed pipes, timeout and cancellation. |
| A2 | P2 | Checking only `$ref` misses external `$dynamicRef` and `$id` resource scopes; unresolved schema references can escape as a generic exception and trigger upstream free-text fallback. Direct `bind(native_schema=...)` also bypasses binding validation. | Validate schemas again before any process; reject external references, resource IDs and unreviewed dialects. Explicit no-fetch referencing registry; safe terminal SubscriptionError on resolution/schema failure. Tests assert no preflight/inference/download for external resources. |
| A3 | P2 | JSON permits duplicate keys and float overflow despite rejecting literal NaN; ChatGPT function arguments could expose ambiguous values to ToolNode. Deep nesting can escape parser handling. | Shared strict object loader rejects duplicates, nonfinite numbers/overflow and excessive nesting for CLI, SSE, credentials and function arguments. Tests prove one model response is rejected before tool execution or refresh. |
| A4 | P2 | OAuth storage prepares symlinked directories and opens symlinked rotation locks; file ownership/type checks were incomplete. Antigravity settings ancestors could be writable by other users. | Protected directory/file ownership and regular-file checks, owner-only OAuth directories, no-follow bounded credential reads and no-follow locks. Antigravity checks real config ancestors. Regressions prove unrelated sentinel files/settings and target permissions remain unchanged. |
| A5 | P2 | ChatGPT malformed/coercible structured values could be accepted by Pydantic or escape as ValueError, causing an extra plain request. | Strict JSON, independent JSON Schema validation with a no-fetch registry, strict Pydantic JSON validation and terminal redacted SubscriptionError. Five malformed/schema cases prove exactly one request and no free-text fallback. Explicit include_raw retains safe parsing_error behavior. |
| A6 | P2 | Nonzero CLI exits before init lost auth classification; cancellation after output pipes closed could wait until the long request deadline. | Classify nonzero exit diagnostics safely; poll cancellation/deadline while waiting for exit. Regressions confirm auth classification without raw-secret leakage and child reaping after closed pipes. |
| A7 | P2 | Action metadata recognition missed camelCase/plugin/skill spellings and confused structured property names with execution metadata. | Normalize reviewed metadata keys and reject all action namespaces; schema/structured-value payloads remain data. Tests cover MCP/plugins/subagents/commands and harmless structured fields named commands/tool_calls. |
| A8 | P1 | Proposed `--print /help` authentication probe assumes a headless account report not promised by official docs; it could be a model prompt rather than trusted identity evidence. | Remove the speculative probe and all Pro-report parsing. Authentication always fails before inference until a supported official non-inference preflight is implemented/reviewed. A configured/version-verified CLI regression proves only --version/--help run; no prompt/Google token inspection or bypass exists. |

All A1–A8 are corrected before live verification. No unresolved P1/P2 code finding
is accepted. OAuth state, nonce, S256 PKCE, signature/issuer/audience/expiry and
returning-subject validation, exact redirect handling, atomic refresh rotation,
credential redaction, cross-turn tool IDs and terminal UTF-8 SSE handling were
reviewed with existing regressions. Credential diagnostics never expose raw CLI
text. Google credentials remain entirely CLI-owned.

Antigravity subscription isolation was reviewed across actual global settings,
API/Vertex/ADC/service-account/custom endpoints, credit overage, environment
contamination, shared customization/policy, private workspace permissions,
file/command/URL denial, MCP/plugins/skills/subagents, strict init, action
metadata, JSON Schema, terminal failure, bounded retries and process cleanup.
No global settings or administrator policy are automatically overwritten or
hidden. Final test evidence: **342 subscription offline cases passed**;
**1,605 whole-fork tests passed; 1,263 clean-baseline tests passed**, with the
same 20 upstream warnings and no failures. Six live cases skip
by default. Skips are not passes.

Two **acceptance/official-interface blockers**, separate from corrected code
findings, remain: there is no reviewed official non-inference headless Pro
preflight, and init-before-input ordering is unverified. Authentication admission
now unconditionally fails before inference; login cannot unlock it. Prompt instructions and mock
metadata are not proof of sandboxing, entitlement or billing. Actual CLI startup
still owns its internal configuration/keyring/log files; the zero-tool boundary
constrains model actions. A future CLI version requires another review. No live
subscription use or full AAPL run has been claimed; Draft PR #1 stays unmerged.
