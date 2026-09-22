from __future__ import annotations

import unittest

from statistical_godel_machine import (
    DENY, PASS, FormalEvidenceV1, RewriteClass, RewriteProposalV1,
    StatisticalEvidenceV1, evaluate_rewrite,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64

class StatisticalGodelMachineTests(unittest.TestCase):
    def proposal(self, rewrite_class=RewriteClass.STATISTICAL, **kw):
        values = {
            "proposal_id": "sgm-proposal-1",
            "parent_state_sha256": H1,
            "target_surface": "MODEL_SELECTOR",
            "rewrite_class": rewrite_class,
            "utility_lcb_microunits": 25,
            "semantic_lineage_receipt_sha256": H2,
        }
        values.update(kw)
        return RewriteProposalV1(**values)

    def test_statistical_positive_control_is_operator_eligibility_only(self):
        proposal = self.proposal()
        evidence = StatisticalEvidenceV1(
            metric_id="heldout-loss-improvement", sample_count=200,
            lower_confidence_bound_microunits=25, bounded_metric=True,
            independent_verifier=True, risk_budget_receipt_sha256=H3,
        )
        result = evaluate_rewrite(proposal, evidence)
        self.assertEqual(result.decision, PASS)
        self.assertFalse(result.automatic_rewrite)
        self.assertFalse(result.global_optimality_claimed)
        self.assertEqual(result.authority_effect, "NONE")

    def test_positive_point_estimate_without_positive_lcb_denies(self):
        proposal = self.proposal(utility_lcb_microunits=0)
        evidence = StatisticalEvidenceV1(
            metric_id="heldout-loss-improvement", sample_count=200,
            lower_confidence_bound_microunits=0, bounded_metric=True,
            independent_verifier=True, risk_budget_receipt_sha256=H3,
        )
        result = evaluate_rewrite(proposal, evidence)
        self.assertEqual(result.decision, DENY)
        self.assertIn("NONPOSITIVE_UTILITY_LOWER_BOUND", result.reason_codes)

    def test_small_sample_denies(self):
        proposal = self.proposal()
        evidence = StatisticalEvidenceV1(
            metric_id="heldout-loss-improvement", sample_count=99,
            lower_confidence_bound_microunits=25, bounded_metric=True,
            independent_verifier=True, risk_budget_receipt_sha256=H3,
        )
        result = evaluate_rewrite(proposal, evidence)
        self.assertEqual(result.decision, DENY)
        self.assertIn("INSUFFICIENT_SAMPLE_COUNT", result.reason_codes)

    def test_protected_surface_denies(self):
        proposal = self.proposal(target_surface="AUTHORITY_POLICY")
        evidence = StatisticalEvidenceV1(
            metric_id="heldout-loss-improvement", sample_count=200,
            lower_confidence_bound_microunits=25, bounded_metric=True,
            independent_verifier=True, risk_budget_receipt_sha256=H3,
        )
        result = evaluate_rewrite(proposal, evidence)
        self.assertEqual(result.decision, DENY)
        self.assertIn("PROTECTED_SURFACE", result.reason_codes)

    def test_formal_rewrite_requires_kernel_and_axiom_audit(self):
        proposal = self.proposal(rewrite_class=RewriteClass.FORMAL, utility_lcb_microunits=1)
        bad = FormalEvidenceV1(H2, H3, False, False, False)
        result = evaluate_rewrite(proposal, bad)
        self.assertEqual(result.decision, DENY)
        self.assertIn("KERNEL_NOT_VERIFIED", result.reason_codes)
        good = FormalEvidenceV1(H2, H3, True, True, False)
        result = evaluate_rewrite(proposal, good)
        self.assertEqual(result.decision, PASS)
        self.assertFalse(result.automatic_rewrite)

    def test_evidence_class_cannot_silently_coerce(self):
        proposal = self.proposal(rewrite_class=RewriteClass.FORMAL)
        statistical = StatisticalEvidenceV1(
            metric_id="heldout-loss-improvement", sample_count=200,
            lower_confidence_bound_microunits=25, bounded_metric=True,
            independent_verifier=True, risk_budget_receipt_sha256=H3,
        )
        result = evaluate_rewrite(proposal, statistical)
        self.assertEqual(result.decision, DENY)
        self.assertIn("EVIDENCE_CLASS_MISMATCH", result.reason_codes)

if __name__ == "__main__":
    unittest.main()
