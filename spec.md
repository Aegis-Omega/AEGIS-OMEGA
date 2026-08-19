# AEGIS Ω Constitutional Invariants — Epoch 6

Status: repository-bound constitutional premise candidate.

This specification formalizes three fail-closed invariants that govern autonomy, external effects, and perception.

## Ω1 — Useful Autonomy Equation

UsefulAutonomy = Capability ∩ BoundedAuthority ∩ VerifiableRecovery

Operational rules:
- no verified recovery path => `RECOVERY_PATH_UNVERIFIED`;
- empty capability/authority intersection => `EMPTY_AUTONOMY_INTERSECTION`;
- admitted capability set is exactly the deterministic set intersection;
- capability presence never creates authority.

## Ω2 — Blast Radius Invariant

BlastRadius ≤ AdmittedEffectEnvelope

`BlastRadius = 0` is claimable only when complete isolation with no external-effect capability is established. The general implementation must reject network, tool, or financial effects outside the admitted envelope using `BLAST_RADIUS_EXCEEDED`.

## Ω3 — Perception != Authority

Sensorium → OBSERVATION_ONLY/T2 → candidate world state → Authority Control Plane.

Sensorium output is constitutionally fixed to:
- `authorityEffect = OBSERVATION_ONLY`;
- `observationTier = T2`;
- `authorityWeight = 0`;
- `mayGroundStateTransition = false`.

Perception alone cannot authorize mutation. A mutation request without an independently supplied PCWO/AAP authority token fails with `MUTATION_BLOCKED_PERCEPTION_CANNOT_PRODUCE_AUTHORITY`. Even when an external token exists, Sensorium does not execute the mutation; it emits an observation requiring external authority evaluation.

## Admission semantics

Implementation presence is not canonical admission. AGNT-004 code already present in PR #264 remains quarantined until this constitutional bundle is in the same lineage and the exact candidate is re-fetched and evaluated.

`OBSERVED != AUTHORITY`
`CAPABILITY != AUTHORITY`
`AUTHORITY != EXECUTION`
`EXECUTION != EVIDENCE`
`EVIDENCE != ADMISSIBLE CLAIM`

## Falsification requirement

The constitutional implementation is tested with a dependency-free Node `node:test` suite. The suite must fail before implementation exists and pass all 35 named falsification cases after implementation. Exact-head GitHub CI remains a separate admission state and cannot be inferred from a local witness.
