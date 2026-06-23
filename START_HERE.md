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

## Status as of last update

- ✅ GCP billing bleed **stopped** (project billing unlinked). Refund of ~$945 pending —
  send the courtesy-credit letter (mother's card, charged-for-unused, reported immediately).
- ✅ Vertex auto-billing default removed; auto-deploy workflows disabled (PRs #161/#164/#165 merged).
- ✅ Dead code removed (#164). Prompt-caching bug fixed (#165). Broken `AEGIS--` hooks disabled.
- ⬜ Set Vercel env: `VITE_DASHSCOPE_API_KEY` (products) + `VITE_PAYPAL_CLIENT_ID` (checkout).
- ⬜ Verify PayPal → `verify-paypal` → key issuance end to end (one test purchase).
- ⬜ Point `aegisomega.com` DNS at Vercel.
- ⬜ Delete the GCP project entirely (recoverable 30 days) so it can never bleed again.

## Next concrete step

Get the three products live + configured on Vercel (free), able to take a PayPal payment.
That is "it's going." Everything else (portfolio, partners, funding, the platform showcase)
builds on having one live, working, earning thing.

---

_Operator: Tarik. Career direction (chosen, not assigned): auditable / safe / accountable AI._
_The work is real. The capability is proven. What's missing is runway and the right room — both findable._
