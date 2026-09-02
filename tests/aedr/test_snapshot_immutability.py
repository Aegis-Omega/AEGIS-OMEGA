#!/usr/bin/env python3
from __future__ import annotations

import pytest

from scripts.aedr.acquisition_types import RawGitCompare, RawPullRequestRecord
from scripts.aedr.snapshot_builder import DeterministicSnapshotBuilder


MAIN = "a" * 40
HEAD = "1" * 40


class OnePROracle:
    def get_main_sha(self, branch: str = "main") -> str:
        return MAIN

    def list_open_pulls(self):
        return [
            RawPullRequestRecord(
                number=1,
                head_sha=HEAD,
                base_sha=MAIN,
                base_ref="main",
                draft=True,
                mergeable_state="clean",
                title="immutable",
                body="",
                labels=("domain:structural",),
                updated_at="2026-09-02T02:00:00Z",
            )
        ]

    def get_exact_head_workflow_receipts(self, head_sha: str):
        return []

    def compare_commits(self, base_sha: str, head_sha: str):
        return RawGitCompare(
            base_sha=base_sha,
            head_sha=head_sha,
            merge_base_sha=base_sha,
            ahead_by=1,
            behind_by=0,
            status="ahead",
            files_changed=("src/a.py",),
        )


def test_digest_bound_snapshot_payload_is_deeply_immutable():
    snapshot = DeterministicSnapshotBuilder(OnePROracle()).build_snapshot()

    with pytest.raises(TypeError):
        snapshot.nodes[0]["number"] = 999

    with pytest.raises(TypeError):
        snapshot.nodes[0]["receipt_run_ids"].append(999)

    with pytest.raises(TypeError):
        snapshot.ancestry_matrix[0]["files_changed"].append("src/evil.py")
