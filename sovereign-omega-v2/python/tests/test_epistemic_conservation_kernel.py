from __future__ import annotations

import unittest

from epistemic_accounting import (
    AccountingEnvelopeV1,
    AccountingMode,
    Relation,
)
from epistemic_authority_conservation import (
    AuthorityLevel,
    TransitionGateV1,
)
from epistemic_conservation_kernel import (
    ConservationRequestV1,
    evaluate_conservation,
    trusted_receipt,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


class Store:
    def __init__(self, *receipts):
        self.items = {item.receipt_sha256: item for item in receipts}

    def fetch_verified(self, receipt_sha256):
        return self.items.get(receipt_sha256)


def lossless_envelope():
    return AccountingEnvelopeV1(
        source_claims=frozenset({"A"}),
        target_claims=frozenset({"A"}),
        preserved_source=frozenset({"A"}),
        preserved_target=frozenset({"A"}),
        omissions=frozenset(),
        additions=frozenset(),
        addition_receipts=(),
        relation=Relation.LOSSLESS,
        uncertainty_bps=0,
    )


class EpistemicConservationKernelTests(unittest.TestCase):
    def test_clean_single_step_receipt_passes(self):
        receipt = evaluate_conservation(
            ConservationRequestV1(
                parent_state_sha256=H1,
                semantic_lineage_receipt_sha256=H2,
                initial_authority=AuthorityLevel.PRODUCTION,
                authority_gates=(
                    TransitionGateV1(
                        AuthorityLevel.EPISTEMIC,
                        AuthorityLevel.PRODUCTION,
                    ),
                ),
                accounting_envelope=lossless_envelope(),
                accounting_mode=AccountingMode.SINGLE_STEP,
            )
        )
        self.assertEqual(receipt.decision, "PASS")
        self.assertEqual(receipt.authority_final, "EPISTEMIC")
        self.assertTrue(receipt.authority_non_amplifying)
        self.assertTrue(receipt.semantic_accounting_pass)
        self.assertTrue(receipt.uncertainty_accounting_pass)
        self.assertEqual(receipt.authority_effect, "NONE")

    def test_transitive_uncertainty_mismatch_denies(self):
        env = AccountingEnvelopeV1(
            source_claims=frozenset({"A", "B"}),
            target_claims=frozenset({"A"}),
            preserved_source=frozenset({"A"}),
            preserved_target=frozenset({"A"}),
            omissions=frozenset({"B"}),
            additions=frozenset(),
            addition_receipts=(),
            relation=Relation.LOSSY,
            uncertainty_bps=200,
        )
        receipt = evaluate_conservation(
            ConservationRequestV1(
                parent_state_sha256=H1,
                semantic_lineage_receipt_sha256=H2,
                initial_authority=AuthorityLevel.EPISTEMIC,
                authority_gates=(),
                accounting_envelope=env,
                accounting_mode=AccountingMode.TRANSITIVE_V1,
                left_uncertainty_bps=300,
                right_uncertainty_bps=700,
            )
        )
        self.assertEqual(receipt.decision, "DENY")
        self.assertIn(
            "UNCERTAINTY_COMPOSITION_MISMATCH",
            receipt.reason_codes,
        )

    def test_unaccounted_semantic_addition_denies(self):
        env = AccountingEnvelopeV1(
            source_claims=frozenset({"A"}),
            target_claims=frozenset({"A", "B"}),
            preserved_source=frozenset({"A"}),
            preserved_target=frozenset({"A"}),
            omissions=frozenset(),
            additions=frozenset({"B"}),
            addition_receipts=(),
            relation=Relation.AUGMENTING,
            uncertainty_bps=0,
        )
        receipt = evaluate_conservation(
            ConservationRequestV1(
                parent_state_sha256=H1,
                semantic_lineage_receipt_sha256=H2,
                initial_authority=AuthorityLevel.EPISTEMIC,
                authority_gates=(),
                accounting_envelope=env,
                accounting_mode=AccountingMode.SINGLE_STEP,
            )
        )
        self.assertEqual(receipt.decision, "DENY")
        self.assertFalse(receipt.semantic_accounting_pass)

    def test_trusted_store_rejects_unknown_or_denied_receipt(self):
        good = evaluate_conservation(
            ConservationRequestV1(
                parent_state_sha256=H1,
                semantic_lineage_receipt_sha256=H2,
                initial_authority=AuthorityLevel.EPISTEMIC,
                authority_gates=(),
                accounting_envelope=lossless_envelope(),
                accounting_mode=AccountingMode.SINGLE_STEP,
            )
        )
        store = Store(good)
        self.assertEqual(
            trusted_receipt(store, good.receipt_sha256),
            good,
        )
        self.assertIsNone(trusted_receipt(store, H3))


if __name__ == "__main__":
    unittest.main()
