#!/usr/bin/env python3
"""UCI-5 falsification suite for local transactional atomic admission.

The initial import-only RED witness was established on exact candidate
``d508861f74728b775f737b3fcfb6670d659434c4`` before production code existed.
UCI-5 consumes byte-semantically frozen UCI-4 CompleteVerification artifacts
under their historical admission-policy commitment, then applies a fresh UCI-5
eligibility policy downstream.
"""
from __future__ import annotations

import sys
import tempfile
import threading
from dataclasses import asdict, replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.atomic_admission import (  # noqa: E402
    ADMISSION_RECORD_KIND,
    ZERO_ADMISSION_ROOT,
    AdmissionRecordV1,
    AtomicAdmissionError,
    LocalSqliteAtomicAdmissionStoreV1,
    uci5_admission_policy_commitment,
)
from harness.sdk.complete_verifier import FALSE, TRUE, CompleteVerifier  # noqa: E402
from harness.sdk.effect_adapters import FilesystemEffectAdapter, filesystem_state_commitment  # noqa: E402
from harness.sdk.effect_verifier import EffectVerifier  # noqa: E402
from harness.sdk.sovereign_execution import SCHEMA_VERSION  # noqa: E402
from harness.sdk.transition_receipts import (  # noqa: E402
    DENY,
    PERMIT,
    DECISION_RECEIPT_KIND,
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    DecisionReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment as legacy_admission_policy_commitment,
    verifier_policy_commitment,
)

HASHES = [f"{i:064x}" for i in range(1, 128)]
COMMIT = "d" * 40
AUTHORITY_EPOCH = 7


class AtomicAdmissionV1Tests(TestCase):
    def bundle(
        self,
        *,
        nonce: str = "nonce-uci5",
        decision_outcome: str = PERMIT,
        source_admission_policy: str | None = None,
        fence: str | None = None,
    ):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        target = root / "state.txt"
        target.write_bytes(b"before")
        pre = filesystem_state_commitment(allowed_root=root, target=target)
        source_policy = source_admission_policy or legacy_admission_policy_commitment()
        transition = TransitionIdentity(
            schema_version=SCHEMA_VERSION,
            source_commit=COMMIT,
            pre_state_commitment=pre,
            identity_root=HASHES[1],
            delegation_commitment=HASHES[2],
            capability_commitment=HASHES[3],
            action_digest=HASHES[4],
            deterministic_nonce=nonce,
            fence_commitment=fence or HASHES[5],
            verifier_policy_commitment=verifier_policy_commitment(),
            admission_policy_commitment=source_policy,
        )
        decision = DecisionReceipt(
            receipt_kind=DECISION_RECEIPT_KIND,
            transition_id=transition.root,
            decision_outcome=decision_outcome,
            policy_decision_root=HASHES[8],
        )
        execution = ExecutionReceipt(
            receipt_kind=EXECUTION_RECEIPT_KIND,
            transition_id=transition.root,
            execution_instance_id=f"exec-{nonce}",
            outcome=EXECUTION_SUCCEEDED,
            result_digest=HASHES[9],
        )
        adapter = FilesystemEffectAdapter(allowed_root=root)
        handle = adapter.prepare_observation(transition=transition, target=target)
        target.write_bytes(b"after")
        witness = adapter.observe_effect(
            transition=transition,
            handle=handle,
            execution_receipt=execution,
        )
        effect_verifier = EffectVerifier()
        effect_verification = effect_verifier.verify_effect(
            transition=transition,
            execution_receipt=execution,
            witness=witness,
        )
        self.assertEqual(effect_verification.status, TRUE)
        effect_receipt = effect_verifier.issue_effect_receipt(
            transition=transition,
            execution_receipt=execution,
            witness=witness,
            verification=effect_verification,
        )
        complete = CompleteVerifier().verify_complete(
            transition=transition,
            decision_receipt=decision,
            execution_receipt=execution,
            effect_witness=witness,
            effect_verification=effect_verification,
            effect_receipt=effect_receipt,
        )
        return (
            tmp,
            root,
            transition,
            decision,
            execution,
            witness,
            effect_verification,
            effect_receipt,
            complete,
        )

    def store(
        self,
        bundle,
        *,
        initial_state: str | None = None,
        policy: str | None = None,
        epoch: int = AUTHORITY_EPOCH,
        fence: str | None = None,
        db_name: str = "admission.sqlite3",
        fault_injector=None,
    ) -> LocalSqliteAtomicAdmissionStoreV1:
        root = bundle[1]
        transition = bundle[2]
        return LocalSqliteAtomicAdmissionStoreV1(
            db_path=root / db_name,
            initial_state_commitment=initial_state or transition.pre_state_commitment,
            admission_policy_commitment=policy or uci5_admission_policy_commitment(),
            authority_epoch=epoch,
            fence_commitment=fence or transition.fence_commitment,
            fault_injector=fault_injector,
        )

    def admit(self, store, bundle, **overrides):
        transition, decision, execution = bundle[2], bundle[3], bundle[4]
        witness, effect_verification, effect_receipt, complete = bundle[5], bundle[6], bundle[7], bundle[8]
        values = {
            "transition": transition,
            "decision_receipt": decision,
            "execution_receipt": execution,
            "effect_witness": witness,
            "effect_verification": effect_verification,
            "effect_receipt": effect_receipt,
            "complete_verification": complete,
            "expected_current_state": transition.pre_state_commitment,
            "expected_policy_commitment": uci5_admission_policy_commitment(),
            "expected_authority_epoch": AUTHORITY_EPOCH,
            "expected_fence_commitment": transition.fence_commitment,
        }
        values.update(overrides)
        return store.compare_and_admit(**values)

    def assert_denied(self, expected_code: str, fn) -> None:
        with self.assertRaises(AtomicAdmissionError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, expected_code)

    def test_nominal_surface_exists(self):
        self.assertEqual(ADMISSION_RECORD_KIND, "ADMISSION_RECORD_V1")
        self.assertEqual(LocalSqliteAtomicAdmissionStoreV1.__name__, "LocalSqliteAtomicAdmissionStoreV1")
        self.assertEqual(len(uci5_admission_policy_commitment()), 64)

    def test_success_commits_state_and_record_together(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(bundle[8].status, TRUE)
        store = self.store(bundle)
        record = self.admit(store, bundle)
        self.assertIsInstance(record, AdmissionRecordV1)
        self.assertEqual(record.record_kind, ADMISSION_RECORD_KIND)
        self.assertEqual(record.transition_id, bundle[2].root)
        self.assertEqual(record.complete_verification_root, bundle[8].root)
        self.assertEqual(record.source_admission_policy_commitment, legacy_admission_policy_commitment())
        self.assertEqual(record.admission_policy_commitment, uci5_admission_policy_commitment())
        self.assertEqual(record.prior_state_commitment, bundle[2].pre_state_commitment)
        self.assertEqual(record.next_state_commitment, bundle[7].post_state_commitment)
        self.assertEqual(record.authority_epoch, AUTHORITY_EPOCH)
        self.assertEqual(record.sequence, 1)
        self.assertEqual(record.prior_admission_root, ZERO_ADMISSION_ROOT)
        state = store.read_state()
        self.assertEqual(state.state_commitment, bundle[7].post_state_commitment)
        self.assertEqual(state.sequence, 1)
        self.assertEqual(state.last_admission_root, record.root)
        self.assertEqual(store.record_count(), 1)

    def test_caller_cannot_supply_next_state(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        store = self.store(bundle)
        with self.assertRaises(TypeError):
            self.admit(store, bundle, next_state_commitment=HASHES[30])
        self.assertEqual(store.record_count(), 0)

    def test_non_true_complete_verification_cannot_admit(self):
        bundle = self.bundle(decision_outcome=DENY)
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(bundle[8].status, FALSE)
        store = self.store(bundle)
        self.assert_denied("COMPLETE_VERIFICATION_NOT_TRUE", lambda: self.admit(store, bundle))
        self.assertEqual(store.record_count(), 0)

    def test_forged_true_result_is_recomputed_and_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = replace(bundle[8], denial_code="FORGED_TRUE")
        store = self.store(bundle)
        self.assert_denied(
            "COMPLETE_VERIFICATION_RECOMPUTE_MISMATCH",
            lambda: self.admit(store, bundle, complete_verification=forged),
        )
        self.assertEqual(store.record_count(), 0)

    def test_stale_current_state_fails_without_mutation(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        store = self.store(bundle)
        self.assert_denied(
            "CURRENT_STATE_MISMATCH",
            lambda: self.admit(store, bundle, expected_current_state=HASHES[31]),
        )
        self.assertEqual(store.record_count(), 0)

    def test_stale_policy_fails_without_mutation(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        store = self.store(bundle)
        self.assert_denied(
            "CURRENT_ADMISSION_POLICY_MISMATCH",
            lambda: self.admit(store, bundle, expected_policy_commitment=HASHES[32]),
        )
        self.assertEqual(store.record_count(), 0)

    def test_stale_authority_epoch_fails_without_mutation(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        store = self.store(bundle)
        self.assert_denied(
            "CURRENT_AUTHORITY_EPOCH_MISMATCH",
            lambda: self.admit(store, bundle, expected_authority_epoch=AUTHORITY_EPOCH + 1),
        )
        self.assertEqual(store.record_count(), 0)

    def test_stale_fence_fails_without_mutation(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        store = self.store(bundle)
        self.assert_denied(
            "CURRENT_FENCE_MISMATCH",
            lambda: self.admit(store, bundle, expected_fence_commitment=HASHES[33]),
        )
        self.assertEqual(store.record_count(), 0)

    def test_transition_prestate_must_equal_transaction_current_state(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        other_state = HASHES[34]
        store = self.store(bundle, initial_state=other_state)
        self.assert_denied(
            "TRANSITION_PRE_STATE_MISMATCH",
            lambda: self.admit(store, bundle, expected_current_state=other_state),
        )
        self.assertEqual(store.record_count(), 0)

    def test_transition_fence_must_equal_transaction_current_fence(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        other_fence = HASHES[35]
        store = self.store(bundle, fence=other_fence)
        self.assert_denied(
            "TRANSITION_FENCE_MISMATCH",
            lambda: self.admit(store, bundle, expected_fence_commitment=other_fence),
        )
        self.assertEqual(store.record_count(), 0)

    def test_unaccepted_source_admission_policy_cannot_admit(self):
        bundle = self.bundle(source_admission_policy=HASHES[36])
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(bundle[8].status, FALSE)
        store = self.store(bundle)
        self.assert_denied("SOURCE_ADMISSION_POLICY_NOT_ACCEPTED", lambda: self.admit(store, bundle))
        self.assertEqual(store.record_count(), 0)

    def test_effect_receipt_splice_is_rejected_by_recompute(self):
        left = self.bundle(nonce="left")
        right = self.bundle(nonce="right")
        self.addCleanup(left[0].cleanup)
        self.addCleanup(right[0].cleanup)
        store = self.store(left)
        self.assert_denied(
            "COMPLETE_VERIFICATION_NOT_TRUE",
            lambda: self.admit(store, left, effect_receipt=right[7]),
        )
        self.assertEqual(store.record_count(), 0)

    def test_duplicate_transition_replay_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        store = self.store(bundle)
        self.admit(store, bundle)
        self.assert_denied("DUPLICATE_TRANSITION_ADMISSION", lambda: self.admit(store, bundle))
        self.assertEqual(store.record_count(), 1)

    def test_reopen_after_state_advance_accepts_same_persisted_controls(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        db_name = "reopen.sqlite3"
        first = self.store(bundle, db_name=db_name)
        self.admit(first, bundle)
        reopened = self.store(bundle, db_name=db_name)
        self.assertEqual(reopened.read_state().sequence, 1)
        self.assertEqual(reopened.record_count(), 1)

    def test_reopen_rejects_conflicting_persisted_policy(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        db_name = "reopen-policy.sqlite3"
        first = self.store(bundle, db_name=db_name)
        self.admit(first, bundle)
        self.assert_denied(
            "ADMISSION_STORE_CONTROL_PLANE_CONFLICT",
            lambda: self.store(bundle, db_name=db_name, policy=HASHES[37]),
        )

    def test_reopen_rejects_conflicting_persisted_authority_epoch(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        db_name = "reopen-epoch.sqlite3"
        first = self.store(bundle, db_name=db_name)
        self.admit(first, bundle)
        self.assert_denied(
            "ADMISSION_STORE_CONTROL_PLANE_CONFLICT",
            lambda: self.store(bundle, db_name=db_name, epoch=AUTHORITY_EPOCH + 1),
        )

    def test_reopen_rejects_conflicting_persisted_fence(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        db_name = "reopen-fence.sqlite3"
        first = self.store(bundle, db_name=db_name)
        self.admit(first, bundle)
        self.assert_denied(
            "ADMISSION_STORE_CONTROL_PLANE_CONFLICT",
            lambda: self.store(bundle, db_name=db_name, fence=HASHES[38]),
        )

    def test_fault_after_record_insert_rolls_back_both_writes(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)

        def fault(phase: str) -> None:
            if phase == "AFTER_RECORD_INSERT":
                raise RuntimeError("injected")

        store = self.store(bundle, fault_injector=fault)
        before = store.read_state()
        self.assert_denied("ATOMIC_ADMISSION_TRANSACTION_FAILED", lambda: self.admit(store, bundle))
        after = store.read_state()
        self.assertEqual(asdict(after), asdict(before))
        self.assertEqual(store.record_count(), 0)

    def test_two_store_handles_same_prestate_admit_exactly_once(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        db_name = "race.sqlite3"
        first = self.store(bundle, db_name=db_name)
        second = self.store(bundle, db_name=db_name)
        successes: list[str] = []
        denials: list[str] = []
        barrier = threading.Barrier(2)

        def run(store):
            try:
                barrier.wait(timeout=5)
                successes.append(self.admit(store, bundle).root)
            except AtomicAdmissionError as exc:
                denials.append(exc.code)

        threads = [threading.Thread(target=run, args=(first,)), threading.Thread(target=run, args=(second,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(denials), 1)
        self.assertIn(denials[0], {"DUPLICATE_TRANSITION_ADMISSION", "CURRENT_STATE_MISMATCH"})
        self.assertEqual(first.record_count(), 1)
        self.assertEqual(first.read_state().sequence, 1)


if __name__ == "__main__":
    main()
