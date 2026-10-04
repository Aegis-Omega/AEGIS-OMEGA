# UCI-4 Effect-Bound Verification Chain Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile the frozen PR #268 → #270 → #272 → #273 transition/effect-verification semantics onto the Universal Collective Intelligence integration spine without changing their epistemic meaning or promoting CompleteVerification into admission.

**Architecture:** UCI-4 is a narrow transplant onto `#275@ebec2f9c8fa00f54605d859df61512108ff3b71d`. It adds the nominal TransitionIdentity/DecisionReceipt/ExecutionReceipt/EffectReceipt contracts, independent filesystem EffectEvidence, VerifyEffect, and CompleteVerification as verifier-only artifacts. It does not add AtomicAdmission, production admission, distributed linearizability, generic EffectReceipt production, or provider/model authority.

**Tech Stack:** Python 3, JSON Schema Draft 2020-12, existing `harness/sdk` canonical hashing, pytest/unittest repository tests, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-19-universal-collective-intelligence-kernel-v1-design.md`

## Global Constraints

- Exact integration parent is `#275@ebec2f9c8fa00f54605d859df61512108ff3b71d`.
- Frozen source semantics are taken from `#273@6407db1b0c4176f67a1d7ecbb16eca77d131d87e`, which contains the complete stacked #268/#270/#272/#273 lineage.
- `DecisionReceipt != ExecutionReceipt != EffectReceipt` both nominally and after serialization.
- Only `PERMIT` carries decision authority; `DEFER -> WAITING`; `DEFER -/-> EXECUTE`.
- `ExecutionReceipt -/-> EffectReceipt`.
- Effect evidence must come from an independently bound observation adapter.
- No generic EffectReceipt producer may exist.
- `CompleteVerificationResult=TRUE` is verifier output only; it is not AdmissionRecord, AtomicAdmission, EffectBoundAdmission, or production admission.
- Provider/model output remains evidence only, never authority.
- D3 remains explicit-operator-approval-bound; D4 remains denied absent separately admitted policy.
- Preserve separate serialized discriminators and hash domains for all nominal artifacts.
- Preserve the theorem: `forall r in AuthorizationDerivedArtifacts: r not in AcceptableEvidence(V_effect)`.
- Do not mutate `main`, #275, #264, #268, #270, #272, or #273.

---

### Task 1: RED — UCI-4 Integration Contract

**Files:**
- Create: `sovereign-omega-v2/python/tests/test_uci4_effect_chain_integration.py`

**Interfaces:**
- Consumes: the intended UCI-4 modules under `harness.sdk`.
- Produces: a focused integration contract proving that the successor spine exposes the frozen nominal types and boundaries.

- [ ] **Step 1: Write the failing integration test**

```python
from harness.sdk.transition_receipts import (
    DECISION_RECEIPT_KIND,
    EXECUTION_RECEIPT_KIND,
    EFFECT_RECEIPT_KIND,
    DEFER,
    WAITING,
    decision_route,
)
from harness.sdk.effect_adapters import EffectWitness
from harness.sdk.effect_verifier import EffectVerificationResult
from harness.sdk.complete_verifier import CompleteVerificationResult


def test_uci4_nominal_effect_chain_surface_exists():
    assert DECISION_RECEIPT_KIND == "DECISION_RECEIPT_V1"
    assert EXECUTION_RECEIPT_KIND == "EXECUTION_RECEIPT_V1"
    assert EFFECT_RECEIPT_KIND == "EFFECT_RECEIPT_V1"
    assert decision_route(DEFER) == WAITING
    assert EffectWitness.__name__ == "EffectWitness"
    assert EffectVerificationResult.__name__ == "EffectVerificationResult"
    assert CompleteVerificationResult.__name__ == "CompleteVerificationResult"
```

- [ ] **Step 2: Run the focused test and require RED**

Run:

```bash
python -m pytest sovereign-omega-v2/python/tests/test_uci4_effect_chain_integration.py -q
```

Expected: FAIL during import because the UCI-4 effect-chain modules do not exist on the #275 parent.

- [ ] **Step 3: Preserve the RED commit**

```bash
git add sovereign-omega-v2/python/tests/test_uci4_effect_chain_integration.py
git commit -m "test(uci): preregister effect-chain integration boundary"
```

---

### Task 2: Transition Identity and Receipt Separation

**Files:**
- Create: `harness/sdk/transition_receipts.py`
- Create: `schemas/transition-identity-envelope.v1.schema.json`
- Create: `schemas/decision-receipt.v1.schema.json`
- Create: `schemas/execution-receipt.v1.schema.json`
- Create: `schemas/effect-receipt.v1.schema.json`
- Modify: `harness/sdk/authority_client.py`
- Modify: `scripts/automaton3-authority.py`
- Test: `sovereign-omega-v2/python/tests/test_transition_receipts_pr1.py`
- Test: `sovereign-omega-v2/python/tests/test_transition_receipts_cli_pr1.py`

**Interfaces:**
- Produces: `TransitionIdentity`, `DecisionReceipt`, `ExecutionReceipt`, schema-only/verifier-constructible `EffectReceipt`, `decision_route`, policy commitments, and canonical authority-client decision receipts.
- Preserves: compatibility-only Python MutationReceipt as `DECISION_DERIVED_NOT_EFFECT_PROOF`.

- [ ] **Step 1: Transplant the exact tested PR-1/PR-3 receipt implementation from #273**

Required constants and semantics include:

```python
DECISION_RECEIPT_KIND = "DECISION_RECEIPT_V1"
EXECUTION_RECEIPT_KIND = "EXECUTION_RECEIPT_V1"
EFFECT_RECEIPT_KIND = "EFFECT_RECEIPT_V1"
PERMIT = "PERMIT"
DENY = "DENY"
DEFER = "DEFER"
WAITING = "WAITING"
```

`decision_route(DEFER)` must return `WAITING`, and `decision_execution_allowed(DEFER)` must be `False`.

- [ ] **Step 2: Restore canonical authority-client/CLI emission of `transition_id` + `decision_receipt`**

No caller-supplied post-state value may become EffectEvidence. Legacy MutationReceipt output remains compatibility-only and cannot satisfy `V_effect`.

- [ ] **Step 3: Run the frozen PR-1 falsifiers**

```bash
python -m pytest sovereign-omega-v2/python/tests/test_transition_receipts_pr1.py sovereign-omega-v2/python/tests/test_transition_receipts_cli_pr1.py -q
```

Expected: PASS.

- [ ] **Step 4: Re-run Task 1 integration test**

Expected: still FAIL because PR-2/3/4 modules are not present yet; receipt imports themselves must now succeed.

- [ ] **Step 5: Commit**

```bash
git add harness/sdk/transition_receipts.py harness/sdk/authority_client.py scripts/automaton3-authority.py schemas/*.schema.json sovereign-omega-v2/python/tests/test_transition_receipts_*.py
git commit -m "feat(uci): restore transition identity and receipt separation"
```

---

### Task 3: Independent Effect Observation

**Files:**
- Create: `harness/sdk/effect_adapters.py`
- Create: `schemas/effect-witness.v1.schema.json`
- Test: `sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py`

**Interfaces:**
- Consumes: `TransitionIdentity`, `ExecutionReceipt`.
- Produces: `EffectObservationHandle`, `EffectWitness`, `FilesystemEffectAdapter`, `is_adapter_bound_effect_evidence`.

- [ ] **Step 1: Transplant the PR-2 reference adapter**

The adapter must derive PRE and POST commitments from fresh filesystem observation and enforce allowed-root containment. The caller cannot supply the post-state commitment.

- [ ] **Step 2: Run PR-2 falsifiers**

```bash
python -m pytest sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py -q
```

Expected: PASS, including stale-prestate, target escape, symlink/identity, execution-binding, and caller-poststate rejection coverage present in the frozen suite.

- [ ] **Step 3: Commit**

```bash
git add harness/sdk/effect_adapters.py schemas/effect-witness.v1.schema.json sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py
git commit -m "feat(uci): add independent effect observation evidence"
```

---

### Task 4: VerifyEffect and Verifier-Gated EffectReceipt

**Files:**
- Create: `harness/sdk/effect_verifier.py`
- Modify: `schemas/effect-receipt.v1.schema.json`
- Test: `sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py`

**Interfaces:**
- Consumes: `TransitionIdentity`, `ExecutionReceipt`, `EffectWitness`.
- Produces: `EffectVerificationResult`; `EffectVerifier.issue_effect_receipt(...)` is the only valid EffectReceipt producer in this slice.

- [ ] **Step 1: Transplant the PR-3 verifier**

Required obligation order:

```python
(
    "V_effect_evidence",
    "V_transition_binding",
    "V_execution_binding",
    "V_prestate_binding",
    "V_adapter_binding",
    "V_verifier_policy_binding",
)
```

- [ ] **Step 2: Preserve recomputation before receipt issuance**

```python
recomputed = self.verify_effect(
    transition=transition,
    execution_receipt=execution_receipt,
    witness=witness,
)
if recomputed.status != TRUE or recomputed.root != verification.root:
    raise EffectVerificationError("EFFECT_VERIFICATION_RECOMPUTE_MISMATCH")
```

- [ ] **Step 3: Run PR-3 falsifiers**

```bash
python -m pytest sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py -q
```

Expected: PASS 15/15 or the current frozen suite count if repository discovery records more tests; runner must report actual discovered count.

- [ ] **Step 4: Commit**

```bash
git add harness/sdk/effect_verifier.py schemas/effect-receipt.v1.schema.json sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py
git commit -m "feat(uci): verify effects before issuing effect receipts"
```

---

### Task 5: CompleteVerification Without Admission Promotion

**Files:**
- Create: `harness/sdk/complete_verifier.py`
- Create: `schemas/complete-verification-result.v1.schema.json`
- Test: `sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py`
- Test: `sovereign-omega-v2/python/tests/test_complete_verifier_pr4_receipt_binding.py`

**Interfaces:**
- Consumes: exact nominal `TransitionIdentity`, `DecisionReceipt`, `ExecutionReceipt`, `EffectWitness`, `EffectVerificationResult`, `EffectReceipt`.
- Produces: `CompleteVerificationResult` with `TRUE | FALSE | UNKNOWN | ERROR | MISSING` and no mutation/admission method.

- [ ] **Step 1: Transplant the PR-4 complete verifier**

Required full binding includes transition, execution instance, witness digest, pre/post state, observation provenance, adapter identity/version, effect-verification root, active verifier policy, and admission-policy commitment.

- [ ] **Step 2: Preserve fail-closed decision semantics**

`DecisionReceipt.decision_outcome != PERMIT` must force non-TRUE CompleteVerification.

- [ ] **Step 3: Run primary and receipt-binding falsifiers**

```bash
python -m pytest sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py sovereign-omega-v2/python/tests/test_complete_verifier_pr4_receipt_binding.py -q
```

Expected: PASS, including the four adversarial receipt-binding cases that previously demonstrated forged post-state/provenance/adapter metadata bypasses before the PR-4 fix.

- [ ] **Step 4: Run the Task 1 UCI-4 integration test**

```bash
python -m pytest sovereign-omega-v2/python/tests/test_uci4_effect_chain_integration.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/sdk/complete_verifier.py schemas/complete-verification-result.v1.schema.json sovereign-omega-v2/python/tests/test_complete_verifier_pr4*.py sovereign-omega-v2/python/tests/test_uci4_effect_chain_integration.py
git commit -m "feat(uci): add complete verification over bound effect lineage"
```

---

### Task 6: Exact-Head UCI-4 Contract Gate

**Files:**
- Create: `scripts/run-uci4-effect-chain-tests.py`
- Create: `.github/workflows/uci-4-effect-chain-contract.yml`

**Interfaces:**
- Produces: one exact-head CI gate over all UCI-4 frozen falsification suites plus schema validation.

- [ ] **Step 1: Add a runner that executes discovered tests and fails closed on nonzero exit**

The runner must execute:

```text
test_transition_receipts_pr1.py
test_transition_receipts_cli_pr1.py
test_effect_adapters_pr2.py
test_effect_verifier_pr3.py
test_complete_verifier_pr4.py
test_complete_verifier_pr4_receipt_binding.py
test_uci4_effect_chain_integration.py
```

It must never print a fabricated expected-pass count; report the actual pytest-discovered result.

- [ ] **Step 2: Add a pull-request workflow**

The workflow must checkout the exact PR head, install only required Python/schema dependencies, run the UCI-4 runner, validate all six UCI-4 JSON schemas, and upload a small evidence artifact containing exact head SHA and test summary.

- [ ] **Step 3: Commit**

```bash
git add scripts/run-uci4-effect-chain-tests.py .github/workflows/uci-4-effect-chain-contract.yml
git commit -m "ci(uci): add exact-head effect-chain contract gate"
```

---

### Task 7: Lineage Ledger and Stacked PR

**Files:**
- Create: `docs/audits/2026-08-20-uci4-effect-chain-lineage-ledger.md`
- Modify: no frozen research/property scope documents.

**Interfaces:**
- Produces: repository-bound provenance from #275 exact parent and frozen #268→#273 source lineage.

- [ ] **Step 1: Record exact lineage**

The ledger must record:

```text
UCI4_PARENT = ebec2f9c8fa00f54605d859df61512108ff3b71d
SOURCE_EFFECT_LINEAGE_TIP = 6407db1b0c4176f67a1d7ecbb16eca77d131d87e
SOURCE_PRS = #268 -> #270 -> #272 -> #273
```

- [ ] **Step 2: Record explicit non-claims**

```text
ATOMIC_ADMISSION = NOT_IMPLEMENTED
EFFECT_BOUND_ADMISSION = UNAVAILABLE
PRODUCTION_ADMISSION = NOT_ESTABLISHED
DISTRIBUTED_LINEARIZABILITY = NOT_ESTABLISHED
AGI = NOT_ESTABLISHED
```

- [ ] **Step 3: Open a draft stacked PR against `feat/uci-1-collective-work-contract-v1`**

The PR must bind the exact parent/head, report only executed evidence, and remain draft until the dedicated UCI-4 gate and inherited constitutional gates pass on the exact head.

---

## Self-Review

- Spec coverage: UCI-4 receipt/effect chain is fully covered; AtomicAdmission is deliberately excluded for UCI-5.
- Placeholder scan: no TBD/TODO implementation steps remain.
- Type consistency: the plan uses the exact nominal type names from the frozen #273 lineage.
- Scope check: no #264 provider-organism, #267 memory, #274 domain-capability, or production bridge code is imported in UCI-4.
- Epistemic check: CompleteVerification remains verifier-only and cannot create or imply AdmissionRecord.
