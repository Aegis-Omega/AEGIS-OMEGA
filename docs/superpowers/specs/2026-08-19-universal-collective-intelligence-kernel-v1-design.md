# AEGIS Ω Universal Collective Intelligence Kernel v1 — Design

Date: 2026-08-19
Status: HISTORICAL DESIGN SOURCE / UCI-1 CORE RESTACKED FOR VERIFICATION
Original design parent: `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`
Current restack base: `integration/effect-chain-main-a34d@1406aacca95fef02a942621a7060e0b6b14a5809`

The original design parent is retained as provenance, not presented as current repository
state. The current restack imports only the bounded UCI-1 collective-work contracts,
schemas, validators, and falsification vectors; it excludes the experiment plan and all
later UCI/other semantic lanes. PR #309 is open and not admitted. If admitted, it
supersedes only the older PR #268 -> #270 -> #272 -> #273 effect-chain integration
route; UCI-1 does not duplicate or modify that effect implementation. This document
remains an architectural hypothesis outside production authority and establishes no
AGI, RH, production-readiness, production-deployment, or repository-admission claim.

## 1. Purpose

Define the minimum canonical integration spine that turns AEGIS Ω from a collection of strong but partially disconnected governance, provider, memory, verification, and domain experiments into one evidence-bound collective-intelligence runtime.

This design does **not** claim that AEGIS Ω is AGI. It defines the architecture and testable invariants required for a system that can coordinate heterogeneous models, tools, humans, and domain-capability modules while preserving bounded authority, independent effect verification, replayability, and explicit epistemic status.

Target architectural claim after implementation:

> AEGIS Ω can coordinate heterogeneous intelligence providers through one shared constitutional kernel in which every proposed action is identity-, capability-, policy-, budget-, and transition-bound; provider output remains evidence only; execution does not imply effect; world effects require independently bound evidence and verification before admission.

## 2. Current repository ground truth motivating this design

At the original design revision, canonical main was
`32b7eb6a37fb69d19dd80189390b6641c5004ef1`. Current implementation evidence is bound
separately to the restack base recorded above.

Relevant existing surfaces already exist but are fragmented:

- `sovereign-omega-v2/`: governance runtime, replay, receipts, policy, consensus, evaluator, pipeline and related tested surfaces; much of this remains test-only relative to the production bridge.
- `aegis-cl-psi/`: Rust inference/math fabric.
- `aegis-runtime/`: Seven-Pillar runtime.
- PR #264: provider-neutral cross-provider organism, durable provider contributions, queue/journal, D3/D4 boundaries, common MCP launcher and provider-session contracts.
- PR #268 -> #270 -> #272 -> #273: transition identity, receipt separation, independent effect observation, VerifyEffect, EffectReceipt, and CompleteVerification.
- PR #267: persistent governed memory experiment and collective metacognitive observation layer.
- PR #274: Khatt-Abjad language/calligraphy capability bridge; this is a domain capability and must remain outside the authority root.
- Existing platform endpoints and production bridge already expose collaboration surfaces, but the repository map records a large gap between tested TS governance code and the actual production runtime wiring.

The problem is therefore primarily **canonical integration and authority unification**, not absence of components.

## 3. Design principles

### 3.1 One authority root

There MUST be exactly one constitutional authority root for state-changing decisions. Provider/model outputs, Sensorium observations, memory retrievals, evaluators, benchmarks, language modules, and domain agents MUST NOT become alternate authority roots.

### 3.2 Evidence before authority

All external intelligence enters as evidence. Evidence may affect a decision only through the shared admission path.

```text
Provider / Human / Tool / Sensorium
              |
              v
        Evidence Artifact
              |
              v
      Constitutional Evaluation
              |
              v
         DecisionReceipt
```

### 3.3 Execution is not effect

The kernel MUST preserve:

```text
DecisionReceipt != ExecutionReceipt != EffectReceipt
ExecutionReceipt -/-> EffectReceipt
```

A successful executor status is insufficient to establish that the external world changed as intended.

### 3.4 World truth requires independent evidence

External effects MUST be grounded through an independently bound observation adapter and verifier chain:

```text
WorldObservation
  -> EffectEvidence
  -> VerifyEffect
  -> EffectReceipt
  -> CompleteVerification
```

### 3.5 Complete verification is not admission

`CompleteVerificationResult = TRUE` is a verifier result only. It MUST NOT itself authorize mutation or production admission.

### 3.6 Universal means provider/domain neutrality, not omniscience

The kernel MUST accept capabilities from heterogeneous providers and domain modules through typed contracts. Universal does not mean every model can perform every capability, and no capability may be promoted from `NOT_TESTED`, `PARTIAL`, or `EVIDENCE_ONLY` to authority by declaration.

### 3.7 Fail closed on ambiguity

Unknown provider identity, stale policy, stale authority epoch, expired lease, duplicate work claim, invalid transition binding, ambiguous target, missing observation, failed verifier, missing receipt lineage, or unsupported consequence class MUST terminate as `DENY`, `DEFER/WAITING`, or explicit `NOT_ESTABLISHED` rather than implicit success.

## 4. Core invariant

For every state transition `τ`:

```text
Admit(τ) =>
  Eligible(τ)
  AND Complete(W_pre(τ))
  AND VerifyTransition(W_pre(τ))
  AND CompleteVerification(τ)
  AND CurrentPolicy(τ)
  AND CurrentAuthorityEpoch(τ)
  AND CurrentFence(τ)
```

where `W_pre(τ)` exists before admission and the resulting admission record is a consequence of the decision, never evidence used to prove itself.

No provider output, memory item, evaluation score, Sensorium observation, or domain-capability result can satisfy `Admit(τ)` by itself.

## 5. Universal Collective Intelligence execution model

### 5.1 High-level flow

```text
IntentEnvelope
   |
   v
Capability Decomposition
   |
   v
Collective Work Graph
   |
   v
WorkOrder Admission
   |
   v
Durable Claim / Lease / Fence
   |
   v
Provider / Agent Execution
   |
   v
Content-Addressed Contributions
   |
   v
Cross-Agent Evaluation
   |
   v
DecisionReceipt
   |
   v
ExecutionReceipt
   |
   v
Independent World Observation
   |
   v
EffectEvidence -> VerifyEffect -> EffectReceipt
   |
   v
CompleteVerification
   |
   v
Atomic Admission Gate
   |
   v
Canonical State + Memory + Economic/Operational Receipts
```

### 5.2 Collective Work Graph

A request MUST decompose into typed work nodes rather than free-form agent chat.

Each `CollectiveWorkNodeV1` MUST bind at minimum:

- `work_node_id`
- `objective_digest`
- `required_capabilities[]`
- `allowed_providers[]`
- `allowed_tools[]`
- `dependency_ids[]`
- `input_artifact_digests[]`
- `max_cost_microunits`
- `max_tokens`
- `max_duration_seconds`
- `consequence_class`
- `authority_epoch`
- `policy_commitment`
- `target_commitment`
- `pre_state_commitment`
- `nonce`

The model may propose decomposition. The kernel owns admission of the graph.

### 5.3 Consequence classes

Preserve the existing bounded-authority semantics:

- `D0`: observation/read-only/local reasoning.
- `D1`: reversible local artifact generation.
- `D2`: bounded reversible external operation where policy permits.
- `D3`: explicit operator approval required before execution.
- `D4`: denied unless a separately admitted policy explicitly establishes permission.

No provider may self-promote a work node to a different consequence class.

## 6. Provider-neutral organism

### 6.1 Provider session identity

Every provider session MUST bind:

- provider
- model/deployment
- session identifier
- repository exact HEAD
- provider capability set
- current policy root
- authority epoch
- skill/catalog root
- current organism state root

Session bootstrap remains identity only:

```text
IDENTITY_ONLY_NOT_AUTHORIZATION
```

### 6.2 Durable contribution contract

Provider work MUST be stored as content-addressed evidence with:

- artifact digest
- media type
- size bound
- producer identity
- work-node binding
- exact pre-state fence
- parent journal root
- production timestamp only as metadata, never hash-order authority

Provider contributions MUST remain `NON_AUTHORITATIVE_EVIDENCE` until admitted by the shared kernel.

### 6.3 Lease/fencing requirement

The provider mesh MUST not rely only on queue status. Work claims require durable lease ownership with monotonically increasing fencing generation.

Required properties:

- only one current lease holder per work node;
- stale holder cannot commit after lease replacement;
- retries create a new generation rather than reusing stale authority;
- contribution writes bind the exact lease generation/fence token;
- duplicate provider execution may exist as evidence, but duplicate authoritative commit is impossible.

## 7. Cross-agent evaluation

Collective intelligence MUST not assume independent model failures.

The evaluator layer SHOULD track joint failure evidence by provider/model/task class and MUST keep evaluation distinct from authority.

Minimum evaluator outputs:

- correctness/evidence status;
- policy compliance;
- replay consistency;
- capability misuse;
- contradiction/conflict set;
- correlated-failure indicators where measured;
- confidence/calibration data;
- provenance of evaluator itself.

A consensus score does not establish truth. Conflicting agents produce a conflict artifact that remains unresolved until the relevant verifier/admission rule resolves it.

## 8. Memory

### 8.1 Memory is evidence, not authority

Retrieved memory MUST be treated as historical evidence with lineage. Memory cannot grant capability or authority merely because a prior session recorded it.

### 8.2 Memory record

`CollectiveMemoryRecordV1` SHOULD include:

- content digest
- semantic/index representation
- provenance
- source transition/work-node IDs
- admission status
- policy/version at creation
- supersession/revocation state
- evidence tier
- reconstruction metadata

### 8.3 Memory admission

Only admitted artifacts may enter canonical long-term memory. Unverified provider contributions may enter a quarantined/evidence store but not canonical authoritative memory.

## 9. Effect-bound transition chain

The canonical integration SHALL preserve the semantics developed in the effect-verification PR lineage.

Nominal artifact chain:

```text
TransitionIdentity
DecisionReceipt
ExecutionReceipt
EffectObservationHandle
EffectWitness / EffectEvidence
EffectVerificationResult
EffectReceipt
CompleteVerificationResult
AdmissionRecord
```

Every artifact MUST have:

- mandatory serialized discriminator;
- separate hash domain;
- exact transition binding;
- no generic reinterpretation between epistemic types.

The following theorem remains mandatory:

```text
forall r in AuthorizationDerivedArtifacts:
    r not in AcceptableEvidence(V_effect)
```

## 10. Atomic admission interface

This design introduces an interface requirement, not an immediate claim of distributed linearizability.

The kernel SHALL define `AtomicAdmissionStore` with semantics capable of later being backed by Postgres/Cockroach/etc. The reference implementation may initially be local/test-backed, but status MUST remain explicit.

Required operation conceptually:

```text
compare_and_admit(
  expected_current_state,
  expected_policy,
  expected_authority_epoch,
  expected_fence,
  complete_verification_root,
  next_state,
  admission_record
)
```

It must either commit the state + admission record together or commit neither.

No code may label the local reference implementation as distributed-linearizable without external evidence.

## 11. Capability graph

The universal kernel SHALL represent abilities as explicit capability nodes rather than provider-name assumptions.

Examples:

```text
LANGUAGE.ARABIC.TEXT
LANGUAGE.ARABIC.CALLIGRAPHY
LANGUAGE.ARABIC.MANUSCRIPT
CODE.RUST
CODE.TYPESCRIPT
FORMAL.LEAN
FORMAL.TLA
SECURITY.STATIC_ANALYSIS
WEB.RESEARCH
MEMORY.RETRIEVAL
EFFECT.FILESYSTEM_OBSERVATION
```

Each capability status is separate:

```text
NOT_TESTED | PARTIAL | TESTED_REFERENCE | VERIFIED_FOR_PROFILE | REVOKED
```

Domain modules such as Khatt-Abjad may emit capability evidence. They never expand authority.

## 12. Observability and economic contribution

Operational/economic telemetry may be linked to admitted work but must remain downstream of execution evidence.

Optional `EconomicContributionRecordV1` may bind:

- work node
- admitted artifact(s)
- deployment state
- realized revenue/prize/verified avoided spend
- provider/model/cloud cost
- human review cost
- external labor/economic taxonomy snapshot

Estimated time saved MUST remain `COUNTERFACTUAL_ESTIMATE`, not realized value.

## 13. Security invariants

The v1 kernel MUST preserve at least these fail-closed properties:

1. Provider output cannot authorize itself.
2. Memory cannot authorize itself.
3. Sensorium observation cannot authorize itself.
4. Evaluator/consensus output cannot authorize itself.
5. Decision success cannot masquerade as execution success.
6. Execution success cannot masquerade as effect truth.
7. CompleteVerification cannot masquerade as AdmissionRecord.
8. Stale policy/authority/fence/lease cannot commit.
9. Unknown serialized fields at constitutional boundaries are rejected where the schema is closed.
10. Unknown receipt kinds are rejected.
11. D3 cannot execute without explicit operator approval.
12. D4 remains denied absent separately admitted policy.
13. No generic EffectReceipt producer exists.
14. Provider credentials/signing secrets do not live in provider-facing project configuration.
15. A replay mismatch is a hard failure, not warning-only.

## 14. Canonicalization and hashing

Do not expand unsupported cross-runtime canonicalization claims.

- Existing established JCS paths may be reused only where their exact implementation/evidence status permits.
- New artifact hash domains must be unique and versioned.
- Hashes prove byte/lineage integrity, not proposition truth.
- No local hash-chain statement may be presented as proof that an external-world proposition is true.

## 15. Production wiring target

The v1 work is successful only when one production-oriented path exercises the same kernel surfaces that tests exercise.

Minimum target path:

```text
POST /platform/collaborate
 -> IntentEnvelope
 -> CollectiveWorkGraph
 -> admitted WorkOrders
 -> provider mesh
 -> bounded contributions
 -> evaluation
 -> receipts
 -> effect verification where external mutation occurs
 -> admission
 -> replayable result/evidence bundle
```

The production bridge MUST not keep a parallel simplified authority path that bypasses the canonical contracts.

## 16. PR decomposition

Do not implement this as one mega-PR.

### UCI-1 — Collective Work Contract

Base: canonical main.

Add typed `IntentEnvelope`/`CollectiveWorkGraph`/`CollectiveWorkNode` contracts, capability graph references, consequence classes, closed JSON schemas, validators and adversarial tests.

No provider execution yet.

### UCI-2 — Durable Provider Claim Lease

Stack on UCI-1.

Transplant/reconcile the narrow lease/fencing mechanics required from the provider organism work. Establish monotonic generation and stale-holder rejection.

### UCI-3 — Provider Contribution Evidence

Stack on UCI-2.

Integrate provider session identity + content-addressed contribution contract. Provider output remains non-authoritative evidence.

### UCI-4 — Receipt / Effect Chain Integration

Historical roadmap ordering: stack on UCI-3.

The original future-lane proposal was to reconcile the semantics from #268 -> #273 into
the UCI spine: TransitionIdentity, DecisionReceipt, ExecutionReceipt, independent
EffectEvidence, VerifyEffect, EffectReceipt, CompleteVerification. That proposal is not
an executable instruction for the current UCI-1-only restack and does not establish an
admitted effect path. PR #309 is open and not admitted; if it is admitted, a future
UCI-4 must build on that admitted effect implementation and must not replay the older
#268 -> #270 -> #272 -> #273 integration route.

Preserve nominal serialization and domain separation.

### UCI-5 — Atomic Admission Reference

Stack on UCI-4.

Introduce `AtomicAdmissionStore` reference interface/implementation and prove no admission occurs without CompleteVerification + current eligibility. Do not claim distributed linearizability.

### UCI-6 — Collective Memory Admission

Stack on UCI-5.

Canonical vs quarantined memory split, revocation/supersession semantics, replay binding.

### UCI-7 — Cross-Agent Evaluation

Stack on UCI-6.

Integrate evaluation artifacts, conflict sets and measured correlated-failure metadata without authority promotion.

### UCI-8 — Production Bridge Wiring

Stack on UCI-7.

Wire `/platform/collaborate` to the canonical UCI kernel rather than a parallel simplified path. Add end-to-end bounded provider tests and replay bundle.

### UCI-9 — Repository Admission / Protection

After UCI-8 is green and reviewed.

Add exact-head required checks/branch-protection policy and reconcile stale CI claims in existing PR/document ledgers. This is repository governance, not intelligence logic.

## 17. Existing PR handling

Existing large/stacked PRs are evidence and source material, not automatically merge targets.

- #264: mine narrow provider/session/organism/lease/contribution primitives; do not merge its 85-file/100+ commit history wholesale into the UCI spine.
- #268/#270/#272/#273: historically, preserve semantics and tested falsifiers for a
  future UCI-4 rather than conflate stacked experimental lineage with canonical
  admission. For the current restack, PR #309 is open and not admitted; if admitted, it
  supersedes only this older integration route, and UCI-4 must not duplicate it.
- #267: mine memory authority-gate patterns for UCI-6; do not import hackathon/cloud code unless required by the kernel.
- #274: remains a domain capability module and may later declare tested Arabic/calligraphic capability evidence through the capability graph.

## 18. Testing strategy

Every UCI PR must use test-first development.

Required classes:

- nominal contract tests;
- closed-schema / unknown-field injection tests;
- stale policy tests;
- stale authority epoch tests;
- stale fence/lease generation tests;
- replay tests;
- anti-splicing tests;
- cross-transition tests;
- D3 approval and D4 denial tests;
- provider/model identity mismatch tests;
- duplicate work claim tests;
- contribution tamper tests;
- execution-without-effect tests;
- effect-without-verification tests;
- verification-without-admission tests;
- memory authority rejection tests;
- evaluator authority rejection tests;
- exact-head CI evidence.

Cross-runtime equivalence must only be claimed for contract/hash paths that are actually exercised by independent runtimes.

## 19. Success criteria for v1

The design is implemented only when all are true:

1. One canonical provider-neutral work contract exists.
2. Multiple provider identities can operate through the same bounded work path.
3. Durable lease/fencing prevents stale worker commitment.
4. Provider contributions are content-addressed and non-authoritative.
5. Receipt epistemic types remain separated after serialization.
6. Independent effect evidence is required for external-effect truth.
7. CompleteVerification exists and is not admission.
8. Admission atomically binds current eligibility + verified transition in the reference store.
9. Canonical memory admits only appropriately verified/admitted records.
10. Cross-agent evaluation cannot promote itself to authority.
11. One production-oriented `/platform/collaborate` path uses the same kernel.
12. Exact-head repository CI runs and passes the relevant UCI gates.
13. Documentation explicitly distinguishes architecture, implementation evidence, production evidence, and AGI hypothesis.

## 20. Explicit non-claims

Even after v1 implementation, unless separately established:

```text
GENERAL_INTELLIGENCE = NOT_ESTABLISHED
HUMAN_LEVEL_AGI = NOT_ESTABLISHED
SUPERINTELLIGENCE = NOT_ESTABLISHED
DISTRIBUTED_LINEARIZABILITY = NOT_ESTABLISHED
FULL_PRODUCTION_ROBUSTNESS = NOT_ESTABLISHED
UNIVERSAL_DOMAIN_COMPETENCE = NOT_ESTABLISHED
AUTONOMOUS_D3_AUTHORITY = FALSE
D4_AUTHORITY = DENIED_ABSENT_ADMITTED_POLICY
```

What v1 may establish is narrower and stronger: a provider-neutral, evidence-bound, replay-verifiable collective-intelligence substrate with explicit authority and world-effect boundaries.
