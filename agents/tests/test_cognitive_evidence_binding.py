from __future__ import annotations

import asyncio
import unittest

from agents.cognitive_pipeline import KanInferenceLog, constitutional_scorer
from agents.cognitive_pipeline_auditbound import EvidenceBinding, arbitrate, run_pipeline


DIGEST = "a" * 64


class CognitiveEvidenceBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = constitutional_scorer()
        self.log = KanInferenceLog()

    def test_t0_wording_without_external_evidence_is_demoted_to_unverified_t3(self):
        verdict = arbitrate(
            "deterministic SHA-256 hash chain mechanically proven",
            self.scorer,
            self.log,
        )
        self.assertEqual(verdict["requested_tier"], "T0")
        self.assertEqual(verdict["tier"], "T3")
        self.assertFalse(verdict["admitted"])
        self.assertEqual(verdict["evidence_status"], "UNVERIFIED")

    def test_t1_wording_without_external_evidence_is_demoted_to_unverified_t3(self):
        verdict = arbitrate(
            "empirically validated benchmark measurement observed across runs",
            self.scorer,
            self.log,
        )
        self.assertEqual(verdict["requested_tier"], "T1")
        self.assertEqual(verdict["tier"], "T3")
        self.assertFalse(verdict["admitted"])
        self.assertEqual(verdict["evidence_status"], "UNVERIFIED")

    def test_bound_t0_evidence_allows_t0_classification_subject_to_score(self):
        verdict = arbitrate(
            "deterministic SHA-256 hash chain mechanically proven",
            self.scorer,
            self.log,
            evidence=EvidenceBinding(
                evidence_tier="T0",
                source="exact-head-execution-receipt",
                reference="receipt://run/42",
                artifact_digest=DIGEST,
            ),
        )
        self.assertEqual(verdict["tier"], "T0")
        self.assertEqual(verdict["evidence_status"], "BOUND")
        self.assertTrue(verdict["admitted"])

    def test_t1_claim_accepts_stronger_t0_bound_evidence(self):
        verdict = arbitrate(
            "empirically validated benchmark measurement observed across runs",
            self.scorer,
            self.log,
            evidence=EvidenceBinding(
                evidence_tier="T0",
                source="deterministic-verifier",
                reference="artifact://benchmark/7",
                artifact_digest=DIGEST,
            ),
        )
        self.assertEqual(verdict["tier"], "T1")
        self.assertEqual(verdict["evidence_status"], "BOUND")

    def test_hash_scope_is_local_scoring_integrity_not_truth_proof(self):
        verdict = arbitrate(
            "engineering hypothesis proposed LUT-KAN seam",
            self.scorer,
            self.log,
        )
        self.assertEqual(verdict["hash_scope"], "LOCAL_SCORING_LOG_INTEGRITY_ONLY")
        self.assertFalse(verdict["hash_proves_claim_truth"])

    def test_offline_pipeline_with_no_claims_emits_no_fabricated_research(self):
        result = asyncio.run(run_pipeline("frontier routing", live=False))
        self.assertEqual(result.arbitration, [])
        self.assertEqual(result.admitted, [])
        self.assertEqual(result.quarantined, [])
        self.assertIn("no supplied claims", result.stage_results["deep_researcher"].lower())


if __name__ == "__main__":
    unittest.main()
