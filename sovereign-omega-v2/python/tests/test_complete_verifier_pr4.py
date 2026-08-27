#!/usr/bin/env python3
"""PR-4 falsification suite: CompleteVerification closes one exact evidence bundle only."""
from __future__ import annotations

import sys
import tempfile
from dataclasses import fields, replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.complete_verifier import (  # noqa: E402
    FALSE,
    MISSING,
    TRUE,
    CompleteVerifier,
)
from harness.sdk.effect_adapters import FilesystemEffectAdapter, filesystem_state_commitment  # noqa: E402
from harness.sdk.effect_verifier import EffectVerifier  # noqa: E402
from harness.sdk.sovereign_execution import SCHEMA_VERSION  # noqa: E402
from harness.sdk.transition_receipts import (  # noqa: E402
    DEFER,
    DENY,
    PERMIT,
    DECISION_RECEIPT_KIND,
    EFFECT_RECEIPT_KIND,
    EXECUTION_FAILED,
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    DecisionReceipt,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment,
    verifier_policy_commitment,
)

HASHES = [f"{i:064x}" for i in range(1, 96)]
COMMIT = "c" * 40


def forge_effect_receipt(receipt: EffectReceipt, **changes: str) -> EffectReceipt:
    forged = object.__new__(EffectReceipt)
    for field in fields(EffectReceipt):
        object.__setattr__(forged, field.name, changes.get(field.name, getattr(receipt, field.name)))
    return forged


class CompleteVerifierPR4Tests(TestCase):
    def transition(
        self,
        *,
        pre: str,
        nonce: str = "nonce-pr4",
        verifier_policy: str | None = None,
        admission_policy: str | None = None,
    ) -> TransitionIdentity:
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
            verifier_policy_commitment=verifier_policy or verifier_policy_commitment(),
            admission_policy_commitment=admission_policy or admission_policy_commitment(),
        )

    def bundle(
        self,
        *,
        nonce: str = "nonce-pr4",
        decision_outcome: str = PERMIT,
        execution_outcome: str = EXECUTION_SUCCEEDED,
        execution_instance_id: str = "exec-pr4",
        change: bool = True,
        verifier_policy: str | None = None,
        admission_policy: str | None = None,
    ):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        target = root / "state.txt"
        target.write_bytes(b"before")
        pre = filesystem_state_commitment(allowed_root=root, target=target)
        transition = self.transition(
            pre=pre,
            nonce=nonce,
            verifier_policy=verifier_policy,
            admission_policy=admission_policy,
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
            execution_instance_id=execution_instance_id,
            outcome=execution_outcome,
            result_digest=HASHES[9],
        )
        adapter = FilesystemEffectAdapter(allowed_root=root)
        handle = adapter.prepare_observation(transition=transition, target=target)
        if change:
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
        return tmp, transition, decision, execution, witness, effect_verification, effect_receipt

    def verify(self, bundle, **overrides):
        _, transition, decision, execution, witness, effect_verification, effect_receipt = bundle
        values = {
            "transition": transition,
            "decision_receipt": decision,
            "execution_receipt": execution,
            "effect_witness": witness,
            "effect_verification": effect_verification,
            "effect_receipt": effect_receipt,
        }
        values.update(overrides)
        return CompleteVerifier().verify_complete(**values)

    def test_valid_exact_bundle_is_true(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle)
        self.assertEqual(result.status, TRUE)
        self.assertTrue(all(status == TRUE for _, status in result.obligations))
        self.assertFalse(hasattr(result, "admitted"))

    def test_missing_decision_receipt_is_missing(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(self.verify(bundle, decision_receipt=None).status, MISSING)

    def test_missing_execution_receipt_is_missing(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(self.verify(bundle, execution_receipt=None).status, MISSING)

    def test_missing_effect_witness_is_missing(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(self.verify(bundle, effect_witness=None).status, MISSING)

    def test_missing_effect_verification_is_missing(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(self.verify(bundle, effect_verification=None).status, MISSING)

    def test_missing_effect_receipt_is_missing(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(self.verify(bundle, effect_receipt=None).status, MISSING)

    def test_deny_is_not_complete(self):
        bundle = self.bundle(decision_outcome=DENY)
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_decision_authority"], FALSE)

    def test_defer_is_not_complete(self):
        bundle = self.bundle(decision_outcome=DEFER)
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_decision_authority"], FALSE)

    def test_cross_transition_decision_is_rejected(self):
        left = self.bundle(nonce="nonce-pr4-left")
        right = self.bundle(nonce="nonce-pr4-right")
        self.addCleanup(left[0].cleanup)
        self.addCleanup(right[0].cleanup)
        result = self.verify(left, decision_receipt=right[2])
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_decision_binding"], FALSE)

    def test_cross_transition_execution_is_rejected(self):
        left = self.bundle(nonce="nonce-pr4-left")
        right = self.bundle(nonce="nonce-pr4-right")
        self.addCleanup(left[0].cleanup)
        self.addCleanup(right[0].cleanup)
        result = self.verify(left, execution_receipt=right[3])
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_execution_binding"], FALSE)

    def test_cross_transition_witness_is_rejected(self):
        left = self.bundle(nonce="nonce-pr4-left")
        right = self.bundle(nonce="nonce-pr4-right")
        self.addCleanup(left[0].cleanup)
        self.addCleanup(right[0].cleanup)
        result = self.verify(left, effect_witness=right[4])
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_evidence"], FALSE)

    def test_cross_transition_effect_receipt_is_rejected(self):
        left = self.bundle(nonce="nonce-pr4-left")
        right = self.bundle(nonce="nonce-pr4-right")
        self.addCleanup(left[0].cleanup)
        self.addCleanup(right[0].cleanup)
        result = self.verify(left, effect_receipt=right[6])
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)

    def test_execution_instance_splice_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], execution_instance_id="exec-pr4-spliced")
        result = self.verify(bundle, effect_receipt=forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)

    def test_forged_effect_verification_result_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = replace(bundle[5], denial_code="FORGED")
        result = self.verify(bundle, effect_verification=forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_verification_binding"], FALSE)

    def test_forged_effect_verification_root_in_receipt_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], effect_verification_root=HASHES[40])
        result = self.verify(bundle, effect_receipt=forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_verification_binding"], FALSE)

    def test_forged_effect_witness_digest_in_receipt_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], effect_witness_digest=HASHES[41])
        result = self.verify(bundle, effect_receipt=forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)

    def test_verifier_policy_mismatch_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], verifier_policy_commitment=HASHES[42])
        result = self.verify(bundle, effect_receipt=forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_verifier_policy_binding"], FALSE)

    def test_admission_policy_mismatch_is_rejected(self):
        bundle = self.bundle(admission_policy=HASHES[43])
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_admission_policy_binding"], FALSE)

    def test_wrong_nominal_type_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle, decision_receipt=object())
        self.assertEqual(result.status, FALSE)
        self.assertEqual(result.denial_code, "COMPLETE_VERIFICATION_INPUT_ERROR")

    def test_raw_effect_witness_cannot_substitute_for_effect_receipt(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle, effect_receipt=bundle[4])
        self.assertEqual(result.status, FALSE)
        self.assertEqual(result.denial_code, "COMPLETE_VERIFICATION_INPUT_ERROR")

    def test_succeeded_execution_without_effect_lineage_is_not_complete(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(bundle[3].outcome, EXECUTION_SUCCEEDED)
        result = self.verify(bundle, effect_witness=None, effect_verification=None, effect_receipt=None)
        self.assertEqual(result.status, MISSING)

    def test_failed_execution_with_verified_effect_is_evidence_driven(self):
        bundle = self.bundle(execution_outcome=EXECUTION_FAILED, change=True)
        self.addCleanup(bundle[0].cleanup)
        self.assertEqual(bundle[3].outcome, EXECUTION_FAILED)
        self.assertTrue(bundle[4].effect_changed)
        self.assertEqual(self.verify(bundle).status, TRUE)

    def test_no_change_effect_can_complete_when_verified(self):
        bundle = self.bundle(change=False)
        self.addCleanup(bundle[0].cleanup)
        self.assertFalse(bundle[4].effect_changed)
        self.assertEqual(self.verify(bundle).status, TRUE)

    def test_result_root_is_deterministic(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        first = self.verify(bundle)
        second = self.verify(bundle)
        self.assertEqual(first.root, second.root)

    def test_complete_result_hash_domain_is_separate_from_receipts(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        result = self.verify(bundle)
        self.assertEqual(bundle[6].receipt_kind, EFFECT_RECEIPT_KIND)
        self.assertNotIn(result.root, {bundle[2].root, bundle[3].root, bundle[6].root})


if __name__ == "__main__":
    main()
