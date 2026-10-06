# Subscription provider code review — 2026-10-06

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
- Four opt-in subscription live checks still skip by default. No real OAuth
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
the single [Ubuntu verification session](subscription-providers.md#one-consolidated-ubuntu-verification-session).
Gemini CLI remains deep-only with the existing free-text fallback; no native
tool-call or constrained-schema capability is claimed. Subscription quota
exhaustion never causes an automatic switch to API billing. Future unverified
Gemini CLI minor versions are rejected. The PR remains Draft and unmerged.

Official protocol sources rechecked:

- [OpenAI registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI accounts, refresh and revocation](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [OpenAI preview transport requirements](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
