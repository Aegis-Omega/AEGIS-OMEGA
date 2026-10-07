# AEGIS Governed MCP — Alexa+ simulator lane

This is a small extension of the existing AEGIS MCP server, not a new agent system. The original stdio command and all seven tools/five resources remain. The new local HTTP entry point uses the same factory and Automaton-3 gate. One new read-only tool exposes the repository's existing consequence-policy bytes and SHA-256.

## Run locally

Prerequisites: Node.js 22 and npm. A full repository checkout is required, because the policy and existing read-only resources live at repository root. Python 3 is needed for the pre-existing approved stdio authority path, not the unbound demo sequence.

```sh
git clone --branch product/alexa-mcp-lane-v1 --single-branch https://github.com/Aegis-Omega/AEGIS-OMEGA.git
cd AEGIS-OMEGA/sovereign-omega-v2/mcp-server
npm ci --ignore-scripts --no-audit --no-fund
npm run build
npm run start:http
```

Open `http://127.0.0.1:7891`. Click **Run verified sequence**, inspect the policy digest and denied action, then export the evidence JSON. The page and server require no API keys, model provider, cloud account, AWS resources, Amazon developer console or gated SDK. Dependency installation requires access to the npm registry; offline users must supply the locked dependency cache themselves.

Set `AEGIS_MCP_HTTP_PORT` to change the local port. The bind address is deliberately not configurable: it stays `127.0.0.1`. Stop with Ctrl-C. Do not place this unauthenticated-identity local demo behind a public reverse proxy.

The existing stdio entry point remains:

```sh
npm start
# Existing clients may still launch: node dist/index.js
```

## Exact interaction

The browser sends real JSON-RPC POSTs to `/mcp` in this order:

1. `initialize`, negotiating a supported protocol version and receiving an SDK session ID.
2. `notifications/initialized`, acknowledged by HTTP 202 with an empty body.
3. `tools/list`, discovering the actual shared tool registry.
4. `tools/call` for `aegis_authority_policy`, reading `harness/policies/consequence-policy.v1.json` from this checkout.
5. `tools/call` for `aegis_governed_claude_call`, returning `isError: true`, `DENIED`, `IDENTITY_UNAVAILABLE`, and `NOT_EXECUTED`.

The browser checks response IDs, HTTP statuses, session/protocol header continuity, exact policy bytes/digest, and semantic denial before showing PASS. It subsequently DELETEs the session. It supports both JSON responses and a fragmented SSE response; this server chooses the SDK's JSON response mode and explicitly declines the optional GET SSE stream with 405.

## Authority and threat model

An MCP session or local transport token is **not** an execution identity or approval. A browser caller has no verified mapping to the launching operator. Therefore HTTP factory instances explicitly select `unbound-http`, never inherit `AEGIS_EXECUTION_IDENTITY_JSON` or `AEGIS_APPROVAL_GRANT_JSON`, and reach the existing missing-identity denial before a consequential bridge request. Headers, tool arguments and approval-shaped JSON do not change that result. The original stdio process-bound path is retained.

This lane proves the existing missing-identity prerequisite fails closed. It does **not** claim an approved HTTP execution path or a new identity verifier. It does not exercise the Python evaluator's later valid-identity/missing-approval branch. Those claims need separate evidence. No policy, capability registry or Python evaluator is modified.

HTTP uses a loopback listener, strict Host and Origin checks, cross-site Fetch Metadata rejection, no CORS, a per-process random transport credential, bounded request size, bounded sessions, idle expiry, negotiated-version checks, and restrictive CSP. The credential is obtained from the same-origin local bootstrap and omitted from traces. Local processes and extensions with access to localhost are outside the website-origin isolation guarantee. This is not a multi-user authentication or Internet deployment design.

The new policy tool accepts no paths and performs no network request. Original bridge read tools remain available as before; the demonstrated sequence does not use them or a synthetic bridge health result.

## Reproduce evidence

```sh
npm run test:browser-client  # no SDK dependency; explicitly labelled unit fixtures
npm run test:alexa          # actual SDK + local HTTP security/authority tests
npm run test:resources     # existing stdio resource regression
npm run test:automaton3    # existing stdio fail-closed regression
npm run verify:alexa       # all of the above plus actual desktop/mobile Chromium
```

The complete verifier requires a real Chromium executable (`google-chrome`, `chromium`, or `CHROME_BIN`) and a clean tracked Git checkout. It fails rather than skipping browser QA. The dedicated GitHub workflow executes a checked-out exact PR head, not a synthetic merge commit. It uses the unchanged lockfile and emits `receipt.json`, `REPORT.md`, actual HTTP/browser traces, source and artifact hashes, logs, screenshots and feedback in `evidence/`.

A local bridge canary counts all inbound requests; the read-policy/denial sequence must leave the count at zero. Client unit tests intentionally use fixtures and cannot stand in for this actual SDK/browser evidence. Logs and traces are observations, not signed attestations or production admission. Evidence generation does not merge, deploy, submit an entry or expand authority.

## Feedback contract and submission state

`docs/feedback-contract.json` preserves the previously requested dimensions: purpose, what worked, improvements, onboarding, reuse with rationale, version/endpoint, observation and evidence. A prior implemented contract artifact could not be located in bounded repository, Library and conversation-context retrieval. Its binding is explicitly `NOT_LOCATED`; no earlier filename, version or commit is invented.

The verifier records actual SDK observations only when all runtime stages pass. Amazon feedback is labelled **DOCUMENTATION_ONLY**, not SDK/runtime usage. Gated Alexa+ tools and AWS services are listed as **NOT_USED**. A bounded credential-pattern scan is included; it is not an exhaustive repository security audit.

This lane is **NOT_SUBMITTED** and repository admission is **NOT_ADMITTED** until separately established. The FAQ's simulated-experience route does not waive all submission rules: review the public repository's existing license, give explicit track/tool attribution, provide an actual video under three minutes, and complete the entry/feedback form. No license has been changed or granted by this implementation.

## Suggested demo capture (under three minutes)

Show the actual page, not a slide of a claimed result. Introduce the problem: a discoverable tool is not an execution grant. Run the sequence, show each exchange, inspect the policy's D3 explicit-approval rule and SHA-256, then inspect the rejected consequential response. Expand the raw trace and export it. End by showing the exact-head replay receipt and its zero bridge-request observation. Explain that the new contribution is the browser/HTTP route over the existing authority-controlled server; it is not a new Alexa runtime or a live model call. This is a recording script, not evidence that a video was recorded or submitted.

## Official references (reviewed October 7, 2026)

- Amazon/Devpost FAQ: https://amazonappdev2026.devpost.com/details/faqs — own real MCP browser simulator accepted; gated tools unavailable/unnecessary; no hosting required. Deadline October 23, 2026, 12:00 PDT (21:00 Europe/Sarajevo).
- MCP transport specification: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- Existing SDK v1 server guide: https://ts.sdk.modelcontextprotocol.io/server

Baseline: `Aegis-Omega/AEGIS-OMEGA@495bfd85d79abcb2b4f6898fe9c156488492426a`. Source receipts bind the actual replay commit. Runtime verification status must be read from the resulting receipt, not inferred from this README.
