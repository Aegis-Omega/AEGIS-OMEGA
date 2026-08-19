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

PR #264 contains two relevant provider surfaces with different evidence strength:

- the Python `GovernedProviderRouter` returns `ProviderEvidence`, which binds provider/request/operation/response information but does **not** carry an Automaton-3 `authority_receipt_root`;
- the TypeScript `FrontierInferenceGateway` verifies a `ProofCarryingWorkOrder` through `Automaton3WorkOrderVerifier` and records `workOrderDigest` plus `authorityReceiptRoot` in `FrontierUsageRecord`.

PR-5A MUST NOT fabricate or infer an authority receipt root for the Python provider path. The normative producer for the cross-lineage integration artifact is therefore the TypeScript frontier gateway path whose authority root is already established by the existing Automaton-3 verifier. The Python provider router remains an inherited regression surface only unless it is later upgraded by a separately admitted contract.

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

Introduce the smallest possible cross-language integration contract proving that a governed provider execution record can be referenced by an AEGIS transition bundle without converting the provider result into authority or effect truth.

Nominal artifact:

```text
ProviderExecutionEvidenceBindingV1
```

with mandatory discriminator:

```text
binding_kind = PROVIDER_EXECUTION_EVIDENCE_BINDING_V1
```

and dedicated hash domain:

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

The normative producer MUST consume the exact admitted TypeScript frontier request/result/usage context and MUST reject missing or malformed `work_order_digest` or `authority_receipt_root` rather than substituting values from another runtime.

The Python side may deserialize and verify the serialized artifact for binding/reference purposes, but it MUST NOT reinterpret the artifact as a DecisionReceipt, EffectWitness, EffectReceipt, or authority grant.

This artifact proves only that a provider execution observation is bound to a specific governed request/execution context. It does not prove world effect, causal correctness, task success, or authorization by itself.

## Data Flow

```text
ProofCarryingWorkOrder
    -> Automaton3WorkOrderVerifier
    -> FrontierInferenceGateway
    -> FrontierProviderResult
    -> FrontierUsageRecord
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

The lightweight Python `GovernedProviderRouter -> ProviderEvidence` path remains valid provider evidence but is not promoted into the authority-root-bound PR-5A artifact.

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
- missing authority receipt root on the normative producer path;
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
sovereign-omega-v2/src/api/frontier-provider-evidence-binding.ts
sovereign-omega-v2/test/unit/frontier-provider-evidence-binding.test.ts
schemas/provider-execution-evidence-binding.v1.schema.json
harness/sdk/provider_execution_binding.py
sovereign-omega-v2/python/tests/test_provider_execution_binding_pr5a.py
integration/witness or test-only adapters needed to exercise both lineages
```

The TypeScript module is the normative producer because it has access to the already-verified `authorityReceiptRoot`. The Python module is a strict serialized-artifact validator/binder for the PR #273 lineage; it is not a second authority verifier.

Parent PR #264 and PR #273 production semantics should remain unchanged unless a regression proves an unavoidable compatibility fix is required. Any such fix must be narrowly scoped and separately called out.

## TDD / Falsification Requirements

PR-5A must start RED and cover at minimum:

1. valid exact TypeScript gateway/execution/transition binding -> TRUE/valid artifact;
2. provider `grantsAuthority=true` -> reject;
3. missing authority receipt root -> reject;
4. provider mismatch -> reject;
5. request-id mismatch -> reject;
6. provider-operation-id mismatch -> reject;
7. response-digest mismatch -> reject;
8. work-order-digest mismatch -> reject;
9. authority-receipt-root mismatch -> reject;
10. transition mismatch -> reject;
11. execution-instance mismatch -> reject;
12. parent-state mismatch -> reject;
13. malformed digest -> reject;
14. Python `ProviderEvidence` without authority root cannot be promoted into PR-5A binding;
15. raw ProviderEvidence cannot substitute for EffectWitness;
16. provider binding cannot substitute for EffectReceipt;
17. serialized TypeScript binding validates identically on Python side;
18. CompleteVerification parent suite remains GREEN;
19. PR #264 provider/frontier/constitutional suites remain GREEN;
20. inherited Automaton-3 suite remains GREEN;
21. MCP fail-closed integration remains GREEN;
22. frozen hashes remain valid;
23. no credentials/secrets are introduced.

## Exact-Head Witness

A successful PR-5A candidate requires a fresh external exact-head witness that proves:

```text
BOTH_PARENT_ANCESTORS = ESTABLISHED
PR264_FRONTIER_REGRESSION = PASS
PR264_CONSTITUTIONAL_REGRESSION = PASS
PR273_COMPLETE_VERIFICATION_REGRESSION = PASS
PR5A_TS_PROVIDER_BINDING_FALSIFIERS = PASS
PR5A_CROSS_LANGUAGE_BINDING_PARITY = PASS
PR5A_PYTHON_NON_PROMOTION_FALSIFIER = PASS
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
   and ProviderExecutionEvidenceBindingV1 is produced only from the authority-root-bound frontier gateway path
   and ProviderExecutionEvidenceBindingV1.grants_authority = false
   and Python ProviderEvidence without authority_receipt_root cannot be promoted
   and provider binding cannot satisfy effect obligations
   and all required regressions = PASS
```

This establishes an auditable provider-to-verification integration substrate. It does not establish autonomous admission or general intelligence.