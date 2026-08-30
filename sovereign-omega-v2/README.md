# AEGIS Sovereign-Omega V2

**Dual Infinite Boundary — Constitutional Governance Runtime**

Gates 1–219 · ~4,088 passing tests · 252 test files · Gate 8 clean  <!-- metrics refreshed 2026-06-28 from CI Gate-8 log + git ls-files; prior headline (198/2648/150) was stale -->

---

## The Dual Infinite Boundary

This runtime is sealed between two infinite boundaries that operate in complementary directions.

```
╔══════════════════════════════════════════════════════════════════╗
║  UPPER BOUNDARY — Constitutional Sovereignty                     ║
║                                                                  ║
║  AdaptivePower(T) ≤ ReplayVerifiability(T)                       ║
║  E[S_{n+1}|F_n] = S_n                                           ║
║  MUTATION_RATE_LIMIT = DEFAULT_QUORUM_THRESHOLD = 1/φ ≈ 0.618   ║
║                                                                  ║
║  No adaptive action can exceed what is replay-certifiable.       ║
║  The martingale ensures the system cannot evolve faster than     ║
║  it can prove. 1/φ governs consensus, mutation rate, and         ║
║  martingale suspension across three holonic scales.              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  CONSTITUTIONAL GOVERNANCE LAYER                                 ║
║  ┌─────────────────────────────────────────────────────────┐    ║
║  │ BFT Synthesis Swarm · Skill Harness · RALPH Executor    │    ║
║  │ MartingaleCertifier · SwarmConvergence (1/φ threshold)  │    ║
║  │ Guardian Policy · Constitutional Reduction              │    ║
║  │ EpochChain · DFA · Topology · Lineage · Divergence      │    ║
║  │ VCG Calibration · Bernstein Gate · RFC 8785 JCS         │    ║
║  └─────────────────────────────────────────────────────────┘    ║
║                                                                  ║
║  MEMORY FABRIC LAYER                                             ║
║  ┌─────────────────────────────────────────────────────────┐    ║
║  │ FiberActorCell   ACTIVE → TERMINATED (irreversible DFA) │    ║
║  │ ZeroCopyChannel  SlabChunkHandle inbox — no byte copy   │    ║
║  │ SlabAllocator    64-bit bitmap · 4 tiers · epoch decom. │    ║
║  │ GraceSupervisor  fault isolation · state reversion      │    ║
║  │ ForkTree         universe genealogy DAG                 │    ║
║  │ MultiverseRegistry  8 parallel AdaptiveLineage branches │    ║
║  └─────────────────────────────────────────────────────────┘    ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  LOWER BOUNDARY — Execution Isolation                            ║
║                                                                  ║
║  Zero-copy: only SlabChunkHandle (slab_id + chunk_index +        ║
║  handle_hash) crosses fiber boundaries. Payload bytes never      ║
║  leave their slab. Grace Loop seals crashed fibers without       ║
║  corruption. FiberActorCell: ACTIVE → TERMINATED.                ║
╚══════════════════════════════════════════════════════════════════╝
```

**Upper boundary** bounds what the system can *become*. Every adaptive action is hash-chained and replay-certifiable. The martingale `E[S_{n+1}|F_n] = S_n` prevents evolution faster than certification. The 1/φ golden ratio (≈ 0.6180) unifies swarm quorum, constitutional mutation rate, and martingale suspension — the same number governs all three scales simultaneously.

**Lower boundary** bounds what the system can *access*. No payload bytes escape a slab. Only `SlabChunkHandle` — a few integers and a SHA-256 digest — crosses fiber boundaries. When a fiber crashes, `GraceSupervisor.autoRelease()` atomically clears its inbox and the `FiberActorCell` transitions irreversibly to `TERMINATED`. The Grace Loop cannot be bypassed.

Both boundaries are self-similar across all six holonic scales. A T0 violation at SUBATOMIC propagates upward and invalidates every scale above it.

---

## What This System Is

Not a workflow engine. Not an agent runtime. Not an orchestration framework.

A **deterministic constitutional execution substrate**: a replay-complete governance machine where every computation is cryptographically hash-chained from byte level to field level, and every adaptive action is bounded by what can be proven equivalent across any runtime (Linux / macOS / Docker / WASM / ARM / x86).

```
SUBATOMIC  → RFC 8785 bytes, SHA-256, BigInt bitmaps, Bernstein bounds
ATOMIC     → individual modules — each a complete holon with own invariants
MOLECULAR  → core/, event/, gate/, constitutional/, consensus/, memory/
CELLULAR   → SITR Immunity, AOIE Oracle, BFT Swarm, Memory Fabric
ORGANISM   → sovereign-omega-v2 governance runtime (2648 tests)
FIELD      → Claude · ChatGPT · Qwen · operators · Drive corpus
```

---

## Execution Stack

```
┌─────────────────────────────────────────┐ ← Upper boundary
│ BFT Synthesis Swarm                     │   Gate 172  1/φ convergence
│ Skill Harness + RALPH Executor          │   Gates 124–133
│ Martingale Certifier                    │   Gate 61   E[S_{n+1}|F_n]=S_n
│ Swarm Convergence Protocol              │   Gate 34   1/φ quorum
│ Guardian Policy Runtime                 │   Gate 21   constitutional amend.
│ Constitutional Governance               │   Gate 13   verdict lattice
│ AOIE Structural Oracle                  │   Gate 12   post-enforcement class.
│ SITR Runtime Immunity                   │   Gate 11   monotonic escalation
│ SHP Frame Kernel (R→A→L→P→H)           │   Gate 14
│ Epoch Chain                             │   Gate 40
│ DFA · Topology · Lineage · Divergence   │   Gates 28–31
│ Ledger · HotStuff Ω · CRDT             │   Gates 17–20
│ Canonicalization · Bernstein · SHA-256  │   Gates 1–6
├─────────────────────────────────────────┤
│ MultiverseRegistry  (8 universes)       │   Gate 186
│ ForkTree            (DAG genealogy)     │   Gate 192
│ GraceSupervisor     (fault isolation)   │   Gate 193
│ SlabAllocator       (64-bit bitmaps)    │   Gate 194
│ ZeroCopyChannel     (handle-only IMC)   │   Gate 196
│ FiberActorCell      (DFA isolation)     │   Gate 198
└─────────────────────────────────────────┘ ← Lower boundary
```

---

## Build Protocol

```bash
cd sovereign-omega-v2
npm install

# Eight-gate protocol — halt on any failure
npm run test -- test/unit/jcs.test.ts        # Gate 1 — RFC 8785
npm run test -- test/unit/sequence.test.ts    # Gate 2 — atomic sequences
npm run test -- test/unit/immutable.test.ts   # Gate 3 — deep-freeze
npm run test -- test/unit/reducer.test.ts     # Gate 4 — pure reducers
npm run test -- test/unit/vcg.test.ts         # Gate 5 — VCG calibration
npm run test -- test/unit/gate.test.ts        # Gate 6 — Bernstein gate
npm run test -- test/integration/             # Gate 7 — replay + pipeline
npm run test && npm run typecheck && npm run build  # Gate 8 — deployment gate
```

```bash
# Python Layer B
python python/tests/stress_test.py --quick        # P1 smoke (~60s)
python python/tests/stress_test.py --crash-loops  # P2 epoch failsafe
```

---

## Core Invariants (T0 — never violate)

| Invariant | Scope |
|-----------|-------|
| No `Date.now()` in core logic | Only `src/event/uuid.ts` |
| No `Set`/`Map` in `ProjectionState` | Arrays only — RFC 8785 |
| No `JSON.stringify` for integrity | Use `canonicalizeJCS` |
| `deepFreeze` every state object | After construction |
| Zero-copy: only `SlabChunkHandle` crosses fiber | Memory fabric |
| `FiberActorCell` TERMINATED is irreversible | Grace Loop |
| `epoch_failsafe` fails closed on hash mismatch | Python layer |
| Version mismatch = hard abort | No fallback |

---

## Constitutional Status

| Flag | State |
|------|-------|
| REPLAY SOVEREIGNTY | ACTIVE |
| MARTINGALE BOUNDEDNESS | ACTIVE — suspension if `!is_anchored ∨ !drift_bounded ∨ !entropy_bounded` |
| φ-CONVERGENCE | ACTIVE — `1/φ ≈ 0.6180` across swarm · martingale · mutation rate |
| HOLONIC GOVERNANCE | ACTIVE — R→A→L→P→H |
| EXECUTION ISOLATION | ACTIVE — `FiberActorCell` + `ZeroCopyChannel` + `SlabAllocator` |
| GRACE LOOP | ACTIVE — `GraceSupervisor.autoRelease()` + TERMINATED seal |
| LAW OF SILENCE | ACTIVE — EventEnvelope only, no direct agent-to-agent exchange |
| CORPUS SOVEREIGNTY | ACTIVE — 5-phase RALPH loop for all corpus ingestion |

**Prohibited (T0_ABORT — no exceptions):**
```
hidden memory · unrestricted recursion · autonomous mutation authority
replay divergence · topology non-determinism · unbounded ecology
payload bytes crossing fiber boundaries · TERMINATED fiber accepting deposits
```

---

## Non-Equivalence Table

```
Replayability ≠ Correctness
Auditability  ≠ Safety
Calibration   ≠ Truthfulness
Governance    ≠ Alignment
Isolation     ≠ Security
```

A perfectly replayable system can replay catastrophic reasoning flawlessly.
A fully isolated fiber can execute incorrect logic with no payload leakage.
The boundaries bound *form*, not *content*.
