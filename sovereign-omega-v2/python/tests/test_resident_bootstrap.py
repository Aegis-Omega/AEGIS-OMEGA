#!/usr/bin/env python3
"""Behavior tests for the resident service repository bootstrap."""
from __future__ import annotations

from pathlib import Path
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import resident_bootstrap
from resident_bootstrap import ResidentBootstrapError, prepare_resident_repository


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class ResidentBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.target = Path(self.tmp.name) / "resident-repository"
        self.source.mkdir()
        _git("init", "-q", "-b", "main", cwd=self.source)
        _git("config", "user.email", "bootstrap@example.invalid", cwd=self.source)
        _git("config", "user.name", "Bootstrap Tests", cwd=self.source)
        (self.source / "observed.txt").write_text("v1\n", encoding="utf-8")
        _git("add", "observed.txt", cwd=self.source)
        _git("commit", "-qm", "v1", cwd=self.source)

    def test_first_start_creates_owned_sensor_clone_at_exact_branch_head(self) -> None:
        expected_head = _git("rev-parse", "HEAD", cwd=self.source)

        observed_head = prepare_resident_repository(
            repository_url=str(self.source),
            repository_root=self.target,
            branch="main",
        )

        self.assertEqual(observed_head, expected_head)
        self.assertEqual(_git("rev-parse", "HEAD", cwd=self.target), expected_head)
        self.assertEqual(_git("status", "--porcelain", cwd=self.target), "")

    def test_restart_fetches_new_exact_head_without_replacing_owned_clone(self) -> None:
        prepare_resident_repository(
            repository_url=str(self.source),
            repository_root=self.target,
            branch="main",
        )
        (self.source / "observed.txt").write_text("v2\n", encoding="utf-8")
        _git("add", "observed.txt", cwd=self.source)
        _git("commit", "-qm", "v2", cwd=self.source)
        expected_head = _git("rev-parse", "HEAD", cwd=self.source)

        observed_head = prepare_resident_repository(
            repository_url=str(self.source),
            repository_root=self.target,
            branch="main",
        )

        self.assertEqual(observed_head, expected_head)
        self.assertEqual((self.target / "observed.txt").read_text(encoding="utf-8"), "v2\n")

    def test_dirty_owned_clone_fails_closed_instead_of_overwriting_state(self) -> None:
        prepare_resident_repository(
            repository_url=str(self.source),
            repository_root=self.target,
            branch="main",
        )
        (self.target / "observed.txt").write_text("local mutation\n", encoding="utf-8")

        with self.assertRaisesRegex(ResidentBootstrapError, "REPOSITORY_DIRTY"):
            prepare_resident_repository(
                repository_url=str(self.source),
                repository_root=self.target,
                branch="main",
            )

        self.assertEqual((self.target / "observed.txt").read_text(encoding="utf-8"), "local mutation\n")

    def test_non_repository_target_and_remote_mismatch_fail_closed(self) -> None:
        self.target.mkdir()
        (self.target / "foreign.txt").write_text("do not overwrite", encoding="utf-8")
        with self.assertRaisesRegex(ResidentBootstrapError, "TARGET_NOT_OWNED_REPOSITORY"):
            prepare_resident_repository(
                repository_url=str(self.source),
                repository_root=self.target,
                branch="main",
            )

        second_source = Path(self.tmp.name) / "other"
        second_source.mkdir()
        _git("init", "-q", "-b", "main", cwd=second_source)
        _git("config", "user.email", "other@example.invalid", cwd=second_source)
        _git("config", "user.name", "Other", cwd=second_source)
        (second_source / "file.txt").write_text("other\n", encoding="utf-8")
        _git("add", "file.txt", cwd=second_source)
        _git("commit", "-qm", "other", cwd=second_source)

        clean_target = Path(self.tmp.name) / "clean-target"
        prepare_resident_repository(
            repository_url=str(self.source),
            repository_root=clean_target,
            branch="main",
        )
        with self.assertRaisesRegex(ResidentBootstrapError, "REMOTE_MISMATCH"):
            prepare_resident_repository(
                repository_url=str(second_source),
                repository_root=clean_target,
                branch="main",
            )

    def test_sensor_bootstrap_failure_keeps_bridge_available_and_reports_unknown(self) -> None:
        class ExecIntercept(RuntimeError):
            pass

        output = io.StringIO()
        with (
            patch.dict(
                os.environ,
                {
                    "AEGIS_RESIDENT_REPOSITORY_URL": str(self.source),
                    "AEGIS_RESIDENT_REPOSITORY_ROOT": str(self.target),
                    "AEGIS_RESIDENT_REPOSITORY_BRANCH": "main",
                },
            ),
            patch.object(
                resident_bootstrap,
                "prepare_resident_repository",
                side_effect=ResidentBootstrapError("REPOSITORY_FETCH_FAILED"),
            ),
            patch.object(
                resident_bootstrap.os,
                "execv",
                side_effect=ExecIntercept("bridge exec"),
            ) as execv,
            contextlib.redirect_stdout(output),
        ):
            with self.assertRaisesRegex(ExecIntercept, "bridge exec"):
                resident_bootstrap.main()
            self.assertEqual(os.environ["AEGIS_RESIDENT_BOOTSTRAP_STATUS"], "UNKNOWN")

        self.assertIn('"knowledge_decision": "UNKNOWN"', output.getvalue())
        execv.assert_called_once()


if __name__ == "__main__":
    unittest.main()
