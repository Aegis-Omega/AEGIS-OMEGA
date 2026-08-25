# Prospective Cross-Domain Epoch V1 — Design

Status: APPROVED ARCHITECTURE / IMPLEMENTATION SPEC  
Date: 2026-08-25  
Parent: `research/cross-domain-collision-v1@07d128889305ae39966e363d8aa7bc4578a5569e` (#324)  
Authority: research evidence only  

## 1. Objective

Build the first real preregistered prospective experiment on top of the established Cross-Domain Collision V1 + ControlCoverageV1 authority line.

Epoch V1 freezes exactly two external domains before the first subject is generated:

1. Unicode Character Database;
2. NCBI Gene.

The epoch must produce replayable evidence for every generated integer subject without allowing live network availability, post-hoc transform changes, missing registry checks, duplicate-control ambiguity, or source parser discretion to become statistical authority.

The authoritative path is:

`ProspectiveEpochV1 -> SubjectGenerationReceiptV1 -> source capture artifacts -> source-specific offline adapters -> RegistryProbeReceiptV1 x2 -> VerifiedControlCoverageV1 -> CollisionReceiptV1 -> ProspectiveEpochSummaryReceiptV1`

A later null-model receipt may consume these collision/coverage receipts, but Epoch V1 does not automatically equate a prospective collision with statistical significance or structural mechanism.

## 2. Governing epistemic boundary

No prospective claim may receive greater authority than the weakest verified transition in its lineage.

Live I/O is evidence acquisition only. It may capture source bytes and transport metadata. It may not classify a registry outcome, mint a collision receipt, compute promotion status, or rewrite an already frozen epoch.

Offline replay is authoritative. Every source-specific classification must be reproducible from immutable captured bytes plus a frozen adapter contract.

The following are distinct states:

- `MATCH`: source-specific exact positive semantics established;
- `NO_MATCH`: source-specific exact negative semantics established;
- `NOT_ESTABLISHED`: transport, parser, schema, provenance, or source semantics are insufficient to establish either result.

`NOT_ESTABLISHED` is never silently converted to `NO_MATCH`.

## 3. Epoch freeze contract

`ProspectiveEpochV1` is immutable and hash-bound before subject generation.

It binds at minimum:

```text
ProspectiveEpochV1 {
  epoch_id
  parent_collision_schema_id
  universe_min
  universe_max
  registry_ids
  registry_adapter_contract_sha256s
  source_contract_sha256s
  score_function_id
  independence_rule_id
  generator_id
  generator_version
  seed
  subject_count
  duplicate_policy_id
  coverage_policy_id
  optional_promotion_threshold
  freeze_reason
  epoch_sha256
}
```

Epoch 1 freezes:

- `registry_ids = ("unicode", "ncbi-gene")`;
- `score_function_id = UNIQUE_EXTERNAL_DOMAINS_V1`;
- `independence_rule_id = UNIQUE_DOMAIN_ID_V1`;
- integer universe `[0, 100000]`;
- `generator_id = PY_RANDOM_UNIFORM_INT_V1`;
- deterministic local `random.Random(seed)` behavior inherited from Cross-Domain Collision V1;
- `subject_count = 1000` for the first operational epoch;
- `duplicate_policy_id = POSITIONAL_DRAWS_WITH_REPLACEMENT_V1`;
- `coverage_policy_id = REQUIRE_ALL_FROZEN_REGISTRIES_V1`.

The exact seed is part of the epoch hash and must be generated/frozen before any subject generation or source lookup. The implementation must not use wall-clock time as implicit seed authority.

Any change to universe, registries, adapter semantics, source semantics, score, generator, seed, subject count, duplicate policy, coverage policy, or threshold creates a new epoch. Existing receipts remain historical evidence and are never retroactively rebound.

## 4. Subject generation lineage

`SubjectGenerationReceiptV1` proves that a subject occupies a specific position in the deterministic frozen sequence.

```text
SubjectGenerationReceiptV1 {
  epoch_sha256
  draw_index
  value
  subject_sha256
  generated_sequence_sha256
  generator_id
  generator_version
  receipt_sha256
}
```

Verification regenerates the entire frozen sequence from the epoch and checks:

1. `0 <= draw_index < subject_count`;
2. `value` equals the deterministic value at that position;
3. `subject_sha256` equals `IntegerSubjectV1(value).subject_sha256`;
4. `generated_sequence_sha256` equals the digest of the full ordered integer sequence;
5. generator id/version equal the frozen epoch;
6. receipt digest is valid.

Duplicate integer values are allowed because the generator samples with replacement. They remain distinct draws by `draw_index` while sharing the same canonical integer subject digest. No deduplication may change the denominator after generation.

## 5. Source capture boundary

Live capture produces immutable source artifacts and no registry verdict.

`SourceCaptureArtifactV1` binds:

```text
SourceCaptureArtifactV1 {
  source_id
  source_contract_sha256
  request_identity
  request_subject_sha256s
  source_version_or_release
  response_status
  response_headers_subset
  raw_content_sha256
  raw_content
  observed_at
  producer_id
  capture_sha256
}
```

`raw_content` is bytes at the capture boundary. Hashing occurs before parsing. The semantic digest covers the source contract, request identity, requested subject lineage, response status, selected stable response metadata, raw bytes digest, observation timestamp supplied by capture, and producer id.

The adapter never trusts a mutable parsed Python object as source authority when the original captured bytes are available.

Transport timeout, DNS failure, HTTP failure, truncated bytes, unsupported content encoding, or schema drift produces a failure artifact / `NOT_ESTABLISHED` lineage. A failed capture is not rewritten in place after retry. A retry produces a new immutable attempt linked to the same epoch/request identity.

## 6. Unicode source contract

Epoch 1 freezes Unicode Standard Version 17.0.0 and an official versioned Unicode Character Database data source.

The preferred promotion-grade source is the versioned Unicode 17.0.0 extracted general-category data (`DerivedGeneralCategory.txt`) because General_Category is defined for every Unicode code point and `Cn` represents the unassigned category under the frozen Unicode data semantics.

`UnicodeSourceContractV1` binds:

- Unicode release `17.0.0`;
- exact versioned source locator, never a `latest` alias;
- expected text encoding;
- file-format/parser version;
- allowed comment/blank-line grammar;
- inclusive range grammar (`XXXX` or `XXXX..YYYY ; GC`);
- positive rule id `UNICODE_GENERAL_CATEGORY_NOT_CN_V1`;
- negative rule id `UNICODE_GENERAL_CATEGORY_CN_V1`;
- out-of-domain rule id `UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1`;
- contract digest.

Because Epoch 1's universe is `[0,100000]`, every generated integer is inside the Unicode code-point range and therefore no operational Epoch 1 draw should be out of domain. The parser still fails closed on out-of-range subjects.

Offline Unicode probe semantics:

- `MATCH` iff the frozen UCD source establishes `General_Category != Cn` for the exact code point;
- `NO_MATCH` iff the frozen UCD source establishes `General_Category == Cn` for the exact code point;
- `NOT_ESTABLISHED` for malformed source, incomplete range coverage, overlapping contradictory ranges, unsupported category token, source-version mismatch, or any unprovable lookup state.

The verifier must prove exactly one general-category range covers each in-domain queried code point. Absence of a parsed line is not itself negative evidence.

Character names, glyphs, decomposition, script, religious/semantic interpretation, or other Unicode properties do not affect Epoch 1 collision score.

## 7. NCBI Gene source contract

Epoch 1 freezes NCBI Entrez Gene ESummary as the external record source.

NCBI documentation defines ESummary as returning document summaries for a supplied list of UIDs. Epoch 1 uses `db=gene`, `retmode=json`, explicit tool identification, and deterministic batching of generated Gene IDs.

`NCBIGeneSourceContractV1` binds:

- source id `ncbi-gene-esummary`;
- database `gene`;
- endpoint family `esummary.fcgi`;
- response mode `json`;
- adapter/parser version;
- deterministic batch size (maximum 100 IDs per request for Epoch 1);
- canonical sorted/positional request construction rule;
- positive rule id `NCBI_ESUMMARY_UID_PRESENT_V1`;
- negative rule id `NCBI_ESUMMARY_UID_ABSENT_FROM_VALID_RESULT_V1`;
- ambiguous/error rule id `NCBI_ESUMMARY_NOT_ESTABLISHED_V1`;
- contract digest.

NCBI live capture must obey documented E-utilities identification/rate guidance. `tool` and `email` are runtime acquisition metadata and must not silently alter semantic classification. API keys, if used, are secrets and are never written into evidence artifacts.

Offline NCBI probe semantics for a requested integer `x`:

- `MATCH` iff a structurally valid ESummary JSON response for the exact frozen request batch contains decimal UID `x` in `result.uids` and contains a corresponding record whose `uid` canonically equals `x`;
- `NO_MATCH` iff the exact requested UID is absent from `result.uids` in a structurally valid, successfully captured ESummary result for the batch, no response-level ambiguity/error applies to that request, and the adapter can prove the response belongs to the exact batch containing `x`;
- `NOT_ESTABLISHED` for transport failure, non-success response, invalid JSON, missing `result`, malformed `uids`, contradictory UID/record fields, response-level error/warning state whose semantics are not frozen as exact negative, batch/request mismatch, or schema drift.

Generic HTTP `404`, empty bytes, parser exceptions, timeouts, rate limits, and missing capture artifacts are never `NO_MATCH`.

## 8. Adapter contracts and verified probes

Epoch 1 must use source-specific adapter contracts rather than the generic fixture-only `MATCH_BOOL_*` rules currently used by ControlCoverageV1 tests.

The implementation may extend `RegistryAdapterContractV1` rule registries with exactly the Unicode and NCBI rule ids required above. Unknown rule ids continue to fail closed.

A promotion-grade probe bundle must carry enough material for offline re-verification:

```text
VerifiedRegistryProbeV1 {
  subject
  criterion/epoch binding
  adapter contract
  source contract
  source capture artifact
  probe receipt
}
```

The verifier recomputes subject-to-query relation, source-artifact digest, source parser result, adapter verdict, and probe receipt. A hash-valid probe receipt without replayable source material is not promotion-grade.

## 9. Coverage construction

For each generated draw, coverage requires exactly one established probe for each frozen registry:

`("unicode", "ncbi-gene")`.

`ControlCoverageReceiptV1` remains the authority carrier for per-subject completeness.

Coverage is complete iff:

1. both required registries occur exactly once;
2. both probes are replay-valid under the epoch's exact adapter/source contracts;
3. each probe is `MATCH` or `NO_MATCH`;
4. neither probe is `NOT_ESTABLISHED`;
5. subject, epoch/criterion, transform, adapter, source release, and request lineage all match;
6. no extra registry is injected.

A subject with incomplete coverage remains in the epoch denominator as an incomplete draw. It may not be silently discarded, replaced, resampled, or treated as score zero.

## 10. Collision score

Epoch 1 uses only the existing simple external-domain score:

`S(x) = I[Unicode MATCH] + I[NCBI Gene MATCH]`, so `S(x) in {0,1,2}`.

A cross-registry collision is exactly `S(x) == 2` under the frozen Epoch 1 contracts.

No semantic weighting is permitted. Unicode names, Gene symbols, biological function, linguistic resemblance, visual resemblance, arithmetic properties, or human judgments of interestingness do not affect the Epoch 1 score.

A local deterministic arithmetic derivation may still exist as contextual evidence but is not one of the two Epoch 1 external registries and contributes zero to this score.

## 11. Epoch summary receipt

Epoch V1 adds an immutable summary over all generated draw positions.

```text
ProspectiveEpochSummaryReceiptV1 {
  epoch_sha256
  generated_count
  fully_covered_count
  incomplete_count
  match_histogram
  score_histogram
  collision_draw_indices
  collision_subject_sha256s
  generation_receipt_sha256s
  coverage_receipt_sha256s_or_null
  collision_receipt_sha256s_or_null
  summary_sha256
}
```

Rules:

- `generated_count` must equal frozen `subject_count`;
- every draw position appears exactly once;
- incomplete positions remain explicit and preserve generation lineage;
- no incomplete draw contributes to a score histogram cell;
- `fully_covered_count + incomplete_count == generated_count`;
- score histogram counts only fully covered draws and sums to `fully_covered_count`;
- collision positions are exactly the fully covered draws with score `2`;
- duplicate subject values remain separate positions if generated more than once;
- all digest vectors are positionally aligned with the frozen generated sequence.

The primary descriptive empirical quantity is:

`collision_rate_covered = collision_count / fully_covered_count`

and must always be reported alongside `generated_count`, `fully_covered_count`, and `incomplete_count`.

The summary receipt is descriptive evidence. It does not by itself mint `NULL_SURVIVED`, `REPLICATED`, or `STRUCTURAL_RELATION`.

## 12. Coverage policy and epoch completion

Epoch 1's frozen policy is `REQUIRE_ALL_FROZEN_REGISTRIES_V1`.

A run is `COMPLETE` only when every generated draw has complete Unicode + NCBI coverage:

`fully_covered_count == generated_count == 1000`.

If even one draw remains `NOT_ESTABLISHED`, the epoch may emit an auditable partial summary but the operational epoch status is `INCOMPLETE`. It must not silently shrink the denominator to covered draws and call the run complete.

Retries are permitted only as additional source-capture attempts for the same frozen request lineage. They do not change subject generation, epoch digest, registry set, or denominator.

## 13. Prospective significance boundary

Epoch 1 establishes genuine prospective selection provenance because the epoch is frozen before generation and every generated draw is retained.

However, detecting one or more prospective collisions is not automatically a significance claim. Selecting the most interesting hit after seeing the cohort and then treating the remaining cohort as an uncorrected null would introduce post-selection bias.

Therefore Epoch 1 completion establishes:

- exact prospective generation lineage;
- exact Unicode + NCBI coverage when complete;
- exact prospective collision count/rate under frozen contracts.

It does not automatically establish:

- per-hit `NULL_SURVIVED`;
- family-wise or FDR-corrected anomaly significance;
- non-random mechanism;
- structural/causal relation.

A later preregistered statistical epoch may define a rate-level null model or corrected per-hit testing contract and consume Epoch 1 artifacts without rewriting them.

## 14. 65010 boundary

`65010` remains the canonical retrospective regression fixture from Cross-Domain Collision V1.

It is not injected, forced, seeded, or guaranteed to appear in Epoch 1. If the frozen generator naturally produces `65010`, that draw is prospectively generated and must be treated as an ordinary draw position under Epoch 1. Its earlier retrospective history remains separate evidence lineage and cannot be used to upgrade the prospective draw.

The implementation must never special-case the value `65010` in epoch generation, live capture, adapter classification, score, retry, or summary logic.

## 15. Storage and replay

Live network capture artifacts are evidence inputs, not generated source code.

Preferred repository/runtime split:

- code/spec/tests contain schemas, deterministic parsers, adapter contracts, small fixtures, and artifact manifests;
- large raw capture bodies are content-addressed artifacts outside normal source history when practical;
- manifests bind artifact SHA-256, source contract, request identity, generation positions, and retrieval metadata;
- offline verification receives exact bytes by digest and does not refetch network sources.

For tests, small frozen fixture bytes are committed locally so CI is network-free.

No authoritative CI job performs live Unicode or NCBI requests.

## 16. Components / files

Preferred isolated implementation surfaces:

- new `sovereign-omega-v2/python/cross_domain_epoch.py`
  - epoch freeze type;
  - subject generation receipts;
  - epoch summary receipt;
  - completion verification.
- new `sovereign-omega-v2/python/cross_domain_registry_adapters.py`
  - Unicode 17.0.0 source contract + parser;
  - NCBI Gene ESummary source contract + parser;
  - source-specific probe replay.
- `sovereign-omega-v2/python/cross_domain_ingest.py`
  - generic immutable raw capture artifact;
  - deterministic retry-attempt lineage;
  - no verdict authority.
- `sovereign-omega-v2/python/cross_domain_coverage.py`
  - register the two source-specific adapter rule ids;
  - accept replay-verified source bundles;
  - no network code.
- new tests:
  - `test_cross_domain_epoch.py`;
  - `test_cross_domain_registry_adapters.py`;
  - additional adversarial coverage/hardening cases.
- small fixture artifacts under `.aegis/cross-domain/fixtures/prospective-epoch-v1/`.
- existing `.github/workflows/cross-domain-collision.yml` extended to compile/run the new offline modules/tests.

No unrelated refactor is authorized.

## 17. Required adversarial tests

At minimum, RED-first implementation must prove:

1. epoch digest changes if any frozen field changes;
2. generation before/after replay yields identical ordered sequence and sequence digest;
3. a subject not at its claimed draw index is rejected;
4. duplicate generated values remain distinct positional draws without denominator loss;
5. generation receipt from another epoch cannot splice;
6. Unicode parser establishes exactly one General_Category for each queried in-range code point;
7. Unicode `Cn` becomes exact `NO_MATCH` and non-`Cn` becomes `MATCH`;
8. malformed/overlapping/incomplete Unicode fixture data yields `NOT_ESTABLISHED` / verification failure, never negative evidence;
9. NCBI valid result with exact UID + matching record yields `MATCH`;
10. NCBI exact requested UID absent from a structurally valid exact-batch result yields `NO_MATCH` only under the frozen adapter rule;
11. NCBI HTTP/transport/parser/schema/error states yield `NOT_ESTABLISHED`;
12. NCBI batch response cannot splice to a subject absent from the captured request identity;
13. raw source bytes tampering invalidates capture and all downstream probe lineage;
14. wrong Unicode release or NCBI source contract fails closed;
15. one missing registry leaves draw incomplete;
16. one `NOT_ESTABLISHED` registry leaves draw incomplete;
17. incomplete draw is retained in generated denominator and excluded from score histogram;
18. epoch cannot be marked COMPLETE with `fully_covered_count < generated_count`;
19. complete two-registry `NO_MATCH/NO_MATCH` draw yields score 0;
20. complete `MATCH/NO_MATCH` draw yields score 1;
21. complete `MATCH/MATCH` draw yields score 2 and collision;
22. post-hoc semantic fields cannot alter score;
23. summary vectors cannot be reordered or spliced across epochs;
24. summary collision indices must equal exact score-2 positions;
25. `65010` has no special-case code path;
26. live ingestion remains outside authoritative CI.

## 18. Completion boundary

The implementation may be called `ProspectiveEpochV1 authority semantics = ESTABLISHED` only when the final exact PR head has terminal GREEN evidence for:

- Cross-Domain Collision V1 offline workflow including all epoch/adapter tests;
- inherited Zero-Discretion Type Gates;
- Kernel One;
- repository cognition / exact-head repository-native checks where applicable.

That statement means the machinery for preregistration, generation lineage, source capture, offline registry classification, proof-carrying coverage, collision scoring, and epoch summary is verified.

It does not mean that a real 1000-draw live Epoch 1 acquisition has completed. Live acquisition and its resulting artifact manifest have their own exact evidence state.

Until a real live run has complete captured artifacts and 1000/1000 verified registry coverage:

- real Epoch 1 execution = `NOT_ESTABLISHED` / not yet complete;
- prospective collision rate = `NOT_ESTABLISHED`;
- prospective statistical significance = `NOT_ESTABLISHED`;
- non-random mechanism = `NOT_ESTABLISHED`;
- structural/causal relation = `NOT_ESTABLISHED`.
