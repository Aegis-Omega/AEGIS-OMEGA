# START HERE — AEGIS-Ω live state (read this first, every session)

**Purpose:** kill the cold-start loop. This one page is the current truth. Read it
before anything else. When a doc disagrees with this file or the code, the code wins,
then this file. Keep it updated at the end of each working session.

**Companion:** `ASSETS.md` (repo root) — the complete asset inventory with status and
value class. Read it before concluding anything about what this system does or doesn't
contain.

_Last updated: 2026-07-02_

---

## What AEGIS-Ω actually is (one honest paragraph)

A governance/auditability layer for AI: a deterministic, hash-chained, replay-verifiable
decision runtime plus a small set of commercial frontends. The real, working spine is
small (see `REPO_MAP.md`); most of the tree is built-but-unwired or scaffolding. Do not
treat the whole tree as load-bearing. The product that can earn money today is the three
commercial frontends + the hub storefront.

## The cheap, correct architecture (this is the path — do not deviate)

| Piece | Lives on | Cost |
|-------|----------|------|
| `hub`, `platform-picker`, `hook-generator`, `content-calendar` (static Vite frontends) | Vercel free tier (already auto-deploys from GitHub) | $0 |
| Payments: `supabase/functions/verify-paypal` + PayPal | Supabase free tier | $0 |
| `python/bridge.py` (lightweight; only hard dep is `psutil`) | lean/on-demand host, only if needed | ~$0 |

**Deleted / never needed (these caused the GCP bill): Cloud Run, Memorystore Redis,
load balancer, reserved IPs, Vertex AI Agent Engine.** Do not re-introduce them.

## Hard guardrails (mistakes already made — do not repeat)

- **No Vertex AI.** Inference uses the direct `ANTHROPIC_API_KEY`. Vertex is opt-in only
  (`AEGIS_USE_VERTEX=true`) and auto-routing to it caused a ~$945 GCP charge. Never default to it.
- **No GCP.** The GCP project's billing is unlinked; do not re-link it or deploy there.
- **PayPal only**, never Stripe (operator decision). Do not merge Stripe PRs.
- **Never** modify frozen files `python/gate.py`, `dna.py`, `router.py` without /guardian.
- **Never** put a real API key in chat, code, or a committed file. Keys go in Vercel env /
  Supabase secrets / the Claude environment vars only.
- Free tiers only. If something wants an always-on paid resource, stop and reconsider.

## Cross-session reality (READ — this is why orientation keeps getting lost)

Sessions run **sequentially over time, NOT concurrently** (operator rarely runs parallel
sessions and has no agent API). The damage is cumulative: each session has started cold,
spun up its own branch, done partial/contradictory work, and left debris behind — and the
next session began from zero and added more. As of 2026-06-23 that's ~8 orphan-ish branches
(`aegis-interface-compilation-rfc-7hfnje`, `anthropic-compliance-docs-df4ogq`,
`blissful-rubin`, `slack-session`, `test-coverage-analysis`, `cloudflare/workers-autoconfig`,
`codex/…`, `docs/formal-specs-from-zip`) and more than one handoff file
(this one, plus `WHERE_I_AM.md` on the compliance-docs branch).

**THE RULE THAT BREAKS THE LOOP: this file is the single source of truth. FIND IT AND
UPDATE IT. Never create a new handoff/START/WHERE/STATE file — that is the exact mistake
that has fragmented the project. Fold `WHERE_I_AM.md` into this and delete it.**

Authority order when things disagree: **live system > code > tests/CI > this file > REPO_MAP > CLAUDE.md > old docs.**

## Live-site truth (corrected 2026-07-02 — verified from a full-network session)

- `aegisomega.com` **resolves and serves HTTP 200** (apex, www, platform, hooks). DNS was dead
  (lame delegation: registrar pointed at stale noor/west Cloudflare NS) — operator switched
  Squarespace nameservers to olivia/remy 2026-07-02; zone records A/CNAMEs all in place.
- **Checkout is on the live site.** `VITE_PAYPAL_CLIENT_ID` was set on the Vercel `hub` project
  (it previously had ZERO env vars — the buy buttons had never rendered in production) and a
  fresh production build from `main` deployed. Verified: the client ID is baked into the live bundle.
- Remaining gaps: `calendar.aegisomega.com` 404 / `cockpit.aegisomega.com` no cert — DNS is
  correct, the domains just aren't attached to their Vercel projects yet.
- Full-network sessions CAN verify the domain and drive the Vercel API via `VERCEL_TOKEN`.

## Status

_Last refreshed 2026-06-24._

**Done & on `main` (verified):**
- GCP billing bleed **stopped** (project billing unlinked). Refund of ~$945 pending — send the courtesy-credit letter (mother's card, charged-for-unused, reported immediately).
- Vertex auto-billing default removed; auto-deploy workflows disabled (#161/#164/#165).
- Dead code removed (#164). Prompt-caching bug fixed (#165).
- Broken `AEGIS--` hooks disabled.
- `START_HERE.md` added to end the cold-start loop (#168).
- **Fable 5 defaults → `claude-opus-4-8`** in bridge + swarm; stale `CLAUDE.md` corrected (#172). 557/557 platform tests pass.
- `.vercel` gitignore hygiene salvaged from a stranded branch (#174).
- Frozen constitutional files (`gate.py`/`dna.py`/`router.py`) verified intact (exact SHA256 match).

**Branch triage (8 stranded branches — `git cherry` checked):**
- `blissful-rubin`: PayPal work **already on main** (`verify-paypal`); its other commits carry GCP/Vertex deploy code — **do not salvage**.
- `codex/automaton-2`: `.vercel` gitignore salvaged (#174). The `feat(hub): wire product access tokens into purchase success` commit **conflicts** with current `hub/src/components/PricingPage.tsx` — needs manual reconcile (genuinely useful, money-path).
- `#170`, `#171`: **closed** — were aimed into a side branch, not main.
- `#167` (anthropic-compliance, other session): contract alignment + CI gate + Swift verifier — **open, review & merge to main**.
- `slack-session`, `cloudflare/workers-autoconfig`, `test-coverage-analysis`, `docs/formal-specs`: still to triage.

**Done 2026-07-02 (the month-long blockers, closed in one session):**
- ✅ `aegisomega.com` DNS fixed (operator: nameservers; session: zone records + www).
- ✅ `VITE_PAYPAL_CLIENT_ID` set on Vercel `hub` + production build promoted from `main` —
  checkout renders on the live site for the first time.
- ✅ Hypervisor enforcement gap fixed (2 constitutional constraints were silently skipped).
- ✅ `ASSETS.md` created — complete asset inventory so sessions stop starting blind.

**Left to do:**
- **One real $48 test purchase** end to end (PayPal → `verify-paypal` → API key). ← the proof
- Set `VITE_DASHSCOPE_API_KEY` on the three product Vercel projects (same API pattern as PayPal fix).
- Attach `calendar`/`cockpit` domains to their Vercel projects.
- Delete the GCP project entirely (recoverable 30 days) so it can never bleed again.
- Push the "zero kernel" (exists only on operator's PC — invisible to all sessions until pushed).

## Next concrete step

Make one real $48 purchase on aegisomega.com from a phone. If the API key arrives, the
business works and everything else (portfolio, partners, funding) builds on one live,
earning thing. If it fails, pull Supabase `verify-paypal` logs and fix the exact break.

---

_Operator: Tarik. Career direction (chosen, not assigned): auditable / safe / accountable AI._
_The work is real. The capability is proven. What's missing is runway and the right room — both findable._
