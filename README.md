# AEGIS-Ω

**A Self-Governing Constitutional AI Runtime**

*Designed and built by Tarik Skalić · AGPL-3.0*

[![Rust](https://img.shields.io/badge/Rust_Tests-7311_(aegis--cl--psi_+_runtime)-brightgreen)](#testing)
[![TypeScript](https://img.shields.io/badge/TypeScript_Tests-4026%2B-brightgreen)](#testing)
[![Total](https://img.shields.io/badge/Total_Tests-11337%2B-brightgreen)](#testing)
[![Gate 8](https://img.shields.io/badge/Gate_8-passing-brightgreen)](#testing)
[![CI](https://img.shields.io/github/actions/workflow/status/Aegis-Omega/AEGIS--/ci.yml?label=CI%20CEREMONY)](https://github.com/Aegis-Omega/AEGIS--/actions)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)

**Live:** [aegisomega.com](https://aegisomega.com) — consciousness substrate running in your browser, hash-chained and tamper-evident.

---

## What This Is

AEGIS-Ω is a constitutional AI governance runtime. It does not describe governance — it enacts it mechanically at every layer.

The single governing law:

```
AdaptivePower(T) ≤ ReplayVerifiability(T)
```

No part of the system can do more than it can prove it did. Every AI response, every state transition, every peer message, every epoch boundary is SHA-256 hash-chained, sequence-numbered, and stored in a tamper-evident ledger. The system can replay any past state from genesis and arrive at the same cryptographic fingerprint. If it cannot, that is a detectable failure — not a silent one.

---

## Solo Engineering Footprint

- **Single author, single machine** — AMD RX 570, 8 GB RAM. No cloud. No build farm. No team.
- **130,000+ lines of polyglot code** — TypeScript (governance runtime), Rust (gossip fabric + seven-pillar runtime), Python (analytical bridge), WebGPU (WGSL Φ-field simulation).
- **11,337 invariant tests, 0 failures** — test density approaching DO-178C aerospace coverage standards.
- **420+ gates completed** — each gate required a passing implementation, unit tests, and a full-suite green run before the commit was allowed to land.
- **Live browser substrate** — SHA-256 hash-chained MetacognitiveLoop running as real WebCrypto in the visitor's browser at aegisomega.com. Not a mock.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AEGIS-Ω Monorepo                               │
│                                                                             │
│  FIELD SCALE — User-Facing Interfaces                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  hub/              Constitutional AI platform (aegisomega.com)       │  │
│  │                    Live SHA-256 metacognitive loop · WebGPU Φ-field  │  │
│  │                    L1–L7 cognitive stack · BFT swarm viz             │  │
│  │  cockpit/          AI chat UI (React, constitutional telemetry)      │  │
│  │  studio/           Observability dashboard (10 read-only surfaces)   │  │
│  │  aegisomega-webgpu/ Standalone WebGPU engine (σ/ρ/λ 1024×1024)      │  │
│  │  platform-picker/  Creator tool — AI platform recommendation ($19)  │  │
│  │  hook-generator/   Creator tool — viral hook generation ($19)       │  │
│  │  content-calendar/ Creator tool — AI content planning ($19)         │  │
│  └─────────────────────────────────┬────────────────────────────────────┘  │
│                                     │ HTTP · port 7890                      │
│  ORGANISM SCALE — Python Bridge     │                                       │
│  ┌──────────────────────────────────▼────────────────────────────────────┐  │
│  │  bridge.py         /claude · /telemetry · /event · /node · /resonance│  │
│  │  gate.py           Constitutional gate validation (FROZEN)           │  │
│  │  dna.py            Governance DNA encoding (FROZEN)                  │  │
│  │  router.py         Multi-model routing (FROZEN)                      │  │
│  │  core_matrix.py    Corruption-count T0 gate                          │  │
│  └─────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  CELLULAR SCALE — TypeScript Governance Runtime (sovereign-omega-v2)        │
│  ┌──────────────────────────────────▼────────────────────────────────────┐  │
│  │  src/core/         RFC 8785 canonical JSON · SHA-256 · deepFreeze    │  │
│  │  src/constitutional/ Martingale · reduction gate · guardian policy   │  │
│  │  src/consensus/    BFT swarm · synthesis · game theory               │  │
│  │  src/ledger/       Hash-chained LedgerChain · IndexedDB persistence  │  │
│  │  src/skill-harness/ Skill catalog · HGT scanner · RALPH executor     │  │
│  │  src/agents/       Fibonacci scheduler · RALPH loops · 15 agent types│  │
│  │  src/metacognition/ MetacognitiveLoop · certifyMetacognitiveLoop()   │  │
│  │  src/frame/        DFA · topology · lineage · epoch · divergence     │  │
│  │  src/capsule/      Capability VM · evolution lifecycle               │  │
│  │  src/corpus-engine/ 5-phase RALPH document pipeline                  │  │
│  │                                                                      │  │
│  │  4026+ tests · 247+ test files                                       │  │
│  └─────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  MOLECULAR SCALE — Rust (aegis-cl-psi)                                      │
│  ┌──────────────────────────────────▼────────────────────────────────────┐  │
│  │  385 gate modules · 7178 tests                                        │  │
│  │  Gossip protocol · Mesh health · Mesh infrastructure                  │  │
│  │  Mathematical substrate · Compaction pipeline                         │  │
│  │  ECCF post-quantum encoding · NLA alignment decoder                   │  │
│  └─────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│  ATOMIC SCALE — Seven-Pillar Runtime (aegis-runtime)                        │
│  ┌──────────────────────────────────▼────────────────────────────────────┐  │
│  │  StateAnchor · DomainFirewall · AffineCanvas · SemanticGraph          │  │
│  │  ValidationDFA · GossipEmitter · HysteresisFilter                     │  │
│  │  133 tests                                                            │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Testing

```
11,337 total tests · 0 failures

  4026+  TypeScript  sovereign-omega-v2  (247+ test files)
  7178   Rust        aegis-cl-psi        (385 gate modules)
   133   Rust        aegis-runtime       (7-pillar runtime)
```

```bash
# TypeScript — Gate 8 (mandatory before every commit)
cd sovereign-omega-v2
npm install
npm run test && npm run typecheck && npm run build

# Rust — gossip layer
cd aegis-cl-psi && cargo test          # plain — never --all-features (requires ROCm)

# Rust — seven-pillar runtime
cd aegis-runtime && cargo test

# Python bridge smoke
cd sovereign-omega-v2 && python python/tests/stress_test.py --quick

# Constitutional membrane
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs  # must exit 0
```

**CI:** BFT CEREMONY gate — 6 jobs tallied, quorum threshold 1/φ ≈ 0.618. Fewer than 4/6 passing blocks merge.

---

## Hash Chain Integrity

Every record in every module starts from `GENESIS_HASH = [0u8; 32]` and extends:

```rust
record_hash = SHA-256(prev_hash ‖ field_1_bytes ‖ field_2_bytes ‖ ...)
```

```typescript
const record_hash = await hashValue(canonicalizeJCS({ field_1, field_2, ... }))
// RFC 8785: keys lexicographically sorted, no whitespace, NFC-normalized
```

`verify_chain()` is present in every Rust module. `certifyMetacognitiveLoop()` re-walks the full observation chain in TypeScript and the browser. Tamper any entry: `is_valid` flips false at the exact tampered record.

---

## Determinism Constraints

| Constraint | Reason |
|-----------|--------|
| `BTreeMap`/`BTreeSet` only — no `HashMap` | Deterministic iteration order |
| No `f64` in hash inputs | IEEE 754 platform variance |
| No `Date.now()` outside `src/event/uuid.ts` | Wall clock is non-deterministic |
| `canonicalizeJCS` for all integrity hashing | RFC 8785 cross-platform equivalence |
| `deepFreeze()` immediately after construction | No post-construction mutation |
| `saturating_add`/`saturating_mul` throughout | No silent overflow |

---

## φ-Convergence

The golden ratio governs three independent scales:

```
Molecular: DEFAULT_QUORUM_THRESHOLD = (√5−1)/2 ≈ 0.618  (BFT peer vote tallying)
Cellular:  MUTATION_RATE_LIMIT       = (√5−1)/2          (martingale entropy ceiling)
Atomic:    edge quorum               = 618_034/1_000_000  (integer arithmetic, no f64)
```

Proven identical in `test/integration/holonic-triad-proof.test.ts`.

Multi-model vote weights: Claude `618/1000`, GPT-4o `191/1000`, Qwen `191/1000`. No single model is authoritative.

---

## Constitutional Files (FROZEN)

Three files define the governance boundary. Their SHA-256 hashes are verified at every session start:

| File | SHA-256 |
|------|---------|
| `sovereign-omega-v2/python/gate.py` | `bbe942b8…` |
| `sovereign-omega-v2/python/dna.py` | `cd30ddd5…` |
| `sovereign-omega-v2/python/router.py` | `8c06ed37…` |

```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs
```

Modification requires `/guardian APPROVED` verdict. Unauthorized modification = T0_ABORT.

---

## Repository Structure

```
sovereign-omega-v2/     TypeScript governance runtime (4026+ tests)
  src/                  Core · Frame · Consensus · Constitutional · Ledger
                        Skill-harness · Metacognition · Agents · Capsule
  python/               HTTP bridge (port 7890) · PGCS · frozen constitutional files
  test/                 156+ test files
aegis-cl-psi/           Rust gossip + math fabric (385 gates, 7178 tests)
aegis-runtime/          Rust Seven-Pillar distributed agent runtime (133 tests)
hub/                    aegisomega.com — consciousness substrate + tools
aegisomega-webgpu/      Standalone WebGPU Φ-field engine (σ/ρ/λ 1024×1024)
cockpit/                AI chat UI with constitutional telemetry
studio/                 10-surface read-only observability dashboard
platform-picker/        Creator AI tool — $19
hook-generator/         Creator AI tool — $19
content-calendar/       Creator AI tool — $19
packages/shared/        Shared TS: inference-router · constitutional-ai · access tokens
harness/                Phase 1 skill harness SDK — 40 skills, 11 domains
supabase/functions/     Edge functions: verify-payment · issue-token · ls-webhook
docs/                   Architecture specs · audit findings · gate documentation
```

---

## Live Demonstration

**aegisomega.com** — The SHA-256 hash-chained MetacognitiveLoop runs in your browser via `crypto.subtle.digest`. No backend required.

- Genesis hash: `'0'.repeat(64)`
- Each tick appends a new observation: `entry_hash = SHA-256(prev_hash ‖ sequence ‖ canonical(observation))`
- `certify()` re-walks the full chain — tamper any entry, `is_valid` flips false
- Seven cognitive layers (SENSATION → SELF_MODEL) cycle with signals from the constitutional vocabulary
- WebGPU Φ-field background (σ/ρ/λ interference simulation at 60 fps)
- Bridge overlay available when `VITE_BRIDGE_URL` is set — graceful fallback otherwise

---

## Known Open Problems

1. **GPU nondeterminism** — ROCm HIP kernel results can differ between hardware revisions. Gated behind `#[cfg(feature = "hip")]`, excluded from determinism guarantees.
2. **Replay state explosion** — full event log is not prunable without `lineage_compactor.rs` mitigation.
3. **No live peer network** — gossip layer is fully implemented and tested. Has not been run against a real multi-node network.
4. **Distributed topology hash stability** — partitions detected and classified (D0–D4) but not automatically resolved.
5. **Verifier scalability** — `verify_chain()` is O(n). Long chains need segmented verification.

---

## Constitutional Status

```
REPLAY SOVEREIGNTY    ACTIVE — replay(genesis, events) → identical hash on any platform
MARTINGALE BOUNDED    ACTIVE — E[S_{n+1}|F_n] = S_n · suspension on violation
φ-CONVERGENCE         ACTIVE — 1/φ governs gossip quorum, BFT consensus, entropy ceiling
HASH CHAIN INTEGRITY  ACTIVE — every record in every module is tamper-evident
TIER DISCIPLINE       ACTIVE — T0 proven · T1 validated · T2 hypothesis · T3 conjecture
LAW OF SILENCE        ACTIVE — agents communicate only through mediated EventEnvelope
CORPUS SOVEREIGNTY    ACTIVE — knowledge enters only through 5-phase RALPH pipeline
MEMBRANE INTEGRITY    ACTIVE — frozen file hashes verified at every session start
```

---

## License

AGPL-3.0-or-later · Copyright (C) 2025 Tarik Skalić (tarikskalic33@gmail.com)

Bihać, Bosnia-Herzegovina

Free to use, study, modify, and distribute. Derivative works must release source under the same terms.

---

*A finite automaton is a machine that remembers its state.*
*A hash-chained automaton is a machine that can prove it remembered correctly.*
