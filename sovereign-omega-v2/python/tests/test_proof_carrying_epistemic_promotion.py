from __future__ import annotations

import unittest

from epistemic_authority_conservation import AuthorityLevel
from no_free_epistemic_gain import (
    EpistemicStateV1,
    conservative_meet,
)
from proof_carrying_epistemic_promotion import (
    PromotionReceiptV1,
    evaluate_promotion,
    promotion_obligations,
    state_sha256,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


class Store:
    def __init__(self, *receipts):
        self.items = {
            receipt.receipt_sha256: receipt
            for receipt in receipts
        }

    def fetch_verified(self, receipt_sha256):
        return self.items.get(receipt_sha256)


def state(claims, authority, uncertainty):
    return EpistemicStateV1(
        frozenset(claims),
        authority,
        uncertainty,
    )


def receipt(obligation, left, right, candidate):
    return PromotionReceiptV1(
        obligation_id=obligation,
        left_state_sha256=state_sha256(left),
        right_state_sha256=state_sha256(right),
        candidate_state_sha256=state_sha256(candidate),
        evidence_sha256=H1,
        verifier_root=H2,
        policy_root=H3,
    )


class ProofCarryingEpistemicPromotionTests(unittest.TestCase):
    def setUp(self):
        self.left = state(
            {"A", "B"},
            AuthorityLevel.EXECUTION,
            1000,
        )
        self.right = state(
            {"A", "C"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        self.meet = conservative_meet(self.left, self.right)

    def test_exact_meet_needs_no_receipt(self):
        result = evaluate_promotion(
            self.left,
            self.right,
            self.meet,
            (),
            store=Store(),
        )
        self.assertEqual(
            result.decision,
            "PASS_CANONICAL_CONSERVATIVE",
        )
        self.assertFalse(result.automatic_promotion)

    def test_strictly_weaker_candidate_is_safe_but_noncanonical(self):
        candidate = state(
            set(),
            AuthorityLevel.NONE,
            5000,
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (),
            store=Store(),
        )
        self.assertEqual(
            result.decision,
            "PASS_CONSERVATIVE_NONCANONICAL",
        )

    def test_claim_gain_without_receipt_denies(self):
        candidate = state(
            {"A", "B"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        self.assertEqual(
            promotion_obligations(
                self.left, self.right, candidate
            ),
            ("CLAIM_GAIN::B",),
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (),
            store=Store(),
        )
        self.assertEqual(result.decision, "DENY")
        self.assertIn(
            "MISSING_PROMOTION_OBLIGATION",
            result.reason_codes,
        )

    def test_exact_claim_gain_receipt_yields_eligibility_only(self):
        candidate = state(
            {"A", "B"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        r = receipt(
            "CLAIM_GAIN::B",
            self.left,
            self.right,
            candidate,
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (r.receipt_sha256,),
            store=Store(r),
        )
        self.assertEqual(
            result.decision,
            "ELIGIBLE_FOR_SEPARATE_PROMOTION_ONLY",
        )
        self.assertFalse(result.automatic_promotion)
        self.assertEqual(result.authority_effect, "NONE")

    def test_authority_gain_requires_separate_receipt(self):
        candidate = state(
            {"A"},
            AuthorityLevel.EXECUTION,
            3000,
        )
        required = promotion_obligations(
            self.left,
            self.right,
            candidate,
        )
        self.assertEqual(
            required,
            ("AUTHORITY_GAIN::EPISTEMIC->EXECUTION",),
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (),
            store=Store(),
        )
        self.assertEqual(result.decision, "DENY")

    def test_uncertainty_reduction_requires_separate_receipt(self):
        candidate = state(
            {"A"},
            AuthorityLevel.EPISTEMIC,
            2000,
        )
        required = promotion_obligations(
            self.left,
            self.right,
            candidate,
        )
        self.assertEqual(
            required,
            ("UNCERTAINTY_REDUCTION::3000->2000",),
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (),
            store=Store(),
        )
        self.assertEqual(result.decision, "DENY")

    def test_all_three_gains_require_complete_exact_coverage(self):
        candidate = state(
            {"A", "B"},
            AuthorityLevel.EXECUTION,
            2000,
        )
        obligations = promotion_obligations(
            self.left,
            self.right,
            candidate,
        )
        self.assertEqual(
            set(obligations),
            {
                "CLAIM_GAIN::B",
                "AUTHORITY_GAIN::EPISTEMIC->EXECUTION",
                "UNCERTAINTY_REDUCTION::3000->2000",
            },
        )
        receipts = tuple(
            receipt(
                obligation,
                self.left,
                self.right,
                candidate,
            )
            for obligation in obligations
        )
        incomplete = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            tuple(r.receipt_sha256 for r in receipts[:-1]),
            store=Store(*receipts),
        )
        self.assertEqual(incomplete.decision, "DENY")

        complete = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            tuple(r.receipt_sha256 for r in receipts),
            store=Store(*receipts),
        )
        self.assertEqual(
            complete.decision,
            "ELIGIBLE_FOR_SEPARATE_PROMOTION_ONLY",
        )

    def test_untrusted_receipt_denies(self):
        candidate = state(
            {"A", "B"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        r = receipt(
            "CLAIM_GAIN::B",
            self.left,
            self.right,
            candidate,
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (r.receipt_sha256,),
            store=Store(),
        )
        self.assertEqual(result.decision, "DENY")
        self.assertIn("UNTRUSTED_RECEIPT", result.reason_codes)

    def test_duplicate_obligation_with_distinct_roots_denies(self):
        candidate = state(
            {"A", "B"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        r1 = receipt(
            "CLAIM_GAIN::B",
            self.left,
            self.right,
            candidate,
        )
        r2 = PromotionReceiptV1(
            obligation_id="CLAIM_GAIN::B",
            left_state_sha256=state_sha256(self.left),
            right_state_sha256=state_sha256(self.right),
            candidate_state_sha256=state_sha256(candidate),
            evidence_sha256="4" * 64,
            verifier_root=H2,
            policy_root=H3,
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (r1.receipt_sha256, r2.receipt_sha256),
            store=Store(r1, r2),
        )
        self.assertEqual(result.decision, "DENY")
        self.assertIn("DUPLICATE_OBLIGATION", result.reason_codes)

    def test_spliced_receipt_denies(self):
        candidate = state(
            {"A", "B"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        other_candidate = state(
            {"A", "C"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        r = receipt(
            "CLAIM_GAIN::B",
            self.left,
            self.right,
            other_candidate,
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            candidate,
            (r.receipt_sha256,),
            store=Store(r),
        )
        self.assertEqual(result.decision, "DENY")
        self.assertIn(
            "RECEIPT_STATE_BINDING_MISMATCH",
            result.reason_codes,
        )

    def test_extra_receipt_denies(self):
        r = receipt(
            "CLAIM_GAIN::B",
            self.left,
            self.right,
            self.meet,
        )
        result = evaluate_promotion(
            self.left,
            self.right,
            self.meet,
            (r.receipt_sha256,),
            store=Store(r),
        )
        self.assertEqual(result.decision, "DENY")


if __name__ == "__main__":
    unittest.main()
