# UCI-1 Collective Work Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first canonical Universal Collective Intelligence contract surface: typed `IntentEnvelopeV1`, `CollectiveWorkGraphV1`, `CollectiveWorkNodeV1`, capability references, consequence classes, closed JSON schemas, deterministic validation, and adversarial tests without provider execution or authority promotion.

**Architecture:** Implement a small TypeScript contract module under `sovereign-omega-v2/src/collective/` and matching root JSON Schemas under `schemas/`. Validation is fail-closed and dependency-free: runtime validators reject unknown fields, malformed digests, invalid graph topology, stale/invalid consequence declarations, and capability/provider/tool ambiguity. UCI-1 creates no scheduler, provider session, receipt producer, effect observer, admission store, or production wiring.

**Tech Stack:** TypeScript 5.5+, Vitest 4, JSON Schema Draft 2020-12, existing `sovereign-omega-v2` Gate 8 CI.

**Spec:** `docs/superpowers/specs/2026-08-19-universal-collective-intelligence-kernel-v1-design.md`

**Restack note (2026-08-24):** The original plan was authored against
`main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`. Its bounded UCI-1 implementation is
restacked for verification on
`integration/effect-chain-main-a34d@1406aacca95fef02a942621a7060e0b6b14a5809`.
PR #309 is open and not admitted; if admitted, it supersedes only the older
PR #268 -> #270 -> #272 -> #273 effect-chain integration route. This restack contains
UCI-1 only. No UCI-2/UCI-3 or later UCI lane, math/RH, formal-attestation,
metacognition, reflexive-self-model, or experiment-admission-plan artifact is included.
It establishes no AGI, RH, production-readiness, production-deployment, or repository
admission claim.

## Global Constraints

- Preserve `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1` as the historical
  authoring base; bind current verification to the restack base stated above.
- Provider/model output is evidence only and never authority.
- UCI-1 does not execute providers, tools, external mutations, receipts, effects, or admission.
- Consequence classes are exactly `D0 | D1 | D2 | D3 | D4`; D3 remains operator-approval-bound and D4 remains denied absent later separately admitted policy.
- Serialized constitutional objects use mandatory discriminators and reject unknown top-level and nested fields.
- Digests/commitments are lowercase 64-hex SHA-256 strings; hashes prove byte/lineage integrity, not proposition truth.
- Graph validation must be deterministic, cycle-detecting, dependency-complete, duplicate-ID rejecting, and independent of object/map iteration order.
- No new runtime dependency is required for UCI-1.
- `tarikskalic/info` may be used only as an independent exact-head witness; it is not the canonical authority or merge admission source.

---

### Task 1: Define the typed collective-work contracts

**Files:**
- Create: `sovereign-omega-v2/src/collective/contracts.ts`
- Create: `sovereign-omega-v2/test/unit/collective/collective-work-contract.test.ts`

**Interfaces:**
- Produces: `ConsequenceClass`, `CapabilityStatus`, `CapabilityRefV1`, `IntentEnvelopeV1`, `CollectiveWorkNodeV1`, `CollectiveWorkGraphV1`.
- No runtime behavior beyond constants/type guards in this task.

- [ ] **Step 1: Write RED tests for nominal discriminators and required fields**

Test fixtures must require:

```ts
schema_version: '1.0.0'
intent_kind: 'INTENT_ENVELOPE_V1'
graph_kind: 'COLLECTIVE_WORK_GRAPH_V1'
work_node_kind: 'COLLECTIVE_WORK_NODE_V1'
```

and verify the exported consequence set is exactly `['D0','D1','D2','D3','D4']`.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
cd sovereign-omega-v2
npm test -- --run test/unit/collective/collective-work-contract.test.ts
```

Expected: module/import failure because `src/collective/contracts.ts` does not exist.

- [ ] **Step 3: Implement minimal contract types/constants**

Use exact shapes:

```ts
export const CONSEQUENCE_CLASSES = ['D0','D1','D2','D3','D4'] as const;
export type ConsequenceClass = typeof CONSEQUENCE_CLASSES[number];

export const CAPABILITY_STATUSES = [
  'NOT_TESTED','PARTIAL','TESTED_REFERENCE','VERIFIED_FOR_PROFILE','REVOKED'
] as const;
export type CapabilityStatus = typeof CAPABILITY_STATUSES[number];

export interface CapabilityRefV1 {
  capability_kind: 'CAPABILITY_REF_V1';
  capability_id: string;
  status: CapabilityStatus;
  profile?: string;
}
```

`IntentEnvelopeV1` must bind intent digest, actor/session identity, policy commitment, authority epoch, input artifact digests, requested capability IDs, max cost/tokens/duration, consequence ceiling, and deterministic nonce.

`CollectiveWorkNodeV1` must bind all fields required by spec §5.2 plus mandatory `work_node_kind`.

`CollectiveWorkGraphV1` must bind `graph_kind`, `schema_version`, `graph_id`, `intent_digest`, ordered `nodes`, `policy_commitment`, `authority_epoch`, and `graph_nonce`.

- [ ] **Step 4: Run focused test and confirm GREEN**

Same command; expected PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/collective/contracts.ts sovereign-omega-v2/test/unit/collective/collective-work-contract.test.ts
git commit -m "feat(uci): define collective work contracts"
```

### Task 2: Add fail-closed runtime validators

**Files:**
- Create: `sovereign-omega-v2/src/collective/validate.ts`
- Modify: `sovereign-omega-v2/test/unit/collective/collective-work-contract.test.ts`

**Interfaces:**
- Consumes: Task 1 contract types.
- Produces: `validateIntentEnvelope(value: unknown): ValidationResult<IntentEnvelopeV1>` and `validateCollectiveWorkGraph(value: unknown): ValidationResult<CollectiveWorkGraphV1>`.

Define:

```ts
export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; errors: readonly string[] };
```

- [ ] **Step 1: Add RED adversarial tests**

Cover at minimum:

1. unknown top-level field rejected;
2. unknown nested capability field rejected;
3. non-64-hex digest rejected;
4. empty provider/tool/capability identifiers rejected;
5. duplicate node IDs rejected;
6. missing dependency rejected;
7. self-dependency rejected;
8. graph cycle rejected;
9. node intent digest mismatch rejected;
10. node policy commitment mismatch rejected;
11. node authority epoch mismatch rejected;
12. `D3` accepted only as a declared consequence class, with no execution/approval field available in UCI-1;
13. `D4` accepted only as a declared class and must not produce any executable/authorized state;
14. negative/non-integer cost, token, duration, epoch values rejected;
15. duplicate capability/provider/tool entries rejected;
16. reordered independent nodes produce the same validation verdict.

- [ ] **Step 2: Run focused tests and confirm RED for missing validators**

- [ ] **Step 3: Implement minimal deterministic validators**

Requirements:

- reject arrays/objects with unexpected keys using explicit allowed-key sets;
- use `/^[0-9a-f]{64}$/` for digests;
- validate positive or zero integer bounds as specified by field semantics;
- use sorted copies for duplicate/topology checks but preserve original graph data;
- use deterministic Kahn/DFS cycle detection with lexicographically sorted node IDs/dependencies;
- collect errors in stable lexicographic order before returning.

Do not infer provider capability from provider names. Do not invent defaults for policy, authority epoch, consequence class, or budgets.

- [ ] **Step 4: Run focused tests and confirm GREEN**

- [ ] **Step 5: Run full TypeScript typecheck**

```bash
cd sovereign-omega-v2
npm run typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/src/collective/validate.ts sovereign-omega-v2/test/unit/collective/collective-work-contract.test.ts
git commit -m "feat(uci): validate collective work graphs fail closed"
```

### Task 3: Add closed JSON Schema contracts

**Files:**
- Create: `schemas/intent-envelope.v1.schema.json`
- Create: `schemas/capability-ref.v1.schema.json`
- Create: `schemas/collective-work-node.v1.schema.json`
- Create: `schemas/collective-work-graph.v1.schema.json`
- Create: `sovereign-omega-v2/test/unit/collective/collective-work-schema.test.ts`

**Interfaces:**
- Schemas mirror Task 1 serialization exactly.
- Test validates schema structure and parity against runtime fixtures; no new JSON-schema library is introduced.

- [ ] **Step 1: Write RED schema-presence/parity tests**

Tests load schema JSON from repository root and assert:

- draft 2020-12;
- `additionalProperties: false` at every constitutional object definition;
- required discriminator consts;
- exact consequence/status enums;
- SHA-256 patterns;
- all Task 1 required properties appear in `required`;
- no schema contains `authority`, `authorized`, `execute`, `effect`, `admission`, or `receipt` as a writable property in UCI-1 contracts.

- [ ] **Step 2: Run focused schema test and confirm RED**

- [ ] **Step 3: Create four schemas with shared local `$defs` where needed**

No remote runtime resolution dependency is allowed. Use explicit local definitions in each schema if cross-file resolution would require extra tooling.

- [ ] **Step 4: Run schema tests and confirm GREEN**

- [ ] **Step 5: Commit**

```bash
git add schemas/*.schema.json sovereign-omega-v2/test/unit/collective/collective-work-schema.test.ts
git commit -m "feat(uci): add closed collective work schemas"
```

### Task 4: Add canonical test vectors and deterministic graph falsifiers

**Files:**
- Create: `test-vectors/collective-intelligence/uci-1-v1.json`
- Create: `sovereign-omega-v2/test/vectors/uci-1-collective-work-vectors.test.ts`

**Interfaces:**
- Consumes validators from Task 2.
- Produces a repository-visible vector corpus for later Rust/Python/provider parity work.

- [ ] **Step 1: Add RED vector runner test expecting the vector file**

Vector file must include at least:

- one valid D0 two-node graph;
- one valid D3 graph declaration;
- invalid unknown field;
- invalid duplicate node;
- invalid missing dependency;
- invalid cycle;
- invalid stale/mismatched policy commitment relative to graph;
- invalid authority epoch mismatch;
- invalid digest;
- invalid duplicate provider/tool/capability;
- invalid attempt to inject `authority` or `execution_receipt`.

Each case has `id`, `expected_ok`, and `payload`.

- [ ] **Step 2: Run focused vector test and confirm RED**

- [ ] **Step 3: Add vectors and deterministic runner**

Runner must sort cases by `id`, execute validator, and assert exact expected verdict. Invalid cases must also assert at least one stable error code/message prefix.

- [ ] **Step 4: Run vector test twice**

```bash
npm test -- --run test/vectors/uci-1-collective-work-vectors.test.ts
npm test -- --run test/vectors/uci-1-collective-work-vectors.test.ts
```

Expected: identical PASS counts both runs.

- [ ] **Step 5: Commit**

```bash
git add test-vectors/collective-intelligence/uci-1-v1.json sovereign-omega-v2/test/vectors/uci-1-collective-work-vectors.test.ts
git commit -m "test(uci): add collective work falsification vectors"
```

### Task 5: Historical exact-head repository and independent witness verification

> **Historical/non-executable for the 2026-08-24 restack:** This task records the
> original workflow against the historical authoring parent. Do not create the
> experiment-admission plan or use its `expected_parent_sha` as a current instruction.
> The experiment plan is excluded from this UCI-1-only restack, whose verification base
> is `integration/effect-chain-main-a34d@1406aacca95fef02a942621a7060e0b6b14a5809`.

**Files:**
- Create: `.aegis/experiments/uci-1-collective-work-contract-v1.json`
- Modify only if required by repository-managed provenance automation: `.claude.json`

**Interfaces:**
- Produces exact-head CI evidence; no production deploy or provider call.

- [ ] **Step 1: Add an experiment-admission plan bound to canonical parent**

Historical instruction only; not executable for the current restack:

Use:

```text
expected_parent_sha = 32b7eb6a37fb69d19dd80189390b6641c5004ef1
execution_class = EXPERIMENT
max_cost_microunits = 0
max_mutations = 0
```

Authority request may cover workflow artifacts/attestation only; no cloud/provider credentials or production effects.

- [ ] **Step 2: Run focused UCI tests on the implementation head via AEGIS CI**

Required PASS:

- UCI contract unit tests;
- schema tests;
- vector tests;
- TypeScript typecheck/build;
- existing Gate 8 / Constitutional Automaton required jobs.

- [ ] **Step 3: Run independent exact-head witness from `tarikskalic/info` if available**

The witness must checkout `Aegis-Omega/AEGIS-OMEGA` by exact candidate SHA, print candidate and expected parent SHA, run only deterministic zero-cost UCI-1 tests/typecheck, and publish a summary artifact with test counts and SHA binding.

Classification:

```text
EXTERNAL_EXACT_HEAD_WITNESS = ESTABLISHED   # only if run succeeds
AEGIS_REPO_NATIVE_CI = separate status
PRODUCTION_ADMISSION = NOT_ESTABLISHED
AGI = NOT_ESTABLISHED
```

- [ ] **Step 4: Run full verification before completion**

```bash
cd sovereign-omega-v2
npm test -- --run test/unit/collective test/vectors/uci-1-collective-work-vectors.test.ts
npm run typecheck
npm run build
```

Then inspect exact-head GitHub Actions results and combined status.

- [ ] **Step 5: Open draft PR**

Title:

```text
feat(uci): add collective work contract v1
```

PR body must state exact base/head, test evidence, explicit non-claims, and that UCI-1 adds contracts/validation only.

## Completion criteria

UCI-1 is complete only when all of the following are true:

1. Exact typed contracts exist with mandatory discriminators.
2. Runtime validators reject unknown fields and all listed graph/binding falsifiers.
3. Closed schemas mirror the runtime contract.
4. Deterministic vectors pass twice with identical outcomes.
5. No provider execution, authority promotion, receipt/effect/admission path, or production deployment is added.
6. Exact-head AEGIS repository CI is green for the relevant gates.
7. Independent `tarikskalic/info` witness is recorded separately if executed.
8. PR remains unmerged pending operator/reviewer admission.
