from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile

from harness.sdk.closed_loop_epistemic_actuation import EvidenceAcquisitionV1
from harness.sdk.evidence_replay_binding import (
    EVIDENCE_ACQUISITION_UNESTABLISHED,
    EVIDENCE_ACQUISITION_VERIFIED,
    EvidenceAcquisitionV2,
    ProvenanceProofV1,
    ReplayProofV1,
    record_replayed_evidence_acquisition,
    reject_legacy_self_asserted_acquisition,
    verify_evidence_acquisition_v2,
    verify_provenance_proof,
    verify_replay_proof,
)
from harness.sdk.resident_runtime import RepositoryEventV1, ResidentRuntime


def _sha(ch: str) -> str:
    return ch * 64


def test_legacy_self_asserted_replay_flags_are_rejected_by_v2_boundary() -> None:
    legacy = EvidenceAcquisitionV1(
        acquisition_id="legacy:self-asserted:1",
        observation_receipt_root=_sha("1"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_roots=(_sha("2"),),
        replay_receipt_root=_sha("3"),
        provenance_verified=True,
        replay_verified=True,
        independent_verifier_count=99,
    )

    receipt = reject_legacy_self_asserted_acquisition(legacy)

    assert receipt.status == EVIDENCE_ACQUISITION_UNESTABLISHED
    assert receipt.evidence_established is False
    assert "LEGACY_SELF_ASSERTED_VERIFICATION_REJECTED" in receipt.reason_codes


def test_v2_derives_provenance_and_replay_status_from_exact_bindings() -> None:
    provenance = verify_provenance_proof(
        ProvenanceProofV1(
            declared_roots=(_sha("4"), _sha("5")),
            independently_observed_roots=(_sha("4"), _sha("5")),
            producer_identity_root=_sha("6"),
            verifier_identity_root=_sha("7"),
        )
    )
    replay = verify_replay_proof(
        ReplayProofV1(
            replay_id="replay:1",
            observation_receipt_root=_sha("8"),
            original_result_root=_sha("9"),
            replayed_result_root=_sha("9"),
            producer_identity_root=_sha("a"),
            verifier_identity_root=_sha("b"),
            environment_root=_sha("c"),
        )
    )

    acquisition = EvidenceAcquisitionV2(
        acquisition_id="evidence:v2:1",
        observation_receipt_root=_sha("8"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_receipt=provenance,
        replay_receipt=replay,
    )
    receipt = verify_evidence_acquisition_v2(acquisition)

    assert receipt.status == EVIDENCE_ACQUISITION_VERIFIED
    assert receipt.evidence_established is True
    assert receipt.provenance_receipt_root == provenance.root
    assert receipt.replay_receipt_root == replay.root
    assert receipt.independent_verifier_count == 2


def test_v2_fails_closed_when_replay_is_same_producer_or_result_mismatches() -> None:
    provenance = verify_provenance_proof(
        ProvenanceProofV1(
            declared_roots=(_sha("d"),),
            independently_observed_roots=(_sha("d"),),
            producer_identity_root=_sha("e"),
            verifier_identity_root=_sha("f"),
        )
    )
    replay = verify_replay_proof(
        ReplayProofV1(
            replay_id="replay:2",
            observation_receipt_root=_sha("1"),
            original_result_root=_sha("2"),
            replayed_result_root=_sha("3"),
            producer_identity_root=_sha("4"),
            verifier_identity_root=_sha("4"),
            environment_root=_sha("5"),
        )
    )
    acquisition = EvidenceAcquisitionV2(
        acquisition_id="evidence:v2:2",
        observation_receipt_root=_sha("1"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_receipt=provenance,
        replay_receipt=replay,
    )

    receipt = verify_evidence_acquisition_v2(acquisition)

    assert receipt.status == EVIDENCE_ACQUISITION_UNESTABLISHED
    assert receipt.evidence_established is False
    assert "REPLAY_RESULT_MISMATCH" in replay.reason_codes
    assert "REPLAY_VERIFIER_NOT_INDEPENDENT" in replay.reason_codes


def test_v2_rejects_receipt_splicing_across_observation_roots() -> None:
    provenance = verify_provenance_proof(
        ProvenanceProofV1(
            declared_roots=(_sha("6"),),
            independently_observed_roots=(_sha("6"),),
            producer_identity_root=_sha("7"),
            verifier_identity_root=_sha("8"),
        )
    )
    replay = verify_replay_proof(
        ReplayProofV1(
            replay_id="replay:3",
            observation_receipt_root=_sha("9"),
            original_result_root=_sha("a"),
            replayed_result_root=_sha("a"),
            producer_identity_root=_sha("b"),
            verifier_identity_root=_sha("c"),
            environment_root=_sha("d"),
        )
    )
    acquisition = EvidenceAcquisitionV2(
        acquisition_id="evidence:v2:splice",
        observation_receipt_root=_sha("e"),
        source_kind="REPOSITORY_GIT_OBJECT",
        provenance_receipt=provenance,
        replay_receipt=replay,
    )

    receipt = verify_evidence_acquisition_v2(acquisition)

    assert receipt.evidence_established is False
    assert "REPLAY_OBSERVATION_BINDING_MISMATCH" in receipt.reason_codes


def test_resident_derives_v2_evidence_from_dereferenced_run_bundle() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    head = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    event = RepositoryEventV1(
        event_id="replay-binding-1",
        idempotency_key="replay-binding-1",
        repository_head=head,
        changed_path="CLAUDE.md",
        question="Verify the exact committed file through the resident evidence path.",
        source="git",
        sequence=1,
        max_cost_microunits=100,
        max_latency_ms=30_000,
        requested_authority="D1",
    )

    with tempfile.TemporaryDirectory() as tmp:
        runtime = ResidentRuntime(repository_root=repo_root, state_root=Path(tmp) / "resident")
        run_receipt = runtime.process_repository_event(event)
        replay = runtime.replay_verify(run_receipt.run_id)
        assert replay.integrity_verified is True
        assert replay.lineage_verified is True

        receipt = record_replayed_evidence_acquisition(
            runtime,
            acquisition_id="evidence:resident-replay:1",
            run_id=run_receipt.run_id,
            source_kind="RESIDENT_RUN_BUNDLE",
        )

        assert receipt.status == EVIDENCE_ACQUISITION_VERIFIED
        assert receipt.evidence_established is True
        assert receipt.observation_receipt_root == run_receipt.self_model["observation_receipt_root"]
        assert receipt.provenance_roots == run_receipt.evidence_roots

        # Tampering with the persisted run body must make a fresh acquisition fail closed.
        run_path = Path(tmp) / "resident" / "runs" / f"{run_receipt.run_id}.json"
        original = run_path.read_text(encoding="utf-8")
        run_path.write_text(original.replace('"integrity_scope"', '"integrity_scope_tampered"', 1), encoding="utf-8")
        failed = record_replayed_evidence_acquisition(
            runtime,
            acquisition_id="evidence:resident-replay:tampered",
            run_id=run_receipt.run_id,
            source_kind="RESIDENT_RUN_BUNDLE",
        )
        assert failed.status == EVIDENCE_ACQUISITION_UNESTABLISHED
        assert failed.evidence_established is False

        # Tampering only with the outer digest must also fail closed. Recomputing
        # bundle_body alone is insufficient because the resident replay contract
        # binds the outer envelope, outer receipt, and event lineage too.
        run_path.write_text(original, encoding="utf-8")
        zero = _sha("0")
        outer_tampered = original.replace(
            f'"bundle_digest":"{run_receipt.bundle_digest}"',
            f'"bundle_digest":"{zero}"',
            1,
        )
        assert outer_tampered != original
        run_path.write_text(outer_tampered, encoding="utf-8")
        failed_outer = record_replayed_evidence_acquisition(
            runtime,
            acquisition_id="evidence:resident-replay:outer-tampered",
            run_id=run_receipt.run_id,
            source_kind="RESIDENT_RUN_BUNDLE",
        )
        assert failed_outer.status == EVIDENCE_ACQUISITION_UNESTABLISHED
        assert failed_outer.evidence_established is False
