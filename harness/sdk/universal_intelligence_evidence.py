"""Universal Intelligence Evidence Plane.

Evidence-only bridge for UCI-7/UCI-8 style evaluation on the resident runtime.
This module cannot mint execution, effect, or admission authority.

T1 empirical status is deliberately stronger than "score went up". A positive
observation reaches T1 only when it is bound to a replay receipt that
mechanically establishes exact result-root equality, an external replication
result-root match, explicit preregistration/checker/contamination/constituent
commitments, and producer/verifier/replicator identity separation. These are
binding checks, not semantic truth claims about the committed artifacts.
Unbound positive output remains T2 hypothesis evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
import math
import re
from typing import Any

from harness.sdk.sovereign_execution import canonical_hash


class EpistemicAuthorityTier(str, Enum):
    T0_FORMAL = "T0_FORMAL"
    T1_EMPIRICAL = "T1_EMPIRICAL"
    T2_HYPOTHESIS = "T2_HYPOTHESIS"
    T3_REFUTED = "T3_REFUTED"


REQUIRED_AXES = (
    "transfer",
    "cross_domain_generality",
    "agency",
    "long_horizon_reliability",
    "safe_adaptation",
    "metacognitive_calibration",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ZERO_HASH = "0" * 64
_REPLAY_SUCCESS_REASON = "REPLAY_ROOTS_CONTROLS_AND_INDEPENDENT_IDENTITIES_BOUND"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name.upper()}_INVALID")


def _require_sha256(name: str, value: str, *, allow_zero: bool = False) -> None:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name.upper()}_INVALID")
    if not allow_zero and value == _ZERO_HASH:
        raise ValueError(f"{name.upper()}_ZERO_HASH_FORBIDDEN")


def _require_bps(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise ValueError(f"{name.upper()}_INVALID")


def _score_to_bps(value: float) -> int | None:
    """Return exact basis-point encoding for a score, or None if not representable."""

    try:
        scaled = Decimal(str(value)) * Decimal(10_000)
    except (InvalidOperation, ValueError):
        return None
    integral = scaled.to_integral_value()
    if scaled != integral:
        return None
    encoded = int(integral)
    return encoded if 0 <= encoded <= 10_000 else None


@dataclass(frozen=True)
class EvaluationCampaignContract:
    campaign_id: str
    axes: tuple[str, ...] = field(default_factory=lambda: REQUIRED_AXES)
    anti_gaming_active: bool = True
    baseline_attribution_required: bool = True

    def validate(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError("campaign_id must be non-empty")
        if tuple(self.axes) != REQUIRED_AXES:
            raise ValueError("campaign axes must exactly match the frozen UCI evidence axes")
        if not self.anti_gaming_active:
            raise ValueError("anti-gaming cannot be disabled")
        if not self.baseline_attribution_required:
            raise ValueError("baseline attribution cannot be disabled")


@dataclass(frozen=True)
class EvaluationReplayProofV1:
    """Untrusted replay/control commitment bundle for one empirical observation."""

    campaign_id: str
    dimension: str
    baseline_score_bps: int
    observed_score_bps: int
    original_result_root: str
    replayed_result_root: str
    external_replication_result_root: str
    preregistration_root: str
    hidden_checker_commitment_root: str
    contamination_control_root: str
    strongest_constituent_root: str
    producer_identity_root: str
    verifier_identity_root: str
    replicator_identity_root: str

    def validate(self) -> None:
        _require_text("campaign_id", self.campaign_id)
        _require_text("dimension", self.dimension)
        _require_bps("baseline_score_bps", self.baseline_score_bps)
        _require_bps("observed_score_bps", self.observed_score_bps)
        for name in (
            "original_result_root",
            "replayed_result_root",
            "external_replication_result_root",
            "preregistration_root",
            "hidden_checker_commitment_root",
            "contamination_control_root",
            "strongest_constituent_root",
            "producer_identity_root",
            "verifier_identity_root",
            "replicator_identity_root",
        ):
            _require_sha256(name, getattr(self, name))


@dataclass(frozen=True)
class EvaluationReplayReceiptV1:
    """Mechanical replay binding receipt with zero execution/admission authority."""

    campaign_id: str
    dimension: str
    baseline_score_bps: int
    observed_score_bps: int
    original_result_root: str
    replayed_result_root: str
    external_replication_result_root: str
    preregistration_root: str
    hidden_checker_commitment_root: str
    contamination_control_root: str
    strongest_constituent_root: str
    producer_identity_root: str
    verifier_identity_root: str
    replicator_identity_root: str
    replay_verified: bool
    reason_codes: tuple[str, ...]
    receipt_type: str = "EVALUATION_REPLAY_RECEIPT_V1"
    authority_weight: int = 0
    may_mint_execution_authority: bool = False
    may_mint_effect_authority: bool = False
    may_mint_admission_authority: bool = False

    def validate(self) -> None:
        EvaluationReplayProofV1(
            campaign_id=self.campaign_id,
            dimension=self.dimension,
            baseline_score_bps=self.baseline_score_bps,
            observed_score_bps=self.observed_score_bps,
            original_result_root=self.original_result_root,
            replayed_result_root=self.replayed_result_root,
            external_replication_result_root=self.external_replication_result_root,
            preregistration_root=self.preregistration_root,
            hidden_checker_commitment_root=self.hidden_checker_commitment_root,
            contamination_control_root=self.contamination_control_root,
            strongest_constituent_root=self.strongest_constituent_root,
            producer_identity_root=self.producer_identity_root,
            verifier_identity_root=self.verifier_identity_root,
            replicator_identity_root=self.replicator_identity_root,
        ).validate()
        if not isinstance(self.replay_verified, bool):
            raise ValueError("REPLAY_VERIFIED_INVALID")
        if not isinstance(self.reason_codes, tuple) or not self.reason_codes:
            raise ValueError("REASON_CODES_INVALID")
        if self.receipt_type != "EVALUATION_REPLAY_RECEIPT_V1":
            raise ValueError("RECEIPT_TYPE_INVALID")
        if self.authority_weight != 0:
            raise ValueError("EVALUATION_REPLAY_AUTHORITY_WEIGHT_INVALID")
        if self.may_mint_execution_authority or self.may_mint_effect_authority or self.may_mint_admission_authority:
            raise ValueError("EVALUATION_REPLAY_AUTHORITY_ESCALATION")
        if self.replay_verified != (self.reason_codes == (_REPLAY_SUCCESS_REASON,)):
            raise ValueError("EVALUATION_REPLAY_STATUS_INCONSISTENT")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EVALUATION_REPLAY_RECEIPT_V1", asdict(self))


def verify_evaluation_replay(proof: EvaluationReplayProofV1) -> EvaluationReplayReceiptV1:
    """Verify mechanical replay bindings without asserting artifact semantics."""

    proof.validate()
    reasons: list[str] = []
    if proof.original_result_root != proof.replayed_result_root:
        reasons.append("REPLAY_RESULT_MISMATCH")
    if proof.original_result_root != proof.external_replication_result_root:
        reasons.append("EXTERNAL_REPLICATION_RESULT_MISMATCH")

    identities = (
        proof.producer_identity_root,
        proof.verifier_identity_root,
        proof.replicator_identity_root,
    )
    if proof.producer_identity_root == proof.verifier_identity_root:
        reasons.append("REPLAY_VERIFIER_NOT_INDEPENDENT")
    if proof.producer_identity_root == proof.replicator_identity_root:
        reasons.append("REPLICATOR_NOT_INDEPENDENT_FROM_PRODUCER")
    if proof.verifier_identity_root == proof.replicator_identity_root:
        reasons.append("REPLICATOR_NOT_INDEPENDENT_FROM_VERIFIER")
    if len(set(identities)) != 3 and not reasons:
        reasons.append("INDEPENDENT_IDENTITY_SET_INVALID")

    verified = not reasons
    receipt = EvaluationReplayReceiptV1(
        campaign_id=proof.campaign_id,
        dimension=proof.dimension,
        baseline_score_bps=proof.baseline_score_bps,
        observed_score_bps=proof.observed_score_bps,
        original_result_root=proof.original_result_root,
        replayed_result_root=proof.replayed_result_root,
        external_replication_result_root=proof.external_replication_result_root,
        preregistration_root=proof.preregistration_root,
        hidden_checker_commitment_root=proof.hidden_checker_commitment_root,
        contamination_control_root=proof.contamination_control_root,
        strongest_constituent_root=proof.strongest_constituent_root,
        producer_identity_root=proof.producer_identity_root,
        verifier_identity_root=proof.verifier_identity_root,
        replicator_identity_root=proof.replicator_identity_root,
        replay_verified=verified,
        reason_codes=(_REPLAY_SUCCESS_REASON,) if verified else tuple(reasons),
    )
    receipt.validate()
    return receipt


@dataclass(frozen=True)
class EvidenceObservation:
    dimension: str
    baseline_score: float
    observed_score: float
    reproducible_receipt_sha: str
    tier: EpistemicAuthorityTier = EpistemicAuthorityTier.T2_HYPOTHESIS
    verification_receipt: EvaluationReplayReceiptV1 | None = None
    verification_reason_codes: tuple[str, ...] = ()

    def validate(self, contract: EvaluationCampaignContract) -> None:
        if self.dimension not in contract.axes:
            raise ValueError(f"unknown evaluation dimension: {self.dimension}")
        for name, value in (("baseline_score", self.baseline_score), ("observed_score", self.observed_score)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} must be finite and in [0, 1]")
        if not isinstance(self.reproducible_receipt_sha, str) or not self.reproducible_receipt_sha.strip():
            raise ValueError("reproducible_receipt_sha is required")
        if self.tier is EpistemicAuthorityTier.T0_FORMAL:
            raise ValueError("empirical evaluation observations cannot self-assert T0_FORMAL")
        if self.verification_receipt is not None:
            if not isinstance(self.verification_receipt, EvaluationReplayReceiptV1):
                raise ValueError("verification_receipt must be EvaluationReplayReceiptV1")
            self.verification_receipt.validate()
        if not isinstance(self.verification_reason_codes, tuple):
            raise ValueError("verification_reason_codes must be a tuple")


class UniversalIntelligenceEvidencePlane:
    """Records bounded capability evidence without any authority-writing API."""

    authority_weight = 0
    may_mint_execution_authority = False
    may_mint_effect_authority = False
    may_mint_admission_authority = False

    def __init__(self, contract: EvaluationCampaignContract):
        contract.validate()
        self.contract = contract
        self._recorded_evidence: list[EvidenceObservation] = []

    @property
    def recorded_evidence(self) -> tuple[EvidenceObservation, ...]:
        return tuple(self._recorded_evidence)

    def _verification_reasons(self, observation: EvidenceObservation) -> tuple[str, ...]:
        receipt = observation.verification_receipt
        if receipt is None:
            return ("REPLAY_RECEIPT_UNVERIFIED",)

        receipt.validate()
        reasons: list[str] = []
        if not receipt.replay_verified:
            reasons.append("REPLAY_RECEIPT_UNESTABLISHED")
        if observation.reproducible_receipt_sha != receipt.root:
            reasons.append("REPLAY_RECEIPT_ROOT_BINDING_MISMATCH")
        if receipt.campaign_id != self.contract.campaign_id:
            reasons.append("REPLAY_CAMPAIGN_BINDING_MISMATCH")
        if receipt.dimension != observation.dimension:
            reasons.append("REPLAY_DIMENSION_BINDING_MISMATCH")

        baseline_bps = _score_to_bps(float(observation.baseline_score))
        observed_bps = _score_to_bps(float(observation.observed_score))
        if baseline_bps is None or observed_bps is None:
            reasons.append("OBSERVATION_SCORE_NOT_EXACT_BPS")
        elif (
            receipt.baseline_score_bps != baseline_bps
            or receipt.observed_score_bps != observed_bps
        ):
            reasons.append("REPLAY_SCORE_BINDING_MISMATCH")

        return tuple(dict.fromkeys(reasons))

    def record_falsification_run(self, observation: EvidenceObservation) -> bool:
        observation.validate(self.contract)

        if observation.observed_score <= observation.baseline_score:
            admitted = replace(
                observation,
                tier=EpistemicAuthorityTier.T3_REFUTED,
                verification_reason_codes=("NON_IMPROVEMENT_REFUTED",),
            )
            self._recorded_evidence.append(admitted)
            return False

        reasons = self._verification_reasons(observation)
        if reasons:
            admitted = replace(
                observation,
                tier=EpistemicAuthorityTier.T2_HYPOTHESIS,
                verification_reason_codes=reasons,
            )
            self._recorded_evidence.append(admitted)
            return False

        admitted = replace(
            observation,
            tier=EpistemicAuthorityTier.T1_EMPIRICAL,
            verification_reason_codes=(_REPLAY_SUCCESS_REASON,),
        )
        self._recorded_evidence.append(admitted)
        return True

    def evaluate_generalization_status(self) -> dict[str, Any]:
        covered = {o.dimension for o in self._recorded_evidence}
        positive = {
            o.dimension
            for o in self._recorded_evidence
            if o.tier is EpistemicAuthorityTier.T1_EMPIRICAL
        }
        return {
            "campaign_id": self.contract.campaign_id,
            "observations_count": len(self._recorded_evidence),
            "covered_axes": sorted(covered),
            "positive_axes": sorted(positive),
            "all_required_axes_observed": covered == set(self.contract.axes),
            "all_required_axes_positive": positive == set(self.contract.axes),
            "agi_proven": False,
            "authority_weight": self.authority_weight,
            "status": "EMPIRICAL_EVALUATION_ACTIVE",
        }


__all__ = [
    "EpistemicAuthorityTier",
    "EvaluationCampaignContract",
    "EvaluationReplayProofV1",
    "EvaluationReplayReceiptV1",
    "EvidenceObservation",
    "REQUIRED_AXES",
    "UniversalIntelligenceEvidencePlane",
    "verify_evaluation_replay",
]
