# AEGIS Ω UCI-5 Atomic Admission Reference — Lineage & Security Ledger

Date: 2026-08-20
Status: IMPLEMENTED / REPO-NATIVE CODE CHECKPOINT VERIFIED / FINAL DOCUMENTED-HEAD RECHECK REQUIRED
Authority: EVIDENCE_ONLY

## 1. Exact lineage

```text
CANONICAL_MAIN = 32b7eb6a37fb69d19dd80189390b6641c5004ef1
UCI4_PARENT_PR = #276
UCI4_PARENT_SHA = 9702004a6230d6a84cc322edb48b55c14e90fe15
UCI5_PR = #277
UCI5_IMPORT_RED_SHA = d508861f74728b775f737b3fcfb6670d659434c4
UCI5_FIRST_GREEN_SHA = 66e45236ce4f50d247410e72301d2e419238348f
UCI5_REOPEN_REGRESSION_RED_SHA = fd1d5d01e168ef0bfdf566b32d93b57633fc35d5
UCI5_HARDENED_CODE_SHA = cca27b70d6645e2079ebbb5ffe1c10074f28574d
```

UCI-5 is stacked directly on the final exact UCI-4 checkpoint. It does not mutate #276 or the frozen #268 -> #273 effect-verification semantics.

## 2. Policy-version boundary

UCI-4 CompleteVerification is preserved under its historical safe-incompleteness admission-policy commitment. UCI-5 does not rewrite that commitment.

Instead, `UCI5_ADMISSION_POLICY_V1` is a fresh downstream eligibility policy that explicitly accepts:

```text
COMPLETE_VERIFICATION_RESULT_V1
+ frozen CompleteVerifier policy commitment
+ frozen source admission-policy commitment
```

and separately requires:

```text
LOCAL_SQLITE_REFERENCE_ONLY atomic admission
current state match
current UCI-5 policy match
current authority epoch match
current fence match
CompleteVerification recomputation
caller-supplied next state forbidden
```

Therefore:

```text
UCI4_POLICY_BYTES_MUTATED_BY_UCI5 = FALSE
UCI5_POLICY_VERSION_BRIDGE = IMPLEMENTED
```

## 3. Admission flow

```text
full nominal UCI-4 bundle
  -> recompute CompleteVerification
  -> require exact supplied/recomputed root equality
  -> require accepted source verifier/policy profile
  -> derive next_state from EffectReceipt.post_state_commitment
  -> BEGIN IMMEDIATE
  -> reject duplicate transition
  -> read current state/policy/epoch/fence inside transaction
  -> compare all current eligibility predicates
  -> bind transition pre-state + transition fence to current snapshot
  -> generate AdmissionRecordV1
  -> insert AdmissionRecord
  -> compare-and-update canonical state
  -> COMMIT
```

Any exception before commit rolls back the transaction. The caller has no `next_state_commitment` parameter.

## 4. Initial RED witness

The import-only UCI-5 test existed before `harness.sdk.atomic_admission`.

Independent hosted witness:

```text
RUNNER_REPOSITORY = tarikskalic33/info
RUN_ID = 32349191220
JOB_ID = 96364388458
CANDIDATE_SHA = d508861f74728b775f737b3fcfb6670d659434c4
EXPECTED_PARENT_SHA = 9702004a6230d6a84cc322edb48b55c14e90fe15
EXACT_LINEAGE = PASS
```

Observed intended failure:

```text
ModuleNotFoundError: No module named 'harness.sdk.atomic_admission'
UCI5_RED_INTENDED_MISSING_ATOMIC_ADMISSION = PASS
```

## 5. First GREEN witness

First implementation candidate:

```text
CANDIDATE_SHA = 66e45236ce4f50d247410e72301d2e419238348f
RUNNER_REPOSITORY = tarikskalic33/info
RUN_ID = 32349739385
JOB_ID = 96366083622
EXACT_LINEAGE = PASS
UCI5_FOCUSED_TESTS = 16/16 PASS
```

The focused suite covered successful atomic commit, no caller next-state, CompleteVerification recomputation, stale state/policy/epoch/fence, source policy rejection, receipt splicing, duplicate replay, transaction rollback after injected post-insert fault, and two independent SQLite store handles racing on one expected pre-state.

## 6. First repo-native integrated witness

Repo-native UCI-5 gate on exact candidate:

```text
CANDIDATE_SHA = 184c981128da71e3a795dc45933407352f8b892e
RUN_ID = 32349834564
JOB_ID = 96366373674
SCHEMAS = 7/7 PASS
INHERITED_UCI4_PLUS_UCI5_TESTS = 95/95 PASS
ARTIFACT_ID = 9399418988
ARTIFACT_ZIP_SHA256 = 74e70d43c42e00f83a344fd94aa6b8c120a7cd645518d972c5e6ba9fe669af7c
```

This established the initial local transactional reference but was not treated as final after adversarial review found a reopen control-plane gap.

## 7. Adversarial reopen finding and second RED

Manual review found that `_initialize()` checked constructor-supplied control-plane values only while `sequence == 0`. After the first admission, reopening an existing database with a conflicting supplied policy, authority epoch, or fence did not fail at construction.

This was not hidden behind the 95/95 result. Regression tests were added before the patch.

Exact test-only candidate:

```text
CANDIDATE_SHA = fd1d5d01e168ef0bfdf566b32d93b57633fc35d5
RUNNER_REPOSITORY = tarikskalic33/info
RUN_ID = 32350115000
JOB_ID = 96367235059
EXACT_LINEAGE = PASS
RESULT = 17 PASS / 3 FAIL
```

The three intended failures were exactly:

```text
test_reopen_rejects_conflicting_persisted_policy
test_reopen_rejects_conflicting_persisted_authority_epoch
test_reopen_rejects_conflicting_persisted_fence
```

Each failed because `AtomicAdmissionError` was not raised.

## 8. Hardened GREEN checkpoint

The fix requires persisted policy, authority epoch, and fence to equal the constructor-supplied control-plane snapshot on every reopen. The historical `initial_state_commitment` is required only at sequence 0, because the canonical state legitimately advances after admission.

Repo-native exact-head evidence:

```text
CANDIDATE_SHA = cca27b70d6645e2079ebbb5ffe1c10074f28574d
EXPECTED_PARENT_SHA = 9702004a6230d6a84cc322edb48b55c14e90fe15
RUN_ID = 32350263664
JOB_ID = 96367695692
EXACT_LINEAGE = PASS
SCHEMAS = 7/7 PASS
ADMISSION_SCHEMA_NEGATIVE_VECTORS = PASS
INHERITED_UCI4_PLUS_UCI5_TESTS = 99/99 PASS
ARTIFACT_ID = 9399576329
ARTIFACT_ZIP_SHA256 = 6a362c0d42629ce146cbb216f0d0d6202a99f8e3af5cd2d39b135808c4e24fb3
```

On the same exact code checkpoint:

```text
UCI-4 Effect Chain Contract = SUCCESS
Kernel One = SUCCESS
AEGIS Coordinator Authority = SUCCESS
AEGIS Agent Dispatch = SKIPPED / NOT EVIDENCE
Coq Formal Attestation = observed in progress at ledger-write time
```

A later completed Coq result must be bound by exact SHA before it is reported as PASS.

## 9. Established reference properties

At the hardened code checkpoint:

```text
UCI5_LOCAL_SQLITE_ATOMIC_ADMISSION = IMPLEMENTED_AND_EXACT_HEAD_TESTED_REFERENCE
STATE_AND_ADMISSION_RECORD_SINGLE_TRANSACTION = ESTABLISHED_FOR_REFERENCE_STORE
UCI4_COMPLETE_VERIFICATION_RECOMPUTE = REQUIRED_AND_TESTED
CALLER_SUPPLIED_NEXT_STATE = FORBIDDEN_AND_TESTED
NEXT_STATE_DERIVED_FROM_VERIFIED_EFFECT_RECEIPT = IMPLEMENTED_AND_TESTED
CURRENT_STATE_CHECK = IMPLEMENTED_AND_TESTED
CURRENT_UCI5_POLICY_CHECK = IMPLEMENTED_AND_TESTED
CURRENT_AUTHORITY_EPOCH_CHECK = IMPLEMENTED_AND_TESTED_AT_ADMISSION_TIME
CURRENT_FENCE_CHECK = IMPLEMENTED_AND_TESTED
TRANSITION_PRESTATE_CURRENT_STATE_BINDING = IMPLEMENTED_AND_TESTED
TRANSITION_FENCE_CURRENT_FENCE_BINDING = IMPLEMENTED_AND_TESTED
DUPLICATE_TRANSITION_ADMISSION = FORBIDDEN_AND_TESTED
TRANSACTION_ROLLBACK_AFTER_INJECTED_PARTIAL_WRITE = ESTABLISHED_FOR_REFERENCE_STORE
TWO_STORE_HANDLE_SINGLE_WINNER = ESTABLISHED_IN_SAME_PROCESS
PERSISTED_CONTROL_PLANE_REOPEN_CONFLICT = FAIL_CLOSED_AND_TESTED
```

## 10. Security and epistemic boundaries that remain open

Successful SQLite transactions and hash-linked AdmissionRecords do not establish authenticated storage integrity against an actor that can rewrite the database file.

```text
SQLITE_DATABASE_AUTHENTICATED_TAMPER_RESISTANCE = NOT_ESTABLISHED
SIGNED_ADMISSION_RECORD_PERSISTENCE = NOT_IMPLEMENTED
DATABASE_FILE_PERMISSION_HARDENING = NOT_ESTABLISHED
FILESYSTEM_DURABILITY_ACROSS_POWER_LOSS = NOT_INDEPENDENTLY_ESTABLISHED
MULTI_PROCESS_RACE_WITNESS = NOT_ESTABLISHED
DISTRIBUTED_LINEARIZABILITY = NOT_ESTABLISHED
POSTGRES_ATOMIC_ADMISSION_EQUIVALENCE = NOT_ESTABLISHED
COCKROACH_ATOMIC_ADMISSION_EQUIVALENCE = NOT_ESTABLISHED
CONTROL_PLANE_POLICY_EPOCH_FENCE_ROTATION_API = NOT_IMPLEMENTED
TRANSITION_HISTORICALLY_BOUND_TO_AUTHORITY_EPOCH = NOT_ESTABLISHED
PRODUCTION_ADMISSION = NOT_ESTABLISHED
```

The two-handle race test uses separate SQLite connections in one process. It must not be promoted to a cross-process or distributed linearizability claim.

UCI-4 also retains its separately recorded production filesystem-observation hardening debt (`resolve -> open` TOCTOU and whole-file hashing bounds). UCI-5 does not erase it.

## 11. Final-head rule

This ledger commit changes the PR head. Therefore the `cca27b70...` evidence is a verified code checkpoint, not automatically the final PR-head receipt.

A fresh repo-native UCI-5 exact-head run is mandatory after this ledger is committed. No PASS from an older SHA may be promoted to the final PR head by assertion.
