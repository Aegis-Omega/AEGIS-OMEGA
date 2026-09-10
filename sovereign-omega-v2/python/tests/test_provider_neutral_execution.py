#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from harness.sdk.provider_neutral_execution import ADMITTED, verify_workspace  # noqa: E402

REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"
COMMIT = "a" * 40


class ProviderNeutralWorkspaceTests(TestCase):
    def test_workspace_does_not_require_claude_anchor_files(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "CONSTITUTIONAL_DECLARATION.md").write_text("constitution\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "claims.json").write_text("{}\n", encoding="utf-8")
            decision = verify_workspace(
                declared_root=root,
                cwd=root,
                expected_remote=REMOTE,
                actual_remote=REMOTE,
                project_identity="AEGIS-OMEGA",
                source_commit=COMMIT,
                operator_authorization="approval-1",
                mutation_target=root,
            )
            self.assertEqual(decision.outcome, ADMITTED)
            self.assertNotIn("REQUIRED_FILE_MISSING:.claude.json", decision.denial_codes)
            self.assertNotIn("REQUIRED_FILE_MISSING:skill-hashes.sha256", decision.denial_codes)


if __name__ == "__main__":
    main()
