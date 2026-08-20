"""UCI-8 preregistered evaluation-campaign reference contract.

This module binds evidence from real benchmark campaigns to an immutable,
content-addressed manifest. It does not run benchmarks, does not grant authority,
and does not define an ``AGI_PROVEN`` state.

UCI-8 v1 intentionally supports descriptive paired evidence only. Statistical
significance, confidence intervals, and causal attribution are outside this
version's admitted claim surface.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from harness.sdk.agi_evidence import CapabilityTrialResultV1, ContaminationClass
from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")

TASK_TRIAL_UNIT_KIND = "CAMPAIGN_TASK_TRIAL_UNIT_V1"
BENCHMARK_TRACK_KIND = "BENCHMARK_TRACK_SPEC_V1"
CAMPAIGN_MANIFEST_KIND = "EVALUATION_CAMPAIGN_MANIFEST_V1"
PAIRED_TRIAL_KIND = "PAIRED_BENCHMARK_TRIAL_V1"
CAMPAIGN_EVIDENCE_BUNDLE_KIND = "CAMPAIGN_EVIDENCE_BUNDLE_V1"


class EvaluationCampaignError(ValueError):
    """Fail-closed UCI-8 contract error."""


class BenchmarkFamily(str, Enum):
    ARC_AGI_2 = "ARC_AGI_2"
    GAIA = "GAIA"
    METR_TIME_HORIZON = "METR_TIME_HORIZON"
    OTHER_PREREGISTERED = "OTHER_PREREGISTERED"


class SplitPrivacy(str, Enum):
    PUBLIC_DEV = "PUBLIC_DEV"
    SEMI_PRIVATE = "SEMI_PRIVATE"
    PRIVATE = "PRIVATE"
    GATED_PRIVATE = "GATED_PRIVATE"


class MetricKind(str, Enum):
    EXACT_MATCH_ACCURACY = "EXACT_MATCH_ACCURACY"
    TOOL_ASSISTED_QA_ACCURACY = "TOOL_ASSISTED_QA_ACCURACY"
    HUMAN_EQUIVALENT_TASK_HORIZON = "HUMAN_EQUIVALENT_TASK_HORIZON"
    OTHER_DETERMINISTIC = "OTHER_DETERMINISTIC"


class StatisticalMode(str, Enum):
    PAIRED_DESCRIPTIVE_V1 = "PAIRED_DESCRIPTIVE_V1"


class CampaignEvidenceStatus(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    DEVELOPMENT_EVIDENCE_ONLY = "DEVELOPMENT_EVIDENCE_ONLY"
    HELD_OUT_EVIDENCE_COMPLETE = "HELD_OUT_EVIDENCE_COMPLETE"
    COLLECTIVE_CONTRIBUTION_EVALUABLE = "COLLECTIVE_CONTRIBUTION_EVALUABLE"
    INVALIDATED_CONTAMINATION = "INVALIDATED_CONTAMINATION"


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EvaluationCampaignError(f"{name}:INVALID_SHA256")


def _require_nonzero_hash(name: str, value: str) -> None:
    _require_hash(name, value)
    if value == ZERO_HASH:
        raise EvaluationCampaignError(f"{name}:ZERO_HASH_NOT_ALLOWED")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise EvaluationCampaignError(f"{name}:INVALID_ID")


@dataclass(frozen=True)
class CampaignTaskTrialUnitV1:
    task_spec_root: str
    trial_index: int
    unit_kind: str = TASK_TRIAL_UNIT_KIND

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.unit_kind != TASK_TRIAL_UNIT_KIND:
            raise EvaluationCampaignError("TASK_TRIAL_UNIT_KIND_MISMATCH")
        _require_hash("task_spec_root", self.task_spec_root)
        if not isinstance(self.trial_index, int) or isinstance(self.trial_index, bool) or self.trial_index < 0:
            raise EvaluationCampaignError("TRIAL_INDEX_INVALID")

    def to_dict(self) -> dict[str, object]:
        return {
            "unit_kind": self.unit_kind,
            "task_spec_root": self.task_spec_root,
            "trial_index": self.trial_index,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_CAMPAIGN_TASK_TRIAL_UNIT_V1", self.to_dict())


@dataclass(frozen=True)
class BenchmarkTrackSpecV1:
    track_id: str
    benchmark_family: BenchmarkFamily
    benchmark_version: str
    benchmark_source_commitment: str
    split_id: str
    split_privacy: SplitPrivacy
    metric_kind: MetricKind
    task_trial_units: tuple[CampaignTaskTrialUnitV1, ...]
    task_manifest_commitment: str
    scorer_commitment: str
    budget_commitment: str
    human_reference_commitment: str
    contamination_class: ContaminationClass
    repetition_count: int
    statistical_mode: StatisticalMode
    track_kind: str = BENCHMARK_TRACK_KIND

    @classmethod
    def create(
        cls,
        *,
        track_id: str,
        benchmark_family: BenchmarkFamily,
        benchmark_version: str,
        benchmark_source_commitment: str,
        split_id: str,
        split_privacy: SplitPrivacy,
        metric_kind: MetricKind,
        task_trial_units: Iterable[CampaignTaskTrialUnitV1],
        scorer_commitment: str,
        budget_commitment: str,
        human_reference_commitment: str,
        contamination_class: ContaminationClass,
        repetition_count: int,
        statistical_mode: StatisticalMode,
    ) -> "BenchmarkTrackSpecV1":
        units = tuple(task_trial_units)
        manifest_commitment = canonical_hash(
            "AEGIS_UCI8_TASK_TRIAL_MANIFEST_V1",
            {"unit_roots": [unit.root for unit in units]},
        )
        track = cls(
            track_id=track_id,
            benchmark_family=benchmark_family,
            benchmark_version=benchmark_version,
            benchmark_source_commitment=benchmark_source_commitment,
            split_id=split_id,
            split_privacy=split_privacy,
            metric_kind=metric_kind,
            task_trial_units=units,
            task_manifest_commitment=manifest_commitment,
            scorer_commitment=scorer_commitment,
            budget_commitment=budget_commitment,
            human_reference_commitment=human_reference_commitment,
            contamination_class=contamination_class,
            repetition_count=repetition_count,
            statistical_mode=statistical_mode,
        )
        track.validate()
        return track

    def validate(self) -> None:
        if self.track_kind != BENCHMARK_TRACK_KIND:
            raise EvaluationCampaignError("BENCHMARK_TRACK_KIND_MISMATCH")
        _require_id("track_id", self.track_id)
        _require_id("benchmark_version", self.benchmark_version)
        _require_id("split_id", self.split_id)
        if not isinstance(self.benchmark_family, BenchmarkFamily):
            raise EvaluationCampaignError("BENCHMARK_FAMILY_INVALID")
        if not isinstance(self.split_privacy, SplitPrivacy):
            raise EvaluationCampaignError("SPLIT_PRIVACY_INVALID")
        if not isinstance(self.metric_kind, MetricKind):
            raise EvaluationCampaignError("METRIC_KIND_INVALID")
        if not isinstance(self.contamination_class, ContaminationClass):
            raise EvaluationCampaignError("CONTAMINATION_CLASS_INVALID")
        if self.statistical_mode is not StatisticalMode.PAIRED_DESCRIPTIVE_V1:
            raise EvaluationCampaignError("STATISTICAL_MODE_NOT_ADMITTED_V1")
        for name in (
            "benchmark_source_commitment",
            "task_manifest_commitment",
            "scorer_commitment",
            "budget_commitment",
            "human_reference_commitment",
        ):
            _require_hash(name, getattr(self, name))
        if not self.task_trial_units:
            raise EvaluationCampaignError("TASK_TRIAL_MANIFEST_EMPTY")
        unit_roots = [unit.root for unit in self.task_trial_units]
        if len(unit_roots) != len(set(unit_roots)):
            raise EvaluationCampaignError("DUPLICATE_TASK_TRIAL_UNIT")
        expected_manifest = canonical_hash(
            "AEGIS_UCI8_TASK_TRIAL_MANIFEST_V1",
            {"unit_roots": unit_roots},
        )
        if self.task_manifest_commitment != expected_manifest:
            raise EvaluationCampaignError("TASK_MANIFEST_COMMITMENT_MISMATCH")
        if not isinstance(self.repetition_count, int) or isinstance(self.repetition_count, bool) or self.repetition_count < 1:
            raise EvaluationCampaignError("REPETITION_COUNT_INVALID")
        expected_trials = set(range(self.repetition_count))
        trials_by_task: dict[str, set[int]] = {}
        for unit in self.task_trial_units:
            trials_by_task.setdefault(unit.task_spec_root, set()).add(unit.trial_index)
        if any(trial_indices != expected_trials for trial_indices in trials_by_task.values()):
            raise EvaluationCampaignError("REPETITION_MANIFEST_MISMATCH")
        if self.split_privacy is SplitPrivacy.PUBLIC_DEV and self.contamination_class is ContaminationClass.HELD_OUT:
            raise EvaluationCampaignError("PUBLIC_SPLIT_CANNOT_BE_HELD_OUT")

        if self.benchmark_family is BenchmarkFamily.ARC_AGI_2:
            if self.metric_kind is not MetricKind.EXACT_MATCH_ACCURACY:
                raise EvaluationCampaignError("ARC_AGI_2_METRIC_MISMATCH")
            if self.budget_commitment == ZERO_HASH:
                raise EvaluationCampaignError("ARC_AGI_2_BUDGET_REQUIRED")
        elif self.benchmark_family is BenchmarkFamily.GAIA:
            if self.metric_kind is not MetricKind.TOOL_ASSISTED_QA_ACCURACY:
                raise EvaluationCampaignError("GAIA_METRIC_MISMATCH")
            if self.scorer_commitment == ZERO_HASH:
                raise EvaluationCampaignError("GAIA_SCORER_REQUIRED")
        elif self.benchmark_family is BenchmarkFamily.METR_TIME_HORIZON:
            if self.metric_kind is not MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON:
                raise EvaluationCampaignError("METR_TIME_HORIZON_METRIC_MISMATCH")
            if self.human_reference_commitment == ZERO_HASH:
                raise EvaluationCampaignError("METR_HUMAN_REFERENCE_REQUIRED")

    def to_dict(self) -> dict[str, object]:
        return {
            "track_kind": self.track_kind,
            "track_id": self.track_id,
            "benchmark_family": self.benchmark_family.value,
            "benchmark_version": self.benchmark_version,
            "benchmark_source_commitment": self.benchmark_source_commitment,
            "split_id": self.split_id,
            "split_privacy": self.split_privacy.value,
            "metric_kind": self.metric_kind.value,
            "task_trial_units": [unit.to_dict() for unit in self.task_trial_units],
            "task_manifest_commitment": self.task_manifest_commitment,
            "scorer_commitment": self.scorer_commitment,
            "budget_commitment": self.budget_commitment,
            "human_reference_commitment": self.human_reference_commitment,
            "contamination_class": self.contamination_class.value,
            "repetition_count": self.repetition_count,
            "statistical_mode": self.statistical_mode.value,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_BENCHMARK_TRACK_SPEC_V1", self.to_dict())


@dataclass(frozen=True)
class EvaluationCampaignManifestV1:
    campaign_id: str
    uci7_suite_root: str
    evaluated_system_commitment: str
    strongest_constituent_baseline_commitment: str
    tracks: tuple[BenchmarkTrackSpecV1, ...]
    campaign_policy_commitment: str
    campaign_kind: str = CAMPAIGN_MANIFEST_KIND

    @classmethod
    def create(
        cls,
        *,
        campaign_id: str,
        uci7_suite_root: str,
        evaluated_system_commitment: str,
        strongest_constituent_baseline_commitment: str,
        tracks: Iterable[BenchmarkTrackSpecV1],
    ) -> "EvaluationCampaignManifestV1":
        track_tuple = tuple(tracks)
        policy = canonical_hash(
            "AEGIS_UCI8_CAMPAIGN_POLICY_V1",
            {
                "campaign_id": campaign_id,
                "uci7_suite_root": uci7_suite_root,
                "evaluated_system_commitment": evaluated_system_commitment,
                "strongest_constituent_baseline_commitment": strongest_constituent_baseline_commitment,
                "track_roots": [track.root for track in track_tuple],
            },
        )
        campaign = cls(
            campaign_id=campaign_id,
            uci7_suite_root=uci7_suite_root,
            evaluated_system_commitment=evaluated_system_commitment,
            strongest_constituent_baseline_commitment=strongest_constituent_baseline_commitment,
            tracks=track_tuple,
            campaign_policy_commitment=policy,
        )
        campaign.validate()
        return campaign

    def validate(self) -> None:
        if self.campaign_kind != CAMPAIGN_MANIFEST_KIND:
            raise EvaluationCampaignError("CAMPAIGN_MANIFEST_KIND_MISMATCH")
        _require_id("campaign_id", self.campaign_id)
        for name in (
            "uci7_suite_root",
            "evaluated_system_commitment",
            "strongest_constituent_baseline_commitment",
            "campaign_policy_commitment",
        ):
            _require_hash(name, getattr(self, name))
        if self.evaluated_system_commitment == self.strongest_constituent_baseline_commitment:
            raise EvaluationCampaignError("SYSTEM_BASELINE_IDENTITY_COLLISION")
        if not self.tracks:
            raise EvaluationCampaignError("CAMPAIGN_TRACKS_EMPTY")
        roots = [track.root for track in self.tracks]
        ids = [track.track_id for track in self.tracks]
        if len(roots) != len(set(roots)) or len(ids) != len(set(ids)):
            raise EvaluationCampaignError("DUPLICATE_CAMPAIGN_TRACK")
        expected_policy = canonical_hash(
            "AEGIS_UCI8_CAMPAIGN_POLICY_V1",
            {
                "campaign_id": self.campaign_id,
                "uci7_suite_root": self.uci7_suite_root,
                "evaluated_system_commitment": self.evaluated_system_commitment,
                "strongest_constituent_baseline_commitment": self.strongest_constituent_baseline_commitment,
                "track_roots": roots,
            },
        )
        if self.campaign_policy_commitment != expected_policy:
            raise EvaluationCampaignError("CAMPAIGN_POLICY_COMMITMENT_MISMATCH")

    def to_dict(self) -> dict[str, object]:
        return {
            "campaign_kind": self.campaign_kind,
            "campaign_id": self.campaign_id,
            "uci7_suite_root": self.uci7_suite_root,
            "evaluated_system_commitment": self.evaluated_system_commitment,
            "strongest_constituent_baseline_commitment": self.strongest_constituent_baseline_commitment,
            "tracks": [track.to_dict() for track in self.tracks],
            "campaign_policy_commitment": self.campaign_policy_commitment,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_EVALUATION_CAMPAIGN_MANIFEST_V1", self.to_dict())


@dataclass(frozen=True)
class PairedBenchmarkTrialV1:
    campaign_root: str
    track_root: str
    task_trial_unit_root: str
    system_result_root: str
    baseline_result_root: str
    system_runtime_commitment: str
    baseline_runtime_commitment: str
    budget_commitment: str
    scorer_commitment: str
    pair_kind: str = PAIRED_TRIAL_KIND

    @classmethod
    def create(
        cls,
        *,
        campaign: EvaluationCampaignManifestV1,
        track: BenchmarkTrackSpecV1,
        system_result: CapabilityTrialResultV1,
        baseline_result: CapabilityTrialResultV1 | None,
    ) -> "PairedBenchmarkTrialV1":
        campaign.validate()
        track.validate()
        if baseline_result is None:
            raise EvaluationCampaignError("BASELINE_RESULT_REQUIRED")
        system_result.validate()
        baseline_result.validate()

        if system_result.task_spec_root != baseline_result.task_spec_root or system_result.trial_index != baseline_result.trial_index:
            raise EvaluationCampaignError("PAIRED_TASK_TRIAL_MISMATCH")
        unit = CampaignTaskTrialUnitV1(
            task_spec_root=system_result.task_spec_root,
            trial_index=system_result.trial_index,
        )
        if unit.root not in {candidate.root for candidate in track.task_trial_units}:
            raise EvaluationCampaignError("TASK_TRIAL_UNIT_NOT_IN_TRACK")
        if system_result.provider_runtime_commitment != campaign.evaluated_system_commitment:
            raise EvaluationCampaignError("SYSTEM_RUNTIME_COMMITMENT_MISMATCH")
        if baseline_result.provider_runtime_commitment != campaign.strongest_constituent_baseline_commitment:
            raise EvaluationCampaignError("BASELINE_RUNTIME_COMMITMENT_MISMATCH")
        if system_result.budget_commitment != track.budget_commitment or baseline_result.budget_commitment != track.budget_commitment:
            raise EvaluationCampaignError("BUDGET_COMMITMENT_MISMATCH")
        if system_result.checker_commitment != track.scorer_commitment or baseline_result.checker_commitment != track.scorer_commitment:
            raise EvaluationCampaignError("SCORER_COMMITMENT_MISMATCH")
        if track.root not in {candidate.root for candidate in campaign.tracks}:
            raise EvaluationCampaignError("TRACK_NOT_IN_CAMPAIGN")

        pair = cls(
            campaign_root=campaign.root,
            track_root=track.root,
            task_trial_unit_root=unit.root,
            system_result_root=system_result.root,
            baseline_result_root=baseline_result.root,
            system_runtime_commitment=system_result.provider_runtime_commitment,
            baseline_runtime_commitment=baseline_result.provider_runtime_commitment,
            budget_commitment=track.budget_commitment,
            scorer_commitment=track.scorer_commitment,
        )
        pair.validate()
        return pair

    def validate(self) -> None:
        if self.pair_kind != PAIRED_TRIAL_KIND:
            raise EvaluationCampaignError("PAIRED_TRIAL_KIND_MISMATCH")
        for name in (
            "campaign_root",
            "track_root",
            "task_trial_unit_root",
            "system_result_root",
            "baseline_result_root",
            "system_runtime_commitment",
            "baseline_runtime_commitment",
            "budget_commitment",
            "scorer_commitment",
        ):
            _require_hash(name, getattr(self, name))

    def to_dict(self) -> dict[str, object]:
        return {
            "pair_kind": self.pair_kind,
            "campaign_root": self.campaign_root,
            "track_root": self.track_root,
            "task_trial_unit_root": self.task_trial_unit_root,
            "system_result_root": self.system_result_root,
            "baseline_result_root": self.baseline_result_root,
            "system_runtime_commitment": self.system_runtime_commitment,
            "baseline_runtime_commitment": self.baseline_runtime_commitment,
            "budget_commitment": self.budget_commitment,
            "scorer_commitment": self.scorer_commitment,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_PAIRED_BENCHMARK_TRIAL_V1", self.to_dict())


@dataclass(frozen=True)
class CampaignEvidenceBundleV1:
    campaign_root: str
    paired_trial_roots: tuple[str, ...]
    benchmark_adapter_executable_commitment: str
    runner_environment_commitment: str
    execution_receipt_bundle_commitment: str
    evidence_status: CampaignEvidenceStatus
    bundle_kind: str = CAMPAIGN_EVIDENCE_BUNDLE_KIND

    @classmethod
    def create(
        cls,
        *,
        campaign: EvaluationCampaignManifestV1,
        pairs: Iterable[PairedBenchmarkTrialV1],
        benchmark_adapter_executable_commitment: str,
        runner_environment_commitment: str,
        execution_receipt_bundle_commitment: str,
    ) -> "CampaignEvidenceBundleV1":
        campaign.validate()
        pair_tuple = tuple(pairs)
        for name, value in (
            ("benchmark_adapter_executable_commitment", benchmark_adapter_executable_commitment),
            ("runner_environment_commitment", runner_environment_commitment),
            ("execution_receipt_bundle_commitment", execution_receipt_bundle_commitment),
        ):
            _require_nonzero_hash(name, value)

        expected_slots = {
            (track.root, unit.root)
            for track in campaign.tracks
            for unit in track.task_trial_units
        }
        actual_slots: list[tuple[str, str]] = []
        for pair in pair_tuple:
            pair.validate()
            if pair.campaign_root != campaign.root:
                raise EvaluationCampaignError("PAIR_CAMPAIGN_ROOT_MISMATCH")
            if pair.track_root not in {track.root for track in campaign.tracks}:
                raise EvaluationCampaignError("PAIR_TRACK_NOT_IN_CAMPAIGN")
            actual_slots.append((pair.track_root, pair.task_trial_unit_root))
        if len(pair_tuple) != len(expected_slots) or set(actual_slots) != expected_slots:
            raise EvaluationCampaignError("PAIR_CARDINALITY_MISMATCH")
        if len(actual_slots) != len(set(actual_slots)):
            raise EvaluationCampaignError("DUPLICATE_PAIRED_TRIAL")

        contaminations = {track.contamination_class for track in campaign.tracks}
        public_dev = any(track.split_privacy is SplitPrivacy.PUBLIC_DEV for track in campaign.tracks)
        if ContaminationClass.SUSPECTED in contaminations or ContaminationClass.EXPOSED in contaminations:
            status = CampaignEvidenceStatus.INVALIDATED_CONTAMINATION
        elif public_dev or ContaminationClass.PUBLIC in contaminations:
            status = CampaignEvidenceStatus.DEVELOPMENT_EVIDENCE_ONLY
        else:
            status = CampaignEvidenceStatus.COLLECTIVE_CONTRIBUTION_EVALUABLE

        bundle = cls(
            campaign_root=campaign.root,
            paired_trial_roots=tuple(pair.root for pair in pair_tuple),
            benchmark_adapter_executable_commitment=benchmark_adapter_executable_commitment,
            runner_environment_commitment=runner_environment_commitment,
            execution_receipt_bundle_commitment=execution_receipt_bundle_commitment,
            evidence_status=status,
        )
        bundle.validate()
        return bundle

    def validate(self) -> None:
        if self.bundle_kind != CAMPAIGN_EVIDENCE_BUNDLE_KIND:
            raise EvaluationCampaignError("CAMPAIGN_EVIDENCE_BUNDLE_KIND_MISMATCH")
        _require_hash("campaign_root", self.campaign_root)
        if not self.paired_trial_roots:
            raise EvaluationCampaignError("PAIRED_TRIAL_ROOTS_EMPTY")
        for root in self.paired_trial_roots:
            _require_hash("paired_trial_root", root)
        if len(self.paired_trial_roots) != len(set(self.paired_trial_roots)):
            raise EvaluationCampaignError("DUPLICATE_PAIRED_TRIAL_ROOT")
        for name in (
            "benchmark_adapter_executable_commitment",
            "runner_environment_commitment",
            "execution_receipt_bundle_commitment",
        ):
            _require_nonzero_hash(name, getattr(self, name))
        if not isinstance(self.evidence_status, CampaignEvidenceStatus):
            raise EvaluationCampaignError("CAMPAIGN_EVIDENCE_STATUS_INVALID")

    def to_dict(self) -> dict[str, object]:
        return {
            "bundle_kind": self.bundle_kind,
            "campaign_root": self.campaign_root,
            "paired_trial_roots": list(self.paired_trial_roots),
            "benchmark_adapter_executable_commitment": self.benchmark_adapter_executable_commitment,
            "runner_environment_commitment": self.runner_environment_commitment,
            "execution_receipt_bundle_commitment": self.execution_receipt_bundle_commitment,
            "evidence_status": self.evidence_status.value,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_CAMPAIGN_EVIDENCE_BUNDLE_V1", self.to_dict())