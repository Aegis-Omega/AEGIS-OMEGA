#!/usr/bin/env python3
"""Negative and determinism tests for the Automaton-2 boundary."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_module(
    "cognitive_manifest_generator",
    REPO_ROOT / "scripts" / "build-cognitive-manifest.py",
)
VALIDATOR = load_module(
    "automaton2_validator",
    REPO_ROOT / "scripts" / "validate-automaton2.py",
)


class Automaton2Tests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".claude" / "skills" / "test").mkdir(parents=True)
        (self.root / ".claude" / "skills" / "test" / "SKILL.md").write_text(
            "---\nname: test-skill\n---\n# Test\n",
            encoding="utf-8",
        )
        (self.root / "scripts").mkdir()
        (self.root / "schemas").mkdir()
        (self.root / "scripts" / "build-cognitive-manifest.py").write_text(
            (REPO_ROOT / "scripts" / "build-cognitive-manifest.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (self.root / "schemas" / "cognitive-state.v1.schema.json").write_text(
            (REPO_ROOT / "schemas" / "cognitive-state.v1.schema.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.parent_hash = "1" * 64
        self.write_manifest()

    def write_manifest(self) -> dict:
        manifest, hashes = GENERATOR.build_manifest(
            self.root,
            source_ref="test-source",
            parent_state_hash=self.parent_hash,
        )
        (self.root / ".claude.json").write_text(
            GENERATOR.render_manifest(manifest),
            encoding="utf-8",
        )
        (self.root / "skill-hashes.sha256").write_text(hashes, encoding="utf-8")
        return manifest

    def evaluate(self, *, require_oidc: bool = False) -> dict:
        return VALIDATOR.evaluate(
            root=self.root,
            manifest_path=self.root / ".claude.json",
            schema_path=self.root / "schemas" / "cognitive-state.v1.schema.json",
            generator_path=self.root / "scripts" / "build-cognitive-manifest.py",
            hashes_path=self.root / "skill-hashes.sha256",
            expected_parent_state_hash=self.parent_hash,
            candidate_sha="a" * 40,
            require_oidc=require_oidc,
        )

    def rewrite_manifest(self, manifest: dict) -> None:
        unhashed = dict(manifest)
        unhashed.pop("state_hash", None)
        manifest["state_hash"] = VALIDATOR.sha256_hex(VALIDATOR.canonical_bytes(unhashed))
        (self.root / ".claude.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_valid_manifest_is_admitted(self) -> None:
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "ADMITTED")
        self.assertEqual(receipt["violation_count"], 0)

    def test_parent_state_mismatch_is_denied(self) -> None:
        self.parent_hash = "2" * 64
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("parent_state_hash mismatch" in item for item in receipt["violations"]))

    def test_skill_digest_mismatch_is_denied(self) -> None:
        skill = self.root / ".claude" / "skills" / "test" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("skill digest mismatch" in item for item in receipt["violations"]))

    def test_invalid_manifest_schema_is_denied(self) -> None:
        manifest = json.loads((self.root / ".claude.json").read_text(encoding="utf-8"))
        manifest.pop("ontology_dimensions")
        self.rewrite_manifest(manifest)
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any(item.startswith("schema:") for item in receipt["violations"]))

    def test_unsigned_transition_is_denied(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GITHUB_ACTIONS": "",
                "ACTIONS_ID_TOKEN_REQUEST_URL": "",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "",
            },
            clear=False,
        ):
            receipt = self.evaluate(require_oidc=True)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("unsigned transition" in item for item in receipt["violations"]))

    def test_replay_divergence_is_denied(self) -> None:
        manifest = json.loads((self.root / ".claude.json").read_text(encoding="utf-8"))
        manifest["cognitive_state"]["actions"]["on_success"] = "changed-after-generation"
        self.rewrite_manifest(manifest)
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertIn(
            "replay divergence: committed manifest does not regenerate",
            receipt["violations"],
        )

    def test_skill_hash_file_mismatch_is_denied(self) -> None:
        (self.root / "skill-hashes.sha256").write_text("bad\n", encoding="utf-8")
        receipt = self.evaluate()
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertIn("skill-hashes.sha256 does not regenerate", receipt["violations"])

    def test_receipts_are_deterministic(self) -> None:
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first, second)
        self.assertEqual(first["receipt_hash"], second["receipt_hash"])


if __name__ == "__main__":
    main()
