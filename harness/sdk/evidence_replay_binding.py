"""Derived replay/provenance evidence bindings for AEGIS Ω.

This module hardens the evidence-acquisition lane without touching execution or
admission authority.  Legacy ``EvidenceAcquisitionV1`` contains caller-supplied
``*_verified`` booleans; V2 deliberately refuses to use those assertions as a
verification source.  Instead it derives status from exact digest equality,
anti-splicing observation bindings, and verifier/producer identity separation.

The resident helper dereferences the persisted run bundle and compares it with
the independently stored run receipt before emitting any V2 evidence receipt.
All outputs remain ``EVIDENCE_ONLY`` and carry zero authority weight.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from harness.sdk.closed_loop_epistemic_actuation import (
    EVIDENCE_ACQUISITION_UNESTABLISHED,
    EVIDENCE_ACQUISITION_VERIFIED,
    EVIDENCE_ONLY,
    EvidenceAcquisitionV1,
)
from harness.sdk.sovereign_execution import canonical_hash


PROVENANCE_VERIFIED = "PROVENANCE_VERIFIED"
PROVENANCE_UNESTABLISHED = "PROVENANCE_UNESTABLISHED"
INDEPENDENT_REPLAY_VERIFIED = "INDEPENDENT_REPLAY_VERIFIED"
INDEPENDENT_REPLAY_UNESTABLISHED = "INDEPENDENT_REPLAY_UNESTABLISHED"
ZERO_HASH = "0" * 64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name.upper()}_INVALID")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_roots(name: str, roots: tuple[str, ...], *, allow_empty: bool) -> None:
    if not isinstance(roots, tuple) or (not allow_empty and not roots):
        raise ValueError(f"{name.upper()}_INVALID")
    for root in roots:
        _require_sha256(name, root)


@dataclass(frozen=True)
class ProvenanceProofV1:
    """Exact provenance comparison with explicit producer/verifier identities."""

    declared_roots: tuple[str, ...]
    independently_observed_roots: tuple[str, ...]
    producer_identity_root: str
    verifier_identity_root: str
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_roots("declared_provenance_root", self.declared_roots, allow_empty=False)
        _require_roots(
            "observed_provenance_root",
            self.independently_observed_roots,
            allow_empty=True,
        )
        _require_sha256("producer_identity_root", self.producer_identity_root)
        _require_sha256("verifier_identity_root", self.verifier_identity_root)
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("PROVENANCE_PROOF_AUTHORITY_INVALID")


@dataclass(frozen=True)
class ProvenanceReceiptV1:
    status: str
    declared_roots: tuple[str, ...]
    independently_observed_roots: tuple[str, ...]
    producer_identity_root: str
    verifier_identity_root: str
    provenance_established: bool
    reason_codes: tuple[str, ...]
    receipt_type: str = "PROVENANCE_RECEIPT_V1"
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_learning_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {PROVENANCE_VERIFIED, PROVENANCE_UNESTABLISHED}:
            raise ValueError("PROVENANCE_RECEIPT_STATUS_INVALID")
        _require_roots("declared_provenance_root", self.declared_roots, allow_empty=False)
        _require_roots(
            "observed_provenance_root",
            self.independently_observed_roots,
            allow_empty=True,
        )
        _require_sha256("producer_identity_root", self.producer_identity_root)
        _require_sha256("verifier_identity_root", self.verifier_identity_root)
        if self.provenance_established != (self.status == PROVENANCE_VERIFIED):
            raise ValueError("PROVENANCE_RECEIPT_STATUS_INCONSISTENT")
        if not self.reason_codes:
            raise ValueError("PROVENANCE_RECEIPT_REASONS_INVALID")
        if self.receipt_type != "PROVENANCE_RECEIPT_V1":
            raise ValueError("PROVENANCE_RECEIPT_TYPE_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("PROVENANCE_RECEIPT_AUTHORITY_INVALID")
        if (
            self.may_mint_execution_authority
            or self.may_mint_learning_authority
            or self.may_mint_admission_authority
        ):
            raise ValueError("PROVENANCE_RECEIPT_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_PROVENANCE_RECEIPT_V1", asdict(self))


def verify_provenance_proof(proof: ProvenanceProofV1) -> ProvenanceReceiptV1:
    proof.validate()
    reasons: list[str] = []
    if proof.declared_roots != proof.independently_observed_roots:
        reasons.append("PROVENANCE_ROOT_MISMATCH")
    if len(set(proof.declared_roots)) != len(proof.declared_roots):
        reasons.append("DUPLICATE_DECLARED_PROVENANCE_ROOT")
    if len(set(proof.independently_observed_roots)) != len(
        proof.independently_observed_roots
    ):
        reasons.append("DUPLICATE_OBSERVED_PROVENANCE_ROOT")
    if proof.producer_identity_root == proof.verifier_identity_root:
        reasons.append("PROVENANCE_VERIFIER_NOT_INDEPENDENT")
    established = not reasons
    receipt = ProvenanceReceiptV1(
        status=PROVENANCE_VERIFIED if established else PROVENANCE_UNESTABLISHED,
        declared_roots=proof.declared_roots,
        independently_observed_roots=proof.independently_observed_roots,
        producer_identity_root=proof.producer_identity_root,
        verifier_identity_root=proof.verifier_identity_root,
        provenance_established=established,
        reason_codes=("EXACT_PROVENANCE_AND_IDENTITY_SEPARATION_VERIFIED",)
        if established
        else tuple(reasons),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class ReplayProofV1:
    """Digest-level replay comparison; no caller-supplied verified boolean exists."""

    replay_id: str
    observation_receipt_root: str
    original_result_root: str
    replayed_result_root: str
    producer_identity_root: str
    verifier_identity_root: str
    environment_root: str
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("replay_id", self.replay_id)
        for name in (
            "observation_receipt_root",
            "original_result_root",
            "replayed_result_root",
            "producer_identity_root",
            "verifier_identity_root",
            "environment_root",
        ):
            _require_sha256(name, getattr(self, name))
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("REPLAY_PROOF_AUTHORITY_INVALID")


@dataclass(frozen=True)
class ReplayReceiptV1:
    status: str
    replay_id: str
    observation_receipt_root: str
    original_result_root: str
    replayed_result_root: str
    producer_identity_root: str
    verifier_identity_root: str
    environment_root: str
    replay_verified: bool
    reason_codes: tuple[str, ...]
    receipt_type: str = "REPLAY_RECEIPT_V1"
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_learning_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {
            INDEPENDENT_REPLAY_VERIFIED,
            INDEPENDENT_REPLAY_UNESTABLISHED,
        }:
            raise ValueError("REPLAY_RECEIPT_STATUS_INVALID")
        _require_text("replay_id", self.replay_id)
        for name in (
            "observation_receipt_root",
            "original_result_root",
            "replayed_result_root",
            "producer_identity_root",
            "verifier_identity_root",
            "environment_root",
        ):
            _require_sha256(name, getattr(self, name))
        if self.replay_verified != (self.status == INDEPENDENT_REPLAY_VERIFIED):
            raise ValueError("REPLAY_RECEIPT_STATUS_INCONSISTENT")
        if not self.reason_codes:
            raise ValueError("REPLAY_RECEIPT_REASONS_INVALID")
        if self.receipt_type != "REPLAY_RECEIPT_V1":
            raise ValueError("REPLAY_RECEIPT_TYPE_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("REPLAY_RECEIPT_AUTHORITY_INVALID")
        if (
            self.may_mint_execution_authority
            or self.may_mint_learning_authority
            or self.may_mint_admission_authority
        ):
            raise ValueError("REPLAY_RECEIPT_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_REPLAY_RECEIPT_V1", asdict(self))


def verify_replay_proof(proof: ReplayProofV1) -> ReplayReceiptV1:
    proof.validate()
    reasons: list[str] = []
    if proof.original_result_root != proof.replayed_result_root:
        reasons.append("REPLAY_RESULT_MISMATCH")
    if proof.producer_identity_root == proof.verifier_identity_root:
        reasons.append("REPLAY_VERIFIER_NOT_INDEPENDENT")
    established = not reasons
    receipt = ReplayReceiptV1(
        status=(
            INDEPENDENT_REPLAY_VERIFIED
            if established
            else INDEPENDENT_REPLAY_UNESTABLISHED
        ),
        replay_id=proof.replay_id,
        observation_receipt_root=proof.observation_receipt_root,
        original_result_root=proof.original_result_root,
        replayed_result_root=proof.replayed_result_root,
        producer_identity_root=proof.producer_identity_root,
        verifier_identity_root=proof.verifier_identity_root,
        environment_root=proof.environment_root,
        replay_verified=established,
        reason_codes=("EXACT_REPLAY_DIGEST_AND_IDENTITY_SEPARATION_VERIFIED",)
        if established
        else tuple(reasons),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class EvidenceAcquisitionV2:
    acquisition_id: str
    observation_receipt_root: str
    source_kind: str
    provenance_receipt: ProvenanceReceiptV1
    replay_receipt: ReplayReceiptV1
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("acquisition_id", self.acquisition_id)
        _require_sha256("observation_receipt_root", self.observation_receipt_root)
        _require_text("source_kind", self.source_kind)
        self.provenance_receipt.validate()
        self.replay_receipt.validate()
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("EVIDENCE_ACQUISITION_V2_AUTHORITY_INVALID")


@dataclass(frozen=True)
class EvidenceAcquisitionReceiptV2:
    status: str
    acquisition_id: str
    observation_receipt_root: str
    source_kind: str
    provenance_roots: tuple[str, ...]
    provenance_receipt_root: str
    replay_receipt_root: str
    independent_verifier_count: int
    evidence_established: bool
    reason_codes: tuple[str, ...]
    receipt_type: str = "EVIDENCE_ACQUISITION_RECEIPT_V2"
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_learning_authority: bool = False
    may_mint_effect_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {
            EVIDENCE_ACQUISITION_VERIFIED,
            EVIDENCE_ACQUISITION_UNESTABLISHED,
        }:
            raise ValueError("EVIDENCE_ACQUISITION_V2_STATUS_INVALID")
        _require_text("acquisition_id", self.acquisition_id)
        _require_sha256("observation_receipt_root", self.observation_receipt_root)
        _require_text("source_kind", self.source_kind)
        _require_roots("provenance_root", self.provenance_roots, allow_empty=False)
        _require_sha256("provenance_receipt_root", self.provenance_receipt_root)
        _require_sha256("replay_receipt_root", self.replay_receipt_root)
        if isinstance(self.independent_verifier_count, bool) or not isinstance(
            self.independent_verifier_count, int
        ) or self.independent_verifier_count < 0:
            raise ValueError("INDEPENDENT_VERIFIER_COUNT_INVALID")
        if self.evidence_established != (
            self.status == EVIDENCE_ACQUISITION_VERIFIED
        ):
            raise ValueError("EVIDENCE_ACQUISITION_V2_STATUS_INCONSISTENT")
        if not self.reason_codes:
            raise ValueError("EVIDENCE_ACQUISITION_V2_REASONS_INVALID")
        if self.receipt_type != "EVIDENCE_ACQUISITION_RECEIPT_V2":
            raise ValueError("EVIDENCE_ACQUISITION_V2_TYPE_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("EVIDENCE_ACQUISITION_V2_AUTHORITY_INVALID")
        if (
            self.may_mint_execution_authority
            or self.may_mint_learning_authority
            or self.may_mint_effect_authority
            or self.may_mint_admission_authority
        ):
            raise ValueError("EVIDENCE_ACQUISITION_V2_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EVIDENCE_ACQUISITION_RECEIPT_V2", asdict(self))


def _unestablished_receipt(
    *,
    acquisition_id: str,
    observation_receipt_root: str,
    source_kind: str,
    provenance_roots: tuple[str, ...],
    provenance_receipt_root: str,
    replay_receipt_root: str,
    reason_codes: tuple[str, ...],
) -> EvidenceAcquisitionReceiptV2:
    receipt = EvidenceAcquisitionReceiptV2(
        status=EVIDENCE_ACQUISITION_UNESTABLISHED,
        acquisition_id=acquisition_id,
        observation_receipt_root=observation_receipt_root,
        source_kind=source_kind,
        provenance_roots=provenance_roots,
        provenance_receipt_root=provenance_receipt_root,
        replay_receipt_root=replay_receipt_root,
        independent_verifier_count=0,
        evidence_established=False,
        reason_codes=reason_codes,
    )
    receipt.validate()
    return receipt


def reject_legacy_self_asserted_acquisition(
    acquisition: EvidenceAcquisitionV1,
) -> EvidenceAcquisitionReceiptV2:
    """Migration gate: V1 flags are data, never verification evidence for V2."""

    acquisition.validate()
    provenance_assertion_root = canonical_hash(
        "AEGIS_LEGACY_PROVENANCE_ASSERTION_V1",
        {
            "provenance_roots": acquisition.provenance_roots,
            "provenance_verified": acquisition.provenance_verified,
        },
    )
    return _unestablished_receipt(
        acquisition_id=acquisition.acquisition_id,
        observation_receipt_root=acquisition.observation_receipt_root,
        source_kind=acquisition.source_kind,
        provenance_roots=acquisition.provenance_roots,
        provenance_receipt_root=provenance_assertion_root,
        replay_receipt_root=acquisition.replay_receipt_root,
        reason_codes=("LEGACY_SELF_ASSERTED_VERIFICATION_REJECTED",),
    )


def verify_evidence_acquisition_v2(
    acquisition: EvidenceAcquisitionV2,
) -> EvidenceAcquisitionReceiptV2:
    acquisition.validate()
    reasons: list[str] = []
    provenance = acquisition.provenance_receipt
    replay = acquisition.replay_receipt
    if not provenance.provenance_established:
        reasons.append("PROVENANCE_RECEIPT_UNESTABLISHED")
    if not replay.replay_verified:
        reasons.append("REPLAY_RECEIPT_UNESTABLISHED")
    if replay.observation_receipt_root != acquisition.observation_receipt_root:
        reasons.append("REPLAY_OBSERVATION_BINDING_MISMATCH")

    verifier_roots = {
        provenance.verifier_identity_root,
        replay.verifier_identity_root,
    }
    independent_verifier_count = len(verifier_roots)
    if independent_verifier_count < 2:
        reasons.append("VERIFIER_DIVERSITY_UNESTABLISHED")

    established = not reasons
    receipt = EvidenceAcquisitionReceiptV2(
        status=(
            EVIDENCE_ACQUISITION_VERIFIED
            if established
            else EVIDENCE_ACQUISITION_UNESTABLISHED
        ),
        acquisition_id=acquisition.acquisition_id,
        observation_receipt_root=acquisition.observation_receipt_root,
        source_kind=acquisition.source_kind,
        provenance_roots=provenance.declared_roots,
        provenance_receipt_root=provenance.root,
        replay_receipt_root=replay.root,
        independent_verifier_count=independent_verifier_count,
        evidence_established=established,
        reason_codes=("PROVENANCE_REPLAY_BINDING_AND_VERIFIER_DIVERSITY_VERIFIED",)
        if established
        else tuple(reasons),
    )
    receipt.validate()
    return receipt


def _persist_v2_receipt(runtime: Any, acquisition: EvidenceAcquisitionV2, receipt: EvidenceAcquisitionReceiptV2) -> None:
    receipts_dir = Path(runtime.state_root) / "evidence-acquisition-v2-receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    path = receipts_dir / f"{receipt.root}.json"
    payload = {
        "schema_version": "2.0.0",
        "acquisition": asdict(acquisition),
        "receipt": asdict(receipt),
        "receipt_root": receipt.root,
        "authority": EVIDENCE_ONLY,
        "non_claims": [
            "NO_EXECUTION_AUTHORITY",
            "NO_EFFECT_AUTHORITY",
            "NO_LEARNING_AUTHORITY",
            "NO_ATOMIC_ADMISSION_AUTHORITY",
            "NO_SEMANTIC_TRUTH_FROM_REPLAY_INTEGRITY_ALONE",
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError("EVIDENCE_ACQUISITION_V2_RECEIPT_COLLISION")
    else:
        temporary = receipts_dir / f".{receipt.root}.tmp"
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, path)

    store = getattr(runtime, "store", None)
    if store is not None and hasattr(store, "append"):
        store.append(
            event_id=f"evidence-v2-{receipt.root[:24]}",
            event_kind="EVIDENCE_ACQUISITION_V2_EVALUATED",
            payload={
                "acquisition_id": receipt.acquisition_id,
                "receipt_root": receipt.root,
                "status": receipt.status,
                "evidence_established": receipt.evidence_established,
                "authority": EVIDENCE_ONLY,
            },
        )
    counter = getattr(runtime, "_update_epistemic_counters", None)
    if callable(counter):
        counter(
            {
                "evidence_acquisition_v2_receipts": 1,
                "evidence_acquisition_v2_verified": int(receipt.evidence_established),
            }
        )


def record_replayed_evidence_acquisition(
    runtime: Any,
    *,
    acquisition_id: str,
    run_id: str,
    source_kind: str,
) -> EvidenceAcquisitionReceiptV2:
    """Dereference one resident run and derive V2 evidence from persisted bytes.

    The database-backed run receipt supplies the original digest/provenance.  A
    separate read of ``runs/<run_id>.json`` supplies the replayed bytes.  The
    comparison therefore fails closed when the persisted bundle is altered,
    even if caller-provided booleans claim success.
    """

    _require_text("acquisition_id", acquisition_id)
    _require_text("run_id", run_id)
    _require_text("source_kind", source_kind)
    run_receipt = runtime.get_run(run_id)
    if run_receipt is None:
        raise ValueError("RUN_RECEIPT_UNAVAILABLE")

    observation_receipt_root = run_receipt.self_model.get(
        "observation_receipt_root",
        ZERO_HASH,
    )
    _require_sha256("observation_receipt_root", observation_receipt_root)
    declared_roots = tuple(run_receipt.evidence_roots)
    _require_roots("declared_provenance_root", declared_roots, allow_empty=False)

    producer_identity_root = canonical_hash(
        "AEGIS_RESIDENT_RUN_PRODUCER_IDENTITY_V1",
        {"run_id": run_id, "bundle_digest": run_receipt.bundle_digest},
    )
    provenance_verifier_root = canonical_hash(
        "AEGIS_RESIDENT_PROVENANCE_VERIFIER_IDENTITY_V1",
        {"implementation": "resident-bundle-provenance-v1"},
    )
    replay_verifier_root = canonical_hash(
        "AEGIS_RESIDENT_REPLAY_VERIFIER_IDENTITY_V1",
        {"implementation": "resident-bundle-replay-v1"},
    )
    environment_root = canonical_hash(
        "AEGIS_RESIDENT_REPLAY_ENVIRONMENT_V1",
        {
            "repository_head": run_receipt.repository_head,
            "authority_ceiling": getattr(runtime, "authority_ceiling", "UNKNOWN"),
            "authority_epoch": getattr(runtime, "authority_epoch", 0),
        },
    )

    observed_roots: tuple[str, ...] = ()
    recomputed_bundle_digest = ZERO_HASH
    path = Path(runtime.state_root) / "runs" / f"{run_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        bundle_body = payload["bundle_body"]
        if not isinstance(bundle_body, Mapping):
            raise ValueError("BUNDLE_BODY_INVALID")
        recomputed_bundle_digest = canonical_hash(
            "AEGIS_RESIDENT_RUN_BUNDLE_V1",
            bundle_body,
        )
        bundled_receipt = bundle_body.get("receipt")
        if not isinstance(bundled_receipt, Mapping):
            raise ValueError("BUNDLE_RECEIPT_INVALID")
        raw_roots = bundled_receipt.get("evidence_roots")
        if not isinstance(raw_roots, list):
            raise ValueError("BUNDLE_PROVENANCE_INVALID")
        observed_roots = tuple(raw_roots)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        observed_roots = ()
        recomputed_bundle_digest = ZERO_HASH

    provenance = verify_provenance_proof(
        ProvenanceProofV1(
            declared_roots=declared_roots,
            independently_observed_roots=observed_roots,
            producer_identity_root=producer_identity_root,
            verifier_identity_root=provenance_verifier_root,
        )
    )
    replay = verify_replay_proof(
        ReplayProofV1(
            replay_id=f"resident:{run_id}",
            observation_receipt_root=observation_receipt_root,
            original_result_root=run_receipt.bundle_digest,
            replayed_result_root=recomputed_bundle_digest,
            producer_identity_root=producer_identity_root,
            verifier_identity_root=replay_verifier_root,
            environment_root=environment_root,
        )
    )
    acquisition = EvidenceAcquisitionV2(
        acquisition_id=acquisition_id,
        observation_receipt_root=observation_receipt_root,
        source_kind=source_kind,
        provenance_receipt=provenance,
        replay_receipt=replay,
    )
    receipt = verify_evidence_acquisition_v2(acquisition)
    _persist_v2_receipt(runtime, acquisition, receipt)
    return receipt


__all__ = [
    "EVIDENCE_ACQUISITION_UNESTABLISHED",
    "EVIDENCE_ACQUISITION_VERIFIED",
    "INDEPENDENT_REPLAY_UNESTABLISHED",
    "INDEPENDENT_REPLAY_VERIFIED",
    "PROVENANCE_UNESTABLISHED",
    "PROVENANCE_VERIFIED",
    "EvidenceAcquisitionReceiptV2",
    "EvidenceAcquisitionV2",
    "ProvenanceProofV1",
    "ProvenanceReceiptV1",
    "ReplayProofV1",
    "ReplayReceiptV1",
    "record_replayed_evidence_acquisition",
    "reject_legacy_self_asserted_acquisition",
    "verify_evidence_acquisition_v2",
    "verify_provenance_proof",
    "verify_replay_proof",
]
