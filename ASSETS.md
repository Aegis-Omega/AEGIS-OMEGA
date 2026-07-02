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

## 3b. Agent infrastructure (repeatedly misread as "noise" by past sessions — it is not)

| Asset | Status | Notes |
|-------|--------|-------|
| Agent memory fabric | REAL | `sovereign-omega-v2/src/agents/memory/agent-memory.ts`, `src/memory/`, `src/ide/workspace/WorkspaceMemoryGraph.ts`, memory-fabric composition tests, `docs/WORKSPACE_MEMORY_MODEL.md` — plus a live Supabase table (`migrations/20260607300000_swarm_memory.sql`). Agent memory logs are SIGNAL: they are the persistence layer of the swarm |
| `harness/skill_tree.json` + `harness/` | LIVE | 30KB versioned skill tree (genesis_seal, phase, doc_count); `agents/coordinator.py` reads/writes it; baked into the vertex Cloud Run image |
| `agents/` department engine | REAL | `cognitive_pipeline.py`, `coordinator.py`, `evolution.py`, `red_team.py`, `revenue_engine.py`, `tool_runner.py`, `register_vertex_adk.py`, `adaptive_lineage.json` — the Python multi-agent org behind the 39-dept swarm |
| `packages/aegis-py/` SDK + `aegis` CLI | REAL | `AegisClient`/`AsyncAegisClient`; `aegis status` / `aegis collaborate` against `/platform/*` |
| Model weights pipeline | REAL (weights external) | No weights in-repo (by design); `clients/gemma-holon/huggingface_publish.py` packages/publishes on-device Gemma holon models to HuggingFace |
| Cross-runtime determinism proof | REAL | Same math verified byte-identical across Rust/TS/Python/Swift (CCIL v5 equivalence gate, INT4 LUT-KAN parity test, Q16.16 shared scale) — the claim competitors can't make |

## 3c. The layer below the languages — and the layer outside the sessions

| Asset | Status | Notes |
|-------|--------|-------|
| **AEGIS binary wire protocol** (`0xE0E0`) | REAL | Hand-specified 64-byte MTU-aligned UDP frame (`aegis-runtime/src/gossip_emitter.rs` + `telemetry_emitter.rs`): magic bytes, node id, root-state pulses, semantic traversals, agent states α/β/γ, consensus score, network friction. Corruption-rejection tested; no tokio, raw `std::net::UdpSocket`. Plus `b"ALCE"` compaction headers in CL-Ψ. The swarm speaks its own byte-level protocol |
| **Out-of-session execution mesh** | LIVE | Built after sessions kept resetting — the system runs without any Claude session open: `supabase/functions/agent` (autonomous Claude agent with DB-query + notify tools), `slack-events` + `notify` (ops loop), Cloudflare Worker `aegisomega.workers.dev` (direct `/platform/collaborate` + holon validate), CEREMONY BFT quorum in GitHub Actions, `.claude/metacog` lifecycle chain (repaired 2026-07-02) |
| Mobile control rig `clients/gemma-holon/quantum/server.py` | REAL | Phone-driven Flask dashboard made to run in a GitHub Codespace: job queue, simulated holon gate transitions, continuous purity checks, PennyLane 4-qubit device. HONEST TIER: the quantum circuit is a *simulator* (T2/T3), the control rig itself is real |

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

## 7. The deep layer — all 35 subsystems under `sovereign-omega-v2/src/`

Exercised by the 4,000+ test suite (TESTED-ONLY per REPO_MAP §2 unless noted). Descriptions
from each subsystem's own file headers. **The operator does not need to remember these — this
table is the memory.**

| Subsystem | Files | What it is |
|-----------|-------|------------|
| `skill-harness/` | 17 | SkillCatalog + SHA-256 skill transfer records |
| `ledger/` | 16 | Blockchain: ordered CommittedBlock sequence |
| `frame/` | 14 | Adaptive Lineage — hash-chained capability evolution |
| `constitutional/` | 13 | Martingale certifier, reduction (T4/T5 blocker), law enforcement |
| `core/` | 12 | RFC 8785 canonicalization, branded types, deepFreeze |
| `agents/` | 11 | Agent runtime incl. `memory/agent-memory.ts` |
| `memory/` | 9 | Memory fabric (composition-tested) |
| `aoie/` | 9 | AOIE Arbitration — policy mutation + assertion classification |
| `consensus/` | 8 | φ-quorum swarm voting kernel |
| `sitr/` | 7 | SITR Intervention Log — append-only monotonic record |
| `event/` | 7 | Event substrate, UUIDv7 (the one Date.now() site) |
| `environment/` | 6 | Environment Adaptation Layer (entropy budgets, Q16.16) |
| `gate/` | 5 | Bernstein bounds (never Hoeffding) |
| `verifier/` | 4 | VCG calibration (V4/V5 excluded) |
| `shp/` | 4 | SHP Kernel Interface |
| `pipeline/` | 4 | Decision pipeline + backpressure |
| `network/` | 4 | Network kernel (injected timestamps) |
| `ide/` | 4 | AEGIS IDE Runtime — constitutional panel state |
| `extensions/` | 4 | Extension/Plugin Habitat |
| `crdt/` | 4 | LedgerEntry G-Set CRDT (federation-ready state merge) |
| `api/` | 4 | Managed-agent + admin clients |
| `registry/` | 3 | Holonic-scale entry registry |
| `corpus-engine/` | 3 | 5-phase RALPH pipeline, fibonacci_depths [1,1,2,3,5] |
| `capsule/` | 3 | Capability Evolution Protocol |
| `calibration/` | 3 | Calibration models |
| `projection/` | 2 | Version-pinned projection compiler (RFC 8785 fingerprint) |
| `enforcement/` | 2 | Enforcement Engine |
| `simulation/` `runtime/` `metacognition/` `forensics/` `federation/` `compliance/` `lib/` | 1 ea | Simulation branches · projection machine · MetacognitiveLoop · Forensic Divergence Localisation · Federation seams (CRGM §7) · compliance · telemetry lib |

## 8. Full-tree audit 2026-07-02 — every directory opened, verdicts recorded

~1,700 source files walked (all 32 top-level dirs; `target/` = build cache, excluded).
New findings that no prior session had recorded:

| Finding | Where | Verdict |
|---------|-------|---------|
| **The triad exists ×3, cross-language** | `harness/sdk/{planner,generator,evaluator}` (Py) · `sovereign-mesh/nodes/{architect,artisan,auditor}` (Py, 53KB real logic) · `.claude/metacog/agent-mesh.mjs` (Node) | The α/β/γ fractal mesh is implemented three times in two languages — plus hypervisor twins in Rust (`src/hypervisor`) AND Python (`sovereign-mesh/hypervisor`, with `managed_settings.json`) |
| **`vertex/serve.py` is an Anthropic-compatible gateway** | 45KB: `POST /v1/messages` drop-in + `GET /v1/audit/chain` | A *governed Claude API proxy* — product-shaped: point any Anthropic SDK at it, get constitutional audit chains for free |
| **`agents/` is a full dual-backend org** | 34 depts registered on BOTH Anthropic Managed Agents (`register_managed.py`) and Vertex ADK (`register_vertex_adk.py`); `revenue_engine.py` (money pipeline), `red_team.py` (self-audit), `tools.py` (real I/O tools), `adaptive_lineage.json` (30 real hash-chained evolution events) | REAL, partially exercised |
| **Launch materials already exist** | `docs/LAUNCH_KIT.md` (9KB) + `docs/COLD_EMAIL_TEMPLATE.md` (6.5KB) | Written weeks ago, never used — the distribution gap was diagnosed AND provisioned, then forgotten |
| **4th revenue channel wired** | `supabase/functions/github-sponsors` | GitHub Sponsors webhook + claim handler, live-deployable |
| Ed25519 signed records, cross-language | `aegis-ccil-verifier/` (Py + Node byte-identical canonicalization; tamper-rejection test; fresh keypair per run — no committed keys) | REAL — guards the exact φ/ć/≤ canonicalization drift that once broke cross-verify |
| Schema evolution with certificates | `packages/aegis-interface/generated/evolution/v{1→2,2→3}.cert.json` | WIT→{Rust,TS,Py} codegen emits *certified* schema migrations |
| Swarm fitness database | 13 Supabase migrations: dept fitness v2, `dept_graces` (Grace Chain), atomic key verify RPC, `agent_api_profiles` (no raw keys stored) | The swarm's evolution is DB-persisted, not in-memory |
| Studio = 7 projection surfaces | `studio/src/{capsule,divergence,epoch,governance,holographic,lineage,…}-surface` | Real observability product surface |
| `core/` MVCC store | 9 tiny TS files (intent store, conflict resolver, schema registry) | DORMANT toy — candidate to remove or label |
| `backend/.env.local` | on disk, untracked since f44eccad | Verified: contains only host/port comments, no secrets |
| Dormant Stripe handler | `supabase/functions/verify-stripe` | Exists in-repo; PayPal-only is the standing operator decision — do not wire |

**The connected dots, one paragraph:** the same constitutional pattern (plan→build→audit triad,
hash-chained lineage, martingale bound) is independently implemented at every layer — Rust gates,
Python mesh, Node session hooks, TS runtime, Supabase tables, CI quorum — and the layers verify
each other across language boundaries (CCIL Ed25519, LUT-KAN parity, 0xE0E0 frames). That is the
system's genuinely rare property: it is *fractal in implementation*, not just in metaphor. What it
never had until tonight is a front door: DNS was dead, checkout unconfigured, launch kit unshipped.

## 9. Value conversion map (what turns which asset into what)

| Goal | Asset | The one next action |
|------|-------|---------------------|
| **Money now** | Money path (§1) | One real $48 test purchase end-to-end; then attach calendar/cockpit domains |
| **Money weeks** | Determinism engine (§2) | Extract "hash-chained replayable agent audit log" as a 5-min-quickstart package; launch on HN/r/LocalLLaMA |
| **Partners** | §4 arsenal + Ogemma demo | One well-aimed email to Anthropic partnerships citing their downstream-provider form gap, with proof-demo.sh attached |
| **Credibility** | §2 + §3 | Publish Ogemma Mythos as the flagship demo ("a phone vetoes the cloud") |
| **Status** | All | Receipts from the three rows above; nothing else generates it |
