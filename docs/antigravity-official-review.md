# Antigravity official-interface review

Access date: **2026-10-06 UTC**. Official Google documentation is the source of
truth; actual Linux executable/version/help checks qualify the implementation.
No user sign-in or model inference was used for this review.

| Topic | Official evidence | Implementation implication |
| --- | --- | --- |
| Google AI Pro | [Plans](https://www.antigravity.google/docs/plans/) | Pro has Antigravity baseline quota; real personal entitlement remains live-pending. |
| Linux / installation | [Install](https://www.antigravity.google/docs/cli/install/) | Reviewed adapter pin: official native `agy` **1.2.17**. A newer stable **1.3.0** was observed/reported after the previous review; it is not adapter-reviewed and is reserved for a separate compatibility task after live acceptance. |
| SSH / cached auth | [Install/auth](https://www.antigravity.google/docs/cli/install/) | CLI prints a URL, local browser returns a code pasted into SSH; CLI/keyring owns credentials. |
| Headless / output | [Headless](https://www.antigravity.google/docs/cli/headless/) | Print mode; JSON completion envelope and NDJSON init/step/result events. |
| Schema | [Headless schema](https://www.antigravity.google/docs/cli/headless/#structured-output-with-a-schema) | `--json-schema`; enforced schema and `structured_output` in terminal result; independently validate. |
| Models / effort | [Headless selection](https://www.antigravity.google/docs/cli/headless/#select-a-model-effort-or-agent), official [CLI changelog](https://www.antigravity.google/docs/changelog?tab=cli), official [issue #777](https://github.com/google-antigravity/antigravity-cli/issues/777) | `--output-format` is a global flag and must precede the subcommand: `agy --output-format json models`. Issue #777 corrects the earlier `agy models --output-format json` ordering and confirms the machine-readable result envelope. |
| Authentication / usage | [Headless cached credentials](https://www.antigravity.google/docs/cli/headless/), official [CLI changelog](https://www.antigravity.google/docs/changelog?tab=cli), [Usage](https://www.antigravity.google/docs/cli/commands/usage) | Cached sign-in is official; authentication-required is a documented headless error. Read-only print `/usage` returns machine-readable JSON without a turn per changelog. Stable account/plan/quota field schema is not documented; status only accepts SUCCESS + zero turns and does not infer entitlement. |
| Effective config/permissions | Official [CLI changelog](https://www.antigravity.google/docs/changelog?tab=cli), [Permissions](https://www.antigravity.google/docs/cli/commands/permissions) | Release notes say JSON is available for `/config` and `/permissions` without a turn. The docs describe an interactive permission manager and publish no stable JSON field schema. Do not parse guessed keys as a policy gate. |
| Credits overage | [Credits](https://www.antigravity.google/docs/cli/credits/), [Plans](https://www.antigravity.google/docs/plans/) | `useG1Credits=false`; no purchased/promotional overage fallback. |
| API / custom endpoint | [Install API mode](https://www.antigravity.google/docs/cli/install/#using-a-gemini-api-key) | `modelProvider=gemini` plus GEMINI_API_KEY routes to API; reject this config before inference. GOOGLE_GEMINI_BASE_URL is a routing override. |
| Settings | [Settings](https://www.antigravity.google/docs/settings?tab=cli), [Reference](https://www.antigravity.google/docs/cli/reference/) | Inspect real `~/.gemini/antigravity-cli/settings.json`; no global modifications or administrator-policy substitution. |
| Permissions | [Permissions](https://www.antigravity.google/docs/permissions?tab=cli) | Deny > Ask > Allow. Workspace file access is implicitly allowed unless denied. Strict preset alone is insufficient. |
| Tool scoping | [Custom agents](https://www.antigravity.google/docs/subagents/), [Google introduction](https://www.antigravity.google/blog/introducing-custom-agents) | Scoped main-agent tool/skill/plugin/MCP lists; validate actual no-tool configuration. |
| Startup side effects | [Hooks](https://www.antigravity.google/docs/hooks/), [MCP](https://www.antigravity.google/docs/mcp/) | Inspect shared/global customizations; a post-output check cannot undo startup commands. |
| Auto-updates | [Troubleshooting](https://www.antigravity.google/docs/cli/troubleshooting/) | Official `AGY_CLI_DISABLE_AUTO_UPDATE=true`; reject unverified protocol versions. |

## Actual executable inspection

The official installer obtained the Google release manifest for Linux amd64:
version 1.2.17, archive SHA-512
`d0ebe612f7cfc21c8de9e7a7a62964b2245d89ddb570d5e27e83e61a2cc76cb38e80b6eb3bdd71bef683eba027c4a97dcce4ced81f47f827763234d0cd3ec592`.
Installer verification and `agy --version` both succeeded. Actual help advertises
`--print`, `--input-format`, `--output-format`, `--json-schema`, `--model`,
`--effort`, `--agent`, `--sandbox`, `--print-timeout`, `--log-file` and
`--disable-slash-commands`. Help permits effort low/medium/high/xhigh/max, while
the website only lists low/medium/high: initially accept the documented three.
The actual installer accepts `--dir`; its published skip flags were absent in
this downloaded bootstrapper. Final verification will use a pinned checked
archive without shell-profile mutation rather than assume installer flags.

### Correct global-flag ordering and model catalog envelope

Rechecked 2026-10-06. Official Antigravity CLI [issue #777](https://github.com/google-antigravity/antigravity-cli/issues/777)
initially reports that `agy models --output-format json` rejects the flag. The
maintainer-confirmed correction is to place global `--output-format json`
before the subcommand: `agy --output-format json models`. The corrected command
returns a zero-turn terminal envelope with `status: SUCCESS`, `num_turns: 0`,
and `command: {name: "models", data: {models: [{id, label}, ...]}}`.

The adapter now calls this exact form. It requires an object root, SUCCESS,
absent/empty `error`, an integer zero `num_turns`, `command.name == "models"`,
an object `data`, and a non-empty bounded models array. IDs must be conservative
safe slugs and unique; labels are optional bounded printable display metadata.
Malformed envelopes, duplicates, unsafe IDs, non-zero turns and plain-text
output fail closed. No human-readable fallback or model request is used for
catalog discovery.

The adapter remains pinned to the reviewed 1.2.17. Version 1.3.0 is noted as a
newer stable release observed/reported after the prior review; it has not been
adapter-reviewed. Keep the current pin for live acceptance and handle 1.3.0 in
a separate compatibility review afterward.

Static inspection also identifies ADC and LLM gateway environment overrides;
they will be excluded conservatively. This is configuration inspection, not an
alternative transport or permission to invoke private endpoints.
Agent inheritance/exclusion fields recognized by static binary inspection are
not claimed runtime verified. Scoped agent files in offline tests use those
fields, but live acceptance must verify their effective exclusion through strict
zero-tool init before accepting a result. Input follows the documented stdin-first
protocol; configuration and tool/permission restrictions apply before startup.

## Cached-account admission correction — 2026-10-06

[CLI reference](https://www.antigravity.google/docs/cli/reference/) documents
`/help` as a TUI commands/shortcuts panel, not a supported non-inference headless
account/plan report. [Status-line metadata](https://www.antigravity.google/docs/cli/statusline/)
includes interactive `plan_tier`, but does not establish a separate headless
attestation endpoint. That absence is not a reason to block documented execution:
the current headless guide explicitly supports cached credentials and terminal
auth/status/error metadata. Use the real settings/binary preflight, default
account route, isolated scoped agent and sanitized environment; let the official
CLI authenticate/refresh from its own secure store during the actual request.
Do not read tokens or trust model-authored identity reports.

Catalog discovery independently executes `agy --output-format json models`,
without model inference. Parse the maintainer-confirmed envelope strictly,
extract only safe slugs, reject malformed/duplicate entries, use no text
fallback, and require fresh membership at invocation. The reviewed pin is
1.2.17; the newer stable 1.3.0 is not adapter-reviewed. There is no
Gemini-family allowlist. GPT choices remain independent in the ChatGPT account
catalog. Availability changes; neither catalog proves subscription entitlement.

The verified CLI's `-p "/usage" --output-format json` is used for an official
read-only cached-account/backend readiness check. Accept only the standard
headless SUCCESS and zero-turn fields; retain no raw output and do not invent
plan/quota fields. `/usage` success means the read-only CLI operation worked,
not that Google AI Pro entitlement or a particular quota was established.
Record official usage evidence before and after requests during live acceptance.

The changelog advertises no-turn JSON for `/config` and `/permissions`; however,
the official docs do not publish stable field schemas. These commands are not
adopted as machine policy validators. Existing local settings/policy checks and
the zero-tool stream init gate remain.

Submit input according to the official programmatic example, then validate init
before accepting the terminal SUCCESS result. Exact selected model, scoped
agent, private cwd, empty tools, strict/request-review mode and schema must match.
The real settings still require strict permissions and universal denies; the
headless guide documents request-review init, so that label alone is not an
unsafe downgrade. Always-proceed/unknown modes are rejected. Reject
autonomous execution metadata and any error; never downgrade or switch to API
billing. Real init/scoping/schema compatibility and Google AI Pro `/usage` quota
evidence are still LIVE PENDING. The catalog argument-order blocker is removed;
proceed to the consolidated live acceptance using the reviewed 1.2.17 pin. CLI
1.3.0 remains out of scope until a separate compatibility review after
acceptance.

## OpenAI recheck

- [Official self-hosted VMs](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms):
  complete OAuth locally, transfer this tool's protected selected registration
  using SSH, preserve the separately created VM host ID, then let the VM refresh.
- [Registration/sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
  and [accounts/sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
  remain the existing OAuth protocol contract; re-open them before any auth change.

SSH loopback forwarding is an optional deployment alternative and must not be
represented as the official OpenAI self-hosted workflow.
