# PR-5A Exact Lineage Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one exact-head candidate that has both `PR #264 @ 31aec51c32caa2431cb94ee742c912059802568b` and `PR #273 @ 6407db1b0c4176f67a1d7ecbb16eca77d131d87e` as ancestors, then add a non-authoritative provider-execution evidence binding with cross-language verification.

**Architecture:** Start from the approved PR-5A spec branch descended from PR #273, construct a real two-parent integration commit whose second parent is exact PR #264, resolving only genuine overlapping files while preserving both semantic surfaces. Then add the smallest TypeScript normative producer plus Python serialized-artifact verifier; provider/model output remains evidence only, and the PR-4 effect/CompleteVerification chain remains independent.

**Tech Stack:** Git two-parent commit topology via GitHub objects API, TypeScript/Vitest, Python 3.12/unittest, existing SHA-256 helpers, JSON Schema draft 2020-12, external exact-head GitHub-hosted witness.

**Spec:** `docs/superpowers/specs/2026-08-19-pr5a-exact-lineage-integration-design.md`

## Global Constraints

- Exact provider parent: `31aec51c32caa2431cb94ee742c912059802568b`.
- Exact verification parent: `6407db1b0c4176f67a1d7ecbb16eca77d131d87e`.
- Both exact anchors must be ancestors of the integration candidate.
- Research / epistemological scope is FROZEN.
- Provider/model output is evidence only and never authority.
- D3 requires explicit operator approval; D4 remains denied.
- Sensorium remains `OBSERVATION_ONLY / T2 / authorityWeight=0 / mayGroundStateTransition=false`.
- Preserve `ExecutionReceipt -/-> EffectReceipt`.
- Preserve `CompleteVerification -/-> CausalClaimAdmission / AtomicAdmission / EffectBoundAdmission / ProductionAdmission`.
- No generic EffectReceipt producer.
- No provider call, secret provisioning, billing/IAM/DNS mutation, merge to `main`, or AGI claim.
- External exact-head witness must not be relabeled AEGIS repo-native CI.

---

### Task 1: Construct and prove the real two-parent integration commit

**Files:**
- Preserve: all PR #264 frontier/provider/Sensorium files.
- Preserve: all PR #273 decision/execution/effect/CompleteVerification files.
- Resolve only overlapping files identified by exact commit comparison.

**Interfaces:**
- Consumes: exact parent commits `31aec51c...` and `6407db1b...` plus PR-5A spec/plan commits descended from the latter.
- Produces: one integration commit with both exact anchors provable as ancestors.

- [ ] **Step 1: Compare exact parents and freeze the overlap set**

Require merge base `001fcb3aa92efd18a226ac5eb5b5bd6ccd0d512a`. The known semantic overlap set requiring explicit three-way resolution is:

```text
.github/workflows/automaton-3.yml
harness/sdk/authority_client.py
scripts/automaton3-authority.py
scripts/run-automaton3-tests.py
scripts/validate-automaton3.py
```

If exact comparison reveals another same-path change, stop and add it to the reviewed overlap set before creating the merge tree.

- [ ] **Step 2: Build merged tree from PR #264 plus PR #273 unique changes**

Use PR #264 as the content-heavy tree and overlay PR #273 unique effect/receipt changes. For the overlap set, preserve both sides' requirements rather than choosing one parent wholesale.

- [ ] **Step 3: Create a two-parent commit**

Primary parent is current `pr5a-exact-lineage-integration` head; additional parent is exact PR #264 head. The resulting commit must satisfy:

```text
ancestor(candidate, 6407db1b0c4176f67a1d7ecbb16eca77d131d87e) = true
ancestor(candidate, 31aec51c32caa2431cb94ee742c912059802568b) = true
```

- [ ] **Step 4: Run an integration-only topology witness before new feature code**

External runner checks both ancestors and executes existing PR #264 and PR #273 regression surfaces. Any semantic regression blocks Task 2.

---

### Task 2: Add RED contract for ProviderExecutionEvidenceBindingV1

**Files:**
- Create: `sovereign-omega-v2/test/unit/frontier-provider-evidence-binding.test.ts`
- Create: `sovereign-omega-v2/python/tests/test_provider_execution_binding_pr5a.py`
- Create: `schemas/provider-execution-evidence-binding.v1.schema.json`

**Interfaces:**
- TypeScript tests import future `createProviderExecutionEvidenceBinding`, `verifyProviderExecutionEvidenceBinding`, and `ProviderExecutionEvidenceBindingV1`.
- Python tests import future `ProviderExecutionEvidenceBinding`, `verify_provider_execution_binding`.

- [ ] **Step 1: Write TypeScript RED falsifiers**

Cover valid exact binding and rejection of `grantsAuthority=true`, missing authority root, provider/request/operation/response/work-order/authority-root/transition/execution/parent-state mismatches, and malformed SHA-256 fields.

- [ ] **Step 2: Write Python RED/non-promotion falsifiers**

Require the serialized TS artifact to validate identically, while raw Python `ProviderEvidence` without an authority root cannot be promoted and cannot substitute for EffectWitness or EffectReceipt.

- [ ] **Step 3: Write JSON Schema**

Required fields are exactly:

```text
binding_kind
provider
request_id
provider_operation_id
response_digest
work_order_digest
authority_receipt_root
transition_id
execution_instance_id
expected_parent_state_root
grants_authority
```

`binding_kind` const is `PROVIDER_EXECUTION_EVIDENCE_BINDING_V1`; all digest/root fields are lowercase 64-hex; `grants_authority` const is `false`; `additionalProperties=false`.

- [ ] **Step 4: Prove RED externally**

Expected failure is missing production modules/functions, not syntax or harness errors.

---

### Task 3: Implement the normative TypeScript producer and verifier

**Files:**
- Create: `sovereign-omega-v2/src/api/frontier-provider-evidence-binding.ts`
- Test: `sovereign-omega-v2/test/unit/frontier-provider-evidence-binding.test.ts`

**Interfaces:**
- Consumes admitted `FrontierInferenceRequest`, successful `FrontierProviderResult`, and authority-bound usage context containing exact `workOrderDigest` and `authorityReceiptRoot`.
- Produces immutable `ProviderExecutionEvidenceBindingV1` and deterministic root using domain `AEGIS_PROVIDER_EXECUTION_EVIDENCE_BINDING_V1`.

- [ ] **Step 1: Implement exact nominal type and validator**

No optional authority root. Reject `grantsAuthority !== false`, malformed digests, empty identifiers, and all caller/context mismatches.

- [ ] **Step 2: Implement deterministic producer**

Producer receives exact request/result plus explicit `transitionId`, `executionInstanceId`, `workOrderDigest`, and `authorityReceiptRoot`. It checks `request.expectedParentStateRoot`, `result.providerOperationId`, `result.responseDigest`, and provider identity before returning the frozen artifact.

- [ ] **Step 3: Implement deterministic root**

Serialize only the frozen artifact fields in stable key order and hash under `AEGIS_PROVIDER_EXECUTION_EVIDENCE_BINDING_V1` using existing hashing helpers; do not describe this as RFC 8785/JCS unless the existing admitted helper proves that claim.

- [ ] **Step 4: Run TypeScript suite GREEN**

All PR-5A TS falsifiers must pass together with inherited frontier gateway/runtime tests.

---

### Task 4: Implement Python serialized-artifact verifier without authority promotion

**Files:**
- Create: `harness/sdk/provider_execution_binding.py`
- Test: `sovereign-omega-v2/python/tests/test_provider_execution_binding_pr5a.py`

**Interfaces:**
- Consumes only serialized `ProviderExecutionEvidenceBindingV1` fields plus expected binding values.
- Produces a strict frozen dataclass and boolean/structured verification result; it never issues DecisionReceipt, ExecutionReceipt, EffectReceipt, or authority.

- [ ] **Step 1: Implement parser/validator**

Require exact discriminator, exact field set, lowercase SHA-256 roots/digests, `grants_authority is False`, and non-empty identity fields.

- [ ] **Step 2: Implement exact-binding verification**

Every provider/request/operation/response/work-order/authority-root/transition/execution/parent-state mismatch returns false/fail-closed.

- [ ] **Step 3: Add explicit non-promotion surface**

Do not expose any function that accepts Python `ProviderEvidence` and invents an authority root. Tests must prove that object is rejected as a substitute for this artifact and for effect artifacts.

- [ ] **Step 4: Run Python suite GREEN**

Require PR-5A Python tests plus PR-4 29 tests and PR-3 15 tests to remain green.

---

### Task 5: Full exact-head integration witness and draft PR

**Files:**
- External witness workflow in the already-used `tarikskalic33/info` runner repository.
- No AEGIS `main` mutation.

**Interfaces:**
- Consumes exact PR-5A candidate SHA.
- Produces a hash-bound witness bundle and draft PR description.

- [ ] **Step 1: Verify both exact parent ancestors**

- [ ] **Step 2: Run PR #264 frontier Python, LUT-KAN, constitutional, Sensorium/frontier Vitest, typecheck, credential scan**

- [ ] **Step 3: Run PR #273 CompleteVerification, PR-3 VerifyEffect, inherited Automaton-3, schema, MCP, frozen-hash regressions**

- [ ] **Step 4: Run PR-5A TS/Python binding falsifiers and cross-language serialized parity**

- [ ] **Step 5: Emit exact candidate SHA, both parent SHAs, test counts, witness root, artifact digest**

- [ ] **Step 6: Open DRAFT PR with no merge request**

Only after a fresh successful witness may the ledger state:

```text
TWO_LINEAGE_INTEGRATION = IMPLEMENTED_AND_EXTERNALLY_EXACT_HEAD_TESTED
PROVIDER_EXECUTION_EVIDENCE_BINDING = IMPLEMENTED_AND_EXTERNALLY_EXACT_HEAD_TESTED_REFERENCE
GENERAL_INTELLIGENCE_ORCHESTRATOR = NOT_IMPLEMENTED
PRODUCTION_ADMISSION = NOT_ESTABLISHED
AEGIS_REPO_NATIVE_EXACT_HEAD_CI_PASS = NOT_ESTABLISHED unless independently proven
AGI = NOT_ESTABLISHED
```
