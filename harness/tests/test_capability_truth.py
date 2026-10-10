"""Adversarial tests of read-only capability assurance; no network or model calls."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness.sdk.capability_truth import (
    CapabilityTruthError,
    build_capability_truth,
    read_capability_truth,
)
from harness.sdk.skill_authority import compute_registry_root


SOURCE = "a" * 40


def fixture(*, observed: bool = False) -> dict:
    skill = {
        "skill_id": "sample_tool",
        "evidence_refs": ["CLAUDE.md"],
        "observation_state": "OBSERVED" if observed else "UNOBSERVED",
        "validated_runs": 3 if observed else 0,
        "confidence": 0.9 if observed else 0.0,
        "failure_rate": 0.0,
        "recency_score": 0.9 if observed else 0.0,
        "last_validated": "2026-10-10T00:00:00Z" if observed else None,
    }
    registry = {
        "schema_version": "2.0.0",
        "source_commit": SOURCE,
        "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
        "skills": [skill],
    }
    registry["registry_root"] = compute_registry_root(registry)
    registry["genesis_seal"] = registry["registry_root"]
    return registry


class CapabilityTruthTests(unittest.TestCase):
    def test_unobserved_is_not_promoted_by_matching_commit(self):
        snapshot = build_capability_truth(fixture(), runtime_commit=SOURCE)
        self.assertEqual(snapshot["source_alignment"], "MATCH")
        self.assertEqual(snapshot["observed_skill_count"], 0)
        self.assertFalse(snapshot["authority_granted"])
        self.assertEqual(snapshot["agent_executability"], "UNKNOWN")
        self.assertEqual(snapshot["skills"][0]["runtime_admission"], "NOT_ESTABLISHED")

    def test_observed_skill_still_has_no_runtime_admission(self):
        snapshot = build_capability_truth(fixture(observed=True), runtime_commit=SOURCE)
        self.assertEqual(snapshot["observed_skill_count"], 1)
        self.assertGreater(snapshot["skills"][0]["competency_evidence_score"], 0)
        self.assertFalse(snapshot["authority_granted"])
        self.assertEqual(snapshot["operational_admission"], "NOT_ESTABLISHED")

    def test_snapshot_stable_and_source_mismatch_reported(self):
        registry = fixture()
        first = build_capability_truth(registry, runtime_commit="b" * 40)
        second = build_capability_truth(registry, runtime_commit="b" * 40)
        self.assertEqual(first, second)
        self.assertEqual(first["source_alignment"], "MISMATCH")
        self.assertNotEqual(first["snapshot_sha256"], build_capability_truth(registry)["snapshot_sha256"])

    def test_registry_mutation_without_resealing_denied(self):
        registry = fixture()
        registry["skills"][0]["validated_runs"] = 3
        with self.assertRaisesRegex(CapabilityTruthError, "INTEGRITY"):
            build_capability_truth(registry)

    def test_duplicate_ids_denied_even_with_recomputed_root(self):
        registry = fixture()
        registry["skills"].append(dict(registry["skills"][0]))
        registry["registry_root"] = compute_registry_root(registry)
        registry["genesis_seal"] = registry["registry_root"]
        with self.assertRaisesRegex(CapabilityTruthError, "DUPLICATE"):
            build_capability_truth(registry)

    def test_schema_or_invalid_commit_denied(self):
        with self.assertRaises(CapabilityTruthError):
            build_capability_truth({**fixture(), "schema_version": "3.0.0"})
        with self.assertRaisesRegex(CapabilityTruthError, "RUNTIME_COMMIT_INVALID"):
            build_capability_truth(fixture(), runtime_commit="unknown")

    def test_missing_and_malformed_registry_denied(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "skills.json"
            with self.assertRaises(CapabilityTruthError):
                read_capability_truth(path)
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(CapabilityTruthError):
                read_capability_truth(path)

    def test_symlink_denied(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "skills.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            shortcut = Path(root) / "alias.json"
            shortcut.symlink_to(path)
            with self.assertRaises(CapabilityTruthError):
                read_capability_truth(shortcut)

    def test_committed_registry_is_integrity_checked(self):
        path = Path(__file__).resolve().parents[1] / "skill_tree.json"
        snapshot = read_capability_truth(path)
        self.assertEqual(snapshot["skill_count"], len(snapshot["skills"]))
        self.assertFalse(snapshot["authority_granted"])
        self.assertEqual(snapshot["source_alignment"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
