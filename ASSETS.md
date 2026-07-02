# ASSETS.md — the complete asset inventory

> **Read this before claiming the repo is "just" anything.** Every session that starts
> blind re-discovers slices of this system and wastes the operator's time. This file
> enumerates ALL of it, with status and value class. When you find an asset not listed
> here, add it — that's the maintenance contract.
>
> Status key: **LIVE** = serving in production · **REAL** = builds/tests green, not deployed
> · **STRANDED** = exists only on operator's PC, not pushed · **REFERENCE** = intelligence
> material, not redistributable.

---

## 1. Money path (LIVE as of 2026-07-02)

| Asset | Status | Notes |
|-------|--------|-------|
| `aegisomega.com` DNS + zone | LIVE | Cloudflare zone (olivia/remy NS), apex→Vercel 76.76.21.21, www/platform/hooks/calendar/cockpit CNAMEs |
| `hub/` storefront + PayPal checkout | LIVE | $48 operator / $498 sovereign / free explorer. `VITE_PAYPAL_CLIENT_ID` set on Vercel 2026-07-02 — buttons render |
| `supabase/functions/verify-paypal` | LIVE | Server-side API-key mint. Never re-add client-side minting |
| `platform-picker/`, `hook-generator/` | LIVE | platform.aegisomega.com / hooks.aegisomega.com serve 200 |
| `content-calendar/`, `cockpit/` | REAL | DNS correct; domains not yet attached to their Vercel projects (calendar 404, cockpit no cert) |
| **Unproven link** | — | No real end-to-end purchase has ever been executed. First $48 test purchase = first proof the business works |

## 2. Governance runtime spine (the deep moat)

| Asset | Status | Notes |
|-------|--------|-------|
| `sovereign-omega-v2/src` TS runtime | REAL | 4,076 tests. RFC 8785 canonical hashing, martingale certifier, φ-quorum consensus, replay kernel, metacognitive loop |
| `sovereign-omega-v2/python` bridge | LIVE | Cloud Run `aegis-vertex` (europe-west3). 39-dept swarm `/platform/collaborate`, SSE executions, prompt caching |
| `aegis-cl-psi/` Rust CL-Ψ engine | REAL | 7,178 tests, 422 gate modules, EU-AI-Act-oriented inference gates |
| `aegis-runtime/` Seven-Pillar runtime | REAL | 133 tests |
| `src/hypervisor` Gate 206 crate | REAL | Constitutional hypervisor; all 5 constraints enforced (fixed 2026-07-02), 17 tests |
| `packages/aegis-interface` + `aegis-ccil-verifier/` | REAL | CCIL v5: WIT→IR→{Rust,TS,Python} compiler + cross-language signature verifier |
| `crates/constitutional-substrate` | REAL | Compiles + tests; standalone, not in CI |
| Frozen constitutional files | LIVE | `gate.py`/`dna.py`/`router.py` SHA-pinned; `verify-hashes.mjs` must exit 0 |

## 3. Novel demos (nothing else in the ecosystem has these)

| Asset | Status | Notes |
|-------|--------|-------|
| **Ogemma Mythos** `clients/gemma-holon/` | LIVE (partly) | iPhone-local Gemma-4E4B holds *veto power* over the cloud MYTHOS pipeline via 3 bio-state gates; Worker endpoint `/platform/holon/validate` deployed. Launch-story material |
| `clients/gemma-edge-ios/` Swift package | REAL | Fail-closed edge verifier (KhattLoopValidation, GemmaEdgeRunner) with tests; CI runs `Analyze (swift)` |
| INT4 LUT-KAN | REAL | `aegis-cl-psi/src/lut_kan.rs` + Python parity test — cross-runtime deterministic quantized inference |
| φ-holographic broadcast + WebGPU surface | REAL | `gossip_broadcast_phi_holographic_e7.rs` + `studio/` + `aegisomega-webgpu/` (σ/ρ/λ Φ-field frame graph). Metaphorical name, real code |
| `clients/` polyglot SDK set | REAL | Python, Go, shell, Google Sheets (`Code.gs` + sidebar), **brainfuck** (yes, a working brainfuck client — API-simplicity flex) |
| `hub/` in-browser MetacognitiveLoop | LIVE | Hash-chained self-observation running client-side on the landing page |
| Stochastic Logic Engine `clients/gemma-holon/skills/stochastic-engine.md` | REAL | Reverse-engineered anti-attractor system prompt (time-inhomogeneous Markov framing) with measured effect: Gemma-3-1B held ~640 coherent tokens at 51 tok/s vs. repetition-collapse without it |
| `.claude/metacog/*.mjs` session constitution | LIVE (repaired 2026-07-02) | 797 lines, dependency-free Node: hash chain mirroring `loop.ts`, martingale certifier, replay gate, quorum, agent-mesh ledger — wired into 5 lifecycle hooks. The dev harness is governed by the same law as the product. Had been silently dead since the repo moved (hardcoded `/home/user/AEGIS--` paths) |

## 4. Partner / compliance arsenal

| Asset | Status | Notes |
|-------|--------|-------|
| `docs/ANTHROPIC_PARTNERSHIP_BRIEF.md` | REAL | The Mythos alignment-gap pitch + runnable proof |
| 17 Anthropic trust-center docs → skills | REAL | Encoded in-repo (commit a210c485); originals in Drive "Anthropic Resources" — **REFERENCE only, never redistribute** |
| `scripts/proof-demo.sh` | REAL | One command, six constitutional proofs — the demo to send anyone |
| EU AI Act Article 12 orientation | REAL | Replay-verifiable audit trails = the downstream-provider documentation gap Anthropic's own forms leave open |
| CI CEREMONY quorum gate | LIVE | 6-job BFT quorum at 1/φ — a working demonstration of the consensus math governing its own repo |

## 5. Ops / observability

| Asset | Status | Notes |
|-------|--------|-------|
| `tactical/` 39-dept dashboard | REAL | Wired to bridge `/platform/*`; no deploy config |
| `studio/`, `cockpit/` | REAL | Projection-only observability + telemetry chat UI |
| `.claude/` skills (60+) + metacog hooks | LIVE | Session governance loop: gates, seals, drift-check, frozen-file guard |
| `vertex/serve.py` + `harness/` | LIVE | FastAPI constitutional proxy + skill harness (Cloud Run) |
| `terraform/`, `backend/`, `enterprise/`, `sovereign-mesh/`, `paperclip/`, `agents/`, `alignment/`, `security/` | REAL/dormant | Built, not wired — see REPO_MAP.md §2 |

## 6. Known STRANDED on operator's PC (not in repo, not on Drive)

| Asset | Action |
|-------|--------|
| **"Zero kernel"** | Named by operator 2026-07-02; not found under any matching name in repo or Drive. Push it or provide the path — until then it does not exist for any session |
| PC repo delta (~352k lines locally vs. remote) | Anything not pushed is invisible to every session. `git push` is the only cure |

## 7. Value conversion map (what turns which asset into what)

| Goal | Asset | The one next action |
|------|-------|---------------------|
| **Money now** | Money path (§1) | One real $48 test purchase end-to-end; then attach calendar/cockpit domains |
| **Money weeks** | Determinism engine (§2) | Extract "hash-chained replayable agent audit log" as a 5-min-quickstart package; launch on HN/r/LocalLLaMA |
| **Partners** | §4 arsenal + Ogemma demo | One well-aimed email to Anthropic partnerships citing their downstream-provider form gap, with proof-demo.sh attached |
| **Credibility** | §2 + §3 | Publish Ogemma Mythos as the flagship demo ("a phone vetoes the cloud") |
| **Status** | All | Receipts from the three rows above; nothing else generates it |
