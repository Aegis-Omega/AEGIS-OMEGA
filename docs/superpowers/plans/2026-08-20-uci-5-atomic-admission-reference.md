# UCI-5 Atomic Admission Reference — Implementation Plan

> **Execution mode:** test-first, exact-head, fail-closed. UCI-4 remains immutable input lineage; UCI-5 is a stacked successor.

**Goal:** add a local transactional reference admission boundary that atomically commits the verified post-state and its generated `AdmissionRecordV1`, or commits neither, while checking current state, admission policy, authority epoch, and fence at the same transaction boundary.

**Exact parent:** `#276@9702004a6230d6a84cc322edb48b55c14e90fe15`

**Architecture:** reuse the frozen UCI-4 decision/execution/effect/CompleteVerification chain. Do not trust a caller-supplied `CompleteVerificationResult` by shape alone: UCI-5 receives the full nominal bundle, recomputes CompleteVerification under the UCI-5 admission-policy commitment, then compares the recomputed root with the supplied result before opening the state mutation path. The next canonical state is derived from the verified `EffectReceipt.post_state_commitment`; it is never caller-supplied. A SQLite standard-library reference store uses one `BEGIN IMMEDIATE` transaction to validate the current control-plane snapshot, insert the generated admission record, and update canonical state. On any exception, rollback leaves both unchanged.

**Important epistemic boundary:** current `authority_epoch` is an admission-time eligibility condition. The frozen UCI-4 `TransitionIdentity` does not contain an authority-epoch field. UCI-5 therefore establishes `CURRENT_EPOCH_CHECKED_AT_ADMISSION`, not `TRANSITION_HISTORICALLY_BOUND_TO_AUTHORITY_EPOCH`. That stronger work-node-to-transition binding remains a later integration obligation.

**Non-claims:** no Postgres/Cockroach transaction proof, no distributed consensus, no distributed linearizability, no production admission, no automatic external mutation, no provider/model authority.

---

## Task 1 — RED: admission module absent

**Create:** `sovereign-omega-v2/python/tests/test_uci5_atomic_admission.py`

Preregister a test importing:

```python
from harness.sdk.atomic_admission import (
    ADMISSION_RECORD_KIND,
    LocalSqliteAtomicAdmissionStoreV1,
    uci5_admission_policy_commitment,
)
```

The first exact-head witness must fail specifically because `harness.sdk.atomic_admission` does not exist.

## Task 2 — admission policy version + CompleteVerifier compatibility

**Modify:** `harness/sdk/complete_verifier.py`

Add an optional `expected_admission_policy_commitment` constructor argument. Default behavior MUST remain byte-semantically compatible with PR-4: if omitted, it resolves to existing `transition_receipts.admission_policy_commitment()`.

`V_admission_policy_binding` compares the transition against the configured expected commitment.

**Create in new module:** `UCI5_ADMISSION_POLICY_V1`, with explicit fields:

```text
atomic_admission = LOCAL_SQLITE_REFERENCE_ONLY
effect_bound_admission = REFERENCE_ONLY
complete_verification = REQUIRED
current_state_match = REQUIRED
current_policy_match = REQUIRED
current_authority_epoch_match = REQUIRED
current_fence_match = REQUIRED
distributed_linearizability = NOT_ESTABLISHED
production_admission = NOT_ESTABLISHED
```

Do not overwrite or reinterpret `PR1_ADMISSION_POLICY` on UCI-4.

## Task 3 — nominal `AdmissionRecordV1`

**Create:** `harness/sdk/atomic_admission.py`
**Create:** `schemas/admission-record.v1.schema.json`

`AdmissionRecordV1` fields:

```text
record_kind = ADMISSION_RECORD_V1
transition_id
complete_verification_root
prior_state_commitment
next_state_commitment
admission_policy_commitment
authority_epoch
fence_commitment
sequence
prior_admission_root
```

The record root uses a dedicated `AEGIS_ADMISSION_RECORD_V1` hash domain.

The store, never the caller, creates the record after every obligation has passed.

## Task 4 — local SQLite atomic store

`LocalSqliteAtomicAdmissionStoreV1` owns two tables:

```text
admission_state(singleton=1, state_commitment, admission_policy_commitment,
                authority_epoch, fence_commitment, sequence, last_admission_root)
admission_records(sequence PK, transition_id UNIQUE, admission_root UNIQUE, payload_json)
```

Initialization creates exactly one control-plane state row.

`compare_and_admit(...)` receives the exact UCI-4 bundle plus:

```text
expected_current_state
expected_policy_commitment
expected_authority_epoch
expected_fence_commitment
```

It MUST:

1. require exact nominal input types;
2. recompute `CompleteVerifier(expected_admission_policy_commitment=...)` over the full bundle;
3. require recomputed status `TRUE` and every obligation `TRUE`;
4. require supplied CompleteVerification root == recomputed root;
5. require EffectReceipt root == recomputed CompleteVerification `effect_receipt_root`;
6. derive `next_state_commitment = effect_receipt.post_state_commitment`;
7. `BEGIN IMMEDIATE`;
8. read the current singleton state inside the transaction;
9. compare current state, policy, authority epoch, and fence with the expected values;
10. also require transition pre-state, transition admission-policy commitment, and transition fence commitment to match the same current snapshot;
11. reject duplicate transition replay;
12. generate `AdmissionRecordV1` with the next sequence and prior admission root;
13. insert the record and update canonical state in the same transaction;
14. COMMIT;
15. on any error, ROLLBACK and leave state + records unchanged.

No caller-provided next-state field exists.

## Task 5 — adversarial/fault tests

Required tests:

- exact successful bundle -> one record + state advances together;
- CompleteVerification FALSE/UNKNOWN/MISSING/ERROR -> no mutation;
- syntactically forged TRUE result whose root differs from recomputation -> reject;
- stale current state -> reject/no mutation;
- stale admission policy -> reject/no mutation;
- stale authority epoch -> reject/no mutation;
- stale fence -> reject/no mutation;
- transition pre-state mismatch -> reject/no mutation;
- transition admission-policy mismatch -> reject/no mutation;
- transition fence mismatch -> reject/no mutation;
- EffectReceipt / CompleteVerification root splicing -> reject;
- duplicate transition replay -> reject/no second record;
- injected fault after record insert but before state update -> transaction rollback leaves zero partial commit;
- two store handles racing from the same expected state -> exactly one admission succeeds;
- serialized schema rejects unknown fields and wrong `record_kind`.

## Task 6 — exact-head CI gate

**Create:** `.github/workflows/uci-5-atomic-admission-contract.yml`

The gate must:

- checkout exact PR head;
- validate exact stacked parent ancestry;
- install pinned pytest/jsonschema only;
- run UCI-5 tests plus the full UCI-4 79-test regression set;
- validate `admission-record.v1.schema.json` and inherited six UCI-4 schemas;
- emit an evidence-only witness summary with explicit non-claims.

## Task 7 — audit ledger and stacked PR

**Create:** `docs/audits/2026-08-20-uci5-atomic-admission-lineage-ledger.md`

Record RED candidate, GREEN candidates, exact runner IDs/artifact digests, and current ledger. Open a DRAFT PR stacked on `feat/uci-4-effect-chain-integration-v1`.

## Acceptance ledger

Only after exact-head GREEN:

```text
UCI5_LOCAL_SQLITE_ATOMIC_ADMISSION = IMPLEMENTED_AND_EXACT_HEAD_TESTED_REFERENCE
STATE_AND_ADMISSION_RECORD_SINGLE_TRANSACTION = ESTABLISHED_FOR_REFERENCE_STORE
CURRENT_STATE_CHECK = ESTABLISHED
CURRENT_POLICY_CHECK = ESTABLISHED
CURRENT_AUTHORITY_EPOCH_CHECK = ESTABLISHED_AT_ADMISSION_TIME
CURRENT_FENCE_CHECK = ESTABLISHED
CALLER_SUPPLIED_NEXT_STATE = FORBIDDEN
COMPLETE_VERIFICATION_RECOMPUTE = REQUIRED
DUPLICATE_TRANSITION_ADMISSION = FORBIDDEN
TRANSACTION_ROLLBACK_ON_INJECTED_FAULT = ESTABLISHED

TRANSITION_HISTORICALLY_BOUND_TO_AUTHORITY_EPOCH = NOT_ESTABLISHED
MULTI_PROCESS_LINEARIZABILITY = LIMITED_TO_SQLITE_LOCAL_DATABASE_SEMANTICS
DISTRIBUTED_LINEARIZABILITY = NOT_ESTABLISHED
PRODUCTION_ADMISSION = NOT_ESTABLISHED
```
