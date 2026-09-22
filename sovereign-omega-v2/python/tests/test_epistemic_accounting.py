from __future__ import annotations

import itertools
import unittest

from epistemic_accounting import (
    AccountingEnvelopeV1,
    AccountingMode,
    Relation,
    composed_uncertainty_bps,
    verify_accounting,
)

R = "a" * 64


def envelope(
    *,
    source=("A",),
    target=("A",),
    preserved_source=("A",),
    preserved_target=("A",),
    omissions=(),
    additions=(),
    receipts=(),
    relation=Relation.LOSSLESS,
    uncertainty=0,
):
    return AccountingEnvelopeV1(
        source_claims=frozenset(source),
        target_claims=frozenset(target),
        preserved_source=frozenset(preserved_source),
        preserved_target=frozenset(preserved_target),
        omissions=frozenset(omissions),
        additions=frozenset(additions),
        addition_receipts=tuple(receipts),
        relation=relation,
        uncertainty_bps=uncertainty,
    )


class EpistemicAccountingTests(unittest.TestCase):
    def test_lossless_exact_partition_passes(self):
        result = verify_accounting(
            envelope(),
            mode=AccountingMode.SINGLE_STEP,
        )
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(result["source_balance"])
        self.assertTrue(result["target_balance"])

    def test_undeclared_loss_denies(self):
        result = verify_accounting(
            envelope(
                source=("A", "B"),
                target=("A",),
                preserved_source=("A",),
                preserved_target=("A",),
            ),
            mode=AccountingMode.SINGLE_STEP,
        )
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("SOURCE_PARTITION_INCOMPLETE", result["reason_codes"])

    def test_unreceipted_addition_denies(self):
        result = verify_accounting(
            envelope(
                source=("A",),
                target=("A", "B"),
                preserved_source=("A",),
                preserved_target=("A",),
                additions=("B",),
                relation=Relation.AUGMENTING,
            ),
            mode=AccountingMode.SINGLE_STEP,
        )
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("ADDITION_RECEIPT_COVERAGE_MISMATCH", result["reason_codes"])

    def test_receipted_single_step_addition_passes(self):
        result = verify_accounting(
            envelope(
                source=("A",),
                target=("A", "B"),
                preserved_source=("A",),
                preserved_target=("A",),
                additions=("B",),
                receipts=(("B", R),),
                relation=Relation.AUGMENTING,
            ),
            mode=AccountingMode.SINGLE_STEP,
        )
        self.assertEqual(result["decision"], "PASS")

    def test_transitive_v1_final_addition_denies_even_with_receipt(self):
        result = verify_accounting(
            envelope(
                source=("A",),
                target=("A", "B"),
                preserved_source=("A",),
                preserved_target=("A",),
                additions=("B",),
                receipts=(("B", R),),
                relation=Relation.AUGMENTING,
            ),
            mode=AccountingMode.TRANSITIVE_V1,
        )
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("TRANSITIVE_FINAL_ADDITION_UNPROVEN", result["reason_codes"])

    def test_lossy_declared_partition_carries_uncertainty(self):
        result = verify_accounting(
            envelope(
                source=("A", "B"),
                target=("A",),
                preserved_source=("A",),
                preserved_target=("A",),
                omissions=("B",),
                relation=Relation.LOSSY,
                uncertainty=250,
            ),
            mode=AccountingMode.SINGLE_STEP,
        )
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(result["source_balance"])

    def test_composite_source_loss_uncertainty_never_below_predecessors(self):
        grid = (0, 1, 100, 5000, 10000)
        for left, right in itertools.product(grid, repeat=2):
            out = composed_uncertainty_bps(
                has_composite_source_loss=True,
                left_uncertainty_bps=left,
                right_uncertainty_bps=right,
            )
            self.assertGreaterEqual(out, left)
            self.assertGreaterEqual(out, right)
            self.assertEqual(out, max(left, right))

    def test_no_composite_source_loss_resets_loss_uncertainty(self):
        self.assertEqual(
            composed_uncertainty_bps(
                has_composite_source_loss=False,
                left_uncertainty_bps=300,
                right_uncertainty_bps=700,
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
