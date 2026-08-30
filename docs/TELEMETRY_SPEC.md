# Telemetry Constitutionalization Specification
## Epistemic Tier: T1
## Status: Active

Telemetry is constitutionally typed epistemic state — not observational output.
No metric may appear in telemetry output without:
(a) ontology registration,
(b) provenance linkage,
(c) invariant admissibility review.

Telemetry semantics may not drift independently from constitutional interpretation.

---

## Admissibility Rule

A metric is constitutionally admissible when all of the following hold:

1. **Ontology registration**: term appears in `docs/ONTOLOGY.md`
2. **Provenance linkage**: grounded in `docs/TRACEABILITY.md` at T0–T2
3. **Deterministic computation path**: no floating-point, no wall-clock time, no random sources
4. **Invariant binding**: either mapped to an existing INV-* or accompanied by a new one
5. **Replay declarability**: the metric can be reconstructed from the replay archive

---

## Metric Definitions

### METRIC: afse_r2

**1. Metric Definition**
AFSE correlation coefficient. Measures the R² correlation between local AMD RX 570
throughput samples and the distributed topology baseline (1000 eps). A value of 1.0
indicates perfect scaling generalisation from consumer hardware to distributed topologies.

**2. Provenance Source**
`python/tgcs_afse.py` — `AFSEController._compute_r_squared()` (T1 empirical)
Grounded in: stress_test.py P2 validation (R²=0.9976 across 1000 crash loops)
TRACEABILITY.md: `tgcs_afse.py holonic_scaling_score()` → RFC 2544 (IETF, 1999)

**3. Deterministic Computation Path**
```
events → AFSEController.record_event(sequence) → _local_samples list →
_compute_r_squared() → Pearson R² via integer arithmetic on sample list
```
No floating-point: Python computation uses integer division approximation.
No wall-clock time: sequence numbers from event substrate only.

**4. Constitutional Invariant Binding**
INV-09: `afse_r2 ≥ 0.98 when pgcs_passes` — T1_ALERT severity
Violation does not halt execution; it surfaces to operator via TelemetryPanel Layer B section.
Substrate enforcement: `EntropyVector` threshold pattern.

**5. Entropy Impact**
afse_r2 degradation (< 0.98) indicates scaling entropy has crossed the calibration boundary.
The metric provides entropy observability, not entropy enforcement.
Entropy impact is bounded: afse_r2 ∈ [0.0, 1.0] with 0.98 as the constitutional floor.

**6. Replay Requirements**
afse_r2 is reconstructable from the sequence of `record_event(sequence)` calls in replay.
The sample list must be archived as part of the epoch checkpoint for full reconstruction.
Archive format: ARCHIVE_V1_0_0 (see docs/SUBSTRATE_EVOLUTION.md RULE-03).

**7. Archive Serialization Rules**
Serialised as Q16.16 fixed-point integer (i64 LE) when stored in a CycleArchive.
Wire field name: `afse_r2_fixed`. Float presentation in telemetry JSON is a display layer
concern only — the canonical value is always the Q16.16 integer.

**8. Failure Semantics**
If afse_r2 is absent from telemetry: INV-09 is vacuously satisfied (metric not yet wired).
If afse_r2 < 0.98 and pgcs_passes: T1_ALERT raised, operator attention required.
If afse_r2 = 0.0 after PGCS passes: indicates empty sample set — bridge restart required.

---

### METRIC: tgcs_variance

**1. Metric Definition**
TGCS run-to-run cycle timing variance σ². Measures thermal throttling impact on AMD RX 570
under sustained inference load. σ² = 0 is the constitutional success criterion.

**2. Provenance Source**
`python/tgcs_afse.py` — `TGCSController._compute_variance()` (T1 empirical)
Grounded in: stress_test.py P2 validation (σ²=0 across all 1000 crash loop runs)
TRACEABILITY.md: `tgcs_afse.py holonic_scaling_score()` (same file)

**3. Deterministic Computation Path**
```
thermal read → regulate_cycle(sequence) → _cycle_seqs list →
_compute_variance() → integer variance over sequence-number deltas
```
No wall-clock time: cycle timing is measured in sequence-number deltas, not milliseconds.
Thermal temperature reading (psutil/GPU) is the only non-deterministic input.
Non-determinism is constitutional: thermal state is a physical observable, not computed.

**4. Constitutional Invariant Binding**
INV-10: `tgcs_variance = 0` — T1_ALERT severity
Non-zero variance indicates thermal instability. Operator may choose to stretch cycles
via `TGCSController.regulate_cycle()` to restore σ² = 0.

**5. Entropy Impact**
Non-zero tgcs_variance increases timing entropy in the computation substrate.
The TGCS cycle stretcher is the entropy reduction mechanism: it trades latency for consistency.
Constitutional guarantee: σ² = 0 after TGCS stretch is applied.

**6. Replay Requirements**
tgcs_variance is NOT reconstructable from the event replay alone (thermal readings are physical).
On replay, tgcs_variance is treated as an informational annotation, not a deterministic value.
This is a constitutional exception: physical observables are exempt from replay reconstruction.

**7. Archive Serialization Rules**
Serialised as Q16.16 fixed-point i64 LE. Wire field name: `tgcs_variance_fixed`.
Non-zero archived values are historical annotations, not replay inputs.

**8. Failure Semantics**
If absent: INV-10 vacuously satisfied.
If non-zero: T1_ALERT; operator should allow thermal recovery or increase stretch_ms.
If thermal read fails: `tgcs_variance = 0` (safe default — no false alert on read failure).

---

### METRIC: holonic_scaling_score

**1. Metric Definition**
Composite scaling quality score: `R² × effective_bandwidth / DISTRIBUTED_BASELINE_EPS`.
Where `effective_bandwidth = mean_throughput × (1 - normalised_entropy)`.
Quantifies the holonic scaling behaviour — how well the organism-scale runtime
generalises to the field scale (distributed topologies).

**2. Provenance Source**
`python/tgcs_afse.py` — `AFSEController.holonic_scaling_score()` (T2 engineering hypothesis)
External ground: RFC 2544 (IETF, 1999) — effective bandwidth as throughput × stability composite
TRACEABILITY.md: `tgcs_afse.py holonic_scaling_score()` → RFC 2544

**3. Deterministic Computation Path**
```
afse_r2 × effective_bandwidth / 1000.0
→ integer approximation: (r2_fixed * eff_bw_fixed) >> 16 / DISTRIBUTED_BASELINE_FIXED
```
All intermediate values in Q16.16. Division by baseline is the only precision-sensitive step.

**4. Constitutional Invariant Binding**
No dedicated invariant at this time (T2 hypothesis). Displayed in TelemetryPanel for
operator observation. Promoted to T1 with an INV-11 binding once sufficient empirical
data exists (minimum: P3 full stress test validation).

**5. Entropy Impact**
holonic_scaling_score summarises the entropy state of the organism→field transition.
A declining score indicates increasing entropy at the scale transition boundary.
Score thresholds: > 0.95 (nominal), 0.80–0.95 (attention), < 0.80 (alert).

**6. Replay Requirements**
Reconstructable from replay if the afse sample list and throughput history are archived.
Reconstruction path is the same as afse_r2 plus the effective_bandwidth computation.

**7. Archive Serialization Rules**
Serialised as Q16.16 fixed-point i64 LE. Wire field name: `holonic_scaling_score_fixed`.

**8. Failure Semantics**
If absent: no invariant violation. Score is informational until elevated to T1.
If score < 0.80: surfaced in TelemetryPanel with amber indicator.
If afse_r2 = 0: holonic_scaling_score = 0 (correct — no data = no scaling claim).

---

### METRIC: governance_throughput

**1. Metric Definition**
Ralph cycles completed per sequence-span unit: `completed_cycles / sequence_span`.
Measures the rate of governance cadence relative to event production volume.
Uses sequence numbers, not wall-clock time — determinism invariant preserved.

**2. Provenance Source**
`sovereign-omega-v2/src/core/ralph-loop.ts` — `governanceThroughput()` (T2 engineering hypothesis)
ChatGPT adversarial audit (CONFIDENCE 0.96): "next scalability bottleneck is likely
governance throughput, not implementation throughput."
TRACEABILITY.md: `src/core/ralph-loop.ts — governanceThroughput()`

**3. Deterministic Computation Path**
```
completedCycles (integer) / sequenceSpan (integer) → number
```
Pure integer division. No Date.now(). No external state. Deterministic and replayable.

**4. Constitutional Invariant Binding**
No dedicated invariant at this time. Alert threshold: < 1/1000 cycles per sequence unit
indicates governance is falling behind event production — backpressure should engage.
Candidate for INV-11 promotion after P3 empirical validation.

**5. Entropy Impact**
Declining governance_throughput increases the latency of invariant enforcement,
which allows entropy to accumulate undetected. The metric is an early warning signal,
not an enforcement mechanism.

**6. Replay Requirements**
Fully reconstructable from replay. `completed_cycles` = count of COHERENT cycles in
the exported CycleArchive. `sequence_span` = archived_at_sequence - initial_sequence.

**7. Archive Serialization Rules**
Not stored directly. Computed on read from CycleArchive fields:
`total_cycles / archived_at_sequence`. Wire representation is derived, not primary.

**8. Failure Semantics**
If sequenceSpan = 0: returns 0 (safe, no throughput measurable).
If completedCycles = 0 and sequenceSpan > 0: governance stalled — operator alert required.
Below 1/1000 threshold: backpressure should be applied upstream by BackpressureController.

---

## Pending Admissibility Reviews

| Metric | Status | Blocking Issue |
|--------|--------|----------------|
| `holonic_scaling_score` | T2 provisional | Requires P3 stress test validation for T1 elevation |
| `governance_throughput` | T2 provisional | Requires empirical bottleneck data for INV-11 binding |
| `calibrator_passes_100k` | T1 admitted | Admitted in prior cycle; full spec pending |

---

## Amendment Process

To add a new metric to telemetry output:
1. Define all 8 sections in this document
2. Obtain ontology registration in ONTOLOGY.md
3. Add provenance entry to TRACEABILITY.md
4. Add or cite an existing INV-* binding (or explicitly state "T2 provisional")
5. Add TypeScript interface field to `TelemetrySnapshot` in `cockpit/src/lib/telemetry.ts`
6. If adding an invariant: add to `invariant-checker.ts` with test coverage
7. PR description must include "Telemetry admissibility: [metric name] — all 8 sections satisfied"
