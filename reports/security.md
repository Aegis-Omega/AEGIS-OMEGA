# Security Audit — AEGIS-OMEGA

Generated 2026-07-12 by repository audit (session), from commit `a0a74ac6f1c98dd72d4dde8837d2ec0efe4c7849`.
Every finding below was verified against the code at the cited file:line this session.

## Findings

### S-01 · CRITICAL — dev-bypass authentication accepts any `aegis_`-prefixed key
**Where:** `sovereign-omega-v2/python/platform_helpers.py:267-271` (and a second instance
at :590-610 for plan/limit lookup).
When `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` are unset, **any** API key starting with
`aegis_` authenticates as `dev@local` / `explorer`. If the bridge ever ships or restarts
without those env vars (misconfigured revision, new environment), the paid API is open.
**Remediation:** gate the bypass behind an explicit `AEGIS_DEV_AUTH=1` opt-in and refuse to
serve `/platform/*` in its absence, rather than keying the bypass off missing config.

### S-02 · HIGH — CORS wildcard on the bridge
**Where:** `sovereign-omega-v2/python/bridge.py:1778-1781` (`_cors_headers` sends
`Access-Control-Allow-Origin: *`, allowing `x-api-key` from any origin).
Any website can drive a visitor's browser to call the bridge with a stolen/embedded key;
combined with S-01 it becomes unauthenticated cross-origin access.
**Remediation:** reflect an allowlist (aegisomega.com + localhost dev) instead of `*`.

### S-03 · HIGH — no rate limiting on bridge endpoints
**Where:** `sovereign-omega-v2/python/bridge.py` — no throttle on `/platform/*`, `/claude`,
or `/claude/stream`; the only quota is the per-key usage counter (and S-01 bypasses keys).
Model-backed endpoints translate directly into provider spend; unmetered abuse is a cost
and availability risk.
**Remediation:** per-key + per-IP token bucket in the handler (or front with Cloud Armor /
a rate-limiting proxy).

### S-04 · HIGH — secrets committed to `hub/cloudbuild.yaml`
**Where:** `hub/cloudbuild.yaml:10` (`VITE_GRANT_SECRET=aegis-omega-v1`) and `:14`
(Supabase anon JWT baked as a build arg; project URL at :12).
The anon key is semi-public by design, but committing it + the grant secret hard-codes
them into git history and the image build.
**Remediation:** move both to Cloud Build substitutions / Secret Manager; rotate
`VITE_GRANT_SECRET` (see S-05 — its fallback twin is also in source).

### S-05 · MEDIUM — legacy client-side token path with hardcoded fallback secret
**Where:** `packages/shared/lib/access.ts:1` (fallback secret `'aegis-omega-v1'`) and
`:53-60` (`sign()` — a 31×h non-cryptographic 32-bit hash, not HMAC), tokens persisted in
localStorage. Anyone reading the bundle can mint a `full`-plan grant token offline.
The P-256 server-issued path (`verifyServerToken`, :29-51) is the real control; the legacy
path weakens it for any component still accepting legacy grants.
**Remediation:** delete the legacy `createGrantToken`/`verifyGrantToken` path; accept only
P-256 server-issued tokens (CLAUDE.md already forbids re-introducing client-side minting).

### S-06 · MEDIUM — SECURITY.md was template boilerplate
**Where:** `SECURITY.md` (pre-audit) — GitHub sample text: fictional versions "5.1.x/4.0.x"
and a `security@example.com` reporting address, i.e. no working disclosure channel.
**Remediation:** replaced with a real policy in the follow-up docs commit (main-branch
support, GitHub private vulnerability reporting, 72h response target).

### S-07 · MEDIUM — no SSO/RBAC; authorization is a 3-tier plan gate only
**Where:** `sovereign-omega-v2/python/platform_helpers.py` (tier = explorer/operator/
sovereign is the entire authorization model; no roles, no org accounts, no per-user scoping
beyond the key's email tag).
Acceptable for a single-operator product; a blocker for team/enterprise use.
**Remediation:** treat as roadmap — introduce per-key scopes before any multi-seat offering.

### S-08 · MEDIUM — single-tenant, in-memory runtime state
**Where:** `sovereign-omega-v2/python/bridge.py` execution registry — in-process dict,
bounded to 1000 entries with per-owner scoping (HANDOFF.md, 2026-06-28 section); state
does not survive restart and does not shard across instances.
One Cloud Run instance = one tenant universe; a crash drops all execution results.
**Remediation:** documented limitation; persist executions (Supabase) if that guarantee matters.

### S-09 · LOW (largely remediated) — committed env file in git history
**Where:** `backend/.env.local` — was tracked; untracked by PR #181
("Stop tracking backend/.env.local (secret hygiene)", commit `4cdbd55`). The historical
blob remains in git history; its observed content is localhost host/port config —
**no provider keys observed in it**.
**Remediation:** none urgent; if the history blob ever matters, rewrite history or rotate.

## Positives (verified this session)

- **Atomic key verification** — `verify_and_increment_api_key` Supabase RPC
  (`platform_helpers.py:284` region) closes the TOCTOU race between usage check and increment.
- **Stripe webhook: constant-time HMAC + replay window** —
  `supabase/functions/verify-stripe/index.ts:22-53`: HMAC-SHA256 over `t.body`,
  XOR-accumulator constant-time compare, and a 300 s replay window
  (`STRIPE_REPLAY_WINDOW_SECONDS`, rejecting stale `t=`).
- **Server-side P-256 token issuance** — `supabase/functions/_shared/jwt.ts` signs; only the
  public JWK is embedded client-side (`packages/shared/lib/access.ts:22-26`).
- **PayPal amount floors server-side** — `verify-paypal/index.ts:18-22` rejects captures
  below tier floor ($48/$498 floors for the $49/$499 tiers).
- **Scanning in CI** — CodeQL (GitHub default setup, active), Dependabot (active),
  GitGuardian on PRs (HANDOFF.md; known φ-fixture false positive), osv-scanner + hadolint
  workflows present. Caveats: osv-scanner's last 30 runs are `startup_failure` and hadolint
  is `continue-on-error` — see `reports/ci.md`.
- **No plaintext provider keys in shipped bundles** — verified this session; model keys are
  server-side (e.g. the OpenAI path proxies via the `chat` edge function with the key in
  Supabase secrets, `packages/shared/lib/inference-router.ts:144-179`).
- **Frozen-file membrane** — `frozen-files.yml` + `verify-hashes.mjs` make constitutional
  file tampering CI-visible (the one hard-blocking CI gate).
