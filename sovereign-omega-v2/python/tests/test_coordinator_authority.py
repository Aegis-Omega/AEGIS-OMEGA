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


def router(tmp_path: Path, capability_map: dict[str, str] | None = None) -> coordinator.SkillRouter:
    path = tmp_path / "skill_tree.json"
    path.write_text(json.dumps({"schema_version": "2.0.0", "skills": []}), encoding="utf-8")
    return coordinator.SkillRouter(
        skill_tree_path=path,
        repo_root=tmp_path,
        capability_map=capability_map or {},
    )


def denied_decision(code: str, *, root: str = "1" * 64) -> dict[str, Any]:
    return {
        "outcome": "DENIED",
        "authority_score": "0.000000",
        "denial_codes": [code],
        "decision_root": root,
        "receipt_root": "2" * 64,
    }


def admitted_decision(score: str = "0.720000", *, root: str = "3" * 64) -> dict[str, Any]:
    return {
        "outcome": "ADMITTED",
        "authority_score": score,
        "denial_codes": [],
        "decision_root": root,
        "receipt_root": "4" * 64,
    }


def test_missing_execution_identity_fails_closed(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.delenv("AEGIS_EXECUTION_IDENTITY_JSON", raising=False)
    instance = router(tmp_path, {"known": "observed"})
    decision = instance.capability_decision("unknown")
    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert "IDENTITY_UNAVAILABLE" in decision.reason_codes


def test_local_registry_or_documentation_prior_cannot_grant_authority(tmp_path: Path, monkeypatch: Any) -> None:
    tree = {
        "schema_version": "2.0.0",
        "skills": [{
            "skill_id": "prose",
            "observation_state": "OBSERVED",
            "validated_runs": 999,
            "confidence": 1.0,
            "recency_score": 1.0,
            "failure_rate": 0.0,
            "documentation_prior": 1.0,
        }],
    }
    path = tmp_path / "skill_tree.json"
    path.write_text(json.dumps(tree), encoding="utf-8")
    monkeypatch.delenv("AEGIS_EXECUTION_IDENTITY_JSON", raising=False)
    instance = coordinator.SkillRouter(skill_tree_path=path, repo_root=tmp_path, capability_map={"prose_cap": "prose"})
    decision = instance.capability_decision("prose_cap")
    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert "IDENTITY_UNAVAILABLE" in decision.reason_codes


def test_central_evaluator_denial_is_propagated_exactly(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    def central(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return denied_decision("INSUFFICIENT_VALIDATED_RUNS")

    monkeypatch.setattr(coordinator, "authorize_from_environment", central)
    instance = router(tmp_path, {"partial_cap": "partial"})
    decision = instance.capability_decision("partial_cap")
    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert decision.reason_codes == ("INSUFFICIENT_VALIDATED_RUNS",)
    assert calls[0]["action_class"] == "D1"
    assert calls[0]["authority_domain"] == "agent:dispatch"
    assert calls[0]["requested_capability"] == "coordinator.dispatch"
    assert calls[0]["tool"] == "agents.coordinator:dispatch"


def test_central_evaluator_admission_is_the_only_score_source(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: admitted_decision("0.720000"))
    instance = router(tmp_path, {"observed_cap": "observed"})
    decision = instance.capability_decision("observed_cap")
    assert decision.outcome == "ADMITTED"
    assert decision.authority_score == pytest.approx(0.72)
    assert decision.observation_state == "CENTRAL_AUTHORITY"


def test_malformed_local_registry_cannot_restore_fallback(tmp_path: Path, monkeypatch: Any) -> None:
    path = tmp_path / "skill_tree.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: denied_decision("AUTHORITY_SERVICE_UNAVAILABLE"))
    instance = coordinator.SkillRouter(skill_tree_path=path, repo_root=tmp_path, capability_map={"known": "observed"})
    first = instance.capability_decision("known")
    second = instance.capability_decision("known")
    assert first.authority_score == 0.0
    assert first.reason_codes == ("AUTHORITY_SERVICE_UNAVAILABLE",)
    assert first.receipt_hash == second.receipt_hash


def test_identical_central_inputs_produce_identical_routing_receipts(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: denied_decision("UNMAPPED_CAPABILITY"))
    instance = router(tmp_path, {"declared_cap": "declared"})
    definitions = {coordinator.AgentRole.ENGINEERING.value: {"capabilities": ["declared_cap"]}}
    first_cap = instance.capability_decision("declared_cap")
    second_cap = instance.capability_decision("declared_cap")
    first_role = instance.role_routing_receipt(coordinator.AgentRole.ENGINEERING, "same task", definitions)
    second_role = instance.role_routing_receipt(coordinator.AgentRole.ENGINEERING, "same task", definitions)
    assert first_cap.receipt_hash == second_cap.receipt_hash
    assert first_role.receipt_hash == second_role.receipt_hash


def test_dispatch_does_not_execute_denied_role(tmp_path: Path, monkeypatch: Any) -> None:
    instance = router(tmp_path, {"declared_cap": "declared"})
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: denied_decision("IDENTITY_UNAVAILABLE"))
    role = coordinator.AgentRole.ENGINEERING
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {role.value: {"capabilities": ["declared_cap"]}}})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")

    async def forbidden_run_agent(_task: Any) -> Any:
        raise AssertionError("denied role must not execute")

    monkeypatch.setattr(coordinator._legacy, "run_agent", forbidden_run_agent)
    assert asyncio.run(coordinator.dispatch_event("test", {})) == []
    receipts = coordinator.last_dispatch_receipts()
    assert receipts[0]["outcome"] == "DENIED"
    assert receipts[0]["authority_score"] == 0.0


def test_dispatch_executes_only_after_central_admission(tmp_path: Path, monkeypatch: Any) -> None:
    instance = router(tmp_path, {"observed_cap": "observed"})
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: admitted_decision())
    role = coordinator.AgentRole.ENGINEERING
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {role.value: {"capabilities": ["observed_cap"]}}})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")

    executed: list[Any] = []

    async def admitted_run_agent(task: Any) -> Any:
        executed.append(task)
        return {"status": "executed"}

    monkeypatch.setattr(coordinator._legacy, "run_agent", admitted_run_agent)
    results = asyncio.run(coordinator.dispatch_event("test", {}))
    assert results == [{"status": "executed"}]
    assert len(executed) == 1
    receipts = coordinator.last_dispatch_receipts()
    assert receipts[0]["outcome"] == "ADMITTED"
    assert receipts[0]["authority_score"] == pytest.approx(0.72)
