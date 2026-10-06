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
| A8 | P1 | Proposed `--print /help` authentication probe assumes a headless account report not promised by official docs; it could be a model prompt rather than trusted identity evidence. | Removed the speculative probe and all Pro-report parsing. The interim unconditional gate in d6865f1/f0f6358 was subsequently corrected by B1 below: use documented cached-account execution, not an invented attestation interface. No speculative prompt, Google token inspection or bypass exists. |

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
hidden. The original migration checkpoint recorded 342 subscription/1,605 full
tests; the correction results below supersede those counts.

## Admission/catalog/model-selection correction review — 2026-10-06

Reviewed user-reported f0f6358 findings and fixes published in 3d35c60/9b44b80.
Reopened current official [headless](https://www.antigravity.google/docs/cli/headless/),
[installation/auth](https://www.antigravity.google/docs/cli/install/),
[models](https://www.antigravity.google/docs/models/),
[credits](https://www.antigravity.google/docs/cli/credits/),
[settings](https://www.antigravity.google/docs/settings?tab=cli) and
[interactive /usage](https://www.antigravity.google/docs/cli/commands/usage).
OpenAI OAuth behavior is unchanged by this correction; existing account catalog,
tool-call, SSE, schema and protected-token regressions still pass.

| ID | Severity | Finding | Fix and offline evidence |
| --- | --- | --- | --- |
| B1 | P1 functional | Authentication always raises, so even a valid cached official Google sign-in can never execute. Lack of a separate Pro attestation is incorrectly treated as an interface blocker. | Remove unconditional gate. Real settings/binary admission permits documented cached-account execution; CLI owns authentication/refresh and terminal auth errors. No invented account probe/token reading. Complete fake-executable admission + catalog + successful stream tests cover each family without bypassing preflight. Actual Pro entitlement remains a live /usage acceptance requirement. |
| B2 | P2 | Catalog discovery calls the blocked inference preflight, preventing documented `agy models`. | Separate catalog preflight; run only version/help/models probes with no model request. The parser/CLI-command regression uses a mocked JSON response only. Actual verified 1.2.17 rejects the output-format flag; see C1 below. Unsafe settings still prevent catalog process startup. |
| B3 | P2 | Gemini-only syntax and parsing rejects official catalog models from Claude/other families. | Conservative family-independent slug syntax plus fresh official catalog membership before inference. Reject malformed/duplicate catalogs, path/flag/shell/custom IDs and unlisted models. Gemini/Claude/GPT-OSS fixtures pass exact --model; mismatched init or unavailable CLI selection fails without fallback. |
| B4 | P2 | Subscription model menu offers arbitrary custom IDs; one env model hides both tier choices; effort is absent from selection/run settings. | Independent Quick/Deep catalog menus with no custom entry; each subscription tier requires its own unattended model. Capability-driven low/medium/high effort passes through run config/CLI and saved settings. Existing API env/default regressions remain unchanged. |
| B5 | P2 | Waiting for init before writing stdin relies on an undocumented ordering and can deadlock a supported input-first CLI. | Use documented stdin-first operation under prevalidated settings, sanitized environment and scoped zero-tool agent. Validate init as soon as received; accept no output before valid init, terminal SUCCESS and exit 0. Unsafe input-first init and autonomous metadata are rejected; real fake-process tests verify cleanup. |
| B6 | P2 | Immediate closed stdin can mask cached-auth failure as BrokenPipe instead of safely classifying terminal diagnostics. | Drain stderr/terminal events after a broken input pipe, then classify nonzero exit safely. Auth failure before init remains terminal and raw diagnostics never escape. |
| B7 | P2 | Strict-only permission label may reject the officially documented request-review init even with strict settings and zero tools. | Require strict real settings + universal denies; admit strict/request-review init only with empty tools and exact isolated model/agent/schema. Reject always-proceed/unknown modes. Complete admission test exercises documented request-review output. Billing-route checks remain identical. |

Focused security review found **no open P1/P2 code finding** after corrections.
Reviewed subscription-only settings and every retry, custom/provider/Vertex/ADC
rejection, allowlisted environment, no global policy bypass, current catalog
membership, exact model/no fallback, private workspace/agent/logs, zero-tool init,
action metadata, terminal schema validation and error classification, subprocess
deadlines/cancellation/group cleanup, and raw diagnostic redaction. Selected
models/effort are safe run metadata; credentials remain CLI/app owned.

At that review checkpoint, **402 subscription offline tests passed; 1,665
full-fork tests passed, 7 integration deselected, 100 subtests; 1,263 clean
v0.6.0 baseline tests passed, 1 integration deselected, 99 subtests**. Both full suites retain the same
20 upstream warnings. Ruff, diff-check, compile/import and dependency check pass.
Six LIVE tests explicitly skip by default; **zero executed**, no live passes.

There is no unconditional admission or catalog blocker. Remaining acceptance
checks require real account credentials and service behavior: actual zero-tool
scoping/init/schema, selected-model Google AI Pro quota in official /usage,
Plus plan authorization, and the complete AAPL report. Catalog/local readiness,
prompt instructions and mocked metadata do not prove entitlement or billing.
Strict startup configuration provides the preventive boundary; metadata rejection
cannot undo actions. The trusted official CLI still owns internal configuration,
keyring, logs and service requests. A future CLI version requires another review.
Draft PR #1 remains unmerged and production acceptance is pending.

Verification workflow correction: the Google TUI helper originally opened a
terminal in buffered read/write mode, which requires seeking. Use unbuffered
binary `/dev/tty` and require a controlling interactive SSH terminal. A local
PTY subprocess check proved stdin/stdout passthrough; this Work runtime has no
accessible controlling `/dev/tty`, and no actual sign-in was attempted. This
changes verification instructions only; provider regression counts are unchanged.

## Machine-catalog and read-only usage correction — 2026-10-06

This addendum supersedes the earlier conclusion that catalog discovery is
currently usable. Rechecked the official [CLI changelog](https://www.antigravity.google/docs/changelog?tab=cli),
[headless JSON protocol](https://www.antigravity.google/docs/cli/headless/),
[usage guide](https://www.antigravity.google/docs/cli/commands/usage),
[permissions guide](https://www.antigravity.google/docs/cli/commands/permissions),
and the official CLI repository's [issue #777](https://github.com/google-antigravity/antigravity-cli/issues/777).
The SHA-512-verified Linux 1.2.17 binary in this workspace reproduces the
reported `agy models --output-format json` unknown-flag error. Therefore no
successful model-list JSON output shape from the pinned official CLI exists to
inspect in this environment.

| ID | Severity | Finding | Correction / remaining evidence |
| --- | --- | --- | --- |
| C1 | P2 external compatibility | Changelog says the model/agent list subcommands accept machine-readable output, but official Linux 1.2.17 rejects the flag and help omits it. | Always invoke only `agy models --output-format json`; parse strict JSON, reject malformed/duplicate/unsafe slugs and never fall back to display rows. Recognize the documented-flag rejection and fail closed. Selection/inference cannot run with 1.2.17. Wait for a fixed official binary and verify its actual JSON envelope before accepting the current fixture shape. |
| C2 | P2 status correctness | Auth status must not be blocked by inference preflight and must not claim a plan based on catalog/local configuration. | Status now runs local subscription-only settings checks, verified binary detection, then official `agy -p "/usage" --output-format json`. Require terminal SUCCESS plus documented zero `num_turns`; return separate local configuration and cached-account/backend readiness. Do not retain raw payload, read tokens or infer undocumented plan/quota fields. Unit tests prove exact command and no model transport. Live sign-in/backend success remains pending. |
| C3 | P3 schema/documentation | `/config` and `/permissions` can return no-turn JSON by release-note contract, but stable field definitions are absent from official docs. | Do not guess effective configuration/permission keys or treat them as a safety gate. Preserve local configuration/policy checks and stream init validation. These commands may be reviewed manually as private evidence. |
| C4 | P3 lifecycle regression | Async cancellation signaled the provider worker but did not reliably wait for owned subprocess cleanup before returning. | Worker now signals a thread-safe completion event after process-group reaping; cancellation waits for that event. Focused test verifies the child is gone before the cancelled task returns. |

The parser fixture uses `command.data.models[]` rows with `id` and optional
`label`; it is an expected strict envelope fixture, **not a verified actual
official 1.2.17 payload**. Tests verify parser behavior against that fixture,
family-independent Gemini/Claude/other slugs, duplicates, malformed JSON and no
text fallback. They must not be reported as proof of the actual catalog shape.
`/usage` fixtures similarly prove parsing/control flow, not Google AI Pro tier
or quota.

The local CLI was unable to start its no-account `/usage` probe because this
execution sandbox denied binding the CLI's local socket. No sign-in, account
query, quota consumption or model inference was performed. The official
changelog states read-only `/usage` print JSON starts no agent turn and spends
no model quota; `auth status` requires SUCCESS/zero turns. The usage guide
documents interactive model quota viewing/refresh, but does not provide stable
headless plan-tier fields. Thus status can establish that the official read-only
operation succeeded, not the plan tier or remaining model quota.

No P1/P2 subscription-isolation or credential-handling code finding is open
after this pass. The external P2 catalog incompatibility is still a real
functional blocker: do not perform live Antigravity model requests until an
official build exposes the advertised interface and its actual model JSON is
validated. PR #1 remains Draft and unmerged. Prior test totals above are the
previous checkpoint; the completed current correction suite is **1,678
full-repository tests passed, 7 integration deselected, 20 existing warnings,
100 subtests**, plus **415 dedicated subscription tests passed**. Six
subscription LIVE tests remain explicitly skipped, zero executed. Ruff, diff
check, compile/import and 102-package dependency check pass. See STATUS.md and
VERIFICATION.md for the remaining live acceptance.
