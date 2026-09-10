#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "harness" / "sdk" / "artifact_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("aegis_artifact_evidence", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ArtifactEvidenceContract(unittest.TestCase):
    def test_production_module_exists(self) -> None:
        self.assertTrue(
            MODULE_PATH.exists(),
            "provider-neutral artifact evidence evaluator is not implemented",
        )

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: artifact evidence evaluator absent")
    def test_named_reference_is_not_implementation_evidence(self) -> None:
        mod = load_module()
        result = mod.classify_artifact_evidence(
            implementation_evidence=[],
            named_references=["refs/heads/proof-prism-v1"],
            required_scopes=["exact_head", "local_refs", "remote_metadata"],
            completed_scopes=["exact_head", "local_refs"],
        )
        self.assertEqual(result["status"], "NAMED_REFERENCE_FOUND")
        self.assertEqual(result["implementation_evidence_count"], 0)
        self.assertEqual(result["named_reference_count"], 1)
        self.assertFalse(result["global_absence_established"])
        self.assertEqual(result["authority_effect"], "NONE")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: artifact evidence evaluator absent")
    def test_incomplete_scan_denies_global_absence(self) -> None:
        mod = load_module()
        result = mod.classify_artifact_evidence(
            implementation_evidence=[],
            named_references=[],
            required_scopes=["exact_head", "local_refs", "remote_metadata"],
            completed_scopes=["exact_head", "local_refs"],
        )
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["incomplete_scopes"], ["remote_metadata"])
        self.assertFalse(result["global_absence_established"])
        self.assertEqual(result["authority_effect"], "NONE")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: artifact evidence evaluator absent")
    def test_complete_declared_repo_miss_remains_bounded(self) -> None:
        mod = load_module()
        result = mod.classify_artifact_evidence(
            implementation_evidence=[],
            named_references=[],
            required_scopes=["exact_head", "local_refs", "remote_metadata"],
            completed_scopes=["remote_metadata", "local_refs", "exact_head"],
        )
        self.assertEqual(result["status"], "NO_MATCHES_IN_COMPLETE_REPO_SCAN")
        self.assertFalse(result["global_absence_established"])
        self.assertEqual(
            result["absence_claim_boundary"],
            "no_match_in_declared_repo_scan_only; external_or_unobserved_absence_not_established",
        )
        self.assertEqual(result["authority_effect"], "NONE")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: artifact evidence evaluator absent")
    def test_implementation_evidence_is_evidence_only(self) -> None:
        mod = load_module()
        result = mod.classify_artifact_evidence(
            implementation_evidence=[
                {
                    "scope": "local_refs",
                    "ref": "refs/heads/feature",
                    "path": "src/feature.py",
                }
            ],
            named_references=["refs/heads/feature"],
            required_scopes=["exact_head", "local_refs", "remote_metadata"],
            completed_scopes=["exact_head"],
        )
        self.assertEqual(result["status"], "IMPLEMENTATION_EVIDENCE_FOUND")
        self.assertEqual(result["implementation_evidence_count"], 1)
        self.assertFalse(result["global_absence_established"])
        self.assertEqual(result["claim_effect"], "EVIDENCE_ONLY")
        self.assertEqual(result["authority_effect"], "NONE")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: artifact evidence evaluator absent")
    def test_scope_and_reference_normalization_is_deterministic(self) -> None:
        mod = load_module()
        left = mod.classify_artifact_evidence(
            implementation_evidence=[],
            named_references=["refs/tags/v1", "refs/heads/x", "refs/tags/v1"],
            required_scopes=["remote_metadata", "exact_head", "local_refs"],
            completed_scopes=["local_refs", "exact_head"],
        )
        right = mod.classify_artifact_evidence(
            implementation_evidence=[],
            named_references=["refs/heads/x", "refs/tags/v1"],
            required_scopes=["local_refs", "remote_metadata", "exact_head"],
            completed_scopes=["exact_head", "local_refs"],
        )
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main(verbosity=2)
