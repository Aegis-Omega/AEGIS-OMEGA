# Cross-Domain Collision V1

Status: DRAFT IMPLEMENTATION SPEC  
Authority: research evidence only  
Parent: Zero-Discretion Type Gates v1 (#320)

## Purpose

Cross-Domain Collision V1 converts integer observations into replayable evidence without treating coincidence as mechanism.

The authoritative path is:

`live source -> immutable snapshot -> offline relation verification -> collision receipt -> null-model receipt -> append-only status transition`

Live connectors are evidence producers only. They cannot admit a claim, promote a status, authorize a mutation, or perform an external effect on behalf of the research verifier.

## Integer-first scope

V1 admits only exact signed integer subjects. Decimal and hexadecimal notation are representations of the same integer, not independent evidence.

For a subject `x`, deterministic transforms are explicit and criterion-bound. In particular:

- `INTEGER_TO_UNICODE_CODEPOINT_V1` maps an in-range integer to its uppercase `U+` code-point label;
- `INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1` maps the integer to its canonical decimal identifier string;
- local arithmetic derivations are separate `DERIVED_PROPERTY` evidence and are not external registry matches.

Unknown transforms fail closed.

## External snapshot boundary

`RegistrySnapshotV1` binds the external registry identity, release/record version, exact query key, result kind, canonical result, source locator, observation date, ingestion producer, and deterministic content digest.

The live ingestion module returns either:

- `ESTABLISHED` with a valid snapshot; or
- `NOT_ESTABLISHED` with no snapshot.

Timeouts, malformed JSON, source failures, and validation failures never become negative registry findings.

## Relation verification

A snapshot does not count merely because its digest exists. `verify_snapshot_observation(...)` recomputes the subject-to-query-key transform before minting `DomainObservationV1`.

For the Unicode transform, the expected query key is the subject's exact `U+` code-point label. For the external decimal-identifier transform, the expected key is the subject's canonical base-10 string. A mismatched key fails before collision scoring.

Each observation binds:

- subject digest;
- domain id;
- evidence class;
- transform id and literal criterion epoch;
- evidence artifact digest;
- normalized claim;
- deterministic observation digest.

## Independence and score

V1 supports only:

`independence_rule_id = UNIQUE_DOMAIN_ID_V1`

and

`score_function_id = UNIQUE_EXTERNAL_DOMAINS_V1`.

The score is the number of unique frozen external/standard domains. Two observations from the same domain count once. `DERIVED_PROPERTY` observations contribute context but never increase the external-domain count.

`CROSS_REGISTRY_COLLISION` requires at least two unique admissible external/standard domains under the frozen criterion.

## Retrospective vs prospective provenance

Every collision receipt binds one of:

- `RETROSPECTIVE`: the subject was already known/selected before the frozen criterion;
- `PROSPECTIVE`: the subject was encountered only after universe, transforms, registries, score function, generator, seed, count, and threshold were frozen.

The provenance is part of the collision receipt hash.

A retrospective observation cannot become promotion-eligible by rerunning it. A retrospective null-model evaluation is descriptive only and requires an explicit opt-in; its receipt contains `promotion_eligible=false` and no `null_survived` verdict.

## Deterministic null model

`CollisionCriterionV1` binds:

- universe bounds;
- external registry set;
- transform set;
- independence rule;
- score function;
- control generator;
- control seed;
- control count;
- optional promotion threshold;
- criterion text.

The criterion digest binds all of those fields, not only the prose label.

V1 control generation uses a local `random.Random(seed)` instance under `PY_RANDOM_UNIFORM_INT_V1`; global PRNG state is irrelevant.

For verified control scores, the finite-sample empirical tail is:

`p_emp = (1 + #{control_score >= observed_score}) / (1 + N_control)`.

A threshold-free criterion produces a descriptive p-value but no survival verdict.

## Status history

Collision status is recorded through the generic hash-chained `StatusJournalV1` foundation.

The V1 statistical path is:

`OBSERVED -> EXACT_MAPPING -> CROSS_REGISTRY_COLLISION -> NULL_SURVIVED -> REPLICATED`.

`NULL_SURVIVED` requires a matching null-model receipt that is both promotion-eligible and surviving. `STRUCTURAL_RELATION` is not a statistical promotion state and cannot be minted by this subsystem.

The generic status journal separately supports explicit demotion while preserving prior evidence and transition hashes.

## Frozen 65010 fixture

`.aegis/cross-domain/fixtures/65010-v1.json` is a retrospective regression fixture, not a significance claim.

It freezes two independent external records observed on 2026-08-25:

1. Unicode 16.0.0: integer `65010` has hexadecimal representation `FDF2`; the deterministic code-point label is `U+FDF2`; the frozen Unicode record names U+FDF2 `ARABIC LIGATURE ALLAH ISOLATED FORM`. Source locator: `https://www.unicode.org/versions/Unicode16.0.0/core-spec/chapter-9/`.
2. NCBI Gene: identifier `65010` resolves to the human protein-coding gene symbol `SLC26A6`; the frozen record notes the NCBI Gene page update date 2026-08-05. Source locator: `https://www.ncbi.nlm.nih.gov/gene/65010/`.

The same bundle also freezes exact local factorisation data as `DERIVED_PROPERTY`; this arithmetic evidence does not count as a third external registry.

The fixture's maximum V1 status without new prospective evidence is `CROSS_REGISTRY_COLLISION`.

No fixture receipt claims causation, biological linkage, theorem-level equivalence, hidden semantics, or non-randomness.

## Fail-closed conditions

Admission/promotion is blocked on missing snapshots, unsupported schemas, subject/query-key mismatch, stale subject digest, unknown transform, external domain absent from the frozen criterion, duplicate-domain inflation, malformed control scores, criterion mismatch, retrospective-to-prospective relabeling, missing null receipt for `NULL_SURVIVED`, or any attempt to mint `STRUCTURAL_RELATION` from collision statistics.

## CI boundary

The authoritative GitHub Actions workflow is offline. It compiles the research modules and runs:

- collision-core regressions;
- live-ingestion boundary regressions using injected transports only;
- frozen 65010 replay regressions;
- inherited zero-discretion research-gate regressions.

The hosted admission path performs no Unicode or NCBI network lookup. Updating an external fact requires a new captured snapshot and therefore new content/observation/collision evidence digests.

A green ancestor is not evidence for a descendant. Exact-head claims require terminal checks on the exact final commit SHA.

## Explicit non-claims

V1 does not establish that cross-domain collisions are meaningful, causal, biologically coupled, mathematically necessary, or evidence for RH/AGI/metaphysical hypotheses. It establishes only exact mappings, provenance, deterministic replay, collision classification, and the machinery required to test future preregistered prospective observations against explicit null models.
