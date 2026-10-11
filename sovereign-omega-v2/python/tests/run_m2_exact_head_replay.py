"""Fail-closed exact-head M2 regression runner; no runtime bootstrap required.

Usage: EXPECTED_HEAD_SHA="$(git rev-parse HEAD)" python tests/run_m2_exact_head_replay.py
Prints one machine-readable JSON receipt to stdout and human test output to stderr.
Never modifies the repository or starts an AEGIS subsystem.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PYTHON = ROOT / "sovereign-omega-v2" / "python"
SOURCES = (
    "sovereign-omega-v2/python/core_matrix.py",
    "sovereign-omega-v2/python/bridge.py",
    # Source-bound ingress/governance tests compile the *frozen* gate.py class.
    # Omitting this dependency from receipts makes exact-head evidence incomplete.
    "sovereign-omega-v2/python/gate.py",
    "sovereign-omega-v2/python/tests/fixtures/m2_sequence_domain_contract.json",
    "sovereign-omega-v2/python/tests/fixtures/M2_Ring_Design_Review_2026-10-11.md",
    "sovereign-omega-v2/python/tests/test_m2_layout_diagnostic.py",
    "sovereign-omega-v2/python/tests/test_m2_runtime_replay.py",
    "sovereign-omega-v2/python/tests/test_m2_mutation_guard.py",
    "sovereign-omega-v2/python/tests/run_m2_exact_head_replay.py",
    ".github/workflows/m2-layout-diagnostic.yml",
)


def _git(*args: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    return process.stdout.strip()


def main() -> int:
    expected = os.environ.get("EXPECTED_HEAD_SHA", "").strip()
    receipt = {
        "schema": "aegis.m2.exact-head-replay.v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "expected_head_sha": expected or None,
        "actual_head_sha": None,
        "tracked_files_clean": None,
        "files_sha256": {},
        "tests_run": 0,
        "failures": 0,
        "errors": 0,
        "disposition": "BLOCKED_UNBOUND_HEAD",
        "authority_effect": "NONE",
    }
    try:
        actual = _git("rev-parse", "HEAD")
        receipt["actual_head_sha"] = actual
        if not expected or len(expected) != 40 or expected != actual:
            receipt["disposition"] = "BLOCKED_HEAD_MISMATCH"
            return 2
        dirty = _git("status", "--porcelain", "--untracked-files=no", "--", *SOURCES)
        receipt["tracked_files_clean"] = not bool(dirty)
        if dirty:
            receipt["disposition"] = "BLOCKED_DIRTY_SOURCES"
            return 2
        for path in SOURCES:
            receipt["files_sha256"][path] = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()

        # Load by exact checkout path; do not depend on a global "tests" package.
        suite = unittest.TestSuite()
        for index, name in enumerate(("test_m2_layout_diagnostic.py",
                                      "test_m2_runtime_replay.py",
                                      "test_m2_mutation_guard.py")):
            path = PYTHON / "tests" / name
            spec = importlib.util.spec_from_file_location(
                "aegis_m2_exact_head_test_" + str(index), str(path))
            if spec is None or spec.loader is None:
                raise ImportError("Cannot load exact-head test file " + name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
        sink = io.StringIO()
        result = unittest.TextTestRunner(stream=sink, verbosity=2).run(suite)
        print(sink.getvalue(), file=sys.stderr)
        receipt["tests_run"] = result.testsRun
        receipt["failures"] = len(result.failures)
        receipt["errors"] = len(result.errors)
        receipt["disposition"] = "PASS" if result.wasSuccessful() and result.testsRun > 0 else "FAIL_TESTS"
        return 0 if receipt["disposition"] == "PASS" else 1
    except Exception as exc:  # preserve machine-readable BLOCKED receipt on loader errors
        receipt["disposition"] = "BLOCKED_REPLAY_ERROR"
        receipt["error_type"] = type(exc).__name__
        return 2
    finally:
        print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    raise SystemExit(main())
