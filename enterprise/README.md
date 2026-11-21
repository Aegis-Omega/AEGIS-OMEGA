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

## OpenAI Partner Network preparation

Prepare for the Technology program with a demonstration of one AEGIS governance workflow backed by OpenAI. The optional OpenAI Chat Completions provider in [the Supabase chat function](../supabase/functions/chat/index.ts) is an existing integration point. The enterprise dashboard currently reads bridge telemetry. An end-to-end enterprise demonstration still needs to exercise an OpenAI request, capture the model and request provenance, and show an audit artifact that an independent verifier can check.

| Evidence | What to capture |
| --- | --- |
| Technical capability | A pinned build, an authenticated staging run using synthetic data, the audit artifact, verification output, and a test showing that a deliberately modified artifact fails verification. |
| Production controls | Separate OpenAI projects for staging and production, server-side credentials, per-project budgets, an explicit data retention configuration, and documented access limits and rollback. |
| Customer experience | A verified customer reference or clearly labeled pilot result, with measured outcomes and permission to share. |
| Company details | Verified legal name, website, business address, company size, partner type, and primary business contact. An authorized company representative reviews and accepts the applicable agreement. |

These are AEGIS deliverables for review. OpenAI evaluates the application. [Partner Network](https://openai.com/business/partners/), [Application form](https://partners.openai.com/partner-application), [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices), [API data controls](https://developers.openai.com/api/docs/guides/your-data).
