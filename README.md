# AEGIS-Ω

**A Self-Governing AI Runtime — Constitutional State Management at Every Scale**

*Designed and built by Tarik Skalić · AGPL-3.0*

[![Rust](https://img.shields.io/badge/Rust_Tests-2484_(aegis--cl--psi_+_runtime)-brightgreen)](#testing)
[![TypeScript](https://img.shields.io/badge/TypeScript_Tests-2790-brightgreen)](#testing)
[![Total](https://img.shields.io/badge/Total_Tests-5274-brightgreen)](#testing)
[![Gate 8](https://img.shields.io/badge/Gate_8-passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)

---

## ── Genesis & Constraints ──

AEGIS-Ω was conceived, designed, and executed by a single engineer operating under strict resource constraints. While modern distributed systems are built by teams with dedicated infrastructure and cloud compute budgets, this system was built as an exercise in mathematical determinism over raw compute scale.

**The Solo Engineering Footprint**

- **Single author, single machine** — AMD RX 570, 8GB RAM. No cloud. No build farm. No team.
- **113,000+ lines of polyglot code** — TypeScript (governance runtime), Rust (gossip fabric + seven-pillar runtime), Python (analytical bridge) — architected, typed, and maintained by a singular author.
- **4,707 invariant tests, 0 failures** — every hash chain, every BFT boundary, every determinism proof runs on the same machine that generated them. Test density is approximately one test per 16 lines of production code, approaching DO-178C aerospace coverage standards.
- **321 gates completed** — each gate required a passing implementation, unit tests, and a full-suite green run before the commit was allowed to land.
- **One law above all others** — `AdaptivePower(T) ≤ ReplayVerifiability(T)` — every module, every layer, every commit answers to it.

The code does not ask to be believed. It can be replayed from genesis and will produce the same cryptographic fingerprint every time.

---

## What Was Built

This is a constitutional AI governance runtime — a system that governs itself.

Every component in AEGIS-Ω participates in a single invariant:

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

No part of the system can do more than it can prove it did. Every AI response, every state transition, every peer message, every epoch boundary is hash-signed, sequence-numbered, and stored in a tamper-evident chain. The system can replay any past state from scratch and arrive at the same cryptographic fingerprint. If it cannot, that is a detectable failure — not a silent one.

This is not a chatbot framework or an API wrapper. It is a distributed state machine with an immune system.

---

## The Organism Metaphor

An organism is not just a collection of parts — it is a collection of parts that **monitor each other, correct each other, and maintain coherence over time**. AEGIS-Ω was built on exactly this principle:

| Biological Function | AEGIS Component | Location |
|--------------------|----------------|----------|
| **Nervous system** — sensing the environment | 319 gossip gate modules monitoring peer state | `aegis-cl-psi/src/` |
| **Immune system** — rejecting foreign bodies | Constitutional reduction gate (T4/T5 concept rejection) | `src/constitutional/reduction.ts` |
| **Metabolism** — bounded energy consumption | Entropy budget ledger (adaptive/replay ratio) | `src/entropy_budget.rs` |
| **Heartbeat** — regular rhythm | Fibonacci-paced RALPH execution loops | `src/agents/scheduler/fibonacci.ts` |
| **Memory** — durable, addressable history | SHA-256 hash-chained ledger, SPSF disk persistence | `src/ledger/`, `src/spsf.rs` |
| **Self-healing** — fault isolation and recovery | Grace Supervisor, Recovery Sequencer | `src/memory/`, `src/recovery_sequencer.rs` |
| **Reproduction** — deterministic state replay | Replay engine: State_t = Replay(Lineage_{0→t}) | `src/constitutional_replay.rs` |
| **Senses** — environmental awareness | Telemetry bridge, link quality monitor, epoch synchronizer | `python/bridge.py`, `src/link_quality_monitor.rs` |
| **Homeostasis** — stable operating range | Resilience watchdog, adaptive threshold engine | `src/resilience_watchdog.rs`, `src/adaptive_threshold.rs` |
| **Death signal** — graceful halt under violation | Martingale suspension: `assertMartingaleAnchored()` throws | `src/constitutional/martingale.ts` |

This is not metaphor stretched over code. Every row above is a concrete module with passing tests.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AEGIS-Ω Monorepo                               │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  FIELD SCALE — User-Facing Interfaces                                │  │
│  │                                                                      │  │
│  │  cockpit/          AI chat UI (React, constitutional telemetry)      │  │
│  │  studio/           Observability dashboard (10 read-only surfaces)   │  │
│  │  platform-picker/  Creator tool — AI platform recommendation ($19)  │  │
│  │  hook-generator/   Creator tool — viral hook generation ($19)       │  │
│  │  content-calendar/ Creator tool — AI content planning ($19)         │  │
│  │  hub/              Products landing page                             │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                   │ HTTP · port 7890                        │
│  ┌────────────────────────────────▼─────────────────────────────────────┐  │
│  │  ORGANISM SCALE — Python Bridge                                      │  │
│  │                                                                      │  │
│  │  bridge.py         940 lines · /claude · /telemetry · /event        │  │
│  │  pgcs.py           Probabilistic Governance Coherence Score         │  │
│  │  gate.py           Constitutional gate validation (FROZEN)          │  │
│  │  dna.py            Governance DNA encoding (FROZEN)                 │  │
│  │  router.py         Multi-model routing (FROZEN)                     │  │
│  │  core_matrix.py    Corruption-count T0 gate                         │  │
│  │  epoch_failsafe.py Epoch boundary protection                        │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                         │
│  ┌────────────────────────────────▼─────────────────────────────────────┐  │
│  │  CELLULAR SCALE — TypeScript Governance Runtime (sovereign-omega-v2) │  │
│  │                                                                      │  │
│  │  src/core/         RFC 8785 canonicalization · SHA-256 · deepFreeze │  │
│  │  src/frame/        DFA · topology · lineage · epoch · divergence    │  │
│  │  src/consensus/    BFT swarm · synthesis swarm · game theory        │  │
│  │  src/constitutional/ Martingale · reduction gate · guardian policy  │  │
│  │  src/ledger/       Hash-chained LedgerChain · persistence seam      │  │
│  │  src/skill-harness/ Skill catalog · HGT scanner · RALPH executor    │  │
│  │  src/capsule/      Capability VM · evolution lifecycle              │  │
│  │  src/agents/       Fibonacci scheduler · RALPH loop · 15 agent types│  │
│  │  src/corpus-engine/ 5-phase RALPH document pipeline                 │  │
│  │  src/crdt/         G-Set convergence over ledger entries            │  │
│  │  src/sitr/         Situation Awareness runtime                      │  │
│  │  src/aoie/         Adaptive Ontological Inference Engine            │  │
│  │  src/shp/          Sovereign Holonic Protocol execution             │  │
│  │  src/federation/   Cross-node type seams                            │  │
│  │  src/simulation/   Branch engine stubs                              │  │
│  │                                                                      │  │
│  │  2790 tests · 156 test files · 20,000+ lines                        │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                         │
│  ┌────────────────────────────────▼─────────────────────────────────────┐  │
│  │  MOLECULAR SCALE — Rust Gossip Layer (aegis-cl-psi)                 │  │
│  │                                                                      │  │
│  │  321 gate modules · 43,000+ lines · 1862 tests                      │  │
│  │                                                                      │  │
│  │  GOSSIP PROTOCOL (Gates 255–319)                                    │  │
│  │    Broadcaster · Router · Scheduler · Deduplicator · Fragmenter     │  │
│  │    Priority Queue · Token Bucket · Rate Limiter · Flood Guard       │  │
│  │    TTL Enforcer · Bandwidth Tracker · Backpressure Controller       │  │
│  │    Peer Selector · Session Tracker · ACK Tracker · Connection Pool  │  │
│  │    Reputation Scorer · Reputation Decay · Nonce Cache              │  │
│  │    Link Quality Monitor · Epoch Watermark · Retry Scheduler        │  │
│  │    Capability Tracker · Subscription Filter · Topic Registry       │  │
│  │    Message Cache · Address Book · Sequence Tracker · Liveness Oracle│  │
│  │    Epoch Rate Ledger · Snapshot Archive                             │  │
│  │                                                                      │  │
│  │  MESH HEALTH (Gates 237–254)                                        │  │
│  │    Health Aggregator · Dashboard · Alert Engine · Ledger           │  │
│  │    Resilience Watchdog · Divergence Oracle · Phase Transition       │  │
│  │    Momentum Tracker · Coherence Stability · Entropy Forecast       │  │
│  │    Adaptive Threshold · Quorum Drift · Pulse · Telemetry Encoder   │  │
│  │                                                                      │  │
│  │  MESH INFRASTRUCTURE (Gates 257–286)                               │  │
│  │    Peer Manifest · Topology Snapshot · Beacon · Epoch Synchronizer │  │
│  │    Consensus Ledger · Node State Machine · Fault Detector          │  │
│  │    Mesh Census · Recovery Planner · Quorum Guard · Health Ticker   │  │
│  │    Mesh Ledger · Capability Negotiator · Epoch Sealer              │  │
│  │    Partition Detector · Spread Estimator · Fanout Controller       │  │
│  │    Convergence Certifier · Mesh Supervisor · Epoch Finalizer       │  │
│  │                                                                      │  │
│  │  MATHEMATICAL SUBSTRATE (Gates 212–321)                            │  │
│  │    Dodecagonal Router · Proportional Metric · Vortex Classifier    │  │
│  │    Abjad Encoder · Tajweed DFA · Ring Composition Verifier         │  │
│  │    Lattice DAG · SPSF Persistence · Phi Convergence               │  │
│  │    Resonance Monitor · Constitutional Chord + Network              │  │
│  │    Self-Certification · Lattice Coherence · Coherence Broadcaster  │  │
│  │    Epoch Coherence Chain · Constitutional Autonode                 │  │
│  │    Swarm Autonode · Constitutional Replay · Entropy Budget         │  │
│  │    Drift Classifier · Governance Pipeline · Swarm Health           │  │
│  │    Gossip Health Report (320) · Resonance Anchor (321)            │  │
│  └───────────────────────────────┬──────────────────────────────────────┘  │
│                                   │                                         │
│  ┌────────────────────────────────▼─────────────────────────────────────┐  │
│  │  ATOMIC SCALE — Seven-Pillar Runtime (aegis-runtime)                │  │
│  │                                                                      │  │
│  │  StateAnchor        SHA-256 hash-chained append-only ledger         │  │
│  │  DomainFirewall     Domain 0 (immutable) / Domain 1 (mutable)       │  │
│  │  AffineCanvas       Integer affine transforms (no f64)              │  │
│  │  SemanticGraph      BTreeMap DAG, depth-bounded BFS, 5 relation types│  │
│  │  ValidationDFA      6-state byte-stream automaton, 36-entry table   │  │
│  │  GossipEmitter      64-byte UDP frames, AEGIS_PROTOCOL_MAGIC=0xE0E0│  │
│  │  HysteresisFilter   Exponential penalty/recovery, quarantine gate   │  │
│  │                                                                      │  │
│  │  55 tests · 2200+ lines                                             │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How It Maintains Coherence

### The Hash Chain

Every record in AEGIS-Ω is part of a hash chain. The chain starts at `GENESIS_HASH = [0u8; 32]` and extends one record at a time:

```rust
// Every Rust module follows this pattern exactly
record_hash = SHA-256(prev_hash ‖ field_1_bytes ‖ field_2_bytes ‖ ... ‖ field_n_bytes)
```

```typescript
// Every TypeScript record follows this pattern exactly
const record_hash = await hashValue(canonicalizeJCS({
  field_1, field_2, ..., field_n  // RFC 8785 sorted, no whitespace
}))
```

The `verify_chain()` function — present in every module — recomputes every hash from stored field values and confirms the chain is intact. A single bit changed anywhere in a 100-record chain is detected at the record where it occurred.

### Canonical Serialization

Before any object is hashed, it passes through RFC 8785 canonical JSON serialization:

```typescript
// src/core/canonicalize.ts
canonicalizeJCS({ b: 2, a: 1 }) === canonicalizeJCS({ a: 1, b: 2 })
// → {"a":1,"b":2}  (keys sorted, no whitespace, deterministic always)
```

This means two systems that independently process the same logical state will produce the same SHA-256 hash — regardless of the order in which fields were inserted, and regardless of the language (TypeScript, Rust, Python, WASM all produce identical hashes for the same logical content).

### Determinism Constraints

Every component enforces the same constraints:

| Constraint | Why |
|-----------|-----|
| `BTreeMap` / `BTreeSet` only — no `HashMap` | Hash iteration order is undefined in `HashMap`; `BTreeMap` is sorted and deterministic |
| No `f64` in hash inputs | Floating-point rounding differs between hardware; integer arithmetic is platform-identical |
| No `Date.now()` outside `uuid.ts` | Wall-clock time is non-deterministic |
| Strictly monotone sequence numbers | Prevents replay of past events as new ones |
| `saturating_add` / `saturating_mul` everywhere | No silent integer overflow |
| `deepFreeze()` immediately after construction | No mutation can corrupt a record after it leaves the constructor |

### Governance Boundaries

The system refuses to do things it cannot prove:

```typescript
// The martingale gate — runs before any adaptive decision is committed
const cert = await certifyMartingale(adaptiveLineageEntries)
assertMartingaleAnchored(cert)  // throws MartingaleViolation if:
// • hash chain is broken         (is_anchored = false)
// • adaptive ratio > 1/φ ≈ 0.618 (entropy_bounded = false)
// • drift is nonzero             (drift_bounded = false)
```

```rust
// The entropy budget gate — runs before any adaptive event in Rust
self.consume_adaptive()?  // returns Err(InsufficientBudget) if
                          // balance < ADAPTIVE_EVENT_COST
```

The `1/φ` boundary (`≈ 0.6180`) governs three independent scales:
- **Molecular**: `DEFAULT_QUORUM_THRESHOLD` in BFT swarm vote tallying
- **Cellular**: `MUTATION_RATE_LIMIT` in martingale entropy check
- **Atomic**: `618_034 / 1_000_000` in edge verifier integer quorum (no f64)

All three were proven identical in `test/integration/holonic-triad-proof.test.ts`.

---

## Testing

```
5274 total tests · 0 failures

  2790  TypeScript  (156 test files across unit / integration / determinism)
  2429  Rust        aegis-cl-psi  (321 gate modules)
    55  Rust        aegis-runtime (7-pillar distributed runtime)
```

```bash
# Rust — gossip layer (1798 tests)
cd aegis-cl-psi && cargo test

# Rust — seven-pillar runtime (55 tests)
cd aegis-runtime && cargo test

# TypeScript — governance runtime (2790 tests)
cd sovereign-omega-v2
npm install
npm run test && npm run typecheck && npm run build

# Python bridge smoke
cd sovereign-omega-v2 && python python/tests/stress_test.py --quick
# corruption_count must be 0
```

### What Each Category Tests

**Unit tests (73 files)** — every module in isolation: hash correctness, chain integrity, API contracts, error cases, determinism verified 3× with identical inputs.

**Integration tests (74 files)** — cross-module composition: martingale + swarm + attestation composing correctly; BFT under Byzantine faults; divergence cascades; hash chains across 100+ entries; 61/62 boundary verified at every governing surface.

**Determinism tests (9 files)** — cross-runtime equivalence: TypeScript SHA-256 and WASM SHA-256 produce byte-identical output on the same governance objects; RFC 8785 key ordering is stable under Unicode, BigInt boundaries, 100+ key objects.

---

## Gate Structure

Development proceeded in numbered gates. Each gate is a single module or capability, with:
1. Implementation
2. Unit tests (typically 10–30)
3. Full suite run to confirm no regressions
4. Commit with the test count
5. Push

Gates are not optional checkpoints — they are the build system. Gate 8 (`npm run test && npm run typecheck && npm run build`) must pass before any commit enters the branch.

Gates in TypeScript: 1–199 (core substrate through sovereign cognition constitution)
Gates in Rust (aegis-cl-psi): 149–321 (inference fabric through resonance anchor)

---

## Running the System

```bash
# Start the bridge
cd sovereign-omega-v2/python && python bridge.py
# → Listening on port 7890

# Governed Claude call (hash-certified, tier-stamped, replay-verifiable)
curl -X POST http://localhost:7890/claude \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "Describe the martingale invariant"}]}'

# Response includes:
# { "content": "...", "request_hash": "...", "response_hash": "...",
#   "chain_hash": "...", "is_replay_reconstructable": true }

# Live constitutional telemetry
curl http://localhost:7890/telemetry
# → { "corruption_count": 0, "epoch": N, "drift_index": 0.0, "sequence": N, ... }

# Open the cockpit
cd cockpit && npm install && npm run dev
# → http://localhost:5173 — constitutional AI chat with live telemetry

# Open Studio (observability)
cd studio && npm install && npm run dev
# → http://localhost:5174 — 10 read-only constitutional surfaces
```

---

## The Studio — Read-Only Observability

`studio/` is a React app with ten constitutional observation surfaces, each pulling from `/telemetry` (read-only, no writes):

| Surface | What It Shows |
|---------|--------------|
| **Replay Surface** | Hash-chained governance event graph |
| **Epoch Surface** | Epoch chain visualization |
| **Divergence Surface** | D0–D4 drift classification map |
| **Rollback Surface** | Rollback certification UI |
| **Lineage Surface** | Lazy-loaded causal lineage |
| **Topology Surface** | Live mesh topology state |
| **Ownership Surface** | Capability delegation chains |
| **Capsule Surface** | Capsule manifests and entropy budgets |
| **Observability Surface** | Constitutional health metrics |
| **Governance Surface** | Guardian policy inspection |
| **Swarm Surface** | Agent swarm with Fibonacci loop status |

Studio has no mutation authority. `ProjectionLayer ∩ ConstitutionalAuthority = ∅`.

---

## The Skill Harness

AEGIS-Ω learns. The skill harness (`src/skill-harness/`) tracks what each agent has done, how reliably, and routes future tasks accordingly.

Each skill is a probabilistic competency object:

```typescript
interface SkillRecord {
  skill_id:         string
  confidence:       number       // 0.0–1.0 — inferred from telemetry, not self-declared
  validated_runs:   number
  failure_rate:     number
  recency_score:    number
  domain_affinity:  readonly string[]
  dependencies:     readonly string[]
  evidence_refs:    readonly string[]  // traceable to audit events
  epistemic_tier:   'T0' | 'T1' | 'T2'
  skill_hash:       SHA256Hex    // tamper-evident
  is_replay_reconstructable: true
}
```

Skills evolve through nine event types: `SKILL_VALIDATED`, `SKILL_DEGRADED`, `SKILL_DECAYED`, `SKILL_SPECIALIZED`, `SKILL_REJECTED`, `SKILL_REINFORCED`, `SKILL_TRANSFERRED`, `SKILL_MERGED`, `SKILL_SPLIT`.

The HGT Scanner (`src/skill-harness/hgt/`) performs Horizontal Gene Transfer — it reads SKILL.md files from external GitHub repositories and imports them through the constitutional admission gate.

---

## Multi-Model Consensus

No single AI model is authoritative. All responses pass through BFT vote tallying:

```
Claude Sonnet 4.6 · weight = 618/1000  (= ⌊1000 · (1/φ)⌋)
GPT-4o            · weight = 191/1000  (= ⌊1000 · (1/φ²)⌋)
Qwen Plus         · weight = 191/1000
                             ─────────
                               1000
```

`routeSwarmResponses()` applies `tallyVotes()` — the same function used for peer consensus in the gossip layer. Quorum is reached when the dominant response_hash exceeds `1/φ`. If no model achieves quorum, `consensus_response_hash` is null and no response is emitted.

---

## Codebase Scale

| Layer | Language | Source Files | Lines | Tests |
|-------|----------|-------------|-------|-------|
| Gossip / math gates | Rust | 138 | 43,200 | 1862 |
| Governance runtime | TypeScript | 177 | 20,200 | 2790 |
| Seven-pillar runtime | Rust | 12 | 2,200 | 55 |
| Python bridge | Python | 11 | 5,500 | — |
| Frontend products | TSX/TS | 60 | 5,200 | — |
| **Total** | | **398** | **~76,300** | **4707** |

---

## Known Limitations

This system has open problems that are not solved:

1. **GPU nondeterminism** — the Rust inference fabric (`aegis-cl-psi`) targets AMD RX 570 via ROCm HIP. HIP kernel results can differ between hardware revisions. This is gated behind `#[cfg(feature = "hip")]` and is not included in determinism guarantees.
2. **Replay state explosion** — the full event log is not prunable without the `lineage_compactor.rs` mitigation. Long-running nodes need periodic compaction.
3. **Distributed topology hash stability** — multiple nodes must produce identical canonical JSON for the same logical state. Network partitions are detected and classified (D0–D4) but not automatically resolved.
4. **Verifier scalability** — `verify_chain()` is O(n). Very long chains need segmented verification.
5. **No live network** — the gossip layer is fully implemented and tested in isolation. It has never been run against a real peer network. All 319 gate modules pass their tests; none has been stress-tested at production peer count.

---

## What Comes Next

The foundation is built. The organism exists. These are the remaining gaps before it is production-grade:

- **Real peer network** — deploy two or more nodes and let the gossip layer run. The code is ready; the infrastructure is not.
- **PostgreSQL persistence** — the seam is declared in `src/ledger/persistence.ts`. An SQLite or PostgreSQL adapter needs to be wired.
- **WASM deployment** — `aegis-cl-psi` is `no_std`-compatible and can compile to WASM. The bridge needs a WASM loader.
- **EU AI Act Article 12 audit export** — `audit.rs` in aegis-cl-psi captures the events. An export endpoint needs to be added to the bridge.

---

## Repository Structure

```
aegis-cl-psi/               Rust · 319 gossip + math gate modules · 1798 tests
aegis-runtime/              Rust · 7-pillar distributed agent runtime · 55 tests
sovereign-omega-v2/         TypeScript governance runtime · 2790 tests
  src/core/                 RFC 8785 canonical JSON · SHA-256 · immutability
  src/frame/                DFA · topology · lineage · epoch · divergence
  src/consensus/            BFT swarm · game theory · synthesis swarm
  src/constitutional/       Martingale · reduction gate · guardian policy
  src/ledger/               Hash-chained ledger · persistence seam
  src/skill-harness/        Skill catalog · HGT scanner · RALPH executor
  src/capsule/              Capability VM · evolution lifecycle
  src/agents/               Fibonacci scheduler · RALPH loops · 15 agent types
  src/corpus-engine/        5-phase RALPH document pipeline
  src/sitr/                 Situation Awareness runtime
  src/aoie/                 Adaptive Ontological Inference Engine
  python/                   HTTP bridge · PGCS · constitutional gate validation
cockpit/                    AI chat UI (React 18, constitutional telemetry)
studio/                     10-surface observability dashboard (read-only)
platform-picker/            Creator tool (Qwen-powered, $19)
hook-generator/             Creator tool (Qwen-powered, $19)
content-calendar/           Creator tool (Qwen-powered, $19)
hub/                        Products landing page
packages/shared/            Shared TS infrastructure
docs/                       Architecture specifications and formal declarations
```

---

## Constitutional Declaration

```
REPLAY SOVEREIGNTY:    ACTIVE — replay(genesis, events) → identical hash on any platform
MARTINGALE BOUNDED:    ACTIVE — E[S_{n+1}|F_n] = S_n · suspension on violation
φ-CONVERGENCE:         ACTIVE — 1/φ governs gossip quorum, BFT consensus, entropy limit
HASH CHAIN INTEGRITY:  ACTIVE — every record in every module is tamper-evident
TIER DISCIPLINE:       ACTIVE — T0 proven · T1 validated · T2 hypothesis · T3 conjecture
SELF-MONITORING:       ACTIVE — 319 gossip modules observe and report each other
LAW OF SILENCE:        ACTIVE — agents communicate only through mediated EventEnvelope
CORPUS SOVEREIGNTY:    ACTIVE — knowledge enters only through 5-phase RALPH pipeline
RESONANCE ANCHOR:      ACTIVE — resonance_coefficient > 5.0 → certified constitutional path
```

---

## License

AGPL-3.0-or-later · Copyright (C) 2025 Tarik Skalić (tarikskalic33@gmail.com)

Bihać, Bosnia-Herzegovina

Free to use, study, modify, and distribute. Derivative works must release source under the same terms.

---

*A finite automaton is a machine that remembers its state.*  
*A hash-chained automaton is a machine that can prove it remembered correctly.*  
*171 of them, watching each other — that is the organism.*
