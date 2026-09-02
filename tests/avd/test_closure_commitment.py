from __future__ import annotations

from pathlib import Path

from scripts.avd.closure_commitment import PythonClosureCommitmentV1


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_commitment_changes_when_transitive_dependency_bytes_change(tmp_path: Path) -> None:
    _write(tmp_path, "scripts/__init__.py", "")
    _write(tmp_path, "scripts/avd/__init__.py", "")
    _write(tmp_path, "scripts/avd/a.py", "from .b import VALUE\n")
    _write(tmp_path, "scripts/avd/b.py", "VALUE = 1\n")

    first = PythonClosureCommitmentV1.compute(
        repo_root=tmp_path,
        domain="VERIFIER",
        entry_modules=("scripts.avd.a",),
    )
    _write(tmp_path, "scripts/avd/b.py", "VALUE = 2\n")
    second = PythonClosureCommitmentV1.compute(
        repo_root=tmp_path,
        domain="VERIFIER",
        entry_modules=("scripts.avd.a",),
    )

    assert first.digest != second.digest
    assert first.paths == second.paths
    assert "scripts/avd/b.py" in first.paths


def test_entrypoint_identity_is_committed_even_for_same_file_closure(tmp_path: Path) -> None:
    _write(tmp_path, "scripts/__init__.py", "")
    _write(tmp_path, "scripts/avd/__init__.py", "")
    _write(tmp_path, "scripts/avd/a.py", "")

    one = PythonClosureCommitmentV1.compute(
        repo_root=tmp_path,
        domain="VERIFIER",
        entry_modules=("scripts.avd.a",),
    )
    two = PythonClosureCommitmentV1.compute(
        repo_root=tmp_path,
        domain="ORACLE",
        entry_modules=("scripts.avd.a",),
    )
    assert one.digest != two.digest


def test_real_avd_verifier_and_oracle_commitments_are_reproducible() -> None:
    repo = Path(__file__).resolve().parents[2]
    verifier_entries = (
        "scripts.avd.coq_verifier",
        "scripts.avd.tripartite_enforcer",
        "scripts.avd.receipt_validator",
        "scripts.avd.offline_toolchain",
    )
    oracle_entries = (
        "scripts.avd.mutation_calibration",
        "scripts.avd.oracle_evaluator",
    )

    v1 = PythonClosureCommitmentV1.compute(
        repo_root=repo,
        domain="VERIFIER",
        entry_modules=verifier_entries,
    )
    v2 = PythonClosureCommitmentV1.compute(
        repo_root=repo,
        domain="VERIFIER",
        entry_modules=verifier_entries,
    )
    o1 = PythonClosureCommitmentV1.compute(
        repo_root=repo,
        domain="ORACLE",
        entry_modules=oracle_entries,
    )

    assert v1 == v2
    assert len(v1.digest) == 64
    assert len(o1.digest) == 64
    assert v1.digest != o1.digest
    assert "scripts/avd/coq_verifier.py" in v1.paths
    assert "scripts/avd/mutation_calibration.py" in o1.paths
