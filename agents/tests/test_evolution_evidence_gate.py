"""Fail-closed EvolutionEngine regressions. Run: python -m unittest agents.tests.test_evolution_evidence_gate -v."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from agents.evolution import AdaptiveLineage, EvolutionEngine, _coherent_observation
from harness.sdk.skill_authority import compute_registry_root, evaluate_registry


class TemporaryLineage(AdaptiveLineage):
    def __init__(self, path):
        super().__init__()
        self.path = path

    def save(self, path=None):
        super().save(self.path if path is None else path)


class EvolutionEvidenceGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "harness").mkdir()
        (self.root / "agents").mkdir()
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "run.json").write_text("{}\n", encoding="utf-8")
        self.tree_path = self.root / "harness" / "skill_tree.json"
        self.lineage_path = self.root / "agents" / "adaptive_lineage.json"

    def skill(self, tier="T2", failure_rate=0.0):
        return {
            "skill_id": "fixture", "tier": tier, "observation_state": "OBSERVED",
            "validated_runs": 4, "confidence": 0.96, "recency_score": 0.98,
            "failure_rate": failure_rate, "failure_rate_observed": failure_rate,
            "last_validated": "2026-11-16T00:00:00Z",
            "evidence_refs": ["evidence/run.json"],
        }

    def write_tree(self, skill):
        tree = {
            "schema_version": "2.0.0", "version": "2.0.0", "phase": 2,
            "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
            "source_commit": "a" * 40, "doc_count": 0, "skills": [skill],
        }
        digest = compute_registry_root(tree)
        tree["registry_root"] = tree["genesis_seal"] = digest
        self.tree_path.write_text(json.dumps(tree, indent=2) + "\n", encoding="utf-8")
        return tree

    def engine(self, lineage=None):
        return EvolutionEngine(
            tree_path=str(self.tree_path),
            lineage=lineage if lineage is not None else TemporaryLineage(self.lineage_path),
            repo_root=self.root,
        )

    def test_forged_observation_cannot_promote(self):
        skill = self.skill()
        self.assertTrue(_coherent_observation(skill))
        self.write_tree(skill)
        before = self.tree_path.read_bytes()
        engine = self.engine()
        for _ in range(3):
            verdict = engine.tick(apply_changes=True)[0]
            self.assertFalse(verdict.promoted)
            self.assertTrue(verdict.requires_evidence)
            self.assertEqual(verdict.eligible_tier, "T1")
        self.assertEqual(before, self.tree_path.read_bytes())
        self.assertEqual(engine.lineage.events, [])
        self.assertFalse(self.lineage_path.exists())

    def test_unobserved_and_invalid_metrics_cannot_promote(self):
        mutations = [
            {"observation_state": "UNOBSERVED"}, {"observation_state": "UNKNOWN"},
            {"validated_runs": True}, {"validated_runs": 2},
            {"confidence": float("nan")}, {"recency_score": float("inf")},
            {"failure_rate": float("-inf")}, {"failure_rate_observed": 0.5},
            {"evidence_refs": []}, {"last_validated": None},
        ]
        for change in mutations:
            with self.subTest(change=change):
                skill = self.skill()
                skill.update(change)
                verdict = self.engine().evaluate_skill(skill)
                self.assertFalse(verdict.promoted)
                self.assertFalse(verdict.requires_evidence)

    def test_bad_registry_root_and_missing_evidence_denied(self):
        for kind in ("root", "missing"):
            with self.subTest(kind=kind):
                tree = self.write_tree(self.skill())
                if kind == "root":
                    tree["registry_root"] = "0" * 64
                    self.tree_path.write_text(json.dumps(tree), encoding="utf-8")
                else:
                    (self.root / "evidence" / "run.json").unlink()
                before = self.tree_path.read_bytes()
                with self.assertRaises(ValueError):
                    self.engine().tick(apply_changes=True)
                self.assertEqual(self.tree_path.read_bytes(), before)
                self.assertFalse(self.lineage_path.exists())
                if kind == "missing":
                    (self.root / "evidence" / "run.json").write_text("{}\n", encoding="utf-8")

    def test_corrupt_lineage_fails_closed(self):
        self.write_tree(self.skill())
        lineage = TemporaryLineage(self.lineage_path)
        lineage.append("EVIDENCE_RECORDED", "fixture", "T2", "T2", "baseline", timestamp_ms=7)
        lineage.events[0].evidence = "tampered"
        before = self.tree_path.read_bytes()
        with self.assertRaises(ValueError):
            self.engine(lineage).tick(apply_changes=True)
        self.assertEqual(before, self.tree_path.read_bytes())
        self.assertFalse(self.lineage_path.exists())

    def test_lineage_metadata_tampering_detected(self):
        lineage = TemporaryLineage(self.lineage_path)
        lineage.append("EVIDENCE_RECORDED", "fixture", "T2", "T2", "baseline", timestamp_ms=7)
        lineage.save()
        raw = json.loads(self.lineage_path.read_text(encoding="utf-8"))
        raw["event_count"] = 99
        self.lineage_path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaises(ValueError):
            AdaptiveLineage.load(self.lineage_path)

    def test_demotion_rebinds_root_and_replayed_evidence_is_idempotent(self):
        self.write_tree(self.skill(tier="T1", failure_rate=0.6))
        before = json.loads(self.tree_path.read_text(encoding="utf-8"))
        engine = self.engine()
        verdict = engine.tick(apply_changes=True)[0]
        self.assertEqual(verdict.eligible_tier, "T2")
        post = json.loads(self.tree_path.read_text(encoding="utf-8"))
        self.assertEqual(post["skills"][0]["tier"], "T2")
        self.assertNotEqual(post["registry_root"], before["registry_root"])
        self.assertEqual(post["registry_root"], compute_registry_root(post))
        self.assertEqual(post["genesis_seal"], post["registry_root"])
        self.assertEqual(evaluate_registry(post, repo_root=self.root).outcome, "ADMITTED")
        self.assertEqual(len(AdaptiveLineage.load(self.lineage_path).events), 1)
        after_tree = self.tree_path.read_bytes()
        after_lineage = self.lineage_path.read_bytes()
        engine2 = self.engine(AdaptiveLineage.load(self.lineage_path))
        engine2.tick(apply_changes=True)
        self.assertEqual(self.tree_path.read_bytes(), after_tree)
        self.assertEqual(self.lineage_path.read_bytes(), after_lineage)

    def test_readonly_tick_preserves_registry(self):
        self.write_tree(self.skill())
        before = self.tree_path.read_bytes()
        self.engine().tick(apply_changes=False)
        self.assertEqual(self.tree_path.read_bytes(), before)
        self.assertFalse(self.lineage_path.exists())

    def test_committed_41_unobserved_skills_have_no_promotion(self):
        tree = json.loads((REPO_ROOT / "harness" / "skill_tree.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tree["skills"]), 41)
        self.assertTrue(all(s["observation_state"] == "UNOBSERVED" for s in tree["skills"]))
        engine = EvolutionEngine(
            tree_path=str(REPO_ROOT / "harness" / "skill_tree.json"),
            lineage=AdaptiveLineage(),
            repo_root=REPO_ROOT,
        )
        verdicts = engine.tick(apply_changes=False)
        self.assertEqual(len(verdicts), 41)
        self.assertFalse(any(v.promoted or v.requires_evidence for v in verdicts))


if __name__ == "__main__":
    unittest.main(verbosity=2)
