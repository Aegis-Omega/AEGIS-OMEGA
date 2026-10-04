# AEGIS Ω Math Disproval Gate v1 — Design

**Status:** DESIGN_APPROVED_IN_CHAT / PRE_IMPLEMENTATION

**Parent integration spine:** PR #275, `feat/uci-1-collective-work-contract-v1`

**Canonical merge base:** `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`

## 1. Purpose

`MATH_DISPROVAL_GATE_V1` is a formal-verification holon for mathematical claims. It must distinguish failure to prove from mathematical disproof and must never allow a model, search process, timeout, compiler failure, or heuristic counterexample suggestion to promote a claim to `DISPROVED` without kernel-verified formal evidence.

The core epistemic law is:

```text
FAIL_TO_PROVE(P) != DISPROVE(P)
```

A mathematical claim may be marked `DISPROVED` only when at least one admitted proof-assistant kernel verifies either a formal proof of `not P` or a formal counterexample witness satisfying the claim assumptions and violating the claim conclusion.

## 2. Scope

v1 implements:

- a typed `MathClaimEnvelopeV1`;
- a typed `FormalizationBindingV1` for Lean and Rocq source artifacts;
- a typed `KernelVerificationResultV1`;
- a typed `MathVerificationReceiptV1`;
- content-addressed proof/counterexample artifacts;
- fail-closed deterministic aggregation into `PROVED`, `DISPROVED`, or `UNRESOLVED`;
- a separate `verification_level` describing one-kernel versus cross-kernel confirmation;
- explicit semantic-binding protection so two different formalizations cannot be laundered into a cross-kernel verdict;
- closed Draft 2020-12 JSON schemas and adversarial vectors;
- adapter interfaces for Lean and Rocq execution;
- an exact-head witness path and native experiment-admission checkpoint.

v1 does not implement autonomous theorem-prover training, unrestricted package/network installation, proof synthesis authority, external effects, production admission authority, or a general-purpose mathematical truth oracle.

## 3. Trust model

The following are evidence only and never formal authority:

- LLM proof suggestions;
- LLM counterexample suggestions;
- heuristic search;
- SMT/SAT/CAS output unless separately translated into and verified as an admitted kernel artifact;
- timeout;
- process exit without a verified proof artifact;
- parser/compiler errors;
- `no proof found`.

Only an admitted proof-assistant kernel verification result may contribute to a formal mathematical verdict.

A kernel result is still bound to its exact formalization and assumptions. It does not by itself establish that a human-language statement was translated correctly.

## 4. Outcome semantics

### 4.1 Truth verdict

```text
MathTruthVerdictV1 = PROVED | DISPROVED | UNRESOLVED
```

`PROVED` requires at least one admitted kernel to verify the proposition represented by its bound formalization.

`DISPROVED` requires at least one admitted kernel to verify one of:

1. a proof of the formal negation of the proposition; or
2. a counterexample theorem/witness proving the assumptions and the negation of the claimed conclusion for a concrete witness.

Every other state is `UNRESOLVED`.

In particular:

```text
proof search exhausted -> UNRESOLVED
kernel timeout         -> UNRESOLVED
compile failure        -> UNRESOLVED
no candidate proof     -> UNRESOLVED
heuristic witness only -> UNRESOLVED
```

### 4.2 Verification level

Truth and diversity are separate axes:

```text
MathVerificationLevelV1 = SINGLE_KERNEL | CROSS_KERNEL
```

`CROSS_KERNEL` requires at least two admitted kernel results from different verifier families configured for this gate and bound to a shared formalization-binding commitment.

`CROSS_KERNEL` does not mean independent mathematical foundations. Lean and Rocq are treated as implementation/verifier diversity, not proof of foundational independence.

### 4.3 Cross-formalization safety

The gate must not infer:

```text
Lean proves not P_lean
and
Rocq proves not P_rocq
therefore cross-disproved(original claim)
```

unless both formalizations are explicitly bound to the same `claim_digest`, `assumptions_digest`, and `formalization_binding_digest`.

v1 therefore exposes `CROSS_KERNEL` only as a verification level. A stronger semantic-equivalence claim is out of scope unless a later admitted mechanism verifies formalization equivalence.

## 5. Core types

### 5.1 `MathClaimEnvelopeV1`

Required fields:

```text
schema_version
claim_kind = MATH_CLAIM_ENVELOPE_V1
claim_id
claim_text_digest
claim_digest
assumptions_digest
notation_digest
source_artifact_digests[]
policy_commitment
authority_epoch
nonce
authority = NON_AUTHORITATIVE_MATH_CLAIM
```

No field may encode authorization, execution permission, effect truth, or admission.

### 5.2 `FormalizationBindingV1`

Required fields:

```text
schema_version
binding_kind = FORMALIZATION_BINDING_V1
claim_id
claim_digest
assumptions_digest
formalization_binding_digest
lean_source_sha256
rocq_source_sha256
lean_toolchain_commitment
rocq_toolchain_commitment
policy_commitment
authority_epoch
authority = FORMALIZATION_BINDING_ONLY
```

The binding digest commits to the canonical ordered tuple of claim and formalization commitments. The gate must reject mismatched claim, assumptions, policy, epoch, or toolchain bindings.

### 5.3 `KernelVerificationResultV1`

Required fields:

```text
schema_version
result_kind = KERNEL_VERIFICATION_RESULT_V1
kernel_family = LEAN | ROCQ
kernel_version
formalization_sha256
formalization_binding_digest
claim_digest
assumptions_digest
attempt_kind = PROVE | DISPROVE_NEGATION | DISPROVE_COUNTEREXAMPLE
process_status = VERIFIED | REJECTED | TIMEOUT | ERROR
proof_artifact_sha256 | null
counterexample_artifact_sha256 | null
stdout_sha256
stderr_sha256
started_at_ms
finished_at_ms
authority = KERNEL_RESULT_ONLY
```

`process_status=VERIFIED` is necessary but not sufficient for a gate verdict; the attempt kind, artifact commitments, and exact binding must also validate.

### 5.4 `MathVerificationReceiptV1`

Required fields:

```text
schema_version
receipt_kind = MATH_VERIFICATION_RECEIPT_V1
claim_id
claim_digest
assumptions_digest
formalization_binding_digest
verdict = PROVED | DISPROVED | UNRESOLVED
verification_level = SINGLE_KERNEL | CROSS_KERNEL
accepted_kernel_result_hashes[]
rejected_kernel_result_hashes[]
proof_artifact_hashes[]
counterexample_artifact_hashes[]
policy_commitment
authority_epoch
receipt_hash
authority = FORMAL_MATH_EVIDENCE_ONLY
```

The receipt is mathematical evidence only. It is not a DecisionReceipt, ExecutionReceipt, EffectReceipt, operator authorization, or admission record.

## 6. Aggregation rules

The aggregator is deterministic and fail closed.

For each kernel result it must first verify:

- exact allowed keys;
- nominal discriminator;
- digest syntax;
- exact claim/assumptions/formalization binding;
- toolchain commitment;
- kernel family admission;
- monotonic timestamps;
- content-addressed artifact integrity;
- valid attempt/result combination.

Accepted evidence rules:

```text
PROVE + VERIFIED + valid proof artifact
  -> positive proof evidence

DISPROVE_NEGATION + VERIFIED + valid proof artifact
  -> disproof evidence

DISPROVE_COUNTEREXAMPLE + VERIFIED + valid formal witness artifact
  -> disproof evidence

anything else
  -> no truth promotion
```

If valid positive proof evidence and valid disproof evidence exist for the same exact binding, the gate must return `UNRESOLVED` with a `KERNEL_INCONSISTENCY_DETECTED` diagnostic and must never choose one side by majority vote.

If no accepted truth-producing evidence remains, verdict is `UNRESOLVED`.

## 7. Counterexample contract

A counterexample artifact is not merely a model-produced value. It must be a formal source artifact whose admitted kernel verifies a theorem equivalent to:

```text
exists x, Assumptions(x) and not Conclusion(x)
```

or verifies a concrete witness plus proofs of the assumptions and violated conclusion.

The raw proposed witness may be stored as `NON_AUTHORITATIVE_EVIDENCE`, but it cannot cause `DISPROVED` until the formal witness theorem is kernel-verified.

## 8. Adapters

v1 defines runner interfaces rather than embedding proof-assistant logic into the aggregator.

```text
LeanKernelAdapterV1.verify(request) -> KernelVerificationResultV1
RocqKernelAdapterV1.verify(request) -> KernelVerificationResultV1
```

Adapters must:

- execute with a fixed toolchain commitment;
- run with network disabled unless separately admitted;
- enforce bounded wall-clock/runtime limits;
- capture stdout/stderr by digest;
- content-address all formal artifacts;
- never translate a nonzero exit code into `VERIFIED`;
- never translate timeout into disproof;
- never derive authorization from proof success.

The aggregator depends only on typed kernel results, not process-specific output text.

## 9. Claim-ledger integration

The existing manuscript claims ledger remains a separate governance surface. v1 does not replace its `Verified/Derived/Proposed/Removed` taxonomy.

A later claim-ledger entry may reference a `MathVerificationReceiptV1` as evidence. The receipt itself must not mutate the ledger or promote a ledger claim automatically.

No existing claim becomes mathematically proved or disproved merely because this gate is introduced.

## 10. UCI integration

`MATH_DISPROVAL_GATE_V1` is a capability/evidence holon above the UCI authority root.

The intended flow is:

```text
Collective Work Node
  -> provider/model proposes formalization/proof/counterexample
  -> provider contribution evidence
  -> formalization binding
  -> Lean/Rocq adapter execution
  -> kernel results
  -> deterministic math receipt
  -> optional downstream evaluation/admission
```

Provider/model outputs remain evidence only. A math receipt cannot authorize a state mutation or external effect.

## 11. Schemas and serialization

All v1 serialized contracts are Draft 2020-12 JSON Schema with:

- `additionalProperties: false` for records;
- nominal `const` discriminators;
- lowercase SHA-256 patterns;
- bounded strings/arrays;
- explicit authority constants;
- no generic receipt field capable of accepting Decision/Execution/Effect receipts.

Hash domains must be distinct for claim envelopes, formalization bindings, kernel results, counterexample artifacts, and math receipts.

## 12. Required falsification vectors

The canonical corpus must include at least:

1. Lean proof success -> `PROVED/SINGLE_KERNEL`.
2. Rocq proof success -> `PROVED/SINGLE_KERNEL`.
3. Lean formal negation success -> `DISPROVED/SINGLE_KERNEL`.
4. Lean formal counterexample success -> `DISPROVED/SINGLE_KERNEL`.
5. Lean + Rocq same-binding proof -> `PROVED/CROSS_KERNEL`.
6. Lean + Rocq same-binding disproof -> `DISPROVED/CROSS_KERNEL`.
7. timeout -> `UNRESOLVED`.
8. compile error -> `UNRESOLVED`.
9. rejected proof -> `UNRESOLVED`.
10. heuristic counterexample only -> `UNRESOLVED`.
11. mismatched claim digest -> reject result.
12. mismatched assumptions digest -> reject result.
13. mismatched formalization binding -> reject result.
14. stale policy/authority epoch -> reject result.
15. unknown field / authority injection -> reject payload.
16. proof/disproof contradiction under one exact binding -> `UNRESOLVED` + inconsistency diagnostic.
17. artifact digest tamper -> reject result.
18. cross-kernel results over different formalization bindings -> no `CROSS_KERNEL` promotion.
19. attempt kind/result combination laundering -> reject result.
20. receipt injection into kernel result -> reject payload.

## 13. CI and evidence

The implementation checkpoint must be verified by:

- focused unit tests;
- schema tests;
- canonical falsification vectors;
- deterministic replay of the same vectors;
- strict TypeScript typecheck/build for the orchestration/receipt layer;
- Lean smoke proofs/disproofs if Lean is available in the admitted runner;
- Rocq smoke proofs/disproofs if Rocq is available in the admitted runner;
- independent exact-head witness in `tarikskalic33/info`;
- AEGIS native experiment admission bound to the exact candidate SHA.

If one proof assistant is unavailable in a runner, the gate may still establish the orchestration contract and `SINGLE_KERNEL` path, but `CROSS_KERNEL` runtime verification remains `NOT_ESTABLISHED` until both toolchains execute successfully on an exact admitted head.

## 14. Non-claims

This feature does not establish:

- AEGIS as AGI;
- correctness of every human-to-formal translation;
- foundational independence of Lean and Rocq;
- universal mathematical truth;
- proof search completeness;
- that every false proposition will be disproved;
- that every true proposition will be proved;
- any production/external-effect authority.

## 15. Success criterion

v1 is complete only when the repository can mechanically demonstrate the following invariant:

```text
DISPROVED(P)
  => KernelVerified(not P)
     OR KernelVerifiedFormalCounterexample(P)
```

and mechanically falsify:

```text
FAIL_TO_PROVE(P) => DISPROVED(P)
```

for the exact admitted implementation head.
