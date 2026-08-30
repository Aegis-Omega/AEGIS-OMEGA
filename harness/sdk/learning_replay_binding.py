"""Replay-bound durable-learning verification for AEGIS Ω.

V1 learning interventions contain an opaque ``independent_replay_receipt_sha``.
A syntactically valid hash is not evidence that anything was replayed.  This V2
module therefore gives the measured learning study its own canonical root and
requires both a verified evidence-acquisition receipt and the exact replay
receipt whose original/replayed result roots equal that study root.

The result is evidence only.  Learning evidence never mints execution, effect,
CompleteVerification, AtomicAdmission, or any other production authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
from typing import Any

from harness.sdk.closed_loop_epistemic_actuation import (
    CAPABILITY_BOOST_ONLY,
    EVIDENCE_ONLY,
    LEARNING_EFFECT_ESTABLISHED,
    LEARNING_EFFECT_UNESTABLISHED,
    LearningInterventionV1,
)
from harness.sdk.evidence_replay_binding import (
    EvidenceAcquisitionReceiptV2,
    ReplayReceiptV1,
)
from harness.sdk.sovereign_execution import canonical_hash


ZERO_HASH = "0" * 64
_ALLOWED_MECHANISM_CLASSES = frozenset({"COMPUTE_ONLY", "STATE_ADAPTATION"})


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name.upper()}_INVALID")


def _require_bps(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_signed_bps(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not -10_000 <= value <= 10_000:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name.upper()}_INVALID")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name.upper()}_INVALID") from exc
    if value.lower() != value:
        raise ValueError(f"{name.upper()}_INVALID")


@dataclass(frozen=True)
class LearningStudyV2:
    """Canonical matched-control study whose exact bytes are the replay subject."""

    intervention_id: str
    mechanism_class: str
    mechanism: str
    matched_control_id: str
    pre_performance_bps: int
    immediate_performance_bps: int
    delayed_performance_bps: int
    control_pre_performance_bps: int
    control_delayed_performance_bps: int
    pre_transfer_bps: int
    post_transfer_bps: int
    control_pre_transfer_bps: int
    control_post_transfer_bps: int
    durable_state_before: str
    durable_state_after: str
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("intervention_id", self.intervention_id)
        _require_text("mechanism_class", self.mechanism_class)
        if self.mechanism_class not in _ALLOWED_MECHANISM_CLASSES:
            raise ValueError("MECHANISM_CLASS_INVALID")
        _require_text("mechanism", self.mechanism)
        _require_text("matched_control_id", self.matched_control_id)
        for name in (
            "pre_performance_bps",
            "immediate_performance_bps",
            "delayed_performance_bps",
            "control_pre_performance_bps",
            "control_delayed_performance_bps",
            "pre_transfer_bps",
            "post_transfer_bps",
            "control_pre_transfer_bps",
            "control_post_transfer_bps",
        ):
            _require_bps(name, getattr(self, name))
        _require_sha256("durable_state_before", self.durable_state_before)
        _require_sha256("durable_state_after", self.durable_state_after)
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("LEARNING_STUDY_AUTHORITY_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_LEARNING_STUDY_V2", asdict(self))


@dataclass(frozen=True)
class LearningVerificationV2:
    """Typed proof bundle: study + verified acquisition + exact replay receipt."""

    study: LearningStudyV2
    evidence_receipt: EvidenceAcquisitionReceiptV2
    replay_receipt: ReplayReceiptV1
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        self.study.validate()
        self.evidence_receipt.validate()
        self.replay_receipt.validate()
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("LEARNING_VERIFICATION_AUTHORITY_INVALID")


@dataclass(frozen=True)
class LearningReceiptV2:
    status: str
    intervention_id: str
    study_root: str
    evidence_receipt_root: str
    replay_receipt_root: str
    immediate_gain_bps: int
    retention_gain_vs_control_bps: int
    transfer_gain_vs_control_bps: int
    durable_state_changed: bool
    learning_established: bool
    reason_codes: tuple[str, ...]
    receipt_type: str = "LEARNING_RECEIPT_V2"
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_effect_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {
            LEARNING_EFFECT_ESTABLISHED,
            LEARNING_EFFECT_UNESTABLISHED,
            CAPABILITY_BOOST_ONLY,
        }:
            raise ValueError("LEARNING_V2_STATUS_INVALID")
        _require_text("intervention_id", self.intervention_id)
        _require_sha256("study_root", self.study_root)
        _require_sha256("evidence_receipt_root", self.evidence_receipt_root)
        _require_sha256("replay_receipt_root", self.replay_receipt_root)
        for name in (
            "immediate_gain_bps",
            "retention_gain_vs_control_bps",
            "transfer_gain_vs_control_bps",
        ):
            _require_signed_bps(name, getattr(self, name))
        if not isinstance(self.durable_state_changed, bool):
            raise ValueError("DURABLE_STATE_CHANGED_INVALID")
        if not isinstance(self.learning_established, bool):
            raise ValueError("LEARNING_ESTABLISHED_INVALID")
        if self.learning_established != (self.status == LEARNING_EFFECT_ESTABLISHED):
            raise ValueError("LEARNING_V2_STATUS_INCONSISTENT")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("LEARNING_V2_REASONS_INVALID")
        if self.receipt_type != "LEARNING_RECEIPT_V2":
            raise ValueError("LEARNING_V2_TYPE_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("LEARNING_V2_AUTHORITY_INVALID")
        if (
            self.may_mint_execution_authority
            or self.may_mint_effect_authority
            or self.may_mint_admission_authority
        ):
            raise ValueError("LEARNING_V2_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_LEARNING_RECEIPT_V2", asdict(self))


def _effects(study: LearningStudyV2) -> tuple[int, int, int, bool]:
    immediate_gain = study.immediate_performance_bps - study.pre_performance_bps
    treatment_retention = study.delayed_performance_bps - study.pre_performance_bps
    control_retention = (
        study.control_delayed_performance_bps - study.control_pre_performance_bps
    )
    retention_vs_control = treatment_retention - control_retention
    treatment_transfer = study.post_transfer_bps - study.pre_transfer_bps
    control_transfer = (
        study.control_post_transfer_bps - study.control_pre_transfer_bps
    )
    transfer_vs_control = treatment_transfer - control_transfer
    durable_changed = study.durable_state_before != study.durable_state_after
    return immediate_gain, retention_vs_control, transfer_vs_control, durable_changed


def reject_legacy_learning_intervention(
    intervention: LearningInterventionV1,
) -> LearningReceiptV2:
    """Migration boundary: an opaque replay hash can never establish V2 learning."""

    intervention.validate()
    immediate_gain = intervention.immediate_performance_bps - intervention.pre_performance_bps
    retention_vs_control = (
        intervention.delayed_performance_bps
        - intervention.pre_performance_bps
        - (
            intervention.control_delayed_performance_bps
            - intervention.control_pre_performance_bps
        )
    )
    transfer_vs_control = (
        intervention.post_transfer_bps
        - intervention.pre_transfer_bps
        - (
            intervention.control_post_transfer_bps
            - intervention.control_pre_transfer_bps
        )
    )
    legacy_study_root = canonical_hash(
        "AEGIS_LEGACY_LEARNING_INTERVENTION_ASSERTION_V1",
        asdict(intervention),
    )
    receipt = LearningReceiptV2(
        status=LEARNING_EFFECT_UNESTABLISHED,
        intervention_id=intervention.intervention_id,
        study_root=legacy_study_root,
        evidence_receipt_root=ZERO_HASH,
        replay_receipt_root=intervention.independent_replay_receipt_sha,
        immediate_gain_bps=immediate_gain,
        retention_gain_vs_control_bps=retention_vs_control,
        transfer_gain_vs_control_bps=transfer_vs_control,
        durable_state_changed=(
            intervention.durable_state_before != intervention.durable_state_after
        ),
        learning_established=False,
        reason_codes=("LEGACY_UNDEREFERENCED_REPLAY_HASH_REJECTED",),
    )
    receipt.validate()
    return receipt


def evaluate_learning_effect_v2(
    verification: LearningVerificationV2,
    *,
    minimum_effect_bps: int = 100,
) -> LearningReceiptV2:
    """Establish learning only from replay-bound, provenance-verified study evidence."""

    verification.validate()
    if (
        isinstance(minimum_effect_bps, bool)
        or not isinstance(minimum_effect_bps, int)
        or not 0 <= minimum_effect_bps <= 10_000
    ):
        raise ValueError("MINIMUM_EFFECT_BPS_INVALID")

    study = verification.study
    evidence = verification.evidence_receipt
    replay = verification.replay_receipt
    immediate_gain, retention_vs_control, transfer_vs_control, durable_changed = _effects(study)

    if study.mechanism_class == "COMPUTE_ONLY":
        receipt = LearningReceiptV2(
            status=(CAPABILITY_BOOST_ONLY if immediate_gain > 0 else LEARNING_EFFECT_UNESTABLISHED),
            intervention_id=study.intervention_id,
            study_root=study.root,
            evidence_receipt_root=evidence.root,
            replay_receipt_root=replay.root,
            immediate_gain_bps=immediate_gain,
            retention_gain_vs_control_bps=retention_vs_control,
            transfer_gain_vs_control_bps=transfer_vs_control,
            durable_state_changed=durable_changed,
            learning_established=False,
            reason_codes=("COMPUTE_IS_CAPABILITY_NOT_LEARNING",),
        )
        receipt.validate()
        return receipt

    reasons: list[str] = []
    if not evidence.evidence_established:
        reasons.append("LEARNING_EVIDENCE_ACQUISITION_UNESTABLISHED")
    if not replay.replay_verified:
        reasons.append("LEARNING_REPLAY_UNESTABLISHED")
    if evidence.replay_receipt_root != replay.root:
        reasons.append("LEARNING_EVIDENCE_REPLAY_RECEIPT_MISMATCH")
    if evidence.observation_receipt_root != replay.observation_receipt_root:
        reasons.append("LEARNING_OBSERVATION_REPLAY_BINDING_MISMATCH")
    if replay.original_result_root != study.root or replay.replayed_result_root != study.root:
        reasons.append("LEARNING_STUDY_REPLAY_BINDING_MISMATCH")
    if study.root not in evidence.provenance_roots:
        reasons.append("LEARNING_STUDY_PROVENANCE_BINDING_MISSING")
    if retention_vs_control < minimum_effect_bps:
        reasons.append("RETENTION_EFFECT_BELOW_THRESHOLD")
    if transfer_vs_control < minimum_effect_bps:
        reasons.append("TRANSFER_EFFECT_BELOW_THRESHOLD")
    if not durable_changed:
        reasons.append("DURABLE_STATE_UNCHANGED")

    established = not reasons
    receipt = LearningReceiptV2(
        status=(LEARNING_EFFECT_ESTABLISHED if established else LEARNING_EFFECT_UNESTABLISHED),
        intervention_id=study.intervention_id,
        study_root=study.root,
        evidence_receipt_root=evidence.root,
        replay_receipt_root=replay.root,
        immediate_gain_bps=immediate_gain,
        retention_gain_vs_control_bps=retention_vs_control,
        transfer_gain_vs_control_bps=transfer_vs_control,
        durable_state_changed=durable_changed,
        learning_established=established,
        reason_codes=("MATCHED_CONTROL_RETENTION_TRANSFER_REPLAY_AND_PROVENANCE_VERIFIED",)
        if established
        else tuple(reasons),
    )
    receipt.validate()
    return receipt


def evaluate_verified_learning_intervention(
    runtime: Any,
    verification: LearningVerificationV2,
    *,
    minimum_effect_bps: int = 100,
) -> LearningReceiptV2:
    """Evaluate and persist a V2 learning receipt inside a resident state root."""

    receipt = evaluate_learning_effect_v2(
        verification,
        minimum_effect_bps=minimum_effect_bps,
    )
    receipts_dir = Path(runtime.state_root) / "learning-v2-receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    path = receipts_dir / f"{receipt.root}.json"
    payload = {
        "schema_version": "2.0.0",
        "study": asdict(verification.study),
        "evidence_receipt": asdict(verification.evidence_receipt),
        "replay_receipt": asdict(verification.replay_receipt),
        "receipt": asdict(receipt),
        "receipt_root": receipt.root,
        "authority": EVIDENCE_ONLY,
        "non_claims": [
            "NO_EXECUTION_AUTHORITY",
            "NO_EFFECT_AUTHORITY",
            "NO_ATOMIC_ADMISSION_AUTHORITY",
            "NO_LEARNING_FROM_OPAQUE_REPLAY_HASH",
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError("LEARNING_V2_RECEIPT_COLLISION")
    else:
        temporary = receipts_dir / f".{receipt.root}.tmp"
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, path)

    store = getattr(runtime, "store", None)
    if store is not None and hasattr(store, "append"):
        store.append(
            event_id=f"learning-v2-{receipt.root[:24]}",
            event_kind="LEARNING_EFFECT_V2_EVALUATED",
            payload={
                "intervention_id": receipt.intervention_id,
                "study_root": receipt.study_root,
                "evidence_receipt_root": receipt.evidence_receipt_root,
                "replay_receipt_root": receipt.replay_receipt_root,
                "receipt_root": receipt.root,
                "status": receipt.status,
                "learning_established": receipt.learning_established,
                "authority": EVIDENCE_ONLY,
            },
        )
    counter = getattr(runtime, "_update_epistemic_counters", None)
    if callable(counter):
        counter(
            {
                "learning_v2_evaluations": 1,
                "learning_v2_established": int(receipt.learning_established),
                "learning_v2_capability_boost_only": int(
                    receipt.status == CAPABILITY_BOOST_ONLY
                ),
            }
        )
    return receipt


__all__ = [
    "CAPABILITY_BOOST_ONLY",
    "LEARNING_EFFECT_ESTABLISHED",
    "LEARNING_EFFECT_UNESTABLISHED",
    "LearningReceiptV2",
    "LearningStudyV2",
    "LearningVerificationV2",
    "evaluate_learning_effect_v2",
    "evaluate_verified_learning_intervention",
    "reject_legacy_learning_intervention",
]
