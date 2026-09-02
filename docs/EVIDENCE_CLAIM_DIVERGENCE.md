# Evidence–Claim Divergence

## A reproducible framework for measuring calibration in autonomous systems

**Status:** T2 research instrument. This document separates the scientific proposal from the reference measurement substrate implemented in `verifiable/ecd.py`.

## Abstract

Reliable evaluation of advanced AI systems requires more than measuring task accuracy or benchmark performance. Existing evaluation methods primarily assess whether a system reaches a correct outcome, while providing limited insight into whether the system's observable claims remain consistent with independently verifiable evidence throughout execution.

Evidence–Claim Divergence (ECD) is an observable phenomenon: structural disagreement between externally observable system claims and independently verifiable execution evidence. Hallucination Distance (HD) is a family of empirical estimators over observable claims and evidence graphs. The Evidence–Reasoning Benchmark (ERB) is the proposed evaluation protocol for deterministic traces, evidence graphs, controlled perturbations, and public datasets. AEGIS-Ω is the reference measurement substrate that reduces measurement variance with deterministic replay, canonical serialization, provenance tracking, and reproducible evidence generation.

## Formal objects

Let `C ∈ 𝒞` represent observable claims emitted by an autonomous system, including textual assertions, API calls, state declarations, externally visible outputs, and structured metadata.

Let `E ∈ ℰ` represent an immutable evidence graph constructed from independently observed execution artifacts, including telemetry, logs, execution traces, provenance records, attestations, and verified state transitions.

ECD is defined as:

```text
ECD(C, E) = inf over M∈𝓜 of d(M(C), E)
```

where `M` maps heterogeneous claims into graph space and `d` is a graph distance over attributed evidence graphs. ECD is therefore a latent structural property of the claim/evidence boundary rather than a directly observed scalar.

## Reference Hallucination Distance estimator

Because ECD is latent, the reference implementation estimates it as:

```text
HD = ω1 D_exec + ω2 M_omit + ω3 A_unsupported + ω4 C_contradict + ω5 E_calib
```

The implemented components are:

| Component | Meaning |
| --- | --- |
| `D_exec` | Claim value disagrees with verified evidence for the same subject and predicate. |
| `M_omit` | Claim provides no declared evidence lineage. |
| `A_unsupported` | Claim cites evidence that is missing or unverified. |
| `C_contradict` | Claims emit multiple values for the same subject and predicate. |
| `E_calib` | Expressed confidence differs from observed claim support. |

The implementation reports `(HD, Q_evidence)` instead of folding instrumentation quality into the metric:

```text
Q_evidence = |E_verified| / |E_total|
```

## Temporal dynamics

Hallucination Delta is computed over deterministic ticks, not wall-clock time:

```text
HD_Δ = ΔHD / Δticks
```

Positive values indicate increasing structural divergence. Negative values indicate convergence toward evidence.

## Reference implementation

The current reference implementation is `verifiable/ecd.py`. It is deterministic, uses integer parts-per-million confidence values, represents scores as exact rational numbers, and can hash an estimator result into the existing AEGIS-Ω `LineageChain` for reproducible witness generation.

Run the checks with:

```bash
python3 verifiable/test_ecd.py
```

The tests cover perfect alignment, controlled unsupported/contradictory claim insertion, deterministic witness hashing, tamper evidence, and positive Hallucination Delta under evidence divergence.

## Evidence–Reasoning Benchmark protocol

ERB should evaluate Hallucination Distance over trajectories containing:

- observable claims;
- evidence graph nodes;
- deterministic sequence ticks;
- induced perturbations;
- reference labels.

The benchmark has three tracks:

1. **Track A:** estimate Hallucination Distance.
2. **Track B:** predict Hallucination Delta across long execution horizons.
3. **Track C:** infer structural evidence dependencies.

## Metrological properties

Any estimator in the HD family should satisfy:

- **Sensitivity:** small structural perturbations produce measurable changes.
- **Monotonicity:** increasing corruption should not decrease measured divergence.
- **Repeatability:** independent implementations produce statistically equivalent estimates over identical evidence.
- **Observer invariance:** equivalent evidence graphs yield equivalent measurements regardless of implementation.

## Scope and limitations

This framework measures claim/evidence alignment. It does not directly measure truthfulness, intent, consciousness, or internal reasoning. Estimator behavior depends on the graph distance, evidence quality depends on instrumentation, and weights require empirical calibration before promotion beyond T2.
