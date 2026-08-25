# Cross-Domain Collision V1

Status: DRAFT IMPLEMENTATION SPEC  
Authority: research evidence only  
Parent: Zero-Discretion Type Gates v1 (#320)

## Purpose

Cross-Domain Collision V1 converts integer observations into replayable evidence without treating coincidence as mechanism.

The promotion-grade computational path is now:

`live/source evidence -> immutable source artifact -> frozen registry adapter -> verified registry probe -> verified control coverage -> collision receipt -> coverage-bound null-model receipt -> append-only status transition`

Live connectors remain evidence producers only. They cannot admit a claim, promote a status, authorize a mutation, or perform an external effect on behalf of the research verifier.

## Integer-first scope

V1 admits only exact signed integer subjects. Decimal and hexadecimal notation are representations of the same integer, not independent evidence.

For a subject `x`, deterministic transforms are explicit and criterion-bound. In particular:

- `INTEGER_TO_UNICODE_CODEPOINT_V1` maps an in-range integer to its uppercase `U+` code-point label;
- `INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1` maps the integer to its canonical decimal identifier string;
- local arithmetic derivations are separate `DERIVED_PROPERTY` evidence and are not external registry matches.

Unknown transforms fail closed.

## External snapshot boundary

`RegistrySnapshotV1` binds registry identity, release/record version, exact query key, result kind, canonical result, source locator, observation date, ingestion producer, and deterministic content digest. Hash-bound nested payloads are defensively deep-frozen before downstream use.

The live-ingestion boundary returns either established source evidence or `NOT_ESTABLISHED`; transport, parser, schema, and source failures never become negative registry findings.

## Relation verification

A snapshot does not count merely because its digest exists. Subject-to-query-key relations are recomputed before observations or probe evidence may be minted.

Each collision observation binds the subject digest, domain, evidence class, transform and criterion epoch, source-evidence digest, normalized claim, and deterministic observation digest. Two observations from the same external domain still count once under `UNIQUE_DOMAIN_ID_V1`; local `DERIVED_PROPERTY` evidence never increases the external-domain score.

## Retrospective vs prospective provenance

Every collision receipt binds `RETROSPECTIVE` or `PROSPECTIVE` provenance. That provenance is hash-bound.

A retrospective subject cannot become prospective merely by rerunning it. Retrospective null evaluation is descriptive only, requires explicit opt-in, carries `promotion_eligible=false`, carries no `null_survived` verdict, and does not claim promotion-grade control coverage.

## Proof-carrying registry probes

An empty observation set is **not** evidence that a registry was queried and returned no match. It may equally mean that the registry was not queried, the query failed, the response was ambiguous, or evidence was omitted.

Promotion-grade control evaluation therefore uses `RegistryProbeOutcomeV1` with three distinct outcomes:

- `MATCH`;
- `NO_MATCH`;
- `NOT_ESTABLISHED`.

`NO_MATCH` is not a fallback state. It requires an immutable source artifact whose result is classified by a frozen `RegistryAdapterContractV1` with an explicit negative-result rule. Timeout, missing data, malformed data, parser failure, unsupported semantics, and absent evidence are never converted into `NO_MATCH`.

A raw hash-valid `RegistryProbeReceiptV1` is not sufficient promotion authority by itself. `VerifiedRegistryProbeV1` carries the exact subject, exact collision criterion, frozen adapter, probe receipt, and the immutable source snapshot or failure artifact needed to replay the classification. Verification reconstructs the probe and requires byte-semantic receipt equality. This blocks hash-valid subject, criterion, adapter, and source splicing.

The current promotion-grade adapter implementation is intentionally narrow and deterministic. Its fixture rule family classifies a literal boolean `match` field under frozen local adapter contracts. This proves the evidence/authority mechanics; it is **not** a claim that real Unicode or NCBI negative-result semantics have already been formalized for prospective experiments.

## Control coverage

`ControlCoverageReceiptV1` binds one generated control subject to the complete frozen registry set. `VerifiedControlCoverageV1` additionally carries the source-bound verified probe bundles required to replay that receipt.

For a frozen registry set `R`, coverage is complete iff every registry in `R` appears exactly once, no extra registry appears, every probe is bound to the same subject and criterion, every probe re-verifies, and every outcome is `MATCH` or `NO_MATCH`. Missing probes and `NOT_ESTABLISHED` outcomes are represented explicitly and make `coverage_complete=false`. Duplicate or extra registry probes fail closed.

`coverage_complete` is derived; it is never accepted as caller-supplied authority.

Control collision construction is also derived from the exact probe bundle. `MATCH` probes mint external collision observations; `NO_MATCH` probes contribute coverage but no collision observation; `NOT_ESTABLISHED` contributes neither a match nor complete coverage. The null evaluator recomputes each control collision from its bound coverage probes and rejects a collision/coverage score splice even when subject and criterion are otherwise identical.

## Deterministic null model

`CollisionCriterionV1` hash-binds universe bounds, registry set, transform set, independence rule, score function, control generator, seed, control count, optional threshold, and criterion text. V1 control generation uses a local `random.Random(seed)` instance; global PRNG state is irrelevant.

The null evaluator does not accept caller-supplied scalar scores. It regenerates the exact ordered control-subject sequence. For a prospective observed collision, every generated control position must carry:

1. a hash-valid `CollisionReceiptV1`;
2. a replay-valid `VerifiedControlCoverageV1`;
3. exact subject equality with the generated control at that position;
4. exact criterion equality;
5. `coverage_complete=true`;
6. a collision receipt that is reproduced from the exact bound probe bundle.

Missing coverage blocks prospective null evaluation. Reordered coverage, cross-subject coverage, cross-criterion coverage, source/probe tampering, or collision/coverage score splicing fail closed.

The finite-sample empirical tail remains:

`p_emp = (1 + #{control_score >= observed_score}) / (1 + N_control)`.

`NullModelReceiptV1` binds the ordered generated subject digests, ordered control collision-receipt digests, ordered control coverage-receipt digests, control-score digest, empirical statistic, and promotion verdict. `verify_null_model_receipt(...)` checks its digest, cardinalities, finite-sample p-value identity, coverage-lineage shape, and promotion-shape invariants.

A threshold-free **prospective** null evaluation still requires complete coverage, even though it produces no survival verdict. A retrospective descriptive evaluation remains non-promoting and may omit promotion-grade coverage.

## Status authority

Collision status uses the generic hash-chained `StatusJournalV1` foundation:

`OBSERVED -> EXACT_MAPPING -> CROSS_REGISTRY_COLLISION -> NULL_SURVIVED -> REPLICATED`.

`NULL_SURVIVED` requires a hash-valid null receipt that is promotion-eligible and surviving, names the exact current collision receipt, contains promotion-grade coverage lineage for every control, and is itself carried in the transition evidence. Coverage-lineage field tampering invalidates the null receipt before status promotion.

`STRUCTURAL_RELATION` is not a statistical state and cannot be minted by this subsystem. The generic journal separately supports explicit demotion while retaining prior evidence and transition hashes.

## Frozen 65010 fixture

`.aegis/cross-domain/fixtures/65010-v1.json` remains a retrospective regression fixture, not a significance claim.

It freezes two independent external records observed on 2026-08-25:

1. Unicode 16.0.0: integer `65010` has hexadecimal representation `FDF2`; its deterministic code-point label is `U+FDF2`; the frozen record names U+FDF2 `ARABIC LIGATURE ALLAH ISOLATED FORM`.
2. NCBI Gene: identifier `65010` resolves in the frozen record to the human protein-coding gene symbol `SLC26A6`.

The bundle also freezes exact local factorisation data as `DERIVED_PROPERTY`; that arithmetic evidence is not a third external registry.

Its V1 ceiling remains `CROSS_REGISTRY_COLLISION`. The control-coverage implementation does not retroactively make the known seed prospective.

No fixture receipt claims causation, biological linkage, theorem-level equivalence, hidden semantics, non-randomness, RH, or AGI.

## Synthetic coverage versus real registry coverage

The new local fixture adapters establish that the authority machinery can distinguish and replay `MATCH`, explicit `NO_MATCH`, and `NOT_ESTABLISHED`; derive complete coverage; derive a control score from the same probe set; bind coverage into the null receipt; and block incomplete, reordered, or spliced evidence.

That is an implementation/evidence result about the **control-plane semantics**.

It does not establish that Unicode, NCBI, or any other real registry exposes promotion-grade exact-negative semantics suitable for a future experiment. Each real registry requires its own frozen adapter contract, authoritative source snapshot format, positive predicate, exact negative predicate, ambiguity/error classification, and canonicalization rule before it may contribute to prospective scientific promotion.

Therefore:

`synthetic fixture coverage semantics` ≠ `real Unicode/NCBI prospective coverage`.

## Fail-closed conditions

Promotion is blocked by missing snapshots/evidence, unsupported schemas or adapter rules, subject/query-key mismatch, stale subject digest, unknown transform, external domain absent from the frozen criterion, duplicate-domain inflation, raw caller-supplied null scores, missing coverage, duplicate/extra registry probes, `NOT_ESTABLISHED` controls, control subject/criterion/provenance mismatch, reordered coverage, collision/coverage score splicing, malformed or tampered receipts, null/collision splicing, retrospective-to-prospective relabeling, missing null receipt or null digest at `NULL_SURVIVED`, or any attempt to mint `STRUCTURAL_RELATION` from collision statistics.

Absence of observations is never documented as proof of an external negative lookup.

## CI boundary

The authoritative Cross-Domain GitHub Actions workflow is offline. It runs collision-core regressions, control-coverage regressions, injected-transport ingestion tests, frozen 65010 replay, adversarial immutability/lineage/anti-splicing tests, and inherited research-gate regressions. It performs no live Unicode or NCBI lookup.

A green ancestor is not evidence for a descendant. Exact-head claims require terminal checks on the exact final commit SHA.

## Explicit epistemic state

The implementation is designed to support these bounded statements when exact-head CI is green:

- `65010 -> FDF2 -> U+FDF2` representation/code-point-label transform = deterministic fact;
- frozen Unicode and NCBI claims = snapshot-bound external evidence;
- frozen 65010 two-domain collision = replay-established retrospective collision;
- proof-carrying **synthetic fixture** control-coverage semantics = implementation-verifiable;
- prospective statistical significance for 65010 = **NOT_ESTABLISHED**;
- real Unicode/NCBI promotion-grade control coverage = **NOT_ESTABLISHED**;
- non-random cross-domain mechanism = **NOT_ESTABLISHED**;
- structural or causal cross-domain relation = **NOT_ESTABLISHED**.

## Explicit non-claims

V1 does not establish that cross-domain collisions are meaningful, causal, biologically coupled, mathematically necessary, or evidence for RH/AGI/metaphysical hypotheses. It establishes exact mappings, frozen provenance, deterministic offline replay, collision classification, proof-carrying synthetic control-coverage authority semantics, and explicit evidence obligations for future preregistered real-registry experiments.
