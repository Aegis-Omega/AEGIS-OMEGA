# AEGIS Ω — Paid Invocation Gate / Candidate Repair

## Scope
Closes the unauthenticated provider-spend path in `worker-src/index.ts` before `/platform/collaborate` can call Anthropic. Does not deploy, activate billing, read live secrets, or send a paid inference request.

**Required dependencies:** Existing `public.api_key_store` table and new `public.reserve_aegis_edge_collaboration` SQL RPC migration. Worker secret settings: `ANTHROPIC_API_KEY`, `SUPABASE_URL` (HTTPS), `SUPABASE_SERVICE_ROLE_KEY`. If anything is missing, deny. Never expose service role secret to the browser.

## Behavior
- Public GET `/platform/status`, `/health` remain anonymous; protected POST `/platform/collaborate` requires a correctly shaped AEGIS API key and atomically available quota.
- Browser CORS allowlist: `https://aegisomega.com`, `https://www.aegisomega.com`. CLI without Origin can authenticate. Origin is **not** authentication.
- Reject invalid bodies, unsupported modes or `live:false` **before any quota reservation**. The worker has no demo execution implementation; pretending otherwise causes unintended paid inference.
- Quota reservation occurs **before the provider call**. Reserved quota is conservatively consumed even if the provider subsequently fails. No automatic refund in v1; pricing/docs must disclose this before launch.
- SQL update uses a row-locking atomic `UPDATE ... RETURNING` to prevent concurrent overdraw of a finite remaining quota.
- RPC malformed result, outage or missing secret → 503; invalid/revoked/depleted key → 403. Unknown origin → 403. Never return secrets/upstream exception bodies.
- `/platform/executions` fake-pending stub should return `501 NOT_IMPLEMENTED` rather than fabricating an execution.

## Verification
Run `node --experimental-strip-types --test tests/invocation-gate.test.mjs` using Node 22+, then `tsc --noEmit ...` for the integration. Re-run exact-head build and check the SQL on isolated staging DB before merge.

## Still open
- Staging integration with actual Supabase service role and schema is **NOT TESTED**.
- Daily rate and provider-spend hard cap beyond the per-key cumulative quota is **NOT IMPLEMENTED**; Cloudflare/DB-enforced rate and cost policy required for a public rollout.
- No provider token metering, automatic refunds, idempotent retry ledger, or abuse anomaly detection in this patch.
- Do **not** deploy SQL or enable Worker secret until reviewed and approved. This is **NOT_ADMITTED**.