# Self-Model Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, evidence-bound self-model calibration subsystem that measures prediction error without granting authority or effect-truth status.

**Architecture:** Implement a focused `src/metacognition/self-calibration.ts` module that defines immutable prediction, observation, calibration, and hash-chained calibration-ledger contracts using existing `hashValue`, `deepFreeze`, `SHA256Hex`, and `SequenceNumber` primitives. Add a narrow bridge that emits existing `MetacognitiveObservation` records at `SELF_MODEL/T2`. Keep `loop.ts`, authority semantics, and external-effect verification unchanged.

**Tech Stack:** TypeScript 5.5+, Vitest 4, existing RFC-8785 canonical hashing, immutable functional update pattern.

**Spec:** `docs/superpowers/specs/2026-08-20-self-model-calibration-design.md`

## Global Constraints

- Prediction, observation, calibration, ledger entries, and certificates are evidence-only; they never grant authority.
- `acceptable_for_effect_truth` is `false` for prediction, outcome observation, and calibration records.
- `predicted_success_bps` is an integer in `[0,10000]`; no floating-point metric is introduced.
- Observation must bind to the exact prediction hash and exact action digest.
- `observation_evidence_digest` must differ from `prediction_hash`.
- Calibration mismatch fails closed.
- Ledger sequence numbers are strictly increasing and hash chained from 64-zero genesis.
- Metacognitive bridge emits exactly `SELF_MODEL/T2`.
- No change to existing authority, admission, or effect-truth contracts.

---

### Task 1: Prediction and observation contracts

**Files:**
- Create: `sovereign-omega-v2/src/metacognition/self-calibration.ts`
- Create: `sovereign-omega-v2/test/unit/self-calibration.test.ts`

**Interfaces:**
- Consumes: `hashValue(value): Promise<SHA256Hex>`, `deepFreeze<T>(value): T`, `SHA256Hex`.
- Produces:
  - `createSelfPrediction(input): Promise<SelfPredictionRecordV1>`
  - `createSelfOutcomeObservation(input): SelfOutcomeObservationV1`
  - `SelfCalibrationError`

- [ ] **Step 1: Write failing tests for prediction validation and evidence separation**

Add tests that assert:

```ts
await expect(createSelfPrediction({ action_digest: H1, predicted_success_bps: -1 }))
  .rejects.toThrow(SelfCalibrationError)
await expect(createSelfPrediction({ action_digest: H1, predicted_success_bps: 10001 }))
  .rejects.toThrow(SelfCalibrationError)

const p1 = await createSelfPrediction({ action_digest: H1, predicted_success_bps: 7500 })
const p2 = await createSelfPrediction({ action_digest: H1, predicted_success_bps: 7500 })
expect(p1.prediction_hash).toBe(p2.prediction_hash)
expect(p1.authority).toBe('NONE')
expect(p1.acceptable_for_effect_truth).toBe(false)

expect(() => createSelfOutcomeObservation({
  prediction_hash: p1.prediction_hash,
  action_digest: H1,
  observation_evidence_digest: p1.prediction_hash,
  observed_success: true,
})).toThrow(SelfCalibrationError)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: FAIL because `src/metacognition/self-calibration.ts` and exported builders do not exist.

- [ ] **Step 3: Implement minimal prediction/observation builders**

Create types and builders with exact discriminators:

```ts
SELF_PREDICTION_RECORD_V1
SELF_OUTCOME_OBSERVATION_V1
```

Use integer validation, canonical `hashValue`, `deepFreeze`, `authority: 'NONE'`, and `acceptable_for_effect_truth: false`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: prediction/observation tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/self-calibration.ts sovereign-omega-v2/test/unit/self-calibration.test.ts
git commit -m "feat(metacognition): add self prediction evidence contracts"
```

### Task 2: Calibration anti-splicing and deterministic error

**Files:**
- Modify: `sovereign-omega-v2/src/metacognition/self-calibration.ts`
- Modify: `sovereign-omega-v2/test/unit/self-calibration.test.ts`

**Interfaces:**
- Consumes: `SelfPredictionRecordV1`, `SelfOutcomeObservationV1`.
- Produces: `createSelfCalibration(prediction, observation): Promise<SelfCalibrationRecordV1>`.

- [ ] **Step 1: Write failing tests for anti-splicing and error arithmetic**

Test exact mismatches:

```ts
await expect(createSelfCalibration(predictionA, { ...obsA, prediction_hash: predictionB.prediction_hash }))
  .rejects.toThrow(SelfCalibrationError)
await expect(createSelfCalibration(predictionA, { ...obsA, action_digest: H2 }))
  .rejects.toThrow(SelfCalibrationError)
```

Test deterministic integer errors:

```ts
expect(successCalibration.absolute_error_bps).toBe(2500) // 7500 vs 10000
expect(failureCalibration.absolute_error_bps).toBe(7500) // 7500 vs 0
expect(c1.calibration_hash).toBe(c2.calibration_hash)
expect(c1.authority).toBe('NONE')
expect(c1.acceptable_for_effect_truth).toBe(false)
```

- [ ] **Step 2: Run focused test and verify RED**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: FAIL because `createSelfCalibration` is not implemented.

- [ ] **Step 3: Implement minimal calibration builder**

Fail closed on prediction-hash/action-digest mismatch. Compute target basis points as `10000` or `0`, then integer absolute difference. Hash only the canonical calibration body before adding `calibration_hash`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: all calibration tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/self-calibration.ts sovereign-omega-v2/test/unit/self-calibration.test.ts
git commit -m "feat(metacognition): bind outcomes to self predictions"
```

### Task 3: Hash-chained calibration ledger

**Files:**
- Modify: `sovereign-omega-v2/src/metacognition/self-calibration.ts`
- Modify: `sovereign-omega-v2/test/unit/self-calibration.test.ts`

**Interfaces:**
- Produces:
  - `SelfCalibrationLedger.empty()`
  - `ledger.append(calibration, sequence)`
  - `ledger.getAll()`
  - `certifySelfCalibrationLedger(entries)`

- [ ] **Step 1: Write failing ledger tests**

Cover strictly increasing sequence, genesis link, deterministic entry hash, valid multi-entry certification, and tampering of previous hash/calibration/entry hash.

- [ ] **Step 2: Run focused test and verify RED**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: FAIL because ledger API is absent.

- [ ] **Step 3: Implement immutable ledger and certificate**

Use the same pattern as `MetacognitiveLoop`: functional update, 64-zero genesis, canonical hash over `{ calibration, previous_entry_hash, sequence: sequence.toString() }`, and replay certification by recomputation.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: ledger tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/self-calibration.ts sovereign-omega-v2/test/unit/self-calibration.test.ts
git commit -m "feat(metacognition): add replayable self calibration ledger"
```

### Task 4: Existing metacognitive-loop bridge

**Files:**
- Modify: `sovereign-omega-v2/src/metacognition/self-calibration.ts`
- Modify: `sovereign-omega-v2/test/unit/self-calibration.test.ts`

**Interfaces:**
- Consumes: `SelfCalibrationRecordV1`.
- Produces: `calibrationToMetacognitiveObservation(calibration): MetacognitiveObservation`.

- [ ] **Step 1: Write failing bridge test**

Assert exact layer/tier and evidence-only semantics:

```ts
const obs = calibrationToMetacognitiveObservation(calibration)
expect(obs.layer).toBe('SELF_MODEL')
expect(obs.tier).toBe('T2')
expect(obs.signal).toContain(calibration.calibration_hash)
```

Append the result to `MetacognitiveLoop.empty()` and certify the resulting chain.

- [ ] **Step 2: Run focused test and verify RED**

Run: `npm test -- test/unit/self-calibration.test.ts`

Expected: FAIL because bridge helper is absent.

- [ ] **Step 3: Implement minimal bridge**

Return only an existing `MetacognitiveObservation`; do not add authority or tier-promotion logic.

- [ ] **Step 4: Run focused and existing metacognition tests**

Run:

```bash
npm test -- test/unit/self-calibration.test.ts test/unit/metacognition-loop.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/self-calibration.ts sovereign-omega-v2/test/unit/self-calibration.test.ts
git commit -m "feat(metacognition): bridge calibration into self model observations"
```

### Task 5: Exact-head verification

**Files:**
- No production changes unless verification exposes a defect.

- [ ] **Step 1: Run focused tests**

```bash
npm test -- test/unit/self-calibration.test.ts test/unit/metacognition-loop.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run typecheck**

```bash
npm run typecheck
```

Expected: PASS.

- [ ] **Step 3: Run full unit suite**

```bash
npm test
```

Expected: PASS with no new regressions.

- [ ] **Step 4: Verify PR exact-head workflows**

Require the relevant GitHub Actions runs to bind to the current PR #275 head SHA. Do not inherit older green runs.

- [ ] **Step 5: Record final evidence boundary**

Report only what exact-head tests establish: deterministic self-prediction/calibration contracts, anti-splicing, replay integrity, and `SELF_MODEL/T2` bridge. Preserve `external effect truth = NOT_ESTABLISHED` and `authority = NONE` for this subsystem.
