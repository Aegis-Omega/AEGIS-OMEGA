# Cross-Domain Collision V1 — Design

Status: proposed design, approved for specification
Date: 2026-08-25
Parent evidence line: `research/zero-discretion-type-gates-v1@85ceacf48d34dfe3a4dba81f7bb5cb027fb38db3` (#320)
Implementation branch: `research/cross-domain-collision-v1`

## 1. Objective

Build the smallest evidence-bearing AEGIS subsystem that can register an integer observation, ingest externally sourced namespace facts into immutable snapshots, replay those facts offline, detect cross-domain collisions without double-counting correlated evidence, evaluate them against a preregistered null model, and preserve all promotion/demotion transitions in an append-only status history.

The first vertical slice is integer-first. It MUST NOT generalize prematurely to arbitrary scalars, text, geometry, proteins, hashes, or formulas.

The subsystem exists to answer one narrow question rigorously:

> Given an integer `x`, do multiple independently defined domains map `x` to nontrivial facts under a frozen transform/registry contract, and is the observed collision stronger than expected under a preregistered null model?

It does not infer causation, metaphysical meaning, biological mechanism, mathematical equivalence, or theorem-level structural relation from collision frequency alone.

## 2. Governing epistemic law

No collision claim may receive greater epistemic authority than its weakest verified transition.

Live lookup is an evidence producer, never final authority. Offline replay over immutable snapshots is the verification boundary.

The canonical path is:

`Live source -> RegistrySnapshotV1 -> Offline verifier -> CollisionReceiptV1 -> NullModelReceiptV1 -> StatusTransitionV1`

Local deterministic derivations enter through a distinct derivation receipt rather than pretending to be an external registry snapshot.

Any missing, stale, malformed, unbound, or schema-incompatible transition fails closed.

## 3. Required parent semantics

The design reuses the #320 research-admission spine rather than creating a parallel authority system. Before CrossDomainCollisionV1 becomes load-bearing, the parent research gate layer needs two narrowly scoped extensions:

1. **Late-bound relational gates.** Some invariants cannot run at object construction time; they become meaningful only when two or more already-created objects are related. The canonical API must support a deterministic relation check analogous to `subject.against(counterpart)` or an equivalent explicit relational verifier.
2. **Append-only status transition history.** A claim may be demoted when stronger evidence arrives. The history must preserve prior states and their evidence receipts rather than mutating a single status record in place.

These are foundational research-governance semantics. They are not collision-specific exceptions.

## 4. Integer subject model

The V1 subject is a canonical signed integer:

```text
IntegerSubjectV1 {
  value: integer,
  subject_sha256: sha256(canonical-json({schema, value}))
}
```

Decimal, hexadecimal, Unicode notation, registry IDs, and formatted strings are representations or transforms of the integer, not separate subjects.

Example: `65010` and `0xFDF2` are two representations of the same integer subject. `U+FDF2` is the deterministic Unicode code-point label produced when the integer lies in the Unicode scalar/code-point range; the character assignment, official name, decomposition, and other Unicode semantics are separate facts established only by a frozen Unicode snapshot.

## 5. Transform registry

Transforms are versioned, named, deterministic functions whose source definition is frozen by criterion hash.

V1 transform classes:

- `INTEGER_TO_HEX_V1`
- `INTEGER_TO_UNICODE_CODEPOINT_V1`
- `INTEGER_TO_NUMBER_THEORY_PROPERTIES_V1`
- `INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1`

A transform MUST declare:

```text
TransformSpecV1 {
  transform_id
  transform_version
  input_type
  output_type
  criterion_text
  criterion_sha256
}
```

Unknown transforms are inadmissible. Editing transform semantics creates a new criterion epoch.

## 6. External snapshot boundary and local derivations

Live external connectors never participate directly in deterministic collision verification. They produce `RegistrySnapshotV1` artifacts.

```text
RegistrySnapshotV1 {
  schema
  registry_id
  registry_version_or_release
  query_key
  query_key_type
  result_kind
  canonical_result
  source_locator
  source_observed_at
  ingestion_producer_id
  content_sha256
}
```

`content_sha256` binds all canonical snapshot fields. Non-authoritative local execution duration or wall-clock timing is not part of the semantic receipt.

The V1 external registry set is intentionally small:

- Unicode character/code-point data
- NCBI Gene identifier data

The V1 local derived domain is:

- deterministic number-theory properties

Local arithmetic output MUST use a `DerivationReceiptV1` (or the generic parent receipt form extended for deterministic derivations) that binds subject, derivation implementation/version, criterion epoch, canonical result, and result digest. It MUST NOT be labeled `EXTERNAL_IDENTIFIER_MATCH` and MUST NOT increase the independent external-registry count.

The ingestion layer may use live connectors, HTTP clients, or manually imported authoritative snapshots, but downstream offline verification sees only canonical snapshots and deterministic derivation receipts.

## 7. Collision evidence model

A `DomainObservationV1` records one admissible relation between the integer subject and one domain result:

```text
DomainObservationV1 {
  subject_sha256
  domain_id
  evidence_class
  transform_id
  transform_criterion_sha256
  evidence_artifact_sha256
  normalized_claim
  observation_sha256
}
```

Initial evidence classes:

- `EXTERNAL_IDENTIFIER_MATCH`
- `STANDARD_CODEPOINT_MAPPING`
- `DERIVED_PROPERTY`

`evidence_artifact_sha256` binds either the external `RegistrySnapshotV1` or the local deterministic derivation receipt that supports the observation.

A collision is not simply "two facts exist". It is a set of domain observations satisfying independence and anti-double-counting rules. `CROSS_REGISTRY_COLLISION` specifically requires at least two unique admissible external/standard domains under the frozen criterion; local derived properties may enrich the observation profile but cannot satisfy that threshold by themselves.

`CollisionReceiptV1` MUST bind:

- the subject digest;
- exact observation digests;
- unique domain identities;
- evidence classes;
- transform epochs;
- evidence artifact digests;
- independence classification;
- collision score specification digest;
- verdict and reason.

Two observations from the same underlying registry/domain MUST NOT count as two independent domains merely because different transforms expose them.

## 8. Retrospective vs prospective provenance

Every candidate MUST declare selection provenance before significance evaluation:

- `RETROSPECTIVE`: the subject was already known or selected because it appeared interesting before the current criterion/null model was frozen;
- `PROSPECTIVE`: the subject was generated or encountered after the transform set, registry set, universe, score function, and null model were frozen.

A retrospective observation may establish exact mappings and a cross-registry collision. It MUST NOT be promoted to prospective statistical evidence by re-labeling or re-running the same known seed.

The integer `65010` is the canonical V1 retrospective regression fixture.

## 9. Collision score and null model

V1 requires a preregistered `CollisionCriterionV1`:

```text
CollisionCriterionV1 {
  universe_definition
  registry_set
  transform_set
  independence_rules
  score_function
  control_generator
  control_seed
  control_count
  criterion_text
  criterion_sha256
}
```

The null-model evaluator computes an empirical tail probability using a finite control set:

`p_emp = (1 + #{x_control : S(x_control) >= S(x_observed)}) / (1 + N_control)`

The receipt MUST bind the universe, generator/version, seed, control count, score function, and criterion epoch.

No p-value threshold is hard-coded into the concept of collision. Promotion thresholds, if used, are criterion-level policy and therefore epoch-bound.

V1 MUST include a deterministic control generator so exact offline replay produces identical controls from the same seed and criterion.

## 10. Status model

Collision status is an append-only transition history, not a mutable label.

Initial status ladder:

```text
OBSERVED
  -> EXACT_MAPPING
  -> CROSS_REGISTRY_COLLISION
  -> NULL_SURVIVED
  -> REPLICATED
```

`STRUCTURAL_RELATION` is deliberately not the next statistical level. It is a separate claim class requiring independent mechanism, theorem, or domain-specific evidence.

Demotion is permitted and must be recorded, for example:

`NULL_SURVIVED -> CROSS_REGISTRY_COLLISION`

when a corrected null model removes the prior statistical basis.

A `StatusTransitionV1` binds previous state, next state, claim digest, evidence receipt digests, criterion epoch, reason, and transition digest. History cannot be silently rewritten.

## 11. Fail-closed rules

Promotion MUST fail when any of the following holds:

- missing required external snapshot or local derivation receipt;
- malformed or unsupported evidence schema;
- snapshot subject/key mismatch;
- stale or spliced subject digest;
- unknown transform or criterion epoch;
- duplicate counting of the same underlying domain;
- local derived properties counted as independent external registries;
- retrospective observation represented as prospective;
- null model missing frozen universe/score/generator/seed;
- non-deterministic replay under the same inputs;
- evidence receipt with FAIL or ERROR verdict;
- attempt to derive `STRUCTURAL_RELATION` from collision significance alone.

A live source timeout, connector failure, or unavailable registry yields `NOT_ESTABLISHED`, never a negative registry finding.

## 12. 65010 regression fixture

The first fixture exists to prove replay and classification semantics, not significance.

Subject:

`65010`

Expected admissible mappings under frozen evidence:

- integer -> hexadecimal `FDF2` as a deterministic representation;
- integer -> code-point label `U+FDF2` as a deterministic transform, while the Unicode snapshot separately establishes the assigned character metadata for `U+FDF2`;
- integer -> an external NCBI Gene identifier record when the frozen NCBI snapshot establishes that exact identifier;
- deterministic arithmetic properties from the local number-theory evaluator, carried by derivation receipt rather than external-registry classification.

The fixture MUST remain `RETROSPECTIVE`.

The expected status ceiling for the fixture without new prospective evidence is `CROSS_REGISTRY_COLLISION`, and reaching that state requires the frozen Unicode and NCBI evidence to satisfy the criterion's independence rules.

The fixture MUST NOT be used to claim non-randomness, causation, biological linkage, or mathematical mechanism.

## 13. Independence and anti-numerology safeguards

V1 must make post-hoc pattern mining expensive rather than easy.

Rules:

- registry and transform sets are frozen by criterion hash before prospective scoring;
- adding a new transform after seeing a subject creates a new retrospective criterion epoch;
- multiple formatting encodings of one mapping are one observation lineage;
- multiple facts from one registry do not automatically imply independent domains;
- derived arithmetic facts are tagged separately from external registry assignments and do not inflate external-registry count;
- significance is reported against the exact tested universe, not against an unspecified notion of "all numbers";
- every promoted claim retains the denominator: how many candidates were examined under that same criterion.

## 14. Components and files

Expected implementation surfaces:

- `sovereign-omega-v2/python/research_invariants.py`
  - add generic late-bound relational gate semantics;
  - add append-only status transition support;
  - no collision-specific business logic.
- `sovereign-omega-v2/python/cross_domain_collision.py`
  - integer subject model;
  - transform specs;
  - snapshot/derivation validation;
  - domain observations;
  - collision scoring;
  - offline null-model verifier;
  - receipt construction.
- `sovereign-omega-v2/python/cross_domain_ingest.py`
  - live-source to immutable-snapshot boundary;
  - no admission authority.
- `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`
  - RED-first behavioral regressions.
- `.aegis/cross-domain/fixtures/65010-v1.json`
  - retrospective immutable fixture bundle.
- `.github/workflows/cross-domain-collision.yml`
  - deterministic offline CI verification; live network lookups are not required for admission.

Generated repository-cognition artifacts are refreshed only after source/spec changes are complete and must correspond to the exact final tree.

## 15. Required tests

At minimum, implementation must prove:

1. identical evidence artifacts + criterion + seed replay to identical deterministic receipts;
2. changing one deterministic snapshot byte changes its digest and invalidates stale downstream receipts;
3. same-registry duplicate observations cannot inflate independent domain count;
4. a local derived property cannot be counted as an independent external registry;
5. a retrospective seed cannot be admitted as prospective;
6. unknown transform epochs fail closed;
7. connector failure cannot be interpreted as a negative registry result;
8. null controls are exactly reproducible from frozen generator + seed;
9. status can be demoted by new evidence while all prior transitions remain inspectable;
10. `65010` reaches exact-mapping/collision status from frozen fixtures but cannot reach `NULL_SURVIVED` merely because it is interesting;
11. `STRUCTURAL_RELATION` cannot be minted from a p-value or collision receipt alone.

## 16. CI and evidence boundary

The authoritative CI path for V1 is offline. CI MUST NOT depend on mutable external network state.

Live ingestion tests may exist as non-authoritative or manually triggered evidence refresh jobs, but their output must first become committed/hash-bound snapshots before affecting deterministic admission.

Exact-head success requires the relevant unit/falsifier suite and repository-native checks to complete on the final commit SHA. A green run on an ancestor is not evidence for a descendant.

## 17. Explicit non-goals

V1 does not:

- prove that cross-domain collisions are meaningful;
- prove that 65010 has a hidden causal relation across Unicode, genomics, and arithmetic;
- search arbitrary internet text for number mentions;
- accept LLM-generated associations as registry evidence;
- define a general ontology of all domains;
- support approximate floating-point matching;
- infer RH, AGI, biological mechanism, or metaphysical interpretation;
- merge, deploy, or grant runtime mutation authority.

## 18. Success criterion

The vertical slice is successful when an exact repository head can replay a frozen integer fixture entirely offline, independently verify every transform/evidence binding, produce deterministic collision and status receipts, reject at least the specified adversarial falsifiers, and preserve a machine-auditable distinction between:

`exact fact -> observed collision -> statistical survival -> structural explanation`.

Anything stronger remains `NOT_ESTABLISHED` until separately evidenced.
