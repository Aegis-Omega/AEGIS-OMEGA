from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from agents import coordinator  # noqa: E402
from harness.sdk.skill_authority import compute_registry_root  # noqa: E402


def skill(
    skill_id: str,
    *,
    runs: int,
    state: str,
    confidence: float,
    failure: float,
    recency: float,
    evidence: Any = "evidence.md",
    prior: float | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "skill_id": skill_id,
        "label": skill_id,
        "domain": "test",
        "tier": "T2",
        "declared_tier": "T2",
        "observation_state": state,
        "confidence": confidence,
        "validated_runs": runs,
        "failure_rate": failure,
        "failure_rate_observed": failure if runs else None,
        "recency_score": recency,
        "evidence_refs": [evidence],
        "last_validated": "2026-07-19T00:00:00+00:00" if runs else None,
    }
    if prior is not None:
        value["documentation_prior"] = prior
    return value


def registry(skills: list[dict[str, Any]]) -> dict[str, Any]:
    tree: dict[str, Any] = {
        "schema_version": "2.0.0",
        "version": "2.0.0",
        "phase": 1,
        "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
        "source_commit": "a" * 40,
        "doc_count": 1,
        "skills": skills,
    }
    root = compute_registry_root(tree)
    tree["registry_root"] = root
    tree["genesis_seal"] = root
    return tree


def write_registry(tmp_path: Path, tree: dict[str, Any]) -> Path:
    path = tmp_path / "skill_tree.json"
    path.write_text(json.dumps(tree), encoding="utf-8")
    return path


def router(
    tmp_path: Path,
    tree: dict[str, Any],
    capability_map: dict[str, str],
) -> coordinator.SkillRouter:
    (tmp_path / "evidence.md").write_text("# evidence\n", encoding="utf-8")
    return coordinator.SkillRouter(
        skill_tree_path=write_registry(tmp_path, tree),
        repo_root=tmp_path,
        capability_map=capability_map,
    )


def test_unknown_capability_receives_zero_authority(tmp_path: Path) -> None:
    instance = router(
        tmp_path,
        registry([skill("observed", runs=3, state="OBSERVED", confidence=.8, failure=0, recency=1)]),
        {"known": "observed"},
    )
    decision = instance.capability_decision("unknown")
    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert "UNMAPPED_CAPABILITY" in decision.reason_codes


def test_zero_run_never_outranks_observed(tmp_path: Path) -> None:
    instance = router(
        tmp_path,
        registry([
            skill("declared", runs=0, state="UNOBSERVED", confidence=0, failure=0, recency=0, prior=.99),
            skill("observed", runs=3, state="OBSERVED", confidence=.8, failure=.1, recency=1),
        ]),
        {"declared_cap": "declared", "observed_cap": "observed"},
    )
    definitions = {
        coordinator.AgentRole.ENGINEERING.value: {"capabilities": ["declared_cap"]},
        coordinator.AgentRole.AI_SAFETY.value: {"capabilities": ["observed_cap"]},
    }
    denied = instance.role_routing_receipt(
        coordinator.AgentRole.ENGINEERING,
        "perform observed work",
        definitions,
    )
    admitted = instance.role_routing_receipt(
        coordinator.AgentRole.AI_SAFETY,
        "perform observed work",
        definitions,
    )
    assert denied.outcome == "DENIED"
    assert denied.authority_score == 0.0
    assert admitted.outcome == "ADMITTED"
    assert admitted.authority_score == pytest.approx(.72)


def test_documentation_prior_cannot_grant_authority(tmp_path: Path) -> None:
    instance = router(
        tmp_path,
        registry([skill("prose", runs=0, state="UNOBSERVED", confidence=0, failure=0, recency=0, prior=1)]),
        {"prose_cap": "prose"},
    )
    decision = instance.capability_decision("prose_cap")
    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert decision.observation_state == "UNOBSERVED"


def test_fewer_than_three_runs_remains_denied(tmp_path: Path) -> None:
    instance = router(
        tmp_path,
        registry([skill("partial", runs=2, state="OBSERVED", confidence=1, failure=0, recency=1)]),
        {"partial_cap": "partial"},
    )
    decision = instance.capability_decision("partial_cap")
    assert decision.authority_score == 0.0
    assert "INSUFFICIENT_VALIDATED_RUNS" in decision.reason_codes


def test_repository_escape_is_denied(tmp_path: Path) -> None:
    (tmp_path.parent / "outside.md").write_text("outside\n", encoding="utf-8")
    tree = registry([
        skill("escape", runs=3, state="OBSERVED", confidence=1, failure=0, recency=1, evidence="../outside.md")
    ])
    instance = coordinator.SkillRouter(
        skill_tree_path=write_registry(tmp_path, tree),
        repo_root=tmp_path,
        capability_map={"escape_cap": "escape"},
    )
    decision = instance.capability_decision("escape_cap")
    assert decision.authority_score == 0.0
    assert any(code.startswith("EVIDENCE_OUTSIDE_REPOSITORY") for code in decision.reason_codes)


def test_malformed_registry_cannot_restore_fallback(tmp_path: Path) -> None:
    path = tmp_path / "skill_tree.json"
    path.write_text("{not-json", encoding="utf-8")
    instance = coordinator.SkillRouter(
        skill_tree_path=path,
        repo_root=tmp_path,
        capability_map={"known": "observed"},
    )
    first = instance.capability_decision("known")
    second = instance.capability_decision("known")
    assert first.authority_score == 0.0
    assert "REGISTRY_JSON_MALFORMED" in first.reason_codes
    assert first.receipt_hash == second.receipt_hash


def test_identical_inputs_produce_identical_routing_receipts(tmp_path: Path) -> None:
    instance = router(
        tmp_path,
        registry([skill("declared", runs=0, state="UNOBSERVED", confidence=0, failure=0, recency=0)]),
        {"declared_cap": "declared"},
    )
    definitions = {
        coordinator.AgentRole.ENGINEERING.value: {"capabilities": ["declared_cap"]},
    }
    first_cap = instance.capability_decision("declared_cap")
    second_cap = instance.capability_decision("declared_cap")
    first_role = instance.role_routing_receipt(coordinator.AgentRole.ENGINEERING, "same task", definitions)
    second_role = instance.role_routing_receipt(coordinator.AgentRole.ENGINEERING, "same task", definitions)
    assert first_cap.receipt_hash == second_cap.receipt_hash
    assert first_role.receipt_hash == second_role.receipt_hash


def test_dispatch_does_not_execute_denied_role(tmp_path: Path, monkeypatch: Any) -> None:
    instance = router(
        tmp_path,
        registry([skill("declared", runs=0, state="UNOBSERVED", confidence=0, failure=0, recency=0)]),
        {"declared_cap": "declared"},
    )
    role = coordinator.AgentRole.ENGINEERING
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(
        coordinator._legacy,
        "_load_agent_defs",
        lambda: {"agents": {role.value: {"capabilities": ["declared_cap"]}}},
    )
    monkeypatch.setattr(
        coordinator._legacy,
        "_event_to_instruction",
        lambda event_type, payload, candidate_role: "same task",
    )

    async def forbidden_run_agent(task: Any) -> Any:
        raise AssertionError("denied role must not execute")

    monkeypatch.setattr(coordinator._legacy, "run_agent", forbidden_run_agent)
    assert asyncio.run(coordinator.dispatch_event("test", {})) == []
    receipts = coordinator.last_dispatch_receipts()
    assert receipts[0]["outcome"] == "DENIED"
    assert receipts[0]["authority_score"] == 0.0
