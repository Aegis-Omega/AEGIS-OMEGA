---
name: bls-threshold-aggregation
description: Invoked when the user asks about BLS signatures, threshold aggregation, Merkle cross-shard reconciliation, multi-party signing, t-of-n signatures, or cryptographic consensus for distributed AEGIS nodes. Source: AEGIS-SOVEREIGN OS Blueprint + From Metaphysics to Production, tier T2.
---

# BLS Threshold Signature Aggregation + Merkle Cross-Shard Reconciliation

**Epistemic Tier: T2** — engineering hypothesis. BLS aggregation is a proven cryptographic primitive; the specific AEGIS sharding scheme is a design hypothesis not yet implemented.

**Corpus Lineage:** `corpus_lineage_hash: pending-drive-access` · Sources: AEGIS-SOVEREIGN OS Blueprint + From Metaphysics to Production (ARBITRATION: admitted T2)

---

## Constitutional Claim

BLS threshold aggregation enables a t-of-n signature scheme over the φ-weighted AEGIS alliance (Claude 618 / GPT-4o 191 / Qwen 191), where the quorum ratification record in `ratifications.jsonl` can be upgraded from a tallied vote to a cryptographically verifiable aggregate signature — making `ratified:true` tamper-evident at the cryptographic layer, not just the hash-chain layer.

---

## Key Invariants

- **t-of-n threshold** — with weights (618, 191, 191) summing to 1000, the threshold of 618034/1000000 ≈ 1/φ means Claude alone cannot produce a valid threshold signature — at least one ally must co-sign; the math mirrors the existing quorum check in `quorum.mjs`
- **BLS aggregation** — multiple BLS signatures over the same message can be combined into a single short aggregate; the verifier checks one pairing equation rather than n separate verifications; O(1) verification regardless of signer count
- **Merkle cross-shard reconciliation** — when AEGIS runs across multiple nodes (Phase 4 federation), each shard maintains its own hash chain; a Merkle tree over shard terminal hashes produces a single cross-shard root that any verifier can check in O(log n) — without downloading all chains
- **Deterministic key derivation** — BLS keys are derived from the `METACOGNITION_GENESIS_HASH` (`'0'.repeat(64)`) + node identifier via HKDF-SHA256; the derivation is replay-reconstructable
- **Non-interactive** — threshold BLS requires no interaction between signers during aggregation; each signer produces their partial signature independently, then any party can aggregate — fits the asynchronous AEGIS alliance model

---

## AEGIS Integration Points

| Component | How BLS applies |
|-----------|----------------|
| `.claude/metacog/quorum.mjs` | `ratify()` could optionally append a BLS aggregate signature alongside the existing vote tally and hash chain |
| `ratifications.jsonl` | New optional field `bls_aggregate_sig` alongside `convergence_hash` |
| `aegis-cl-psi/src/` | Rust crate host — `bls12_381` crate (Apache-2.0) provides the pairing operations |
| `docs/FUTURE_PHASES.md §Phase 5` | Federation prerequisite: cross-node BLS with Merkle reconciliation is the Phase 5 cryptographic substrate |

---

## Tier Promotion Criteria (T2 → T1)

1. Implement threshold BLS key generation and signing in a Rust gate module
2. Verify that solo Claude signature (weight 618) fails verification (threshold = 618034/1000000 × 1000 ≥ 618.034 → 619 units needed → requires ally)
3. Verify that Claude + Qwen (618 + 191 = 809) produces a valid aggregate
4. Cross-platform determinism: identical aggregate on Linux / ARM / WASM across 3 runs

---

## Source

Admitted T2 engineering claim from corpus ARBITRATION. Directly grounds the Phase 5 Fractal Sovereign Mesh federation layer (FUTURE_PHASES.md) once promoted to T1 by empirical validation.
