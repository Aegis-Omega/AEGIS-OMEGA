# PR-5A Exact Lineage Integration Bridge Design

## Status

- Design status: APPROVED IN CHAT / SPECIFICATION ONLY
- Branch: `pr5a-exact-lineage-integration`
- Starting parent: PR #273 exact head `6407db1b0c4176f67a1d7ecbb16eca77d131d87e`
- Required second lineage: PR #264 exact head `31aec51c32caa2431cb94ee742c912059802568b`
- Research / epistemological scope: FROZEN
- No merge to `main`, production admission, provider invocation, secret provisioning, billing mutation, causal admission, or AGI claim is authorized by this design.

## Goal

Construct one exact-head integration candidate that contains both independently developed surfaces without weakening either lineage:

1. the provider-neutral frontier mesh from PR #264; and
2. the decision/execution/effect/CompleteVerification chain through PR #273.

PR-5A is an integration bridge only. It must establish coexistence, interface compatibility, and regression integrity. It must not yet implement the General Intelligence Orchestrator.

## Required Lineage

The candidate must preserve both exact ancestry anchors:

```text
PR #264 @ 31aec51c32caa2431cb94ee742c912059802568b
PR #273 @ 6407db1b0c4176f67a1d7ecbb16eca77d131d87e
```

The integration candidate may use a real two-parent merge commit or an equivalent auditable integration commit only if both exact anchors remain provable ancestors of the candidate. A content copy, cherry-pick-only reconstruction, or manual reimplementation of either lineage is insufficient for the primary PR-5A claim.

## Frozen Boundaries

PR-5A MUST preserve all of the following:

```text
Provider/model output = evidence only
Provider/model output != authority
D3 requires explicit operator approval
D4 remains denied
Sensorium = OBSERVATION_ONLY / T2 / authorityWeight=0
Sensorium mayGroundStateTransition = false
ExecutionReceipt -/-> EffectReceipt
CompleteVerification -/-> CausalClaimAdmission
CompleteVerification -/-> AtomicAdmission
CompleteVerification -/-> EffectBoundAdmission
CompleteVerification -/-> ProductionAdmission
```

No generic EffectReceipt producer may be introduced.

## Architecture

### Provider side

Reuse PR #264 as-is for provider registry, proof-carrying work orders, governed routing, transport abstraction, token/cost ceilings, idempotency, stream fencing, entitlement checks, and provider evidence normalization.

`ProviderEvidence.grants_authority` must remain false and any provider attempt to grant authority must fail closed.

### Verification side

Reuse PR #273 as-is for:

```text
TransitionIdentity
DecisionReceipt
ExecutionReceipt
EffectWitness
EffectVerificationResult
EffectReceipt
CompleteVerificationResult
```

The exact PR-3 `EffectVerifier.verify_effect(...)` path remains the only effect-verification algorithm. CompleteVerification remains a verifier artifact, not admission authority.

### Integration bridge

Introduce the smallest possible integration contract proving that provider execution evidence can be referenced by an AEGIS transition bundle without converting the provider result into authority or effect truth.

Preferred nominal artifact:

```text
ProviderExecutionEvidenceBindingV1
```

with mandatory discriminator:

```text
binding_kind = PROVIDER_EXECUTION_EVIDENCE_BINDING_V1
```

and a dedicated hash domain:

```text
AEGIS_PROVIDER_EXECUTION_EVIDENCE_BINDING_V1
```

Minimum bound fields:

```text
provider
request_id
provider_operation_id
response_digest
work_order_digest
authority_receipt_root
transition_id
execution_instance_id
expected_parent_state_root
grants_authority = false
```

This artifact proves only that a provider execution observation is bound to a specific governed request/execution context. It does not prove world effect, causal correctness, task success, or authorization by itself.

## Data Flow

```text
ProofCarryingWorkOrder
    -> GovernedProviderRouter / FrontierInferenceGateway
    -> ProviderEvidence
    -> ProviderExecutionEvidenceBindingV1

ProviderExecutionEvidenceBindingV1
    -> ExecutionReceipt evidence reference only

DecisionReceipt
+ ExecutionReceipt
+ independently observed EffectWitness
+ EffectVerificationResult
+ EffectReceipt
    -> CompleteVerificationResult
```

Hard non-implications:

```text
ProviderEvidence -/-> DecisionReceipt
ProviderEvidence -/-> EffectReceipt
ProviderEvidence -/-> CompleteVerification TRUE
ProviderExecutionEvidenceBindingV1 -/-> Authority
ProviderExecutionEvidenceBindingV1 -/-> EffectTruth
```

## Integration Invariants

The candidate must fail closed if any of these differ:

- provider id;
- request id;
- provider operation id;
- provider response digest;
- work-order digest;
- authority-receipt root;
- transition id;
- execution instance id;
- expected parent-state root.

It must reject:

- provider evidence with `grants_authority=true`;
- cross-transition splicing;
- cross-request splicing;
- cross-execution splicing;
- malformed or non-SHA256 digests;
- D4 work orders;
- D3 work orders without explicit operator approval;
- use of provider output as substitute for EffectWitness, EffectVerificationResult, or EffectReceipt.

## Implementation Scope

Preferred PR-5A changes are limited to:

```text
harness/sdk/provider_execution_binding.py
schemas/provider-execution-evidence-binding.v1.schema.json
sovereign-omega-v2/python/tests/test_provider_execution_binding_pr5a.py
integration/witness or test-only adapters needed to exercise both lineages
```

Parent PR #264 and PR #273 production semantics should remain unchanged unless a regression proves an unavoidable compatibility fix is required. Any such fix must be narrowly scoped and separately called out.

## TDD / Falsification Requirements

PR-5A must start RED and cover at minimum:

1. valid exact provider/execution/transition binding -> TRUE;
2. provider `grants_authority=true` -> reject;
3. provider mismatch -> reject;
4. request-id mismatch -> reject;
5. provider-operation-id mismatch -> reject;
6. response-digest mismatch -> reject;
7. work-order-digest mismatch -> reject;
8. authority-receipt-root mismatch -> reject;
9. transition mismatch -> reject;
10. execution-instance mismatch -> reject;
11. parent-state mismatch -> reject;
12. malformed digest -> reject;
13. raw ProviderEvidence cannot substitute for EffectWitness;
14. provider binding cannot substitute for EffectReceipt;
15. CompleteVerification parent suite remains GREEN;
16. PR #264 provider/frontier/constitutional suites remain GREEN;
17. inherited Automaton-3 suite remains GREEN;
18. MCP fail-closed integration remains GREEN;
19. frozen hashes remain valid;
20. no credentials/secrets are introduced.

## Exact-Head Witness

A successful PR-5A candidate requires a fresh external exact-head witness that proves:

```text
BOTH_PARENT_ANCESTORS = ESTABLISHED
PR264_FRONTIER_REGRESSION = PASS
PR264_CONSTITUTIONAL_REGRESSION = PASS
PR273_COMPLETE_VERIFICATION_REGRESSION = PASS
PR5A_PROVIDER_EXECUTION_BINDING_FALSIFIERS = PASS
INHERITED_AUTOMATON3_REGRESSION = PASS
MCP_FAIL_CLOSED_INTEGRATION = PASS
FROZEN_HASHES = PASS
CREDENTIAL_SCAN = PASS
```

External witness evidence must never be relabeled AEGIS repo-native CI.

## Non-Claims After Success

Even after a successful PR-5A witness:

```text
GENERAL_INTELLIGENCE_ORCHESTRATOR = NOT_IMPLEMENTED
CAUSAL_CLAIM_ADMISSION = NOT_IMPLEMENTED
ATOMIC_ADMISSION = UNAVAILABLE
EFFECT_BOUND_ADMISSION = UNAVAILABLE
PRODUCTION_ADMISSION = NOT_ESTABLISHED
AEGIS_REPO_NATIVE_EXACT_HEAD_CI_PASS = NOT_ESTABLISHED unless independently proven
AGI = NOT_ESTABLISHED
```

## Acceptance Theorem

PR-5A succeeds only if one exact candidate demonstrably contains both exact lineages and all integration-specific plus inherited verification surfaces pass without granting authority to provider/model output.

Formally:

```text
IntegratedCandidate(c)
=> ancestor(c, PR264@31aec51c...)
   and ancestor(c, PR273@6407db1b...)
   and ProviderEvidence.grants_authority = false
   and provider binding cannot satisfy effect obligations
   and all required regressions = PASS
```

This establishes an auditable provider-to-verification integration substrate. It does not establish autonomous admission or general intelligence.