"""Universal Intelligence Evidence Plane.

Evidence-only bridge for UCI-7/UCI-8 style evaluation on the resident runtime.
This module cannot mint execution, effect, or admission authority.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any


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
class EvidenceObservation:
    dimension: str
    baseline_score: float
    observed_score: float
    reproducible_receipt_sha: str
    tier: EpistemicAuthorityTier = EpistemicAuthorityTier.T2_HYPOTHESIS

    def validate(self, contract: EvaluationCampaignContract) -> None:
        if self.dimension not in contract.axes:
            raise ValueError(f"unknown evaluation dimension: {self.dimension}")
        if not self.reproducible_receipt_sha.strip():
            raise ValueError("reproducible_receipt_sha is required")
        if self.tier is EpistemicAuthorityTier.T0_FORMAL:
            raise ValueError("empirical evaluation observations cannot self-assert T0_FORMAL")


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

    def record_falsification_run(self, observation: EvidenceObservation) -> bool:
        observation.validate(self.contract)
        tier = (
            EpistemicAuthorityTier.T3_REFUTED
            if observation.observed_score <= observation.baseline_score
            else EpistemicAuthorityTier.T1_EMPIRICAL
        )
        admitted = replace(observation, tier=tier)
        self._recorded_evidence.append(admitted)
        return tier is not EpistemicAuthorityTier.T3_REFUTED

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
