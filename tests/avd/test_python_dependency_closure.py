from __future__ import annotations

from pathlib import Path

import pytest

from scripts.avd.python_closure import PythonClosureError, discover_python_closure


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_relative_and_absolute_local_imports_form_one_deterministic_closure(tmp_path: Path) -> None:
    _write(tmp_path, "scripts/__init__.py", "")
    _write(tmp_path, "scripts/avd/__init__.py", "")
    _write(
        tmp_path,
        "scripts/avd/a.py",
        "import hashlib\nfrom . import b\nfrom .c import C\n",
    )
    _write(tmp_path, "scripts/avd/b.py", "from scripts.avd.c import C\n")
    _write(tmp_path, "scripts/avd/c.py", "C = 1\n")

    closure = discover_python_closure(tmp_path, ("scripts.avd.a",))
    assert closure == (
        "scripts/avd/a.py",
        "scripts/avd/b.py",
        "scripts/avd/c.py",
    )


def test_unresolved_local_import_fails_closed(tmp_path: Path) -> None:
    _write(tmp_path, "scripts/__init__.py", "")
    _write(tmp_path, "scripts/avd/__init__.py", "")
    _write(tmp_path, "scripts/avd/a.py", "from .missing import x\n")

    with pytest.raises(PythonClosureError, match="UNRESOLVED_LOCAL_IMPORT"):
        discover_python_closure(tmp_path, ("scripts.avd.a",))


def test_dynamic_import_in_committed_runtime_fails_closed(tmp_path: Path) -> None:
    _write(tmp_path, "scripts/__init__.py", "")
    _write(tmp_path, "scripts/avd/__init__.py", "")
    _write(
        tmp_path,
        "scripts/avd/a.py",
        "import importlib\nmod = importlib.import_module('scripts.avd.hidden')\n",
    )
    _write(tmp_path, "scripts/avd/hidden.py", "X = 1\n")

    with pytest.raises(PythonClosureError, match="DYNAMIC_IMPORT_FORBIDDEN"):
        discover_python_closure(tmp_path, ("scripts.avd.a",))


def test_real_verifier_and_oracle_entrypoints_have_closed_local_dependency_graph() -> None:
    repo = Path(__file__).resolve().parents[2]
    verifier = discover_python_closure(
        repo,
        (
            "scripts.avd.coq_verifier",
            "scripts.avd.tripartite_enforcer",
            "scripts.avd.receipt_validator",
            "scripts.avd.offline_toolchain",
        ),
    )
    oracle = discover_python_closure(
        repo,
        (
            "scripts.avd.mutation_calibration",
            "scripts.avd.oracle_evaluator",
        ),
    )

    assert "scripts/avd/coq_verifier.py" in verifier
    assert "scripts/avd/coq_signature_contract.py" in verifier
    assert "scripts/avd/bundle_commitment.py" in verifier
    assert "scripts/avd/mutation_calibration.py" in oracle
    assert "scripts/avd/mutation_decision.py" in oracle
    assert "scripts/avd/submission_policy.py" in oracle
