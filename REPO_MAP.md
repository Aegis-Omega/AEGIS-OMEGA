# AEGIS Repo Map — what's real, what's dead, what lies

**Why this exists:** the repo has ~40 top-level dirs and CLAUDE.md documents ~14. Holding
"where is what" in your head is what caused the burnout. This is the index. It was produced
by a full four-way inspection of all 1,649 real files (2026-06-13) and is the source of truth
when a doc and the code disagree — **the code wins; the docs are stale.**

Status key: **WIRED** = runs in prod / built / deployed / imported · **TESTED-ONLY** = real code,
only tests touch it · **DORMANT** = nothing references it · **BROKEN** = does not compile ·
**DEAD/DUP** = duplicate or orphaned, safe to consider removing.

---

## 1. What actually runs in production (the real spine)

| Area | What it is | Deploy |
|------|-----------|--------|
| `python/bridge.py` (+ 11 modules) | The governance/swarm/inference HTTP service — `/telemetry`, `/platform/*`, `/claude`, `/node` | Cloud Run `aegis-vertex`, europe-west3 (`sovereign-omega-v2/Dockerfile` ships **only** `python/`) |
| `vertex/serve.py` | FastAPI "constitutional-proxy" / `aegis-platform`; bundles `agents/` + `harness/` | `vertex/cloudbuild.yaml` |
| `aegis-cl-psi/` | Rust CL-Ψ engine — ~7,198 tests, CI-gated ≥6800 | `aegis-cl-psi/deploy/Dockerfile`; CI `ci.yml` |
| `aegis-runtime/` | Rust Seven-Pillar runtime | CI build+test |
| `harness/` (`skill_tree.json`) | Python skill harness; `agents/coordinator.py` reads/writes it; baked into vertex image | via vertex |
| `hub/` | **The storefront.** PayPal checkout → `supabase/functions/verify-paypal` → mints API key | Vercel + Cloud Run |
| `platform-picker/`, `hook-generator/`, `content-calendar/` | The 3 commercial tools; share `packages/shared` (`@shared`); `AccessGate` → hub PayPal | Cloud Run via `deploy.yml` |
| `packages/shared/` | Shared lib (access, constitutional-ai, inference-router, dashscope, AccessGate) | imported by the 3 tools |
| `tactical/` | Real 39-dept dashboard wired to bridge `/platform/*` | **no deploy config** (runs vs bridge) |
| `cockpit/`, `studio/` | Internal telemetry / observability dashboards | deployable, not monetized |
| `supabase/functions/` | Live: `verify-paypal` (payment), `agent`+`slack-events`+`notify` (ops), `chat` (Qwen) | Supabase edge |
| `.claude/` hooks + `metacog/` | The live governance loop (session-start, per-prompt chain, pre-commit Gate 8, seal) | local to Claude Code |
| CI | `ci.yml` (7-scale quorum), `frozen-files`, `osv-scanner`, `hadolint`; `deploy.yml` → Cloud Run | GitHub Actions |

**The one true money path:** `hub` PricingPage → PayPal → `verify-paypal` → API key. Tiers are
**$48 operator / $498 sovereign + free Explorer** — *not* "$19".

---

## 2. Built but not wired — the "97%" (TESTED-ONLY / DORMANT)

- **`sovereign-omega-v2/src/`: ~184 of 189 TS files never reach the running app.** `main.tsx` transitively uses only `components/` + `lib/telemetry.ts` (~5 files). Everything else — `core/`, `constitutional/`, `agents/`, `verifier/`, `consensus/`, `pipeline/`, `memory/`, `api/`, `compliance/`, `corpus-engine/`, etc. — is exercised only by the 250-file test suite.
- **`src/skill-harness/` (the SHA-256 skill transfer)** — tested-only. The bridge's `/catalog` serves a **hardcoded 3-item literal**, not this code.
- **`packages/kernel/`** (Rust) — orphaned workspace member; nothing depends on it.
- **`crates/constitutional-substrate/`** — compiles + has tests, but standalone, not in CI.
- **`terraform/`** — valid GCP IaC, but not automated (deploys go via `gcloud builds submit`).
- **`backend/`** — complete Express server, no CI/deploy/importer. ⚠ ships a committed `.env.local` (check for leaked secrets).
- **`agents/`, `paperclip/`, `sovereign-mesh/`, `state/`, `security/`, `alignment/`** — manual-run or doc-only; not in CI/deploy.
- **`enterprise/`** — React 19 dashboard that builds but is wired nowhere; duplicates studio/hub.

---

## 3. Broken — does not compile

- **`eccf/`** — Rust crate, syntax error + unresolved import. Won't build. The only live "ECCF" is a Python comment-marker stub in `sovereign-mesh`, unrelated to this crate.
- **`gcce/`** — Rust crate, borrow-after-move error. Won't build.
- **`src/hypervisor/*.rs`** — orphan Rust using `crate::hypervisor::…` with **no Cargo.toml anywhere above it**. Cannot compile in place.

---

## 4. Dead / duplicate — safe to consider removing

- **`frontend/`** = dead older duplicate of `tactical/` (Google Gemini, `MOCK_WEBHOOK_URL`, setTimeout simulation).
- **Gumroad path** = dead code: `packages/shared/components/LicenseGate.tsx` + `*/api/verify-license.ts` (all 3 tools) — **imported by nothing**.
- **Lemon Squeezy subsystem** = dormant: `supabase/functions/{ls-webhook,issue-token,restore-access}` + `scripts/gen-grant-keypair.mjs` — nothing calls them.
- **`.github/workflows/deploy-cloud-run.yml`** = no-op duplicate of `deploy.yml`; **`agent-dispatch.yml`** = no-op unless a repo var is set.
- **root `package.json`** named `aegis-tactical-dashboard` with `frontend`/`backend` workspaces = orphaned identity from a different app.
- **`studio/dist/`** = committed build artifact (shouldn't be tracked).
- Dormant scripts: `sync-readme.sh` (CLAUDE.md wrongly claims it's a hook), `check-frontend-build.sh`, `wire-custom-domain.sh`, `auto-gate.py`, `resonance_dashboard.js`, `review-copilot-worktree.ps1` (Windows, hardcoded path).

---

## 5. Contradictions to fix (docs lying to you — the burnout source)

| Topic | Live reality (code) | Docs that disagree |
|-------|--------------------|--------------------|
| **Payment provider** | **PayPal** (hub) + dead Gumroad (tools) | `DEPLOY.md` says Lemon Squeezy; `CONSTITUTIONAL_DECLARATION.md`/`README.md` say Gumroad $19; `CLAUDE.md` cites a `verify-payment` fn that doesn't exist (it's `verify-paypal`) |
| **Price** | $48 / $498 + free | docs say "$19 each" |
| **Deploy target** | Cloud Run (`deploy.yml`) | `CLAUDE.md`/`DEPLOY.md` say Vercel; `vercel.json` builds hub only |
| **GTM** | $19 tools still build & deploy | `GTM_ENGINEERING_SPEC.md` ordered them killed + Stripe SaaS — never done |
| **Region** | europe-west3 | `vertex/serve.py` header says us-central1 |
| **Frozen SHAs** | `CLAUDE.md` table | `main.tsx` displays different (stale) abbreviated SHAs |

---

## 6. Why sessions felt slow (not asked, but real)
The hooks are heavy: `post-write.sh` runs `npm run typecheck` after **every** `.ts` edit;
`pre-commit-gate.sh` runs full Gate 8 (test+typecheck+build) on **every** `git commit`. On an
8 GB box that's the likely source of sluggishness.

---

*This map is descriptive, not a change. Deletions/fixes in §3–5 await operator approval.*
