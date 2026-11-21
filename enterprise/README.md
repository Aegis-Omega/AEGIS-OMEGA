# AEGIS Enterprise

The dashboard consumes read-only telemetry routes from the AEGIS bridge. The Vite build uses `VITE_BRIDGE_URL` as the browser-visible bridge address. Keep provider keys in server-side configuration.

## Staging preflight

From the repository root, with Node.js 22.12 or newer:

```sh
node enterprise/check-bridge.mjs https://bridge.example.com https://enterprise.example.com
cd enterprise
npm ci
VITE_BRIDGE_URL=https://bridge.example.com npm run build
```

Substitute the actual staging URLs. The bridge check exercises seven dashboard routes, verifies the node hash against the returned fields, and checks CORS when the dashboard origin is supplied. A pass records route compatibility at that time. The bridge's `/network` route includes synthetic peers, and several dashboard panels use fixtures. Keep both out of customer production evidence. Restrict staging access before connecting any customer telemetry.

## Reproduce synthetic pilot evidence

From the repository root, run the fixture and then verify its receipt against the same checked-out source:

```sh
revision=$(git rev-parse HEAD)
node enterprise/pilot-receipt.mjs run "$revision" > pilot-receipt.json
node enterprise/pilot-receipt.mjs verify "$revision" pilot-receipt.json
```

The fixture checks that seven dashboard routes are accepted and that a synthetic HTTP 401 is reported when the node route is withheld. The receipt contains the supplied commit, source and fixture hashes, route results, and a checksum. The verifier replays the fixture and rejects changed receipts. The run makes zero external requests and incurs zero model charges. Use an independently checked-out revision to verify the evidence. Hosted authentication and OpenAI inference require separate staging evidence.

## OpenAI Services Technical Assessment

For the Services assessment, document how AEGIS scopes a customer workflow, governs AI and tool access, tests changes, obtains release approval, and measures results. The enterprise preflight can support the engineering methodology with a reproducible example.

The optional OpenAI Chat Completions provider in [the Supabase chat function](../supabase/functions/chat/index.ts) is an existing integration point. The enterprise dashboard reads bridge telemetry. A staging demonstration can exercise an authenticated OpenAI request using synthetic data, record model and request provenance, and show an audit artifact that an independent verifier can check. Record the source revision and the verification results.

For the assessment's delivery-history fields, use confirmed deployments and measured outcomes with permission to share. Label internal demos and pilots according to their actual scope. List issued credentials and certifications with verifiable records.

[Partner onboarding](https://partners.openai.com/onboarding) · [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices) · [API data controls](https://developers.openai.com/api/docs/guides/your-data)
