#!/usr/bin/env python3
"""PR-2 falsification suite: independent effect observation remains below VerifyEffect."""
from __future__ import annotations

import inspect
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import MutationReceipt, SCHEMA_VERSION, ZERO_HASH  # noqa: E402
from harness.sdk.transition_receipts import (  # noqa: E402
    DECISION_RECEIPT_KIND,
    EFFECT_RECEIPT_KIND,
    EXECUTION_FAILED,
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    PERMIT,
    PR1_VERIFIER_POLICY,
    PR2_VERIFIER_POLICY,
    DecisionReceipt,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    accept_effect_evidence,
    build_transition_identity,
    pr1_verifier_policy_commitment,
    verifier_policy_commitment,
)
from harness.sdk.effect_adapters import (  # noqa: E402
    EffectAdapterError,
    EffectWitness,
    FilesystemEffectAdapter,
    filesystem_state_commitment,
    is_adapter_bound_effect_evidence,
)

HASHES = [f"{index:064x}" for index in range(1, 40)]
COMMIT = "a" * 40


class EffectAdapterPR2Tests(TestCase):
    def transition(self, *, pre_state_commitment: str, **changes) -> TransitionIdentity:
        values = {
            "schema_version": SCHEMA_VERSION,
            "source_commit": COMMIT,
            "pre_state_commitment": pre_state_commitment,
            "identity_root": HASHES[1],
            "delegation_commitment": HASHES[2],
            "capability_commitment": HASHES[3],
            "action_digest": HASHES[4],
            "deterministic_nonce": "nonce-pr2-1",
            "fence_commitment": HASHES[5],
            "verifier_policy_commitment": HASHES[6],
            "admission_policy_commitment": HASHES[7],
        }
        values.update(changes)
        return TransitionIdentity(**values)

    def decision(self, transition: TransitionIdentity) -> DecisionReceipt:
        return DecisionReceipt(
            receipt_kind=DECISION_RECEIPT_KIND,
            transition_id=transition.root,
            decision_outcome=PERMIT,
            policy_decision_root=HASHES[8],
        )

    def execution(
        self,
        transition: TransitionIdentity,
        *,
        execution_instance_id: str = "exec-pr2-1",
        outcome: str = EXECUTION_SUCCEEDED,
    ) -> ExecutionReceipt:
        return ExecutionReceipt(
            receipt_kind=EXECUTION_RECEIPT_KIND,
            transition_id=transition.root,
            execution_instance_id=execution_instance_id,
            outcome=outcome,
            result_digest=HASHES[9],
        )

    def legacy_receipt(self) -> MutationReceipt:
        return MutationReceipt(
            receipt_version=SCHEMA_VERSION,
            execution_identity_root=HASHES[1],
            workspace_binding=HASHES[2],
            policy_decision_root=HASHES[8],
            authority_score="1.000000",
            authority_domain="repo",
            action_class="D2",
            tool="write_file",
            target=HASHES[10],
            pre_state_digest=HASHES[11],
            requested_action_digest=HASHES[12],
            result_digest=HASHES[13],
            post_state_digest=HASHES[14],
            parent_receipt=ZERO_HASH,
            sequence=1,
            outcome="SUCCEEDED",
            denial_code="NONE",
        )

    def prepared(self, root: Path, *, content: bytes = b"before"):
        target = root / "state.txt"
        target.write_bytes(content)
        pre = filesystem_state_commitment(allowed_root=root, target=target)
        transition = self.transition(pre_state_commitment=pre)
        adapter = FilesystemEffectAdapter(allowed_root=root)
        handle = adapter.prepare_observation(transition=transition, target=target)
        execution = self.execution(transition)
        return target, transition, adapter, handle, execution

    def test_authorization_artifact_still_not_effect_evidence(self):
        transition = self.transition(pre_state_commitment=HASHES[15])
        self.assertFalse(accept_effect_evidence(self.decision(transition)))

    def test_legacy_succeeded_receipt_still_not_effect_evidence(self):
        receipt = self.legacy_receipt()
        self.assertEqual(receipt.outcome, "SUCCEEDED")
        self.assertFalse(accept_effect_evidence(receipt))

    def test_direct_effect_receipt_construction_still_forbidden(self):
        with self.assertRaises(TypeError):
            EffectReceipt(
                receipt_kind=EFFECT_RECEIPT_KIND,
                transition_id=HASHES[1],
                execution_instance_id="exec-forged",
                effect_witness_digest=HASHES[2],
                pre_state_commitment=HASHES[3],
                post_state_commitment=HASHES[4],
                observation_provenance=HASHES[5],
                adapter_identity="forged.adapter",
                adapter_version="1.0.0",
            )

    def test_caller_post_state_digest_has_no_effect_authority(self):
        signature = inspect.signature(FilesystemEffectAdapter.observe_effect)
        self.assertNotIn("post_state_digest", signature.parameters)
        self.assertNotIn("post_state_commitment", signature.parameters)

    def test_prepare_observation_rejects_pre_state_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "state.txt"
            target.write_text("actual", encoding="utf-8")
            transition = self.transition(pre_state_commitment=HASHES[20])
            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_PRE_STATE_COMMITMENT_MISMATCH"):
                FilesystemEffectAdapter(allowed_root=root).prepare_observation(transition=transition, target=target)

    def test_prepare_observation_rejects_target_escape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            outside = Path(other) / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            transition = self.transition(pre_state_commitment=HASHES[20])
            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT"):
                FilesystemEffectAdapter(allowed_root=root).prepare_observation(transition=transition, target=outside)

    def test_prepare_observation_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            outside = Path(other) / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            transition = self.transition(pre_state_commitment=HASHES[20])
            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT"):
                FilesystemEffectAdapter(allowed_root=root).prepare_observation(transition=transition, target=link)

    def test_effect_observation_binds_transition_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, transition, adapter, handle, execution = self.prepared(Path(tmp))
            target.write_text("after", encoding="utf-8")
            other = replace(transition, deterministic_nonce="nonce-pr2-other")
            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_TRANSITION_BINDING_MISMATCH"):
                adapter.observe_effect(transition=other, handle=handle, execution_receipt=execution)

    def test_effect_observation_binds_execution_instance_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, transition, adapter, handle, _ = self.prepared(Path(tmp))
            target.write_text("after", encoding="utf-8")
            execution = self.execution(transition, execution_instance_id="exec-pr2-bound")
            witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
            self.assertEqual(witness.execution_instance_id, "exec-pr2-bound")

    def test_cross_transition_execution_receipt_splicing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, transition, adapter, handle, _ = self.prepared(Path(tmp))
            target.write_text("after", encoding="utf-8")
            other = replace(transition, deterministic_nonce="nonce-pr2-splice")
            wrong_execution = self.execution(other)
            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_EXECUTION_TRANSITION_MISMATCH"):
                adapter.observe_effect(transition=transition, handle=handle, execution_receipt=wrong_execution)

    def test_cross_target_observation_splicing_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, transition, adapter, handle, execution = self.prepared(root)
            other_target = root / "other.txt"
            other_target.write_text("before", encoding="utf-8")
            forged = replace(handle, target_identity="other.txt")
            target.write_text("after", encoding="utf-8")
            with self.assertRaisesRegex(EffectAdapterError, "EFFECT_OBSERVATION_HANDLE_MISMATCH"):
                adapter.observe_effect(transition=transition, handle=forged, execution_receipt=execution)

    def test_post_state_is_derived_from_fresh_filesystem_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target, transition, adapter, handle, execution = self.prepared(root)
            target.write_bytes(b"world-after")
            expected = filesystem_state_commitment(allowed_root=root, target=target)
            witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
            self.assertEqual(witness.observed_post_state_commitment, expected)

    def test_no_effect_produces_evidence_with_effect_changed_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, transition, adapter, handle, execution = self.prepared(Path(tmp))
            witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
            self.assertFalse(witness.effect_changed)
            self.assertTrue(is_adapter_bound_effect_evidence(witness=witness))
            self.assertFalse(accept_effect_evidence(witness))

    def test_real_effect_produces_distinct_observed_post_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            target, transition, adapter, handle, _ = self.prepared(Path(tmp))
            execution = self.execution(transition, outcome=EXECUTION_FAILED)
            target.write_text("changed-after-failed-execution", encoding="utf-8")
            witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
            self.assertEqual(execution.outcome, EXECUTION_FAILED)
            self.assertTrue(witness.effect_changed)
            self.assertNotEqual(witness.observed_pre_state_commitment, witness.observed_post_state_commitment)
            self.assertEqual(witness.execution_instance_id, execution.execution_instance_id)

    def test_observation_does_not_produce_effect_receipt_and_policy_is_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, transition, adapter, handle, execution = self.prepared(Path(tmp))
            witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
            self.assertIsInstance(witness, EffectWitness)
            self.assertFalse(isinstance(witness, tuple))
            receipts_module = sys.modules["harness.sdk.transition_receipts"]
            self.assertFalse(hasattr(receipts_module, "_issue_adapter_bound_effect_receipt"))
            self.assertFalse(hasattr(receipts_module, "_EFFECT_RECEIPT_PRODUCER_CAPABILITY"))
            self.assertEqual(PR1_VERIFIER_POLICY["effect_receipt_production"], "UNAVAILABLE")
            self.assertEqual(PR2_VERIFIER_POLICY["effect_evidence_production"], "ADAPTER_BOUND_ONLY")
            self.assertEqual(PR2_VERIFIER_POLICY["verify_effect"], "NOT_IMPLEMENTED")
            self.assertEqual(PR2_VERIFIER_POLICY["effect_receipt_production"], "UNAVAILABLE")
            self.assertEqual(PR2_VERIFIER_POLICY["complete_verification"], "UNAVAILABLE")
            self.assertEqual(PR2_VERIFIER_POLICY["atomic_admission"], "UNAVAILABLE")
            self.assertNotEqual(verifier_policy_commitment(), pr1_verifier_policy_commitment())
            built = build_transition_identity(
                source_commit=COMMIT,
                pre_state_commitment=HASHES[0],
                identity_root=HASHES[1],
                approval=None,
                requested_capability="filesystem.write",
                registry_root=HASHES[2],
                action_digest=HASHES[4],
                deterministic_nonce="nonce-pr2-policy-bound",
                fence_token="fence-pr2-1",
            )
            self.assertEqual(built.verifier_policy_commitment, verifier_policy_commitment())

    def test_effect_witness_exists_does_not_imply_verified_or_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, transition, adapter, handle, execution = self.prepared(Path(tmp))
            witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
            self.assertTrue(is_adapter_bound_effect_evidence(witness=witness))
            self.assertFalse(accept_effect_evidence(witness))
            self.assertFalse(hasattr(witness, "verified"))
            self.assertFalse(hasattr(witness, "admitted"))
            self.assertFalse(hasattr(witness, "receipt_kind"))

    def test_missing_effect_receipt_still_has_no_legacy_fallback(self):
        transition = self.transition(pre_state_commitment=HASHES[15])
        self.assertFalse(accept_effect_evidence(None))
        self.assertFalse(accept_effect_evidence(self.legacy_receipt()))
        self.assertFalse(accept_effect_evidence(self.decision(transition)))
        self.assertFalse(accept_effect_evidence(self.execution(transition, outcome=EXECUTION_FAILED)))


if __name__ == "__main__":
    main()
