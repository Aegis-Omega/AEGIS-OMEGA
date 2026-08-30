# Constitutional Execution Substrate

The constitutional substrate provides deterministic replay-verifiable enforcement primitives for provenance continuity, invariant validation, entropy containment, and schema-governed archival persistence.

## Epistemic Tier

T0 — mechanically verified. All primitives are pure functions over fixed-size types.
Zero floating-point arithmetic. Zero external runtime dependencies.

## Scope

| Module | Primitives | Role |
|--------|-----------|------|
| `primitives` | `StateHash`, `InvariantViolation`, `ProvenanceReference`, `OntologyReference` | Core types and Q16.16 arithmetic |
| `replay` | `ReplayEvent`, `ReplayLedger`, `ChainHasher` | Append-only deterministic ledger |
| `entropy` | `EntropyVector` | Entropy boundary enforcement |
| `attestation` | `VerifierAttestation` | Verifier class admission (V1–V3 only for VCG) |
| `archive` | `ArchiveVersion`, `ArchiveHeader` | Schema-versioned persistence |

## Explicit Non-Scope

The substrate does **not** implement:
- Cognition claims or autonomous reasoning
- Ontology authority (docs/ONTOLOGY.md is the single source of truth)
- Semantic generation or interpretation
- Recursive abstraction logic
- Universal architecture claims

Complex governance logic remains in `invariant-checker.ts`, `ralph-loop.ts`, `ONTOLOGY.md`, and `TRACEABILITY.md`.

## Determinism Guarantee

- Q16.16 fixed-point arithmetic throughout — no `f32` or `f64`
- All serialization is little-endian with explicit field ordering
- Wire formats are frozen at v1.0.0 — documented in each module
- `cargo test` produces identical results on any conforming Rust target

## Integration Boundary

SHA-256 computation is provided by callers via the `ChainHasher` trait.
The substrate stores and chains hashes; it does not compute them.
This preserves constitutional minimalism: zero cryptographic dependencies.

## Governance

Evolution rules: `docs/SUBSTRATE_EVOLUTION.md`
Replay laws: `docs/REPLAY_CONSTITUTION.md`
Telemetry spec: `docs/TELEMETRY_SPEC.md`
Ontology: `docs/ONTOLOGY.md`
Traceability: `docs/TRACEABILITY.md`

## Building

```bash
cd crates/constitutional-substrate
cargo test        # 50 tests, all passing
cargo build       # zero warnings in library target
```
