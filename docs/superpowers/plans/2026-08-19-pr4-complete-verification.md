# PR-4 CompleteVerification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a fail-closed CompleteVerification gate over the exact PR-3 transition/effect lineage without introducing admission authority or a second effect-verification path.

**Architecture:** PR-4 is stacked on PR #272 exact head `bf29570cf4ae189de93f38a9018e124c2136c687`. A new `complete_verifier.py` consumes exact nominal artifacts (`TransitionIdentity`, `DecisionReceipt`, `ExecutionReceipt`, `EffectWitness`, `EffectVerificationResult`, `EffectReceipt`), reuses `EffectVerifier.verify_effect(...)`, and emits a separately domain-bound `CompleteVerificationResult`. PR-3 verifier-policy semantics remain unchanged; PR-4 gets a separate complete-verifier policy commitment.

**Tech Stack:** Python 3.12 stdlib (`dataclasses`, typing), existing AEGIS canonical hashing, JSON Schema draft 2020-12, existing unittest-based exact-head witness pattern.

**Spec:** `docs/superpowers/specs/2026-08-19-pr4-complete-verification-design.md`

## Global Constraints

- Exact stacked parent: `PR #272 @ bf29570cf4ae189de93f38a9018e124c2136c687`.
- Research/epistemological scope is FROZEN.
- Preserve `DecisionReceipt != ExecutionReceipt != EffectReceipt`.
- Preserve `ExecutionReceipt -/-> EffectReceipt`.
- Reuse parent `EffectVerifier`; do not create an alternate effect-verification algorithm.
- CompleteVerification must require the supplied EffectWitness and EffectVerificationResult and recompute the PR-3 verification root.
- No generic `Any` artifact role inference; runtime must fail closed on wrong nominal types.
- `DENY` and `DEFER` can never yield CompleteVerification TRUE.
- Execution outcome is not effect truth; FAILED/CANCELLED execution may still have independently observed verified effect evidence.
- `CausalClaimAdmission = NOT_IMPLEMENTED`.
- `AtomicAdmission = UNAVAILABLE`.
- `EffectBoundAdmission = UNAVAILABLE`.
- `ProductionAdmission = NOT_ESTABLISHED`.
- AEGIS-native CI remains a separate infrastructure claim; external exact-head witness must not be relabeled repo-native CI.

---

### Task 1: Define the PR-4 RED contract and result schema

**Files:**
- Create: `sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py`
- Create: `schemas/complete-verification-result.v1.schema.json`

**Interfaces:**
- Test imports future `CompleteVerifier`, `CompleteVerificationResult`, status constants, and `complete_verifier_policy_commitment` from `harness.sdk.complete_verifier`.
- Tests reuse `FilesystemEffectAdapter`, `EffectVerifier`, receipt types, and existing policy helpers.
- Schema serializes `CompleteVerificationResult` with discriminator `COMPLETE_VERIFICATION_RESULT_V1`.

- [ ] **Step 1: Write the failing PR-4 falsification suite**

Create one `unittest.TestCase` class with helpers that build real filesystem PRE/POST observations and a parent PR-3 EffectReceipt. Cover these exact behaviors:

```python
TEST_NAMES = (
    "test_valid_exact_bundle_is_true",
    "test_missing_decision_receipt_is_missing",
    "test_missing_execution_receipt_is_missing",
    "test_missing_effect_witness_is_missing",
    "test_missing_effect_verification_is_missing",
    "test_missing_effect_receipt_is_missing",
    "test_deny_is_not_complete",
    "test_defer_is_not_complete",
    "test_cross_transition_decision_is_rejected",
    "test_cross_transition_execution_is_rejected",
    "test_cross_transition_witness_is_rejected",
    "test_cross_transition_effect_receipt_is_rejected",
    "test_execution_instance_splice_is_rejected",
    "test_forged_effect_verification_result_is_rejected",
    "test_forged_effect_verification_root_in_receipt_is_rejected",
    "test_forged_effect_witness_digest_in_receipt_is_rejected",
    "test_verifier_policy_mismatch_is_rejected",
    "test_admission_policy_mismatch_is_rejected",
    "test_wrong_nominal_type_is_rejected",
    "test_raw_effect_witness_cannot_substitute_for_effect_receipt",
    "test_succeeded_execution_without_effect_lineage_is_not_complete",
    "test_failed_execution_with_verified_effect_is_evidence_driven",
    "test_no_change_effect_can_complete_when_verified",
    "test_result_root_is_deterministic",
    "test_complete_result_hash_domain_is_separate_from_receipts",
)
```

Use a bundle helper returning:

```python
(tmp, transition, decision, execution, witness, effect_verification, effect_receipt)
```

where EffectReceipt is issued only through `EffectVerifier.issue_effect_receipt(...)`.

- [ ] **Step 2: Write the result schema**

Schema required fields:

```text
result_kind
status
transition_id
decision_receipt_root
execution_receipt_root
effect_witness_digest
effect_verification_root
effect_receipt_root
complete_verifier_policy_commitment
obligations
denial_code
```

Hash fields use `^[0-9a-f]{64}$`; `result_kind` is const `COMPLETE_VERIFICATION_RESULT_V1`; status enum is `TRUE|FALSE|UNKNOWN|ERROR|MISSING`; `additionalProperties=false`.

- [ ] **Step 3: Prove RED on an external exact-head runner**

Run:

```bash
python sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py
```

Expected failure must be the intended missing production module:

```text
ModuleNotFoundError: No module named 'harness.sdk.complete_verifier'
```

Do not accept syntax/import-path errors unrelated to the missing module as a valid RED witness.

- [ ] **Step 4: Commit RED artifacts**

Commit only the test/schema/plan state before production code.

---

### Task 2: Implement CompleteVerification policy, result type, and verifier

**Files:**
- Create: `harness/sdk/complete_verifier.py`

**Interfaces:**
- Consumes exact parent classes:

```python
TransitionIdentity
DecisionReceipt
ExecutionReceipt
EffectReceipt
EffectWitness
EffectVerificationResult
EffectVerifier
```

- Produces:

```python
COMPLETE_VERIFICATION_RESULT_KIND = "COMPLETE_VERIFICATION_RESULT_V1"
OBLIGATION_ORDER = (...13 frozen obligations...)

class CompleteVerificationError(ValueError): ...

@dataclass(frozen=True)
class CompleteVerificationResult:
    result_kind: str
    status: str
    transition_id: str
    decision_receipt_root: str
    execution_receipt_root: str
    effect_witness_digest: str
    effect_verification_root: str
    effect_receipt_root: str
    complete_verifier_policy_commitment: str
    obligations: tuple[tuple[str, str], ...]
    denial_code: str

class CompleteVerifier:
    def verify_complete(
        self,
        *,
        transition: TransitionIdentity,
        decision_receipt: DecisionReceipt | None,
        execution_receipt: ExecutionReceipt | None,
        effect_witness: EffectWitness | None,
        effect_verification: EffectVerificationResult | None,
        effect_receipt: EffectReceipt | None,
    ) -> CompleteVerificationResult: ...
```

- [ ] **Step 1: Implement the separated PR-4 policy commitment**

Use policy id `AEGIS_PR4_COMPLETE_VERIFIER_POLICY_V1` and domain:

```python
canonical_hash("AEGIS_COMPLETE_VERIFIER_POLICY_COMMITMENT_V1", PR4_COMPLETE_VERIFIER_POLICY)
```

The policy binds safe incompleteness, exact required inputs, effect-verification recompute REQUIRED, and all admission non-claims.

- [ ] **Step 2: Implement `CompleteVerificationResult.validate()` and `.root`**

Require exact discriminator, allowed status, 64-hex hash fields, frozen obligation names/order, allowed obligation statuses, and non-empty denial code. Root domain must be exactly:

```python
AEGIS_COMPLETE_VERIFICATION_RESULT_V1
```

- [ ] **Step 3: Implement missing/wrong-type fail-closed input handling**

Missing required artifacts return `status=MISSING`, denial code `COMPLETE_VERIFICATION_MISSING_ARTIFACT`, and ZERO_HASH for unavailable roots.

Wrong nominal types or invalid discriminators return `status=FALSE` with `COMPLETE_VERIFICATION_INPUT_ERROR`; do not infer roles structurally.

- [ ] **Step 4: Implement decision and transition obligations**

Require valid TransitionIdentity and exact receipt roots. Set `V_decision_authority=TRUE` only for PERMIT. DENY/DEFER return FALSE with `COMPLETE_VERIFICATION_DECISION_NOT_PERMIT`.

Require transition_id equality for DecisionReceipt, ExecutionReceipt, EffectWitness, and EffectReceipt.

- [ ] **Step 5: Implement exact effect-lineage recomputation**

Call:

```python
recomputed = EffectVerifier().verify_effect(
    transition=transition,
    execution_receipt=execution_receipt,
    witness=effect_witness,
)
```

Require all of:

```python
recomputed.status == TRUE
recomputed.root == effect_verification.root
effect_receipt.effect_verification_root == effect_verification.root
effect_receipt.effect_witness_digest == effect_witness.root
effect_receipt.execution_instance_id == execution_receipt.execution_instance_id
effect_receipt.pre_state_commitment == transition.pre_state_commitment
```

Do not derive any of these from execution outcome.

- [ ] **Step 6: Implement policy obligations**

Require the transition, supplied effect verification, and EffectReceipt to remain bound to the active PR-3 `verifier_policy_commitment()`. Separately require `transition.admission_policy_commitment == admission_policy_commitment()`.

- [ ] **Step 7: Aggregate deterministically**

Top-level TRUE iff every obligation is TRUE. FALSE dominates UNKNOWN/MISSING; UNKNOWN/MISSING remain non-authoritative; unexpected internal exceptions return ERROR when a trustworthy structured result can still be emitted.

- [ ] **Step 8: Run the PR-4 suite to GREEN**

Run the exact PR-4 test file and require all 25 tests pass.

---

### Task 3: Verify compatibility and serialized contract

**Files:**
- No parent semantic changes unless a failing regression proves one is necessary.

**Interfaces:**
- Parent PR-3 test: `sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py`.
- Inherited Automaton-3 runner: `scripts/run-automaton3-tests.py` (75-test inherited surface).
- Schema: `schemas/complete-verification-result.v1.schema.json`.

- [ ] **Step 1: Run PR-3 regression unchanged**

```bash
python sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py
```

Expected: 15/15 PASS.

- [ ] **Step 2: Run inherited Automaton-3 suite unchanged**

```bash
python scripts/run-automaton3-tests.py --output /tmp/pr4-inherited-summary.json --log /tmp/pr4-inherited.log
```

Expected: 75/75 PASS.

- [ ] **Step 3: Validate serialized result against JSON Schema**

Generate one valid CompleteVerificationResult, convert dataclass tuples through JSON round-trip, and validate with Draft202012Validator.

- [ ] **Step 4: Run MCP fail-closed integration**

Reuse the exact MCP command/path used by PR-3 witness. No promotion if the command is absent or not executed.

- [ ] **Step 5: Commit implementation only after fresh verification evidence**

No `IMPLEMENTED_AND_TESTED` claim before the external exact-head commands return zero failures.

---

### Task 4: External exact-head witness and draft PR

**Files:**
- External witness workflow in the already-used `tarikskalic33/info` runner repository.
- No AEGIS main mutation.

- [ ] **Step 1: Bind witness to exact PR-4 candidate SHA and exact parent `bf29570...`**
- [ ] **Step 2: Execute PR-4 suite, PR-3 regression, inherited 75-test runner, schema validation, and MCP fail-closed integration**
- [ ] **Step 3: Record run id, candidate SHA, test counts, and artifact/evidence digest if emitted**
- [ ] **Step 4: Open a DRAFT stacked PR with base `pr3-verify-effect-receipt-gate`**
- [ ] **Step 5: Preserve these non-claims in PR body**

```text
CAUSAL_CLAIM_ADMISSION = NOT_IMPLEMENTED
ATOMIC_ADMISSION = UNAVAILABLE
EFFECT_BOUND_ADMISSION = UNAVAILABLE
PRODUCTION_ADMISSION = NOT_ESTABLISHED
AEGIS_REPO_NATIVE_EXACT_HEAD_CI_PASS = NOT_ESTABLISHED
C_IMPLEMENTATION = FALSE
```

## Required Postcondition

Only if the fresh exact-head witness succeeds:

```text
COMPLETE_VERIFICATION = IMPLEMENTED_AND_EXTERNALLY_EXACT_HEAD_TESTED_REFERENCE
PR4_COMPLETE_VERIFICATION_FALSIFICATION_SUITE = PASS
PR3_EFFECT_VERIFIER_REGRESSION = PASS
INHERITED_AUTOMATON3_REGRESSION = PASS
SCHEMA_VALIDATION = PASS
MCP_FAIL_CLOSED_INTEGRATION = PASS
```

Still unavailable:

```text
CAUSAL_CLAIM_ADMISSION
ATOMIC_ADMISSION
EFFECT_BOUND_ADMISSION
PRODUCTION_ADMISSION
C_IMPLEMENTATION
```
