#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "baseline",
    HERE / "verify-frontier-engineering-baseline.py",
)
assert SPEC and SPEC.loader
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)

FULL = "a" * 40
CANDIDATE = "b" * 40
VERIFIER = "c" * 64


def populate_required(root: Path, *, mutable: bool) -> None:
    for rel in baseline.REQUIRED:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder\n", encoding="utf-8")

    automaton2 = root / ".github/workflows/automaton-2.yml"
    checkout = "v4" if mutable else FULL
    automaton2.write_text(
        f"""permissions:
  id-token: write
  attestations: write
  artifact-metadata: write
env:
  CANDIDATE_SHA: x
steps:
  - uses: actions/checkout@{checkout}
  - uses: actions/attest@{FULL}
""",
        encoding="utf-8",
    )
    for rel in (
        ".github/workflows/automaton-3.yml",
        ".github/workflows/ci.yml",
        ".github/workflows/osv-scanner.yml",
    ):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"steps:\n  - uses: actions/checkout@{FULL}\n", encoding="utf-8")


class FrontierEngineeringBaselineTests(unittest.TestCase):
    def test_parser_catches_dash_uses_mutable_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "w.yml"
            p.write_text("steps:\n  - uses: actions/checkout@v4\n", encoding="utf-8")
            rows = baseline.action_refs(p)
            self.assertEqual(len(rows), 1)
            self.assertFalse(rows[0]["pinned_full_sha"])

    def test_parser_accepts_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "w.yml"
            p.write_text(f"steps:\n  - uses: actions/checkout@{FULL}\n", encoding="utf-8")
            rows = baseline.action_refs(p)
            self.assertEqual(len(rows), 1)
            self.assertTrue(rows[0]["pinned_full_sha"])

    def test_mutable_critical_ref_is_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            populate_required(root, mutable=True)
            report = baseline.evaluate(
                root,
                candidate_sha=CANDIDATE,
                verifier_sha256=VERIFIER,
            )
            self.assertEqual(report["overall"], "FAIL")
            self.assertFalse(report["immutable_action_refs_complete"])
            self.assertGreater(len(report["critical_workflow_mutable_action_refs"]), 0)

    def test_all_full_shas_can_pass_source_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            populate_required(root, mutable=False)
            report = baseline.evaluate(
                root,
                candidate_sha=CANDIDATE,
                verifier_sha256=VERIFIER,
            )
            self.assertEqual(report["overall"], "PASS")
            self.assertTrue(report["immutable_action_refs_complete"])
            self.assertEqual(report["critical_workflow_mutable_action_refs"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)