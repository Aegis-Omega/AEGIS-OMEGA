#!/usr/bin/env python3
"""UCI-6 falsification suite for admitted collective memory.

The import-only RED witness was already established on exact candidate
``78fd533f9613ba24a34c48cf5ea0af24a87a2119`` before production memory code
existed. These tests preregister the behavioral boundary before implementation.
"""
from __future__ import annotations

import tempfile
import threading
from dataclasses import asdict, replace
from pathlib import Path
from unittest import TestCase, main

from harness.sdk.atomic_admission import (
    AdmissionRecordV1,
    AtomicAdmissionError,
    LocalSqliteAtomicAdmissionStoreV1,
    uci5_admission_policy_commitment,
)
from harness.sdk.collective_memory import (
    ACTIVE,
    EVIDENCE_ONLY,
    REVOKE,
    REVOKED,
    SUPERSEDE,
    SUPERSEDED,
    CANONICAL_MEMORY_RECORD_KIND,
    MEMORY_CONTROL_RECORD_KIND,
    MEMORY_CONTROL_REQUEST_KIND,
    MEMORY_PROJECTION_REQUEST_KIND,
    QUARANTINED_MEMORY_RECORD_KIND,
    CanonicalMemoryRecordV1,
    CollectiveMemoryError,
    LocalSqliteCollectiveMemoryStoreV1,
    MemoryControlRequestV1,
    MemoryProjectionRequestV1,
    QuarantinedEvidenceMemoryRecordV1,
    uci6_memory_policy_commitment,
)
from harness.sdk.complete_verifier import TRUE, CompleteVerifier
from harness.sdk.effect_adapters import FilesystemEffectAdapter, filesystem_state_commitment
from harness.sdk.effect_verifier import EffectVerifier
from harness.sdk.sovereign_execution import SCHEMA_VERSION
from harness.sdk.transition_receipts import (
    DECISION_RECEIPT_KIND,
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    PERMIT,
    DecisionReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment as source_admission_policy_commitment,
    verifier_policy_commitment,
)

HASHES = [f"{i:064x}" for i in range(1, 256)]
COMMIT = "e" * 40
AUTHORITY_EPOCH = 11
FENCE = HASHES[5]


class CollectiveMemoryV1Tests(TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.world = self.root / "world.txt"
        self.world.write_bytes(b"state-0")
        initial = filesystem_state_commitment(allowed_root=self.root, target=self.world)
        self.admission_store = LocalSqliteAtomicAdmissionStoreV1(
            db_path=self.root / "admission.sqlite3",
            initial_state_commitment=initial,
            admission_policy_commitment=uci5_admission_policy_commitment(),
            authority_epoch=AUTHORITY_EPOCH,
            fence_commitment=FENCE,
        )
        self.memory_store = LocalSqliteCollectiveMemoryStoreV1(
            db_path=self.root / "memory.sqlite3",
            memory_policy_commitment=uci6_memory_policy_commitment(),
        )
        self.action_counter = 0

    def assert_memory_denied(self, code: str, fn) -> None:
        with self.assertRaises(CollectiveMemoryError) as ctx:
            fn()
        self.assertEqual(ctx.exception.code, code)

    def quarantine_record(
        self,
        *,
        content_digest: str = HASHES[70],
        memory_class: str = "WORK_RESULT",
        epistemic_tier: str = "T2",
        source_ref: str = "provider-artifact:example",
    ) -> QuarantinedEvidenceMemoryRecordV1:
        return QuarantinedEvidenceMemoryRecordV1(
            record_kind=QUARANTINED_MEMORY_RECORD_KIND,
            content_digest=content_digest,
            media_type="text/plain",
            producer_ref="provider:test-model",
            source_ref=source_ref,
            memory_class=memory_class,
            epistemic_tier=epistemic_tier,
            authority=EVIDENCE_ONLY,
            authority_weight_bps=0,
        )

    def projection_request(
        self,
        quarantine: QuarantinedEvidenceMemoryRecordV1,
        *,
        nonce: str,
        content_digest: str | None = None,
        memory_class: str | None = None,
        epistemic_tier: str | None = None,
        policy: str | None = None,
    ) -> MemoryProjectionRequestV1:
        return MemoryProjectionRequestV1(
            request_kind=MEMORY_PROJECTION_REQUEST_KIND,
            quarantine_root=quarantine.root,
            content_digest=content_digest or quarantine.content_digest,
            memory_class=memory_class or quarantine.memory_class,
            epistemic_tier=epistemic_tier or quarantine.epistemic_tier,
            memory_policy_commitment=policy or uci6_memory_policy_commitment(),
            nonce=nonce,
        )

    def admit_action(self, action_digest: str, *, nonce: str | None = None):
        self.action_counter += 1
        actual_nonce = nonce or f"memory-action-{self.action_counter}"
        pre = filesystem_state_commitment(allowed_root=self.root, target=self.world)
        transition = TransitionIdentity(
            schema_version=SCHEMA_VERSION,
            source_commit=COMMIT,
            pre_state_commitment=pre,
            identity_root=HASHES[1],
            delegation_commitment=HASHES[2],
            capability_commitment=HASHES[3],
            action_digest=action_digest,
            deterministic_nonce=actual_nonce,
            fence_commitment=FENCE,
            verifier_policy_commitment=verifier_policy_commitment(),
            admission_policy_commitment=source_admission_policy_commitment(),
        )
        decision = DecisionReceipt(
            receipt_kind=DECISION_RECEIPT_KIND,
            transition_id=transition.root,
            decision_outcome=PERMIT,
            policy_decision_root=HASHES[8],
        )
        execution = ExecutionReceipt(
            receipt_kind=EXECUTION_RECEIPT_KIND,
            transition_id=transition.root,
            execution_instance_id=f"exec-{actual_nonce}",
            outcome=EXECUTION_SUCCEEDED,
            result_digest=HASHES[9],
        )
        adapter = FilesystemEffectAdapter(allowed_root=self.root)
        handle = adapter.prepare_observation(transition=transition, target=self.world)
        self.world.write_bytes(f"state-{self.action_counter}".encode("utf-8"))
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
        self.assertEqual(complete.status, TRUE)
        record = self.admission_store.compare_and_admit(
            transition=transition,
            decision_receipt=decision,
            execution_receipt=execution,
            effect_witness=witness,
            effect_verification=effect_verification,
            effect_receipt=effect_receipt,
            complete_verification=complete,
            expected_current_state=pre,
            expected_policy_commitment=uci5_admission_policy_commitment(),
            expected_authority_epoch=AUTHORITY_EPOCH,
            expected_fence_commitment=FENCE,
        )
        return transition, record

    def project_one(
        self,
        *,
        suffix: str = "one",
        content_digest: str = HASHES[70],
        memory_class: str = "WORK_RESULT",
    ):
        quarantine = self.quarantine_record(
            content_digest=content_digest,
            memory_class=memory_class,
            source_ref=f"provider-artifact:{suffix}",
        )
        self.memory_store.quarantine(quarantine)
        request = self.projection_request(quarantine, nonce=f"projection-{suffix}")
        transition, admission = self.admit_action(request.root, nonce=f"projection-{suffix}")
        canonical = self.memory_store.project_canonical(
            request=request,
            transition=transition,
            admission_record=admission,
            admission_store=self.admission_store,
        )
        return quarantine, request, transition, admission, canonical

    def test_nominal_surface_exists(self):
        self.assertEqual(QUARANTINED_MEMORY_RECORD_KIND, "QUARANTINED_EVIDENCE_MEMORY_RECORD_V1")
        self.assertEqual(CANONICAL_MEMORY_RECORD_KIND, "CANONICAL_MEMORY_RECORD_V1")
        self.assertEqual(MEMORY_PROJECTION_REQUEST_KIND, "MEMORY_PROJECTION_REQUEST_V1")
        self.assertEqual(MEMORY_CONTROL_REQUEST_KIND, "MEMORY_CONTROL_REQUEST_V1")
        self.assertEqual(MEMORY_CONTROL_RECORD_KIND, "MEMORY_CONTROL_RECORD_V1")
        self.assertEqual(len(uci6_memory_policy_commitment()), 64)

    def test_quarantine_is_evidence_only_and_idempotent(self):
        record = self.quarantine_record()
        first = self.memory_store.quarantine(record)
        second = self.memory_store.quarantine(record)
        self.assertEqual(first.root, second.root)
        self.assertEqual(first.authority, EVIDENCE_ONLY)
        self.assertEqual(first.authority_weight_bps, 0)
        self.assertEqual(self.memory_store.quarantine_count(), 1)

    def test_quarantine_rejects_unsupported_tier_promotion_surface(self):
        self.assert_memory_denied(
            "QUARANTINE_EPISTEMIC_TIER_UNSUPPORTED",
            lambda: self.quarantine_record(epistemic_tier="T1"),
        )

    def test_canonical_projection_requires_persisted_uci5_admission(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record())
        request = self.projection_request(quarantine, nonce="not-admitted")
        fake_transition = TransitionIdentity(
            schema_version=SCHEMA_VERSION,
            source_commit=COMMIT,
            pre_state_commitment=filesystem_state_commitment(allowed_root=self.root, target=self.world),
            identity_root=HASHES[1],
            delegation_commitment=HASHES[2],
            capability_commitment=HASHES[3],
            action_digest=request.root,
            deterministic_nonce="not-admitted",
            fence_commitment=FENCE,
            verifier_policy_commitment=verifier_policy_commitment(),
            admission_policy_commitment=source_admission_policy_commitment(),
        )
        forged = AdmissionRecordV1(
            record_kind="ADMISSION_RECORD_V1",
            transition_id=fake_transition.root,
            complete_verification_root=HASHES[40],
            source_admission_policy_commitment=source_admission_policy_commitment(),
            admission_policy_commitment=uci5_admission_policy_commitment(),
            prior_state_commitment=fake_transition.pre_state_commitment,
            next_state_commitment=HASHES[41],
            authority_epoch=AUTHORITY_EPOCH,
            fence_commitment=FENCE,
            sequence=1,
            prior_admission_root="0" * 64,
        )
        self.assert_memory_denied(
            "MEMORY_ADMISSION_NOT_PERSISTED",
            lambda: self.memory_store.project_canonical(
                request=request,
                transition=fake_transition,
                admission_record=forged,
                admission_store=self.admission_store,
            ),
        )
        self.assertEqual(self.memory_store.canonical_count(), 0)

    def test_admission_store_exposes_integrity_checked_record_lookup(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record())
        request = self.projection_request(quarantine, nonce="lookup")
        transition, admission = self.admit_action(request.root, nonce="lookup")
        persisted = self.admission_store.read_admission_record(transition.root)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.root, admission.root)

    def test_projection_action_digest_must_equal_request_root(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record())
        request = self.projection_request(quarantine, nonce="digest-bind")
        transition, admission = self.admit_action(HASHES[80], nonce="digest-bind-wrong")
        self.assert_memory_denied(
            "MEMORY_ACTION_DIGEST_MISMATCH",
            lambda: self.memory_store.project_canonical(
                request=request,
                transition=transition,
                admission_record=admission,
                admission_store=self.admission_store,
            ),
        )

    def test_projection_rejects_forged_admission_record_even_for_admitted_transition(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record())
        request = self.projection_request(quarantine, nonce="forged-record")
        transition, admission = self.admit_action(request.root, nonce="forged-record")
        forged = replace(admission, next_state_commitment=HASHES[81])
        self.assert_memory_denied(
            "MEMORY_ADMISSION_RECORD_MISMATCH",
            lambda: self.memory_store.project_canonical(
                request=request,
                transition=transition,
                admission_record=forged,
                admission_store=self.admission_store,
            ),
        )

    def test_projection_rejects_current_memory_policy_mismatch(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record())
        request = self.projection_request(quarantine, nonce="policy-mismatch", policy=HASHES[82])
        transition, admission = self.admit_action(request.root, nonce="policy-mismatch")
        self.assert_memory_denied(
            "CURRENT_MEMORY_POLICY_MISMATCH",
            lambda: self.memory_store.project_canonical(
                request=request,
                transition=transition,
                admission_record=admission,
                admission_store=self.admission_store,
            ),
        )

    def test_projection_rejects_quarantine_metadata_splice(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record())
        request = self.projection_request(
            quarantine,
            nonce="metadata-splice",
            content_digest=HASHES[83],
        )
        transition, admission = self.admit_action(request.root, nonce="metadata-splice")
        self.assert_memory_denied(
            "MEMORY_PROJECTION_SOURCE_MISMATCH",
            lambda: self.memory_store.project_canonical(
                request=request,
                transition=transition,
                admission_record=admission,
                admission_store=self.admission_store,
            ),
        )

    def test_successful_projection_is_evidence_only_and_event_chained(self):
        _, request, transition, admission, canonical = self.project_one()
        self.assertIsInstance(canonical, CanonicalMemoryRecordV1)
        self.assertEqual(canonical.record_kind, CANONICAL_MEMORY_RECORD_KIND)
        self.assertEqual(canonical.projection_request_root, request.root)
        self.assertEqual(canonical.source_transition_id, transition.root)
        self.assertEqual(canonical.source_admission_root, admission.root)
        self.assertEqual(canonical.authority, EVIDENCE_ONLY)
        self.assertEqual(canonical.authority_weight_bps, 0)
        self.assertEqual(canonical.sequence, 1)
        self.assertEqual(self.memory_store.canonical_count(), 1)
        state = self.memory_store.read_memory_state()
        self.assertEqual(state.sequence, 1)
        self.assertEqual(state.last_event_root, canonical.root)
        view = self.memory_store.get_effective(canonical.root)
        self.assertEqual(view.status, ACTIVE)
        self.assertEqual(view.record.authority, EVIDENCE_ONLY)

    def test_projection_replay_is_rejected(self):
        _, request, transition, admission, canonical = self.project_one()
        self.assert_memory_denied(
            "MEMORY_PROJECTION_REPLAY",
            lambda: self.memory_store.project_canonical(
                request=request,
                transition=transition,
                admission_record=admission,
                admission_store=self.admission_store,
            ),
        )
        self.assertEqual(self.memory_store.canonical_count(), 1)
        self.assertEqual(self.memory_store.get_effective(canonical.root).status, ACTIVE)

    def test_direct_canonical_insert_surface_does_not_exist(self):
        self.assertFalse(hasattr(self.memory_store, "insert_canonical"))
        self.assertFalse(hasattr(self.memory_store, "promote"))

    def test_revoke_requires_admitted_control_and_is_append_only(self):
        _, _, _, _, canonical = self.project_one()
        request = MemoryControlRequestV1(
            request_kind=MEMORY_CONTROL_REQUEST_KIND,
            operation=REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            memory_policy_commitment=uci6_memory_policy_commitment(),
            nonce="revoke-one",
        )
        transition, admission = self.admit_action(request.root, nonce="revoke-one")
        control = self.memory_store.control_memory(
            request=request,
            transition=transition,
            admission_record=admission,
            admission_store=self.admission_store,
        )
        self.assertEqual(control.record_kind, MEMORY_CONTROL_RECORD_KIND)
        self.assertEqual(control.operation, REVOKE)
        self.assertEqual(self.memory_store.get_effective(canonical.root).status, REVOKED)
        self.assertIsNotNone(self.memory_store.read_canonical(canonical.root))
        self.assertEqual(self.memory_store.canonical_count(), 1)
        self.assertEqual(self.memory_store.control_count(), 1)

    def test_control_without_persisted_admission_is_rejected(self):
        _, _, _, _, canonical = self.project_one()
        request = MemoryControlRequestV1(
            request_kind=MEMORY_CONTROL_REQUEST_KIND,
            operation=REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            memory_policy_commitment=uci6_memory_policy_commitment(),
            nonce="forged-control",
        )
        transition = replace(
            self.admit_action(HASHES[90], nonce="other-admitted")[0],
            action_digest=request.root,
            deterministic_nonce="forged-control",
        )
        forged = AdmissionRecordV1(
            record_kind="ADMISSION_RECORD_V1",
            transition_id=transition.root,
            complete_verification_root=HASHES[91],
            source_admission_policy_commitment=source_admission_policy_commitment(),
            admission_policy_commitment=uci5_admission_policy_commitment(),
            prior_state_commitment=transition.pre_state_commitment,
            next_state_commitment=HASHES[92],
            authority_epoch=AUTHORITY_EPOCH,
            fence_commitment=FENCE,
            sequence=99,
            prior_admission_root=HASHES[93],
        )
        self.assert_memory_denied(
            "MEMORY_ADMISSION_NOT_PERSISTED",
            lambda: self.memory_store.control_memory(
                request=request,
                transition=transition,
                admission_record=forged,
                admission_store=self.admission_store,
            ),
        )

    def test_supersede_requires_active_distinct_replacement(self):
        _, _, _, _, first = self.project_one(suffix="first", content_digest=HASHES[100])
        _, _, _, _, replacement = self.project_one(suffix="replacement", content_digest=HASHES[101])
        request = MemoryControlRequestV1(
            request_kind=MEMORY_CONTROL_REQUEST_KIND,
            operation=SUPERSEDE,
            target_memory_root=first.root,
            replacement_memory_root=replacement.root,
            memory_policy_commitment=uci6_memory_policy_commitment(),
            nonce="supersede-first",
        )
        transition, admission = self.admit_action(request.root, nonce="supersede-first")
        self.memory_store.control_memory(
            request=request,
            transition=transition,
            admission_record=admission,
            admission_store=self.admission_store,
        )
        view = self.memory_store.get_effective(first.root)
        self.assertEqual(view.status, SUPERSEDED)
        self.assertEqual(view.replacement_memory_root, replacement.root)
        self.assertEqual(self.memory_store.get_effective(replacement.root).status, ACTIVE)

    def test_control_rejects_inactive_target_second_time(self):
        _, _, _, _, canonical = self.project_one()
        first_request = MemoryControlRequestV1(
            request_kind=MEMORY_CONTROL_REQUEST_KIND,
            operation=REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            memory_policy_commitment=uci6_memory_policy_commitment(),
            nonce="first-revoke",
        )
        transition, admission = self.admit_action(first_request.root, nonce="first-revoke")
        self.memory_store.control_memory(
            request=first_request,
            transition=transition,
            admission_record=admission,
            admission_store=self.admission_store,
        )
        second_request = replace(first_request, nonce="second-revoke")
        second_transition, second_admission = self.admit_action(second_request.root, nonce="second-revoke")
        self.assert_memory_denied(
            "MEMORY_TARGET_NOT_ACTIVE",
            lambda: self.memory_store.control_memory(
                request=second_request,
                transition=second_transition,
                admission_record=second_admission,
                admission_store=self.admission_store,
            ),
        )

    def test_supersede_self_is_rejected_by_request_contract(self):
        _, _, _, _, canonical = self.project_one()
        self.assert_memory_denied(
            "MEMORY_SUPERSEDE_SELF",
            lambda: MemoryControlRequestV1(
                request_kind=MEMORY_CONTROL_REQUEST_KIND,
                operation=SUPERSEDE,
                target_memory_root=canonical.root,
                replacement_memory_root=canonical.root,
                memory_policy_commitment=uci6_memory_policy_commitment(),
                nonce="self",
            ),
        )

    def test_fault_after_canonical_insert_rolls_back_record_and_event_state(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record(source_ref="provider:fault"))
        request = self.projection_request(quarantine, nonce="fault-projection")
        transition, admission = self.admit_action(request.root, nonce="fault-projection")
        before = self.memory_store.read_memory_state()

        def fault(phase: str) -> None:
            if phase == "AFTER_CANONICAL_INSERT":
                raise RuntimeError("injected")

        faulting = LocalSqliteCollectiveMemoryStoreV1(
            db_path=self.root / "memory.sqlite3",
            memory_policy_commitment=uci6_memory_policy_commitment(),
            fault_injector=fault,
        )
        self.assert_memory_denied(
            "MEMORY_TRANSACTION_FAILED",
            lambda: faulting.project_canonical(
                request=request,
                transition=transition,
                admission_record=admission,
                admission_store=self.admission_store,
            ),
        )
        self.assertEqual(asdict(self.memory_store.read_memory_state()), asdict(before))
        self.assertEqual(self.memory_store.canonical_count(), 0)

    def test_two_store_handles_racing_same_projection_yield_one_record(self):
        quarantine = self.memory_store.quarantine(self.quarantine_record(source_ref="provider:race"))
        request = self.projection_request(quarantine, nonce="race-projection")
        transition, admission = self.admit_action(request.root, nonce="race-projection")
        other = LocalSqliteCollectiveMemoryStoreV1(
            db_path=self.root / "memory.sqlite3",
            memory_policy_commitment=uci6_memory_policy_commitment(),
        )
        barrier = threading.Barrier(2)
        successes: list[str] = []
        denials: list[str] = []

        def run(store):
            try:
                barrier.wait(timeout=5)
                record = store.project_canonical(
                    request=request,
                    transition=transition,
                    admission_record=admission,
                    admission_store=self.admission_store,
                )
                successes.append(record.root)
            except CollectiveMemoryError as exc:
                denials.append(exc.code)

        threads = [threading.Thread(target=run, args=(self.memory_store,)), threading.Thread(target=run, args=(other,))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(len(successes), 1)
        self.assertEqual(denials, ["MEMORY_PROJECTION_REPLAY"])
        self.assertEqual(self.memory_store.canonical_count(), 1)
        self.assertEqual(self.memory_store.read_memory_state().sequence, 1)

    def test_reopen_with_conflicting_memory_policy_fails_closed(self):
        self.assert_memory_denied(
            "MEMORY_STORE_POLICY_CONFLICT",
            lambda: LocalSqliteCollectiveMemoryStoreV1(
                db_path=self.root / "memory.sqlite3",
                memory_policy_commitment=HASHES[120],
            ),
        )


if __name__ == "__main__":
    main()
