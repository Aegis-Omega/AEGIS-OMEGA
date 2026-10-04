from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from agents.evolution import AdaptiveLineage, EvolutionEngine  # noqa: E402
from harness.sdk.skill_authority import compute_registry_root, evaluate_registry  # noqa: E402


class _TempLineage(AdaptiveLineage):
    def __init__(self, path: Path):
        super().__init__()
        self._path = path

    def save(self, path: Path | None = None) -> None:
        super().save(path=self._path if path is None else path)


class EvolutionRegistryRootTests(TestCase):
    def test_promotion_rebinds_skill_registry_root_and_preserves_admission(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence" / "run.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("{}\n", encoding="utf-8")

            tree = {
                "schema_version": "2.0.0",
                "version": "2.0.0",
                "phase": 2,
                "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
                "source_commit": "a" * 40,
                "doc_count": 0,
                "skills": [{
                    "skill_id": "promotion_candidate",
                    "tier": "T2",
                    "observation_state": "OBSERVED",
                    "validated_runs": 3,
                    "confidence": 0.92,
                    "recency_score": 0.95,
                    "failure_rate": 0.0,
                    "failure_rate_observed": 0.0,
                    "last_validated": "2026-10-04T00:00:00+00:00",
                    "evidence_refs": ["evidence/run.json"],
                }],
            }
            original_root = compute_registry_root(tree)
            tree["registry_root"] = original_root
            tree["genesis_seal"] = original_root

            tree_path = root / "harness" / "skill_tree.json"
            tree_path.parent.mkdir(parents=True)
            tree_path.write_text(json.dumps(tree, indent=2) + "\n", encoding="utf-8")
            lineage = _TempLineage(root / "agents" / "adaptive_lineage.json")
            lineage._path.parent.mkdir(parents=True)

            engine = EvolutionEngine(tree_path=str(tree_path), lineage=lineage)
            verdicts = engine.tick(apply_changes=True)

            saved = json.loads(tree_path.read_text(encoding="utf-8"))
            self.assertTrue(any(v.promoted for v in verdicts))
            self.assertEqual(saved["skills"][0]["tier"], "T1")
            self.assertNotEqual(saved["registry_root"], original_root)

            expected_root = compute_registry_root(saved)
            self.assertEqual(saved["registry_root"], expected_root)
            self.assertEqual(saved["genesis_seal"], expected_root)

            receipt = evaluate_registry(saved, repo_root=root)
            self.assertEqual(receipt.outcome, "ADMITTED")
            self.assertEqual(receipt.violation_count, 0)


if __name__ == "__main__":
    main()
