# AEGIS Evolutionary Learning Mesh v1 — Design

## Status

PREREGISTERED DESIGN. This document specifies a bounded, evidence-gated learning-replication substrate. It is not evidence that AEGIS self-improves in production, not evidence of AGI, and not authority for autonomous deployment, model retraining, policy mutation, or external effects.

Exact parent: `d113c0511e92670040a3a70fbfdc2c3e7bae617f` on the UCI-8 evaluation lineage. This design is intentionally isolated on `feat/evolutionary-learning-mesh-v1`; it does not redefine frozen UCI-8 claim semantics or promote the current actual-compute RED state.

## Goal

Make verified learning artifacts heritable across an agent mesh while preserving the constitutional separation between capability and authority.

The V1 system must support the following closed loop:

`verified experience -> learning candidate -> lineage-bound mutation -> external evaluation evidence -> replication admission -> scoped replication -> new local evaluation`

The system may propagate a capability artifact only after evidence-bound admission. It must never propagate or mint authority merely because an artifact improved performance.

Core invariant:

`Replicate(Capability) != Replicate(Authority)`

and, more strongly:

`Capability(g+1) > Capability(g)` may be an optimization target, but `Authority(g+1) > Authority(g)` is invalid without a separate pre-existing authority admission path.

## Scope of V1

V1 is a local/reference control-plane implementation for heritable skill artifacts and their evidence lineage. It does not train frontier models or autonomously edit executable production code.

V1 includes:

1. a closed `LearningCapsuleV1` artifact;
2. explicit parent/child lineage and generation identity;
3. mutation envelopes that bind a child artifact to one parent and one preregistered mutation operator commitment;
4. external evaluation evidence bindings;
5. binary replication admission;
6. bounded replication envelopes defining target, generation, fan-out, and capability scope;
7. a tamper-evident lineage ledger/reference chain;
8. fail-closed replay verification;
9. tests proving that no learning artifact can mint authority.

V1 excludes:

- live foundation-model weight updates;
- autonomous code deployment;
- autonomous policy edits;
- autonomous capability grants;
- self-issued evaluation truth;
- self-issued authority receipts;
- recursive unbounded fan-out;
- provider-signed cross-provider training/evaluation proof;
- claims that improvement generalizes outside the exact preregistered evaluation population;
- claims that the mesh is AGI or self-improving in an unrestricted sense.

## Relationship to existing AEGIS evidence boundaries

The Evolutionary Learning Mesh is downstream of existing execution/evaluation evidence. It consumes evidence roots; it does not manufacture higher epistemic authority for them.

The intended boundary is:

`Execution evidence -> Evaluation evidence -> Learning admission`

not:

`Learning artifact -> truth`

and never:

`Learning artifact -> authority`.

Where UCI-8 or a successor provides actual-compute-matched evaluation evidence, the mesh may bind that evidence by root. Until such evidence exists and verifies, the mesh must remain unable to claim compute-controlled structural improvement.

The learning layer therefore treats every external evaluation root as evidence with an explicit evidence class. V1 must not silently translate `LOCAL_REFERENCE_TESTED` into `EXTERNALLY_ESTABLISHED`.

## Core contract types

### `LearningCapsuleV1`

A capsule is the smallest heritable learning unit.

Required fields:

- `capsule_id`
- `skill_id`
- `generation >= 0`
- `content_commitment`
- `source_experience_root`
- `parent_capsule_root`: null only for generation 0
- `mutation_envelope_root`: null only for generation 0
- `training_runtime_commitment`
- `task_population_commitment`
- `capability_scope_commitment`
- `evaluation_evidence_root`
- `evaluation_evidence_class`
- `failure_mode_commitment`
- `created_by_runtime_commitment`
- `capsule_kind = LEARNING_CAPSULE_V1`

The capsule root is domain-separated and canonical. Any change to content, evidence, lineage, task population, runtime identity, or capability scope changes the root.

A capsule contains no authority grant, role elevation, lease, policy mutation, tool grant, or external-effect permission.

### `MutationEnvelopeV1`

A mutation envelope binds one proposed child to one exact parent.

Required fields:

- `parent_capsule_root`
- `parent_generation`
- `child_content_commitment`
- `mutation_operator_id`
- `mutation_operator_commitment`
- `mutation_seed_commitment`
- `mutation_budget_commitment`
- `requested_capability_scope_commitment`
- `envelope_kind = MUTATION_ENVELOPE_V1`

V1 does not require the mutation generator itself to be deterministic. It requires the mutation identity, seed commitment, budget commitment, parent, and resulting content commitment to be bound so the resulting child cannot be spliced into a different lineage after evaluation.

The requested capability scope may be equal to or narrower than the parent's admitted scope. A mutation envelope requesting a broader scope is ineligible in V1.

### `LearningEvaluationEvidenceV1`

This type is a reference boundary, not an evaluator.

Required fields:

- `evaluated_capsule_root`
- `task_population_commitment`
- `evaluator_runtime_commitment`
- `evaluation_protocol_commitment`
- `comparison_baseline_root`
- `metric_set_commitment`
- `compute_evidence_root`
- `execution_receipt_bundle_commitment`
- `status`: `SATISFIED | FALSIFIED`
- `evidence_class`
- `evidence_kind = LEARNING_EVALUATION_EVIDENCE_V1`

The mesh must not create this object from raw model claims. Production issuance requires a separately admitted evaluator boundary. The reference implementation may construct fixtures in tests, but such fixtures carry no external epistemic status.

`SATISFIED` means only that the exact preregistered evaluation contract bound by this evidence object was satisfied. It does not mean globally better, safe, canonical, or authorized.

### `ReplicationAdmissionV1`

Binary admission result:

- `ELIGIBLE`
- `INELIGIBLE`

Required bindings:

- capsule root
- evaluation evidence root
- parent capsule root, when generation > 0
- lineage root
- target capability scope commitment
- replication policy commitment
- admission reason code
- admission kind

There is no `PARTIAL`, `PROVISIONAL_SUCCESS`, or equivalent success-adjacent state in V1.

### `ReplicationEnvelopeV1`

Defines the exact bounded propagation event.

Required fields:

- `source_capsule_root`
- `replication_admission_root`
- ordered, non-empty `target_runtime_commitments[]`
- `target_capability_scope_commitment`
- `max_children`
- `max_generation`
- `replication_budget_commitment`
- `expiry_sequence`
- `envelope_kind = REPLICATION_ENVELOPE_V1`

A replication envelope does not execute a remote deployment. It authorizes only the reference transfer/admission of a learning artifact into a target learning registry under the exact bound scope.

### `LearningLineageEntryV1`

Tamper-evident lineage record:

- monotonic `sequence`
- capsule root
- parent capsule root or genesis marker
- generation
- mutation envelope root or genesis marker
- evaluation evidence root
- replication admission root
- previous lineage entry hash
- entry hash

The entry hash uses a domain-separated canonical representation. Replay from genesis must reproduce the same terminal lineage root.

## State machine

The V1 lifecycle is:

`OBSERVED_EXPERIENCE`
-> `CANDIDATE_CREATED`
-> `EVALUATED`
-> `ELIGIBLE | INELIGIBLE`
-> if eligible: `REPLICATED`
-> target-local `EVALUATED`

A replicated artifact does not inherit the source environment's success by declaration. The target must preserve source evidence but perform a target-local evaluation before the replicated artifact can become locally preferred or produce another generation.

A failed local evaluation does not delete the source lineage. It creates a new evidence record attached to the target-local evaluation context.

## Heritability and generation rules

1. Generation 0 capsules have no parent and no mutation envelope.
2. Generation `g+1` must bind exactly one parent at generation `g`.
3. A child cannot claim multiple parents in V1. Recombination/crossover is a future protocol because it creates substantially harder provenance semantics.
4. A child's requested capability scope cannot exceed its parent's admitted capability scope.
5. A child's generation must equal `parent.generation + 1` exactly.
6. Parent capsule roots are immutable.
7. Failed children remain in lineage as failed/ineligible candidates if they entered the evaluation ledger; they are not deleted to create a cleaner ancestry.
8. A new mutation seed creates a distinct mutation envelope and therefore a distinct child attempt.

## Selection semantics

V1 does not define a universal scalar fitness function. A single scalar would prematurely collapse heterogeneous metrics, costs, and risk into one gameable number.

Selection is instead preregistered and binary:

`Select(child)` only if:

- all required evaluation metrics satisfy their preregistered floors;
- evaluation evidence is bound to the exact child root;
- the exact task population matches the preregistered population;
- required compute/execution evidence roots are present;
- capability scope is not widened;
- lineage replay verifies;
- replication policy bounds are satisfied.

A future protocol may add Pareto or scalar fitness selection, but V1 must not infer it.

## Replication semantics

Replication means copying a verified learning artifact and its evidence/lineage bundle into another agent/runtime learning registry. It does not mean cloning a running process, opening new accounts, deploying autonomous services, creating credentials, or acquiring new external tools.

The target registry stores:

- capsule root and content commitment;
- parent lineage proof;
- source evaluation evidence root;
- source admission root;
- target-local evaluation state.

A target must treat a newly replicated capsule as `IMPORTED_UNVERIFIED_LOCALLY` until target-local evaluation completes.

Only after local `SATISFIED` evidence may it transition to `LOCALLY_ELIGIBLE`.

## Authority firewall

The following fields are forbidden in learning/mutation/replication contracts:

- policy write authority;
- role promotion;
- D3/D4 authority elevation;
- lease issuance;
- capability grant issuance;
- secret access grant;
- external side-effect authorization;
- admission-record impersonation;
- effect-receipt impersonation.

No API in the learning module may return an existing AEGIS authority type as a side effect of learning admission.

The strongest invariant is:

`forall learning_artifact: learning_artifact notin AuthorizationDerivedArtifacts`

and:

`LearningAdmission(artifact) => CapabilityEvidenceEligible(artifact)`

but not:

`LearningAdmission(artifact) => AuthorityEligible(artifact)`.

Any future bridge from learning into authority must be a separately specified, externally authorized transition and is out of scope for V1.

## Contamination and self-propagation defense

The mesh deliberately distinguishes controlled learning replication from uncontrolled memetic propagation.

Untrusted agent messages, prompts, generated rationales, or shared-memory text cannot directly become a capsule. They may only become `source experience` candidates.

The admissible path is:

`untrusted idea -> experience candidate -> evidence-bound capsule -> evaluation -> admission -> bounded replication`

The forbidden path is:

`untrusted idea -> shared memory -> automatic replication`.

A capsule's content commitment must be bound before evaluation. Post-evaluation content mutation invalidates the evidence binding.

## Fan-out and recursion bounds

V1 replication is always finite.

Required policy constraints:

- `max_children >= 1` and finite;
- `max_generation >= source_generation` and finite;
- target list cardinality must not exceed `max_children`;
- expired replication envelopes fail closed;
- a target cannot use the source envelope as authority to create grandchildren;
- every next-generation replication requires a fresh mutation envelope, fresh evaluation evidence, and fresh replication admission.

There is no unbounded recursive self-spawn primitive in V1.

## Replay and anti-splicing requirements

The implementation must reject:

1. child capsule whose parent root differs from mutation envelope parent;
2. child generation not equal to parent generation + 1;
3. evaluation evidence bound to a different capsule;
4. evaluation evidence bound to a different task population;
5. replication admission bound to a different evaluation evidence root;
6. replication envelope bound to a different admission root;
7. capability scope widening at mutation or replication boundary;
8. duplicate lineage sequence or broken previous-hash link;
9. lineage replay terminal mismatch;
10. content commitment changed after evaluation;
11. manually fabricated success that lacks the required evaluation-evidence object;
12. authority-bearing fields or authority-type outputs from the learning module.

## Error handling

All malformed, missing, mismatched, widened, expired, replay-divergent, or evidence-incomplete states fail closed with stable machine-readable reason codes.

No exception path may silently downgrade a verification failure into eligibility.

At minimum the reference implementation should distinguish:

- `LEARNING_PARENT_MISMATCH`
- `LEARNING_GENERATION_MISMATCH`
- `LEARNING_MUTATION_SCOPE_WIDENING`
- `LEARNING_EVALUATION_BINDING_MISMATCH`
- `LEARNING_EVALUATION_FALSIFIED`
- `LEARNING_EVIDENCE_INCOMPLETE`
- `LEARNING_REPLICATION_SCOPE_WIDENING`
- `LEARNING_REPLICATION_FANOUT_EXCEEDED`
- `LEARNING_REPLICATION_GENERATION_EXCEEDED`
- `LEARNING_REPLICATION_EXPIRED`
- `LEARNING_LINEAGE_REPLAY_DIVERGED`
- `LEARNING_AUTHORITY_REPLICATION_FORBIDDEN`.

## Initial implementation boundaries

The first production slice should remain intentionally small:

- Python reference contracts in `harness/sdk/evolutionary_learning.py`;
- tests in `python/tests/test_evolutionary_learning_mesh_v1.py` or the repository's exact prevailing UCI test location;
- JSON Schemas only after the Python semantic contract is RED-tested and stable;
- no provider calls;
- no remote execution;
- no model retraining;
- no UCI-8 semantic changes;
- no mutation of frozen constitutional files.

The mutation operator in V1 is an externally supplied commitment plus child content commitment. Generating mutations with an LLM is a later adapter; the constitutional kernel first proves it can bind, evaluate, admit, and replay mutations safely.

## TDD falsifiers to preregister before production implementation

At minimum:

1. generation-1 capsule without parent fails;
2. generation-0 capsule with parent fails;
3. child generation skip (`g -> g+2`) fails;
4. mutation parent/capsule parent mismatch fails;
5. capability-scope widening fails;
6. `FALSIFIED` evaluation cannot yield `ELIGIBLE`;
7. evaluation for another capsule cannot be reused;
8. evaluation for another task population cannot be reused;
9. replication envelope without matching admission fails;
10. fan-out above `max_children` fails;
11. generation above `max_generation` fails;
12. expired envelope fails;
13. content mutation after evidence issuance changes root and invalidates admission;
14. removed/reordered lineage entry causes replay failure;
15. imported capsule starts locally unverified;
16. target-local success can create local eligibility without rewriting source evidence;
17. learning module cannot emit or embed authority grants;
18. same canonical input reconstructs the same capsule/lineage roots across process reconstruction.

The initial GREEN is meaningful only if these falsifiers are observed RED before production implementation.

## Evidence status vocabulary

V1 implementation reports must use explicit statuses:

- `DESIGN_PREREGISTERED`
- `RED_FALSIFIERS_OBSERVED`
- `LOCAL_REFERENCE_IMPLEMENTED_AND_TESTED`
- `REPLAY_VERIFIED_LOCAL`
- `EXTERNAL_EVALUATION_BOUND`
- `TARGET_LOCAL_REPLICATION_VERIFIED`

The following are forbidden unless independently established:

- `SELF_IMPROVING_AGI`
- `AUTONOMOUS_RECURSIVE_SELF_IMPROVEMENT`
- `GLOBAL_GENERALIZATION_PROVEN`
- `AUTHORITY_SELF_REPLICATION`
- `PROVIDER_INDEPENDENT_TRAINING_ATTESTATION_ESTABLISHED`.

## Completion criteria for V1

V1 is `LOCAL_REFERENCE_IMPLEMENTED_AND_TESTED` only when:

- all preregistered RED falsifiers fail for the intended reason before implementation;
- the minimal production contracts make them GREEN;
- lineage replay is deterministic and tamper-evident in tests;
- capability scope cannot widen through mutation or replication;
- a `FALSIFIED` evaluation cannot replicate;
- imported artifacts require target-local evaluation;
- the learning module has no code path that creates authority grants or effect authority;
- inherited exact-head prooflines remain green;
- hosted CI emits a content-addressed witness for the exact head.

A real self-replicating-learning claim requires an additional external experiment showing at least one admitted capsule propagated to a distinct target runtime, was independently re-evaluated there, and either reproduced or failed to reproduce the preregistered gain. Until that exists, the correct status is local/reference implementation only.

## Future extensions explicitly deferred

- multi-parent crossover/recombination;
- provider-specific learning adapters;
- LoRA/adapter or model-weight mutation;
- continual-learning replay buffers;
- Pareto-front selection;
- decentralized multi-node lineage consensus;
- public-key signatures for cross-organization replication;
- external timestamp/transparency anchoring for learning lineage;
- automatic generation of mutation candidates;
- economic/metabolic selection budgets beyond fixed preregistered envelopes.

Each requires a separate design and evidence boundary rather than silent expansion of V1.
