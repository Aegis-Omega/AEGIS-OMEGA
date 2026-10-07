# Public MCP evidence page — /labs/mcp

This is an isolated static evidence explorer inside the existing hub, not an Internet-exposed MCP server. The original local simulator and Automaton-3 boundary in PR #716 remain unchanged. No runtime dependency, API endpoint, model provider, secret, identity grant, AWS resource or new project is added.

## Public display versus live execution

`public/labs/mcp/` contains the exact original desktop trace, replay receipt and tool-feedback JSON from AEGIS source `897fa55556a639a04a67d25481b7a432af007d04`. These bytes were downloaded from witness run `37557084479`, artifact `11454608841`, archive SHA-256 `ad40d440e808c89967cf9fc369db7f0d62dc5962b09a75a13922b6a6be75ea56`. They are re-hosted to preserve them beyond the artifact's October 14 expiration. Original source and observation dates are displayed, never replaced with the current deployment time.

The verify button makes two fixed same-origin GET requests, with cookies omitted and redirects rejected. The page checks pinned artifact SHA-256 values, recorded source, six completed stages, five correlated protocol exchanges, policy bytes and the recorded missing-identity denial. Only then are exchange inspection and the tamper test enabled. A failed subsequent verification clears the preceding success state. The tamper test changes a copy and expects rejection; it never changes the archived files. Raw JSON is rendered with `textContent`, not HTML.

This is integrity checking against a pinned site snapshot, not a signed or site-independent attestation. It does not run MCP, contact localhost, call models, make an AWS request, grant execution authority, prove a valid-identity approval path or assert current Devpost submission status. The actual MCP browser simulator remains available in the original exact source for local reproduction.

## Scope and deployment

The only application additions are under `hub/public/labs/mcp`, with tests/documentation alongside. Root and hub Vercel configuration add the exact `/labs/mcp` route before the unchanged SPA fallback, with security/cache headers scoped to this path. Existing homepage source, MCP code, authority policies and capability registry are untouched.

The `preview/hub/mcp-evidence-v1` branch is excluded from the two unrelated platform-picker and hook-generator Git deployments using exact-branch `git.deploymentEnabled` entries. Other branches and main retain their prior settings. The existing hub project is the only intended preview target; no domain or production alias promotion is included.

At read time, `aegisomega.com` points to deployment `dpl_UCEPFLGhgBSmPKYJZBfkyLzHb41R`, source `d329eae1b15ad89bf38e38857e53de9151ed7b4c`. That differs from the source baseline for this lane. Do not promote the whole feature deployment over production merely to publish this path. A production path publication needs a separately verified release/routing decision that preserves that homepage.

## Reproduce

From a full checkout of this feature's exact head:

```sh
cd hub
node --test test/mcp-evidence.test.mjs test/mcp-routing.test.mjs
node test/verify-mcp-public.mjs
```

The second command requires Node.js 22+ and an installed Chromium (`google-chrome`, `chromium`, `chromium-browser` or `CHROME_BIN`). It fails rather than skipping a missing or policy-blocked browser. It starts only a static local test server, inspects desktop/mobile interaction, verifies no cross-origin page requests or MCP calls, checks the negative control and corrupt-download state reset, and emits screenshots, logs and source-bound JSON/Markdown receipts. Its static test server is not a claim to emulate every Vercel route; hosted path behavior requires separate deployment verification. The full hub build remains the existing Vercel build path.

The initial container browser was blocked by its administrator URL policy. That protection was not altered. Browser verification must use an allowed runner and must be reported separately from the already executed local Node unit tests.

## Feedback

The original `friction-log.json` is preserved byte-for-byte. It distinguishes MCP SDK execution from documentation-only Amazon feedback and records `prior_artifact_binding=NOT_LOCATED`. This static presentation adds no Amazon SDK/runtime use. Do not reclassify it as an Alexa execution or fabricate additional Amazon onboarding observations.

## References

- Original MCP source: https://github.com/Aegis-Omega/AEGIS-OMEGA/tree/897fa55556a639a04a67d25481b7a432af007d04/sovereign-omega-v2/mcp-server
- Original witness: https://github.com/tarikskalic33/formal-conjectures/actions/runs/37557084479
- Vercel routing: https://vercel.com/docs/project-configuration/vercel-json
- Exact-branch deployment controls: https://vercel.com/docs/project-configuration/git-configuration

Current implementation and publication status must be read from the latest delivery receipt, not inferred from this document.
