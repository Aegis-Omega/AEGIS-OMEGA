---
name: int4-lut-kan
description: Invoked when the user asks about INT4 quantisation, LUT-KAN, Kolmogorov-Arnold Networks, cache-local inference, spline-free activation functions, or on-device inference optimisation for AEGIS. Source: AEGIS OMEGA Deployment-Certifiable, tier T2.
---

# INT4 LUT-KAN — Cache-Local Inference Without Spline Overhead

**Epistemic Tier: T2** — engineering hypothesis. LUT-KAN replaces B-spline activations with integer lookup tables; the inference speedup is analytically derivable; AEGIS-specific benchmarks are pending.

**Corpus Lineage:** `corpus_lineage_hash: pending-drive-access` · Source: AEGIS OMEGA Deployment-Certifiable (ARBITRATION: admitted T2; "civilizational evolution / self-improving" framing quarantined)

---

## Constitutional Claim

INT4 LUT-KAN replaces continuous B-spline activation functions in Kolmogorov-Arnold Networks with INT4 integer lookup tables, eliminating floating-point spline evaluation and enabling cache-resident inference on the AMD RX 570 (8 GB VRAM) — making KAN-based governance scoring viable within the AEGIS Python Layer B without exceeding the hardware memory envelope.

---

## Key Invariants

- **Spline elimination** — standard KAN uses learnable B-splines as activation functions; each spline evaluation requires float multiply-adds proportional to the spline degree; INT4 LUT replaces this with a single table lookup — O(1) per activation, cache-line aligned
- **INT4 quantisation** — activation inputs are quantised to 4-bit integers (16 representable values per input); the LUT has 16 entries per activation function, fitting in 64 bytes (one cache line); this makes activation evaluation cache-local even on a CPU L1 cache
- **AMD RX 570 compatibility** — the RX 570 has 2304 stream processors and 8 GB GDDR5; INT4 LUT operations can be vectorised via ROCm HIP kernels; the `hip` feature flag in `aegis-cl-psi` is the appropriate host
- **Determinism** — INT4 lookup is exact integer arithmetic (no rounding); the same input always produces the same output across AMD/NVIDIA/CPU; replay-safe by construction
- **Constitutional audit unchanged** — the INT4 LUT-KAN model produces a scalar score; that score feeds into the existing `callConstitutional()` hash-audit chain; the inference mechanism does not affect the hash chain topology

---

## AEGIS Integration Points

| Component | How INT4 LUT-KAN applies |
|-----------|--------------------------|
| `aegis-cl-psi/src/` | Rust gate module for INT4 LUT kernel; `#[cfg(feature = "hip")]` for ROCm, fallback to CPU table scan |
| `python/core_matrix.py` | M3 operator (the "verifier output" functional definition) is the natural slot for a KAN scorer; INT4 LUT-KAN replaces a future float-KAN M3 implementation |
| `python/hardware_config.py` | AMD RX 570 hardware profile should declare `int4_lut_kan: supported` once the Rust kernel is validated |
| `python/bridge.py` `/claude` endpoint | Governance scoring via LUT-KAN would produce a `kan_score` field alongside existing `chain_hash` in `ConstitutionalResponse` |

---

## Implementation Notes

```rust
// Pseudocode — INT4 LUT activation (no f64, deterministic)
fn lut_activation(input: i32, table: &[i32; 16]) -> i32 {
    // Clamp to [0, 15] and look up
    let idx = input.clamp(0, 15) as usize;
    table[idx]   // O(1), cache-local, no floating point
}
```

The `table` values are stored as `i32` (scaled fixed-point); the scaling factor must be a power of 2 so that the final result can be rescaled with a bit-shift, preserving the no-f64 invariant in hash inputs.

---

## Tier Promotion Criteria (T2 → T1)

1. Implement `lut_activation()` in a Rust gate module; 19-test viability ring must pass
2. Benchmark on AMD RX 570: confirm ≥2× throughput improvement over float B-spline activation at batch_size=256
3. Determinism: identical output across ROCm GPU, CPU fallback, and ARM across 3 runs

---

## Implementation Status (updated 2026-06-06)

**Criterion #1 — COMPLETE.** `lut_activation()` is implemented in
`aegis-cl-psi/src/int4_lut_kan.rs` with a full 20-test viability ring (the 19-test
ring + 1 cross-implementation parity test). `cargo test int4_lut_kan` → 20 passed.

Module surface:
- `lut_activation(input: i32, &Lut) -> i32` — clamped 16-entry lookup, no f64
- `quantize_int4(value, shift)` — power-of-two fixed-point → 4-bit index
- `KanLayer` / `KanScorer` — two-layer Kolmogorov-Arnold form, saturating i32
- `KanInferenceLog` — hash-chained scoring decisions; `verify_chain() → (bool, Option<usize>)`;
  `record_hash = SHA-256(prev ‖ seq_be8 ‖ input_fingerprint ‖ score_be4)`; genesis `[0u8;32]`

**Criterion #3 — PARTIAL (Rust ↔ Python parity proven).** A faithful Python port
in `agents/cognitive_pipeline.py` produces byte-identical fingerprints and record
hashes; the Rust test `fingerprint_matches_python_reference` asserts the exact
Python-computed values. Cross-platform determinism across ROCm/CPU/ARM remains
pending hardware access (Criterion #2 benchmark also pending).

**Orchestration.** The scorer is wired as the ARBITRATION gate of the Mythos
cognitive pipeline (`deep-research → corpus-ingestion → batch → chronology`).
Each candidate claim is quantised to four constitutional features
[evidence, determinism, t45_contamination, citation] and scored; the decision is
hash-chained and replay-certifiable. T4/T5 contamination is a hard veto regardless
of score. See `docs/MYTHOS_COGNITIVE_SUBSTRATE.md`.

Promotion note: criterion #1 met is necessary but not sufficient for T2→T1 — that
requires the ≥2× benchmark (criterion #2) AND tri-platform determinism (criterion #3).
The module remains **T2** until both land. (Test pass ≠ Correctness; the invariant holds.)

---

## Source

Admitted T2 engineering claim from corpus ARBITRATION (AEGIS OMEGA Deployment-Certifiable). Also admitted from same document: eBPF sandbox boundaries, SGM Hoeffding LCB bounds, TimescaleDB hypertable 2ms SLA — all as independent T2 patterns.
