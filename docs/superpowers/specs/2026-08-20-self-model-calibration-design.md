# Evidence-Bound Self-Model Calibration Design

## Status

Approved architectural slice for PR #275. This design extends the existing `sovereign-omega-v2/src/metacognition/` substrate. It does not create a second authority path and does not establish consciousness, production AGI, external-effect truth, or implementation correspondence beyond the tests and receipts that explicitly verify this slice.

## Goal

Add a deterministic, replayable self-model calibration layer that records what AEGIS predicted about its own execution, binds that prediction to an independently referenced observed outcome, computes a deterministic calibration error, and emits evidence that can be mirrored into the existing `MetacognitiveLoop` as `SELF_MODEL` / `T2` observation.

The operational loop is:

`SelfPrediction -> Execution -> OutcomeObservation -> Calibration -> ErrorLedger`

with the hard invariants:

- `Prediction != Observation`
- `Observation != Authority`
- `Calibration != Authority`
- prediction artifacts are never acceptable as external-effect truth evidence
- calibration artifacts are never acceptable as external-effect truth evidence
- an outcome observation must bind to the exact prediction and exact action digest it evaluates
- self-model evidence remains T2 unless separately promoted by admitted evidence outside this subsystem

## Existing substrate

`src/metacognition/loop.ts` already provides a hash-chained, replay-reconstructable `MetacognitiveLoop` and a `SELF_MODEL` layer. `src/ledger/ledger-observer.ts` already records node checkpoints into that layer. The new component must reuse those semantics instead of creating a parallel metacognitive authority channel.

`src/core/hashing.ts` provides canonical RFC-8785-based `hashValue()` and `src/core/types.ts` provides the branded `SHA256Hex` and `SequenceNumber` types. The new component must use these existing primitives.

## Contracts

### SelfPredictionRecordV1

A prediction is evidence-only and must contain:

- `receipt_kind = SELF_PREDICTION_RECORD_V1`
- `schema_version = 1.0.0`
- `action_digest: SHA256Hex`
- `predicted_success_bps: integer in [0, 10000]`
- `prediction_hash: SHA256Hex`, computed over the canonical prediction body
- `authority = NONE`
- `acceptable_for_effect_truth = false`

No timestamp is required; sequencing belongs to the enclosing ledger.

### SelfOutcomeObservationV1

An observation evaluates one exact prediction and must contain:

- `receipt_kind = SELF_OUTCOME_OBSERVATION_V1`
- `schema_version = 1.0.0`
- `prediction_hash: SHA256Hex`
- `action_digest: SHA256Hex`
- `observation_evidence_digest: SHA256Hex`
- `observed_success: boolean`
- `authority = NONE`
- `acceptable_for_effect_truth = false`

The observation evidence digest must not equal the prediction hash. This prevents a prediction from being recycled as its own observation evidence. This check is a structural anti-self-grounding rule; it does not by itself establish the truth or independence of the referenced evidence.

### SelfCalibrationRecordV1

Calibration is constructed only from a matching prediction and outcome observation. It must contain:

- `receipt_kind = SELF_CALIBRATION_RECORD_V1`
- `schema_version = 1.0.0`
- exact `prediction_hash`
- exact `action_digest`
- exact `observation_evidence_digest`
- exact `predicted_success_bps`
- exact `observed_success`
- `absolute_error_bps = abs(predicted_success_bps - observed_target_bps)`, where `observed_target_bps = 10000` for success and `0` for failure
- `calibration_hash: SHA256Hex` over the canonical calibration body
- `authority = NONE`
- `acceptable_for_effect_truth = false`

Construction must fail closed when the observation's `prediction_hash` or `action_digest` differs from the supplied prediction.

## Calibration ledger

`SelfCalibrationLedger` is an immutable hash chain over calibration records.

Each ledger entry contains:

- `calibration: SelfCalibrationRecordV1`
- `previous_entry_hash`
- monotonic `SequenceNumber`
- `entry_hash`

Genesis previous hash is 64 zeroes. Append rejects non-monotonic or duplicate sequence numbers. Certification recomputes every entry hash and every previous-link relation; any tampering yields `is_valid = false`.

The ledger is evidence storage only. A valid ledger certificate means the stored calibration chain is structurally/hash consistent; it does not prove that referenced observations are true.

## Metacognitive bridge

A helper converts a `SelfCalibrationRecordV1` into an existing `MetacognitiveObservation`:

- `layer = SELF_MODEL`
- `tier = T2`
- signal includes the calibration hash, action digest prefix, predicted bps, observed success, and absolute error bps

The resulting observation can be appended to `MetacognitiveLoop`. The bridge must not add authority fields or promote tier.

## Error model

V1 intentionally uses integer basis points and a binary observed target. No floating-point calibration metric is introduced. This gives deterministic, cross-runtime-stable arithmetic and avoids claiming that V1 is a complete statistical calibration framework.

Aggregate ECE/Brier-style estimators, domain-conditioned calibration, provider-conditioned calibration, and adaptive self-model policy are explicitly out of scope for this slice.

## Security / epistemic invariants

1. Anti-splicing: calibration cannot combine a prediction with an observation for another prediction or action.
2. Anti-self-grounding: prediction hash cannot be used as its own observation evidence digest.
3. Evidence-only: prediction, observation, calibration, ledger entry, and ledger certificate never grant authority.
4. Effect-truth separation: all generated records expose `acceptable_for_effect_truth = false` where applicable.
5. Replay: same inputs and same sequence produce byte-identical canonical hashes.
6. Tamper evidence: modifying a calibration record, previous link, or entry hash invalidates certification.
7. No implicit promotion: metacognitive bridge emits only `SELF_MODEL/T2`.

## Tests required before admission

- invalid confidence below 0 or above 10000 is rejected
- same prediction input yields the same prediction hash
- observation using the prediction hash as evidence is rejected
- action/prediction mismatch is rejected by calibration
- absolute error is correct for success and failure observations
- calibration hash is deterministic
- ledger sequence must increase strictly
- valid multi-entry ledger certifies
- tampered previous hash, calibration content, or entry hash fails certification
- metacognitive bridge emits exactly `SELF_MODEL` and `T2`
- generated prediction/calibration records remain unacceptable for effect truth

## Non-claims

This subsystem does not establish self-awareness, psychological consciousness, autonomous authority, correctness of the referenced outcome evidence, external-effect truth, or general intelligence. It establishes only a deterministic evidence-bound mechanism for measuring the error between an AEGIS self-prediction and a separately referenced observed outcome.