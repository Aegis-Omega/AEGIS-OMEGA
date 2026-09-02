#!/usr/bin/env python3
from __future__ import annotations

from scripts.aedr.acquisition_adapter import snapshot_to_evaluator
from scripts.aedr.acquisition_types import MultilayerDAGSnapshot
from scripts.aedr.dag_model import FalsificationSurface


HEAD_A = "a" * 40
HEAD_B = "b" * 40
MAIN = "c" * 40


def _node(number: int, head: str, run_id: int) -> dict[str, object]:
    return {
        "number": number,
        "head_sha": head,
        "base_sha": MAIN,
        "base_ref": "main",
        "draft": True,
        "mergeable_state": "clean",
        "declared_parent_pr": None,
        "cited_head_sha": None,
        "semantic_dependencies": [],
        "labels": ["domain:structural"],
        "exact_head_green": True,
        "receipt_run_ids": [run_id],
        "workflow_receipts": [
            {
                "run_id": run_id,
                "run_number": 1,
                "workflow_name": "AEDR",
                "head_sha": head,
                "conclusion": "success",
                "completed_at": "2026-09-02T02:00:00Z",
                "html_url": "https://example.invalid/run",
            }
        ],
    }


def _snapshot() -> MultilayerDAGSnapshot:
    return MultilayerDAGSnapshot(
        schema_version="AEDR-SNAPSHOT-V1",
        global_main_sha=MAIN,
        captured_at_utc="2026-09-02T02:00:00Z",
        node_count=2,
        nodes=(_node(1, HEAD_A, 10), _node(2, HEAD_B, 20)),
        ancestry_matrix=(),
        merkle_root="d" * 64,
        snapshot_digest="e" * 64,
    )


def _surface(head: str) -> FalsificationSurface:
    return FalsificationSurface(
        source_head_sha=head,
        required_behavior_ids=frozenset(["B1"]),
        required_falsifier_ids=frozenset(["F1"]),
        unique_non_generated_paths=frozenset(["src/a.py"]),
        verified_behavior_ids=frozenset(["B1"]),
        verified_falsifier_ids=frozenset(["F1"]),
        assumption_debt_ids=frozenset(),
        security_exposure_ids=frozenset(),
        exact_head_receipt_green=True,
    )


def test_default_snapshot_adapter_remains_fail_closed_without_surface_factory():
    evaluator = snapshot_to_evaluator(_snapshot())
    assert evaluator.evaluate_supersedes(1, 2) == (False, "MISSING_FALSIFICATION_SURFACE")


def test_opt_in_surface_factory_receives_exact_snapshot_nodes_and_can_supply_evaluator_surface():
    observed = {}

    def factory(nodes):
        observed.update({number: node.head_sha for number, node in nodes.items()})
        surfaces = {1: _surface(HEAD_A), 2: _surface(HEAD_B)}
        return lambda pr_number: surfaces.get(pr_number)

    evaluator = snapshot_to_evaluator(_snapshot(), surface_oracle_factory=factory)

    assert observed == {1: HEAD_A, 2: HEAD_B}
    assert evaluator.evaluate_supersedes(1, 2) == (True, "DOMINANCE_VERIFIED")
