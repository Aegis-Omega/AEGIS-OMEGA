# REFLEXIVE_SELF_MODEL_V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, evidence-bound reflexive self-model loop that seals predictions before outcomes, compares them with verified observations, emits calibration receipts and self-model update proposals, and bridges those events into the existing metacognitive chain without granting authority.

**Architecture:** The implementation is a TypeScript orchestration layer in `sovereign-omega-v2/src/reflexive-self-model/`. It consumes existing exact-bound UCI/execution/effect/formal evidence, produces only T2 reflexive evidence artifacts, and reuses `hashValue()` for domain-separated canonical digests plus `MetacognitiveLoop` for append-only observation history. The first slice is deliberately non-executing and non-authoritative: it evaluates and records reflexive cycles only.

**Tech Stack:** TypeScript, Vitest, existing RFC8785/JCS -> SHA-256 `hashValue`, JSON Schema Draft 2020-12, existing metacognitive loop, existing UCI evidence bindings.

**Spec:** `docs/superpowers/specs/2026-08-20-reflexive-self-model-v1-design.md`

## Global Constraints

- `Observe(Self) != Authorize(Self)` is a hard invariant.
- `CalibrationScore ↑ != Authority ↑` is a hard invariant.
- `REFLEXIVE_SELF_MODEL_V1_PASS != CONSCIOUSNESS_PROVED` is a hard invariant.
- Prediction must be sealed before governed execution/outcome evidence; otherwise the cycle is `UNSCORABLE_POSTDICTION`.
- Provider/model reports are candidate observations only and cannot establish world-effect truth.
- All canonical scoring is integer-only in basis points; no float is serialized as canonical result.
- Self-model update proposals may only be `HOLD`, `DEMOTE_CONFIDENCE`, `RAISE_UNCERTAINTY`, `MARK_CONTRADICTION`, or `REQUEST_REVIEW`.
- V1 cannot encode tier promotion, policy mutation, capability grants, authority expansion, execution, effect, or admission.
- Formal-verifier inventory must reflect actually executed receipt-bearing verifier paths; source presence alone is insufficient.
- Work remains on PR #275 integration spine; no additional persistent feature branch.

---

## File Structure

- `sovereign-omega-v2/src/reflexive-self-model/contracts.ts` — closed typed contracts and strict runtime validators for snapshots, predictions, observations, error receipts, update proposals, and cycle receipts.
- `sovereign-omega-v2/src/reflexive-self-model/evaluate.ts` — deterministic integer-only clause scoring and aggregate calibration/error computation.
- `sovereign-omega-v2/src/reflexive-self-model/cycle.ts` — state-machine/binding validation and cycle receipt construction.
- `sovereign-omega-v2/src/reflexive-self-model/metacognition-bridge.ts` — bounded projection from reflexive events into the existing metacognitive loop.
- `sovereign-omega-v2/test/unit/reflexive-self-model/contracts.test.ts` — contract and injection tests.
- `sovereign-omega-v2/test/unit/reflexive-self-model/evaluate.test.ts` — scoring and determinism tests.
- `sovereign-omega-v2/test/unit/reflexive-self-model/cycle.test.ts` — ordering/binding/state-machine/contradiction tests.
- `sovereign-omega-v2/test/unit/reflexive-self-model/metacognition-bridge.test.ts` — evidence-only bridge tests.
- `schemas/reflexive-self-model/*.schema.json` — closed wire contracts.
- `test-vectors/reflexive-self-model/reflexive-self-model-v1.json` — canonical positive/adversarial corpus.
- `sovereign-omega-v2/test/vectors/reflexive-self-model-vectors.test.ts` — vector replay tests.

---

### Task 1: Closed contracts and deterministic prediction-error evaluator

**Files:**
- Create: `sovereign-omega-v2/src/reflexive-self-model/contracts.ts`
- Create: `sovereign-omega-v2/src/reflexive-self-model/evaluate.ts`
- Create: `sovereign-omega-v2/test/unit/reflexive-self-model/contracts.test.ts`
- Create: `sovereign-omega-v2/test/unit/reflexive-self-model/evaluate.test.ts`

**Interfaces:**
- Produces `SelfModelSnapshotV1`, `SelfPredictionV1`, `SelfObservationV1`, `PredictionClauseV1`, `ObservedClauseV1`, `PredictionErrorReceiptV1`, `SelfModelUpdateProposalV1`, `ReflexiveCycleReceiptV1`.
- Produces `validateSelfModelSnapshotV1`, `validateSelfPredictionV1`, `validateSelfObservationV1`, `validateSelfModelUpdateProposalV1`.
- Produces `evaluatePrediction(prediction, observation): Promise<PredictionErrorReceiptV1>`.
- Uses existing `hashValue()` for receipt/digest construction.

- [ ] **Step 1: Write RED contract tests**

Add tests that require exact nominal discriminators and reject unknown/injected fields. Representative cases:

```ts
it('rejects injected authority escalation in a prediction', () => {
  const raw = { ...validPrediction(), authority: 'EXECUTION_AUTHORITY' }
  expect(() => validateSelfPredictionV1(raw)).toThrow(/authority/)
})

it('rejects prediction weights whose sum is not 10000 bps', () => {
  const raw = validPrediction()
  raw.clauses = [
    { clause_id: 'a', kind: 'BOOLEAN', expected: true, weight_bps: 6000, confidence_bps: 9000 },
    { clause_id: 'b', kind: 'BOOLEAN', expected: false, weight_bps: 3000, confidence_bps: 8000 },
  ]
  expect(() => validateSelfPredictionV1(raw)).toThrow(/10000/)
})
```

Also test: confidence outside `0..10000`, duplicate clause IDs, unsupported kind, non-SHA256 digests, stale nominal authority constants, injected `execute`, `permit`, `effect`, `receipt_kind`, automatic tier promotion, policy mutation, and capability grant fields.

- [ ] **Step 2: Run contract test and require RED because module is missing**

Run:

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/contracts.test.ts
```

Expected: FAIL on missing `src/reflexive-self-model/contracts` import, not on harness setup.

- [ ] **Step 3: Implement minimal closed contracts and validators**

Use explicit key allowlists and discriminators. Canonical authority constants are fixed:

```ts
export const SELF_MODEL_EVIDENCE_ONLY = 'SELF_MODEL_EVIDENCE_ONLY' as const
export const PREDICTION_EVIDENCE_ONLY = 'PREDICTION_EVIDENCE_ONLY' as const
export const OBSERVATION_EVIDENCE_ONLY = 'OBSERVATION_EVIDENCE_ONLY' as const
export const CALIBRATION_EVIDENCE_ONLY = 'CALIBRATION_EVIDENCE_ONLY' as const
export const UPDATE_PROPOSAL_ONLY = 'UPDATE_PROPOSAL_ONLY' as const
```

`PredictionClauseV1.kind` is exactly `BOOLEAN | EXACT_STRING | SHA256_DIGEST | INTEGER_RANGE | BPS_INTERVAL`. Validate all numeric fields with `Number.isSafeInteger` and explicit bounds.

- [ ] **Step 4: Write RED evaluator tests**

Require deterministic scoring for all five clause kinds. Representative expectations:

```ts
it('scores exact boolean match as zero error', async () => {
  const receipt = await evaluatePrediction(predictionWithBoolean(true), observationWithBoolean(true))
  expect(receipt.per_clause[0]!.error_bps).toBe(0)
})

it('scores exact boolean mismatch as 10000 error', async () => {
  const receipt = await evaluatePrediction(predictionWithBoolean(true), observationWithBoolean(false))
  expect(receipt.per_clause[0]!.error_bps).toBe(10000)
})
```

For `INTEGER_RANGE`, error is `0` inside the closed interval and otherwise normalized deterministically against the declared interval width, capped at `10000`. For `BPS_INTERVAL`, observed values are integer bps `0..10000`; same interval rule applies. `EXACT_STRING` and `SHA256_DIGEST` are exact-match only. Confidence residual for a scored clause is `abs(confidence_bps - (correct ? 10000 : 0))`.

- [ ] **Step 5: Run evaluator test and require RED because evaluator is missing**

Run:

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/evaluate.test.ts
```

Expected: FAIL on missing `evaluate.ts` import.

- [ ] **Step 6: Implement minimal deterministic evaluator**

Aggregate weighted error with integer arithmetic:

```ts
weighted_error_bps = Math.trunc(
  sum(error_bps * weight_bps) / 10000
)
```

Require one-to-one clause IDs between prediction and observation. A missing/extra clause, unverified outcome, binding mismatch, or non-integer observed value produces `scoring_status = 'UNSCORABLE'` with deterministic diagnostics; it never fabricates a score.

- [ ] **Step 7: Run focused tests twice and require identical receipt digests**

Run twice:

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/contracts.test.ts test/unit/reflexive-self-model/evaluate.test.ts
npm run typecheck
npm run build
```

Expected: PASS both runs; same fixtures produce the same `receipt_digest`.

- [ ] **Step 8: Commit Task 1 GREEN**

Commit subject:

```text
feat(reflexive): add closed self-model contracts and scorer
```

---

### Task 2: Reflexive cycle state machine and fail-closed binding

**Files:**
- Create: `sovereign-omega-v2/src/reflexive-self-model/cycle.ts`
- Create: `sovereign-omega-v2/test/unit/reflexive-self-model/cycle.test.ts`

**Interfaces:**
- Consumes Task 1 contracts and `evaluatePrediction`.
- Produces `closeReflexiveCycle(input): Promise<ReflexiveCycleReceiptV1>`.
- Produces exact side-state diagnostics: `UNSCORABLE_STALE_BINDING`, `UNSCORABLE_POSTDICTION`, `UNSCORABLE_UNVERIFIED_OUTCOME`, `CONTRADICTION_DETECTED`, `TAMPER_DETECTED`, `VERIFIER_UNAVAILABLE`.

- [ ] **Step 1: Write RED state-machine tests**

Cover all ordering and binding rules. Required cases:

```ts
it('rejects a prediction sealed after governed execution starts', async () => {
  const result = await closeReflexiveCycle({ ...validCycle(), prediction: latePrediction() })
  expect(result.cycle_status).toBe('UNSCORABLE_POSTDICTION')
})

it('rejects cross-cycle observation binding', async () => {
  const input = validCycle()
  input.observation.cycle_id = 'other-cycle'
  const result = await closeReflexiveCycle(input)
  expect(result.cycle_status).toBe('UNSCORABLE_STALE_BINDING')
})
```

Also test wrong policy digest, epoch, transition/work-node, prestate root, prediction digest, observation digest, verified-world-effect claim backed only by `PROVIDER_REPORT`, assumption-bearing formal receipt presented as axiom-free, source-only TLA+/C/WASM presented as executed success, and contradictory verified observations.

- [ ] **Step 2: Run focused test and require RED because `cycle.ts` is missing**

Run:

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/cycle.test.ts
```

Expected: missing-module RED.

- [ ] **Step 3: Implement minimal cycle closure logic**

Validate in this order so diagnostics are deterministic:

1. artifact contract validity;
2. digest integrity;
3. cycle/target/policy/epoch/prestate binding;
4. temporal ordering (`sealed_at <= execution_started_at <= observed_at`);
5. observation verification eligibility;
6. contradiction detection;
7. deterministic scoring;
8. update-proposal policy;
9. cycle receipt hashing.

Do not accept provider agreement as verification and do not auto-resolve contradictory verified observations.

- [ ] **Step 4: RED-test self-model update proposal rules**

Require automatic proposal selection only from the allowed action set. Example policy for V1:

```text
SCORED and weighted_error_bps == 0 and no contradiction -> HOLD
SCORED and weighted_error_bps > 0 -> DEMOTE_CONFIDENCE or RAISE_UNCERTAINTY
CONTRADICTION_DETECTED -> MARK_CONTRADICTION + REQUEST_REVIEW diagnostic
UNSCORABLE -> REQUEST_REVIEW
```

No case may yield tier promotion, policy mutation, capability grant, execution, effect, or admission.

- [ ] **Step 5: Implement minimal deterministic proposal derivation**

The proposal includes supporting error/verification digests and `authority = UPDATE_PROPOSAL_ONLY`. It is a proposal artifact only.

- [ ] **Step 6: Run focused tests twice + typecheck/build**

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/contracts.test.ts test/unit/reflexive-self-model/evaluate.test.ts test/unit/reflexive-self-model/cycle.test.ts
npm run typecheck
npm run build
```

Expected: all PASS; replayed cycle receipt digest identical.

- [ ] **Step 7: Commit Task 2 GREEN**

Commit subject:

```text
feat(reflexive): close evidence-bound reflexive cycles
```

---

### Task 3: Bridge reflexive evidence into the existing metacognitive chain

**Files:**
- Create: `sovereign-omega-v2/src/reflexive-self-model/metacognition-bridge.ts`
- Create: `sovereign-omega-v2/test/unit/reflexive-self-model/metacognition-bridge.test.ts`
- Reuse without semantic change: `sovereign-omega-v2/src/metacognition/loop.ts`

**Interfaces:**
- Consumes `MetacognitiveLoop`, `SequenceNumber`, and reflexive artifacts.
- Produces `appendReflexiveCycleToMetacognition(loop, receipt, startingSequence)` returning a new immutable loop plus emitted entries.

- [ ] **Step 1: Write RED bridge tests**

Require the bridge to emit only these mappings:

```text
prediction sealed -> SELF_MODEL
verified outcome -> PERCEPTION
prediction error -> METACOGNITIVE
update proposal -> SELF_MODEL
contradiction -> METACOGNITIVE
```

Require that no successful reflexive cycle needs the historical `CONSCIOUSNESS` label.

- [ ] **Step 2: Require RED because bridge module is missing**

Run:

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/metacognition-bridge.test.ts
```

- [ ] **Step 3: Implement bridge as an evidence projection only**

Signals must include stable receipt/cycle digest prefixes and status, not free-form provider narratives. The bridge may call `loop.observe(...)`; it cannot alter authority, policy, capability, tier, or execution state.

- [ ] **Step 4: Test tamper and replay behavior**

Require the resulting metacognitive chain to pass `certifyMetacognitiveLoop()` and a tampered entry to fail certification. Replaying the same reflexive event sequence from the same genesis must produce identical terminal/certificate hashes.

- [ ] **Step 5: Run focused suite + typecheck/build**

```bash
cd sovereign-omega-v2
npx vitest run test/unit/reflexive-self-model/*.test.ts
npm run typecheck
npm run build
```

- [ ] **Step 6: Commit Task 3 GREEN**

Commit subject:

```text
feat(reflexive): bridge cycle receipts into metacognition
```

---

### Task 4: Closed schemas and canonical falsification corpus

**Files:**
- Create: `schemas/reflexive-self-model/self-model-snapshot-v1.schema.json`
- Create: `schemas/reflexive-self-model/self-prediction-v1.schema.json`
- Create: `schemas/reflexive-self-model/self-observation-v1.schema.json`
- Create: `schemas/reflexive-self-model/prediction-error-receipt-v1.schema.json`
- Create: `schemas/reflexive-self-model/self-model-update-proposal-v1.schema.json`
- Create: `schemas/reflexive-self-model/reflexive-cycle-receipt-v1.schema.json`
- Create: `test-vectors/reflexive-self-model/reflexive-self-model-v1.json`
- Create: `sovereign-omega-v2/test/vectors/reflexive-self-model-vectors.test.ts`

**Interfaces:**
- Schemas mirror Task 1 contracts and use `additionalProperties: false` at authority-sensitive objects.
- Vector corpus replays through Tasks 1-3 runtime validators/evaluator/cycle.

- [ ] **Step 1: Write RED schema/vector tests before files exist**

Require exactly six schema files plus corpus file; missing files must be the only RED cause.

- [ ] **Step 2: Add six closed Draft 2020-12 schemas**

Every schema fixes `record_kind`, `schema_version`, `epistemic_ceiling`/`authority` constants where applicable, numeric bounds, digest patterns, and allowed proposal actions. Explicitly reject `permit`, `execute`, `effect`, `admission`, `capability_grant`, `policy_mutation`, `tier_promotion`, and alternate authority strings.

- [ ] **Step 3: Add at least 24 canonical falsification vectors**

Include every adversarial requirement from spec section 11: postdiction, stale binding, tampered digests, provider-report world-effect laundering, authority injection, weights/confidence/kind errors, float leakage, replay divergence, tier/policy/capability escalation, assumption-bearing formal source laundering, source-only TLA+/C/WASM success laundering, contradiction suppression, provider agreement as authority, calibration as grant, and nominal `CONSCIOUSNESS` as proof of consciousness.

- [ ] **Step 4: Run vectors twice and require byte-identical canonical outputs**

```bash
cd sovereign-omega-v2
npx vitest run test/vectors/reflexive-self-model-vectors.test.ts
npx vitest run test/vectors/reflexive-self-model-vectors.test.ts
npm run typecheck
npm run build
```

- [ ] **Step 5: Commit Task 4 GREEN**

Commit subject:

```text
feat(reflexive): lock wire schemas and falsification vectors
```

---

### Task 5: Exact-head witness, native admission, and checkpoint ledger

**Files:**
- Update: `tarikskalic33/info` witness workflow to run all prior UCI regression plus reflexive tests, typecheck, build, and replay.
- Rotate: the single `.aegis/experiments/` plan changed by PR #275 to the reflexive-self-model checkpoint only after the preceding UCI/math evidence remains preserved by exact SHA/artifact.
- Update: PR #275 body with the new checkpoint evidence.

**Interfaces:**
- Consumes the exact AEGIS branch head produced by Tasks 1-4.
- Produces independent witness artifact plus native Experiment Admission/Constitutional CI evidence.

- [ ] **Step 1: Run independent exact-head witness**

The witness must verify exact candidate SHA and canonical merge-base before install/test. Required workload:

```text
prior UCI regression
math-verification regression
reflexive contracts/evaluate/cycle/bridge/vector tests
strict typecheck
production build
second unchanged replay pass
```

- [ ] **Step 2: Require unchanged replay GREEN**

Rerun the exact same witness against the same AEGIS SHA. Do not advance the spine between the two runs.

- [ ] **Step 3: Rotate experiment plan atomically**

PR diff must contain exactly one active experiment plan. The plan describes only the reflexive T2 evidence checkpoint and binds to the canonical PR base rules required by Experiment Admission.

- [ ] **Step 4: Run native Experiment Admission and Constitutional Automaton on the same exact head**

Require native admission success plus the repository's constitutional pipeline. Any failure is a blocker; no completion claim based only on external witness.

- [ ] **Step 5: Record formal-verifier inventory honestly**

Checkpoint metadata must distinguish at minimum:

```text
COQ_REPO_NATIVE = executed/attested only if current Coq workflow receipt succeeded
TLA_REPO_NATIVE = source present unless an exact-bound model-check receipt exists
C_WASM_FORMAL = FORMAL_SCAFFOLD_PRESENT unless executable verifier receipt exists
LEAN_REPO_NATIVE = NOT_PRESENT
```

- [ ] **Step 6: Update PR #275 body with exact SHA and artifact/run identifiers**

Do not call the subsystem conscious, sentient, AGI, self-authorizing, or self-modifying. State only the established bounded capability.

- [ ] **Step 7: Verification-before-completion review**

Freshly verify changed-file scope, unknown-field boundaries, authority constants, replay determinism, exact-head CI, and absence of automatic tier/policy/capability mutation.

- [ ] **Step 8: Leave PR #275 unmerged unless the operator explicitly orders merge**
