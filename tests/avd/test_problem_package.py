from __future__ import annotations

from pathlib import Path

import pytest

from scripts.avd.problem_package import ProblemPackageError, ProblemPackageV1


ANCHOR_COMMIT = "d98ef00c6d65b45e253aa13eeebb6f9b1f256009"
ANCHOR_TREE = "8fa6cc600d75cd78a518a8b5b08cfb9f4e665c30"
TARGET = "sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v"
SPEC = "sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v"


def _snapshot(tmp_path: Path) -> Path:
    root = tmp_path / "snapshot"
    spec = root / SPEC
    spec.parent.mkdir(parents=True)
    spec.write_text("Require Import CornO0MorphismBridge.\n", encoding="utf-8")
    readme = root / "README.md"
    readme.write_text("historical challenge\n", encoding="utf-8")
    return root


def test_problem_digest_binds_entire_snapshot_and_public_contract(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    first = ProblemPackageV1.compute(
        snapshot_root=root,
        anchor_commit_sha=ANCHOR_COMMIT,
        anchor_tree_sha=ANCHOR_TREE,
        target_path=TARGET,
        spec_path=SPEC,
        canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
    )

    (root / "README.md").write_text("historical challenge changed\n", encoding="utf-8")
    second = ProblemPackageV1.compute(
        snapshot_root=root,
        anchor_commit_sha=ANCHOR_COMMIT,
        anchor_tree_sha=ANCHOR_TREE,
        target_path=TARGET,
        spec_path=SPEC,
        canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
    )
    assert first.h_problem != second.h_problem


def test_future_solution_presence_is_rejected(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    target = root / TARGET
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("(* leaked future solution *)\n", encoding="utf-8")

    with pytest.raises(ProblemPackageError, match="FUTURE_SOLUTION_PRESENT_IN_PROBLEM_PACKAGE"):
        ProblemPackageV1.compute(
            snapshot_root=root,
            anchor_commit_sha=ANCHOR_COMMIT,
            anchor_tree_sha=ANCHOR_TREE,
            target_path=TARGET,
            spec_path=SPEC,
            canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
        )


def test_missing_frozen_spec_is_rejected(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    (root / SPEC).unlink()
    with pytest.raises(ProblemPackageError, match="FROZEN_SPEC_MISSING"):
        ProblemPackageV1.compute(
            snapshot_root=root,
            anchor_commit_sha=ANCHOR_COMMIT,
            anchor_tree_sha=ANCHOR_TREE,
            target_path=TARGET,
            spec_path=SPEC,
            canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
        )


def test_git_metadata_and_anchor_identity_fail_closed(tmp_path: Path) -> None:
    root = _snapshot(tmp_path)
    (root / ".git").mkdir()
    with pytest.raises(ProblemPackageError, match="GIT_METADATA_FORBIDDEN"):
        ProblemPackageV1.compute(
            snapshot_root=root,
            anchor_commit_sha=ANCHOR_COMMIT,
            anchor_tree_sha=ANCHOR_TREE,
            target_path=TARGET,
            spec_path=SPEC,
            canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
        )

    (root / ".git").rmdir()
    with pytest.raises(ProblemPackageError, match="ANCHOR_COMMIT_SHA_INVALID"):
        ProblemPackageV1.compute(
            snapshot_root=root,
            anchor_commit_sha="bad",
            anchor_tree_sha=ANCHOR_TREE,
            target_path=TARGET,
            spec_path=SPEC,
            canonical_coq_logical_path='-Q sovereign-omega-v2/formal/theories/Weil ""',
        )
