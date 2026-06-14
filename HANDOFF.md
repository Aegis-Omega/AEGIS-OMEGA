# AEGIS-Ω — Handoff (ground truth as of 2026-06-14, 10:46 UTC)

A no-spin snapshot. Hand it to any engineer or AI and they're productive in 30 minutes.
Everything here was verified by probing live systems and running the tests, not read from docs.
Where a doc disagrees with the live system, the live system wins.

---

## 0. THE ONE THING THAT MATTERS RIGHT NOW

All the work below is **merged to `main`** (commit `a7cedc6`) and **verified green**. The single
thing standing between it and running in production is a **GCP Workload Identity (WIF) auth
misconfiguration** that has blocked every Cloud Run deploy for weeks — not just this work.
It is a ~5-minute fix on the GCP side (operator's credentials required; cannot be done from a
sandbox). **Do this first** — see §4.

Your **money path is NOT blocked by it** (§3).

---

## 1. What is DONE and merged to `main` (verified)

PR #156 merged → `main` (`a7cedc6`). Verified: Python contract suite **788/788**, autonomous
executor tests **18/18**, frozen-file membrane intact, PayPal kept (no Stripe).

- **Autonomous per-agent swarm** (the real one, not the single-call fake):
  `sovereign-omega-v2/python/platform_helpers.py` → `swarm_collaborate_autonomous()` +
  `make_autonomous_agent_call()`. Each department runs its **own** governed model call in
  dependency-layer order (research → revenue/product → marketing/sales/eng → finance/ops →
  executive → governance/constitutional), reading earlier layers' artifacts via the shared
  store — coordination only through that store (Law of Silence), bounded by `max_agents`.
  Tests: `python/tests/test_autonomous_swarm.py`.
- **Wired into the API**: `POST /platform/collaborate` and `/platform/executions` accept
  `{ "objective": "...", "mode": "gtm", "live": true, "autonomous": true, "max_agents": 10 }`.
  `max_agents` is the cost ceiling (= number of real model calls). Tier gate: operator/sovereign.
- **De-hardcoded the 39**: roster is dynamic; count is always derived; extend via
  `AEGIS_DEPARTMENTS_FILE` (JSON of id/role/category). Default stays 39 (contract intact).
- **White-screen bug FIXED**: the 3 tools shipped a blank page (two React copies bundled).
  Added `resolve.dedupe:['react','react-dom']` to each product's `vite.config.ts`. Proven by
  headless-browser render.
- **CI FIELD builds FIXED**: install `packages/shared` deps before each product build
  (`.github/workflows/ci.yml`). The 6 FIELD jobs went red→green.
- **Repo cleanup**: untracked 21,669 committed `node_modules`; removed editor/jupyter junk.
- **Docs**: `REPO_MAP.md`, `WORKFLOW.md`, `EXECUTION_PLAN.md`, anti-slop `CLAUDE.md`,
  `anthropic-alignment` skill + `references/docs-digest.md`.
- **Model pin**: `.claude/settings.json` → `"model": "claude-opus-4-8"` (Fable 5 was blocking
  the operator's app sessions — that's account-level entitlement, the repo pin may not override
  a session-bound model; use the app model picker if it still reverts).

---

## 2. What is LIVE in production right now (verified earlier this session)

| System | Status |
|--------|--------|
| Store `https://aegisomega.com` (hub, Vercel) | LIVE (200) |
| Payment fn `verify-paypal` (Supabase, project `rwehltdwpsncnwxzkwik`) | DEPLOYED v5, minted a real key in one call |
| Platform `aegis-vertex.aegisomega.com/platform/status` (Cloud Run) | LIVE, 39 agents, chain valid — **but running the OLD build** (new build can't deploy until §4) |

---

## 3. The money path (independent of the deploy blocker)

`hub` PricingPage → PayPal Smart Buttons → `supabase/functions/verify-paypal` captures the order,
checks amount vs tier floor ($48 Operator / $498 Sovereign), mints an `aegis_…` API key (free
**Explorer** provisions directly). hub is on Vercel, the function on Supabase — **neither touches
Cloud Run**, so payments work regardless of §4. Verify `PAYPAL_MODE=live` (not sandbox) in
Supabase secrets before expecting real money.

---

## 4. THE BLOCKER: fix the Cloud Run deploy (operator action, ~5 min)

`.github/workflows/deploy.yml` ("Deploy to Cloud Run", 6 jobs incl. **Bridge**) fails every run at
the GCP auth step: `"The given credential is rejected by the attribute condition."` The Workload
Identity provider in GCP is pinned to a repo identity that no longer matches (repo resolves as
`Aegis-Omega/AEGIS-OMEGA`). Not in the repo, not in terraform — it's GCP-side config.

```bash
# values: POOL + PROVIDER ids and SA_EMAIL live in GitHub → Settings → Secrets
#   (GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_SERVICE_ACCOUNT) or GCP → IAM → Workload Identity Federation
PROJECT_NUMBER=$(gcloud projects describe aegisomegav1 --format='value(projectNumber)')

# 1. inspect the current condition (confirms the stale repo pin)
gcloud iam workload-identity-pools providers describe <PROVIDER> \
  --project=aegisomegav1 --location=global --workload-identity-pool=<POOL> \
  --format='value(attributeCondition)'

# 2. point it at the current repo
gcloud iam workload-identity-pools providers update-oidc <PROVIDER> \
  --project=aegisomegav1 --location=global --workload-identity-pool=<POOL> \
  --attribute-condition="assertion.repository=='Aegis-Omega/AEGIS-OMEGA'"

# 3. fix the service-account binding
gcloud iam service-accounts add-iam-policy-binding <SA_EMAIL> \
  --project=aegisomegav1 --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/<POOL>/attribute.repository/Aegis-Omega/AEGIS-OMEGA"
```

Then re-run the failed "Deploy to Cloud Run" run → bridge deploys → **autonomous swarm goes live**.

---

## 5. Open items / decisions (not blockers)

- **PR #153 contains a Stripe swap — do NOT merge it.** Stripe can't onboard a Bosnia-based
  seller; PayPal works and is what's live. Take #153's SDK/tests if wanted, drop the Stripe parts.
- **Vercel free-tier deploy spam**: every push rebuilds all ~6 Vercel projects → hit the 100/day
  cap (24h cooldown). Fix: per-project "Ignored Build Step" so a project only builds when its own
  folder changed. Until then, Vercel prod deploys of the fixed tools may lag.
- **The 3 commercial tools (platform-picker/hook-generator/content-calendar)**: undecided
  keep-vs-remove (deleted/re-added ~15× across sessions). They build + render now. Operator call.
- **Generation needs network + a model key**: in a cloud sandbox the model host is blocked
  (Trusted network policy). The tools render but only *generate* where network is open (prod) and
  a key is set (`VITE_DASHSCOPE_API_KEY`, or route through `supabase/functions/chat`).

---

## 6. Fastest path to first revenue (unchanged, none of it needs §4)

1. One tool (recommend `hook-generator`). 2. Bake in YOUR key behind a server proxy with a hard
spend cap (so the buyer needs nothing and it can't become a runaway bill). 3. Confirm it renders +
generates on its live Vercel URL. 4. Point the PayPal Operator tier at it. 5. Put the link in front
of 50 people in one niche. The infra all exists; the work is wiring + telling people.

---

## 7. Pointers

- Map of repo: `REPO_MAP.md` · Operating loop: `WORKFLOW.md` · Plan: `EXECUTION_PLAN.md`
- Swarm: `sovereign-omega-v2/python/{platform_helpers.py,bridge.py}` · tests in `python/tests/`
- Money: `hub/src/components/PricingPage.tsx`, `supabase/functions/verify-paypal/index.ts`
- Session sense-organ: `bash scripts/ground-truth.sh`
- Active branch: `claude/anthropic-compliance-docs-df4ogq` (merged to main via #156)
