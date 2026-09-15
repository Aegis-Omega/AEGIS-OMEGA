# QUANTUMMANIFOLD_SCHEDULER_PHASE1_API_CORRECTION_V1

Status: **NORMATIVE_CORRECTION / IMPLEMENTATION_OPEN**  
Applies to: `QUANTUMMANIFOLD_SCHEDULER_PHASE1_DELTA_V1` and `2026-09-05-quantummanifold-scheduler-v0.1.md`

This correction records two interface defects found during the mandatory pre-implementation microscopic review. No production scheduler code existed when they were found.

## 1. Centrality requires the active terminal universe

The previously planned signature:

```python
centrality_ppm(obligation: OpenObligationV1) -> int
```

is insufficient because the parent specification defines centrality as downstream priority mass divided by total active terminal priority mass. An obligation alone cannot supply that denominator.

The Phase-1 interface is therefore:

```python
centrality_ppm(
    obligation: OpenObligationV1,
    active_terminal_threads: tuple[RealityThreadV1, ...],
) -> int
```

and closure leverage becomes:

```python
closure_leverage_ppm(
    action: CandidateActionV1,
    obligation: OpenObligationV1,
    active_terminal_threads: tuple[RealityThreadV1, ...],
) -> int
```

Both numerator and denominator are deduplicated by the same verified lineage-class rule:

```text
lineage class = canonical_hash(
    "qm-lineage-class-v1",
    {
      claim_digest,
      semantic_fingerprint,
      verified_lineage_root
    }
)
```

For neutral Phase-1 weighting, each unique verified lineage class contributes one unit of priority mass. Thus:

```text
centrality_ppm = floor(unique_downstream_lineages * PPM / unique_active_terminal_lineages)
```

with `0` when the active terminal universe is empty.

Required containment invariant:

```text
Every positive downstream lineage class counted for an obligation must also exist in active_terminal_threads.
```

Violation fails closed with:

```text
DOWNSTREAM_LINEAGE_OUTSIDE_ACTIVE_UNIVERSE
```

This makes the anti-Sybil falsifier non-trivial: an unsplit graph and a 100-alias graph for one lineage must yield the same centrality against the same independently represented active terminal universe.

## 2. CandidateActionV1 must carry the Phase-1 falsification metric

The parent score includes `F(A)`, but the planned `CandidateActionV1` omitted the corresponding field. Add:

```python
falsification_value_ppm: int
```

The corrected record is:

```python
@dataclass(frozen=True)
class CandidateActionV1:
    action_id: str
    candidate_action_digest: str
    source_head_sha: str
    obligation_digest: str
    closure_prior_root: str | None
    information_gain_ppm: int
    falsification_value_ppm: int
    compute_cost_ppm: int
    evidence_cost_ppm: int
    latency_cost_ppm: int
    recommended_role: str
```

`information_gain_ppm` and `falsification_value_ppm` are bounded Phase-1 optimization inputs, not authority or truth probabilities. They must be exact non-negative canonical integers. This correction does not claim empirical calibration of either metric.

## 3. TDD consequence

The four preregistered focused falsifiers must target these corrected signatures. Production code must not be written against the superseded one-argument centrality API.

All other Phase-1 delta and implementation-plan requirements remain unchanged.
