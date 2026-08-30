from __future__ import annotations

import json
from pathlib import Path
import tempfile

from harness.sdk.closed_loop_epistemic_actuation import (
    COMPUTE_CAPABILITY_EFFECT,
    EVIDENCE_ACQUISITION_UNESTABLISHED,
    EVIDENCE_ACQUISITION_VERIFIED,
    EVIDENCE_ONLY,
    ComputeUsageV1,
    EvidenceAcquisitionV1,
    record_compute_effect,
    verify_evidence_acquisition,
)
from harness.sdk.resident_runtime import ResidentRuntime


def _sha(ch: str) -> str:
    return ch * 64


def test_compute_receipt_is_distinct_from_learning_receipt_and_cannot_mint_learning() -> None:
    usage = ComputeUsageV1(
        compute_action_id="compute:trial:1",
        mechanism="extra_test_time_compute",
        requested_units=8,
        consumed_units=8,
        pre_performance_bps=5000,
        immediate_performance_bps=7300,
        durable_state_before=_sha("1"),
        durable_state_after=_sha("1"),
        execution_receipt_root=_sha("2"),
    )

    receipt = record_compute_effect(usage)

    assert receipt.status == COMPUTE_CAPABILITY_EFFECT
    assert receipt.immediate_gain_bps == 2300
    assert receipt.learning_established is False
    assert receipt.authority == EVIDENCE_ONLY
    assert receipt.receipt_type == "COMPUTE_RECEIPT_V1"
    assert receipt.may_mint_learning_authority is False
    assert receipt.may_mint_execution_authority is False
    assert len(receipt.root) == 64


def test_legacy_evidence_helper_preserves_v1_shape_but_is_not_resident_authority() -> None:
    acquisition = EvidenceAcquisitionV1(
        acquisition_id="evidence:trial:1",
        observation_receipt_root=_sha("3"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_roots=(_sha("4"), _sha("5")),
        replay_receipt_root=_sha("6"),
        provenance_verified=True,
        replay_verified=True,
        independent_verifier_count=1,
    )

    receipt = verify_evidence_acquisition(acquisition)

    # Compatibility behavior remains visible at the pure V1 helper boundary.
    # Production resident admission below must downgrade this self-asserted form.
    assert receipt.status == EVIDENCE_ACQUISITION_VERIFIED
    assert receipt.evidence_established is True
    assert receipt.receipt_type == "EVIDENCE_ACQUISITION_RECEIPT_V1"
    assert receipt.authority == EVIDENCE_ONLY
    assert receipt.may_mint_execution_authority is False
    assert receipt.may_mint_learning_authority is False
    assert receipt.may_mint_admission_authority is False
    assert len(receipt.root) == 64


def test_evidence_acquisition_fails_closed_without_independent_replay_verification() -> None:
    acquisition = EvidenceAcquisitionV1(
        acquisition_id="evidence:trial:2",
        observation_receipt_root=_sha("7"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_roots=(_sha("8"),),
        replay_receipt_root=_sha("9"),
        provenance_verified=True,
        replay_verified=False,
        independent_verifier_count=0,
    )

    receipt = verify_evidence_acquisition(acquisition)

    assert receipt.evidence_established is False
    assert "REPLAY_NOT_VERIFIED" in receipt.reason_codes
    assert "NO_INDEPENDENT_VERIFIER" in receipt.reason_codes


def test_resident_persists_compute_but_downgrades_self_asserted_v1_evidence() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    usage = ComputeUsageV1(
        compute_action_id="compute:resident:1",
        mechanism="frontier_escalation",
        requested_units=3,
        consumed_units=2,
        pre_performance_bps=6000,
        immediate_performance_bps=6500,
        durable_state_before=_sha("a"),
        durable_state_after=_sha("a"),
        execution_receipt_root=_sha("b"),
    )
    acquisition = EvidenceAcquisitionV1(
        acquisition_id="evidence:resident:1",
        observation_receipt_root=_sha("c"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_roots=(_sha("d"),),
        replay_receipt_root=_sha("e"),
        provenance_verified=True,
        replay_verified=True,
        independent_verifier_count=1,
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "resident"
        runtime = ResidentRuntime(repository_root=repo_root, state_root=root)
        compute_receipt = runtime.record_compute_usage(usage)
        evidence_receipt = runtime.record_evidence_acquisition(acquisition)

        assert evidence_receipt.status == EVIDENCE_ACQUISITION_UNESTABLISHED
        assert evidence_receipt.evidence_established is False
        assert "LEGACY_SELF_ASSERTED_VERIFICATION_REJECTED" in evidence_receipt.reason_codes

        compute_path = root / "compute-receipts" / f"{compute_receipt.root}.json"
        evidence_path = root / "evidence-acquisition-receipts" / f"{evidence_receipt.root}.json"
        assert compute_path.is_file()
        assert evidence_path.is_file()
        assert compute_path != evidence_path

        compute_payload = json.loads(compute_path.read_text(encoding="utf-8"))
        evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert compute_payload["receipt"]["receipt_type"] == "COMPUTE_RECEIPT_V1"
        assert evidence_payload["receipt"]["receipt_type"] == "EVIDENCE_ACQUISITION_RECEIPT_V1"
        assert compute_payload["authority"] == EVIDENCE_ONLY
        assert evidence_payload["authority"] == EVIDENCE_ONLY
        assert "NO_VERIFIED_EVIDENCE_FROM_SELF_ASSERTED_V1_FLAGS" in evidence_payload["non_claims"]

        status = runtime.status()["self_model"]
        assert status["compute_receipts"] == 1
        assert status["evidence_acquisition_receipts"] == 1
        assert status["learning_evaluations"] == 0
