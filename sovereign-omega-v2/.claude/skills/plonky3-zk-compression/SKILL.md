---
name: plonky3-zk-compression
description: Invoked when the user asks about Plonky3, zero-knowledge proofs, Mersenne-31 field, ZK proof compression, fast proof generation, or ZK-SNARKs for governance audit chains. Source: AEGIS-SOVEREIGN OS Blueprint + From Metaphysics to Production, tier T2.
---

# Plonky3 over Mersenne-31 — ZK Proof Compression

**Epistemic Tier: T2** — engineering hypothesis. <10ms latency is the vendor benchmark; verification on AEGIS-specific proof shapes is pending.

**Corpus Lineage:** `corpus_lineage_hash: pending-drive-access` · Sources: AEGIS-SOVEREIGN OS Blueprint + From Metaphysics to Production (ARBITRATION: admitted T2, "thermodynamic overload framing" quarantined)

---

## Constitutional Claim

Plonky3 operating over the Mersenne-31 prime field achieves sub-10ms proof generation for governance audit trails, making ZK-compressed proofs viable as a T0-upgrade path for the AEGIS hash chain — where the proof *is* the replay certificate rather than the chain hash alone.

---

## Key Invariants

- **Mersenne-31 field** — `p = 2^31 − 1`; modular arithmetic is a single conditional subtraction, making it the fastest 32-bit prime field on standard CPUs; no special hardware required
- **<10ms proof time** — Plonky3's FRI-based construction generates proofs for circuits of ~10^5 gates in under 10ms on x86 hardware; this is the vendor benchmark from the Polygon ZK team
- **Proof size ≤ 100KB** — for governance-scale circuits (replay verification, hash chain), Plonky3 proofs are compact enough to store as entries in the AEGIS hash chain without bloating the ledger
- **Deterministic across platforms** — Mersenne-31 arithmetic is defined over integers; the same circuit produces the same proof on Linux/ARM/WASM given identical witness inputs — replay-safe
- **Additive to existing hash chain** — the Plonky3 proof does not replace `entry_hash`; it is an optional second field `zk_proof_hash` in `MetacognitiveEntry`, enabling verifiers to check replay integrity without re-running the full chain walk

---

## AEGIS Integration Points

| Component | How Plonky3 applies |
|-----------|---------------------|
| `src/metacognition/loop.ts` | Optional `zk_proof_hash` field alongside `entry_hash`; proof is computed over the (prev_hash, observation, sequence) tuple |
| `aegis-cl-psi/src/` | Rust crate is the natural host — Plonky3 has a pure Rust implementation; gate module would expose `prove_chain_step()` and `verify_chain_step()` |
| `.claude/metacog/chain.mjs` | `certify()` could optionally verify Plonky3 proofs if present alongside SHA-256 hashes |

---

## Tier Promotion Criteria (T2 → T1)

1. Implement `prove_chain_step()` in a Rust gate module in `aegis-cl-psi/src/`
2. Benchmark on AEGIS observation chain: confirm <10ms for circuits up to `entry_count=10000`
3. Verify cross-platform determinism: identical proof on Linux x86, ARM, and WASM across 3 runs (per testing.md rule)

---

## Source

Admitted T2 engineering claim from corpus ARBITRATION. "From Metaphysics to Production" also admitted: polyglot microservices (Rust/Python/C++/Go), PBFT Merkle sharding, 5s Darwin Prover timeout, Matter-Hash load-shedding as T2 patterns.
