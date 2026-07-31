"""Pytest collection boundary for the mixed Python verification corpus.

Historical AEGIS contract tests include executable scripts that intentionally run
at module load and terminate with ``sys.exit``. Importing those files as pytest
modules aborts collection even when the script reports success. They are not
silently skipped: ``test_standalone_contract_scripts.py`` executes each one in an
isolated subprocess and binds its exit status and output to a pytest result.
"""
from __future__ import annotations

from pathlib import Path

_WRAPPER = "test_standalone_contract_scripts.py"


def is_standalone_contract_script(path: Path) -> bool:
    if path.name == _WRAPPER or not path.name.startswith("test_") or path.suffix != ".py":
        return False
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "sys.exit(" in source


def pytest_ignore_collect(collection_path: Path, config):  # type: ignore[no-untyped-def]
    del config
    return is_standalone_contract_script(Path(collection_path))
