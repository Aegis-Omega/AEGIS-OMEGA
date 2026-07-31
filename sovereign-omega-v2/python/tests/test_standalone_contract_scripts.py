"""Execute legacy standalone contract tests without importing them into pytest."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from conftest import is_standalone_contract_script

TEST_DIRECTORY = Path(__file__).resolve().parent
STANDALONE_SCRIPTS = tuple(
    path
    for path in sorted(TEST_DIRECTORY.glob("test_*.py"))
    if is_standalone_contract_script(path)
)


@pytest.mark.parametrize(
    "script_path",
    STANDALONE_SCRIPTS,
    ids=lambda path: path.name,
)
def test_standalone_contract_script(script_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=TEST_DIRECTORY.parent,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    assert completed.returncode == 0, (
        f"standalone contract script failed: {script_path.name}\n{output}"
    )
