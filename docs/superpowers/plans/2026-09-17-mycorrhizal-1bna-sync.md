# Mycorrhizal 1BNA Evidence Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the existing Mycorrhizal Collective Metacognition v1 contract on `#264@db311cfc900f594dc24aa5cc842586495a43ce61` and synchronize the source-bound 1BNA structural benchmark into it as zero-authority verification evidence.

**Architecture:** Three pure TypeScript MCM units implement contracts, deterministic reduction, and verification routing under the frozen `OBSERVATION_ONLY/T2/0/false` boundary. A fourth pure adapter validates exact 1BNA evidence digests and converts them into an MCM node-observation input without importing raw PDB bytes or granting semantic/authority promotion.

**Tech Stack:** TypeScript 5.x, Vitest 4.x, repository `hashValue()` RFC-8785/JCS hashing path, existing Sensorium contract, integer-only BPS arithmetic.

**Spec:** `docs/superpowers/specs/2026-09-17-mycorrhizal-1bna-sync-design.md`

## Global Constraints

- Exact implementation parent is `db311cfc900f594dc24aa5cc842586495a43ce61`.
- Feature branch is `feat/mycorrhizal-1bna-sync-v1`; do not mutate `main` or `feat/frontier-provider-mesh-v1`.
- Every load-bearing MCM output must contain exactly `authorityEffect='OBSERVATION_ONLY'`, `observationTier='T2'`, `authorityWeight=0`, `mayGroundStateTransition=false`.
- MCM must never emit authority grants, admission, leases/fencing authority, provider/tool calls, effect receipts, or canonical state transitions.
- No `Date.now()` in deterministic TypeScript logic.
- All v1 arithmetic is integer-only BPS in `[0,10000]`.
- Hashes use repository `hashValue()` / RFC-8785 canonicalisation, never ad-hoc `JSON.stringify()` integrity hashing.
- Tests live in `sovereign-omega-v2/test/unit/` (singular `test`).
- 1BNA biological mechanism and standard-3DNA equivalence remain `NOT_CLAIMED`.
- `authority_effect=NONE` throughout.

---

### Task 1: Preregister MCM and 1BNA RED contracts

**Files:**
- Create: `sovereign-omega-v2/test/unit/mycorrhizal-contracts.test.ts`
- Create: `sovereign-omega-v2/test/unit/mycorrhizal-state.test.ts`
- Create: `sovereign-omega-v2/test/unit/mycorrhizal-routing.test.ts`
- Create: `sovereign-omega-v2/test/unit/mycorrhizal-1bna.test.ts`

**Interfaces:**
- Consumes: not-yet-existing modules under `src/metacognition/`.
- Produces: RED evidence proving implementation is absent before production code.

- [ ] **Step 1: Add contract RED tests**

Use Vitest imports and require these future exports:

```ts
import { describe, expect, it } from 'vitest'
import {
  createMcmNodeObservation,
  type McmNodeObservationInputV1,
} from '../../src/metacognition/mycorrhizal-contracts.js'
```

Tests must cover constitutional constants, freezing, malformed digest, out-of-range BPS, duplicate evidence, and attempted authority override via widened untrusted input.

- [ ] **Step 2: Add state RED tests**

Require:

```ts
import { reduceMycorrhizalCollectiveState } from '../../src/metacognition/mycorrhizal-state.js'
```

Tests: empty set, mixed parent, mixed topology, conflicting node/sequence, input-order independence, repeated deterministic root.

- [ ] **Step 3: Add routing RED tests**

Require:

```ts
import { deriveMcmVerificationRequests } from '../../src/metacognition/mycorrhizal-routing.js'
```

Cover all six threshold reasons, canonical sorted evidence/reasons, priority formula, stale-state rejection, and absence of authority/effect fields.

- [ ] **Step 4: Add 1BNA RED tests**

Require:

```ts
import {
  ONE_BNA_SOURCE_SHA256,
  ONE_BNA_V3_BENCHMARK_DIGEST,
  ONE_BNA_V4_CROSS_RUNTIME_DIGEST,
  create1BnaMcmObservationInput,
} from '../../src/metacognition/mycorrhizal-1bna.js'
```

Assert exact canonical digests, drift rejection, stronger-claim rejection, default BPS profile, and that resulting MCM observation routes to `LOW_CALIBRATION` plus `EXPLICIT_VERIFICATION_DEMAND` only as evidence/review signal.

- [ ] **Step 5: Execute RED**

Run:

```bash
cd sovereign-omega-v2
npx vitest run \
  test/unit/mycorrhizal-contracts.test.ts \
  test/unit/mycorrhizal-state.test.ts \
  test/unit/mycorrhizal-routing.test.ts \
  test/unit/mycorrhizal-1bna.test.ts
```

Expected: FAIL because the four implementation modules do not exist.

- [ ] **Step 6: Commit RED**

```bash
git add sovereign-omega-v2/test/unit/mycorrhizal-*.test.ts
git commit -m "test(mcm): preregister 1BNA mycorrhizal sync"
```

---

### Task 2: Implement MCM observation contracts

**Files:**
- Create: `sovereign-omega-v2/src/metacognition/mycorrhizal-contracts.ts`
- Test: `sovereign-omega-v2/test/unit/mycorrhizal-contracts.test.ts`

**Interfaces:**
- Consumes: `hashValue()` from `../core/hashing.js`.
- Produces: `McmNodeObservationInputV1`, `McmNodeObservationV1`, `McmVerificationReason`, `McmVerificationRequestV1`, `createMcmNodeObservation()`.

- [ ] **Step 1: Implement exact public types**

```ts
export interface McmNodeObservationInputV1 {
  readonly nodeIdentityDigest: string
  readonly sensoriumObservationDigest: string
  readonly observationSequence: number
  readonly expectedParentStateRoot: string
  readonly topologyDigest: string
  readonly calibrationBps: number
  readonly evidenceSupportBps: number
  readonly evidenceFreshnessBps: number
  readonly resourcePressureBps: number
  readonly contradictionPressureBps: number
  readonly verificationDemandBps: number
  readonly evidenceReferences: readonly string[]
}
```

`McmNodeObservationV1` extends the input with the four constitutional constants plus `schemaVersion='1.0.0'` and `observationDigest`.

- [ ] **Step 2: Implement fail-closed validation**

Validate every digest with `/^[a-f0-9]{64}$/`; every BPS as safe integer `[0,10000]`; sequence non-negative safe integer; evidence strings non-empty and unique. Reject any input object containing conflicting `authorityEffect`, `observationTier`, `authorityWeight`, or `mayGroundStateTransition` properties.

- [ ] **Step 3: Canonicalize and hash**

Sort evidence references, construct the immutable payload, derive `observationDigest = await hashValue(payload)`, and return a frozen object.

- [ ] **Step 4: Run focused GREEN**

```bash
npx vitest run test/unit/mycorrhizal-contracts.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/mycorrhizal-contracts.ts sovereign-omega-v2/test/unit/mycorrhizal-contracts.test.ts
git commit -m "feat(mcm): add zero-authority observation contracts"
```

---

### Task 3: Implement deterministic collective state

**Files:**
- Create: `sovereign-omega-v2/src/metacognition/mycorrhizal-state.ts`
- Test: `sovereign-omega-v2/test/unit/mycorrhizal-state.test.ts`

**Interfaces:**
- Consumes: `readonly McmNodeObservationV1[]`.
- Produces: `reduceMycorrhizalCollectiveState(observations): Promise<MycorrhizalCollectiveStateV1>`.

- [ ] **Step 1: Implement set validation**

Reject empty sets, malformed constitutional fields, mixed parent roots, mixed topology digests, unsafe sums, and conflicting duplicate `(nodeIdentityDigest, observationSequence)` entries.

- [ ] **Step 2: Canonical ordering**

Sort a copied array by `nodeIdentityDigest`, then numeric `observationSequence`, then `observationDigest`. Never mutate caller input.

- [ ] **Step 3: Integer aggregation**

For each BPS field use:

```ts
Math.floor(sum / observations.length)
```

using safe-integer checked sums.

- [ ] **Step 4: Bind state root**

Hash a frozen payload containing the four constitutional constants, parent root, topology digest, node/observation counts, six aggregate metrics, and ordered `nodeObservationDigests`.

- [ ] **Step 5: Run GREEN**

```bash
npx vitest run test/unit/mycorrhizal-contracts.test.ts test/unit/mycorrhizal-state.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/mycorrhizal-state.ts sovereign-omega-v2/test/unit/mycorrhizal-state.test.ts
git commit -m "feat(mcm): add deterministic collective state"
```

---

### Task 4: Implement deterministic verification routing

**Files:**
- Create: `sovereign-omega-v2/src/metacognition/mycorrhizal-routing.ts`
- Test: `sovereign-omega-v2/test/unit/mycorrhizal-routing.test.ts`

**Interfaces:**
- Consumes: exact state plus the observations represented by that state.
- Produces: `readonly McmVerificationRequestV1[]`.

- [ ] **Step 1: Validate state/observation binding**

Every observation must match `state.parentStateRoot`, `state.topologyDigest`, and occur exactly once in `state.nodeObservationDigests`.

- [ ] **Step 2: Implement frozen thresholds**

Derive reason codes from each individual observation with the six exact thresholds from the spec.

- [ ] **Step 3: Implement deterministic priority**

```ts
Math.max(
  10000 - calibrationBps,
  10000 - evidenceSupportBps,
  10000 - evidenceFreshnessBps,
  resourcePressureBps,
  contradictionPressureBps,
  verificationDemandBps,
)
```

Return one request per observation with at least one reason; reason codes and evidence references sorted+unique; request object frozen and zero-authority.

- [ ] **Step 4: Run GREEN**

```bash
npx vitest run test/unit/mycorrhizal-contracts.test.ts test/unit/mycorrhizal-state.test.ts test/unit/mycorrhizal-routing.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/mycorrhizal-routing.ts sovereign-omega-v2/test/unit/mycorrhizal-routing.test.ts
git commit -m "feat(mcm): route deterministic verification demand"
```

---

### Task 5: Implement exact 1BNA evidence adapter

**Files:**
- Create: `sovereign-omega-v2/src/metacognition/mycorrhizal-1bna.ts`
- Test: `sovereign-omega-v2/test/unit/mycorrhizal-1bna.test.ts`

**Interfaces:**
- Consumes: exact digests plus caller-provided MCM node/state identifiers.
- Produces: `McmNodeObservationInputV1` only.

- [ ] **Step 1: Hard-bind canonical evidence identities**

Export exact constants:

```ts
export const ONE_BNA_SOURCE_SHA256 = 'df42f1506792f191b957227b061360652adcf6f813eb69d9ec553067ea584670'
export const ONE_BNA_V3_BENCHMARK_DIGEST = '0d23a1449c4110c11fe99809df1fd9bb55216d8b14eee75cdcff81f21f794276'
export const ONE_BNA_V4_CROSS_RUNTIME_DIGEST = 'f8197fa4ee9d37fd81bd4f3d1d9391d8eff153aefc3d0ff5e0ecce2ade1d053a'
```

- [ ] **Step 2: Validate evidence binding**

`create1BnaMcmObservationInput()` must fail closed unless supplied source/V3/V4 digests exactly equal those constants. Optional hotspot digest must be lowercase SHA-256 when present.

Reject objects containing any of these truth/authority promotion fields or equivalent exact keys:

```text
biologicalMechanismEstablished
standard3dnaVerified
authorityEffect
authorityWeight
mayGroundStateTransition
admission
```

- [ ] **Step 3: Emit conservative model-defined MCM profile**

Return a frozen `McmNodeObservationInputV1` with:

```text
calibrationBps=6500
evidenceSupportBps=9000
evidenceFreshnessBps=8000
resourcePressureBps=1000
contradictionPressureBps=0
verificationDemandBps=7500
```

Evidence references must include source, V3, and V4 digest URNs in canonical sorted order and include optional hotspot digest when present.

- [ ] **Step 4: Verify end-to-end MCM behavior**

Test pipeline:

```text
create1BnaMcmObservationInput
 -> createMcmNodeObservation
 -> reduceMycorrhizalCollectiveState
 -> deriveMcmVerificationRequests
```

Required reasons include `LOW_CALIBRATION` and `EXPLICIT_VERIFICATION_DEMAND`. Serialized output must not contain `ADMITTED`, `EffectReceipt`, provider/tool invocation, lease/grant/fencing authority, or `mayGroundStateTransition:true`.

- [ ] **Step 5: Run focused GREEN + typecheck**

```bash
npx vitest run test/unit/mycorrhizal-*.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/src/metacognition/mycorrhizal-1bna.ts sovereign-omega-v2/test/unit/mycorrhizal-1bna.test.ts
git commit -m "feat(mcm): bind 1BNA evidence into mycorrhizal verification"
```

---

### Task 6: Full repository verification and exact-head evidence

**Files:**
- No production file changes unless a verification-only workflow is required by existing repo patterns.

**Interfaces:**
- Consumes: Tasks 1–5 exact branch head.
- Produces: observed verification disposition only.

- [ ] **Step 1: Verify frozen hashes**

```bash
cd sovereign-omega-v2
node scripts/verify-hashes.mjs
```

Expected: PASS.

- [ ] **Step 2: Run MCM focused suite**

```bash
npx vitest run test/unit/mycorrhizal-*.test.ts
```

Expected: PASS.

- [ ] **Step 3: Run Gate 8**

```bash
npm run test
npm run typecheck
npm run build
```

Expected: PASS. Any failure halts promotion of the verification status.

- [ ] **Step 4: Open a DRAFT PR against `feat/frontier-provider-mesh-v1`**

The PR body must bind the exact parent `db311cfc900f594dc24aa5cc842586495a43ce61`, current exact head, focused test result, Gate-8 status, and explicit non-claims.

- [ ] **Step 5: Read hosted exact-head checks**

Only exact-head successful runs may establish `MCM_EXACT_HEAD_CI_PASS`. Vercel/deployment quota failures remain separate from TypeScript/MCM verification.

## Completion Ledger

At completion, report exactly:

```text
MCM_FORMAL_SPEC                    = ESTABLISHED
MCM_CODE_PRESENT                   = <exact-head bound status>
MCM_FOCUSED_TEST_PASS              = <observed status>
MCM_GATE8_PASS                     = <observed status>
MCM_EXACT_HEAD_CI_PASS             = <observed status>
MCM_EMPIRICAL_VALIDATION           = NOT_ESTABLISHED
MCM_AUTHORITY_INTEGRATION_PASS     = NOT_ESTABLISHED unless separately observed
MCM_PRODUCTION_ADMISSION           = NOT_ESTABLISHED
1BNA_SOURCE_BINDING                 = <observed status>
1BNA_CROSS_RUNTIME_EVIDENCE_BINDING = <observed status>
1BNA_STANDARD_3DNA_EQUIVALENCE     = NOT_CLAIMED
1BNA_BIOLOGICAL_MECHANISM          = NOT_CLAIMED
authority_effect                   = NONE
```
