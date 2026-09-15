import asyncio
import importlib

import pytest


def _authority():
    return importlib.import_module("agents.quantummanifold.authority")


def test_qm_red_022_automaton3_deny_produces_zero_agent_side_effects(monkeypatch):
    coordinator = importlib.import_module("agents.coordinator")

    monkeypatch.setattr(
        coordinator,
        "establish_repository_knowledge",
        lambda **_kwargs: {
            "status": "ESTABLISHED",
            "reason_codes": [],
            "snapshot_digest": "a" * 64,
            "source_head_sha": "1" * 40,
            "source_tree_sha": "2" * 40,
            "receipt_hash": "b" * 64,
        },
    )

    def deny_receipt(role, _instruction, _defs, *, repository_knowledge=None):
        assert repository_knowledge is not None
        return coordinator.RoleRoutingReceipt(
            schema_version="2.0.0",
            receipt_kind=coordinator.ROLE_RECEIPT_KIND,
            role=role.value,
            outcome="DENIED",
            authority_score=0.0,
            capability_receipt_hashes=("c" * 64,),
            reason_codes=("AUTOMATON3_DENY",),
            receipt_hash="d" * 64,
        )

    monkeypatch.setattr(coordinator._skill_router, "role_routing_receipt", deny_receipt)
    monkeypatch.setattr(coordinator._legacy, "_load_agent_defs", lambda: {"agents": {}})

    side_effect_calls = []

    async def forbidden_run_agent(_task):
        side_effect_calls.append("called")
        raise AssertionError("agent side effect occurred after DENY")

    monkeypatch.setattr(coordinator._legacy, "run_agent", forbidden_run_agent)

    result = asyncio.run(coordinator.dispatch_event("qm-authority-red", {"x": 1}))
    assert result == []
    assert side_effect_calls == []


def test_qm_red_023_builder_cannot_directly_promote_m4_result_to_m2():
    with pytest.raises(ValueError, match="^DIRECT_M4_TO_M2_PROMOTION_FORBIDDEN$"):
        _authority().validate_role_result_transition(
            role="BUILDER",
            source_plane="M4",
            destination_plane="M2",
            admission_receipt=None,
        )


def test_qm_red_024_survived_falsifier_cannot_map_to_proven():
    with pytest.raises(ValueError, match="^EPISTEMIC_INFLATION_FORBIDDEN$"):
        _authority().validate_epistemic_transition(
            falsifier_outcome="SURVIVED_CURRENT_FALSIFIER",
            proposed_status="PROVEN",
        )
