#!/usr/bin/env python3
"""Fail-closed tests for recovery from a denied canonical cognitive base."""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
RECOVERY_PATH = REPO_ROOT / "scripts" / "validate-cognitive-recovery.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RECOVERY = load_module("cognitive_recovery_validator", RECOVERY_PATH)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class CognitiveRecoveryTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init")
        git(self.root, "config", "user.name", "AEGIS Test")
        git(self.root, "config", "user.email", "aegis-test@example.invalid")

        self.parent_state_hash = "1" * 64
        self.recovery_state_hash = "2" * 64

        self.write_manifest(
            parent_state_hash="0" * 64,
            state_hash=self.parent_state_hash,
            source_ref="parent",
        )
        (self.root / "skill-hashes.sha256").write_text("parent  skill\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "parent")
        self.parent_sha = git(self.root, "rev-parse", "HEAD")

        self.write_manifest(
            parent_state_hash="0" * 64,
            state_hash="0" * 64,
            source_ref="main",
        )
        (self.root / "skill-hashes.sha256").write_text("/dev/null\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "denied base")
        self.denied_sha = git(self.root, "rev-parse", "HEAD")

        self.write_manifest(
            parent_state_hash=self.parent_state_hash,
            state_hash=self.recovery_state_hash,
            source_ref="main",
        )
        (self.root / "skill-hashes.sha256").write_text("recovered  skill\n", encoding="utf-8")
        git(self.root, "add", ".")
        git(self.root, "commit", "-m", "recovery candidate")
        self.candidate_sha = git(self.root, "rev-parse", "HEAD")
        self.manifest_blob = git(self.root, "rev-parse", f"{self.candidate_sha}:.claude.json")
        self.hashes_blob = git(self.root, "rev-parse", f"{self.candidate_sha}:skill-hashes.sha256")

    def write_manifest(self, *, parent_state_hash: str, state_hash: str, source_ref: str) -> None:
        payload = {
            "provenance": {
                "source_ref": source_ref,
                "parent_state_hash": parent_state_hash,
            },
            "state_hash": state_hash,
        }
        (self.root / ".claude.json").write_text(
            json.dumps(payload, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    def evaluate(self, **overrides):
        args = {
            "repo": self.root,
            "candidate_sha": self.candidate_sha,
            "denied_base_sha": self.denied_sha,
            "recovery_parent_sha": self.parent_sha,
            "expected_parent_state_hash": self.parent_state_hash,
            "expected_manifest_blob": self.manifest_blob,
            "expected_skill_hashes_blob": self.hashes_blob,
            "expected_recovery_state_hash": self.recovery_state_hash,
            "denied_receipt_hash": "3" * 64,
            "recovery_validation_receipt_hash": "4" * 64,
        }
        args.update(overrides)
        return RECOVERY.evaluate(**args)

    def test_exact_bounded_recovery_is_verified_without_production_admission(self) -> None:
        receipt = self.evaluate()
        self.assertEqual(receipt["receipt_kind"], "AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1")
        self.assertEqual(receipt["outcome"], "RECOVERY_VERIFIED")
        self.assertEqual(receipt["production_admission"], "NONE")
        self.assertEqual(receipt["violation_count"], 0)

    def test_denied_base_must_be_direct_child_of_recovery_parent(self) -> None:
        receipt = self.evaluate(recovery_parent_sha=self.candidate_sha)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("direct child" in item for item in receipt["violations"]))

    def test_denied_base_may_only_change_governed_anchor_files(self) -> None:
        git(self.root, "checkout", self.denied_sha)
        (self.root / "extra.txt").write_text("unexpected\n", encoding="utf-8")
        git(self.root, "add", "extra.txt")
        git(self.root, "commit", "-m", "denied extra mutation")
        broadened_denied = git(self.root, "rev-parse", "HEAD")
        receipt = self.evaluate(denied_base_sha=broadened_denied)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("denied-base changed paths" in item for item in receipt["violations"]))

    def test_candidate_must_bind_exact_verifier_generated_blobs(self) -> None:
        receipt = self.evaluate(expected_manifest_blob="f" * 40)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("manifest blob mismatch" in item for item in receipt["violations"]))

    def test_candidate_parent_and_recovery_state_are_exact(self) -> None:
        receipt = self.evaluate(expected_recovery_state_hash="9" * 64)
        self.assertEqual(receipt["outcome"], "DENIED")
        self.assertTrue(any("recovery state_hash mismatch" in item for item in receipt["violations"]))

    def test_receipt_is_deterministic(self) -> None:
        self.assertEqual(self.evaluate(), self.evaluate())


if __name__ == "__main__":
    main()
