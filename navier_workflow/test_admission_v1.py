import pytest

from navier_workflow.schema_v1 import validate_receipt


def receipt(**overrides):
    value = {
        "schema": "AEGIS_NAVIER_RECEIPT_V1",
        "transition_id": "t",
        "candidate_id": "c",
        "from_state": "ADMISSION_REVIEW",
        "to_state": "TARGET_THEOREM_CLOSED",
        "exact_head_sha": "e" * 40,
        "input_artifact_digests": ["a" * 64],
        "output_artifact_digest": "b" * 64,
        "assumptions": [],
        "open_obligations": [],
        "checks": ["formal_kernel_pass", "independent_replay_pass", "exact_head_fresh"],
        "verifier_identity": "verifier-B",
        "producer_identity": "worker-A",
        "verifier_independence_class": "INDEPENDENT",
        "decision": "ALLOW",
        "claim_promotion": "TARGET",
        "authority_effect": "ELIGIBLE_FOR_ADMISSION_REVIEW_ONLY",
        "previous_receipt_digest": "c" * 64,
    }
    value.update(overrides)
    return value


def test_caller_verified_string_does_not_replace_required_checks():
    with pytest.raises(ValueError, match="required target-closure checks"):
        validate_receipt(receipt(checks=["VERIFIED"]))


def test_stale_head_blocks_target_closure():
    with pytest.raises(ValueError, match="exact-head freshness"):
        validate_receipt(receipt(checks=["formal_kernel_pass", "independent_replay_pass"]))


def test_numerical_evidence_cannot_close_target():
    with pytest.raises(ValueError, match="formal kernel"):
        validate_receipt(receipt(checks=["numerical_simulation_pass", "independent_replay_pass", "exact_head_fresh"]))
