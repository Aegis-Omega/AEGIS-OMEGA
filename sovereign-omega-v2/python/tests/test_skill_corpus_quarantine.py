"""Fail-closed contract for a salvaged external skill source corpus.

Presence of source bytes in Git is repository evidence only. The corpus must stay
outside provider auto-discovery paths, remain bound to its historical source, and
must not acquire execution or admission authority merely because it is present.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS_ROOT = ROOT / "knowledge" / "source-corpora" / "google-datacloud-skills-v1"
SKILLS = CORPUS_ROOT / "skills"
PROVENANCE = CORPUS_ROOT / "provenance.json"
SOURCE_MANIFEST = CORPUS_ROOT / "evidence" / "source-manifest.json"

EXPECTED_SOURCE_HEAD = "8606c90014dc59d234ddc9de9d38a787a2d32d8e"
EXPECTED_SOURCE_PREFIX = ".agents/skills"
EXPECTED_CORPUS_ROOT_SHA256 = "af5595d2254e4a7d2d337aa2910368e7a87cbc2d6a1807be6abf484093ef0285"
EXPECTED_BUNDLE_CHECKSUM = "de6fab4170eb7786ed7e405889312448e8c982302fb3651f1aaff30f577c2591"
EXPECTED_SOURCE_MANIFEST_SHA256 = "3126675fb90fe6d7cecb07006338c76f5c5bc41f5714d7bcd88e55d9e6f2dfc7"
EXPECTED_PACKAGES = 56
EXPECTED_FILES = 325


def _provenance(test: unittest.TestCase) -> dict:
    test.assertTrue(PROVENANCE.is_file(), "source-corpus provenance metadata is missing")
    return json.loads(PROVENANCE.read_text(encoding="utf-8"))


class SkillCorpusQuarantine(unittest.TestCase):
    def test_source_corpus_is_content_addressed_and_dormant(self) -> None:
        self.assertTrue(SKILLS.is_dir(), "provider-neutral source corpus is missing")
        self.assertTrue(SOURCE_MANIFEST.is_file(), "source manifest evidence is missing")
        p = _provenance(self)

        self.assertEqual(p["schema"], "AEGIS_DORMANT_SOURCE_CORPUS_V1")
        self.assertEqual(p["source_pr"], 240)
        self.assertEqual(p["source_sha"], EXPECTED_SOURCE_HEAD)
        self.assertEqual(p["source_prefix"], EXPECTED_SOURCE_PREFIX)
        self.assertEqual(p["source_bundle_checksum"], EXPECTED_BUNDLE_CHECKSUM)
        self.assertEqual(p["source_manifest_sha256"], EXPECTED_SOURCE_MANIFEST_SHA256)
        self.assertEqual(p["corpus_root_sha256"], EXPECTED_CORPUS_ROOT_SHA256)
        self.assertEqual(p["package_count"], EXPECTED_PACKAGES)
        self.assertEqual(p["file_count"], EXPECTED_FILES)
        self.assertEqual(p["epistemic_status"], "UNVERIFIED_SOURCE_CORPUS")
        self.assertEqual(p["activation_status"], "DORMANT_NOT_DISCOVERABLE_BY_ACTIVE_SKILL_PATH")
        self.assertEqual(p["execution_status"], "SOURCE_BYTES_NOT_EXECUTED")
        self.assertEqual(p["authority_effect"], "NONE")

    def test_provider_mirror_and_internal_execution_paths_are_not_reintroduced(self) -> None:
        self.assertFalse((ROOT / ".agents" / "skills").exists())
        self.assertFalse((ROOT / ".gemini" / "skills").exists())
        self.assertFalse((SKILLS / "run-aegis").exists())

    def test_corpus_presence_does_not_mean_skill_admission(self) -> None:
        p = _provenance(self)
        self.assertNotEqual(p["epistemic_status"], "ADMITTED")
        self.assertEqual(p["authority_effect"], "NONE")
        self.assertNotEqual(p["execution_status"], "EXECUTION_ENABLED")


if __name__ == "__main__":
    unittest.main()
