"""Capability-order advisory: unit and admission-boundary regression tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.capability_selection import advise_admitted_order
from harness.sdk.skill_authority import compute_registry_root


@pytest.fixture
def case(tmp_path):
    root = tmp_path
    (root / "proofs").mkdir()
    (root / "proofs" / "ci-pass.json").write_text("{}", encoding="utf-8")
    defs = {
        "engineering": {"capabilities": ["code_review", "ci_debugging"]},
        "research": {"capabilities": ["formal_verification"]},
    }
    cap_map = {
        "code_review": "code_review_skill",
        "ci_debugging": "ci_skill",
        "formal_verification": "formal_skill",
    }
    candidates = [(0, "engineering", 0.9), (1, "research", 0.6)]
    registry = root / "skills.json"
    return root, defs, cap_map, candidates, registry


def skill(sid, runs, confidence):
    observed = runs >= 1
    return {
        "skill_id": sid, "tier": "T1", "declared_tier": "T1",
        "documentation_prior": 1.0,
        "observation_state": "OBSERVED" if observed else "UNOBSERVED",
        "confidence": confidence if observed else 0.0,
        "validated_runs": runs, "failure_rate": 0.0,
        "failure_rate_observed": 0.0 if observed else None,
        "recency_score": 1.0 if observed else 0.0,
        "evidence_refs": ["proofs/ci-pass.json"],
        "last_validated": "2026-10-10T08:00:00Z" if observed else None,
    }


def write_registry(path, skills):
    tree = {
        "schema_version": "2.0.0", "version": "2.0.0",
        "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
        "source_commit": "a" * 40, "skills": skills,
    }
    root = compute_registry_root(tree)
    tree["registry_root"] = root
    tree["genesis_seal"] = root
    path.write_text(json.dumps(tree), encoding="utf-8")


def run_case(case, task="fix formal verification errors", candidates=None, required=()):
    root, defs, mapping, original, registry = case
    return advise_admitted_order(
        candidates if candidates is not None else original,
        task_instruction=task,
        agent_defs=defs,
        capability_map=mapping,
        registry_path=registry,
        repo_root=root,
        required_capabilities=required,
    )


def test_unobserved_does_not_promote(case):
    write_registry(case[4], [skill("formal_skill", 0, 0.0)])
    order, receipt = run_case(case)
    assert order == [0, 1]
    assert receipt["status"] == "INSUFFICIENT_TELEMETRY"
    assert receipt["authority_effect"] == "NONE_ORDER_ONLY"


def test_validated_relevant_skill_ranks_ahead(case):
    write_registry(case[4], [skill("formal_skill", 5, 0.9)])
    order, receipt = run_case(case)
    assert order == [1, 0]
    assert receipt["status"] == "OBSERVED_SKILL_PREFERENCE"
    assert receipt["candidates"][1]["matched_validated_skill_ids"] == ["formal_skill"]


def test_irrelevant_skill_does_not_bias(case):
    write_registry(case[4], [skill("formal_skill", 7, 0.95)])
    order, receipt = run_case(case, task="speed up UI build")
    assert order == [0, 1]
    assert receipt["status"] == "INSUFFICIENT_TELEMETRY"


def test_under_three_runs_does_not_bias(case):
    write_registry(case[4], [skill("formal_skill", 2, 0.95)])
    order, receipt = run_case(case)
    assert order == [0, 1]
    assert receipt["status"] == "INSUFFICIENT_TELEMETRY"


def test_tampered_registry_does_not_change_order(case):
    write_registry(case[4], [skill("formal_skill", 9, 0.99)])
    tree = json.loads(case[4].read_text(encoding="utf-8"))
    tree["skills"][0]["confidence"] = 0.1
    case[4].write_text(json.dumps(tree), encoding="utf-8")
    order, receipt = run_case(case)
    assert order == [0, 1]
    assert receipt["status"] == "REGISTRY_INVALID"


def test_missing_evidence_does_not_change_order(case):
    write_registry(case[4], [skill("formal_skill", 9, 0.99)])
    (case[0] / "proofs" / "ci-pass.json").unlink()
    order, receipt = run_case(case)
    assert order == [0, 1]
    assert receipt["status"] in ("REGISTRY_INVALID", "INSUFFICIENT_TELEMETRY")


def test_missing_registry_retains_baseline(case):
    order, receipt = run_case(case)
    assert order == [0, 1]
    assert receipt["status"] == "REGISTRY_UNAVAILABLE"


def test_receipt_is_deterministic(case):
    write_registry(case[4], [skill("formal_skill", 4, 0.8)])
    first = run_case(case)
    second = run_case(case)
    assert first == second
    assert len(first[1]["receipt_hash"]) == 64


def test_never_adds_a_role(case):
    write_registry(case[4], [skill("formal_skill", 9, 0.99)])
    ordered, _ = run_case(case, candidates=case[3][:1])
    assert ordered == [0]


def test_duplicate_index_rejected(case):
    with pytest.raises(ValueError, match="duplicate candidate"):
        run_case(case, candidates=[(0, "research", 0.2), (0, "engineering", 0.3)])


def test_explicit_required_capability(case):
    write_registry(case[4], [skill("formal_skill", 5, 0.9)])
    order, receipt = run_case(case, task="resolve failed build", required=("formal_verification",))
    assert order == [1, 0]
    assert receipt["authority_effect"] == "NONE_ORDER_ONLY"

@pytest.mark.parametrize("deny_research", [False, True])
def test_coordinator_orders_only_centrally_admitted_roles(case, monkeypatch, deny_research):
    """Live dispatch seam: ranking must never convert a denial into a run."""
    import asyncio
    from agents import coordinator

    write_registry(case[4], [skill("formal_skill", 5, 0.9)])
    engineering = coordinator.AgentRole.ENGINEERING
    research = coordinator.AgentRole.AI_RESEARCH
    definitions = {
        "agents": {
            engineering.value: case[1]["engineering"],
            research.value: case[1]["research"],
        },
        "capability_skill_map": case[2],
    }
    knowledge = {
        "status": "ESTABLISHED", "reason_codes": [],
        "snapshot_digest": "6" * 64,
        "source_head_sha": "7" * 40, "source_tree_sha": "8" * 40,
        "receipt_hash": "9" * 64,
    }
    monkeypatch.setattr(coordinator, "establish_repository_knowledge", lambda **_: knowledge)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"advisory-test": [engineering, research]})
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: definitions)
    monkeypatch.setattr(coordinator._legacy, "_event_to_instruction", lambda *_: "fix formal verification errors")
    instance = coordinator.SkillRouter(
        skill_tree_path=case[4], repo_root=case[0], capability_map=case[2],
    )
    monkeypatch.setattr(coordinator, "_skill_router", instance)

    def central(**request):
        role = request["target"]
        outcome = "DENIED" if deny_research and role == research.value else "ADMITTED"
        return {
            "outcome": outcome,
            "authority_score": "0.000000" if outcome == "DENIED" else (
                "0.900000" if role == engineering.value else "0.600000"
            ),
            "denial_codes": ["TEST_DENIAL"] if outcome == "DENIED" else [],
            "decision_root": "3" * 64, "receipt_root": "4" * 64,
        }

    monkeypatch.setattr(coordinator, "authorize_from_environment", central)
    seen = []

    async def record_run(task):
        seen.append(task.role.value)
        return {"executed": task.role.value}

    monkeypatch.setattr(coordinator._legacy, "run_agent", record_run)
    asyncio.run(coordinator.dispatch_event("advisory-test", {}))

    if deny_research:
        assert seen == [engineering.value]
    else:
        assert seen == [research.value, engineering.value]
        assert coordinator.last_capability_advisory_receipt()["status"] == "OBSERVED_SKILL_PREFERENCE"
    assert set(seen).issubset({engineering.value, research.value})
