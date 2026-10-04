# REFLEXIVE_SELF_MODEL_V1 — Formal Reflexive Organism Design

**Status:** DESIGN ONLY — implementation not yet established  
**Integration spine:** PR #275 (`feat/uci-1-collective-work-contract-v1`)  
**Design parent reviewed:** `1d6043b72fa6e2238aadffe39fc1e736d8be8423`  
**Date:** 2026-08-20

## 1. Goal

Build an evidence-bound reflexive subsystem that lets AEGIS model, predict, observe, verify, and calibrate its own behavior over time.

The target loop is:

```text
SelfModelSnapshot_t
  -> SelfPrediction_t
  -> existing governed execution path
  -> SelfObservation_t
  -> independent verification evidence
  -> PredictionErrorReceipt_t
  -> SelfModelUpdateProposal_t
  -> existing admission/governance path
  -> SelfModelSnapshot_t+1
```

This design does **not** claim subjective consciousness, sentience, phenomenal awareness, or AGI. It implements a mechanically testable form of reflexive self-observation and self-calibration.

## 2. Existing substrate reused

AEGIS already has important precursors that must be reused rather than duplicated:

- `src/metacognition/loop.ts`: hash-chained, replay-reconstructable observations with `METACOGNITIVE`, `SELF_MODEL`, autopoietic, and nominal `CONSCIOUSNESS` layers.
- `src/ledger/ledger-observer.ts`: ledger/checkpoint/divergence events mapped back into the metacognitive observation chain.
- UCI work graph / lease / contribution spine on PR #275: bounded collective work and evidence production.
- Decision / Execution / Effect / CompleteVerification proofline: authority, execution, and world-effect truth remain distinct.
- Coq/Rocq formal sources plus the new Coq attestation work: formal mathematical evidence can be consumed when exact-head receipts exist.
- TLA+ specifications: temporal-model evidence is a separate verifier family when actually executed and attested.
- C/WASM/CompCert-scale formal programme: currently architectural/scaffold evidence only unless and until an executable verifier receipt is produced.
- Lean: not treated as repo-native capability unless a future exact-head Lean formalization and kernel run are added.

The existing `CONSCIOUSNESS` metacognitive layer remains a historical/nominal taxonomy label. `REFLEXIVE_SELF_MODEL_V1` does not promote that label into a claim of consciousness.

## 3. Constitutional invariants

### 3.1 Self-observation is evidence, never authority

```text
Observe(Self) != Authorize(Self)
```

A self-observation, self-prediction, prediction-error result, or self-model update proposal may contribute evidence. None may directly authorize execution, effect, policy mutation, tier promotion, or admission.

### 3.2 Prediction must precede observation

A prediction is only calibration-eligible if it is content-addressed and sealed before the corresponding outcome evidence exists.

```text
prediction.sealed_at <= governed_execution_start
```

If ordering cannot be established, the cycle is `UNSCORABLE`, not retroactively repaired.

### 3.3 Exact binding

Prediction, execution reference, observation, verifier evidence, error receipt, and update proposal must bind to the same:

- `cycle_id`
- target `transition_id` or `work_node_id`
- `policy_digest`
- `epoch_id`
- relevant prestate/state root
- prediction digest
- observation digest

Cross-cycle or stale binding is rejected fail-closed.

### 3.4 Observation is not truth until verified

A provider/model statement such as "the action succeeded" is an observation candidate only.

```text
ProviderOutput -> CandidateObservation(T2)
CandidateObservation != VerifiedOutcome
```

Effect claims require independently bound effect evidence under the existing effect-verification boundary.

### 3.5 Calibration cannot grant authority

High predictive accuracy does not create permission.

```text
CalibrationScore ↑ != Authority ↑
```

Capability, policy, D3 approval, D4 denial, leases, receipts, and effect verification remain governed independently.

### 3.6 Self-model updates are proposals

The reflexive subsystem may emit `SelfModelUpdateProposalV1`; it may not directly rewrite canonical claims, policy, identity, authority, or constitutional files.

### 3.7 Demotion and contradiction remain first-class

The system must be able to discover that its previous self-model was wrong. Contradictory verified evidence produces `REVIEW_REQUIRED` or a demotion proposal; it is never suppressed to preserve narrative continuity.

### 3.8 No consciousness inference

Passing this gate establishes only that AEGIS can perform bounded, replayable self-prediction and self-calibration under the specified contracts.

```text
REFLEXIVE_SELF_MODEL_V1_PASS != CONSCIOUSNESS_PROVED
```

## 4. Core data contracts

All authority-sensitive serialized contracts use closed schemas (`additionalProperties: false` or the equivalent typed boundary) and nominal `record_kind` discriminators.

### 4.1 `SelfModelSnapshotV1`

A content-addressed description of what the system currently believes about its own operational state.

Required fields:

- `record_kind = SELF_MODEL_SNAPSHOT_V1`
- `schema_version`
- `snapshot_id`
- `created_at`
- `source_commit_sha`
- `policy_digest`
- `epoch_id`
- `state_root`
- `capability_inventory_digest`
- `claim_state_digest`
- `calibration_state_digest`
- `previous_snapshot_digest | null`
- `snapshot_digest`
- `epistemic_ceiling = T2`
- `authority = SELF_MODEL_EVIDENCE_ONLY`

The snapshot does not assert hidden mental state. It summarizes auditable system state and previously admitted claims.

### 4.2 `SelfPredictionV1`

A sealed forecast about a specific governed transition or work node.

Required fields:

- `record_kind = SELF_PREDICTION_V1`
- `prediction_id`
- `cycle_id`
- `self_model_snapshot_digest`
- `transition_id | work_node_id`
- `policy_digest`
- `epoch_id`
- `prestate_root`
- ordered `clauses`
- `sealed_at`
- `prediction_digest`
- `authority = PREDICTION_EVIDENCE_ONLY`

Each prediction clause is typed and includes a predeclared weight and confidence in basis points.

V1 clause kinds:

- `BOOLEAN`
- `EXACT_STRING`
- `SHA256_DIGEST`
- `INTEGER_RANGE`
- `BPS_INTERVAL`

Clause weights must sum to exactly `10000` basis points. No post-outcome weight mutation is permitted.

### 4.3 `SelfObservationV1`

A candidate account of what happened.

Required fields:

- `record_kind = SELF_OBSERVATION_V1`
- `cycle_id`
- target binding
- `source_modality`
- observed clause values
- evidence artifact digests
- optional external verifier receipt references
- `observed_at`
- `observation_digest`
- `epistemic_status`
- `authority = OBSERVATION_EVIDENCE_ONLY`

`source_modality` distinguishes at least:

- `RUNTIME_TELEMETRY`
- `LEDGER_STATE`
- `TEST_RESULT`
- `FORMAL_VERIFIER_RECEIPT`
- `WORLD_OBSERVATION_RECEIPT`
- `PROVIDER_REPORT`

Provider reports alone cannot make an outcome verification-eligible for effect truth.

### 4.4 `PredictionErrorReceiptV1`

A deterministic comparison between sealed prediction and verified/scorable outcome.

Required fields:

- `record_kind = PREDICTION_ERROR_RECEIPT_V1`
- prediction/observation/binding digests
- per-clause correctness
- per-clause error score `0..10000`
- weighted aggregate error `0..10000`
- confidence calibration residual
- `scoring_status = SCORED | UNSCORABLE`
- diagnostics
- `receipt_digest`
- `authority = CALIBRATION_EVIDENCE_ONLY`

For V1, scoring is deterministic and integer-only. No floating-point result is canonical.

A simple confidence residual for a binary correctness event is computed in basis-point space from the sealed confidence and the observed correctness target (`0` or `10000`). Any more sophisticated calibration metric must be separately versioned rather than silently changing V1 semantics.

### 4.5 `SelfModelUpdateProposalV1`

A proposed correction to the next self-model.

Allowed proposal actions:

- `HOLD`
- `DEMOTE_CONFIDENCE`
- `RAISE_UNCERTAINTY`
- `MARK_CONTRADICTION`
- `REQUEST_REVIEW`

V1 deliberately excludes automatic `PROMOTE_TIER`, policy mutation, new capability grants, or authority expansion.

Required fields include supporting receipt digests and `authority = UPDATE_PROPOSAL_ONLY`.

### 4.6 `ReflexiveCycleReceiptV1`

Binds the complete reflexive cycle:

```text
snapshot -> prediction -> execution reference -> observation
-> verification references -> error receipt -> update proposal
```

It records whether the cycle is replayable, scorable, contradiction-free, and eligible to be considered by the external admission path.

It does not itself perform that admission.

## 5. Formal sensorium

Formal verification results are one class of self-observation evidence, not a privileged escape from binding rules.

### 5.1 Coq/Rocq

Consume only exact-head Coq attestation receipts that record:

- compiler/kernel version
- source commit and source digest
- compile status
- theorem inventory
- `Print Assumptions` classification
- assumption-bearing vs axiom-free status

A source containing `Axiom`, `Parameter`, `Admitted`, or unresolved assumption output cannot be normalized as axiom-free proof evidence.

### 5.2 TLA+

A TLA+ specification becomes verification evidence only when a concrete TLC/Apalache-style run is exact-bound and receipt-bearing. Presence of `.tla` source alone is design/formal-spec evidence, not model-check success.

### 5.3 C/WASM formal layer

The existing CompCert-scale / Coq-Iris / WASM programme is represented in the self-model as `FORMAL_SCAFFOLD_PRESENT` until an executable C/Clight/CompCert/VST/CBMC/Frama-C or equivalent verifier path is actually installed, executed, and receipt-bound.

The self-model must not infer `C_KERNEL_VERIFIED` from documents or proof sketches.

### 5.4 Lean

V1 records `LEAN_REPO_NATIVE_STATUS = NOT_PRESENT` unless the repo later contains and executes an exact-head Lean formalization. External/reference Lean workflows do not silently upgrade the AEGIS repo-native verifier inventory.

## 6. Reflexive cycle state machine

```text
SNAPSHOT_CREATED
  -> PREDICTION_SEALED
  -> EXECUTION_REFERENCED
  -> OBSERVATION_CAPTURED
  -> EVIDENCE_VERIFIED
  -> ERROR_COMPUTED
  -> UPDATE_PROPOSED
  -> CYCLE_CLOSED
```

Fail-closed side states:

- `UNSCORABLE_STALE_BINDING`
- `UNSCORABLE_POSTDICTION`
- `UNSCORABLE_UNVERIFIED_OUTCOME`
- `CONTRADICTION_DETECTED`
- `TAMPER_DETECTED`
- `VERIFIER_UNAVAILABLE`

No fail state is converted into success by retrying with a different narrative or provider answer.

## 7. Autobiographical continuity

The reflexive organism keeps an append-only, content-addressed lineage of cycle receipts.

Continuity means:

- each canonical self-model snapshot references its predecessor;
- every change is explainable by supporting evidence receipts;
- replay from genesis can reconstruct the same accepted snapshot chain;
- historical wrong beliefs remain visible as historical states rather than being rewritten.

This is machine-checkable temporal identity/provenance, not a claim of subjective personal identity.

## 8. Calibration state

Calibration is maintained per prediction domain and prediction kind. V1 must not collapse unrelated prediction classes into one vanity score.

Example domains:

- `BUILD_AND_TEST`
- `FORMAL_VERIFICATION`
- `PROVIDER_EXECUTION`
- `LEDGER_TRANSITION`
- `WORLD_EFFECT`
- `RESOURCE_AND_COST`

For each domain, the self-model may retain:

- sample count
- mean weighted error
- mean confidence residual
- recent-window error
- contradiction count
- unscorable count
- last update cycle digest

Versioned units and windows prevent metric gaming by silently redefining the denominator.

## 9. Integration with the existing metacognitive loop

V1 does not replace `MetacognitiveLoop`.

Instead a bridge emits bounded observations:

- prediction sealed -> `SELF_MODEL`
- verified outcome captured -> `PERCEPTION`
- prediction error computed -> `METACOGNITIVE`
- update proposal emitted -> `SELF_MODEL`
- contradiction found -> `METACOGNITIVE`

The metacognitive hash chain records that the reflexive cycle happened. The dedicated reflexive contracts carry the structured semantics.

The historical nominal `CONSCIOUSNESS` layer is not required for a reflexive cycle to pass.

## 10. Interaction with UCI collective intelligence

The self-model is collective but provider-neutral.

Different providers/agents may:

- propose predictions;
- produce observations;
- challenge observations;
- propose counterevidence;
- independently score or verify artifacts.

But canonical reflexive receipts are produced only by deterministic AEGIS logic over exact-bound evidence.

Provider disagreement is preserved as evidence diversity. It is not averaged into truth.

## 11. Security and adversarial requirements

At minimum V1 tests must falsify:

1. observation inserted before prediction seal;
2. prediction written after outcome is known;
3. stale `policy_digest`;
4. stale epoch;
5. wrong transition/work-node binding;
6. wrong prestate root;
7. prediction digest tamper;
8. observation digest tamper;
9. provider report presented as verified world effect;
10. unknown/injected `authority` field;
11. injected `execute`/`permit`/`effect` fields;
12. weight sum not equal to 10000;
13. confidence outside `0..10000`;
14. unsupported prediction kind;
15. scorer float/non-integer leakage;
16. cycle replay produces different receipt digest;
17. self-model proposal tries to promote tier automatically;
18. self-model proposal tries to mutate policy;
19. formal source receipt is assumption-bearing but presented as axiom-free;
20. TLA+/C/WASM source presence presented as executed verifier success;
21. contradictory verified observations are silently discarded;
22. cross-provider agreement presented as authority;
23. self-calibration score presented as capability grant;
24. nominal `CONSCIOUSNESS` observation presented as proof of consciousness.

## 12. First implementation slice

Create:

- `sovereign-omega-v2/src/reflexive-self-model/contracts.ts`
- `sovereign-omega-v2/src/reflexive-self-model/evaluate.ts`
- `sovereign-omega-v2/src/reflexive-self-model/cycle.ts`
- `sovereign-omega-v2/src/reflexive-self-model/metacognition-bridge.ts`
- `schemas/reflexive-self-model/*.schema.json`
- `test-vectors/reflexive-self-model/reflexive-self-model-v1.json`
- focused unit/vector tests

The first slice does **not** autonomously execute actions, alter canonical policy, promote epistemic tiers, rewrite identity, or merge branches. It evaluates and records reflexive evidence only.

## 13. Success criteria

`REFLEXIVE_SELF_MODEL_V1` is established only when all of the following are true on one exact head:

1. prediction is immutable and provably sealed before observed outcome;
2. all cycle artifacts are exact-bound;
3. tampering is detected;
4. score calculation is deterministic and integer-only;
5. identical replay yields byte-identical canonical receipt hashes;
6. update proposals cannot encode authority or policy mutation;
7. metacognitive bridge records the reflexive event without becoming authority;
8. prior UCI regression suite remains green;
9. independent `tarikskalic33/info` witness is green;
10. native AEGIS admission/constitutional CI is green for the exact checkpoint;
11. formal-verifier inventory reports actual execution status rather than source presence;
12. no completion claim equates this subsystem with proven consciousness or AGI.

## 14. Non-goals

V1 does not establish:

- subjective consciousness;
- qualia;
- sentience;
- moral patienthood;
- general intelligence;
- autonomous constitutional self-modification;
- automatic self-granting of capabilities;
- unrestricted recursive self-improvement;
- automatic tier promotion;
- semantic equivalence among Coq, TLA+, C/WASM, Lean, or runtime implementations;
- truth of a provider/model self-report.

## 15. Design decision

Three broad designs were considered:

1. **Label-only awakening:** reuse the existing `CONSCIOUSNESS` layer and expose it as a product feature. Rejected because it creates a semantic claim without new evidence.
2. **Autonomous self-modifying organism:** let self-observation directly update policy/capabilities. Rejected because it collapses evidence into authority and violates AEGIS constitutional boundaries.
3. **Formal reflexive organism:** immutable self-prediction, independently verified observation, deterministic error calculation, explicit update proposals, and externally governed admission. **Selected.**

The selected design makes the system increasingly able to detect when its own model of itself is wrong while preserving the principle that self-observation cannot certify its own authority.
