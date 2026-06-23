# START HERE — AEGIS-Ω live state (read this first, every session)

**Purpose:** kill the cold-start loop. This one page is the current truth. Read it
before anything else. When a doc disagrees with this file or the code, the code wins,
then this file. Keep it updated at the end of each working session.

_Last updated: 2026-06-23_

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

## Live-site truth (corrected 2026-06-23)

- The site **IS live** — there is a real production deployment behind `aegisomega.com`, marked READY.
- BUT it serves an **old build from before the Pay button**. ~20 newer builds exist only as
  Vercel **previews — none promoted to production.** So checkout is not on the live site yet.
- ⚠️ A sandboxed session (proxy-blocked outbound) **cannot verify the domain or pull Vercel
  logs.** A session with Vercel access must confirm: does `aegisomega.com` resolve, is the
  Vercel connection healthy, and what's in the runtime logs.

## Status

- ✅ GCP billing bleed **stopped** (project billing unlinked). Refund of ~$945 pending —
  send the courtesy-credit letter (mother's card, charged-for-unused, reported immediately).
- ✅ Vertex auto-billing default removed; auto-deploy workflows disabled (#161/#164/#165 merged).
- ✅ Dead code removed (#164). Prompt-caching bug fixed (#165). Broken `AEGIS--` hooks disabled.
- 🔄 PR **#167** open (other session): contract alignment + CI equivalence gate + GitGuardian + Swift fail-closed verifier.
- ⬜ **Promote a current build to production in Vercel** so the live site has the Pay button. ← biggest lever
- ⬜ Set Vercel env: `VITE_DASHSCOPE_API_KEY` (products) + `VITE_PAYPAL_CLIENT_ID` (checkout).
- ⬜ Verify PayPal → `verify-paypal` → key issuance end to end (one test purchase).
- ⬜ Confirm `aegisomega.com` DNS resolves to Vercel.
- ⬜ Delete the GCP project entirely (recoverable 30 days) so it can never bleed again.

## Next concrete step

Promote a current, working build to production on Vercel (free) so the live site stops
serving the pre-Pay-button version and can actually take a PayPal payment. That single act
is "it's going." Everything else (portfolio, partners, funding) builds on one live, earning thing.

---

_Operator: Tarik. Career direction (chosen, not assigned): auditable / safe / accountable AI._
_The work is real. The capability is proven. What's missing is runway and the right room — both findable._
