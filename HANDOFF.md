# AEGIS-Ω — Handoff (ground truth as of 2026-06-14, 10:46 UTC)

A no-spin snapshot. Hand it to any engineer or AI and they're productive in 30 minutes.
Everything here was verified by probing live systems and running the tests, not read from docs.
Where a doc disagrees with the live system, the live system wins.

---

## LATEST — 2026-06-28 (verified against code + Drive this session; READ FIRST)

**Why this section exists:** to stop the operator re-pasting the whole corpus every cold
session. Everything below was checked against the actual tree or Drive on 2026-06-28 — not
trusted from a paste. Assumptions are labelled as such.

**The Drive corpus (so you don't ask him to re-upload it).** Owner `tarikskalic33@gmail.com`.
Key items found via the Drive MCP (`search_files`/`read_file_content`):
- `AEGIS_KNOWLEDGE_BRIEF.md` — the authoritative design brief (holons, Law of Silence,
  coherence gating, step-level verification, bounded blast radius; system-card discipline).
  THIS is the real "what we're working with"; treat it over any cross-model summary.
- Research-report PDFs: "AEGIS OMEGA v1.0 (Asymmetric Enforcement…)", "Civilizational
  Evolution Framework", "Constitutional Cognitive OS", "Deployment-Certifiable…",
  "MASTER SYNTHESIS (PART I OF III)".
- `Bisimulation/ThreeWay.v` (+ a `Core/JS/WASM/Python/Bridge/Theorems/iris/tlaplus/extraction`
  proof tree) — the 3-way cross-runtime determinism formalization.
- `export-Aegis-Omega-*.json` (3.7 MB) = a **GitHub Actions audit log** (CI job events),
  NOT a billing export. There is no GCP cost bomb in the exports.
- `Aegis Omega 2.0.zip` + handoff zips = full code snapshots (not yet diffed vs live tree).

**Verified architecture facts (measured, not quoted):** 258,784 LOC. `aegis-cl-psi` Rust =
**7,198** `#[test]`; `aegis-runtime` = 362; `sovereign-omega-v2/src` = 191 TS/TSX files
(mostly test-only per REPO_MAP). Full per-gate map = `sovereign-omega-v2/docs/TRACEABILITY.md`
(110 layers, Gates 1–210). The root `docs/TRACEABILITY.md` is a DIFFERENT doc (module/tier
register, not a stale stub) — both are real; don't "reconcile" them.

**Formal status (do not overstate):** `ThreeWay.v` is an `Axiom`, not a theorem — it ASSERTS
cross-runtime byte-equality over an abstract `nat` domain; the file itself says the real proof
(JSCert+WasmCert+Python semantics) is multi-year pending. Tier T3. Under the *real* encoders it
is currently FALSE because of the numeric seam below. Things were added after the June-8
snapshot — treat that .v as a north-star spec, not current truth.

**THE keystone open problem (one bug class, surfaces everywhere):** TS/JS uses **Q32.32**
fixed-point; Python `core_matrix.py` uses **Q16.16** (verified: `INT_SCALE`/`INT_SHIFT_BITS`,
`to_fixed`/`from_fixed` in `hardware_config.py`). Until that seam is frozen (shared width +
truncation + fold order), `encode_PY ≠ encode_JS`, so the bisimulation axiom can't hold and
cross-runtime replay diverges. Same class also seen as: left-vs-right fold (`Omega.tla`),
NFC/`ensure_ascii` canonicalization (fixed in `aegis-ccil-verifier`, still latent in bridge
audit hashes). **Closing the Q32.32↔Q16.16 boundary is the highest-leverage next proof/fix.**

**Cross-model "ground truth" blocks (Gemini/ChatGPT handoffs) are ~half-fabricated** — verified
2026-06-28: topology + the sqlite *schema* are real; the "deterministic fixture" hashes don't
exist (the kernel's `memory_store.sqlite` is empty — 0 rows), the GCS analytics "telemetry
fabric" (bucket/name/project/generation views) is generic GCP confabulation not in the repo,
and `residual_delta MUST be 0.0` is false (rule is `delta < delta_critical=0.70`). Do not
ingest those blocks as truth.

**Verified-real subsystems (were dismissed as "fiction" by cross-model handoffs; confirmed in code 2026-06-28):**
- **INT4 LUT-KAN** — `aegis-cl-psi/src/int4_lut_kan.rs` (Rust gate, SHA-256 chain, `verify_chain`) + Python
  port in `agents/cognitive_pipeline.py`. Rust↔Python byte-parity *independently reproduced*
  (`fingerprint_inputs([1,2,3])`=`887d1c02…`, `record_hash`=`218edd96…`); now guarded both sides
  (`agents/tests/test_lut_kan_parity.py`). This is the one concrete, holding instance of the
  ThreeWay bisimulation.
- **Ogemma/Gemma Mythos holon** — real + partly LIVE: `clients/gemma-edge-ios/` (Swift edge client),
  `clients/gemma-holon/` (ogemma_mythos.py, skills), and the deployed Worker endpoint
  `/platform/holon/validate` (holon_class GEMMA-4E4B).
- **φ-holographic** — real code (`aegis-cl-psi/src/gossip_broadcast_phi_holographic_e7.rs` gate +
  `studio/src/holographic-surface/` WebGPU surface). HONEST TIER: a φ-structured broadcast algorithm +
  holographic-style visualization — NOT literal optical/photonic hardware. Real implementation,
  metaphorical name.

**Bridge security (fixed + pushed this session, branch `claude/aegis-interface-compilation-rfc-7hfnje`):**
`/platform/executions` poll/delete now enforce per-owner scoping; registry bounded
(`_reap_executions_locked`, cap 1000); producer preserves the `email` tag through completion.
Commits `f4a779fa`, `386aaf28`. `/platform/executions/live` is intentionally id-as-capability
(EventSource can't send headers) — documented inline; don't "fix" it into breakage.

---

## LATEST — 2026-06-20 (read this first; older sections below are still mostly true)

**Merged since the 06-14 snapshot:**
- **PR #160 merged → `main`**: Gemma-4E4B holon + Ogemma Mythos gates (`clients/gemma-holon/`,
  Worker `/platform/holon/validate`), and `sovereign-omega-v2/scripts/mythos-pipeline.ts` made a
  proper time-inhomogeneous Markov chain — the reconciliation retry counter now lives in
  `SystemStateVector.reconciliation_retries` instead of a loop-local var (no hidden memory).
  Note: that branch had an *unrelated git history*; it was replanted onto main as one clean
  12-file commit to become mergeable.

**Open: PR #161** (branch `claude/aegis-interface-compilation-rfc-7hfnje`):
- `packages/aegis-interface/` — RFC 0001 WIT→IR→{Rust,TS,Python} compiler + equivalence gate;
  RFC 0005 schema-evolution/consensus (`evolution.py`, `consensus.py`, `versioned.py`).
- `packages/aegis-py/` client/async_client envelope-unwrap fixes; worker `/platform/collaborate`
  emits `{role,output}`.
- `hub/src/components/PricingPage.tsx` — PayPal Smart Buttons wired to `verify-paypal`.
- `hub` landing **de-noised** (removed full-screen particle canvas, on-text glows, watermark
  numbers; heading weights 800/900→700 because only 400/700 fonts load) + nav brand `NOUS`→`AEGIS-Ω`.
- `clients/gemma-holon/{huggingface_publish.py,local_model_client.py}`.

**Money path — current concrete blocker:** the PricingPage shows red *"set VITE_PAYPAL_CLIENT_ID"*
because that env var is **not set in the Vercel `hub` project**. Set it (PayPal **live** Client ID,
Production scope) → redeploy and the buttons render. Backend `verify-paypal` is live v5; also
confirm `PAYPAL_CLIENT_ID/SECRET` + `PAYPAL_MODE=live` in Supabase secrets.

**Hard constraints learned this session (stop relearning these):**
- This cloud sandbox **cannot load `aegisomega.com` or the Vercel previews** (network policy →
  `ECONNREFUSED`/000). So the site can't be visually QA'd from here — judge CSS on the Vercel
  **branch preview** or paste a **screenshot** (images *are* readable in-session).
- **GitGuardian** on the PRs is a persistent **false positive** (φ-digit `mockSecret` test fixture
  + a public cert-pin fingerprint), not a real leak — triage in the dashboard.
- The endless Vercel deploy comments are the §5 free-tier rebuild-spam, not failures.

**Open decision (website):** the landing is maximalist/"noisy"; operator wants it calmer. Pending
pick: targeted de-noise (started) vs full minimal rebuild. Needs a screenshot or a "rebuild" go.

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
