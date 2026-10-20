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
- `/platform/executions` fake-pending stub now returns `501 NOT_IMPLEMENTED` rather than fabricating an execution.

## Verification
Run `npm run test:edge-invocation` (18 tests: admission plus injected paid-request handler) using Node 22+, then `tsc --noEmit ...` for the integration. Re-run exact-head build and check the SQL on isolated staging DB before merge.

- `worker-src/paidInvocation.ts` isolates the HTTP path for mock replay; model invocation is dependency-injected, and tests verify auth/validation happens before the provider. An explicit `live:false` responds 501 rather than charging.
- `runSwarm` counts actually returned artifacts, not a hard-coded 39 completions.
- Local isolated TypeScript checks PASS, 18/18 test cases PASS; full Worker and SQL staging replay remain unverified.

## Still open
- Staging integration with actual Supabase service role and schema is **NOT TESTED**.
- Daily rate and provider-spend hard cap beyond the per-key cumulative quota is **NOT IMPLEMENTED**; Cloudflare/DB-enforced rate and cost policy required for a public rollout.
- No provider token metering, automatic refunds, idempotent retry ledger, or abuse anomaly detection in this patch.
- Do **not** deploy SQL or enable Worker secret until reviewed and approved. This is **NOT_ADMITTED**.

## 2026-10-11 strict mode type repair

**Reproduced failure at the exact original source blob**
`6c7c6879024b5e257762bfb4bcf8000d49f6730d`: the
`!modes.includes(String(input.mode))` expression invokes coercion of
user-supplied JSON. With `mode: {"toString": null}`, Node raises
`TypeError: Cannot convert object to primitive value` before the
admission gate can return its documented 400. This is an input-handling
failure, **not** evidence of a paid provider call or quota spend.

**Repair:** check `typeof input.mode === 'string'` before checking the
allowlist; never coerce an object supplied by untrusted JSON. Candidate
implementation blob `d0e52d7eba023506bd85775d2ae656ccc13a2ac0`;
new negative regression blob `d99039c20fb71ab027035fc771a97ea1c8fa2cb5`;
the root `test:edge-invocation` command includes the new test.

**Executed local exact-blob replay:** pre-fix 1/2 tests failed with the
expected uncaught TypeError; post-fix **2/2 PASS** for malformed and
nonstring modes, with zero mock quota reservations/provider calls.
Source and test bytes each matched GitHub blob SHA. Isolated strict
TypeScript 5.8.3 check passed for patched `paidInvocation.ts`.

This is *not* a complete exact-head build or live credential/quota
exercise; existing 18 admission/provider tests and staging SQL
integration remain separate release requirements. No production
deployment, database migration, billing activation or authority change.


## 2026-10-11 complete exact-blob replay and CI coverage

The six exact GitHub file blobs (two Worker modules, three Node regression
files, and root `package.json`) were reconstructed byte-for-byte in a
dependency-free local replay. Under Node v22.16.0:

```bash
npm run test:edge-invocation # 20/20 PASS, process exit 0
tsc --noEmit --strict --target ES2022 --module esnext \
  --moduleResolution bundler --lib ES2022,DOM,DOM.Iterable \
  --skipLibCheck worker-src/paidInvocation.ts worker-src/invocationGate.ts # exit 0
```

The new workflow `.github/workflows/edge-paid-invocation.yml` (Git blob
`212ba9a80fc31f62e052bb58e9ab701a990b488f`) adds a source-triggered
exact-head Node 22 check for changes in the Worker, tests, root test script
and itself. It uses read-only repository permission and requests **no**
provider credentials, database secrets or paid inference; dependency-free
tests do not require installation or network.

**Hosted workflow is NOT PASS:** at first observed head
`4c6117adbc0599315ef1d28ce6f8df3b04cdf373` the
`Paid Invocation Admission` GitHub workflow run `38119538309` was
reported FAILURE with **zero reported job steps** (job `114411225391`).
No paid-source test failure is inferable from that result. Confirm runner
startup, account policy/billing and job logs before re-running or asserting
production readiness. Draft branch only; no deployment or authority change.
