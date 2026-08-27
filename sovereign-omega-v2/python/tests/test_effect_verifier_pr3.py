#!/usr/bin/env python3
"""PR-3 falsification suite: VerifyEffect gates nominal EffectReceipt issuance."""
from __future__ import annotations

import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.effect_adapters import FilesystemEffectAdapter, filesystem_state_commitment  # noqa: E402
from harness.sdk.effect_verifier import (  # noqa: E402
    FALSE,
    MISSING,
    TRUE,
    UNKNOWN,
    EffectVerificationError,
    EffectVerifier,
)
from harness.sdk.sovereign_execution import SCHEMA_VERSION  # noqa: E402
from harness.sdk.transition_receipts import (  # noqa: E402
    EFFECT_RECEIPT_KIND,
    EXECUTION_FAILED,
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    accept_effect_evidence,
    pr2_verifier_policy_commitment,
    verifier_policy_commitment,
)

HASHES = [f"{i:064x}" for i in range(1, 64)]
COMMIT = "b" * 40


class EffectVerifierPR3Tests(TestCase):
    def transition(self, *, pre: str, policy: str | None = None, nonce: str = "nonce-pr3") -> TransitionIdentity:
        return TransitionIdentity(
            schema_version=SCHEMA_VERSION,
            source_commit=COMMIT,
            pre_state_commitment=pre,
            identity_root=HASHES[1],
            delegation_commitment=HASHES[2],
            capability_commitment=HASHES[3],
            action_digest=HASHES[4],
            deterministic_nonce=nonce,
            fence_commitment=HASHES[5],
            verifier_policy_commitment=policy or verifier_policy_commitment(),
            admission_policy_commitment=HASHES[6],
        )

    def execution(self, transition: TransitionIdentity, *, instance: str = "exec-pr3", outcome: str = EXECUTION_SUCCEEDED) -> ExecutionReceipt:
        return ExecutionReceipt(
            receipt_kind=EXECUTION_RECEIPT_KIND,
            transition_id=transition.root,
            execution_instance_id=instance,
            outcome=outcome,
            result_digest=HASHES[7],
        )

    def observed(self, *, change: bool = True, outcome: str = EXECUTION_SUCCEEDED, policy: str | None = None):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        target = root / "state.txt"
        target.write_bytes(b"before")
        pre = filesystem_state_commitment(allowed_root=root, target=target)
        transition = self.transition(pre=pre, policy=policy)
        adapter = FilesystemEffectAdapter(allowed_root=root)
        handle = adapter.prepare_observation(transition=transition, target=target)
        execution = self.execution(transition, outcome=outcome)
        if change:
            target.write_bytes(b"after")
        witness = adapter.observe_effect(transition=transition, handle=handle, execution_receipt=execution)
        return tmp, transition, execution, witness

    def test_missing_effect_evidence_is_missing_and_cannot_issue_receipt(self):
        transition = self.transition(pre=HASHES[10])
        execution = self.execution(transition)
        verifier = EffectVerifier()
        result = verifier.verify_effect(transition=transition, execution_receipt=execution, witness=None)
        self.assertEqual(result.status, MISSING)
        with self.assertRaisesRegex(EffectVerificationError, "EFFECT_VERIFICATION_NOT_TRUE"):
            verifier.issue_effect_receipt(transition=transition, execution_receipt=execution, witness=None, verification=result)

    def test_malformed_effect_evidence_is_false(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        malformed = replace(witness, observed_post_state_commitment="not-a-hash")
        result = EffectVerifier().verify_effect(transition=transition, execution_receipt=execution, witness=malformed)
        self.assertEqual(result.status, FALSE)

    def test_unknown_adapter_is_unknown_not_true(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        unknown = replace(witness, adapter_identity="unknown.adapter")
        result = EffectVerifier().verify_effect(transition=transition, execution_receipt=execution, witness=unknown)
        self.assertEqual(result.status, UNKNOWN)

    def test_cross_transition_witness_binding_fails(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        other = replace(transition, deterministic_nonce="nonce-pr3-other")
        result = EffectVerifier().verify_effect(transition=other, execution_receipt=execution, witness=witness)
        self.assertEqual(result.status, FALSE)

    def test_execution_transition_binding_fails(self):
        tmp, transition, _, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        other = replace(transition, deterministic_nonce="nonce-pr3-execution-other")
        wrong_execution = self.execution(other)
        result = EffectVerifier().verify_effect(transition=transition, execution_receipt=wrong_execution, witness=witness)
        self.assertEqual(result.status, FALSE)

    def test_execution_instance_binding_fails(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        spliced = replace(witness, execution_instance_id="exec-pr3-spliced")
        result = EffectVerifier().verify_effect(transition=transition, execution_receipt=execution, witness=spliced)
        self.assertEqual(result.status, FALSE)

    def test_prestate_binding_fails(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        spliced = replace(witness, observed_pre_state_commitment=HASHES[20])
        result = EffectVerifier().verify_effect(transition=transition, execution_receipt=execution, witness=spliced)
        self.assertEqual(result.status, FALSE)

    def test_stale_pr2_verifier_policy_is_rejected(self):
        tmp, transition, execution, witness = self.observed(policy=pr2_verifier_policy_commitment())
        self.addCleanup(tmp.cleanup)
        result = EffectVerifier().verify_effect(transition=transition, execution_receipt=execution, witness=witness)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_verifier_policy_binding"], FALSE)

    def test_valid_no_change_evidence_verifies_and_can_issue_receipt(self):
        tmp, transition, execution, witness = self.observed(change=False)
        self.addCleanup(tmp.cleanup)
        verifier = EffectVerifier()
        result = verifier.verify_effect(transition=transition, execution_receipt=execution, witness=witness)
        self.assertEqual(result.status, TRUE)
        self.assertFalse(witness.effect_changed)
        receipt = verifier.issue_effect_receipt(transition=transition, execution_receipt=execution, witness=witness, verification=result)
        self.assertEqual(receipt.receipt_kind, EFFECT_RECEIPT_KIND)
        self.assertEqual(receipt.effect_witness_digest, witness.root)

    def test_failed_execution_can_still_have_verified_observed_effect(self):
        tmp, transition, execution, witness = self.observed(change=True, outcome=EXECUTION_FAILED)
        self.addCleanup(tmp.cleanup)
        verifier = EffectVerifier()
        result = verifier.verify_effect(transition=transition, execution_receipt=execution, witness=witness)
        self.assertEqual(execution.outcome, EXECUTION_FAILED)
        self.assertTrue(witness.effect_changed)
        self.assertEqual(result.status, TRUE)
        receipt = verifier.issue_effect_receipt(transition=transition, execution_receipt=execution, witness=witness, verification=result)
        self.assertEqual(receipt.execution_instance_id, execution.execution_instance_id)

    def test_forged_or_mutated_verification_result_cannot_issue_receipt(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        verifier = EffectVerifier()
        result = verifier.verify_effect(transition=transition, execution_receipt=execution, witness=witness)
        forged = replace(result, verifier_policy_commitment=pr2_verifier_policy_commitment())
        with self.assertRaisesRegex(EffectVerificationError, "EFFECT_VERIFICATION_RECOMPUTE_MISMATCH"):
            verifier.issue_effect_receipt(transition=transition, execution_receipt=execution, witness=witness, verification=forged)

    def test_effect_receipt_binds_verification_root_and_policy_commitment(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        verifier = EffectVerifier()
        result = verifier.verify_effect(transition=transition, execution_receipt=execution, witness=witness)
        receipt = verifier.issue_effect_receipt(transition=transition, execution_receipt=execution, witness=witness, verification=result)
        self.assertEqual(receipt.effect_verification_root, result.root)
        self.assertEqual(receipt.verifier_policy_commitment, verifier_policy_commitment())
        self.assertEqual(receipt.transition_id, transition.root)

    def test_direct_effect_receipt_construction_remains_forbidden(self):
        with self.assertRaises(TypeError):
            EffectReceipt(
                receipt_kind=EFFECT_RECEIPT_KIND,
                transition_id=HASHES[1],
                execution_instance_id="exec-forged",
                effect_witness_digest=HASHES[2],
                effect_verification_root=HASHES[3],
                verifier_policy_commitment=HASHES[4],
                pre_state_commitment=HASHES[5],
                post_state_commitment=HASHES[6],
                observation_provenance=HASHES[7],
                adapter_identity="forged.adapter",
                adapter_version="1.0.0",
            )

    def test_effect_receipt_still_does_not_satisfy_complete_verification(self):
        tmp, transition, execution, witness = self.observed()
        self.addCleanup(tmp.cleanup)
        verifier = EffectVerifier()
        result = verifier.verify_effect(transition=transition, execution_receipt=execution, witness=witness)
        receipt = verifier.issue_effect_receipt(transition=transition, execution_receipt=execution, witness=witness, verification=result)
        self.assertFalse(accept_effect_evidence(receipt))
        self.assertFalse(hasattr(receipt, "admitted"))

    def test_no_generic_effect_receipt_factory_exists(self):
        receipts_module = sys.modules["harness.sdk.transition_receipts"]
        self.assertFalse(hasattr(receipts_module, "make_effect_receipt"))
        self.assertFalse(hasattr(receipts_module, "effect_receipt_from_post_state"))
        self.assertFalse(hasattr(receipts_module, "_issue_adapter_bound_effect_receipt"))


if __name__ == "__main__":
    main()
