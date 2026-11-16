"""Native fail-closed skill ID validation, no external writes or pytest dependency."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from harness.sdk.skill_authority import (
    SkillAuthorityError, compute_registry_root, evaluate_registry,
    sanitize_legacy_tree,
)


def _legacy_skill(sid: str) -> dict:
    return {
        "skill_id": sid, "tier": "T2", "validated_runs": 0,
        "confidence": 0.5, "failure_rate": 0.0,
        "recency_score": 0.0, "evidence_refs": ["evidence/test.md"],
        "last_validated": None,
    }


def _legacy_tree(*ids: str) -> dict:
    return {"phase": 1, "skills": [_legacy_skill(sid) for sid in ids]}


class SkillIdentityIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "test.md").write_text(
            "# Fixture only\n", encoding="utf-8",
        )

    def _admitted(self, *ids: str) -> dict:
        return sanitize_legacy_tree(_legacy_tree(*ids), source_commit="a" * 40)

    def test_two_unique_source_ids_are_admitted(self) -> None:
        tree = self._admitted("candidate", "beta")
        receipt = evaluate_registry(tree, repo_root=self.root)
        self.assertEqual(receipt.outcome, "ADMITTED")
        self.assertEqual(receipt.violation_count, 0)

    def test_duplicate_skills_with_recomputed_valid_roots_are_denied(self) -> None:
        tree = self._admitted("candidate", "beta")
        tree["skills"][1]["skill_id"] = "candidate"
        root = compute_registry_root(tree)
        tree["registry_root"] = tree["genesis_seal"] = root
        self.assertEqual(tree["registry_root"], compute_registry_root(tree))
        receipt = evaluate_registry(tree, repo_root=self.root)
        self.assertEqual(receipt.outcome, "DENIED")
        self.assertIn("candidate: duplicate skill_id", receipt.violations)
        self.assertNotIn("TREE: registry_root mismatch", receipt.violations)

    def test_legacy_migration_rejects_duplicate_identifiers(self) -> None:
        legacy = _legacy_tree("candidate", "candidate")
        with self.assertRaisesRegex(SkillAuthorityError, "duplicate skill_id: candidate"):
            sanitize_legacy_tree(legacy, source_commit="a" * 40)
        self.assertEqual(legacy["skills"][0]["skill_id"], "candidate")

    def test_empty_and_nonstring_legacy_identifiers_are_denied(self) -> None:
        for sid in ("", None, 0, False, []):
            with self.subTest(sid=sid):
                with self.assertRaises(SkillAuthorityError):
                    sanitize_legacy_tree(_legacy_tree("candidate", sid),
                                         source_commit="a" * 40)

    def test_missing_evaluation_identifier_is_denied_even_with_updated_roots(self) -> None:
        for invalid in ("", None, False):
            with self.subTest(invalid=invalid):
                tree = self._admitted("candidate")
                tree["skills"][0]["skill_id"] = invalid
                tree["registry_root"] = tree["genesis_seal"] = compute_registry_root(tree)
                receipt = evaluate_registry(tree, repo_root=self.root)
                self.assertEqual(receipt.outcome, "DENIED")

    def test_unique_id_order_reversal_keeps_authority(self) -> None:
        tree = self._admitted("candidate", "beta")
        tree["skills"].reverse()
        tree["registry_root"] = tree["genesis_seal"] = compute_registry_root(tree)
        self.assertEqual(evaluate_registry(tree, repo_root=self.root).outcome, "ADMITTED")

    def test_real_committed_registry_has_unique_ids(self) -> None:
        tree = json.loads((ROOT / "harness" / "skill_tree.json").read_text(encoding="utf-8"))
        ids = [skill["skill_id"] for skill in tree["skills"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(evaluate_registry(tree, repo_root=ROOT).outcome, "ADMITTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
