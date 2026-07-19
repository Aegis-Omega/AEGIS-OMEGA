# AEGIS-Ω — Handoff (ground truth as of 2026-07-19)

A no-spin snapshot. Hand it to any engineer or AI and they're productive in 30 minutes.
Everything here was verified by probing live systems and running the tests, not read from docs.
Where a doc disagrees with the live system, the live system wins.

---

## LATEST — 2026-07-19 (authoritative session handoff; READ FIRST)

Written so ANY next session (Claude or ChatGPT, with or without the transcript) can continue
without re-asking the operator for anything below. Facts verified against git + the GitHub API
on 2026-07-19, not trusted from memory.

### 1. Branch / PR state

- Branch **`claude/slack-session-yyw7h6`** was **rebased onto `main` @ `5770c1a`**
  (post-rebase head **`06a022f`**, pushed; local == origin verified). 25 commits on top of main.
- **PR #192** — OPEN, **not draft** (verified via API), base `main` @ `5770c1a`, head `06a022f`,
  `mergeable_state: unstable` (solely the experiment-admission check, see §3 below). Carries:
  - **Provenance envelope Phase 1**: ADR 0001, `sovereign-omega-v2/python/canonical_envelope.py`
    (`canon()` byte-parity with `verifiable/chain.py`), dual-emit in `bridge.py` (legacy hashes
    byte-identical), 11-vector TS↔Python digest-equivalence CI gate. Envelope `signature` field
    is a Phase 2 placeholder (Cloud KMS Ed25519).
  - **Opt-in inference backends**: governed OpenAI (`9cf88fd`) + Azure OpenAI/Foundry (`56255f5`) —
    both server-side-key-only via `supabase/functions/chat`, enabled only by explicit flag; chain
    stays CL-Ψ → OpenAI (opt-in) → Ollama → Claude → DashScope.
  - **Claims ledger**: `docs/claims.json` (**34 claims**, evidence-contract schema, per-claim
    `fails_if` predicates), `scripts/validate-claims.mjs` DAG validator, `claims-ledger.yml` CI
    (green on head).
  - **osv-scanner archaeology** (`4d90615`/`d035713`/`bd6aa4e`), **Kaggle Hallucination-Delta
    evidence lineage** (`6ccb889`/`2ecaeeb`, HD=|claimed−actual|, hash-pinned), sponsors claim
    hardening + FUNDING.yml (`37e775b`), plugin `marketplace.json` (`fe066d2`).
  - **2026-07-18/19 additions**:
    - Funnel fixes (`b691436`): discovery meta, pricing clarity, product linking (audit-driven).
    - **Paywall hole closed** (`245caa8`): no pre-payment client-side grant-token minting;
      `AccessGate` accepts **only P-256 server tokens** (`verifyServerToken`). The legacy
      `createGrantToken`/`verifyGrantToken` still exist in `packages/shared/lib/access.ts` but
      are referenced only by the lib + its tests — a cleanup commit is a follow-up, not a hole.
    - **verify-paypal mints `tool_token`** (`b8b4a0c`): P-256 server token for paid tiers,
      **fail-open** — if `GRANT_PRIVATE_KEY_JWK` is unset it logs and omits `tool_token`, still
      issuing the API key.
    - **Fable-era transition record** (`c145474`): `docs/transitions/2026-06-model-default.md` —
      swarm default was `claude-fable-5` 2026-06-10 (`4747755`, PR #148) → 2026-06-23 (`8305ec6`,
      PR #172); never the frontend default. Ledger **CLM-009 Verified/EQ-A**.
    - **CLM-206 Proposed/EQ-D** (`06a022f`): origin claim that the 4747755 transition was shaped
      by an upstream session that had ingested the Mythos model card. Promotion contract: requires
      recovery of that session transcript binding BOTH the ingestion and the authorship; operator
      attestation alone cannot promote. All recovered June sessions logged a different model.
- **Grace-fix resolution during rebase**: our original `6f0e60d` was superseded by main's **#211**
  (`935dc7a`). The rebase kept our commit as `bfdc7fa` carrying **only the 74-line regression
  tests** (`test_grace_rpc_dispatch` in `python/tests/test_platform.py`); the
  `platform_helpers.py` hunk dropped as already applied. Verified: the award loop lives in
  `award_graces_for_cycle` (`platform_helpers.py:1619`), RPC `…/rest/v1/rpc/award_grace`.

### 2. Main movement 2026-07-18/19 (merged by the ChatGPT agent)

- **#208** fix(ci): restore OSV scanner execution (osv v2.3.8)
- **#209** docs: operator-sovereign control plane (RFC 0001)
- **#210** feat(governance): Integration Ledger made commit-bound
- **#211** fix(runtime): grace-chain control flow restored
- **#212** feat(governance): operator-sovereignty contracts v1 (six records)
- **#213** feat(governance): experiment admission gate v0.1
- **#214** feat(scale-os): signed control-plane events v1 (five files; **Supabase migration NOT
  applied to the live project**)

### 3. OPEN COORDINATION POINT — experiment-admission gate vs PR #192 (do NOT resolve unilaterally)

`#213`'s `.github/workflows/experiment-admission.yml` runs `aegis / experiment-admission` on
**every** PR to main and DENIES unless the PR diff changes **exactly one**
`.aegis/experiments/*.json` plan. PR #192 changes zero → the check **fails on head `06a022f`**
(verified). Operator must pick one:
(a) confirm the check is not branch-protection-required and merge past the red X,
(b) path-filter the gate so docs/feature PRs without experiments are exempt, or
(c) give #192 a pinned experiment plan.
This is an operator/coordination decision — no session should resolve it unilaterally.

### 4. Key/token locations (operator-attested — STOP RE-ASKING)

The operator states **API keys and tokens are stored on their Google Drive**. A session with the
Drive MCP connected should retrieve needed credentials from Drive directly — and **NEVER commit
them**. Known needed (names only, no values):
- `GRANT_PRIVATE_KEY_JWK` — P-256 private JWK matching (or replacing — then update the embedded
  public key too) the public JWK in `packages/shared/lib/access.ts:22-26`. Set as a Supabase
  function secret, then redeploy `verify-paypal` (§6).
- PayPal **live** credentials (`PAYPAL_CLIENT_ID`/`PAYPAL_CLIENT_SECRET`) + confirm
  `PAYPAL_MODE=live` (function defaults to `sandbox`).
- `RESEND_API_KEY`.
- Supabase project: `rwehltdwpsncnwxzkwik`.

NDA Drive folder `1KUrECDCNH3oOxdwKsfxIybOEbhGLD12-`: may be referenced by ID only —
**never republish its content to the public repo**.

### 5. MCP / session-surface state

- This remote session ended with **only the GitHub MCP** connected (Supabase, Google Drive, and
  Cloudflare-adjacent servers disconnected mid-session).
- The operator's **mobile** connectors show Supabase (all tools "Always" — recommend flipping
  write tools to "Ask") and Google Drive (all "Always"). That is a **different surface**, not
  this environment.
- To make a coding session capable: **reconnect Drive + Supabase MCP in the session environment**.

### 6. Deployed-state gaps (revenue-critical — from the funnel audit + live probes)

- `aegis-vertex.aegisomega.com` = **NXDOMAIN**. Needs Cloudflare DNS record + Cloud Run domain
  mapping + a manual `workflow_dispatch` deploy (auto-deploy stays disabled for billing safety).
- The three tool subdomains (`platform.` / `hooks.` / `calendar.`) are **stale or deleted on
  Vercel** — attach them to the correct projects per `DEPLOY.md` (repo root).
- Deployed `verify-paypal` **predates** the `tool_token` commit (`b8b4a0c`) — redeploy after
  `GRANT_PRIVATE_KEY_JWK` is set.
- `PAYPAL_MODE` defaults to `sandbox` — verify `live` in Supabase secrets.
- **First-dollar gate**: one live **$49 self-purchase end-to-end**. Then: a real Explorer
  transcript as social proof → Stripe rail (payment links + webhook secret + env-gated button)
  → GitHub Sponsors enrollment last.

### 7. Governance / audit alignment

- The operator's **Scale OS control plane + Canonical Timeline + Request-to-Delivery Audit** docs
  (on Drive) do **NOT yet register PR #192 or the P0 paywall fix** — registration pending from a
  Drive-capable surface.
- Audit standard adopted: **"green previews are not production receipts."**
- **CP-001 finding**: persistence verified; **fail-open gates + broad connector authority** is
  the incident mechanism; fail-closed enforcement ("Automaton 2") is still **unbuilt**.

### 8. Next actions

**Operator-only:**
- Cloudflare DNS + Cloud Run mapping for `aegis-vertex` (§6) and Vercel project attachment for
  the three tool subdomains.
- Set Supabase secrets from Drive (§4), redeploy `verify-paypal`, confirm `PAYPAL_MODE=live`.
- Reconnect Drive + Supabase MCP for the next coding session (§5).
- Decide the experiment-admission handling for #192 (§3) and review/merge #192.

**Next-session (any capable agent):**
- Sweep the **June 1–10 session archives** for the fable-5 transcript to **promote or refute
  CLM-206** (promotion contract in `docs/claims.json`).
- Rank-6 demo / live-quickstart work.
- Stripe + Sponsors `tool_token` follow-ups (mirror the verify-paypal minting).
- Legacy grant-token cleanup commit (`createGrantToken`/`verifyGrantToken` + `GRANT_SECRET` in
  `packages/shared/lib/access.ts`, now unused by products).
- Register PR #192 + the P0 fix in the Scale OS docs once on a Drive-capable surface.

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
| Platform `aegis-vertex.aegisomega.com/platform/status` (Cloud Run) | ~~LIVE~~ **STALE — as of 2026-07-19 this hostname is NXDOMAIN** (see LATEST §6) |

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
- Active branch: `claude/slack-session-yyw7h6` (PR #192, rebased onto main `5770c1a`, head `06a022f`)
