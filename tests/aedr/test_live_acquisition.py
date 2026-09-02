#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import replace

import pytest

from scripts.aedr.acquisition_adapter import label_to_authority_domains, snapshot_to_evaluator
from scripts.aedr.acquisition_types import (
    RawGitCompare,
    RawPullRequestRecord,
    RawWorkflowReceipt,
    WorkflowRunConclusion,
)
from scripts.aedr.dag_model import AuthorityDomain
from scripts.aedr.snapshot_builder import DeterministicSnapshotBuilder, SnapshotIntegrityError


MAIN = "a" * 40
HEAD_1 = "1" * 40
HEAD_2 = "2" * 40
STALE = "9" * 40


def _pr(number: int, head: str, *, body: str = "", labels: tuple[str, ...] = ()) -> RawPullRequestRecord:
    return RawPullRequestRecord(
        number=number,
        head_sha=head,
        base_sha=MAIN,
        base_ref="main",
        draft=True,
        mergeable_state="clean",
        title=f"PR {number}",
        body=body,
        labels=labels,
        updated_at="2026-09-02T02:00:00Z",
    )


def _receipt(run_id: int, head: str, conclusion: WorkflowRunConclusion) -> RawWorkflowReceipt:
    return RawWorkflowReceipt(
        run_id=run_id,
        run_number=run_id,
        workflow_name=f"workflow-{run_id}",
        head_sha=head,
        conclusion=conclusion,
        completed_at="2026-09-02T02:00:00Z",
        html_url=f"https://example.invalid/runs/{run_id}",
    )


class FakeOracle:
    def __init__(
        self,
        *,
        initial_prs: list[RawPullRequestRecord],
        final_prs: list[RawPullRequestRecord] | None = None,
        initial_main: str = MAIN,
        final_main: str | None = None,
        receipts: dict[str, list[RawWorkflowReceipt]] | None = None,
    ):
        self._initial_prs = list(initial_prs)
        self._final_prs = list(final_prs if final_prs is not None else initial_prs)
        self._main_values = [initial_main, final_main or initial_main]
        self._main_calls = 0
        self._pull_calls = 0
        self._receipts = receipts or {}

    def get_main_sha(self, branch: str = "main") -> str:
        value = self._main_values[min(self._main_calls, len(self._main_values) - 1)]
        self._main_calls += 1
        return value

    def list_open_pulls(self) -> list[RawPullRequestRecord]:
        value = self._initial_prs if self._pull_calls == 0 else self._final_prs
        self._pull_calls += 1
        return list(value)

    def get_exact_head_workflow_receipts(self, head_sha: str) -> list[RawWorkflowReceipt]:
        return list(self._receipts.get(head_sha, ()))

    def compare_commits(self, base_sha: str, head_sha: str) -> RawGitCompare:
        return RawGitCompare(
            base_sha=base_sha,
            head_sha=head_sha,
            merge_base_sha=base_sha,
            ahead_by=1,
            behind_by=0,
            status="ahead",
            files_changed=(f"src/{head_sha[:4]}.py",),
        )


def test_deterministic_digest_across_unordered_runs():
    pr1 = _pr(
        1,
        HEAD_1,
        body=f"[head-sha: {HEAD_1}] [depends-on: #2]",
        labels=("domain:runtime",),
    )
    pr2 = _pr(2, HEAD_2, labels=("domain:mhp",))
    receipts_1 = [
        _receipt(20, HEAD_1, WorkflowRunConclusion.FAILURE),
        _receipt(10, HEAD_1, WorkflowRunConclusion.SUCCESS),
    ]
    receipts_2 = [_receipt(30, HEAD_2, WorkflowRunConclusion.SUCCESS)]

    a = DeterministicSnapshotBuilder(
        FakeOracle(
            initial_prs=[pr2, pr1],
            final_prs=[pr1, pr2],
            receipts={HEAD_1: list(reversed(receipts_1)), HEAD_2: receipts_2},
        )
    ).build_snapshot()
    b = DeterministicSnapshotBuilder(
        FakeOracle(
            initial_prs=[pr1, pr2],
            final_prs=[pr2, pr1],
            receipts={HEAD_1: receipts_1, HEAD_2: list(reversed(receipts_2))},
        )
    ).build_snapshot()

    assert a.snapshot_digest == b.snapshot_digest
    assert a.merkle_root == b.merkle_root
    assert a.nodes == b.nodes
    assert a.ancestry_matrix == b.ancestry_matrix


def test_concurrent_main_mutation_detection():
    oracle = FakeOracle(
        initial_prs=[_pr(1, HEAD_1)],
        initial_main=MAIN,
        final_main="b" * 40,
    )
    with pytest.raises(SnapshotIntegrityError, match="CONCURRENT_MUTATION_DETECTED: main"):
        DeterministicSnapshotBuilder(oracle).build_snapshot()


def test_concurrent_pr_head_mutation_detection():
    initial = _pr(1, HEAD_1)
    moved = replace(initial, head_sha=HEAD_2, updated_at="2026-09-02T02:01:00Z")
    oracle = FakeOracle(initial_prs=[initial], final_prs=[moved])

    with pytest.raises(SnapshotIntegrityError, match="CONCURRENT_MUTATION_DETECTED: pull_requests"):
        DeterministicSnapshotBuilder(oracle).build_snapshot()


def test_concurrent_open_pr_set_mutation_detection():
    oracle = FakeOracle(
        initial_prs=[_pr(1, HEAD_1)],
        final_prs=[_pr(1, HEAD_1), _pr(2, HEAD_2)],
    )
    with pytest.raises(SnapshotIntegrityError, match="CONCURRENT_MUTATION_DETECTED: pull_requests"):
        DeterministicSnapshotBuilder(oracle).build_snapshot()


def test_stale_workflow_receipt_exclusion():
    oracle = FakeOracle(
        initial_prs=[_pr(1, HEAD_1)],
        receipts={
            HEAD_1: [
                _receipt(1, STALE, WorkflowRunConclusion.SUCCESS),
                _receipt(2, HEAD_1, WorkflowRunConclusion.FAILURE),
            ]
        },
    )
    snapshot = DeterministicSnapshotBuilder(oracle).build_snapshot()
    node = snapshot.nodes[0]

    assert node["exact_head_green"] is False
    assert node["receipt_run_ids"] == [2]
    assert [r["head_sha"] for r in node["workflow_receipts"]] == [HEAD_1]


def test_mhp_label_maps_to_semantic_lineage_evidence():
    assert label_to_authority_domains(["domain:mhp"]) == frozenset(
        [AuthorityDomain.SEMANTIC_LINEAGE_EVIDENCE]
    )


def test_snapshot_adapter_does_not_fabricate_falsification_surface():
    oracle = FakeOracle(
        initial_prs=[
            _pr(1, HEAD_1, labels=("domain:structural",)),
            _pr(2, HEAD_2, labels=("domain:structural",)),
        ],
        receipts={
            HEAD_1: [_receipt(1, HEAD_1, WorkflowRunConclusion.SUCCESS)],
            HEAD_2: [_receipt(2, HEAD_2, WorkflowRunConclusion.SUCCESS)],
        },
    )
    evaluator = snapshot_to_evaluator(DeterministicSnapshotBuilder(oracle).build_snapshot())

    assert evaluator.evaluate_supersedes(1, 2) == (False, "MISSING_FALSIFICATION_SURFACE")
