# PR-2 — Independent Effect Observation & Adapter-Bound Effect Evidence

**Status:** DESIGN FROZEN FOR IMPLEMENTATION

**Stacked parent:** `pr1-transition-receipt-separation@6bf071d9c757d0f3514904f1efad3e3b14a60a09`

**Research/property scope:** unchanged from the frozen EffectBoundClosure program.

## Goal

PR-2 implements the next dependency node after PR-1 SafeIncompleteness:

```text
TransitionBinding
  -> ReceiptSeparation
  -> EffectObservation        # PR-2
  -> CompleteVerification     # later
  -> AtomicAdmission          # later
```

PR-2 must make effect evidence possible **only** through an independent post-effect observation path. It must not implement complete transition verification, atomic admission, or EffectBoundAdmission.

Canonical invariant preserved from PR-1:

```text
AuthorizationDerivedArtifacts
∩ AcceptableEvidence(V_effect)
= ∅
```

New PR-2 invariant:

```text
EffectReceipt production
=> AdapterBoundIndependentObservation
```

and still:

```text
EffectReceipt exists
!=> Verified
!=> Admitted
```

## Epistemic boundary

Decision, execution, and effect evidence remain distinct:

```text
DECISION != EXECUTION != EFFECT
```

An authorization artifact, legacy MutationReceipt, DecisionReceipt, ExecutionReceipt, executor return value, caller-supplied `post_state_digest`, or HTTP/provider success code can never by itself produce valid effect evidence.

The only canonical PR-2 path is:

```text
TransitionIdentity(τ)
  + independent pre-effect observation
  + ExecutionReceipt(τ, execution_instance_id)
  + independent post-effect observation
  -> EffectWitness
  -> adapter-bound EffectReceipt
```

The adapter observes the system of record. It does not trust a caller-provided post-state commitment.

## Scope

### In scope

1. Provider-neutral `EffectAdapter` protocol.
2. First-class `EffectObservationHandle` created from an independent pre-effect observation.
3. First-class `EffectWitness` containing the observed pre/post commitments and observation provenance.
4. Adapter-bound production of `EffectReceipt` using the existing PR-1 nominal `EFFECT_RECEIPT_V1` domain.
5. One deterministic local reference adapter: `FilesystemEffectAdapter`.
6. Fail-closed binding to:
   - TransitionID `τ`;
   - execution instance ID;
   - exact target identity;
   - adapter identity/version;
   - observed pre-state;
   - observed post-state.
7. Tests proving independent observation, no caller post-state authority, no cross-transition splicing, path containment, and no automatic verification/admission semantics.

### Explicitly out of scope

- complete verifier registry / `VerifyTransition(W_pre)`;
- full `V_causality` across arbitrary external providers;
- current-revocation eligibility;
- distributed CAS / database linearization point;
- `AdmissionRecord`;
- EffectBoundAdmission;
- production deployment guarantees;
- payments, messages, actuator, or cloud-specific adapters;
- redefining TypeScript sovereignty `MutationReceiptV1`.

## Types

### EffectObservationHandle

An opaque pre-effect observation record:

```text
EffectObservationHandle = (
  τ,
  target_identity,
  observed_pre_state_commitment,
  pre_observation_provenance,
  adapter_identity,
  adapter_version,
  observer_nonce
)
```

Creation MUST fail if the independently observed pre-state commitment does not equal `TransitionIdentity.pre_state_commitment`.

This prevents a transition authorized against one state from silently observing/mutating another.

### EffectWitness

Produced only after a successful independent post-effect read:

```text
EffectWitness = (
  τ,
  execution_instance_id,
  target_identity,
  observed_pre_state_commitment,
  observed_post_state_commitment,
  effect_changed,
  pre_observation_provenance,
  post_observation_provenance,
  adapter_identity,
  adapter_version
)
```

`effect_changed` is an observation, not an admission result.

A no-op transition may therefore have an EffectWitness with:

```text
effect_changed = false
```

without implying effect success.

### EffectReceipt

PR-1 defined the schema/type but intentionally made it non-constructible. PR-2 enables construction only through the effect-adapter module after a valid independent post-effect observation.

The public generic caller still has no API equivalent to:

```text
make_effect_receipt(post_state_digest=...)
```

and direct `EffectReceipt(...)` construction remains forbidden.

## Filesystem reference adapter

`FilesystemEffectAdapter` is a reference implementation, not the universal semantics of all external effects.

The adapter:

1. is initialized with an explicit `allowed_root`;
2. resolves the target and rejects escape outside `allowed_root`;
3. rejects symlink/path disagreement that crosses the containment boundary;
4. reads the actual target state before execution;
5. computes the state commitment from the observed target identity + content digest;
6. requires that commitment to equal `transition.pre_state_commitment`;
7. after execution, re-reads the target from the filesystem;
8. derives `observed_post_state_commitment` from the new read;
9. records independent observation provenance from filesystem metadata and content digest;
10. issues an adapter-bound `EffectWitness` and `EffectReceipt`.

The post-state value is never accepted from caller input.

## State commitment

Reference filesystem state commitment:

```text
Commit_fs(state) = H_D(
  AEGIS_FILESYSTEM_EFFECT_STATE_V1,
  {
    target_identity,
    exists,
    content_sha256,
    size_bytes
  }
)
```

The target identity is canonicalized relative to the adapter's admitted root so the same bytes at a different target are not the same state commitment.

## Observation provenance

Pre/post observation provenance is domain-separated and includes recorded evidence sufficient for later verifier replay without re-executing the side effect:

```text
ObservationProvenance = H_D(
  AEGIS_EFFECT_OBSERVATION_PROVENANCE_V1,
  {
    τ,
    phase,                    # PRE or POST
    target_identity,
    state_commitment,
    content_sha256,
    size_bytes,
    filesystem_device,
    filesystem_inode,
    filesystem_mtime_ns,
    adapter_identity,
    adapter_version,
    observer_nonce
  }
)
```

Recorded metadata is evidence. PR-2 does not claim that inode/mtime establish philosophical causality.

## Binding rules

PR-2 production fails closed unless:

```text
execution_receipt.transition_id == τ
handle.transition_id == τ
handle.adapter_identity == adapter.identity
handle.adapter_version == adapter.version
handle.target_identity == canonical_target_identity
handle.observed_pre_state_commitment == transition.pre_state_commitment
```

The adapter then performs a fresh post-effect observation itself.

No cross-transition or cross-target receipt splicing is accepted.

## Construction authority

`EffectReceipt` remains `init=False`.

PR-2 adds a module-private adapter construction capability. The canonical effect-adapter code may create the object only after constructing a valid `EffectWitness`; arbitrary callers are not given a generic producer.

This is an architectural producer boundary, not a claim of cryptographic unforgeability against malicious code executing inside the same Python process. Cryptographic producer attestation remains outside PR-2.

## No automatic verification semantics

PR-2 MUST NOT change the epistemic ladder into:

```text
EffectReceipt exists -> Verified
```

Instead:

```text
EffectReceipt exists
=> effect evidence object exists
```

Future PR-3 decides whether the evidence satisfies `V_effect`, `V_binding`, `V_causality`, policy binding, freshness, replay, and the remaining verifier obligations.

Therefore PR-2 postcondition remains:

```text
COMPLETE_VERIFICATION = NOT_IMPLEMENTED
ATOMIC_ADMISSION = NOT_IMPLEMENTED
EFFECT_BOUND_ADMISSION = UNAVAILABLE
C_IMPLEMENTATION = FALSE
```

## Falsification suite

PR-2 acceptance requires tests for at least:

```text
test_authorization_artifact_still_not_effect_evidence
test_legacy_succeeded_receipt_still_not_effect_evidence
test_direct_effect_receipt_construction_still_forbidden
test_caller_post_state_digest_has_no_effect_authority
test_prepare_observation_rejects_pre_state_mismatch
test_prepare_observation_rejects_target_escape
test_prepare_observation_rejects_symlink_escape
test_effect_observation_binds_transition_id
test_effect_observation_binds_execution_instance_id
test_cross_transition_execution_receipt_splicing_fails
test_cross_target_observation_splicing_fails
test_post_state_is_derived_from_fresh_filesystem_read
test_no_effect_produces_evidence_with_effect_changed_false
test_real_effect_produces_distinct_observed_post_state
test_effect_receipt_is_adapter_bound
test_effect_receipt_exists_does_not_imply_verified
test_missing_effect_receipt_still_has_no_legacy_fallback
```

## Required postcondition

If exact-head execution proves the slice:

```text
TRANSITION_BINDING
= IMPLEMENTED_AND_TESTED / inherited PR-1 exact-head witness

RECEIPT_SEPARATION
= IMPLEMENTED_AND_TESTED / inherited PR-1 exact-head witness

EFFECT_ADAPTER_PROTOCOL
= IMPLEMENTED_AND_TESTED_REFERENCE

FILESYSTEM_EFFECT_ADAPTER
= IMPLEMENTED_AND_TESTED_REFERENCE

INDEPENDENT_PRE_POST_EFFECT_OBSERVATION
= IMPLEMENTED_AND_TESTED_REFERENCE

VALID_EFFECT_RECEIPT_PRODUCTION
= ADAPTER_BOUND_ONLY / IMPLEMENTED_AND_TESTED_REFERENCE

AUTHORIZATION_DERIVED_ARTIFACT_ACCEPTED_AS_EFFECT_EVIDENCE
= NEVER

CALLER_SUPPLIED_POST_STATE_ACCEPTED_AS_EFFECT_EVIDENCE
= NEVER

COMPLETE_VERIFICATION
= NOT_IMPLEMENTED

ATOMIC_ADMISSION
= NOT_IMPLEMENTED

EFFECT_BOUND_ADMISSION
= UNAVAILABLE

C_IMPLEMENTATION
= FALSE
```

## Acceptance sentence

> **Effect evidence can only be produced from an independent observation path bound to the exact transition and execution instance; its existence still does not mean the transition is verified or admitted.**
