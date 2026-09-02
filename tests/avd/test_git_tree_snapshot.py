from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.avd.git_tree_snapshot import GitTreeSnapshotError, GitTreeSnapshotV1


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc.stdout.strip()


def _historical_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "avd@example.invalid")
    _git(repo, "config", "user.name", "AVD Test")

    spec = repo / "frozen" / "spec.v"
    spec.parent.mkdir(parents=True)
    spec.write_text("Check historical_contract.\n", encoding="utf-8")
    (repo / "README.md").write_text("historical challenge\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "historical anchor")

    commit = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    return repo, commit, tree


def test_exact_git_tree_is_exported_without_git_metadata(tmp_path: Path) -> None:
    repo, commit, tree = _historical_repo(tmp_path)
    snapshot = tmp_path / "snapshot"

    bound = GitTreeSnapshotV1.export(
        repo_root=repo,
        snapshot_root=snapshot,
        anchor_commit_sha=commit,
        expected_tree_sha=tree,
        required_path="frozen/spec.v",
        forbidden_path="future/solution.v",
    )

    assert bound.anchor_commit_sha == commit
    assert bound.anchor_tree_sha == tree
    assert bound.git_tree_verified is True
    assert bound.forbidden_path_absent is True
    assert (snapshot / "frozen/spec.v").read_text(encoding="utf-8") == "Check historical_contract.\n"
    assert (snapshot / "README.md").read_text(encoding="utf-8") == "historical challenge\n"
    assert not (snapshot / ".git").exists()


def test_tree_identity_mismatch_fails_closed(tmp_path: Path) -> None:
    repo, commit, _ = _historical_repo(tmp_path)

    with pytest.raises(GitTreeSnapshotError, match="ANCHOR_TREE_MISMATCH"):
        GitTreeSnapshotV1.export(
            repo_root=repo,
            snapshot_root=tmp_path / "snapshot",
            anchor_commit_sha=commit,
            expected_tree_sha="0" * 40,
            required_path="frozen/spec.v",
            forbidden_path="future/solution.v",
        )


def test_future_solution_in_anchor_tree_is_rejected(tmp_path: Path) -> None:
    repo, _, _ = _historical_repo(tmp_path)
    target = repo / "future" / "solution.v"
    target.parent.mkdir(parents=True)
    target.write_text("future solution\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "leaked future")
    commit = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")

    with pytest.raises(GitTreeSnapshotError, match="FORBIDDEN_PATH_PRESENT_IN_ANCHOR_TREE"):
        GitTreeSnapshotV1.export(
            repo_root=repo,
            snapshot_root=tmp_path / "snapshot",
            anchor_commit_sha=commit,
            expected_tree_sha=tree,
            required_path="frozen/spec.v",
            forbidden_path="future/solution.v",
        )
