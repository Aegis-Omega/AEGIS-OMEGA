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



def write_valid_registry(tmp_path: Path, skill_id: str = "observed") -> Path:
    evidence = tmp_path / "evidence" / "run.json"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("{}\n", encoding="utf-8")
    tree = {
        "schema_version": "2.0.0",
        "version": "2.0.0",
        "phase": 2,
        "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
        "source_commit": "a" * 40,
        "doc_count": 0,
        "skills": [{
            "skill_id": skill_id,
            "observation_state": "OBSERVED",
            "validated_runs": 3,
            "confidence": 0.9,
            "recency_score": 0.9,
            "failure_rate": 0.0,
            "failure_rate_observed": 0.0,
            "last_validated": "2026-10-04T00:00:00+00:00",
            "evidence_refs": ["evidence/run.json"],
        }],
    }
    root = compute_registry_root(tree)
    tree["registry_root"] = root
    tree["genesis_seal"] = root
    path = tmp_path / "skill_tree.json"
    path.write_text(json.dumps(tree, sort_keys=True), encoding="utf-8")
    return path


def write_empty_lineage(tmp_path: Path) -> Path:
    path = tmp_path / "agents" / "adaptive_lineage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "genesis_hash": "0" * 64,
        "terminal_hash": "0" * 64,
        "event_count": 0,
        "events": [],
    }, sort_keys=True), encoding="utf-8")
    return path


def full_admitted_decision(registry_root: str, score: str = "0.720000") -> dict[str, Any]:
    decision_root = "3" * 64
    identity_root = "4" * 64
    workspace_binding = "5" * 64
    action_digest = "6" * 64
    return {
        "outcome": "ADMITTED",
        "authority_score": score,
        "denial_codes": [],
        "decision_root": decision_root,
        "execution_identity_root": identity_root,
        "workspace_binding": workspace_binding,
        "requested_action_digest": action_digest,
        "policy_decision": {
            "schema_version": "1.0.0",
            "outcome": "ADMITTED",
            "authority_score": score,
            "action_class": "D1",
            "authority_domain": "agent:dispatch",
            "requested_capability": "coordinator.dispatch",
            "tool": "agents.coordinator:dispatch",
            "target_digest": "7" * 64,
            "identity_root": identity_root,
            "workspace_binding": workspace_binding,
            "registry_root": registry_root,
            "policy_root": "8" * 64,
            "denial_codes": (),
            "decision_root": decision_root,
        },
    }


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
    }


def admitted_decision(score: str = "0.720000", *, root: str = "3" * 64) -> dict[str, Any]:
    return {
        "outcome": "ADMITTED",
        "authority_score": score,
        "denial_codes": [],
        "decision_root": root,
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


def test_dispatch_denies_before_central_authority_when_repository_knowledge_unavailable(tmp_path: Path, monkeypatch: Any) -> None:
    instance = router(tmp_path, {"observed_cap": "observed"})
    role = coordinator.AgentRole.ENGINEERING
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {role.value: {"capabilities": ["observed_cap"]}}})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")
    monkeypatch.setattr(
        coordinator,
        "establish_repository_knowledge",
        lambda **_kwargs: {
            "status": "DENIED",
            "reason_codes": ["REPOSITORY_KNOWLEDGE_UNAVAILABLE"],
            "receipt_hash": "5" * 64,
        },
        raising=False,
    )

    def forbidden_central(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("central authority must not be queried without repository knowledge")

    async def forbidden_run_agent(_task: Any) -> Any:
        raise AssertionError("agent must not execute without repository knowledge")

    monkeypatch.setattr(coordinator, "authorize_from_environment", forbidden_central)
    monkeypatch.setattr(coordinator._legacy, "run_agent", forbidden_run_agent)

    assert asyncio.run(coordinator.dispatch_event("test", {})) == []
    receipts = coordinator.last_dispatch_receipts()
    assert len(receipts) == 1
    assert receipts[0]["outcome"] == "DENIED"
    assert receipts[0]["authority_score"] == 0.0
    assert receipts[0]["reason_codes"] == ("REPOSITORY_KNOWLEDGE_UNAVAILABLE",)
    assert receipts[0]["receipt_hash"] == "5" * 64


def test_dispatch_binds_established_repository_knowledge_into_authority_and_task_context(tmp_path: Path, monkeypatch: Any) -> None:
    instance = router(tmp_path, {"observed_cap": "observed"})
    role = coordinator.AgentRole.ENGINEERING
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {role.value: {"capabilities": ["observed_cap"]}}})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")

    knowledge = {
        "status": "ESTABLISHED",
        "reason_codes": [],
        "snapshot_digest": "6" * 64,
        "source_head_sha": "7" * 40,
        "source_tree_sha": "8" * 40,
        "receipt_hash": "9" * 64,
    }
    monkeypatch.setattr(coordinator, "establish_repository_knowledge", lambda **_kwargs: knowledge, raising=False)

    calls: list[dict[str, Any]] = []

    def central(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return admitted_decision()

    executed: list[Any] = []

    async def admitted_run_agent(task: Any) -> Any:
        executed.append(task)
        return {"status": "executed"}

    monkeypatch.setattr(coordinator, "authorize_from_environment", central)
    monkeypatch.setattr(coordinator._legacy, "run_agent", admitted_run_agent)

    results = asyncio.run(coordinator.dispatch_event("test", {}))
    assert results == [{"status": "executed"}]
    assert len(calls) == 1
    assert calls[0]["action"]["repository_knowledge"] == {
        "snapshot_digest": "6" * 64,
        "source_head_sha": "7" * 40,
        "source_tree_sha": "8" * 40,
    }
    assert len(executed) == 1
    assert executed[0].context["repository_knowledge"] == calls[0]["action"]["repository_knowledge"]


def test_authority_only_entrypoints_do_not_issue_success_mutation_receipts() -> None:
    authority_client = (REPO_ROOT / "harness/sdk/authority_client.py").read_text(encoding="utf-8")
    authority_cli = (REPO_ROOT / "scripts/automaton3-authority.py").read_text(encoding="utf-8")
    assert "make_mutation_receipt" not in authority_client
    assert "make_mutation_receipt" not in authority_cli
    assert '"mutation_receipt"' not in authority_cli
    assert '"mutation_receipt_root"' not in authority_cli
    assert '"receipt_root": receipt.root' not in authority_client


def test_legacy_admission_to_success_receipt_constructor_is_removed() -> None:
    sovereign_execution = (REPO_ROOT / "harness/sdk/sovereign_execution.py").read_text(encoding="utf-8")
    assert "def make_mutation_receipt(" not in sovereign_execution


def test_coordinator_evidence_state_binds_verified_registry_and_lineage(tmp_path: Path) -> None:
    registry_path = write_valid_registry(tmp_path)
    lineage_path = write_empty_lineage(tmp_path)
    state = coordinator._coordinator_evidence_state(
        skill_tree_path=registry_path,
        lineage_path=lineage_path,
        repo_root=tmp_path,
    )
    assert state["status"] == "ESTABLISHED"
    assert state["skill_registry_root"] == json.loads(registry_path.read_text(encoding="utf-8"))["registry_root"]
    assert state["adaptive_lineage_root"] == "0" * 64
    assert state["adaptive_lineage_event_count"] == 0
    assert len(state["state_root"]) == 64


def test_coordinator_evidence_state_rejects_tampered_lineage(tmp_path: Path) -> None:
    registry_path = write_valid_registry(tmp_path)
    lineage_path = write_empty_lineage(tmp_path)
    lineage_path.write_text(json.dumps({
        "genesis_hash": "0" * 64,
        "terminal_hash": "f" * 64,
        "event_count": 1,
        "events": [{
            "sequence": 0,
            "event_type": "CAPABILITY_EVOLUTION",
            "skill_id": "engineering",
            "from_tier": "T2",
            "to_tier": "T2",
            "evidence": "tampered",
            "timestamp_ms": 1,
            "prev_hash": "0" * 64,
            "entry_hash": "f" * 64,
        }],
    }, sort_keys=True), encoding="utf-8")
    state = coordinator._coordinator_evidence_state(
        skill_tree_path=registry_path,
        lineage_path=lineage_path,
        repo_root=tmp_path,
    )
    assert state["status"] == "UNAVAILABLE"
    assert state["reason"] == "ADAPTIVE_LINEAGE_INVALID"


def test_dispatch_attests_only_after_verified_evidence_state_mutation(tmp_path: Path, monkeypatch: Any) -> None:
    registry_path = write_valid_registry(tmp_path)
    write_empty_lineage(tmp_path)
    instance = coordinator.SkillRouter(
        skill_tree_path=registry_path,
        repo_root=tmp_path,
        capability_map={"observed_cap": "observed"},
    )
    pre_registry_root = json.loads(registry_path.read_text(encoding="utf-8"))["registry_root"]
    role = coordinator.AgentRole.ENGINEERING
    knowledge = {
        "status": "ESTABLISHED",
        "reason_codes": [],
        "snapshot_digest": "9" * 64,
        "source_head_sha": "a" * 40,
        "source_tree_sha": "b" * 40,
        "receipt_hash": "c" * 64,
    }
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {role.value: {"capabilities": ["observed_cap"]}}})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")
    monkeypatch.setattr(coordinator, "establish_repository_knowledge", lambda **_kwargs: knowledge)
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: full_admitted_decision(pre_registry_root))

    async def mutating_run_agent(_task: Any) -> Any:
        tree = json.loads(registry_path.read_text(encoding="utf-8"))
        updated = coordinator.record_skill_observation(
            tree,
            skill_id="observed",
            success=True,
            observed_at="2026-10-04T01:00:00+00:00",
            repo_root=tmp_path,
        )
        registry_path.write_text(json.dumps(updated, sort_keys=True), encoding="utf-8")
        return {"status": "executed", "is_valid": True}

    monkeypatch.setattr(coordinator._legacy, "run_agent", mutating_run_agent)
    results = asyncio.run(coordinator.dispatch_event("test", {}))
    assert results == [{"status": "executed", "is_valid": True}]
    attestations = coordinator.last_dispatch_execution_attestations()
    assert len(attestations) == 1
    assert attestations[0]["status"] == "ATTESTED"
    receipt = attestations[0]["mutation_receipt"]
    assert receipt["outcome"] == "SUCCEEDED"
    assert receipt["pre_state_digest"] != receipt["post_state_digest"]
    assert receipt["post_state_digest"] == attestations[0]["post_state"]["state_root"]


def test_dispatch_dry_run_without_evidence_mutation_is_unattested(tmp_path: Path, monkeypatch: Any) -> None:
    registry_path = write_valid_registry(tmp_path)
    write_empty_lineage(tmp_path)
    instance = coordinator.SkillRouter(
        skill_tree_path=registry_path,
        repo_root=tmp_path,
        capability_map={"observed_cap": "observed"},
    )
    pre_registry_root = json.loads(registry_path.read_text(encoding="utf-8"))["registry_root"]
    role = coordinator.AgentRole.ENGINEERING
    knowledge = {
        "status": "ESTABLISHED",
        "reason_codes": [],
        "snapshot_digest": "9" * 64,
        "source_head_sha": "a" * 40,
        "source_tree_sha": "b" * 40,
        "receipt_hash": "c" * 64,
    }
    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {role.value: {"capabilities": ["observed_cap"]}}})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")
    monkeypatch.setattr(coordinator, "establish_repository_knowledge", lambda **_kwargs: knowledge)
    monkeypatch.setattr(coordinator, "authorize_from_environment", lambda **_kwargs: full_admitted_decision(pre_registry_root))

    async def dry_run_agent(_task: Any) -> Any:
        return {"status": "dry-run", "governance": {"dry_run": True}, "is_valid": True}

    monkeypatch.setattr(coordinator._legacy, "run_agent", dry_run_agent)
    asyncio.run(coordinator.dispatch_event("test", {}))
    attestations = coordinator.last_dispatch_execution_attestations()
    assert len(attestations) == 1
    assert attestations[0]["status"] == "UNATTESTED"
    assert attestations[0]["reason"] == "NO_EVIDENCE_STATE_CHANGE"
    assert "mutation_receipt" not in attestations[0]


def test_dispatch_reauthorizes_each_role_after_prior_state_mutation(tmp_path: Path, monkeypatch: Any) -> None:
    registry_path = write_valid_registry(tmp_path)
    write_empty_lineage(tmp_path)
    instance = coordinator.SkillRouter(
        skill_tree_path=registry_path,
        repo_root=tmp_path,
        capability_map={"observed_cap": "observed"},
    )
    roles = [coordinator.AgentRole.ENGINEERING, coordinator.AgentRole.AI_RESEARCH]
    knowledge = {
        "status": "ESTABLISHED",
        "reason_codes": [],
        "snapshot_digest": "9" * 64,
        "source_head_sha": "a" * 40,
        "source_tree_sha": "b" * 40,
        "receipt_hash": "c" * 64,
    }
    observed_authority_roots: list[str] = []

    def central(**_kwargs: Any) -> dict[str, Any]:
        current_root = json.loads(registry_path.read_text(encoding="utf-8"))["registry_root"]
        observed_authority_roots.append(current_root)
        return full_admitted_decision(current_root)

    run_count = 0

    async def mutating_run_agent(_task: Any) -> Any:
        nonlocal run_count
        run_count += 1
        tree = json.loads(registry_path.read_text(encoding="utf-8"))
        updated = coordinator.record_skill_observation(
            tree,
            skill_id="observed",
            success=True,
            observed_at=f"2026-10-04T0{run_count}:00:00+00:00",
            repo_root=tmp_path,
        )
        registry_path.write_text(json.dumps(updated, sort_keys=True), encoding="utf-8")
        return {"status": "executed", "is_valid": True}

    monkeypatch.setattr(coordinator, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", instance)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": roles})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {
        role.value: {"capabilities": ["observed_cap"]} for role in roles
    }})
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_args: "same task")
    monkeypatch.setattr(coordinator, "establish_repository_knowledge", lambda **_kwargs: knowledge)
    monkeypatch.setattr(coordinator, "authorize_from_environment", central)
    monkeypatch.setattr(coordinator._legacy, "run_agent", mutating_run_agent)

    results = asyncio.run(coordinator.dispatch_event("test", {}))
    assert len(results) == 2
    assert run_count == 2
    # Two routing decisions happen first. Each execution must then be re-authorized
    # against the registry state that exists immediately before that role runs.
    assert len(observed_authority_roots) == 4
    assert observed_authority_roots[0] == observed_authority_roots[1]
    assert observed_authority_roots[2] == observed_authority_roots[0]
    assert observed_authority_roots[3] != observed_authority_roots[2]
