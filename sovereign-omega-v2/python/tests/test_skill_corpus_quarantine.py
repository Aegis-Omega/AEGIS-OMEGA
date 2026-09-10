"""Fail-closed contract for salvaged external skill source corpora.

A source corpus is repository evidence only. It must live outside provider auto-discovery
paths, remain content-addressed to its historical source tree, and carry no admission
or execution authority merely because the bytes are present in Git.
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "knowledge" / "skill-corpus" / "datacloud-v1"
META = ROOT / "knowledge" / "skill-corpus" / "datacloud-v1.source.json"
EXPECTED_TREE = "fe7f9600f673727a50175533b60cc0fde07a6ca1"
EXPECTED_SOURCE_HEAD = "8606c90014dc59d234ddc9de9d38a787a2d32d8e"


class SkillCorpusQuarantine(unittest.TestCase):
    def test_source_corpus_is_exactly_content_addressed_and_quarantined(self) -> None:
        self.assertTrue(CORPUS.is_dir(), "provider-neutral source corpus is missing")
        tree = subprocess.check_output(
            ["git", "rev-parse", "HEAD:knowledge/skill-corpus/datacloud-v1"],
            cwd=ROOT,
            text=True,
        ).strip()
        self.assertEqual(tree, EXPECTED_TREE)

        metadata = json.loads(META.read_text(encoding="utf-8"))
        self.assertEqual(metadata["schema"], "AEGIS_SKILL_SOURCE_CORPUS_V1")
        self.assertEqual(metadata["source_pr"], 240)
        self.assertEqual(metadata["source_head_sha"], EXPECTED_SOURCE_HEAD)
        self.assertEqual(metadata["source_tree_sha"], EXPECTED_TREE)
        self.assertEqual(metadata["corpus_path"], "knowledge/skill-corpus/datacloud-v1")
        self.assertEqual(metadata["status"], "UNVERIFIED_SOURCE_CORPUS")
        self.assertEqual(metadata["activation"], "DISABLED")
        self.assertEqual(metadata["validated_runs"], 0)
        self.assertEqual(metadata["authority_effect"], "NONE")

    def test_provider_mirror_paths_are_not_reintroduced(self) -> None:
        self.assertFalse((ROOT / ".agents" / "skills").exists())
        self.assertFalse((ROOT / ".gemini" / "skills").exists())

    def test_corpus_presence_does_not_mean_skill_admission(self) -> None:
        metadata = json.loads(META.read_text(encoding="utf-8"))
        self.assertNotEqual(metadata["status"], "ADMITTED")
        self.assertEqual(metadata["authority_effect"], "NONE")
        self.assertFalse(metadata.get("execution_enabled", False))


if __name__ == "__main__":
    unittest.main()
