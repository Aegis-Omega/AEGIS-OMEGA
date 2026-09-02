from __future__ import annotations

from pathlib import Path

import pytest

from scripts.avd.crypto_util import compute_receipt_digest
from scripts.avd.oracle_evaluator import OracleEvaluationError, OracleEvaluationV1
from scripts.avd.receipt_validator import ReceiptValidationError, validate_trial_receipt
from scripts.avd.trial_runner import AVDTrialRunner, TrialExecutionError


EXPECTED_KEYS = {
    "candidate_semantic": {"MUT_01", "MUT_02", "MUT_03", "MUT_04", "MUT_05", "MUT_06", "MUT_15"},
    "proof_integrity": {"MUT_07", "MUT_08", "MUT_09", "MUT_10"},
    "provenance_verifier": {"MUT_11", "MUT_12", "MUT_13", "MUT_14"},
}


def _passing_oracle_results() -> dict[str, dict[str, str]]:
    return {
        category: {mutation_id: "PASS" for mutation_id in sorted(ids)}
        for category, ids in EXPECTED_KEYS.items()
    }


def test_oracle_evaluation_requires_complete_exact_mutation_surface() -> None:
    evaluation = OracleEvaluationV1.from_results(_passing_oracle_results())
    assert evaluation.all_required_passed is True
    assert evaluation.to_dict() == _passing_oracle_results()

    incomplete = _passing_oracle_results()
    del incomplete["proof_integrity"]["MUT_10"]
    with pytest.raises(OracleEvaluationError, match="ORACLE_RESULT_SURFACE_MISMATCH"):
        OracleEvaluationV1.from_results(incomplete)

    unexpected = _passing_oracle_results()
    unexpected["candidate_semantic"]["MUT_00"] = "PASS"
    with pytest.raises(OracleEvaluationError, match="ORACLE_RESULT_SURFACE_MISMATCH"):
        OracleEvaluationV1.from_results(unexpected)


def test_oracle_evaluation_fails_closed_on_any_failed_falsifier() -> None:
    results = _passing_oracle_results()
    results["candidate_semantic"]["MUT_03"] = "FAIL"
    evaluation = OracleEvaluationV1.from_results(results)
    assert evaluation.all_required_passed is False


def test_receipt_validator_recomputes_digest_and_rejects_authority_widening() -> None:
    receipt = {
        "protocol_version": "AVD_PROTOCOL_V1",
        "authority_class": "NONE",
        "execution_mode": "BENCHMARK_MEASUREMENT_ONLY",
        "trial_id": "trial-001",
        "arm_id": "ARM_B_AEDR_AUTONOMOUS",
        "anchor": {
            "commit_sha": "d98ef00c6d65b45e253aa13eeebb6f9b1f256009",
            "tree_sha": "8fa6cc600d75cd78a518a8b5b08cfb9f4e665c30",
            "pr_base_sha": "88b7b937b90719cc4e05ddca2aa2bcff2894e443",
            "git_parent_sha": "16769820d37616d319cdee8ad9954d0fda086715",
        },
        "submission": {"patch_sha256": "1" * 64, "result_tree_sha256": "2" * 64},
        "commitment_digests": {"h_problem": "3" * 64, "h_verifier": "4" * 64, "h_oracle": "5" * 64},
        "resource_telemetry": {
            "wall_nanoseconds": 1,
            "active_nanoseconds": 1,
            "human_active_nanoseconds": 0,
            "machine_active_nanoseconds": 1,
            "cpu_user_microseconds": 0,
            "cpu_system_microseconds": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tool_actions": 0,
            "model_calls": 0,
            "gpu_seconds": "UNAVAILABLE",
            "cached_tokens": "UNAVAILABLE",
            "api_cost_usd": "UNAVAILABLE",
        },
        "oracle_falsifier_outcomes": _passing_oracle_results(),
        "isolation_attestation": {
            "workspace_git_metadata_absent": True,
            "candidate_network_mode": "NONE",
            "fresh_clean_room_context": True,
            "external_repo_tools_disabled": True,
            "future_solution_absent_at_start": True,
        },
        "gate_outcome": "PASS",
    }
    receipt["receipt_digest"] = compute_receipt_digest(receipt)
    validate_trial_receipt(receipt)

    widened = dict(receipt)
    widened["authority_class"] = "T0_FORMAL"
    with pytest.raises(ReceiptValidationError, match="AUTHORITY_CLASS_NOT_NONE"):
        validate_trial_receipt(widened)

    tampered = dict(receipt)
    tampered["trial_id"] = "trial-tampered"
    with pytest.raises(ReceiptValidationError, match="RECEIPT_DIGEST_MISMATCH"):
        validate_trial_receipt(tampered)


def test_trial_runner_cannot_pass_without_network_none_attestation(tmp_path: Path) -> None:
    runner = AVDTrialRunner()
    with pytest.raises(TrialExecutionError, match="NETWORK_NONE_ATTESTATION_REQUIRED"):
        runner.determine_gate_outcome(
            verifier_passed=True,
            oracle_evaluation=OracleEvaluationV1.from_results(_passing_oracle_results()),
            isolation_attestation={
                "workspace_git_metadata_absent": True,
                "candidate_network_mode": "NONE",
                "fresh_clean_room_context": True,
                "external_repo_tools_disabled": True,
                "future_solution_absent_at_start": True,
            },
            os_network_none_attested=False,
        )


def test_trial_runner_rejects_commitment_compromise_before_candidate_failure() -> None:
    runner = AVDTrialRunner()
    outcome = runner.map_commitment_failure_to_outcome("H_V_MISMATCH")
    assert outcome == "REJECTED_VERIFIER_COMPROMISE"
