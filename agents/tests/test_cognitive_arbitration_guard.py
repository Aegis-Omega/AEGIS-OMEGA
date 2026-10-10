"""AEGIS cognitive arbitration — fail-closed claim-routing regressions."""
import asyncio
import unittest

from agents.cognitive_pipeline import (
    ADMISSION_THRESHOLD,
    KanInferenceLog,
    arbitrate,
    constitutional_scorer,
    run_pipeline,
)


class CognitiveArbitrationGuard(unittest.TestCase):
    def setUp(self):
        self.scorer = constitutional_scorer()
        self.log = KanInferenceLog()

    def verdict(self, text):
        return arbitrate(text, self.scorer, self.log)

    def test_zero_evidence_yields_zero_score(self):
        self.assertEqual(self.scorer.score([0, 0, 0, 0]), 0)

    def test_score_has_nonsaturated_order(self):
        scores = [self.scorer.score(row) for row in
                  ([0, 0, 0, 0], [4, 0, 0, 0], [15, 15, 0, 15])]
        self.assertLess(scores[0], scores[1])
        self.assertLess(scores[1], scores[2])
        self.assertGreaterEqual(scores[2], ADMISSION_THRESHOLD)

    def test_plain_fabrication_rejected(self):
        v = self.verdict("No source supplied; this idea was never tested")
        self.assertEqual(v["tier"], "T3")
        self.assertFalse(v["candidate_for_review"])
        self.assertFalse(v["admitted"])

    def test_fake_mechanical_proof_cannot_be_admitted(self):
        v = self.verdict("Mechanically proven deterministic SHA-256: 2+2 = 7")
        self.assertEqual(v["claimed_tier"], "T0")
        self.assertEqual(v["tier"], "T3")
        self.assertTrue(v["candidate_for_review"])
        self.assertFalse(v["admitted"])

    def test_fake_empirical_claim_cannot_be_admitted(self):
        v = self.verdict("Empirically validated; no data were collected")
        self.assertEqual(v["claimed_tier"], "T1")
        self.assertEqual(v["tier"], "T3")
        self.assertFalse(v["admitted"])

    def test_citation_words_cannot_create_evidence(self):
        v = self.verdict("DOI peer-reviewed journal arxiv proceedings benchmark")
        self.assertFalse(v["admitted"])
        self.assertEqual(v["admission_status"], "PENDING_INDEPENDENT_VERIFICATION")

    def test_t45_quarantine_preserved(self):
        v = self.verdict("Planetary sovereign consciousness mechanically proven")
        self.assertEqual(v["tier"], "T4/T5")
        self.assertEqual(v["admission_status"], "DENIED_T45")
        self.assertFalse(v["candidate_for_review"])
        self.assertFalse(v["admitted"])

    def test_chain_integrity_preserved(self):
        self.verdict("sha-256 deterministic test")
        self.verdict("unverified idea")
        valid, index = self.log.verify_chain()
        self.assertTrue(valid)
        self.assertIsNone(index)

    def test_offline_run_does_not_invent_research(self):
        r = asyncio.run(run_pipeline("new subject"))
        self.assertEqual(r.arbitration, [])
        self.assertEqual(r.admitted, [])
        self.assertEqual(r.candidates, [])
        self.assertTrue(r.chain_valid)
        self.assertIn("NO_CLAIMS", r.stage_results["deep_researcher"])

    def test_review_candidates_remain_separate(self):
        r = asyncio.run(run_pipeline(
            "test", claims=["Mechanically proven deterministic SHA-256: 2+2=7"]))
        self.assertEqual(len(r.candidates), 1)
        self.assertEqual(r.admitted, [])
        self.assertEqual(r.candidates[0]["tier"], "T3")


if __name__ == "__main__":
    unittest.main()
