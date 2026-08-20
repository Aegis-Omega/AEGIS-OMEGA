# UCI-6 Collective Memory Admission — Lineage Ledger

Date context: 2026-08-20

## Frozen stacked parent

```text
UCI5_PARENT = c47e99b8139a280c39ceacc46db738b2617866d5
PR = #278
BRANCH = feat/uci-6-collective-memory-admission-v1
```

UCI-6 is downstream of the UCI-5 local atomic-admission reference. It does not alter the UCI-4 effect-verification semantics and does not convert memory, retrieval, provider output, or observation into authority.

## Contract

```text
arbitrary evidence -> QUARANTINED_EVIDENCE_MEMORY_RECORD_V1
quarantine authority -> EVIDENCE_ONLY / weight 0
canonical projection -> requires persisted UCI-5 admission + exact action-root binding
canonical memory authority -> EVIDENCE_ONLY / weight 0
revocation/supersession -> append-only admitted control event
memory request -> binds expected memory sequence + prior event root
memory mutation -> rechecks that pre-state inside BEGIN IMMEDIATE
prestate-less internal base direct construction -> FORBIDDEN_AND_TESTED
self-promotion -> FORBIDDEN
canonical truth claim -> FORBIDDEN
```

The persisted UCI-5 admission record is re-read from the trusted reference admission store. A caller-constructed `AdmissionRecordV1` object is not sufficient evidence that the transition was admitted.

## TDD lineage

### RED 1 — missing module

```text
CANDIDATE = 78fd533f9613ba24a34c48cf5ea0af24a87a2119
WITNESS_REPO = tarikskalic33/info
RUN_ID = 32350977651
RESULT = intended ModuleNotFoundError for harness.sdk.collective_memory
EXACT_LINEAGE = PASS
```

No production collective-memory module existed at this candidate.

### GREEN 1 — first admitted-memory implementation

```text
CANDIDATE = 5457427e9439d7b4c188009bdbb67f7cab2dadd9
RUN_ID = 32351627421
RESULT = 20/20 PASS
EXACT_LINEAGE = PASS
```

This established the first focused local reference behavior only.

### RED 2 — memory pre-state binding gap

Adversarial review found that an admitted memory action did not commit the memory event sequence/root that existed before admission. Two regression tests were added before the patch.

```text
TEST_ONLY_CANDIDATE = 9007edc0be602ec6f6021a8f94d32091b5fb5f23
RUN_ID = 32351827802
RESULT = 20 PASS / 2 FAIL
EXACT_LINEAGE = PASS
```

Both failures were the intended missing `expected_memory_sequence` / `expected_memory_event_root` request fields.

### Intermediate candidate — correct invariant, wrong replay precedence

```text
CANDIDATE = 70343f4c19c9473ba5be86065c53b9ef8ba561d2
RESULT = 20/22 PASS
```

The new pre-state check worked, but exact replay and the losing concurrent contender were classified as `MEMORY_PRESTATE_MISMATCH` instead of their stable replay class. This candidate was not promoted to GREEN.

### GREEN 2 — pre-state + replay precedence

```text
CANDIDATE = f2821a7e31ffd9e16422a2b4766e5152de148264
WITNESS_RUN = 32372114665
WITNESS_JOB = 96434852515
EXACT_LINEAGE = PASS
RESULT = 22/22 PASS
```

Inside the memory transaction, exact duplicate/admitted-binding replay classification now precedes the stale pre-state check. New unseen actions still fail closed on a stale `{sequence,last_event_root}` pair.

### RED 3 — closed serialization surface missing

Five nominal serialized memory types were preregistered before their JSON Schemas existed.

```text
TEST_ONLY_CANDIDATE = 1514efc37652139b8baf1207ec4bd0c0c49b7dea
WITNESS_RUN = 32372433188
WITNESS_JOB = 96435856984
EXACT_LINEAGE = PASS
BEHAVIORAL_BASELINE = 22/22 PASS
SCHEMA_TEST = 2 FAIL
INTENDED_FAILURE = FileNotFoundError for preregistered UCI-6 schema paths
```

The RED therefore did not hide a behavioral regression.

### GREEN 3 — closed serialization surface

Five Draft 2020-12 schemas were added with closed objects and mandatory `const` discriminators:

```text
QUARANTINED_EVIDENCE_MEMORY_RECORD_V1
MEMORY_PROJECTION_REQUEST_V1
CANONICAL_MEMORY_RECORD_V1
MEMORY_CONTROL_REQUEST_V1
MEMORY_CONTROL_RECORD_V1
```

Focused exact-head witness:

```text
CANDIDATE = afd64628cb32720f0661216d079c28d293a41b35
WITNESS_RUN = 32372675351
WITNESS_JOB = 96436633376
EXACT_LINEAGE = PASS
RESULT = 24/24 PASS
```

The two schema tests validate Draft 2020-12 syntax, valid nominal instances, unknown-field rejection, wrong-discriminator rejection, and REVOKE/SUPERSEDE replacement shape.

### RED 4 — importable prestate-less internal mutation path

Security diff review found that `harness.sdk._collective_memory_base.LocalSqliteCollectiveMemoryStoreV1` remained directly constructible. The leading underscore was not a fail-closed boundary; ordinary callers could therefore instantiate the older prestate-less store and bypass the public UCI-6 memory-prestate contract.

A regression was committed before the patch:

```text
TEST_ONLY_CANDIDATE = 46c474309254fc6909071ea4d8e79a0bbce48d47
WITNESS_RUN = 32373063733
WITNESS_JOB = 96437875969
EXACT_LINEAGE = PASS
PRIOR_UCI6_BASELINE = 24/24 PASS
INTERNAL_BASE_GUARD = 1 FAIL / 1 PASS
INTENDED_FAILURE = DID NOT RAISE CollectiveMemoryError
```

This was treated as a real security blocker and no earlier head was promoted.

### GREEN 4 — internal weaker store direct-use guard

The internal implementation store now permits construction only through the exact public subclass `harness.sdk.collective_memory.LocalSqliteCollectiveMemoryStoreV1`; ordinary direct or alternate construction fails with `MEMORY_INTERNAL_BASE_DIRECT_USE_FORBIDDEN`.

```text
CANDIDATE = 8a2d2d6859619e5dd69b2c12bb6627c0cfc7760c
WITNESS_RUN = 32373519415
WITNESS_JOB = 96439327563
EXACT_LINEAGE = PASS
RESULT = 26/26 PASS
```

This closes the accidental parallel mutation API. It is not represented as a Python sandbox against arbitrary malicious same-process code, monkeypatching, or module/class spoofing; that stronger adversary is outside the established reference boundary.

## Final repo-native exact-head witness

The dedicated `UCI-6 Collective Memory Contract` gate ran on the final documented candidate:

```text
CANDIDATE = cfda4275389493b30f54e18b31567b9c05931bca
EXPECTED_PARENT = c47e99b8139a280c39ceacc46db738b2617866d5
RUN_ID = 32373679686
JOB_ID = 96439848249
EXACT_LINEAGE = PASS
SCHEMAS = 12/12 PASS
INHERITED_UCI4_UCI5_TESTS = 99
UCI6_TESTS = 26
TOTAL = 125/125 PASS
FAILURES = 0
ARTIFACT_ID = 9408127778
ARTIFACT_ZIP_SHA256 = 8f5c5d3f9454040dc103dcf68a647b3aaebe141d7c89f53d03ab848290723d51
```

On that same exact candidate SHA, the following inherited gates were observed completed successfully:

```text
UCI-6 Collective Memory Contract = SUCCESS
UCI-5 Atomic Admission Contract = SUCCESS
UCI-4 Effect Chain Contract = SUCCESS
Kernel One = SUCCESS
AEGIS Coordinator Authority = SUCCESS
Coq Formal Attestation = SUCCESS
AEGIS Agent Dispatch = SKIPPED / NOT EVIDENCE OF PASS OR FAILURE
```

## Explicit security and epistemic boundaries

```text
MEMORY_IS_AUTHORITY = FALSE
MEMORY_IS_PROPOSITION_TRUTH = FALSE
QUARANTINE_SELF_PROMOTION = FORBIDDEN
DIRECT_CANONICAL_INSERT_SURFACE = FORBIDDEN_AND_TESTED
PERSISTED_UCI5_ADMISSION_LOOKUP = REQUIRED_AND_TESTED
MEMORY_PRESTATE_BINDING = REQUIRED_AND_TESTED
INTERNAL_PRESTATE_LESS_BASE_DIRECT_USE = FORBIDDEN_AND_TESTED
APPEND_ONLY_REVOKE_SUPERSEDE = IMPLEMENTED_AND_TESTED_REFERENCE
LOCAL_SQLITE_REFERENCE = IMPLEMENTED

PYTHON_MALICIOUS_IN_PROCESS_SANDBOX = NOT_ESTABLISHED
CROSS_DATABASE_ATOMICITY_BETWEEN_UCI5_AND_UCI6 = NOT_ESTABLISHED
SQLITE_AUTHENTICATED_TAMPER_RESISTANCE = NOT_ESTABLISHED
SIGNED_MEMORY_PERSISTENCE = NOT_IMPLEMENTED
MULTI_PROCESS_LINEARIZABILITY = NOT_ESTABLISHED
DISTRIBUTED_LINEARIZABILITY = NOT_ESTABLISHED
PRODUCTION_MEMORY_BACKEND = NOT_ESTABLISHED
PRODUCTION_MEMORY_ADMISSION = NOT_ESTABLISHED
SEMANTIC_TRUTH_OF_STORED_CONTENT = NOT_ESTABLISHED
MEMORY_CONFIDENTIALITY_OR_ENCRYPTION = NOT_ESTABLISHED
QUARANTINE_QUOTA_RETENTION_POLICY = NOT_IMPLEMENTED
VECTOR_RETRIEVAL_IN_THIS_UCI6_PYTHON_REFERENCE = NOT_IMPLEMENTED
AGI = NOT_ESTABLISHED
```

The UCI-5 admission transaction and UCI-6 memory transaction are separate SQLite database transactions. UCI-6 proves that a memory mutation consumes a persisted admitted action; it does **not** claim one cross-database atomic commit spanning admission and memory.

The inherited UCI-4 filesystem-observation hardening debt also remains: resolve/open TOCTOU resistance and bounded/streaming hashing are not established by UCI-6.
