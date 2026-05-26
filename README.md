# AEGIS-Ω

**Constitutional AI Governance Runtime**

*Built by Tarik Skalić · AGPL-3.0*

[![Rust Tests](https://img.shields.io/badge/Rust_Tests-1798-brightgreen)](#testing)
[![Gate 8](https://img.shields.io/badge/Gate_8-passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue)](LICENSE)

---

## What It Does

AEGIS-Ω is a state-management and governance runtime for AI pipelines. Its core guarantee is **deterministic replay**: given the same sequence of inputs, the system always produces the same hashes, in the same order, on any platform (Linux, macOS, Docker, WASM, ARM, x86).

Every response from an AI model that passes through the pipeline is:

- **Hash-certified** — SHA-256 chained from request through response, stored immutably
- **Replay-verifiable** — the chain can be replayed from genesis to reconstruct any past state
- **Tier-classified** — claims in the system are tagged T0 (mechanically proven) through T3 (conjecture); nothing unproven sneaks into the governance layer
- **Entropy-bounded** — the ratio of adaptive decisions to replay-verifiable operations is tracked; if it exceeds `1/φ ≈ 0.618`, the system suspends mutation authority

This is auditing infrastructure, not a product with magic properties.

---

## Technical Architecture

```
sovereign-omega-v2/          TypeScript governance runtime
  src/core/canonicalize.ts   RFC 8785 canonical JSON serialization (canonicalizeJCS)
  src/core/hashing.ts        sha256Hex() — all integrity hashes flow through here
  src/frame/                 DFA, topology, lineage, epoch, divergence, attestation
  src/consensus/swarm.ts     BFT vote tallying at 1/φ quorum threshold
  src/constitutional/        Martingale certifier, reduction gate, guardian policy
  src/ledger/                Hash-chained LedgerChain, persistence seam
  python/bridge.py           HTTP bridge (port 7890) — /claude, /telemetry, /event

aegis-cl-psi/                Rust subsystem — gossip layer and mathematical gate modules
  src/                       319 gate modules, 1798 tests
  Cargo.toml                 sha2, serde, ed25519-dalek; no_std compatible
```

### How State Is Managed (TypeScript)

Every piece of governance state is:

1. **Canonicalized with RFC 8785** before hashing. `canonicalizeJCS(obj)` sorts JSON keys lexicographically and eliminates whitespace. This means `{"b":1,"a":2}` and `{"a":2,"b":1}` hash identically — field-insertion order is irrelevant.

2. **Hashed with SHA-256** via `hashValue(obj)` — which calls `sha256Hex(canonicalizeJCS(obj))`. Two objects with the same logical content always produce the same 64-character hex hash.

3. **Frozen immediately** with `deepFreeze()` after construction. No mutations can corrupt a record after it leaves the constructor.

4. **Sequenced with BigInt**, not `array.length` or `Date.now()`. Sequence numbers are allocated by `IndexedDBSequenceAllocator` and are strictly monotone.

5. **Stored in BTreeMap equivalents** (sorted arrays) rather than `Set`/`Map`. This prevents hash instability from iteration-order non-determinism.

The result: the same governance event sequence always produces the same chain of hashes, regardless of JavaScript engine or platform.

### How State Is Managed (Rust / aegis-cl-psi)

The Rust crate implements the gossip protocol layer — peer-to-peer message routing, rate limiting, liveness tracking, sequence enforcement, and epoch management. Each module follows the same pattern:

```rust
// Every record is hash-chained from a genesis hash of [0u8; 32].
// record_hash = SHA-256(prev_hash ‖ field_1 ‖ field_2 ‖ ... ‖ field_n)

fn compute_record_hash(prev: &[u8; 32], epoch: u64, sent: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());  // big-endian, platform-independent
    h.update(sent.to_be_bytes());
    h.finalize().into()
}
```

Key invariants enforced across all 319 modules:

- **No `HashMap`** — only `BTreeMap` and `BTreeSet`. Sorted iteration order is required for deterministic SHA-256 input.
- **No `f64`** — all arithmetic is integer, with `saturating_add`/`saturating_mul`/`min`. Floating-point nondeterminism is a known hazard for cross-platform replay.
- **Strictly monotone epochs** — any module that accepts epoch numbers returns `Err(StaleEpoch)` if the epoch is not strictly greater than the last recorded value.
- **`verify_chain()`** on every log — recomputes all hashes from stored field values and confirms each record's stored hash matches. Any in-memory or at-rest tampering is detected.

### What Makes It Immune to Logical Drift

"Drift" in this context means: the system's live state diverges from what can be reconstructed by replaying its event log. AEGIS prevents this through:

1. **Root law enforcement**: `AdaptivePower(T) ≤ ReplayVerifiability(T)`. The entropy budget (`entropy_budget.rs`) tracks every adaptive decision. If the adaptive ratio exceeds `1/φ`, `consume_adaptive()` returns an error and the caller cannot proceed.

2. **Martingale anchoring**: `certifyMartingale()` checks that the hash chain is valid (`is_anchored`), the chain shows zero drift (`drift_bounded`), and the adaptive ratio is within bounds (`entropy_bounded`). `assertMartingaleAnchored()` throws `MartingaleViolation` if any condition fails.

3. **Divergence classification**: D0 (observational) through D4 (constitutional invalidity). At D2+, mutation authority is suspended. The drift classifier (`drift_classifier.rs`) records every classification in a hash-chained log.

4. **Replay proof**: `constitutional_replay.rs` implements `State_t = Replay(Lineage_{0→t})`. The `ReplayProof` struct contains a `terminal_hash` and `replay_fingerprint` that can be independently verified.

---

## Testing

```bash
# Rust — aegis-cl-psi (gossip layer, 319 gate modules)
cd aegis-cl-psi && cargo test
# → 1798 tests, 0 failures

# TypeScript — sovereign-omega-v2 (governance runtime)
cd sovereign-omega-v2
npm install
npm run test && npm run typecheck && npm run build
# → ~2778 tests, 0 type errors, production build

# Python bridge smoke test
cd sovereign-omega-v2 && python python/tests/stress_test.py --quick
# → corruption_count === 0
```

The test suite is the specification. Every invariant in this document has a corresponding test that fails if the invariant is violated. The tests are not added after the fact — they are written gate-by-gate as the feature is implemented.

### What the Tests Cover

| Layer | Module | What Is Tested |
|-------|--------|---------------|
| Canonicalization | `canonicalize.ts` | RFC 8785 key ordering, BigInt serialization, Unicode stability |
| Hashing | `hashing.ts` | SHA-256 byte-identity across TS and WASM; Merkle root parity |
| Governance state | `topology.ts`, `lineage.ts`, `epoch.ts` | Hash chain integrity, tamper detection, scale to 100+ entries |
| BFT consensus | `swarm.ts` | 1/φ quorum boundary (61/100 passes, 62/100 suspends) |
| Martingale | `martingale.ts` | Anchoring, entropy bounding, violation cascade |
| Gossip protocol | `aegis-cl-psi/src/` | 319 modules: rate limiting, dedup, sequence tracking, liveness, backpressure, partition detection |
| Constitutional reduction | `reduction.ts` | T4/T5 concept rejection; all-mapping-present admission |

---

## Running the System

```bash
# Start the bridge (port 7890)
cd sovereign-omega-v2/python && python bridge.py

# Send a governed Claude request
curl -X POST http://localhost:7890/claude \
  -H 'Content-Type: application/json' \
  -d '{"messages": [{"role": "user", "content": "Hello"}], "model": "claude-sonnet-4-6"}'

# Response includes audit fields:
# { "content": "...", "request_hash": "abc...", "response_hash": "def...",
#   "chain_hash": "ghi...", "is_replay_reconstructable": true }

# Live telemetry
curl http://localhost:7890/telemetry
# → { "corruption_count": 0, "epoch": N, "drift_index": ..., "sequence": N }
```

---

## Known Limitations and Open Problems

This system has hard problems that are not solved, and we are not claiming otherwise:

1. **Cross-platform deterministic replay** — guaranteed for pure CPU operations; GPU nondeterminism (floating-point rounding differences between hardware) is an open problem.
2. **Verifier scalability** — the `verify_chain()` functions are O(n) over the full log. Long-running nodes will need periodic pruning or compaction.
3. **Replay state explosion** — storing the full event log indefinitely is not practical at scale. The `lineage_compactor.rs` module is a partial mitigation.
4. **Distributed topology hash stability** — when multiple nodes agree on a `topology_hash`, they must have identical serialization. Network partition scenarios are detected but not automatically resolved.
5. **Floating-point canonicalization** — `f64` values are banned from all hash inputs. Any caller that needs floating-point must convert to a fixed-precision integer before entering the hash chain.

---

## Repository Structure

```
aegis-cl-psi/          Rust crate — gossip protocol (319 modules, 1798 tests)
sovereign-omega-v2/    TypeScript governance runtime (~2778 tests)
  src/core/            Canonicalization, hashing, immutability primitives
  src/frame/           DFA, topology, lineage, divergence, epoch, attestation
  src/consensus/       BFT swarm, convergence
  src/constitutional/  Martingale, reduction gate, guardian policy
  src/ledger/          Hash-chained ledger, persistence seam
  python/              Bridge server, stress tests, gate validation
aegis-runtime/         Seven-pillar distributed agent runtime (Rust)
cockpit/               React chat UI with telemetry integration
studio/                Read-only constitutional observability dashboard
platform-picker/       Creator tool (Qwen-powered, $19)
hook-generator/        Creator tool (Qwen-powered, $19)
content-calendar/      Creator tool (Qwen-powered, $19)
hub/                   Products landing page
packages/shared/       Shared TS infrastructure (DashScope client, hooks, components)
docs/                  Architecture specifications
```

---

## Contributing

The codebase is open (AGPL-3.0). To contribute:

1. Every new module needs a `verify_chain()` function and tests for tamper detection.
2. No `HashMap`, no `f64` in hash inputs, no `Date.now()` outside `src/event/uuid.ts`.
3. Gate 8 (`npm run test && npm run typecheck && npm run build`) must pass before any commit.
4. New Rust modules: `BTreeMap` only, `saturating_*` arithmetic, strictly monotone epoch enforcement.

If you find a hash collision, a chain verification bypass, or a replay divergence between platforms — that is the most valuable bug report this project can receive.

---

## License

AGPL-3.0-or-later · Copyright (C) 2025 Tarik Skalić (tarikskalic33@gmail.com)

Free to use, study, modify, and distribute. Derivative works must release source under the same terms.
