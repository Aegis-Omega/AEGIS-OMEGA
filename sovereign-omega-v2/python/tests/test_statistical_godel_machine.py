from __future__ import annotations

import unittest

from epistemic_conservation_kernel import EpistemicConservationReceiptV1
from statistical_godel_machine import (
    DENY,
    PASS,
    FormalEvidenceV1,
    RewriteClass,
    RewriteProposalV1,
    StatisticalEvidenceV1,
    evaluate_rewrite,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64


class ConservationStore:
    def __init__(self, *receipts):
        self.items = {item.receipt_sha256: item for item in receipts}

    def fetch_verified(self, receipt_sha256):
        return self.items.get(receipt_sha256)


def conservation_receipt(
    *,
    parent=H1,
    lineage=H2,
):
    return EpistemicConservationReceiptV1(
        parent_state_sha256=parent,
        semantic_lineage_receipt_sha256=lineage,
        authority_final="NONE",
        authority_global_meet="NONE",
        authority_non_amplifying=True,
        semantic_accounting_pass=True,
        uncertainty_accounting_pass=True,
        reason_codes=(),
        decision="PASS",
    )


class StatisticalGodelMachineTests(unittest.TestCase):
    def setUp(self):
        self.conservation = conservation_receipt()
        self.store = ConservationStore(self.conservation)

    def proposal(self, rewrite_class=RewriteClass.STATISTICAL, **kw):
        values = {
            "proposal_id": "sgm-proposal-1",
            "parent_state_sha256": H1,
            "target_surface": "MODEL_SELECTOR",
            "rewrite_class": rewrite_class,
            "utility_lcb_microunits": 25,
            "semantic_lineage_receipt_sha256": H2,
            "conservation_receipt_sha256": self.conservation.receipt_sha256,
        }
        values.update(kw)
        return RewriteProposalV1(**values)

    def evaluate(self, proposal, evidence, store=None):
        return evaluate_rewrite(
            proposal,
            evidence,
            conservation_store=self.store if store is None else store,
        )

    def statistical_evidence(self, **kw):
        values = {
            "metric_id": "heldout-loss-improvement",
            "sample_count": 200,
            "lower_confidence_bound_microunits": 25,
            "bounded_metric": True,
            "independent_verifier": True,
            "risk_budget_receipt_sha256": H3,
        }
        values.update(kw)
        return StatisticalEvidenceV1(**values)

    def test_statistical_positive_control_is_operator_eligibility_only(self):
        result = self.evaluate(
            self.proposal(),
            self.statistical_evidence(),
        )
        self.assertEqual(result.decision, PASS)
        self.assertFalse(result.automatic_rewrite)
        self.assertFalse(result.global_optimality_claimed)
        self.assertEqual(result.authority_effect, "NONE")

    def test_untrusted_conservation_receipt_denies(self):
        result = self.evaluate(
            self.proposal(),
            self.statistical_evidence(),
            store=ConservationStore(),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn(
            "CONSERVATION_RECEIPT_UNTRUSTED",
            result.reason_codes,
        )

    def test_spliced_parent_conservation_receipt_denies(self):
        other = conservation_receipt(parent="9" * 64)
        proposal = self.proposal(
            conservation_receipt_sha256=other.receipt_sha256
        )
        result = self.evaluate(
            proposal,
            self.statistical_evidence(),
            store=ConservationStore(other),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn(
            "CONSERVATION_PARENT_STATE_MISMATCH",
            result.reason_codes,
        )

    def test_spliced_lineage_conservation_receipt_denies(self):
        other = conservation_receipt(lineage="8" * 64)
        proposal = self.proposal(
            conservation_receipt_sha256=other.receipt_sha256
        )
        result = self.evaluate(
            proposal,
            self.statistical_evidence(),
            store=ConservationStore(other),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn(
            "CONSERVATION_LINEAGE_MISMATCH",
            result.reason_codes,
        )

    def test_positive_point_estimate_without_positive_lcb_denies(self):
        result = self.evaluate(
            self.proposal(utility_lcb_microunits=0),
            self.statistical_evidence(
                lower_confidence_bound_microunits=0
            ),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn(
            "NONPOSITIVE_UTILITY_LOWER_BOUND",
            result.reason_codes,
        )

    def test_small_sample_denies(self):
        result = self.evaluate(
            self.proposal(),
            self.statistical_evidence(sample_count=99),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn("INSUFFICIENT_SAMPLE_COUNT", result.reason_codes)

    def test_protected_surface_denies(self):
        result = self.evaluate(
            self.proposal(target_surface="AUTHORITY_POLICY"),
            self.statistical_evidence(),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn("PROTECTED_SURFACE", result.reason_codes)

    def test_formal_rewrite_requires_kernel_and_axiom_audit(self):
        proposal = self.proposal(
            rewrite_class=RewriteClass.FORMAL,
            utility_lcb_microunits=1,
        )
        bad = FormalEvidenceV1(H2, H3, False, False, False)
        result = self.evaluate(proposal, bad)
        self.assertEqual(result.decision, DENY)
        self.assertIn("KERNEL_NOT_VERIFIED", result.reason_codes)

        good = FormalEvidenceV1(H2, H3, True, True, False)
        result = self.evaluate(proposal, good)
        self.assertEqual(result.decision, PASS)
        self.assertFalse(result.automatic_rewrite)

    def test_evidence_class_cannot_silently_coerce(self):
        proposal = self.proposal(rewrite_class=RewriteClass.FORMAL)
        result = self.evaluate(
            proposal,
            self.statistical_evidence(),
        )
        self.assertEqual(result.decision, DENY)
        self.assertIn("EVIDENCE_CLASS_MISMATCH", result.reason_codes)


if __name__ == "__main__":
    unittest.main()
