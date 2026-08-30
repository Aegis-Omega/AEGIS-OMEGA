from __future__ import annotations

import json
from pathlib import Path
import tempfile

from harness.sdk.closed_loop_epistemic_actuation import (
    CAPABILITY_BOOST_ONLY,
    EVIDENCE_ONLY,
    LEARNING_EFFECT_ESTABLISHED,
    LearningInterventionV1,
)
from harness.sdk.resident_runtime import ResidentRuntime


def _sha(ch: str) -> str:
    return ch * 64


def _adaptation() -> LearningInterventionV1:
    return LearningInterventionV1(
        intervention_id="resident-adapt-1",
        mechanism_class="STATE_ADAPTATION",
        mechanism="verified_memory_update",
        matched_control_id="resident-sham-adapt-1",
        pre_performance_bps=5000,
        immediate_performance_bps=7000,
        delayed_performance_bps=6800,
        control_pre_performance_bps=5000,
        control_delayed_performance_bps=5200,
        pre_transfer_bps=4000,
        post_transfer_bps=5900,
        control_pre_transfer_bps=4000,
        control_post_transfer_bps=4200,
        durable_state_before=_sha("1"),
        durable_state_after=_sha("2"),
        independent_replay_receipt_sha=_sha("3"),
    )


def _compute_only() -> LearningInterventionV1:
    return LearningInterventionV1(
        intervention_id="resident-compute-1",
        mechanism_class="COMPUTE_ONLY",
        mechanism="extra_test_time_compute",
        matched_control_id="resident-sham-compute-1",
        pre_performance_bps=5000,
        immediate_performance_bps=7900,
        delayed_performance_bps=5100,
        control_pre_performance_bps=5000,
        control_delayed_performance_bps=5100,
        pre_transfer_bps=4000,
        post_transfer_bps=4050,
        control_pre_transfer_bps=4000,
        control_post_transfer_bps=4050,
        durable_state_before=_sha("4"),
        durable_state_after=_sha("4"),
        independent_replay_receipt_sha=_sha("5"),
    )


def test_resident_persists_learning_receipt_as_evidence_only() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tmp:
        runtime = ResidentRuntime(repository_root=repo_root, state_root=Path(tmp) / "resident")
        receipt = runtime.evaluate_learning_intervention(_adaptation(), minimum_effect_bps=500)

        assert receipt.status == LEARNING_EFFECT_ESTABLISHED
        assert receipt.learning_established is True
        assert receipt.authority == EVIDENCE_ONLY
        assert receipt.may_mint_execution_authority is False
        assert receipt.may_mint_effect_authority is False
        assert receipt.may_mint_admission_authority is False

        path = Path(tmp) / "resident" / "learning-receipts" / f"{receipt.root}.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["receipt"]["status"] == LEARNING_EFFECT_ESTABLISHED
        assert payload["receipt_root"] == receipt.root
        assert payload["authority"] == EVIDENCE_ONLY
        assert payload["non_claims"] == [
            "NO_EXECUTION_AUTHORITY",
            "NO_EFFECT_AUTHORITY",
            "NO_ATOMIC_ADMISSION_AUTHORITY",
            "NO_LEARNING_CLAIM_FROM_IMMEDIATE_OUTPUT_GAIN_ALONE",
        ]


def test_resident_compute_boost_is_persisted_but_never_promoted_to_learning() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory() as tmp:
        runtime = ResidentRuntime(repository_root=repo_root, state_root=Path(tmp) / "resident")
        receipt = runtime.evaluate_learning_intervention(_compute_only(), minimum_effect_bps=100)

        assert receipt.status == CAPABILITY_BOOST_ONLY
        assert receipt.learning_established is False
        assert receipt.immediate_gain_bps == 2900
        assert receipt.authority == EVIDENCE_ONLY

        status = runtime.status()
        assert status["self_model"]["learning_evaluations"] == 1
        assert status["self_model"].get("learning_established", 0) == 0
        assert status["self_model"]["capability_boost_only"] == 1
