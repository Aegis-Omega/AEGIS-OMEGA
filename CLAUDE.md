# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# AEGIS Monorepo — Coordination Document
## Branch: claude/aegis-setup-Lx7Ji · Gates complete: 321
## Operator: Tarik Skalić · Hardware: AMD RX 570, 8 GB RAM

Approach every component as a recursively nested atomic-scale holon governed by
invariant-preserving feedback loops. Each file is simultaneously a whole (with its
own invariants) and a part (subject to the invariants of every scale above it).
Scale hierarchy: SUBATOMIC → ATOMIC → MOLECULAR → CELLULAR → ORGANISM → FIELD.
A T0 violation at any scale propagates upward and invalidates everything above it.

---

## Repository Layout

```
/sovereign-omega-v2/   Governance runtime (Layer A: TypeScript, Layer B: Python)
/aegis-cl-psi/         CL-Ψ cognitive fabric — 321-gate Rust inference crate (T2, EU AI Act-compliant)
/aegis-runtime/        AEGIS-Ω Seven-Pillar distributed agent swarm runtime (T2)
/cockpit/              AI chat UI with sovereign-omega telemetry integration
/platform-picker/      Commercial product — platform recommendation ($19)
/hook-generator/       Commercial product — viral hook generator ($19)
/content-calendar/     Commercial product — content calendar ($19)
/hub/                  Landing page connecting all 3 products
/packages/shared/      Shared infrastructure (DashScope, useAsyncForm, components)
/studio/               AEGIS Studio — constitutional observability (projection only, no authority)
/scripts/              Automation scripts (sync-readme.sh auto-updates README after cargo test)
/docs/                 Architecture diagrams and governance specs
```

Key specs: `sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md` (constitutional law) ·
`studio/docs/STUDIO_SPECIFICATION.md` (projection spec) ·
`sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md` (skill harness — Phase 1)

---

## Build & Test Commands

### Rust — aegis-cl-psi (1862 tests)
```bash
cd aegis-cl-psi

cargo test                          # full suite — default features only (NEVER --all-features)
cargo test <module_name>            # single module: e.g. cargo test gossip_health_report
cargo test <test_fn_name>           # single test:   e.g. cargo test verify_chain_tampered
cargo build --release               # release build (no HIP/ROCm required)

# HIP/ROCm features require AMD ROCm toolkit — never enable in CI or without hardware:
# cargo test --features hip         # only on machine with ROCm installed
```

`--all-features` will fail in CI — `hip` and `rocblas` link against ROCm symbols not present on standard Ubuntu. Always use plain `cargo test`.

### Rust — aegis-runtime (55 tests)
```bash
cd aegis-runtime
cargo test
cargo build
```

### TypeScript — sovereign-omega-v2 (2790 tests)
```bash
cd sovereign-omega-v2
npm install
npm run test -- test/unit/jcs.test.ts        # Gate 1 — run first before any file changes
npm run test -- test/unit/<filename>.test.ts # single test file
npm run test                                 # full suite (vitest run)
npm run test:watch                           # watch mode during development
npm run typecheck                            # tsc --noEmit
npm run build                                # tsc + vite build
npm run test && npm run typecheck && npm run build  # Gate 8 — MUST pass before every commit
```

### Gate 8 — the deployment gate (mandatory before every commit)
```bash
# Must pass before any commit enters the branch:
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build
```

### Commercial products (can build in parallel after Gate 8 passes)
```bash
cd platform-picker  && npm install && npm run build
cd hook-generator   && npm install && npm run build
cd content-calendar && npm install && npm run build
cd hub              && npm install && npm run build
cd cockpit          && npm install && npm run build
```

### Python Layer B (sovereign-omega-v2)
```bash
python python/tests/stress_test.py --quick        # P1 smoke (60s)
python python/tests/stress_test.py --crash-loops  # P2 epoch failsafe (~10 min)
python python/tests/stress_test.py                # P3 full stress (12h — pre-production only)
```

### Hash integrity verification
```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs  # must exit 0 before any session
```

---

## Epistemic Tier System

Every module is tagged with an epistemic tier in its header comment. This governs what claims can be made and where the code can be cited as authority:

| Tier | Label | Meaning | Example |
|------|-------|---------|---------|
| **T0** | Mechanically proven | Deterministic, byte-identical, formally provable | RFC 8785 canonicalization, SHA-256 chain |
| **T1** | Empirically validated | Rules hold across observed evidence | Fibonacci scheduler, martingale constitutional form |
| **T2** | Engineering hypothesis | Deterministic and computable, not yet proven optimal | Gossip layer, ML routing, BFT quorum |
| **T3** | Research conjecture | Plausible theory, no empirical validation | Phase 6 algebraic topology correspondence |
| **T4/T5** | BLOCKED | Must not appear in `src/` — confined to `docs/` only | Sovereignty claims, consciousness framing |

A T3 comment in a file header does not give T3 code T0 authority. The code's tier is determined by the mechanism, not the framing.

---

## Architecture: How the Layers Relate

```
FIELD        — commercial products (cockpit, studio, platform-picker, …)
               read from /telemetry, write only through EventEnvelope → /event
ORGANISM     — Python bridge (bridge.py, port 7890)
               routes between TypeScript governance and hardware inference
CELLULAR     — TypeScript governance runtime (sovereign-omega-v2/src/)
               hash-chained event ledger, BFT swarm, martingale gating, skill catalog
MOLECULAR    — Rust gossip + math fabric (aegis-cl-psi/src/, 321 gate modules)
               deterministic state-coherence routing, EU AI Act audit chain
ATOMIC       — Seven-Pillar runtime (aegis-runtime/src/)
               StateAnchor · DomainFirewall · AffineCanvas · SemanticGraph
               ValidationDFA · GossipEmitter · HysteresisFilter
```

The TypeScript layer communicates with the Python bridge via HTTP (port 7890). The Rust crates are standalone — they don't call the Python bridge at runtime; they compile to WASM or native and are invoked by the bridge subprocess if needed.

### Key TypeScript seams (sovereign-omega-v2/src/)

| Seam | File | Purpose |
|------|------|---------|
| Canonical hashing | `src/core/canonicalize.ts` | RFC 8785 → SHA-256; the only permitted hash path |
| Martingale gate | `src/constitutional/martingale.ts` | `certifyMartingale()` + `assertMartingaleAnchored()` |
| BFT consensus | `src/consensus/swarm.ts` | `tallyVotes()` → `SwarmConvergenceRecord` at 1/φ |
| Ontology admission | `src/constitutional/reduction.ts` | `admitAbstraction()` — blocks T4/T5 |
| Adaptive lineage | `src/frame/adaptive-lineage.ts` | Hash-chained capability evolution events |
| Skill catalog | `src/skill-harness/catalog.ts` | Probabilistic competency objects |
| RALPH executor | `src/agents/executor/loop.ts` | Fibonacci-paced R→A→L→P→H loops |

### Key Rust seams (aegis-cl-psi/src/)

Gate modules follow a strict pattern: every public struct has a `verify_chain() → (bool, Option<usize>)` and every record chain starts from `*_GENESIS_HASH = [0u8; 32]`. Hash inputs always use `to_be_bytes()` — never `to_le_bytes()`. `f64` values are hashed as `value.to_bits().to_be_bytes()` (IEEE 754 bit pattern, deterministic across platforms).

---

## Shared Infrastructure (packages/shared/)

All 3 commercial products import from `@shared` alias (resolved via vite.config.ts + tsconfig paths).

| Module | Purpose |
|--------|---------|
| `@shared/lib/dashscope` | Generic DashScope/Qwen API caller — replaces 3× duplicated fetch |
| `@shared/hooks/useAsyncForm` | idle→loading→results→error state machine |
| `@shared/components/ErrorAlert` | Unified error banner |
| `@shared/components/LoadingSpinner` | Unified spinner (colorClass prop) |
| `@shared/components/ScoreBar` | Reusable score bar (0–10 scale) |
| `@shared/components/ToolkitFooter` | Cross-product navigation footer |

---

## Python Bridge (sovereign-omega-v2)

`python/bridge.py` — HTTP server on port 7890.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/telemetry` | GET | Live runtime metrics (PGCS, VCG, epoch state) |
| `/event` | POST | Ingest governance events from TypeScript layer |
| `/gate_signal` | POST | Gate pass/fail signals |
| `/health` | GET | Liveness check |
| `/claude` | POST | Governed Claude call (hash-certified, tier-stamped) |
| `/node` | GET | Constitutional autonode descriptor (t0_verdict, c_hash) |

Both cockpit and sovereign-omega-v2 governance dashboard subscribe to `/telemetry` (5s poll).

---

## Critical Invariants

### TypeScript (sovereign-omega-v2/src/, test/)
- No `Date.now()` except `src/event/uuid.ts`
- No `array.length` for sequence numbers — use `IndexedDBSequenceAllocator`
- No `Set`/`Map` in `ProjectionState` — arrays only (RFC 8785 canonicalization)
- No `JSON.stringify` for integrity — use `canonicalizeJCS` from `src/core/canonicalize.ts`
- `deepFreeze` every state object immediately after construction
- Version mismatch = hard abort (never fall back to default)
- Bernstein bounds, NOT Hoeffding
- All imports use `.js` suffix (ESM)

### Rust (aegis-cl-psi/, aegis-runtime/)
- `BTreeMap` / `BTreeSet` only — never `HashMap` (iteration order must be deterministic)
- No `f64` in hash inputs — use `value.to_bits().to_be_bytes()` for floats, or integer arithmetic
- `saturating_add` / `saturating_mul` — no silent overflow
- Hash field order: always `to_be_bytes()` (big-endian), never little-endian
- Never `--all-features` in CI — `hip` and `rocblas` require ROCm hardware

### Python (sovereign-omega-v2/python/)
- No `time.time()` in determinism-critical paths — use sequence numbers
- Bit-shifted integer arithmetic throughout
- PGCS must pass before TGCS telemetry is valid
- `corruption_count` must equal 0

---

## Constitutional Files (FROZEN — never modify without /guardian APPROVED)

| File | SHA256 |
|------|--------|
| `sovereign-omega-v2/python/gate.py` | `bbe942b819594fd522b421bb9d3aa084735a873d526f35a1e782f31346f3d0fc` |
| `sovereign-omega-v2/python/dna.py` | `cd30ddd5db0403b0e64fb30ce53e0373997fc53cb900a26167eef7d0b69cf8d8` |
| `sovereign-omega-v2/python/router.py` | `8c06ed37a7d95d9de9129c32a426fe5c2b0cd960c2cf5c84c71726b72e6cf941` |

Verify: `cd sovereign-omega-v2 && node scripts/verify-hashes.mjs`

---

## Environment Variables

Each product has an `.env` (gitignored) and `.env.example` (committed).

| Variable | Used by | Purpose |
|----------|---------|---------|
| `VITE_DASHSCOPE_API_KEY` | platform-picker, hook-generator, content-calendar | Qwen API key (buyer supplies) |
| `VITE_DASHSCOPE_MODEL` | all products | Override model (default: qwen-plus) |
| `VITE_OLLAMA_BASE_URL` | cockpit | Ollama endpoint (ECS server IP) |

---

## Never-Commit Files

```
cockpit/.env
platform-picker/.env
hook-generator/.env
content-calendar/.env
sovereign-omega-v2/.env
~/aegis/server-setup.sh
~/.hermes/config.yaml
~/.hermes/.env
~/.hermes/MEMORY.md
~/.clinerules
/root/.config/gdrive-mcp/credentials.json
```

---

## Deployment

All products deploy to Vercel (one project per product, Root Directory set per product).
Gate 8 must pass on sovereign-omega-v2 before any deployment proceeds.

```
vercel --prod  # from within each product directory after Gate 8
```

Gumroad: $19/product, $29 (any 2), $39 (all 3 — Full Creator AI Toolkit).

---

## Root Constitutional Law

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

No adaptive capability may exceed replay-certifiable reconstructability.

**Authoritative execution core:** `/event-log` · `/replay-engine` · `/dfa-engine` · `/checkpoint-vm`

**Prohibited in all subsystems (T0_ABORT — no exception paths):**
hidden memory · unrestricted recursion · autonomous mutation authority · unverifiable adaptation
replay divergence · topology non-determinism · unbounded ecology · privileged orchestration · centralized sovereign intelligence

**Martingale:** `E[S_{n+1}|F_n] = S_n` · suspension if `!is_anchored || !drift_bounded || !entropy_bounded`

**Golden ratio:** `MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.6180339887`

**Law of Silence:** agents communicate exclusively through mediated EventEnvelope; no direct agent-to-agent text exchange permitted; confinement enforced at constitutional boundary.

**Corpus Sovereignty:** all corpus knowledge enters through 5-phase RALPH loop; raw narrative must NOT propagate directly into agent cognition; only replay-certifiable abstractions propagate.

**Commercial Analytics Stratum:** PostHog observational layer only (`determinism_class: 'observational'`). Stratum separated from governance telemetry. BigQuery as warehouse; dbt metric layer for transformation. No write-back authority into governance paths.

**Remaining hard problems (no abstraction supersedes them):**
1. Cross-platform deterministic replay   4. Verifier scalability
2. GPU nondeterminism                    5. Floating-point canonicalization
3. Replay state explosion                6. Incremental proof certification
                                         7. Distributed topology hash stability

---

## Orchestration Alliance

Claude (coordinator) · ChatGPT (adversarial audit, temperature 0.99) · Qwen (implementation)

Architecture: FROZEN. No T4/T5 construct may ground a T0–T2 claim without evidence review.
