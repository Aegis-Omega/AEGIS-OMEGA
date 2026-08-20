#!/usr/bin/env python3
"""UCI-6 behavioral suite with exact memory-prestate request binding.

The original 20-test RED/GREEN baseline is preserved byte-for-byte in the
adjacent non-collected ``_uci6_collective_memory_base.py`` module.  This public
test module subclasses that baseline and updates only request construction that
must bind the current memory event sequence/root discovered by adversarial
review.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_BASE_PATH = Path(__file__).with_name("_uci6_collective_memory_base.py")
_SPEC = importlib.util.spec_from_file_location("uci6_collective_memory_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_base)


class CollectiveMemoryV1Tests(_base.CollectiveMemoryV1Tests):
    def projection_request(
        self,
        quarantine,
        *,
        nonce: str,
        content_digest: str | None = None,
        memory_class: str | None = None,
        epistemic_tier: str | None = None,
        policy: str | None = None,
    ):
        state = self.memory_store.read_memory_state()
        return _base.MemoryProjectionRequestV1(
            request_kind=_base.MEMORY_PROJECTION_REQUEST_KIND,
            quarantine_root=quarantine.root,
            content_digest=content_digest or quarantine.content_digest,
            memory_class=memory_class or quarantine.memory_class,
            epistemic_tier=epistemic_tier or quarantine.epistemic_tier,
            memory_policy_commitment=policy or _base.uci6_memory_policy_commitment(),
            expected_memory_sequence=state.sequence,
            expected_memory_event_root=state.last_event_root,
            nonce=nonce,
        )

    def _control_request(
        self,
        *,
        operation: str,
        target_memory_root: str,
        replacement_memory_root: str | None,
        nonce: str,
    ):
        state = self.memory_store.read_memory_state()
        return _base.MemoryControlRequestV1(
            request_kind=_base.MEMORY_CONTROL_REQUEST_KIND,
            operation=operation,
            target_memory_root=target_memory_root,
            replacement_memory_root=replacement_memory_root,
            memory_policy_commitment=_base.uci6_memory_policy_commitment(),
            expected_memory_sequence=state.sequence,
            expected_memory_event_root=state.last_event_root,
            nonce=nonce,
        )

    def test_revoke_requires_admitted_control_and_is_append_only(self):
        _, _, _, _, canonical = self.project_one()
        request = self._control_request(
            operation=_base.REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            nonce="revoke-one",
        )
        transition, admission = self.admit_action(request.root, nonce="revoke-one")
        control = self.memory_store.control_memory(
            request=request,
            transition=transition,
            admission_record=admission,
            admission_store=self.admission_store,
        )
        self.assertEqual(control.record_kind, _base.MEMORY_CONTROL_RECORD_KIND)
        self.assertEqual(control.operation, _base.REVOKE)
        self.assertEqual(self.memory_store.get_effective(canonical.root).status, _base.REVOKED)
        self.assertIsNotNone(self.memory_store.read_canonical(canonical.root))
        self.assertEqual(self.memory_store.canonical_count(), 1)
        self.assertEqual(self.memory_store.control_count(), 1)

    def test_control_without_persisted_admission_is_rejected(self):
        _, _, _, _, canonical = self.project_one()
        request = self._control_request(
            operation=_base.REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            nonce="forged-control",
        )
        transition = _base.replace(
            self.admit_action(_base.HASHES[90], nonce="other-admitted")[0],
            action_digest=request.root,
            deterministic_nonce="forged-control",
        )
        forged = _base.AdmissionRecordV1(
            record_kind="ADMISSION_RECORD_V1",
            transition_id=transition.root,
            complete_verification_root=_base.HASHES[91],
            source_admission_policy_commitment=_base.source_admission_policy_commitment(),
            admission_policy_commitment=_base.uci5_admission_policy_commitment(),
            prior_state_commitment=transition.pre_state_commitment,
            next_state_commitment=_base.HASHES[92],
            authority_epoch=_base.AUTHORITY_EPOCH,
            fence_commitment=_base.FENCE,
            sequence=99,
            prior_admission_root=_base.HASHES[93],
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
        _, _, _, _, first = self.project_one(suffix="first", content_digest=_base.HASHES[100])
        _, _, _, _, replacement = self.project_one(suffix="replacement", content_digest=_base.HASHES[101])
        request = self._control_request(
            operation=_base.SUPERSEDE,
            target_memory_root=first.root,
            replacement_memory_root=replacement.root,
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
        self.assertEqual(view.status, _base.SUPERSEDED)
        self.assertEqual(view.replacement_memory_root, replacement.root)
        self.assertEqual(self.memory_store.get_effective(replacement.root).status, _base.ACTIVE)

    def test_control_rejects_inactive_target_second_time(self):
        _, _, _, _, canonical = self.project_one()
        first_request = self._control_request(
            operation=_base.REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            nonce="first-revoke",
        )
        transition, admission = self.admit_action(first_request.root, nonce="first-revoke")
        self.memory_store.control_memory(
            request=first_request,
            transition=transition,
            admission_record=admission,
            admission_store=self.admission_store,
        )

        # The second action must bind the *new* memory pre-state so that the
        # failure reaches target-status semantics rather than failing stale.
        second_request = self._control_request(
            operation=_base.REVOKE,
            target_memory_root=canonical.root,
            replacement_memory_root=None,
            nonce="second-revoke",
        )
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
        state = self.memory_store.read_memory_state()
        self.assert_memory_denied(
            "MEMORY_SUPERSEDE_SELF",
            lambda: _base.MemoryControlRequestV1(
                request_kind=_base.MEMORY_CONTROL_REQUEST_KIND,
                operation=_base.SUPERSEDE,
                target_memory_root=canonical.root,
                replacement_memory_root=canonical.root,
                memory_policy_commitment=_base.uci6_memory_policy_commitment(),
                expected_memory_sequence=state.sequence,
                expected_memory_event_root=state.last_event_root,
                nonce="self",
            ),
        )


if __name__ == "__main__":
    _base.main()
