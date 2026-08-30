"""Closed-loop epistemic actuation contracts for AEGIS Ω.

This module separates four concepts that must not be conflated:

    compute/capability != observation != evidence != learning.

Observation actions declare the transfer they intend to apply before evidence is
acquired. Information gain is established only when a bound observation both
reduces uncertainty and does not worsen calibration. Evidence acquisition binds
an observation to independently replayed provenance. Learning is established
only from a matched-control adaptation with delayed retention, transfer, a
changed durable-state commitment, and an independent replay receipt.

Every object in this module is evidence-only. Nothing here can mint execution,
effect, CompleteVerification, AtomicAdmission, or production authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re

from harness.sdk.sovereign_execution import canonical_hash


EVIDENCE_ONLY = "EVIDENCE_ONLY"
COMPUTE_CAPABILITY_EFFECT = "COMPUTE_CAPABILITY_EFFECT"
EVIDENCE_ACQUISITION_VERIFIED = "EVIDENCE_ACQUISITION_VERIFIED"
EVIDENCE_ACQUISITION_UNESTABLISHED = "EVIDENCE_ACQUISITION_UNESTABLISHED"
VERIFIED_INFORMATION_GAIN = "VERIFIED_INFORMATION_GAIN"
INFORMATION_GAIN_UNESTABLISHED = "INFORMATION_GAIN_UNESTABLISHED"
CAPABILITY_BOOST_ONLY = "CAPABILITY_BOOST_ONLY"
LEARNING_EFFECT_ESTABLISHED = "LEARNING_EFFECT_ESTABLISHED"
LEARNING_EFFECT_UNESTABLISHED = "LEARNING_EFFECT_UNESTABLISHED"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_MECHANISM_CLASSES = frozenset({"COMPUTE_ONLY", "STATE_ADAPTATION"})


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name.upper()}_INVALID")


def _require_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_bps(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_signed_bps(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not -10_000 <= value <= 10_000:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_nonnegative_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name.upper()}_INVALID")


def _require_entropy(name: str, value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name.upper()}_INVALID")
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name.upper()}_INVALID")


@dataclass(frozen=True)
class ComputeUsageV1:
    """Measured compute usage and its immediate capability effect.

    This contract deliberately does not encode retention, transfer, a matched
    control, or replayed adaptation evidence, so it cannot establish learning.
    """

    compute_action_id: str
    mechanism: str
    requested_units: int
    consumed_units: int
    pre_performance_bps: int
    immediate_performance_bps: int
    durable_state_before: str
    durable_state_after: str
    execution_receipt_root: str
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("compute_action_id", self.compute_action_id)
        _require_text("mechanism", self.mechanism)
        _require_nonnegative_int("requested_units", self.requested_units)
        _require_nonnegative_int("consumed_units", self.consumed_units)
        if self.requested_units < 1:
            raise ValueError("REQUESTED_UNITS_INVALID")
        if self.consumed_units > self.requested_units:
            raise ValueError("CONSUMED_UNITS_EXCEED_REQUEST")
        _require_bps("pre_performance_bps", self.pre_performance_bps)
        _require_bps("immediate_performance_bps", self.immediate_performance_bps)
        _require_sha256("durable_state_before", self.durable_state_before)
        _require_sha256("durable_state_after", self.durable_state_after)
        _require_sha256("execution_receipt_root", self.execution_receipt_root)
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("COMPUTE_USAGE_AUTHORITY_INVALID")


@dataclass(frozen=True)
class ComputeReceiptV1:
    status: str
    compute_action_id: str
    mechanism: str
    requested_units: int
    consumed_units: int
    immediate_gain_bps: int
    durable_state_changed: bool
    execution_receipt_root: str
    reason_codes: tuple[str, ...]
    receipt_type: str = "COMPUTE_RECEIPT_V1"
    learning_established: bool = False
    authority: str = EVIDENCE_ONLY
    may_mint_learning_authority: bool = False
    may_mint_execution_authority: bool = False
    may_mint_effect_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status != COMPUTE_CAPABILITY_EFFECT:
            raise ValueError("COMPUTE_RECEIPT_STATUS_INVALID")
        _require_text("compute_action_id", self.compute_action_id)
        _require_text("mechanism", self.mechanism)
        _require_nonnegative_int("requested_units", self.requested_units)
        _require_nonnegative_int("consumed_units", self.consumed_units)
        if self.requested_units < 1 or self.consumed_units > self.requested_units:
            raise ValueError("COMPUTE_RECEIPT_UNITS_INVALID")
        _require_signed_bps("immediate_gain_bps", self.immediate_gain_bps)
        if not isinstance(self.durable_state_changed, bool):
            raise ValueError("DURABLE_STATE_CHANGED_INVALID")
        _require_sha256("execution_receipt_root", self.execution_receipt_root)
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("COMPUTE_RECEIPT_REASONS_INVALID")
        if self.receipt_type != "COMPUTE_RECEIPT_V1":
            raise ValueError("COMPUTE_RECEIPT_TYPE_INVALID")
        if self.learning_established:
            raise ValueError("COMPUTE_RECEIPT_CANNOT_ESTABLISH_LEARNING")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("COMPUTE_RECEIPT_AUTHORITY_INVALID")
        if (
            self.may_mint_learning_authority
            or self.may_mint_execution_authority
            or self.may_mint_effect_authority
            or self.may_mint_admission_authority
        ):
            raise ValueError("COMPUTE_RECEIPT_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_COMPUTE_RECEIPT_V1", asdict(self))


def record_compute_effect(usage: ComputeUsageV1) -> ComputeReceiptV1:
    """Record an immediate compute/capability effect without inferring learning."""

    usage.validate()
    reasons = ["COMPUTE_EFFECT_IS_CAPABILITY_NOT_LEARNING"]
    durable_changed = usage.durable_state_before != usage.durable_state_after
    if durable_changed:
        reasons.append("DURABLE_STATE_CHANGE_REQUIRES_SEPARATE_LEARNING_VERIFICATION")
    receipt = ComputeReceiptV1(
        status=COMPUTE_CAPABILITY_EFFECT,
        compute_action_id=usage.compute_action_id,
        mechanism=usage.mechanism,
        requested_units=usage.requested_units,
        consumed_units=usage.consumed_units,
        immediate_gain_bps=usage.immediate_performance_bps - usage.pre_performance_bps,
        durable_state_changed=durable_changed,
        execution_receipt_root=usage.execution_receipt_root,
        reason_codes=tuple(reasons),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class EvidenceAcquisitionV1:
    """Observation/provenance bundle requiring independent replay verification."""

    acquisition_id: str
    observation_receipt_root: str
    source_kind: str
    provenance_roots: tuple[str, ...]
    replay_receipt_root: str
    provenance_verified: bool
    replay_verified: bool
    independent_verifier_count: int
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("acquisition_id", self.acquisition_id)
        _require_sha256("observation_receipt_root", self.observation_receipt_root)
        _require_text("source_kind", self.source_kind)
        if not isinstance(self.provenance_roots, tuple) or not self.provenance_roots:
            raise ValueError("PROVENANCE_ROOTS_INVALID")
        for root in self.provenance_roots:
            _require_sha256("provenance_root", root)
        _require_sha256("replay_receipt_root", self.replay_receipt_root)
        if not isinstance(self.provenance_verified, bool):
            raise ValueError("PROVENANCE_VERIFIED_INVALID")
        if not isinstance(self.replay_verified, bool):
            raise ValueError("REPLAY_VERIFIED_INVALID")
        _require_nonnegative_int("independent_verifier_count", self.independent_verifier_count)
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("EVIDENCE_ACQUISITION_AUTHORITY_INVALID")


@dataclass(frozen=True)
class EvidenceAcquisitionReceiptV1:
    status: str
    acquisition_id: str
    observation_receipt_root: str
    source_kind: str
    provenance_roots: tuple[str, ...]
    replay_receipt_root: str
    independent_verifier_count: int
    evidence_established: bool
    reason_codes: tuple[str, ...]
    receipt_type: str = "EVIDENCE_ACQUISITION_RECEIPT_V1"
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_learning_authority: bool = False
    may_mint_effect_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {EVIDENCE_ACQUISITION_VERIFIED, EVIDENCE_ACQUISITION_UNESTABLISHED}:
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_STATUS_INVALID")
        _require_text("acquisition_id", self.acquisition_id)
        _require_sha256("observation_receipt_root", self.observation_receipt_root)
        _require_text("source_kind", self.source_kind)
        if not isinstance(self.provenance_roots, tuple) or not self.provenance_roots:
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_PROVENANCE_INVALID")
        for root in self.provenance_roots:
            _require_sha256("provenance_root", root)
        _require_sha256("replay_receipt_root", self.replay_receipt_root)
        _require_nonnegative_int("independent_verifier_count", self.independent_verifier_count)
        if not isinstance(self.evidence_established, bool):
            raise ValueError("EVIDENCE_ESTABLISHED_INVALID")
        if self.evidence_established != (self.status == EVIDENCE_ACQUISITION_VERIFIED):
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_STATUS_INCONSISTENT")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_REASONS_INVALID")
        if self.receipt_type != "EVIDENCE_ACQUISITION_RECEIPT_V1":
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_TYPE_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_AUTHORITY_INVALID")
        if (
            self.may_mint_execution_authority
            or self.may_mint_learning_authority
            or self.may_mint_effect_authority
            or self.may_mint_admission_authority
        ):
            raise ValueError("EVIDENCE_ACQUISITION_RECEIPT_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EVIDENCE_ACQUISITION_RECEIPT_V1", asdict(self))


def verify_evidence_acquisition(acquisition: EvidenceAcquisitionV1) -> EvidenceAcquisitionReceiptV1:
    """Fail closed unless provenance and replay are independently verified."""

    acquisition.validate()
    reasons: list[str] = []
    if not acquisition.provenance_verified:
        reasons.append("PROVENANCE_NOT_VERIFIED")
    if not acquisition.replay_verified:
        reasons.append("REPLAY_NOT_VERIFIED")
    if acquisition.independent_verifier_count < 1:
        reasons.append("NO_INDEPENDENT_VERIFIER")

    established = not reasons
    receipt = EvidenceAcquisitionReceiptV1(
        status=(EVIDENCE_ACQUISITION_VERIFIED if established else EVIDENCE_ACQUISITION_UNESTABLISHED),
        acquisition_id=acquisition.acquisition_id,
        observation_receipt_root=acquisition.observation_receipt_root,
        source_kind=acquisition.source_kind,
        provenance_roots=acquisition.provenance_roots,
        replay_receipt_root=acquisition.replay_receipt_root,
        independent_verifier_count=acquisition.independent_verifier_count,
        evidence_established=established,
        reason_codes=("PROVENANCE_REPLAY_AND_INDEPENDENCE_VERIFIED",) if established else tuple(reasons),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class ObservationTransformV1:
    """Precommitted description of how a sensing action changes observability."""

    action_id: str
    action_kind: str
    target_scope: str
    predicted_transform: str
    budget_units: int
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("action_id", self.action_id)
        _require_text("action_kind", self.action_kind)
        _require_text("target_scope", self.target_scope)
        _require_text("predicted_transform", self.predicted_transform)
        if isinstance(self.budget_units, bool) or not isinstance(self.budget_units, int) or self.budget_units < 1:
            raise ValueError("BUDGET_UNITS_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("OBSERVATION_TRANSFORM_AUTHORITY_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_OBSERVATION_TRANSFORM_V1", asdict(self))


@dataclass(frozen=True)
class ObservationEvidenceV1:
    """Independent evidence produced after a declared observation action."""

    action_id: str
    observed_transform: str
    observation_root: str
    prior_entropy_bits: float | None
    posterior_entropy_bits: float | None
    calibration_before_bps: int | None
    calibration_after_bps: int | None
    missed_critical_feature: bool | None
    authority: str = EVIDENCE_ONLY

    def validate(self) -> None:
        _require_text("action_id", self.action_id)
        _require_text("observed_transform", self.observed_transform)
        _require_sha256("observation_root", self.observation_root)
        _require_entropy("prior_entropy_bits", self.prior_entropy_bits)
        _require_entropy("posterior_entropy_bits", self.posterior_entropy_bits)
        if (self.prior_entropy_bits is None) != (self.posterior_entropy_bits is None):
            raise ValueError("ENTROPY_PAIR_INCOMPLETE")
        if (self.calibration_before_bps is None) != (self.calibration_after_bps is None):
            raise ValueError("CALIBRATION_PAIR_INCOMPLETE")
        if self.calibration_before_bps is not None:
            _require_bps("calibration_before_bps", self.calibration_before_bps)
            _require_bps("calibration_after_bps", self.calibration_after_bps)  # type: ignore[arg-type]
        if self.missed_critical_feature is not None and not isinstance(self.missed_critical_feature, bool):
            raise ValueError("MISSED_CRITICAL_FEATURE_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("OBSERVATION_EVIDENCE_AUTHORITY_INVALID")


@dataclass(frozen=True)
class ObservationReceiptV1:
    status: str
    action_id: str
    transform_root: str
    observation_root: str
    information_gain_bits: float | None
    information_gain_established: bool
    reason_codes: tuple[str, ...]
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_learning_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {VERIFIED_INFORMATION_GAIN, INFORMATION_GAIN_UNESTABLISHED}:
            raise ValueError("OBSERVATION_RECEIPT_STATUS_INVALID")
        _require_text("action_id", self.action_id)
        _require_sha256("transform_root", self.transform_root)
        _require_sha256("observation_root", self.observation_root)
        _require_entropy("information_gain_bits", self.information_gain_bits)
        if not isinstance(self.information_gain_established, bool):
            raise ValueError("INFORMATION_GAIN_ESTABLISHED_INVALID")
        if self.information_gain_established != (self.status == VERIFIED_INFORMATION_GAIN):
            raise ValueError("OBSERVATION_RECEIPT_STATUS_INCONSISTENT")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("OBSERVATION_RECEIPT_REASONS_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("OBSERVATION_RECEIPT_AUTHORITY_INVALID")
        if self.may_mint_execution_authority or self.may_mint_learning_authority or self.may_mint_admission_authority:
            raise ValueError("OBSERVATION_RECEIPT_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_OBSERVATION_RECEIPT_V1", asdict(self))


def verify_observation_effect(
    transform: ObservationTransformV1,
    evidence: ObservationEvidenceV1,
) -> ObservationReceiptV1:
    """Verify information gain without treating confidence as evidence.

    Entropy reduction alone is insufficient: calibration may not worsen and the
    observation must not be known to have missed a critical feature.
    """

    transform.validate()
    evidence.validate()
    if transform.action_id != evidence.action_id:
        raise ValueError("OBSERVATION_ACTION_BINDING_MISMATCH")

    reasons: list[str] = []
    if transform.predicted_transform != evidence.observed_transform:
        reasons.append("OBSERVATION_TRANSFORM_MISMATCH")

    information_gain: float | None = None
    if evidence.prior_entropy_bits is None:
        reasons.append("INFORMATION_GAIN_UNMEASURED")
    else:
        information_gain = float(evidence.prior_entropy_bits) - float(evidence.posterior_entropy_bits)  # type: ignore[arg-type]
        if information_gain <= 0.0:
            reasons.append("NO_POSITIVE_ENTROPY_REDUCTION")

    if evidence.calibration_before_bps is None:
        reasons.append("CALIBRATION_UNMEASURED")
    elif evidence.calibration_after_bps < evidence.calibration_before_bps:  # type: ignore[operator]
        reasons.append("CALIBRATION_WORSENED")

    if evidence.missed_critical_feature is None:
        reasons.append("CRITICAL_FEATURE_COVERAGE_UNMEASURED")
    elif evidence.missed_critical_feature:
        reasons.append("CRITICAL_FEATURE_MISSED")

    established = not reasons and information_gain is not None and information_gain > 0.0
    receipt = ObservationReceiptV1(
        status=VERIFIED_INFORMATION_GAIN if established else INFORMATION_GAIN_UNESTABLISHED,
        action_id=transform.action_id,
        transform_root=transform.root,
        observation_root=evidence.observation_root,
        information_gain_bits=information_gain if information_gain is None or information_gain >= 0.0 else None,
        information_gain_established=established,
        reason_codes=("NONE",) if established else tuple(reasons),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class LearningInterventionV1:
    """Matched-control evidence request for durable learning, not output quality."""

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
    independent_replay_receipt_sha: str
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
        _require_sha256("independent_replay_receipt_sha", self.independent_replay_receipt_sha)
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("LEARNING_INTERVENTION_AUTHORITY_INVALID")


@dataclass(frozen=True)
class LearningReceiptV1:
    status: str
    intervention_id: str
    immediate_gain_bps: int
    retention_gain_vs_control_bps: int
    transfer_gain_vs_control_bps: int
    durable_state_changed: bool
    learning_established: bool
    reason_codes: tuple[str, ...]
    authority: str = EVIDENCE_ONLY
    may_mint_execution_authority: bool = False
    may_mint_effect_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        if self.status not in {LEARNING_EFFECT_ESTABLISHED, LEARNING_EFFECT_UNESTABLISHED, CAPABILITY_BOOST_ONLY}:
            raise ValueError("LEARNING_RECEIPT_STATUS_INVALID")
        _require_text("intervention_id", self.intervention_id)
        if not isinstance(self.learning_established, bool) or not isinstance(self.durable_state_changed, bool):
            raise ValueError("LEARNING_RECEIPT_BOOLEAN_INVALID")
        if self.learning_established != (self.status == LEARNING_EFFECT_ESTABLISHED):
            raise ValueError("LEARNING_RECEIPT_STATUS_INCONSISTENT")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("LEARNING_RECEIPT_REASONS_INVALID")
        if self.authority != EVIDENCE_ONLY:
            raise ValueError("LEARNING_RECEIPT_AUTHORITY_INVALID")
        if self.may_mint_execution_authority or self.may_mint_effect_authority or self.may_mint_admission_authority:
            raise ValueError("LEARNING_RECEIPT_AUTHORITY_ESCALATION")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_LEARNING_RECEIPT_V1", asdict(self))


def evaluate_learning_effect(
    intervention: LearningInterventionV1,
    *,
    minimum_effect_bps: int = 100,
) -> LearningReceiptV1:
    """Classify durable learning separately from immediate capability gain."""

    intervention.validate()
    if isinstance(minimum_effect_bps, bool) or not isinstance(minimum_effect_bps, int) or not 0 <= minimum_effect_bps <= 10_000:
        raise ValueError("MINIMUM_EFFECT_BPS_INVALID")

    immediate_gain = intervention.immediate_performance_bps - intervention.pre_performance_bps
    treatment_retention = intervention.delayed_performance_bps - intervention.pre_performance_bps
    control_retention = intervention.control_delayed_performance_bps - intervention.control_pre_performance_bps
    retention_vs_control = treatment_retention - control_retention
    treatment_transfer = intervention.post_transfer_bps - intervention.pre_transfer_bps
    control_transfer = intervention.control_post_transfer_bps - intervention.control_pre_transfer_bps
    transfer_vs_control = treatment_transfer - control_transfer
    durable_changed = intervention.durable_state_before != intervention.durable_state_after

    if intervention.mechanism_class == "COMPUTE_ONLY":
        reasons = ("COMPUTE_IS_CAPABILITY_NOT_LEARNING",)
        status = CAPABILITY_BOOST_ONLY if immediate_gain > 0 else LEARNING_EFFECT_UNESTABLISHED
        receipt = LearningReceiptV1(
            status=status,
            intervention_id=intervention.intervention_id,
            immediate_gain_bps=immediate_gain,
            retention_gain_vs_control_bps=retention_vs_control,
            transfer_gain_vs_control_bps=transfer_vs_control,
            durable_state_changed=durable_changed,
            learning_established=False,
            reason_codes=reasons,
        )
        receipt.validate()
        return receipt

    reasons: list[str] = []
    if retention_vs_control < minimum_effect_bps:
        reasons.append("RETENTION_EFFECT_BELOW_THRESHOLD")
    if transfer_vs_control < minimum_effect_bps:
        reasons.append("TRANSFER_EFFECT_BELOW_THRESHOLD")
    if not durable_changed:
        reasons.append("DURABLE_STATE_UNCHANGED")

    established = not reasons
    if established:
        status = LEARNING_EFFECT_ESTABLISHED
        reason_codes = ("MATCHED_CONTROL_RETENTION_TRANSFER_AND_DURABLE_STATE_PASS",)
    elif immediate_gain > 0:
        status = CAPABILITY_BOOST_ONLY
        reason_codes = tuple(reasons + ["IMMEDIATE_GAIN_NOT_DURABLE_LEARNING"])
    else:
        status = LEARNING_EFFECT_UNESTABLISHED
        reason_codes = tuple(reasons)

    receipt = LearningReceiptV1(
        status=status,
        intervention_id=intervention.intervention_id,
        immediate_gain_bps=immediate_gain,
        retention_gain_vs_control_bps=retention_vs_control,
        transfer_gain_vs_control_bps=transfer_vs_control,
        durable_state_changed=durable_changed,
        learning_established=established,
        reason_codes=reason_codes,
    )
    receipt.validate()
    return receipt


__all__ = [
    "CAPABILITY_BOOST_ONLY",
    "COMPUTE_CAPABILITY_EFFECT",
    "EVIDENCE_ACQUISITION_UNESTABLISHED",
    "EVIDENCE_ACQUISITION_VERIFIED",
    "EVIDENCE_ONLY",
    "INFORMATION_GAIN_UNESTABLISHED",
    "LEARNING_EFFECT_ESTABLISHED",
    "LEARNING_EFFECT_UNESTABLISHED",
    "VERIFIED_INFORMATION_GAIN",
    "ComputeReceiptV1",
    "ComputeUsageV1",
    "EvidenceAcquisitionReceiptV1",
    "EvidenceAcquisitionV1",
    "LearningInterventionV1",
    "LearningReceiptV1",
    "ObservationEvidenceV1",
    "ObservationReceiptV1",
    "ObservationTransformV1",
    "evaluate_learning_effect",
    "record_compute_effect",
    "verify_evidence_acquisition",
    "verify_observation_effect",
]
