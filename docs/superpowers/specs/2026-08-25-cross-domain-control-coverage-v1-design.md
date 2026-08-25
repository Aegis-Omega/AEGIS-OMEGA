# Cross-Domain Control Coverage V1 — Design

Status: APPROVED ARCHITECTURE / PRE-IMPLEMENTATION SPEC  
Date: 2026-08-25  
Parent: Cross-Domain Collision V1 (#324)  
Authority: research evidence only  

## 1. Problem

Cross-Domain Collision V1 can bind an observed collision to deterministic control subjects and collision receipts, but a control receipt with score `0` does not by itself prove that every frozen external registry was actually queried for that control subject.

An empty observation set is therefore ambiguous:

- all registries were checked and produced exact `NO_MATCH` outcomes;
- some registries were not checked;
- a lookup failed or timed out;
- evidence was never produced.

Treating all four cases as the same score-0 control would be epistemically fail-open. Absence of an observation is not evidence of absence.

## 2. Goal

Add proof-carrying registry coverage to prospective control evaluation so that statistical promotion can occur only when every required `(control subject, frozen registry)` pair is backed by a verifiable probe receipt.

The authoritative path becomes:

`subject -> registry probe receipts -> complete control coverage receipt -> collision receipt -> null-model receipt -> NULL_SURVIVED`

The subsystem must preserve the existing separation between evidence, statistical classification, and structural/causal claims.

## 3. Non-goals

V1 does not establish that any observed cross-domain collision is meaningful, causal, biologically coupled, mathematically necessary, or evidence for RH, AGI, or metaphysical hypotheses.

V1 does not permit live network calls inside authoritative admission CI. Live connectors remain evidence producers only.

V1 does not infer `NO_MATCH` from timeout, HTTP error, parser error, missing evidence, stale evidence, unsupported schema, or unqueried registry state.

## 4. Core Types

### 4.1 `RegistryProbeOutcomeV1`

Closed enum:

- `MATCH`
- `NO_MATCH`
- `NOT_ESTABLISHED`

`NOT_ESTABLISHED` covers transport failure, malformed source data, incomplete source semantics, unsupported source state, or any condition where an exact positive or negative lookup result cannot be established.

There is intentionally no boolean `matched` field without the typed outcome.

### 4.2 `RegistryAdapterContractV1`

Every promotion-grade registry requires a frozen adapter contract. The contract binds the semantics needed to classify a source artifact without discretionary interpretation:

- `registry_id`
- `adapter_version`
- `query_key_type`
- `transform_id`
- `transform_criterion_sha256`
- `positive_result_rule_id`
- `negative_result_rule_id`
- `ambiguous_result_rule_id`
- `canonicalization_rule_id`
- `contract_text`
- `contract_sha256`

The contract digest covers every field. Unknown rule ids fail closed. V1 implementations may support only the concrete rule ids needed by the frozen test adapters; unsupported adapters remain `NOT_ESTABLISHED`.

A registry that cannot define trustworthy exact-negative semantics is not promotion-grade in V1.

### 4.3 `RegistryProbeReceiptV1`

A receipt binds exactly one `(subject, registry, criterion epoch, adapter epoch)` probe:

- `subject_sha256`
- `registry_id`
- `query_key`
- `query_key_type`
- `transform_id`
- `transform_criterion_sha256`
- `registry_version_or_release`
- `adapter_contract_sha256`
- `source_evidence_sha256`
- `outcome: RegistryProbeOutcomeV1`
- `criterion_sha256`
- `receipt_sha256`

Rules:

1. `MATCH` requires an admissible immutable external source artifact and a verified subject-to-query-key relation.
2. `NO_MATCH` requires an immutable source artifact whose exact-negative semantics are established by the frozen adapter contract. Missing data is insufficient.
3. `NOT_ESTABLISHED` may bind a failure/ambiguous evidence artifact but cannot contribute to complete coverage.
4. `source_evidence_sha256` is mandatory for every outcome; absence of evidence cannot mint a probe receipt.
5. The receipt digest covers every semantic field.
6. Unknown outcome values fail closed.
7. Nested/hash material is defensively frozen before hashing.

### 4.4 `ControlCoverageReceiptV1`

A coverage receipt binds one control subject to the complete frozen external registry set:

- `subject_sha256`
- `criterion_sha256`
- `required_registry_ids`
- `probe_receipt_sha256s`
- `covered_registry_ids`
- `missing_registry_ids`
- `unestablished_registry_ids`
- `coverage_complete`
- `receipt_sha256`

`coverage_complete=True` is derived, never caller-supplied authority.

Canonical ordering is deterministic: `required_registry_ids` equals the frozen `criterion.registry_set` tuple; probe-derived registry and digest sequences are ordered by that required registry order, not by caller input order.

Coverage is complete iff:

1. every registry in `criterion.registry_set` appears exactly once;
2. no extra registry appears;
3. every probe receipt has the same subject and criterion digest;
4. every probe receipt is hash-valid;
5. every probe outcome is either `MATCH` or `NO_MATCH`;
6. every probe binds a supported frozen adapter contract for that registry;
7. there are no missing or `NOT_ESTABLISHED` registries.

Duplicate registry probes fail closed rather than being silently deduplicated.

## 5. Collision Construction From Probe Evidence

Prospective control collision receipts must be constructible only from verified probe receipts plus the frozen criterion.

For each `MATCH` probe, the evaluator mints the corresponding external `DomainObservationV1` from the verified source relation. `NO_MATCH` contributes coverage but no collision observation. `NOT_ESTABLISHED` contributes neither collision evidence nor complete coverage.

`evaluate_control_from_probes(...)` returns both:

- `CollisionReceiptV1`
- `ControlCoverageReceiptV1`

The same verified probe set therefore determines both the control score and the evidence that the score was computed over the full required registry set.

The implementation must not accept a caller-provided score or caller-provided `coverage_complete` boolean.

## 6. Null-Model Promotion Gate

`evaluate_null_model(...)` remains responsible for the empirical finite-sample statistic, but promotion eligibility is strengthened.

For every generated control subject, the evaluator must receive:

- a hash-valid `CollisionReceiptV1`;
- a hash-valid `ControlCoverageReceiptV1`;
- matching subject digest;
- matching criterion digest;
- complete registry coverage.

The control collision receipt and coverage receipt must refer to the same exact generated control subject at the same sequence position. Reordering or splicing controls fails closed.

`NullModelReceiptV1` is extended to bind `control_coverage_receipt_sha256s` in the exact generated-control order, alongside the already bound control subject/collision receipt lineage.

Promotion fails closed if any control lacks complete coverage.

The empirical statistic remains:

`p_emp = (1 + #{control_score >= observed_score}) / (1 + N_control)`

but `p_emp` is only a statistic over established controls. A computed p-value from incomplete controls must not yield `promotion_eligible=True` or `null_survived=True`.

For retrospective observations, existing behavior remains unchanged: descriptive null evaluation may be emitted only with explicit opt-in, and it is never promotion-eligible.

## 7. Status Authority

`NULL_SURVIVED` requires all of the following:

1. hash-valid `NullModelReceiptV1`;
2. exact collision lineage binding;
3. exact criterion binding;
4. exact null-receipt digest carried in status-transition evidence;
5. `promotion_eligible=True`;
6. `null_survived=True`;
7. exact `control_coverage_receipt_sha256s` lineage bound into the null receipt;
8. proof that every control receipt consumed by the null model has the corresponding complete `ControlCoverageReceiptV1`.

`STRUCTURAL_RELATION` remains unreachable from this subsystem.

## 8. Ingestion Boundary

Live ingestion remains non-authoritative.

The ingestion layer may produce immutable source evidence artifacts/snapshots, but the offline verifier decides whether that evidence establishes `MATCH`, `NO_MATCH`, or `NOT_ESTABLISHED` under a frozen registry adapter contract.

A network or parser failure must produce evidence classified as `NOT_ESTABLISHED`, never `NO_MATCH`.

The authoritative CI path must remain network-free.

## 9. Registry Adapter Semantics

A registry adapter contract defines what constitutes exact positive, exact negative, and ambiguous results. This is registry-specific and frozen before prospective use.

For the first vertical slice, promotion-grade behavior may be proven with deterministic local fixture adapters rather than live Unicode/NCBI controls. This isolates the authority semantics from network availability. Real registries become promotion-grade only after their exact-negative contracts and frozen source evidence are separately established.

No generic "404 means no match" rule is permitted.

## 10. 65010 Boundary

The existing `65010` fixture remains permanently retrospective.

Its exact Unicode and NCBI mappings continue to establish a retrospective `CROSS_REGISTRY_COLLISION` under the frozen criterion. This design does not retroactively make `65010` statistically prospective.

The known seed may be used for deterministic regression mechanics, but prospective significance remains `NOT_ESTABLISHED` until a future preregistered experiment has complete proof-carrying control coverage.

## 11. Failure Conditions

The verifier must fail closed on:

- missing required registry probe;
- duplicate registry probe;
- extra registry not in the frozen criterion;
- subject mismatch;
- criterion mismatch;
- transform mismatch;
- adapter-contract mismatch;
- unsupported adapter rule;
- tampered probe receipt digest;
- tampered coverage receipt digest;
- caller-supplied raw score;
- caller-supplied `coverage_complete` authority;
- `NOT_ESTABLISHED` treated as `NO_MATCH`;
- missing source evidence for any probe outcome;
- missing explicit negative semantics/evidence for `NO_MATCH`;
- incomplete coverage passed into null promotion;
- coverage receipt spliced from a different control subject;
- coverage receipt spliced from a different criterion epoch;
- reordered collision/coverage lineage relative to generated controls;
- null receipt that omits the exact coverage receipt lineage.

## 12. TDD / Verification Strategy

Implementation must be RED-first.

Required adversarial tests include:

1. empty observations cannot establish complete coverage;
2. one missing registry blocks promotion;
3. one `NOT_ESTABLISHED` registry blocks promotion;
4. duplicate registry probes fail closed;
5. cross-subject coverage splicing fails;
6. cross-criterion coverage splicing fails;
7. tampered probe digest fails;
8. tampered coverage digest fails;
9. `NO_MATCH` without explicit negative evidence/adapter semantics fails;
10. `MATCH` without a verified source relation fails;
11. unsupported adapter rules fail closed;
12. complete `MATCH/NO_MATCH` coverage permits a valid zero-score control;
13. caller order cannot alter canonical coverage digest;
14. complete coverage for every generated control permits null evaluation;
15. reordered control coverage lineage fails;
16. positive `NULL_SURVIVED` path preserves exact collision + coverage + null lineage;
17. retrospective fixtures remain unable to promote.

The hosted exact-head checks must include Cross-Domain Collision V1, Zero-Discretion Type Gates, Kernel One, repository cognition, and any repository-native checks triggered by the changed paths.

## 13. Files / Isolation

Preferred implementation keeps responsibilities small:

- `cross_domain_collision.py`: collision/statistical receipts and status authority;
- new `cross_domain_coverage.py`: adapter contracts, probe receipts, coverage aggregation, control evaluation;
- `cross_domain_ingest.py`: live evidence production only;
- dedicated `test_cross_domain_coverage.py` plus adversarial lineage tests;
- existing cross-domain workflow extended to run coverage regressions offline.

No unrelated refactor is authorized.

## 14. Completion Boundary

The implementation may be called `ControlCoverageV1 = ESTABLISHED` only when the final exact PR head has terminal GREEN evidence for the authoritative offline coverage regressions and inherited gates.

Even then:

- prospective significance for `65010` = `NOT_ESTABLISHED`;
- non-random cross-domain mechanism = `NOT_ESTABLISHED`;
- structural/causal relation = `NOT_ESTABLISHED`.
