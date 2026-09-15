import importlib
import json

import pytest


D64_A = "a" * 64
D64_B = "b" * 64
D64_C = "c" * 64
D64_D = "d" * 64
HEAD = "1" * 40
BASELINE = "457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404"


def _scheduler():
    return importlib.import_module("agents.quantummanifold.scheduler")


def _receipts():
    return importlib.import_module("agents.quantummanifold.receipts")


def _roles():
    return importlib.import_module("agents.quantummanifold.roles")


def _candidate(*, digest, score=100, leverage=100, falsification=100, cost=100):
    return {
        "candidate_action_digest": digest,
        "ranking_score_ppm": score,
        "closure_leverage_ppm": leverage,
        "falsification_value_ppm": falsification,
        "cost_ppm": cost,
    }


def test_qm_red_013_tie_break_prefers_larger_closure_leverage():
    selected = _scheduler().rank_actions(
        [
            _candidate(digest=D64_A, leverage=500),
            _candidate(digest=D64_B, leverage=600),
        ]
    )
    assert selected["candidate_action_digest"] == D64_B


def test_qm_red_013_tie_break_prefers_larger_falsification_value_after_leverage():
    selected = _scheduler().rank_actions(
        [
            _candidate(digest=D64_A, leverage=500, falsification=400),
            _candidate(digest=D64_B, leverage=500, falsification=500),
        ]
    )
    assert selected["candidate_action_digest"] == D64_B


def test_qm_red_013_tie_break_prefers_smaller_cost_after_value_terms():
    selected = _scheduler().rank_actions(
        [
            _candidate(digest=D64_A, leverage=500, falsification=500, cost=400),
            _candidate(digest=D64_B, leverage=500, falsification=500, cost=300),
        ]
    )
    assert selected["candidate_action_digest"] == D64_B


def test_qm_red_013_final_tie_break_is_ascii_lexicographic_digest():
    selected = _scheduler().rank_actions(
        [
            _candidate(digest=D64_B, leverage=500, falsification=500, cost=300),
            _candidate(digest=D64_A, leverage=500, falsification=500, cost=300),
        ]
    )
    assert selected["candidate_action_digest"] == D64_A


def _receipt_kwargs():
    return {
        "baseline_digest": BASELINE,
        "source_head_sha": HEAD,
        "reality_snapshot_digest": D64_A,
        "obligation_set_digest": D64_B,
        "candidate_set_digest": D64_C,
        "scheduler_policy_digest": D64_D,
        "selected_action_digest": D64_A,
        "score_components_fixed_point": {
            "information_gain_ppm": 100,
            "closure_leverage_ppm": 200,
            "falsification_value_ppm": 300,
            "cost_ppm": 400,
            "ranking_score_ppm": 500,
        },
        "recommended_role": "BUILDER",
    }


def test_qm_red_014_identical_input_emits_byte_identical_receipt_three_times():
    receipts = [_receipts().build_scheduling_receipt(**_receipt_kwargs()) for _ in range(3)]
    assert receipts[0] == receipts[1] == receipts[2]
    decoded = json.loads(receipts[0].decode("utf-8"))
    assert decoded["receipt_kind"] == "AEGIS_QUANTUMMANIFOLD_SCHEDULING_RECEIPT_V1"
    assert decoded["authority_effect"] == "NONE"


def test_qm_red_015_non_none_authority_effect_fails_closed():
    receipt = json.loads(_receipts().build_scheduling_receipt(**_receipt_kwargs()).decode("utf-8"))
    receipt["authority_effect"] = "ADMIT"
    with pytest.raises(ValueError, match="^AUTHORITY_TUNNELING_ATTEMPT$"):
        _receipts().validate_scheduling_receipt(receipt)


def _role_context(role, inheritance_policy):
    return {
        "receipt_kind": "AEGIS_ROLE_CONTEXT_ENVELOPE_V1",
        "role": role,
        "inheritance_policy": inheritance_policy,
        "baseline_digest": BASELINE,
        "source_head_sha": HEAD,
        "reality_snapshot_digest": D64_A,
        "selected_action_digest": D64_B,
        "obligation_digest": D64_C,
        "scheduler_receipt_digest": D64_D,
        "role_policy_digest": D64_A,
        "input_evidence_roots": [D64_B],
        "continuation_state_digest": None,
        "authority_effect": "NONE",
    }


def test_qm_red_016_falsifier_builder_continuation_fails_closed():
    context = _role_context("FALSIFIER", "RAW_EVIDENCE_ONLY")
    context["continuation_state_digest"] = D64_C
    with pytest.raises(ValueError, match="^ROLE_ISOLATION_VIOLATION$"):
        _roles().validate_role_context(context)


def test_qm_red_017_reviewer_prose_continuation_fails_closed():
    context = _role_context("REVIEWER", "CLEAN_ROOM")
    context["prose_continuation"] = "builder narrative must never cross this boundary"
    with pytest.raises(ValueError, match="^CLEAN_ROOM_VIOLATION$"):
        _roles().validate_role_context(context)
