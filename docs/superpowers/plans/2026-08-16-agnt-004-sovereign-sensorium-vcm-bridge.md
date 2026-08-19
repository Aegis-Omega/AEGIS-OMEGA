# AGNT-004 Sovereign Sensorium & VCM Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a deterministic, observation-only Sovereign Sensorium and VCM bridge that can preserve, reduce, or suspend an already-admitted authority envelope but can never create or expand authority.

**Architecture:** The slice lives inside `sovereign-omega-v2`, beside the active frontier/authority runtime rather than under the unrelated root Rust `src/`. Three pure TypeScript modules separate canonical observation encoding, fixed-point VCM dynamics, and contractive degradation. The first implementation remains observation/degradation logic only; production authority integration stays a separate witness until the Authority Control Plane execution layer consumes the artifact.

**Tech Stack:** TypeScript 5.5+, Vitest 4, existing `sha256Hex` helper, integer/bigint fixed-point arithmetic, ESM `.js` import suffixes.

## Global Constraints

- `authority_effect` is exactly `OBSERVATION_ONLY`.
- Sensorium may return only `UNCHANGED | DEGRADED | SUSPENDED`; no expansion/grant state exists.
- `D_sensorium(A) ⊆ A` for every admitted authority envelope.
- Fixed observation state must be idempotent under repeated degradation.
- No transcendental math (`Math.exp`, `Math.log`, `Math.sqrt`) is used in AGNT-004 v1.
- VCM/retention formulas are engineering models; `EMPIRICALLY_VALIDATED` is never inferred from implementation or tests.
- Observation digest uses the component-local fixed-order length-prefixed UTF-8 encoding from the design spec, not an RFC-8785/JCS claim.
- Audit-only wall-clock metadata is excluded from the observation digest.
- Every execution receipt/test report must bind the exact commit SHA it ran against; a moving branch name is not a fixed witness.
- Existing PR #264 frontier behavior must remain non-regressed.

---

### Task 1: Canonical Sensorium Observation Artifact

**Files:**
- Create: `sovereign-omega-v2/src/sensorium/sensorium-observation.ts`
- Create: `sovereign-omega-v2/test/unit/sensorium-observation.test.ts`

**Interfaces:**
- Produces: `SensoriumObservationInputV1`, `SensoriumObservationV1`, `SensoriumObservationError`, `createSensoriumObservation(input)`, `encodeSensoriumObservationPayload(payload)`.
- Consumes: `sha256Hex(bytes: Uint8Array): Promise<string>` from `../core/hashing.js`.

- [ ] **Step 1: Write failing tests for deterministic encoding and authority boundary**

```ts
import { describe, expect, it } from 'vitest'
import { createSensoriumObservation } from '../../src/sensorium/sensorium-observation.js'

const HEX_A = 'a'.repeat(64)
const HEX_B = 'b'.repeat(64)

const baseInput = {
  sourceKind: 'runtime' as const,
  sourceIdentityDigest: HEX_A,
  subjectResourceDigest: HEX_B,
  observationSequence: 7,
  expectedParentStateRoot: 'c'.repeat(64),
  topologyDigest: 'd'.repeat(64),
  activeLoad: 40n,
  carryingCapacity: 100n,
  growthRateBps: 1000,
  retentionBps: 8000,
  decayBps: 500,
  reinforcementBps: 200,
  observationQualityBps: 9000,
  evidenceReferences: ['receipt://b', 'receipt://a'],
}

describe('SensoriumObservationV1', () => {
  it('is deterministic and observation-only', async () => {
    const first = await createSensoriumObservation(baseInput)
    const second = await createSensoriumObservation({ ...baseInput, evidenceReferences: ['receipt://a', 'receipt://b'] })
    expect(first.observationDigest).toBe(second.observationDigest)
    expect(first.observationId).toBe(first.observationDigest)
    expect(first.authorityEffect).toBe('OBSERVATION_ONLY')
    expect('grantsAuthority' in first).toBe(false)
  })

  it('changes digest when an authority-relevant binding changes', async () => {
    const first = await createSensoriumObservation(baseInput)
    const second = await createSensoriumObservation({ ...baseInput, topologyDigest: 'e'.repeat(64) })
    expect(second.observationDigest).not.toBe(first.observationDigest)
  })

  it('does not hash audit-only wall-clock metadata', async () => {
    const first = await createSensoriumObservation({ ...baseInput, auditObservedAt: '2026-08-16T05:00:00Z' })
    const second = await createSensoriumObservation({ ...baseInput, auditObservedAt: '2026-08-16T06:00:00Z' })
    expect(second.observationDigest).toBe(first.observationDigest)
  })
})
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-observation.test.ts
```

Expected: FAIL because `src/sensorium/sensorium-observation.ts` does not exist.

- [ ] **Step 3: Implement strict validation and component-local canonical encoding**

Implementation requirements:

```ts
export type SensoriumSourceKind = 'runtime' | 'telemetry' | 'operator' | 'replay'
export type SensoriumModelStatus = 'MODEL_DEFINED'
export type SensoriumEmpiricalStatus = 'NOT_ESTABLISHED' | 'EMPIRICALLY_VALIDATED'

export interface SensoriumObservationInputV1 {
  readonly sourceKind: SensoriumSourceKind
  readonly sourceIdentityDigest: string
  readonly subjectResourceDigest: string
  readonly observationSequence: number
  readonly expectedParentStateRoot: string
  readonly topologyDigest: string
  readonly activeLoad: bigint
  readonly carryingCapacity: bigint
  readonly growthRateBps: number
  readonly retentionBps: number
  readonly decayBps: number
  readonly reinforcementBps: number
  readonly observationQualityBps: number
  readonly evidenceReferences: readonly string[]
  readonly auditObservedAt?: string
}
```

Use a fixed schema-order length-prefixed UTF-8 encoding. Reject malformed 64-hex digests, negative/non-safe sequences, `carryingCapacity <= 0`, `activeLoad < 0`, `activeLoad > carryingCapacity`, BPS values outside `0..10000`, empty/duplicate evidence references, and unsupported source kinds. Sort evidence references before encoding. Exclude `auditObservedAt` and `observationDigest` from the digest payload.

- [ ] **Step 4: Run tests and typecheck GREEN**

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-observation.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/sensorium/sensorium-observation.ts sovereign-omega-v2/test/unit/sensorium-observation.test.ts
git commit -m "feat(sensorium): add deterministic observation artifact"
```

---

### Task 2: Deterministic VCM Capacity and Retention Dynamics

**Files:**
- Create: `sovereign-omega-v2/src/sensorium/vcm-bridge.ts`
- Create: `sovereign-omega-v2/test/unit/sensorium-vcm-bridge.test.ts`
- Modify: `sovereign-omega-v2/src/sensorium/sensorium-observation.ts`

**Interfaces:**
- Produces: `nextLogisticLoad(current, capacity, growthRateBps)`, `capacityPressureBps(active, capacity)`, `nextRetentionBps(current, decayBps, reinforcementBps)`.
- Consumed by: `createSensoriumObservation(...)` to populate predicted fields from inputs rather than accepting caller-supplied predictions.

- [ ] **Step 1: Write failing mathematical-boundary tests**

```ts
import { describe, expect, it } from 'vitest'
import {
  capacityPressureBps,
  nextLogisticLoad,
  nextRetentionBps,
} from '../../src/sensorium/vcm-bridge.js'

describe('VCM bridge', () => {
  it('applies the discrete Verhulst-style step without exceeding carrying capacity', () => {
    expect(nextLogisticLoad(40n, 100n, 1000)).toBe(42n)
    expect(nextLogisticLoad(100n, 100n, 1000)).toBe(100n)
  })

  it('computes bounded capacity pressure', () => {
    expect(capacityPressureBps(40n, 100n)).toBe(4000)
    expect(capacityPressureBps(100n, 100n)).toBe(10000)
  })

  it('applies discrete retention decay and reinforcement within BPS bounds', () => {
    expect(nextRetentionBps(8000, 500, 200)).toBe(7800)
    expect(nextRetentionBps(9800, 0, 500)).toBe(10000)
  })
})
```

- [ ] **Step 2: Verify RED**

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-vcm-bridge.test.ts
```

Expected: FAIL because `vcm-bridge.ts` does not exist.

- [ ] **Step 3: Implement integer-only recurrences**

Use `bigint` for the discrete logistic numerator/denominator:

```ts
const delta = BigInt(growthRateBps) * current * (capacity - current) / (10_000n * capacity)
const next = current + delta
```

Clamp the result to `0..capacity`. For pressure use integer division of `active * 10000 / capacity`. For retention use integer BPS arithmetic and clamp to `0..10000`. Throw `SensoriumModelError` for invalid ranges; never silently repair invalid capacity.

- [ ] **Step 4: Make observation predictions internal**

`createSensoriumObservation` must call the three VCM helpers and include:

- `predictedNextLoad`;
- `capacityPressureBps`;
- `predictedNextRetentionBps`;
- `modelStatus: 'MODEL_DEFINED'`;
- `empiricalStatus: 'NOT_ESTABLISHED'`.

Callers must not supply those derived fields.

- [ ] **Step 5: Verify GREEN and determinism**

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-vcm-bridge.test.ts test/unit/sensorium-observation.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/src/sensorium/vcm-bridge.ts sovereign-omega-v2/src/sensorium/sensorium-observation.ts sovereign-omega-v2/test/unit/sensorium-vcm-bridge.test.ts sovereign-omega-v2/test/unit/sensorium-observation.test.ts
git commit -m "feat(sensorium): add deterministic VCM bridge"
```

---

### Task 3: Contractive Sensorium Degradation Operator

**Files:**
- Create: `sovereign-omega-v2/src/sensorium/sensorium-degradation.ts`
- Create: `sovereign-omega-v2/test/unit/sensorium-degradation.test.ts`

**Interfaces:**
- Consumes: `SensoriumObservationV1`.
- Produces: `SensoriumDegradationV1`, `recommendSensoriumDegradation(observation)`, `applyConsequenceCap(admittedClass, degradation)`.

- [ ] **Step 1: Write failing threshold and non-amplification tests**

```ts
import { describe, expect, it } from 'vitest'
import { recommendSensoriumDegradation, applyConsequenceCap } from '../../src/sensorium/sensorium-degradation.js'

it('never increases an admitted consequence class', () => {
  const degraded = { recommendation: 'DEGRADED', maxConsequenceClass: 'D1' } as const
  expect(applyConsequenceCap('D0', degraded)).toBe('D0')
  expect(applyConsequenceCap('D1', degraded)).toBe('D1')
  expect(applyConsequenceCap('D3', degraded)).toBe('D1')
})

it('suspension caps authority at D0', () => {
  const suspended = { recommendation: 'SUSPENDED', maxConsequenceClass: 'D0' } as const
  expect(applyConsequenceCap('D3', suspended)).toBe('D0')
})
```

Add observation fixtures proving:

- quality `7999` => at least `DEGRADED`;
- quality `4999` => `SUSPENDED`;
- pressure `8000` => at least `DEGRADED`;
- pressure `9500` => `SUSPENDED`;
- retention `6999` => at least `DEGRADED`;
- retention `3999` => `SUSPENDED`;
- combined state chooses the most restrictive recommendation.

- [ ] **Step 2: Verify RED**

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-degradation.test.ts
```

Expected: FAIL because the degradation module does not exist.

- [ ] **Step 3: Implement the degradation lattice**

Use the order:

```ts
const consequenceRank = { D0: 0, D1: 1, D2: 2, D3: 3, D4: 4 } as const
```

`applyConsequenceCap` must return `min(admitted, cap)` by rank. It must reject unknown consequence classes. `recommendSensoriumDegradation` must emit reason codes and bind the exact observation digest, parent state root, topology digest, and observation sequence. Do not add any `grant`, `expand`, or `authority=true` field.

- [ ] **Step 4: Prove idempotence in tests**

```ts
const once = applyConsequenceCap('D3', degradation)
const twice = applyConsequenceCap(once, degradation)
expect(twice).toBe(once)
```

- [ ] **Step 5: Verify GREEN**

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-degradation.test.ts test/unit/sensorium-vcm-bridge.test.ts test/unit/sensorium-observation.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/src/sensorium/sensorium-degradation.ts sovereign-omega-v2/test/unit/sensorium-degradation.test.ts
git commit -m "feat(sensorium): add contractive authority degradation"
```

---

### Task 4: Export Boundary and Regression Witness

**Files:**
- Create: `sovereign-omega-v2/src/sensorium/index.ts`
- Modify: `.github/workflows/frontier-provider-mesh.yml`
- Modify: `docs/superpowers/specs/2026-08-16-agnt-004-sovereign-sensorium-vcm-bridge-design.md` only for evidence status after actual execution.

**Interfaces:**
- Produces: one stable export surface for AGNT-004.
- Does not yet mutate `FrontierInferenceGateway`; authority integration remains separately classified until the Authority Control Plane consumes `SensoriumDegradationV1`.

- [ ] **Step 1: Add stable exports**

```ts
export * from './sensorium-observation.js'
export * from './vcm-bridge.js'
export * from './sensorium-degradation.js'
```

- [ ] **Step 2: Extend the existing #264 workflow path/test scope**

Add `sovereign-omega-v2/src/sensorium/**` and `sovereign-omega-v2/test/unit/sensorium-*.test.ts` to the workflow path filters and include the three Sensorium tests in the existing Vitest command. Do not create another workflow or authority gate.

- [ ] **Step 3: Run the complete local witness set**

```bash
cd sovereign-omega-v2
npm run test -- test/unit/sensorium-observation.test.ts test/unit/sensorium-vcm-bridge.test.ts test/unit/sensorium-degradation.test.ts test/unit/frontier-inference-gateway.test.ts test/unit/frontier-provider-transports.test.ts test/unit/frontier-stream-lease.test.ts test/unit/frontier-automaton3-verifier.test.ts test/unit/frontier-runtime.test.ts
npm run typecheck
```

Expected: all selected tests PASS and typecheck PASS.

- [ ] **Step 4: Record only the evidence actually obtained**

If local commands pass, update the design ledger to:

```text
AGNT_004_IMPLEMENTATION: ESTABLISHED_AT_<EXACT_SHA>
AGNT_004_LOCAL_TEST_PASS: ESTABLISHED_AT_<EXACT_SHA>
AGNT_004_EXACT_HEAD_CI_PASS: NOT_ESTABLISHED
AGNT_004_EMPIRICAL_VALIDATION: NOT_ESTABLISHED
AGNT_004_AUTHORITY_INTEGRATION_PASS: NOT_ESTABLISHED
AGNT_004_PRODUCTION_ADMISSION: NOT_ESTABLISHED
```

Do not replace `<EXACT_SHA>` until the actual commit exists. The committed document must contain the real SHA, not a moving branch reference.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/sensorium/index.ts .github/workflows/frontier-provider-mesh.yml docs/superpowers/specs/2026-08-16-agnt-004-sovereign-sensorium-vcm-bridge-design.md
git commit -m "test(sensorium): bind AGNT-004 regression witness"
```

---

### Task 5: PR #264 Exact-Head Attestation

**Files:**
- PR metadata only; no new branch and no new PR.

**Interfaces:**
- Consumes: final exact head SHA and compare metadata.
- Produces: current PR body attestation that distinguishes design, implementation, local test evidence, exact-head CI, empirical validation, authority integration, and production admission.

- [ ] **Step 1: Resolve exact final head and lineage**

Run repository-equivalent checks:

```bash
git rev-parse HEAD
git merge-base --is-ancestor cd920379df1a23a61b969f0e52549c04bc3a91bb HEAD
git rev-list --count cd920379df1a23a61b969f0e52549c04bc3a91bb..HEAD
```

Expected: ancestor check exit 0. Record the actual SHA/count.

- [ ] **Step 2: Update #264 body with exact current values**

The body must explicitly state that historical heads such as `81a39789...` and `5bc36a91...` are prior exact commits in the same advancing lineage, not aliases for the new final head.

- [ ] **Step 3: Preserve fail-closed admission state**

Until a runner actually executes on the final SHA:

```text
EXACT_HEAD_CI_PASS: NOT_ESTABLISHED
PRODUCTION_ADMISSION: NOT_ESTABLISHED
```

A local PASS is never rewritten as an exact-head GitHub Actions PASS.
