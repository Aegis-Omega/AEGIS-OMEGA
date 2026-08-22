#!/usr/bin/env python3
"""Falsifiers for the Gate-205 Artisan -> canonical Glasswing evidence adapter."""

import importlib.util
from pathlib import Path
import unittest

from security.glasswing_evidence import SecurityDisposition


REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = REPO_ROOT / "sovereign-mesh" / "nodes" / "artisan" / "generator.py"
SPEC = importlib.util.spec_from_file_location("aegis_gate205_artisan", GENERATOR_PATH)
ARTISAN = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ARTISAN)


class GlasswingArtisanAdapterTests(unittest.TestCase):
    def _unsafe_artifact(self):
        content = "fn dangerous() { unsafe { let p = as_mut_ptr(); } }"
        return ARTISAN.GeneratedArtifact(
            file_path="src/dangerous.rs",
            content=content,
            language="rust",
            lines_of_code=1,
            complexity_score=0.1,
            eccf_lattice_applied=False,
            glasswing_scan_passed=False,
        )

    def test_artisan_emits_canonical_evidence_only_report(self):
        artifact = self._unsafe_artifact()
        report = ARTISAN.GlasswingHook().scan_artifact_evidence(artifact)

        self.assertEqual(report.authority, "EVIDENCE_ONLY")
        self.assertEqual(report.disposition, SecurityDisposition.BLOCKED)
        self.assertTrue(report.findings)
        self.assertTrue(all(f.detector_id == "glasswing-regex-v1" for f in report.findings))

    def test_high_finding_blocks_sprint_success_via_same_disposition(self):
        artifact = self._unsafe_artifact()
        contract = {
            "sprint_id": "glasswing-adapter-test",
            "directive": "exercise security adapter",
            "specifications": ["PROCESS: unsafe fixture"],
            "constraints": [],
            "complexity_lambda": 1,
        }
        executor = ARTISAN.SprintExecutor(contract)
        executor._generate_artifacts = lambda specifications, level: [artifact]

        result = executor.execute()

        self.assertFalse(result.success)
        self.assertFalse(result.artifacts[0].glasswing_scan_passed)
        self.assertEqual(result.artifacts[0].glasswing_disposition, "BLOCKED")
        self.assertEqual(len(result.glasswing_evidence), 1)
        self.assertEqual(result.glasswing_evidence[0]["authority"], "EVIDENCE_ONLY")
        self.assertEqual(result.glasswing_evidence[0]["disposition"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
