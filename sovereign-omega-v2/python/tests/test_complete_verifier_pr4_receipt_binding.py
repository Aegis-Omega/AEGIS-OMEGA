#!/usr/bin/env python3
"""PR-4 adversarial receipt-binding falsifiers discovered during security review."""
from __future__ import annotations

import sys
import tempfile
from dataclasses import fields
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.complete_verifier import FALSE, TRUE, CompleteVerifier  # noqa: E402
from harness.sdk.effect_adapters import FilesystemEffectAdapter, filesystem_state_commitment  # noqa: E402
from harness.sdk.effect_verifier import EffectVerifier  # noqa: E402
from harness.sdk.sovereign_execution import SCHEMA_VERSION  # noqa: E402
from harness.sdk.transition_receipts import (  # noqa: E402
    PERMIT,
    DECISION_RECEIPT_KIND,
    EXECUTION_RECEIPT_KIND,
    DecisionReceipt,
    EffectReceipt,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment,
    verifier_policy_commitment,
)

HASHES = [f"{i:064x}" for i in range(100, 160)]
COMMIT = "d" * 40


def forge_effect_receipt(receipt: EffectReceipt, **changes: str) -> EffectReceipt:
    forged = object.__new__(EffectReceipt)
    for field in fields(EffectReceipt):
        object.__setattr__(forged, field.name, changes.get(field.name, getattr(receipt, field.name)))
    return forged


class CompleteVerifierPR4ReceiptBindingTests(TestCase):
    def bundle(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        target = root / "state.txt"
        target.write_bytes(b"before")
        pre = filesystem_state_commitment(allowed_root=root, target=target)
        transition = TransitionIdentity(
            schema_version=SCHEMA_VERSION,
            source_commit=COMMIT,
            pre_state_commitment=pre,
            identity_root=HASHES[1],
            delegation_commitment=HASHES[2],
            capability_commitment=HASHES[3],
            action_digest=HASHES[4],
            deterministic_nonce="nonce-pr4-receipt-binding",
            fence_commitment=HASHES[5],
            verifier_policy_commitment=verifier_policy_commitment(),
            admission_policy_commitment=admission_policy_commitment(),
        )
        decision = DecisionReceipt(
            receipt_kind=DECISION_RECEIPT_KIND,
            transition_id=transition.root,
            decision_outcome=PERMIT,
            policy_decision_root=HASHES[6],
        )
        execution = ExecutionReceipt(
            receipt_kind=EXECUTION_RECEIPT_KIND,
            transition_id=transition.root,
            execution_instance_id="exec-pr4-receipt-binding",
            outcome="SUCCEEDED",
            result_digest=HASHES[7],
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
        verification = effect_verifier.verify_effect(
            transition=transition,
            execution_receipt=execution,
            witness=witness,
        )
        self.assertEqual(verification.status, TRUE)
        receipt = effect_verifier.issue_effect_receipt(
            transition=transition,
            execution_receipt=execution,
            witness=witness,
            verification=verification,
        )
        return tmp, transition, decision, execution, witness, verification, receipt

    def verify(self, bundle, receipt):
        _, transition, decision, execution, witness, verification, _ = bundle
        return CompleteVerifier().verify_complete(
            transition=transition,
            decision_receipt=decision,
            execution_receipt=execution,
            effect_witness=witness,
            effect_verification=verification,
            effect_receipt=receipt,
        )

    def test_forged_post_state_commitment_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], post_state_commitment=HASHES[20])
        result = self.verify(bundle, forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)

    def test_forged_observation_provenance_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], observation_provenance=HASHES[21])
        result = self.verify(bundle, forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)

    def test_forged_adapter_identity_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], adapter_identity="forged.adapter")
        result = self.verify(bundle, forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)

    def test_forged_adapter_version_is_rejected(self):
        bundle = self.bundle()
        self.addCleanup(bundle[0].cleanup)
        forged = forge_effect_receipt(bundle[6], adapter_version="9.9.9")
        result = self.verify(bundle, forged)
        self.assertEqual(result.status, FALSE)
        self.assertEqual(dict(result.obligations)["V_effect_binding"], FALSE)


if __name__ == "__main__":
    main()
