"""Regression checks for exact-revision repository verification receipts.

These are ordinary Python bridge pytest tests. They invoke the real aggregator
without replacing its policy, manifest, or hash verification logic.
"""
from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VERIFIER = runpy.run_path(str(REPOSITORY_ROOT / "scripts/repository_verification.py"))
AGGREGATE = VERIFIER["aggregate"]
CENSUS_KIND = VERIFIER["CENSUS_KIND"]
RESULT_KIND = VERIFIER["RESULT_KIND"]

COMMIT = "a" * 40
TREE = "b" * 40
OTHER = "c" * 40


def evidence(tmp_path: Path, *, census_commit: str = COMMIT,
             census_tree: str = TREE, include_census: bool = True) -> None:
    if include_census:
        (tmp_path / "definition-census.json").write_text(json.dumps({
            "artifact_kind": CENSUS_KIND,
            "commit_sha": census_commit,
            "tree_sha": census_tree,
            "definition_total": 1,
        }), encoding="utf-8")
    (tmp_path / "smoke.json").write_text(json.dumps({
        "artifact_kind": RESULT_KIND,
        "suite_id": "smoke",
        "status": "PASSED",
        "commit_sha": COMMIT,
        "tree_sha": TREE,
        "executed_tests": 1,
        "skipped_tests": 0,
    }), encoding="utf-8")


def test_matching_census_and_suite_revision_is_verified(tmp_path: Path) -> None:
    evidence(tmp_path)
    receipt, _ = AGGREGATE(tmp_path, ["smoke"])
    assert receipt["status"] == "VERIFIED"
    assert receipt["commit_sha"] == COMMIT
    assert receipt["tree_sha"] == TREE


@pytest.mark.parametrize("field", ["commit", "tree"])
def test_stale_census_cannot_verify_another_revision(
    tmp_path: Path, field: str
) -> None:
    evidence(
        tmp_path,
        census_commit=OTHER if field == "commit" else COMMIT,
        census_tree=OTHER if field == "tree" else TREE,
    )
    receipt, _ = AGGREGATE(tmp_path, ["smoke"])
    assert receipt["status"] == "INCOMPLETE_OR_FAILED"


def test_missing_census_is_incomplete(tmp_path: Path) -> None:
    evidence(tmp_path, include_census=False)
    receipt, _ = AGGREGATE(tmp_path, ["smoke"])
    assert receipt["status"] == "INCOMPLETE_OR_FAILED"


def test_missing_required_suite_is_incomplete(tmp_path: Path) -> None:
    evidence(tmp_path)
    receipt, _ = AGGREGATE(tmp_path, ["smoke", "missing"])
    assert receipt["status"] == "INCOMPLETE_OR_FAILED"
    assert receipt["missing_suites"] == ["missing"]


def test_mixed_suite_commits_are_incomplete(tmp_path: Path) -> None:
    evidence(tmp_path)
    (tmp_path / "other.json").write_text(json.dumps({
        "artifact_kind": RESULT_KIND,
        "suite_id": "other",
        "status": "PASSED",
        "commit_sha": OTHER,
        "tree_sha": TREE,
        "executed_tests": 1,
        "skipped_tests": 0,
    }), encoding="utf-8")
    receipt, _ = AGGREGATE(tmp_path, ["smoke", "other"])
    assert receipt["status"] == "INCOMPLETE_OR_FAILED"
