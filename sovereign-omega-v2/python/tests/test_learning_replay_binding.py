from __future__ import annotations

import json
from pathlib import Path
import tempfile

from harness.sdk.closed_loop_epistemic_actuation import LearningInterventionV1
from harness.sdk.evidence_replay_binding import (
    EvidenceAcquisitionV2,
    ProvenanceProofV1,
    ReplayProofV1,
    verify_evidence_acquisition_v2,
    verify_provenance_proof,
    verify_replay_proof,
)
from harness.sdk.learning_replay_binding import (
    CAPABILITY_BOOST_ONLY,
    LEARNING_EFFECT_ESTABLISHED,
    LEARNING_EFFECT_UNESTABLISHED,
    LearningStudyV2,
    LearningVerificationV2,
    evaluate_learning_effect_v2,
    evaluate_verified_learning_intervention,
    reject_legacy_learning_intervention,
)
from harness.sdk.resident_runtime import ResidentRuntime


def _sha(ch: str) -> str:
    return ch * 64


def _study(*, mechanism_class: str = "STATE_ADAPTATION", suffix: str = "1") -> LearningStudyV2:
    return LearningStudyV2(
        intervention_id=f"learning:v2:{suffix}",
        mechanism_class=mechanism_class,
        mechanism=("verified_memory_update" if mechanism_class == "STATE_ADAPTATION" else "extra_test_time_compute"),
        matched_control_id=f"control:v2:{suffix}",
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
        durable_state_after=(_sha("2") if mechanism_class == "STATE_ADAPTATION" else _sha("1")),
    )


def _verification(study: LearningStudyV2, *, observation_root: str = "3" * 64) -> LearningVerificationV2:
    provenance = verify_provenance_proof(
        ProvenanceProofV1(
            declared_roots=(study.root,),
            independently_observed_roots=(study.root,),
            producer_identity_root=_sha("4"),
            verifier_identity_root=_sha("5"),
        )
    )
    replay = verify_replay_proof(
        ReplayProofV1(
            replay_id=f"replay:{study.intervention_id}",
            observation_receipt_root=observation_root,
            original_result_root=study.root,
            replayed_result_root=study.root,
            producer_identity_root=_sha("6"),
            verifier_identity_root=_sha("7"),
            environment_root=_sha("8"),
        )
    )
    evidence = verify_evidence_acquisition_v2(
        EvidenceAcquisitionV2(
            acquisition_id=f"evidence:{study.intervention_id}",
            observation_receipt_root=observation_root,
            source_kind="MATCHED_CONTROL_LEARNING_STUDY",
            provenance_receipt=provenance,
            replay_receipt=replay,
        )
    )
    return LearningVerificationV2(
        study=study,
        evidence_receipt=evidence,
        replay_receipt=replay,
    )


def test_arbitrary_legacy_replay_hash_cannot_establish_learning_at_v2_boundary() -> None:
    legacy = LearningInterventionV1(
        intervention_id="legacy-learning-1",
        mechanism_class="STATE_ADAPTATION",
        mechanism="verified_memory_update",
        matched_control_id="legacy-control-1",
        pre_performance_bps=5000,
        immediate_performance_bps=7000,
        delayed_performance_bps=6800,
        control_pre_performance_bps=5000,
        control_delayed_performance_bps=5200,
        pre_transfer_bps=4000,
        post_transfer_bps=5900,
        control_pre_transfer_bps=4000,
        control_post_transfer_bps=4200,
        durable_state_before=_sha("a"),
        durable_state_after=_sha("b"),
        independent_replay_receipt_sha=_sha("c"),
    )

    receipt = reject_legacy_learning_intervention(legacy)

    assert receipt.status == LEARNING_EFFECT_UNESTABLISHED
    assert receipt.learning_established is False
    assert "LEGACY_UNDEREFERENCED_REPLAY_HASH_REJECTED" in receipt.reason_codes


def test_v2_establishes_learning_only_with_exact_study_replay_and_verified_evidence() -> None:
    verification = _verification(_study())

    receipt = evaluate_learning_effect_v2(verification, minimum_effect_bps=500)

    assert receipt.status == LEARNING_EFFECT_ESTABLISHED
    assert receipt.learning_established is True
    assert receipt.study_root == verification.study.root
    assert receipt.evidence_receipt_root == verification.evidence_receipt.root
    assert receipt.replay_receipt_root == verification.replay_receipt.root
    assert receipt.retention_gain_vs_control_bps == 1600
    assert receipt.transfer_gain_vs_control_bps == 1700
    assert receipt.may_mint_execution_authority is False
    assert receipt.may_mint_effect_authority is False
    assert receipt.may_mint_admission_authority is False


def test_v2_rejects_replay_receipt_spliced_from_a_different_learning_study() -> None:
    target = _study(suffix="target")
    foreign = _study(suffix="foreign")
    foreign_verification = _verification(foreign)
    spliced = LearningVerificationV2(
        study=target,
        evidence_receipt=foreign_verification.evidence_receipt,
        replay_receipt=foreign_verification.replay_receipt,
    )

    receipt = evaluate_learning_effect_v2(spliced, minimum_effect_bps=500)

    assert receipt.status == LEARNING_EFFECT_UNESTABLISHED
    assert receipt.learning_established is False
    assert "LEARNING_STUDY_REPLAY_BINDING_MISMATCH" in receipt.reason_codes


def test_compute_only_stays_capability_even_with_verified_replay_evidence() -> None:
    verification = _verification(_study(mechanism_class="COMPUTE_ONLY", suffix="compute"))

    receipt = evaluate_learning_effect_v2(verification, minimum_effect_bps=100)

    assert receipt.status == CAPABILITY_BOOST_ONLY
    assert receipt.learning_established is False
    assert "COMPUTE_IS_CAPABILITY_NOT_LEARNING" in receipt.reason_codes


def test_resident_persists_only_verified_v2_learning_in_separate_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    verification = _verification(_study(suffix="resident"))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "resident"
        runtime = ResidentRuntime(repository_root=repo_root, state_root=root)
        receipt = evaluate_verified_learning_intervention(
            runtime,
            verification,
            minimum_effect_bps=500,
        )

        assert receipt.status == LEARNING_EFFECT_ESTABLISHED
        path = root / "learning-v2-receipts" / f"{receipt.root}.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["receipt"]["receipt_type"] == "LEARNING_RECEIPT_V2"
        assert payload["authority"] == "EVIDENCE_ONLY"
        status = runtime.status()["self_model"]
        assert status["learning_v2_evaluations"] == 1
        assert status["learning_v2_established"] == 1
