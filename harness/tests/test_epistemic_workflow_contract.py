from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class EpistemicWorkflowContractTests(unittest.TestCase):
    def test_workflow_is_exact_head_and_least_authority(self):
        workflow = (ROOT / ".github/workflows/epistemic-admission.yml").read_text()
        self.assertIn("CANDIDATE_SHA", workflow)
        self.assertIn('ref: ${{ env.CANDIDATE_SHA }}', workflow)
        self.assertIn("python3 -m unittest harness.tests.test_epistemic_admission", workflow)
        self.assertIn("python3 -m unittest harness.tests.test_epistemic_bootstrap", workflow)
        self.assertIn("python3 scripts/validate-epistemic-admission.py", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("attestations: write", workflow)
        self.assertNotIn("artifact-metadata: write", workflow)

    def test_checkout_dependency_is_immutable(self):
        workflow = (ROOT / ".github/workflows/epistemic-admission.yml").read_text()
        match = re.search(r"actions/checkout@([0-9a-f]{40})", workflow)
        self.assertIsNotNone(match)
        self.assertNotIn("actions/checkout@v", workflow)

    def test_validator_declares_evidence_only_authority(self):
        validator = (ROOT / "scripts/validate-epistemic-admission.py").read_text()
        self.assertIn("EVIDENCE_ONLY_NOT_ADMISSION_AUTHORITY", validator)
        self.assertIn("--candidate-sha", validator)


if __name__ == "__main__":
    unittest.main()
