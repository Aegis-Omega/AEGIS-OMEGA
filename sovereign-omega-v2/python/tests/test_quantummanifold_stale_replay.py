import importlib

import pytest


HEAD_A = "1" * 40
HEAD_B = "2" * 40
D64_A = "a" * 64
D64_B = "b" * 64
D64_C = "c" * 64


def _guards():
    return importlib.import_module("agents.quantummanifold.guards")


def test_qm_red_018_result_after_head_drift_requires_rebase():
    bound = {
        "source_head_sha": HEAD_A,
        "reality_snapshot_digest": D64_A,
        "obligation_digest": D64_B,
    }
    current = dict(bound)
    current["source_head_sha"] = HEAD_B
    with pytest.raises(ValueError, match="^STALE_RESULT_REQUIRES_REBASE$"):
        _guards().validate_result_freshness(bound=bound, current=current)


def test_qm_red_018_result_after_reality_drift_requires_rebase():
    bound = {
        "source_head_sha": HEAD_A,
        "reality_snapshot_digest": D64_A,
        "obligation_digest": D64_B,
    }
    current = dict(bound)
    current["reality_snapshot_digest"] = D64_C
    with pytest.raises(ValueError, match="^STALE_RESULT_REQUIRES_REBASE$"):
        _guards().validate_result_freshness(bound=bound, current=current)


def test_qm_red_019_execution_intent_cannot_be_consumed_twice():
    consumed = set()
    _guards().consume_execution_intent(D64_A, consumed=consumed)
    with pytest.raises(ValueError, match="^EXECUTION_INTENT_REPLAY$"):
        _guards().consume_execution_intent(D64_A, consumed=consumed)


def test_qm_red_020_replay_state_digest_divergence_fails_closed():
    with pytest.raises(ValueError, match="^REPLAY_STATE_DIVERGENCE$"):
        _guards().validate_replay_state(
            recorded_reality_digest=D64_A,
            reconstructed_reality_digest=D64_B,
        )


def test_qm_red_021_restart_without_persisted_authoritative_root_fails_closed():
    with pytest.raises(ValueError, match="^STATE_RESET_EXPOSURE$"):
        _guards().require_persisted_authoritative_root(None)


def test_matching_coordinates_and_replay_digest_are_accepted():
    coordinate = {
        "source_head_sha": HEAD_A,
        "reality_snapshot_digest": D64_A,
        "obligation_digest": D64_B,
    }
    _guards().validate_result_freshness(bound=coordinate, current=dict(coordinate))
    _guards().validate_replay_state(
        recorded_reality_digest=D64_A,
        reconstructed_reality_digest=D64_A,
    )
    assert _guards().require_persisted_authoritative_root(D64_C) == D64_C
