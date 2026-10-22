"""Regression gate: mutable skill counters never trigger autonomous tier writes.

Reuses the exact prior safety repair from Foundry PR #727. No model/network.
"""
import json
import tempfile
import unittest
from pathlib import Path

from agents.evolution import AdaptiveLineage, EvolutionEngine
from agents.dendrite_workplane import observe_evolution


class EvolutionSafetyTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.dir = Path(work.name)
        self.tree = self.dir / "skills.json"
        self.lineage_path = self.dir / "lineage.json"
        self.skill = {"skill_id": "synthetic_skill", "tier": "T2",
                      "validated_runs": 20, "failure_rate": 0.0, "confidence": 0.99}
        self.write_tree()
        AdaptiveLineage().save(self.lineage_path)

    def write_tree(self):
        self.tree.write_text(json.dumps({"skills": [self.skill]}, sort_keys=True))

    def engine(self):
        return EvolutionEngine(tree_path=str(self.tree),
                               lineage=AdaptiveLineage.load(self.lineage_path))

    def test_reported_success_only_yields_candidate(self):
        v = self.engine().evaluate_skill(self.skill)
        self.assertEqual(v.eligible_tier, "T1")
        self.assertFalse(v.promoted)
        self.assertTrue(v.requires_guardian)

    def test_reported_failure_cannot_autodemote(self):
        self.skill.update(tier="T1", failure_rate=0.8)
        v = self.engine().evaluate_skill(self.skill)
        self.assertEqual(v.eligible_tier, "T2")
        self.assertFalse(v.promoted)
        self.assertTrue(v.requires_guardian)

    def test_t1_to_t0_cannot_self_promote(self):
        self.skill.update(tier="T1")
        v = self.engine().evaluate_skill(self.skill)
        self.assertEqual(v.eligible_tier, "T0")
        self.assertFalse(v.promoted)
        self.assertTrue(v.requires_guardian)

    def test_apply_true_does_not_write_tree_or_lineage(self):
        before_tree = self.tree.read_bytes()
        before_lineage = self.lineage_path.read_bytes()
        engine = self.engine()
        verdicts = engine.tick(apply_changes=True)
        self.assertEqual(len(verdicts), 1)
        self.assertFalse(verdicts[0].promoted)
        self.assertEqual(self.tree.read_bytes(), before_tree)
        self.assertEqual(self.lineage_path.read_bytes(), before_lineage)

    def test_engine_does_not_mutate_in_memory_lineage(self):
        lineage = AdaptiveLineage()
        lineage.append("EVIDENCE_RECORDED", "synthetic_skill", "T2", "T2",
                       "not independently verified", timestamp_ms=100)
        before = lineage.terminal_hash()
        engine = EvolutionEngine(tree_path=str(self.tree), lineage=lineage)
        engine.tick(apply_changes=True)
        self.assertEqual(before, lineage.terminal_hash())
        self.assertEqual(len(lineage.events), 1)

    def test_workplane_uses_real_readonly_evolution(self):
        before_tree = self.tree.read_bytes()
        before_lineage = self.lineage_path.read_bytes()
        observation = observe_evolution(self.tree, self.lineage_path)
        self.assertEqual(observation["status"], "READ_ONLY_OBSERVATION")
        self.assertFalse(observation["promotion_applied"])
        self.assertEqual(observation["skills_observed"], 1)
        self.assertEqual(self.tree.read_bytes(), before_tree)
        self.assertEqual(self.lineage_path.read_bytes(), before_lineage)


if __name__ == "__main__":
    unittest.main()
