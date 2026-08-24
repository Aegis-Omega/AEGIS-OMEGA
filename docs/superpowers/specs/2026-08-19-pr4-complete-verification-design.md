# PR-4 CompleteVerification Design

## Status

- Design status: APPROVED IN CHAT / SPECIFICATION ONLY
- Exact stacked parent: `PR #272 @ bf29570cf4ae189de93f38a9018e124c2136c687`
- Branch: `pr4-complete-verification`
- Research / epistemological scope: FROZEN
- Implementation scope: CompleteVerification only
- No merge, production admission, causal-claim admission, AtomicAdmission, or EffectBoundAdmission is authorized by this design.

## Goal

Implement a fail-closed `CompleteVerification` gate that consumes already-separated transition artifacts and returns a nominal, hash-bound verification result only when all required decision, binding, execution, effect, and effect-verification obligations are satisfied for the exact same transition.

PR-4 must close the current verification chain without collapsing epistemic classes:

```text
DecisionReceipt
    -> ExecutionReceipt

ExecutionReceipt -/-> EffectReceipt

WorldObservation
    -> EffectEvidence
    -> VerifyEffect
    -> EffectReceipt

DecisionReceipt
+ ExecutionReceipt
+ EffectEvidence
+ EffectVerificationResult
+ EffectReceipt
+ exact TransitionIdentity
    -> CompleteVerification
```

`CompleteVerification` is not state admission. It is a verifier result about one exact transition bundle.

## Frozen Non-Goals

PR-4 MUST NOT implement or claim:

- `CausalClaimAdmission`;
- `AtomicAdmission`;
- `EffectBoundAdmission`;
- production readiness;
- distributed linearizability;
- universal external-effect verification;
- generic EffectReceipt production;
- model or provider output as authority;
- AGI or general-intelligence establishment.

`SAFE_INCOMPLETENESS` remains mandatory whenever an obligation cannot be established.

## Existing Parent Semantics

The parent PR #272 already establishes:

- `TransitionIdentity` / transition root `tau`;
- nominal `DecisionReceipt`, `ExecutionReceipt`, and `EffectReceipt`;
- separate receipt hash domains:
  - `AEGIS_DECISION_RECEIPT_V1`
  - `AEGIS_EXECUTION_RECEIPT_V1`
  - `AEGIS_EFFECT_RECEIPT_V1`
- `WorldObservation -> EffectEvidence` through adapter-bound observation;
- `VerifyEffect` through `EffectVerifier.verify_effect`;
- `EffectReceipt` issuance only when `VerifyEffect=TRUE` and the verification result recomputes identically;
- current effect verification obligations:
  - `V_effect_evidence`
  - `V_transition_binding`
  - `V_execution_binding`
  - `V_prestate_binding`
  - `V_adapter_binding`
  - `V_verifier_policy_binding`.

PR-4 must reuse those artifacts and the existing `EffectVerifier`; it must not create a second effect-verification path.

## CompleteVerification Semantics

### Nominal result type

Introduce a frozen result type:

```text
CompleteVerificationResultV1
```

with mandatory discriminator:

```text
result_kind = COMPLETE_VERIFICATION_RESULT_V1
```

and dedicated hash domain:

```text
AEGIS_COMPLETE_VERIFICATION_RESULT_V1
```

The result is a verifier artifact, not an authority receipt and not an admission record.

### Required input bundle

`CompleteVerifier.verify_complete(...)` consumes exactly:

```text
TransitionIdentity
DecisionReceipt
ExecutionReceipt
EffectWitness              # EffectEvidence
EffectVerificationResult
EffectReceipt
```

No legacy `MutationReceipt`, model output, provider output, caller-supplied post-state digest, raw authorization artifact, or execution-status assertion may substitute for any member of this bundle.

The additional EffectWitness + EffectVerificationResult inputs are required so PR-4 can recompute the parent PR-3 `VerifyEffect` result and prove that `EffectReceipt.effect_verification_root` is bound to the exact evidence actually supplied to CompleteVerification. Merely checking that the receipt contains a 64-hex verification root is insufficient.

### Required obligations

The PR-4 obligation registry is version-bound and ordered:

```text
V_transition_identity
V_decision_receipt
V_decision_authority
V_decision_binding
V_execution_receipt
V_execution_binding
V_effect_evidence
V_effect_verification
V_effect_receipt
V_effect_binding
V_effect_verification_binding
V_verifier_policy_binding
V_admission_policy_binding
```

Status vocabulary remains fail-closed:

```text
TRUE | FALSE | UNKNOWN | ERROR | MISSING
```

The top-level result may be `TRUE` only when every required obligation is `TRUE`.

### Decision semantics

`DecisionReceipt.decision_outcome` must equal `PERMIT`.

```text
DENY  -> CompleteVerification != TRUE
DEFER -> CompleteVerification != TRUE
```

`DEFER -> WAITING` remains the only permitted routing semantics. PR-4 must never reinterpret DEFER as executable or complete.

### Transition binding

All three receipts and EffectWitness must bind the exact recomputed `TransitionIdentity.root`.

Any cross-transition splice must fail:

```text
tau_decision != tau_execution
or
tau_execution != tau_effect
or
tau_witness != tau_effect
or
any tau != TransitionIdentity.root
    => CompleteVerification != TRUE
```

### Execution semantics

CompleteVerification establishes that the execution receipt is nominally valid and transition-bound. It does not infer effect truth from `ExecutionReceipt.outcome`.

Specifically:

```text
ExecutionReceipt(outcome=SUCCEEDED) -/-> EffectReceipt
ExecutionReceipt(outcome=FAILED)    -/-> no-effect
ExecutionReceipt(outcome=CANCELLED) -/-> no-effect
```

The effect path remains independent. A failed or cancelled execution may still have a separately observed and verified external effect.

### Effect semantics

PR-4 accepts only adapter-bound EffectEvidence plus a nominal `EffectReceipt` issued under the PR-3 verifier-gated path.

The complete verifier must:

1. validate the EffectWitness and EffectVerificationResult nominal contracts;
2. call the existing `EffectVerifier.verify_effect(...)` over the exact `TransitionIdentity`, `ExecutionReceipt`, and EffectWitness;
3. require the recomputed verification status to equal `TRUE`;
4. require `recomputed_verification.root == supplied_effect_verification.root`;
5. require `EffectReceipt.effect_verification_root == supplied_effect_verification.root`;
6. require `EffectReceipt.effect_witness_digest == EffectWitness.root`;
7. require `EffectReceipt.transition_id == TransitionIdentity.root`;
8. require `EffectReceipt.execution_instance_id == ExecutionReceipt.execution_instance_id`;
9. require `EffectReceipt.pre_state_commitment == TransitionIdentity.pre_state_commitment`;
10. require `EffectReceipt.verifier_policy_commitment == active PR-3 verifier policy commitment`.

PR-4 does not independently re-observe the world and does not create another EffectReceipt producer. It reuses PR-3 verification deterministically to validate the supplied verification lineage.

## Policy Versioning

Introduce a PR-4 complete-verifier policy with a distinct policy id:

```text
AEGIS_PR4_COMPLETE_VERIFIER_POLICY_V1
```

and a separate commitment helper/domain so the existing PR-3 verifier-policy commitment remains unchanged.

The complete-verifier policy should bind at minimum:

```text
safe_incompleteness = true
required_inputs = [
  TransitionIdentity,
  DecisionReceipt,
  ExecutionReceipt,
  EffectWitness,
  EffectVerificationResult,
  EffectReceipt
]
effect_verification_recompute = REQUIRED
causal_claim_admission = NOT_IMPLEMENTED
atomic_admission = UNAVAILABLE
effect_bound_admission = UNAVAILABLE
```

The existing `TransitionIdentity.verifier_policy_commitment` continues to bind PR-3 effect-verifier policy. PR-4 MUST NOT silently replace it, because doing so would retroactively invalidate the exact parent transition fixtures.

The existing `TransitionIdentity.admission_policy_commitment` must still equal the recomputed active admission-policy commitment. PR-4 does not upgrade that policy into effect-bound admission authority.

## Result Fields

`CompleteVerificationResultV1` should minimally bind:

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

Its root is:

```text
canonical_hash(
  "AEGIS_COMPLETE_VERIFICATION_RESULT_V1",
  serialized_result
)
```

No field may contain an unbound free-form assertion of effect truth or causal truth.

## Denial / Failure Codes

The implementation should use deterministic, testable codes. Minimum required classes:

```text
COMPLETE_VERIFICATION_INPUT_ERROR
COMPLETE_VERIFICATION_MISSING_ARTIFACT
COMPLETE_VERIFICATION_DECISION_NOT_PERMIT
COMPLETE_VERIFICATION_TRANSITION_MISMATCH
COMPLETE_VERIFICATION_EXECUTION_MISMATCH
COMPLETE_VERIFICATION_EFFECT_EVIDENCE_MISMATCH
COMPLETE_VERIFICATION_EFFECT_VERIFICATION_MISMATCH
COMPLETE_VERIFICATION_EFFECT_RECEIPT_MISMATCH
COMPLETE_VERIFICATION_POLICY_MISMATCH
COMPLETE_VERIFICATION_CONTRADICTED
COMPLETE_VERIFICATION_UNRESOLVABLE
COMPLETE_VERIFICATION_INTERNAL_ERROR
NONE
```

A failed or unresolved result must not throw merely because a caller supplied incomplete evidence; the verifier should return a structured fail-closed result where safe. Construction/type errors that make a trustworthy result impossible may raise a bounded verifier exception.

## API Boundary

Preferred reference API:

```python
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
    ) -> CompleteVerificationResult:
        ...
```

No API in PR-4 may accept a generic `Any` artifact and attempt to infer its epistemic role.

## Security Properties / Falsifiers

PR-4 must have explicit tests for:

1. valid exact-transition bundle -> `TRUE`;
2. missing DecisionReceipt -> `MISSING`;
3. missing ExecutionReceipt -> `MISSING`;
4. missing EffectWitness -> `MISSING`;
5. missing EffectVerificationResult -> `MISSING`;
6. missing EffectReceipt -> `MISSING`;
7. `DENY` -> not TRUE;
8. `DEFER` -> not TRUE;
9. decision receipt from another transition -> reject;
10. execution receipt from another transition -> reject;
11. EffectWitness from another transition -> reject;
12. EffectReceipt from another transition -> reject;
13. execution instance mismatch -> reject;
14. supplied EffectVerificationResult whose root differs from recomputation -> reject;
15. EffectReceipt whose `effect_verification_root` differs from verified result -> reject;
16. EffectReceipt whose `effect_witness_digest` differs from supplied EffectWitness -> reject;
17. verifier-policy commitment mismatch -> reject;
18. admission-policy commitment mismatch -> reject;
19. malformed nominal discriminator -> reject;
20. legacy MutationReceipt substitution -> reject by type/interface;
21. raw EffectEvidence substitution for EffectReceipt -> reject by type/interface;
22. authorization-derived artifact substitution for effect -> reject;
23. `ExecutionReceipt.outcome=SUCCEEDED` with missing effect lineage -> not TRUE;
24. failed/cancelled execution with a valid independently observed effect is evaluated from evidence rather than execution status;
25. deterministic root reproducibility for identical complete-verification results;
26. hash-domain separation from Decision/Execution/Effect receipts.

## Compatibility Boundary

PR-4 must not alter the semantic meaning of parent artifacts.

In particular:

- PR-1 receipt hash domains remain unchanged;
- PR-2 EffectEvidence semantics remain unchanged;
- PR-3 VerifyEffect and EffectReceipt issuance remain unchanged;
- the historical Python compatibility `MutationReceipt` remains decision-derived compatibility evidence only;
- TypeScript sovereignty `MutationReceiptV1` is not redefined by this Python reference slice.

## Expected Files

Preferred implementation surface:

```text
harness/sdk/complete_verifier.py              # new CompleteVerification gate
harness/sdk/transition_receipts.py             # PR-4 complete policy commitment helper only
schemas/complete-verification-result.v1.schema.json
sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py
```

Only add other files if exact-head inspection proves they are required for the canonical test runner or schema registry.

## Testing and Evidence

Implementation must be test-first.

Minimum evidence target before any promotion:

```text
PR4_COMPLETE_VERIFICATION_FALSIFICATION_SUITE = PASS
INHERITED_AUTOMATON3_REGRESSION_SUITE = PASS
PR3_EFFECT_VERIFIER_REGRESSION = PASS
SCHEMA_VALIDATION = PASS
MCP_FAIL_CLOSED_INTEGRATION = PASS
```

If AEGIS-hosted GitHub Actions remain blocked before repository-code execution, an external exact-head witness may establish only external exact-head execution. It must not be represented as AEGIS repo-native CI.

## Epistemic Ledger After Successful PR-4

A successful implementation may promote only:

```text
COMPLETE_VERIFICATION
= IMPLEMENTED_AND_TESTED / EXACT_WITNESS_SCOPE
```

while preserving:

```text
CAUSAL_CLAIM_ADMISSION = NOT_IMPLEMENTED
ATOMIC_ADMISSION = UNAVAILABLE
EFFECT_BOUND_ADMISSION = UNAVAILABLE
PRODUCTION_ADMISSION = NOT_ESTABLISHED
C_IMPLEMENTATION = FALSE
```

## Acceptance Theorem

The PR-4 acceptance condition is:

```text
CompleteVerification(tau) = TRUE
iff
  DecisionReceipt is nominally valid
  and DecisionReceipt.outcome = PERMIT
  and DecisionReceipt.transition_id = tau
  and ExecutionReceipt is nominally valid
  and ExecutionReceipt.transition_id = tau
  and EffectWitness is nominally valid and adapter-bound
  and EffectWitness.transition_id = tau
  and EffectVerificationResult is nominally valid
  and EffectVerifier.verify_effect(exact bundle).status = TRUE
  and EffectVerifier.verify_effect(exact bundle).root = EffectVerificationResult.root
  and EffectReceipt is nominally valid
  and EffectReceipt.transition_id = tau
  and EffectReceipt.execution_instance_id = ExecutionReceipt.execution_instance_id
  and EffectReceipt.effect_witness_digest = EffectWitness.root
  and EffectReceipt.effect_verification_root = EffectVerificationResult.root
  and all version-bound CompleteVerification obligations = TRUE.
```

And still:

```text
CompleteVerification = TRUE
-/-> CausalClaimAdmission
-/-> AtomicAdmission
-/-> EffectBoundAdmission
-/-> ProductionAdmission
```

This preserves the frozen principle that no artifact receives greater epistemic authority than the strongest verified transition actually established by its evidence.
