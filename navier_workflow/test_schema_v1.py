import pytest

from navier_workflow.schema_v1 import (
    canonical_json,
    sha256_digest,
    transition_allowed,
    validate_candidate,
    validate_receipt,
)


def base_candidate():
    return {
        "candidate_id": "cand-1",
        "lane_id": "target-positive",
        "claim": "conditional estimate",
        "claim_scope": "SURROGATE_ONLY",
        "assumptions": ["smooth compactly supported seed"],
        "source_coordinates": ["paper:1#lemma-2"],
        "dependencies": ["dep-a"],
        "open_obligations": ["dep-a"],
        "known_failure_modes": [],
        "falsification_attempts": [],
        "artifact_digest": "a" * 64,
    }


def test_canonical_json_rejects_float():
    with pytest.raises(ValueError, match="floats are forbidden"):
        canonical_json({"score": 0.5})


def test_canonical_digest_is_order_independent():
    assert sha256_digest({"b": 2, "a": 1}) == sha256_digest({"a": 1, "b": 2})


def test_candidate_validation_accepts_complete_candidate():
    assert validate_candidate(base_candidate())["candidate_id"] == "cand-1"


def test_open_dependency_blocks_target_theorem_closed():
    receipt = {
        "schema": "AEGIS_NAVIER_RECEIPT_V1",
        "transition_id": "t1",
        "candidate_id": "cand-1",
        "from_state": "ADMISSION_REVIEW",
        "to_state": "TARGET_THEOREM_CLOSED",
        "exact_head_sha": "b" * 40,
        "input_artifact_digests": ["a" * 64],
        "output_artifact_digest": "c" * 64,
        "assumptions": [],
        "open_obligations": ["unclosed-lemma"],
        "checks": ["formal_kernel_pass", "independent_replay_pass", "exact_head_fresh"],
        "verifier_identity": "verifier-B",
        "producer_identity": "worker-A",
        "verifier_independence_class": "INDEPENDENT",
        "decision": "ALLOW",
        "claim_promotion": "TARGET",
        "authority_effect": "ELIGIBLE_FOR_ADMISSION_REVIEW_ONLY",
        "previous_receipt_digest": "d" * 64,
    }
    with pytest.raises(ValueError, match="open obligations"):
        validate_receipt(receipt)


def test_self_verification_is_rejected():
    receipt = {
        "schema": "AEGIS_NAVIER_RECEIPT_V1",
        "transition_id": "t1",
        "candidate_id": "cand-1",
        "from_state": "ADVERSARIAL_REVIEW",
        "to_state": "FORMALIZATION",
        "exact_head_sha": "b" * 40,
        "input_artifact_digests": ["a" * 64],
        "output_artifact_digest": "c" * 64,
        "assumptions": [],
        "open_obligations": [],
        "checks": [],
        "verifier_identity": "worker-A",
        "producer_identity": "worker-A",
        "verifier_independence_class": "INDEPENDENT",
        "decision": "ALLOW",
        "claim_promotion": "NONE",
        "authority_effect": "NONE",
        "previous_receipt_digest": "d" * 64,
    }
    with pytest.raises(ValueError, match="independently verify its own artifact"):
        validate_receipt(receipt)


def test_invalid_transition_is_rejected():
    assert transition_allowed("PROPOSED", "TARGET_THEOREM_CLOSED") is False
