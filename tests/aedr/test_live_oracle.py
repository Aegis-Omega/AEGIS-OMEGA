#!/usr/bin/env python3
from __future__ import annotations

from scripts.aedr.live_oracle import GitHubLiveOracle
from scripts.aedr.acquisition_types import WorkflowRunConclusion


HEAD = "1" * 40
STALE = "9" * 40


def _run(run_id: int, head_sha: str, *, status: str, conclusion: str | None):
    return {
        "id": run_id,
        "run_number": run_id,
        "name": f"workflow-{run_id}",
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "updated_at": "2026-09-02T02:00:00Z",
        "html_url": f"https://example.invalid/runs/{run_id}",
    }


def test_oracle_filters_mismatched_head_even_if_upstream_query_returns_it():
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA")
    oracle._get = lambda endpoint, params=None: {
        "workflow_runs": [
            _run(1, STALE, status="completed", conclusion="success"),
            _run(2, HEAD, status="completed", conclusion="failure"),
        ]
    }

    receipts = oracle.get_exact_head_workflow_receipts(HEAD)

    assert [receipt.run_id for receipt in receipts] == [2]
    assert receipts[0].head_sha == HEAD
    assert receipts[0].conclusion == WorkflowRunConclusion.FAILURE


def test_oracle_maps_nonterminal_status_without_promoting_to_green():
    oracle = GitHubLiveOracle("Aegis-Omega", "AEGIS-OMEGA")
    oracle._get = lambda endpoint, params=None: {
        "workflow_runs": [
            _run(3, HEAD, status="queued", conclusion=None),
            _run(4, HEAD, status="in_progress", conclusion=None),
        ]
    }

    receipts = oracle.get_exact_head_workflow_receipts(HEAD)

    assert [receipt.conclusion for receipt in receipts] == [
        WorkflowRunConclusion.QUEUED,
        WorkflowRunConclusion.IN_PROGRESS,
    ]
    assert not any(receipt.is_terminal_green_for(HEAD) for receipt in receipts)
