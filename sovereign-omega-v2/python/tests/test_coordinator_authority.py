from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from agents import coordinator  # noqa: E402
from harness.sdk.skill_authority import compute_registry_root  # noqa: E402


def _skill(
    skill_id: str,
    *,
    runs: int,
    state: str,
    confidence: float,
    failure_rate: float,
    recency: float,
    evidence_ref: Any = "evidence.md",
    documentation_prior: float | None = None,
) -> dict[str, Any]:
    skill: dict[str, Any] = {
        "skill_id": skill_id,
        "label": skill_id,
        "domain": "test",
        "tier": "T2",
        "declared_tier": "T2",
        "observation_state": state,
        "confidence": confidence,
        "validated_runs": runs,
        "failure_rate": failure_rate,
        "failure_rate_observed": failure_rate if runs else None,
        "recency_score": recency,
        "evidence_refs": [evidence_ref],
        "last_validated": "2026-07-19T00:00:00+00:00" if runs else None,
    }
    if documentation_prior is not None:
        skill["documentation_prior"] = documentation_prior
    return skill


def _registry(skills: list[dict[str, Any]]) -> dict[str, Any]:
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


def _write_registry(tmp_path: Path, tree: dict[str, Any]) -> Path:
    path = tmp_path / "skill_tree.json"
    path.write_text(json.dumps(tree), encoding="utf-8")
    return path


def _router(
    tmp_path: Path,
    tree: dict[str, Any],
    capability_map: dict[str, str],
) -> coordinator.SkillRouter:
    (tmp_path / "evidence.md").write_text("# evidence\n", encoding="utf-8")
    return coordinator.SkillRouter(
        skill_tree_path=_write_registry(tmp_path, tree),
        repo_root=tmp_path,
        capability_map=capability_map,
    )


def test_unknown_capability_receives_zero_authority(tmp_path: Path) -> None:
    tree = _registry([
        _skill(
            "observed",
            runs=3,
            state="OBSERVED",
            confidence=0.8,
            failure_rate=0.0,
            recency=1.0,
        )
    ])
    router = _router(tmp_path, tree, {"known": "observed"})

    decision = router.capability_decision("unknown")

    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert "UNMAPPED_CAPABILITY" in decision.reason_codes


def test_zero_run_capability_never_outranks_observed_capability(tmp_path: Path) -> None:
    tree = _registry([
        _skill(
            "declared_only",
            runs=0,
            state="UNOBSERVED",
            confidence=0.0,
            failure_rate=0.0,
            recency=0.0,
            documentation_prior=0.99,
        ),
        _skill(
            "observed",
            runs=3,
            state="OBSERVED",
            confidence=0.8,
            failure_rate=0.1,
            recency=1.0,
        ),
    ])
    router = _router(
        tmp_path,
        tree,
        {"declared": "declared_only", "verified": "observed"},
    )
    agent_defs = {
        coordinator.AgentRole.ENGINEERING.value: {"capabilities": ["declared"]},
        coordinator.AgentRole.AI_SAFETY.value: {"capabilities": ["verified"]},
    }

    declared = router.role_routing_receipt(
        coordinator.AgentRole.ENGINEERING,
        "perform verified work",
        agent_defs,
    )
    observed = router.role_routing_receipt(
        coordinator.AgentRole.AI_SAFETY,
        "perform verified work",
        agent_defs,
    )

    assert declared.outcome == "DENIED"
    assert declared.authority_score == 0.0
    assert observed.outcome == "ADMITTED"
    assert observed.authority_score == 0.72


def test_documentation_prior_cannot_grant_runtime_authority(tmp_path: Path) -> None:
    tree = _registry([
        _skill(
            "prose_only",
            runs=0,
            state="UNOBSERVED",
            confidence=0.0,
            failure_rate=0.0,
            recency=0.0,
            documentation_prior=1.0,
        )
    ])
    router = _router(tmp_path, tree, {"prose": "prose_only"})

    decision = router.capability_decision("prose")

    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert decision.observation_state == "UNOBSERVED"
    assert "UNOBSERVED" in decision.reason_codes


def test_below_three_validated_runs_remains_denied(tmp_path: Path) -> None:
    tree = _registry([
        _skill(
            "under_observed",
            runs=2,
            state="OBSERVED",
            confidence=1.0,
            failure_rate=0.0,
            recency=1.0,
        )
    ])
    router = _router(tmp_path, tree, {"under": "under_observed"})

    decision = router.capability_decision("under")

    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert "INSUFFICIENT_VALIDATED_RUNS" in decision.reason_codes


def test_repository_escaping_evidence_cannot_restore_neutral_fallback(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    tree = _registry([
        _skill(
            "bad_evidence",
            runs=3,
            state="OBSERVED",
            confidence=1.0,
            failure_rate=0.0,
            recency=1.0,
            evidence_ref="../outside.md",
        )
    ])
    router = coordinator.SkillRouter(
        skill_tree_path=_write_registry(tmp_path, tree),
        repo_root=tmp_path,
        capability_map={"escape": "bad_evidence"},
    )

    decision = router.capability_decision("escape")

    assert decision.outcome == "DENIED"
    assert decision.authority_score == 0.0
    assert any(code.startswith("EVIDENCE_OUTSIDE_REPOSITORY") for code in decision.reason_codes)


def test_malformed_registry_is_deterministically_denied(tmp_path: Path) -> None:
    path = tmp_path / "skill_tree.json"
    path.write_text("{not-json", encoding="utf-8")
    router = coordinator.SkillRouter(
        skill_tree_path=path,
        repo_root=tmp_path,
        capability_map={"known": "observed"},
    )

    first = router.capability_decision("known")
    second = router.capability_decision("known")

    assert first.outcome == "DENIED"
    assert first.authority_score == 0.0
    assert "REGISTRY_JSON_MALFORMED" in first.reason_codes
    assert first.receipt_hash == second.receipt_hash


def test_identical_inputs_produce_identical_role_and_denial_receipts(tmp_path: Path) -> None:
    tree = _registry([
        _skill(
            "declared_only",
            runs=0,
            state="UNOBSERVED",
            confidence=0.0,
            failure_rate=0.0,
            recency=0.0,
        )
    ])
    router = _router(tmp_path, tree, {"declared": "declared_only"})
    agent_defs = {
        coordinator.AgentRole.ENGINEERING.value: {"capabilities": ["declared"]},
    }

    first_capability = router.capability_decision("declared")
    second_capability = router.capability_decision("declared")
    first_role = router.role_routing_receipt(
        coordinator.AgentRole.ENGINEERING,
        "same task",
        agent_defs,
    )
    second_role = router.role_routing_receipt(
        coordinator.AgentRole.ENGINEERING,
        "same task",
        agent_defs,
    )

    assert first_capability.receipt_hash == second_capability.receipt_hash
    assert first_role.receipt_hash == second_role.receipt_hash


def test_dispatch_does_not_execute_denied_role(tmp_path: Path, monkeypatch: Any) -> None:
    tree = _registry([
        _skill(
            "declared_only",
            runs=0,
            state="UNOBSERVED",
            confidence=0.0,
            failure_rate=0.0,
            recency=0.0,
        )
    ])
    router = _router(tmp_path, tree, {"declared": "declared_only"})
    role = coordinator.AgentRole.ENGINEERING

    monkeypatch.setattr(coordinator, "_skill_router", router)
    monkeypatch.setattr(coordinator._legacy, "_skill_router", router)
    monkeypatch.setattr(coordinator._legacy, "EVENT_ROUTING", {"test": [role]})
    monkeypatch.setattr(
        coordinator._legacy,
        "_load_agent_defs",
        lambda: {"agents": {role.value: {"capabilities": ["declared"]}}},
    )
    monkeypatch.setattr(
        coordinator._legacy,
        "_event_to_instruction",
        lambda event_type, payload, candidate_role: "same task",
    )

    async def forbidden_run_agent(task: Any) -> Any:
        raise AssertionError("denied role must not execute")

    monkeypatch.setattr(coordinator._legacy, "run_agent", forbidden_run_agent)

    results = asyncio.run(coordinator.dispatch_event("test", {}))
    receipts = coordinator.last_dispatch_receipts()

    assert results == []
    assert len(receipts) == 1
    assert receipts[0]["outcome"] == "DENIED"
    assert receipts[0]["authority_score"] == 0.0
