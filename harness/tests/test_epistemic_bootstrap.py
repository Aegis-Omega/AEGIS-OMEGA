from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


class EpistemicBootstrapTests(unittest.TestCase):
    def test_prompt_intake_marks_observation_chain_as_integrity_only(self):
        intake = (ROOT / ".claude/hooks/user-prompt-intake.sh").read_text()
        self.assertIn("ObservationChain(integrity-only)", intake)
        self.assertIn("chain-integrity≠truth", intake)
        self.assertIn("chain-integrity≠identity", intake)
        self.assertIn("chain-integrity≠consciousness", intake)
        self.assertIn("Claim-status-required:", intake)
        self.assertNotIn("MetacognitiveLoop(live):", intake)
        self.assertNotIn("temporal-mass=", intake)

    def test_prompt_intake_loads_repo_local_bootstrap(self):
        intake = (ROOT / ".claude/hooks/user-prompt-intake.sh").read_text()
        self.assertIn(".claude/epistemic/bootstrap.md", intake)

    def test_bootstrap_carries_historical_boundaries_not_fresh_state(self):
        bootstrap = (ROOT / ".claude/epistemic/bootstrap.md").read_text()
        self.assertIn("Epistemic Debugging Bootstrap", bootstrap)
        self.assertIn("search miss", bootstrap.lower())
        self.assertIn("F-18", bootstrap)
        self.assertIn("historical failure patterns", bootstrap.lower())
        self.assertIn("verify current repository facts afresh", bootstrap.lower())


if __name__ == "__main__":
    unittest.main()
