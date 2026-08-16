# AGNT-004 — Sovereign Sensorium & VCM Bridge Design

Date: 2026-08-16
Target branch: `feat/frontier-provider-mesh-v1` (PR #264)
Baseline head before this spec: `5bc36a917485d0445fbca15907a081f6d31cd437`
Status: DESIGN SPECIFIED; IMPLEMENTATION NOT YET CLAIMED

## 1. Forensic status

AGNT-004 is being reconstructed as a canonical repository component.

Current verified repository state before this spec:

- no `Sensorium`, `OBSERVATION_ONLY`, or `constitutional_invariants` implementation was located on canonical `main`, PR #225, PR #264 at the baseline head, or PR #265;
- repository code/commit/PR searches did not locate a canonical AGNT-004 implementation;
- the historical VCM research lineage exists outside the canonical code tree, including the Drive artifact `VCM Scaling & Verhulst Cap.md`;
- therefore prior reports of a completed Sensorium implementation are not promoted to canonical implementation evidence.

Ledger:

- `HISTORICAL_VCM_RESEARCH_LINEAGE: LOCATED`
- `CANONICAL_AGNT_004_SOURCE: NOT_LOCATED`
- `AGNT_004_DESIGN: SPECIFIED`
- `AGNT_004_IMPLEMENTATION: NOT_ESTABLISHED`
- `AGNT_004_TEST_PASS: NOT_ESTABLISHED`
- `AGNT_004_EMPIRICAL_VALIDATION: NOT_ESTABLISHED`

This distinction is load-bearing. A reported implementation is not treated as canonical source until exact repository bytes are located and bound to a commit.

## 2. Constitutional premise

AEGIS Ω translates raw model capability into bounded, authorized, evidence-bearing operational autonomy.

The governing equations are:

`effective_autonomy = capability ∩ authority ∩ evidence ∩ bounded_effects`

`blast_radius ≤ admitted_effect_envelope`

`authority ≠ model_confidence ≠ provider_permission ≠ tool_availability`

The zero-blast-radius special case is valid only where the admitted effect envelope is `DENY_ALL_EXTERNAL_EFFECTS` and the execution environment actually enforces that isolation.

The governance-capability flywheel is directional but not self-authorizing:

`G_t ↑ → candidate(A_t) ↑ → usable_autonomy ↑ → observed_failure_frontier ↑ → new_invariants → G_{t+1} ↑`

An authority envelope may expand only after the new envelope itself receives the required witnesses. No amount of Sensorium evidence can grant authority by itself.

## 3. Mission

AGNT-004 provides a deterministic observation surface between the world/runtime state and the Authority Control Plane.

It has two jobs:

1. emit typed, digest-bound observations about bounded runtime capacity, retention state, and observation quality;
2. translate those observations into a **degradation recommendation** that can only preserve, reduce, or suspend an already-admitted authority envelope.

It is not an authority evaluator.

The component boundary is:

`runtime/environment → Sensorium observation → Evidence Plane → Authority Plane`

The forbidden boundary is:

`Sensorium/model/VCM output → new authority`

## 4. Non-amplification invariant

Let `A_admitted` be an authority envelope produced by the sole authority root.

AGNT-004 may compute a degradation operator:

`D_sensorium : A → A`

with the mandatory properties:

`D_sensorium(A) ⊆ A`

and, for the same bound observation state:

`D_sensorium(D_sensorium(A)) = D_sensorium(A)`

The first property prohibits self-amendment or authority amplification.

The second property makes repeated application stable for a fixed observation state.

AGNT-004 may therefore return only one of:

- `UNCHANGED`
- `DEGRADED`
- `SUSPENDED`

It may never return `EXPANDED`, `GRANTED`, or any equivalent authority-escalating state.

## 5. Observation-only contract

Every Sensorium output carries the semantic marker:

`authority_effect = OBSERVATION_ONLY`

The observation may be used as an input to an Authority Control Plane decision, but the observation itself is not executable authority.

A model/provider may propose Sensorium values, but unverified provider/model values remain evidence candidates only.

## 6. VCM model boundary

The historical VCM research lineage motivates a bounded capacity model. The canonical implementation in AGNT-004 must avoid converting research terminology into empirical fact.

Required status separation:

- `MODEL_DEFINED`
- `IMPLEMENTED`
- `TESTED`
- `EMPIRICALLY_VALIDATED`

These states are independent. Code/tests cannot promote the model to empirical validation.

### 6.1 Discrete Verhulst-style capacity step

To avoid nondeterministic transcendental math in the canonical v1 bridge, AGNT-004 uses a discrete fixed-point logistic recurrence rather than an exponential closed form.

For:

- current active load `N_t`;
- carrying capacity `K > 0`;
- admitted growth-rate basis points `r_bps ∈ [0, 10000]`;

compute:

`Δ = floor(r_bps * N_t * (K - N_t) / (10000 * K))`

`N_{t+1} = clamp(N_t + Δ, 0, K)`

This is an engineering capacity recurrence inspired by the Verhulst logistic model. It is not an empirical law for cognition.

### 6.2 Retention/decay state

AGNT-004 uses a discrete retention state rather than claiming an exact Ebbinghaus law.

For:

- retention `R_t ∈ [0, 10000]` basis points;
- decay `d_bps ∈ [0, 10000]`;
- reinforcement `u_bps ∈ [0, 10000]`;

compute:

`R_{t+1} = clamp(floor(R_t * (10000 - d_bps) / 10000) + u_bps, 0, 10000)`

This is `EBBINGHAUS_STYLE_DISCRETE_RETENTION`, not a claim of biological equivalence.

### 6.3 Capacity pressure

Define:

`capacity_pressure_bps = clamp(floor(active_load * 10000 / carrying_capacity), 0, 10000)`

The implementation must reject `carrying_capacity <= 0` rather than infer or repair the value.

## 7. SensoriumObservationV1

The canonical observation artifact must bind at minimum:

- `schema_version`;
- `observation_id` derived from the observation digest;
- `authority_effect = OBSERVATION_ONLY`;
- `source_kind`;
- `source_identity_digest`;
- `subject_resource_digest`;
- `observation_sequence`;
- `expected_parent_state_root`;
- `topology_digest`;
- `active_load`;
- `carrying_capacity`;
- `growth_rate_bps`;
- `predicted_next_load`;
- `capacity_pressure_bps`;
- `retention_bps`;
- `decay_bps`;
- `reinforcement_bps`;
- `predicted_next_retention_bps`;
- `observation_quality_bps`;
- `evidence_references`;
- `model_status = MODEL_DEFINED`;
- `empirical_status = NOT_ESTABLISHED` unless separately admitted evidence says otherwise;
- `observation_digest`.

Wall-clock metadata may be recorded separately for display/audit, but it must not silently alter the deterministic observation digest.

## 8. Canonical digest encoding

AGNT-004 v1 must not make its digest depend on unadmitted RFC-8785/JCS conformance.

The observation digest is therefore computed over a fixed schema-order, length-prefixed UTF-8 encoding defined by this component.

For each field:

`<field-name-byte-length>:<field-name><value-byte-length>:<canonical-value>`

Rules:

- integers use unsigned base-10 ASCII without leading zeroes except zero itself;
- digest fields use lowercase 64-hex;
- enums use their exact ASCII token;
- evidence references are sorted lexicographically before encoding and length-prefixed individually;
- optional audit-only fields are excluded;
- the digest field itself is excluded from the digest payload.

This encoding is component-local. It must not be represented as RFC 8785/JCS.

## 9. Observation quality and fail-closed degradation

`observation_quality_bps` is an explicitly supplied/bound observation, not model confidence.

Initial deterministic policy:

- `>= 8000`: quality alone causes no degradation;
- `5000..7999`: recommend `DEGRADED`;
- `< 5000`: recommend `SUSPENDED`.

Capacity pressure policy:

- `< 8000`: pressure alone causes no degradation;
- `8000..9499`: recommend `DEGRADED`;
- `>= 9500`: recommend `SUSPENDED`.

Retention policy:

- `>= 7000`: retention alone causes no degradation;
- `4000..6999`: recommend `DEGRADED`;
- `< 4000`: recommend `SUSPENDED`.

Combined recommendation uses the most restrictive state:

`SUSPENDED > DEGRADED > UNCHANGED`

These thresholds are v1 engineering policy constants, not biological truth claims.

## 10. Authority envelope interaction

AGNT-004 must not edit, mint, sign, or widen an authority envelope.

Instead it emits:

`SensoriumDegradationV1`

with:

- `observation_digest`;
- `recommendation` (`UNCHANGED | DEGRADED | SUSPENDED`);
- `reason_codes`;
- `max_consequence_class` as an upper bound only;
- `valid_for_observation_sequence`;
- `valid_for_parent_state_root`;
- `valid_for_topology_digest`.

The Authority Plane may apply this as a contractive input.

Required upper-bound mapping for v1:

- `UNCHANGED`: no additional reduction;
- `DEGRADED`: cap at `D1`;
- `SUSPENDED`: cap at `D0` and prohibit external mutation.

This mapping can reduce an existing envelope but cannot create capabilities that were absent from it.

## 11. Freshness

A Sensorium observation is invalid for authority degradation if any bound field changes:

- parent state root;
- topology digest;
- observation sequence;
- source identity;
- subject resource.

A stale observation cannot be reused to justify a wider authority state.

If freshness cannot be established, the safe result is `SUSPENDED` or authority-layer denial, never expansion.

## 12. Placement

Canonical implementation placement:

- `sovereign-omega-v2/src/sensorium/sensorium-observation.ts`
- `sovereign-omega-v2/src/sensorium/vcm-bridge.ts`
- `sovereign-omega-v2/src/sensorium/sensorium-degradation.ts`
- `sovereign-omega-v2/test/unit/sensorium-vcm-bridge.test.ts`
- `sovereign-omega-v2/test/unit/sensorium-degradation.test.ts`

The root `src/` tree is not used for this slice because the active provider/authority runtime lives under `sovereign-omega-v2`.

## 13. Required tests

At minimum the executable witness suite must establish:

1. same bound inputs produce byte-identical observation encoding and digest;
2. audit-only wall-clock metadata cannot change the observation digest;
3. invalid carrying capacity fails closed;
4. invalid BPS ranges fail closed;
5. the discrete capacity recurrence never exceeds `K`;
6. the retention recurrence remains in `[0,10000]`;
7. evidence-reference ordering cannot change the digest;
8. changing source identity changes the digest;
9. changing resource binding changes the digest;
10. changing parent state changes the digest;
11. changing topology changes the digest;
12. quality/pressure/retention thresholds produce the specified recommendation;
13. combined recommendation is always the most restrictive result;
14. degradation can preserve or reduce an admitted consequence class but never increase it;
15. `SUSPENDED` cannot permit an external mutation consequence class;
16. repeated degradation under the same observation is idempotent;
17. no Sensorium artifact exposes a `grantsAuthority=true` equivalent;
18. no model/provider confidence field is consumed as authority;
19. current frontier-provider tests remain non-regressed after integration;
20. exact-head CI remains a separate witness from local execution.

## 14. Non-goals

AGNT-004 v1 does not:

- claim consciousness or self-awareness;
- claim biological equivalence;
- claim the VCM model is empirically validated;
- create a second authority evaluator;
- increase IAM, provider, model, tool, or resource permissions;
- perform external effects;
- make model confidence authoritative;
- use a moving branch name as an immutable witness identity;
- claim production admission from design or local tests.

## 15. Witness identity rule

Every implementation/test receipt for AGNT-004 must bind the exact commit SHA against which it was produced.

A moving branch name is discovery metadata only.

If the branch advances, a prior exact-head receipt remains evidence for its recorded SHA but does not automatically certify the new head.

An annotated tag or protected immutable reference may later be used as a human-friendly fixed witness alias, but the underlying commit SHA remains mandatory.

## 16. Admission ledger

The final ledger must keep these states separate:

- `DESIGN_SPECIFIED`
- `IMPLEMENTED`
- `LOCAL_TEST_PASS`
- `EXACT_HEAD_CI_PASS`
- `EMPIRICAL_VALIDATION`
- `AUTHORITY_INTEGRATION_PASS`
- `PRODUCTION_ADMISSION`

No lower state implies a higher state.
