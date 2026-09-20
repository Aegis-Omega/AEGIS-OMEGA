#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_MODULE = ROOT / "harness" / "sdk" / "archive_coverage.py"
KNOWLEDGE_MODULE = ROOT / "harness" / "sdk" / "repository_knowledge.py"
REPORT = ROOT / "reports" / "archive-coverage-v1.json"
EXPORTER = ROOT / "scripts" / "export-operations-center-sources.py"
UI_PROJECTION = ROOT / "reports" / "operations-center-sources-v1.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


class ArchiveCoverageContract(unittest.TestCase):
    def setUp(self) -> None:
        self.coverage = load_module("archive_coverage_contract", COVERAGE_MODULE)
        self.document = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_checked_in_report_is_verified_and_projects_honestly(self) -> None:
        result = self.coverage.verify_document(self.document)
        self.assertEqual(result, {"status": "VERIFIED", "reason_codes": []})

        projection = self.coverage.project_for_operations_center(self.document)
        self.assertEqual(projection["catalogue_source_count"], 38)
        self.assertEqual(projection["catalogue_completeness"], "INCOMPLETE_SELECTED_SAMPLE")
        self.assertEqual(projection["archive_project_file_count"], 1163)
        self.assertEqual(projection["coverage_group_count"], 24)
        self.assertEqual(projection["unsurfaced_no_counterpart_count"], 23)
        self.assertEqual(
            projection["warning"],
            "CATALOGUE_IS_SELECTED_SAMPLE_NOT_COMPLETE_INVENTORY",
        )
        self.assertEqual(projection["authority_effect"], "NONE")

    def test_false_completeness_is_denied_even_with_recomputed_root(self) -> None:
        tampered = copy.deepcopy(self.document)
        tampered["production_catalogue"]["is_complete_inventory"] = True
        unsigned = dict(tampered)
        unsigned.pop("coverage_root", None)
        tampered["coverage_root"] = self.coverage.digest(unsigned)

        result = self.coverage.verify_document(tampered)
        self.assertEqual(result["status"], "DENIED")
        self.assertIn("ARCHIVE_COVERAGE_FALSE_COMPLETENESS", result["reason_codes"])

    def test_no_counterpart_count_must_match_exact_path_list(self) -> None:
        tampered = copy.deepcopy(self.document)
        tampered["coverage"]["new_uncatalogued_no_counterpart_count"] = 22
        unsigned = dict(tampered)
        unsigned.pop("coverage_root", None)
        tampered["coverage_root"] = self.coverage.digest(unsigned)

        result = self.coverage.verify_document(tampered)
        self.assertEqual(result["status"], "DENIED")
        self.assertIn(
            "ARCHIVE_COVERAGE_NO_COUNTERPART_COUNT_MISMATCH",
            result["reason_codes"],
        )

    def test_authority_escalation_is_denied(self) -> None:
        tampered = copy.deepcopy(self.document)
        tampered["authority_effect"] = "ADMIT"
        unsigned = dict(tampered)
        unsigned.pop("coverage_root", None)
        tampered["coverage_root"] = self.coverage.digest(unsigned)

        result = self.coverage.verify_document(tampered)
        self.assertEqual(result["status"], "DENIED")
        self.assertIn("ARCHIVE_COVERAGE_AUTHORITY_ESCALATION", result["reason_codes"])

    def test_checked_in_ui_projection_is_exact_generator_output(self) -> None:
        exporter = load_module("operations_center_sources_exporter", EXPORTER)
        expected = exporter.build_projection(ROOT, self.document)
        actual = json.loads(UI_PROJECTION.read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)
        self.assertEqual(
            actual["projection_root"],
            "4833e006bb21f3f925e74d73aed44fbe800ad1a0f0c2c7d7ac4c3c6ea79515e6",
        )
        self.assertEqual(len(actual["findings"]), 24)
        self.assertEqual(len(actual["unsurfaced_paths"]), 23)
        self.assertEqual(
            [card["value"] for card in actual["cards"]],
            [38, 1163, 24, 23],
        )
        self.assertEqual(actual["cards"][0]["label"], "Katalogizirani izvori")
        self.assertNotIn("arhiva + Git", UI_PROJECTION.read_text(encoding="utf-8"))
        self.assertEqual(actual["authority_effect"], "NONE")
        self.assertEqual(
            actual["consumer_contract"]["legacy_label_to_replace"],
            "38 arhiva + Git",
        )
        self.assertEqual(
            actual["consumer_contract"]["invalid_source_behavior"],
            "SHOW_INVALID_OR_STALE; DO_NOT_FALL_BACK_TO_COMPLETE_INVENTORY_CLAIM",
        )

    def test_repository_knowledge_surfaces_verified_projection(self) -> None:
        knowledge = load_module("repository_knowledge_with_archive", KNOWLEDGE_MODULE)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            git(repo, "config", "user.email", "aegis@example.invalid")
            git(repo, "config", "user.name", "AEGIS Test")
            report = repo / "reports" / "archive-coverage-v1.json"
            report.parent.mkdir(parents=True)
            report.write_text(REPORT.read_text(encoding="utf-8"), encoding="utf-8")
            (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "-m", "fixture")

            snapshot = knowledge.build_snapshot(
                repo,
                repository_id=1095915905,
                repository_full_name="Aegis-Omega/AEGIS-OMEGA",
            )
            coverage = snapshot["archive_coverage"]
            self.assertEqual(coverage["state"], "VERIFIED_EVIDENCE_PACKAGE_SNAPSHOT")
            self.assertEqual(coverage["catalogue_source_count"], 38)
            self.assertEqual(coverage["archive_project_file_count"], 1163)
            self.assertEqual(coverage["coverage_group_count"], 24)
            self.assertEqual(coverage["unsurfaced_no_counterpart_count"], 23)

            verified = knowledge.verify_snapshot_document(
                snapshot,
                expected_repository_id=1095915905,
            )
            self.assertEqual(verified["status"], "ESTABLISHED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
