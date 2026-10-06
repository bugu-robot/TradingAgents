# Antigravity official-interface review

Access date: **2026-10-06 UTC**. Official Google documentation is the source of
truth; actual Linux executable/version/help checks qualify the implementation.
No user sign-in or model inference was used for this review.

| Topic | Official evidence | Implementation implication |
| --- | --- | --- |
| Google AI Pro | [Plans](https://www.antigravity.google/docs/plans/) | Pro has Antigravity baseline quota; real personal entitlement remains live-pending. |
| Linux / installation | [Install](https://www.antigravity.google/docs/cli/install/) | Official native `agy`, verified Linux amd64 release **1.2.17**. |
| SSH / cached auth | [Install/auth](https://www.antigravity.google/docs/cli/install/) | CLI prints a URL, local browser returns a code pasted into SSH; CLI/keyring owns credentials. |
| Headless / output | [Headless](https://www.antigravity.google/docs/cli/headless/) | Print mode; JSON completion envelope and NDJSON init/step/result events. |
| Schema | [Headless schema](https://www.antigravity.google/docs/cli/headless/#structured-output-with-a-schema) | `--json-schema`; enforced schema and `structured_output` in terminal result; independently validate. |
| Models / effort | [Headless selection](https://www.antigravity.google/docs/cli/headless/#select-a-model-effort-or-agent) | `agy models`, explicit slug, `--effort`; unknown selection fails rather than silently switching. |
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

Static inspection also identifies ADC and LLM gateway environment overrides;
they will be excluded conservatively. This is configuration inspection, not an
alternative transport or permission to invoke private endpoints.

## OpenAI recheck

- [Official self-hosted VMs](https://developers.openai.com/siwc/token-sharing-open-source/self-hosted-vms):
  complete OAuth locally, transfer this tool's protected selected registration
  using SSH, preserve the separately created VM host ID, then let the VM refresh.
- [Registration/sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
  and [accounts/sessions](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
  remain the existing OAuth protocol contract; re-open them before any auth change.

SSH loopback forwarding is an optional deployment alternative and must not be
represented as the official OpenAI self-hosted workflow.
