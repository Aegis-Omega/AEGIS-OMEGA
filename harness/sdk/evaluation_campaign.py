"""UCI-8 preregistered evaluation-campaign reference contract.

This module binds evidence from real benchmark campaigns to an immutable,
content-addressed manifest. It does not run benchmarks, does not grant authority,
and does not define an ``AGI_PROVEN`` state.

UCI-8 v1 intentionally supports descriptive paired evidence only. Statistical
significance, confidence intervals, and causal attribution are outside this
version's admitted claim surface.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import threading
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from harness.sdk.agi_evidence import CapabilityTrialResultV1, ContaminationClass, _is_checker_issued_result
from harness.sdk.sovereign_execution import ZERO_HASH, canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")
TASK_TRIAL_UNIT_KIND = "CAMPAIGN_TASK_TRIAL_UNIT_V1"
BENCHMARK_TRACK_KIND = "BENCHMARK_TRACK_SPEC_V1"
CAMPAIGN_MANIFEST_KIND = "EVALUATION_CAMPAIGN_MANIFEST_V1"
CHECKER_RESULT_ATTESTATION_KIND = "CHECKER_RESULT_ATTESTATION_V1"
PAIR_VERIFICATION_ATTESTATION_KIND = "PAIR_VERIFICATION_ATTESTATION_V1"
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


class BaselineSelectionMode(str, Enum):
    FIXED_A_PRIORI_CAMPAIGN = "FIXED_A_PRIORI_CAMPAIGN"
    SEPARATE_SELECTION_SPLIT_PER_TASK = "SEPARATE_SELECTION_SPLIT_PER_TASK"
    SAME_COMPARISON_DATA_PER_TASK = "SAME_COMPARISON_DATA_PER_TASK"


class PublishedComparability(str, Enum):
    NOT_COMPARABLE_TO_PUBLISHED = "NOT_COMPARABLE_TO_PUBLISHED"
    PUBLISHED_METHODOLOGY_MATCHED = "PUBLISHED_METHODOLOGY_MATCHED"


class DeltaResolutionStatus(str, Enum):
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    BELOW_MEASUREMENT_RESOLUTION = "BELOW_MEASUREMENT_RESOLUTION"
    AT_OR_ABOVE_MEASUREMENT_RESOLUTION = "AT_OR_ABOVE_MEASUREMENT_RESOLUTION"


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
        return {"unit_kind": self.unit_kind, "task_spec_root": self.task_spec_root, "trial_index": self.trial_index}

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
    published_comparability: PublishedComparability = PublishedComparability.NOT_COMPARABLE_TO_PUBLISHED
    published_methodology_commitment: str = ZERO_HASH
    measurement_resolution_bps: int | None = None
    measurement_resolution_basis_commitment: str = ZERO_HASH
    track_kind: str = BENCHMARK_TRACK_KIND

    @classmethod
    def create(cls, *, track_id: str, benchmark_family: BenchmarkFamily, benchmark_version: str,
               benchmark_source_commitment: str, split_id: str, split_privacy: SplitPrivacy,
               metric_kind: MetricKind, task_trial_units: Iterable[CampaignTaskTrialUnitV1],
               scorer_commitment: str, budget_commitment: str, human_reference_commitment: str,
               contamination_class: ContaminationClass, repetition_count: int,
               statistical_mode: StatisticalMode,
               published_comparability: PublishedComparability = PublishedComparability.NOT_COMPARABLE_TO_PUBLISHED,
               published_methodology_commitment: str = ZERO_HASH,
               measurement_resolution_bps: int | None = None,
               measurement_resolution_basis_commitment: str = ZERO_HASH) -> "BenchmarkTrackSpecV1":
        units = tuple(task_trial_units)
        manifest_commitment = canonical_hash("AEGIS_UCI8_TASK_TRIAL_MANIFEST_V1", {"unit_roots": [u.root for u in units]})
        track = cls(track_id=track_id, benchmark_family=benchmark_family, benchmark_version=benchmark_version,
                    benchmark_source_commitment=benchmark_source_commitment, split_id=split_id,
                    split_privacy=split_privacy, metric_kind=metric_kind, task_trial_units=units,
                    task_manifest_commitment=manifest_commitment, scorer_commitment=scorer_commitment,
                    budget_commitment=budget_commitment, human_reference_commitment=human_reference_commitment,
                    contamination_class=contamination_class, repetition_count=repetition_count,
                    statistical_mode=statistical_mode, published_comparability=published_comparability,
                    published_methodology_commitment=published_methodology_commitment,
                    measurement_resolution_bps=measurement_resolution_bps,
                    measurement_resolution_basis_commitment=measurement_resolution_basis_commitment)
        track.validate()
        return track

    def validate(self) -> None:
        if self.track_kind != BENCHMARK_TRACK_KIND:
            raise EvaluationCampaignError("BENCHMARK_TRACK_KIND_MISMATCH")
        _require_id("track_id", self.track_id); _require_id("benchmark_version", self.benchmark_version); _require_id("split_id", self.split_id)
        if not isinstance(self.benchmark_family, BenchmarkFamily): raise EvaluationCampaignError("BENCHMARK_FAMILY_INVALID")
        if not isinstance(self.split_privacy, SplitPrivacy): raise EvaluationCampaignError("SPLIT_PRIVACY_INVALID")
        if not isinstance(self.metric_kind, MetricKind): raise EvaluationCampaignError("METRIC_KIND_INVALID")
        if not isinstance(self.contamination_class, ContaminationClass): raise EvaluationCampaignError("CONTAMINATION_CLASS_INVALID")
        if self.statistical_mode is not StatisticalMode.PAIRED_DESCRIPTIVE_V1: raise EvaluationCampaignError("STATISTICAL_MODE_NOT_ADMITTED_V1")
        if not isinstance(self.published_comparability, PublishedComparability): raise EvaluationCampaignError("PUBLISHED_COMPARABILITY_INVALID")
        for name in ("benchmark_source_commitment", "task_manifest_commitment", "scorer_commitment", "budget_commitment",
                     "human_reference_commitment", "published_methodology_commitment", "measurement_resolution_basis_commitment"):
            _require_hash(name, getattr(self, name))
        if self.published_comparability is PublishedComparability.PUBLISHED_METHODOLOGY_MATCHED and self.published_methodology_commitment == ZERO_HASH:
            raise EvaluationCampaignError("PUBLISHED_METHODOLOGY_COMMITMENT_REQUIRED")
        if self.measurement_resolution_bps is None:
            if self.measurement_resolution_basis_commitment != ZERO_HASH: raise EvaluationCampaignError("MEASUREMENT_RESOLUTION_VALUE_REQUIRED")
        else:
            if not isinstance(self.measurement_resolution_bps, int) or isinstance(self.measurement_resolution_bps, bool) or not 1 <= self.measurement_resolution_bps <= 10_000:
                raise EvaluationCampaignError("MEASUREMENT_RESOLUTION_BPS_INVALID")
            if self.measurement_resolution_basis_commitment == ZERO_HASH: raise EvaluationCampaignError("MEASUREMENT_RESOLUTION_BASIS_REQUIRED")
            if self.metric_kind is MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON: raise EvaluationCampaignError("BPS_RESOLUTION_NOT_APPLICABLE_TO_HORIZON_METRIC")
            if self.metric_kind not in (MetricKind.EXACT_MATCH_ACCURACY, MetricKind.TOOL_ASSISTED_QA_ACCURACY): raise EvaluationCampaignError("BPS_RESOLUTION_NOT_APPLICABLE_TO_METRIC")
        if not self.task_trial_units: raise EvaluationCampaignError("TASK_TRIAL_MANIFEST_EMPTY")
        unit_roots = [u.root for u in self.task_trial_units]
        if len(unit_roots) != len(set(unit_roots)): raise EvaluationCampaignError("DUPLICATE_TASK_TRIAL_UNIT")
        expected_manifest = canonical_hash("AEGIS_UCI8_TASK_TRIAL_MANIFEST_V1", {"unit_roots": unit_roots})
        if self.task_manifest_commitment != expected_manifest: raise EvaluationCampaignError("TASK_MANIFEST_COMMITMENT_MISMATCH")
        if not isinstance(self.repetition_count, int) or isinstance(self.repetition_count, bool) or self.repetition_count < 1: raise EvaluationCampaignError("REPETITION_COUNT_INVALID")
        expected_trials = set(range(self.repetition_count)); trials_by_task: dict[str, set[int]] = {}
        for unit in self.task_trial_units: trials_by_task.setdefault(unit.task_spec_root, set()).add(unit.trial_index)
        if any(indices != expected_trials for indices in trials_by_task.values()): raise EvaluationCampaignError("REPETITION_MANIFEST_MISMATCH")
        if self.split_privacy is SplitPrivacy.PUBLIC_DEV and self.contamination_class is ContaminationClass.HELD_OUT: raise EvaluationCampaignError("PUBLIC_SPLIT_CANNOT_BE_HELD_OUT")
        if self.benchmark_family is BenchmarkFamily.ARC_AGI_2:
            if self.metric_kind is not MetricKind.EXACT_MATCH_ACCURACY: raise EvaluationCampaignError("ARC_AGI_2_METRIC_MISMATCH")
            if self.budget_commitment == ZERO_HASH: raise EvaluationCampaignError("ARC_AGI_2_BUDGET_REQUIRED")
        elif self.benchmark_family is BenchmarkFamily.GAIA:
            if self.metric_kind is not MetricKind.TOOL_ASSISTED_QA_ACCURACY: raise EvaluationCampaignError("GAIA_METRIC_MISMATCH")
            if self.scorer_commitment == ZERO_HASH: raise EvaluationCampaignError("GAIA_SCORER_REQUIRED")
        elif self.benchmark_family is BenchmarkFamily.METR_TIME_HORIZON:
            if self.metric_kind is not MetricKind.HUMAN_EQUIVALENT_TASK_HORIZON: raise EvaluationCampaignError("METR_TIME_HORIZON_METRIC_MISMATCH")
            if self.human_reference_commitment == ZERO_HASH: raise EvaluationCampaignError("METR_HUMAN_REFERENCE_REQUIRED")

    def classify_delta_resolution(self, delta_bps: int) -> DeltaResolutionStatus:
        self.validate()
        if not isinstance(delta_bps, int) or isinstance(delta_bps, bool): raise EvaluationCampaignError("DELTA_BPS_INVALID")
        if self.measurement_resolution_bps is None: return DeltaResolutionStatus.NOT_ESTABLISHED
        if abs(delta_bps) < self.measurement_resolution_bps: return DeltaResolutionStatus.BELOW_MEASUREMENT_RESOLUTION
        return DeltaResolutionStatus.AT_OR_ABOVE_MEASUREMENT_RESOLUTION

    def to_dict(self) -> dict[str, object]:
        return {"track_kind": self.track_kind, "track_id": self.track_id, "benchmark_family": self.benchmark_family.value,
                "benchmark_version": self.benchmark_version, "benchmark_source_commitment": self.benchmark_source_commitment,
                "split_id": self.split_id, "split_privacy": self.split_privacy.value, "metric_kind": self.metric_kind.value,
                "task_trial_units": [u.to_dict() for u in self.task_trial_units], "task_manifest_commitment": self.task_manifest_commitment,
                "scorer_commitment": self.scorer_commitment, "budget_commitment": self.budget_commitment,
                "human_reference_commitment": self.human_reference_commitment, "contamination_class": self.contamination_class.value,
                "repetition_count": self.repetition_count, "statistical_mode": self.statistical_mode.value,
                "published_comparability": self.published_comparability.value,
                "published_methodology_commitment": self.published_methodology_commitment,
                "measurement_resolution_bps": self.measurement_resolution_bps,
                "measurement_resolution_basis_commitment": self.measurement_resolution_basis_commitment}

    @property
    def root(self) -> str:
        self.validate(); return canonical_hash("AEGIS_UCI8_BENCHMARK_TRACK_SPEC_V1", self.to_dict())


@dataclass(frozen=True)
class EvaluationCampaignManifestV1:
    campaign_id: str
    uci7_suite_root: str
    evaluated_system_commitment: str
    strongest_constituent_baseline_commitment: str
    tracks: tuple[BenchmarkTrackSpecV1, ...]
    baseline_selection_mode: BaselineSelectionMode
    campaign_policy_commitment: str
    campaign_kind: str = CAMPAIGN_MANIFEST_KIND

    @classmethod
    def create(cls, *, campaign_id: str, uci7_suite_root: str, evaluated_system_commitment: str,
               strongest_constituent_baseline_commitment: str, tracks: Iterable[BenchmarkTrackSpecV1],
               baseline_selection_mode: BaselineSelectionMode = BaselineSelectionMode.FIXED_A_PRIORI_CAMPAIGN) -> "EvaluationCampaignManifestV1":
        track_tuple = tuple(tracks)
        policy = canonical_hash("AEGIS_UCI8_CAMPAIGN_POLICY_V1", {"campaign_id": campaign_id, "uci7_suite_root": uci7_suite_root,
            "evaluated_system_commitment": evaluated_system_commitment, "strongest_constituent_baseline_commitment": strongest_constituent_baseline_commitment,
            "baseline_selection_mode": baseline_selection_mode.value if isinstance(baseline_selection_mode, BaselineSelectionMode) else baseline_selection_mode,
            "track_roots": [t.root for t in track_tuple]})
        campaign = cls(campaign_id=campaign_id, uci7_suite_root=uci7_suite_root, evaluated_system_commitment=evaluated_system_commitment,
                       strongest_constituent_baseline_commitment=strongest_constituent_baseline_commitment, tracks=track_tuple,
                       baseline_selection_mode=baseline_selection_mode, campaign_policy_commitment=policy)
        campaign.validate(); return campaign

    def validate(self) -> None:
        if self.campaign_kind != CAMPAIGN_MANIFEST_KIND: raise EvaluationCampaignError("CAMPAIGN_MANIFEST_KIND_MISMATCH")
        _require_id("campaign_id", self.campaign_id)
        for name in ("uci7_suite_root", "evaluated_system_commitment", "strongest_constituent_baseline_commitment", "campaign_policy_commitment"):
            _require_hash(name, getattr(self, name))
        if not isinstance(self.baseline_selection_mode, BaselineSelectionMode): raise EvaluationCampaignError("BASELINE_SELECTION_MODE_INVALID")
        if self.baseline_selection_mode is BaselineSelectionMode.SAME_COMPARISON_DATA_PER_TASK: raise EvaluationCampaignError("BASELINE_SELECTION_USES_COMPARISON_DATA")
        if self.baseline_selection_mode is BaselineSelectionMode.SEPARATE_SELECTION_SPLIT_PER_TASK: raise EvaluationCampaignError("PER_TASK_BASELINE_SELECTION_NOT_IMPLEMENTED_V1")
        if self.baseline_selection_mode is not BaselineSelectionMode.FIXED_A_PRIORI_CAMPAIGN: raise EvaluationCampaignError("BASELINE_SELECTION_MODE_NOT_ADMITTED_V1")
        if self.evaluated_system_commitment == self.strongest_constituent_baseline_commitment: raise EvaluationCampaignError("SYSTEM_BASELINE_IDENTITY_COLLISION")
        if not self.tracks: raise EvaluationCampaignError("CAMPAIGN_TRACKS_EMPTY")
        roots = [t.root for t in self.tracks]; ids = [t.track_id for t in self.tracks]
        if len(roots) != len(set(roots)) or len(ids) != len(set(ids)): raise EvaluationCampaignError("DUPLICATE_CAMPAIGN_TRACK")
        expected = canonical_hash("AEGIS_UCI8_CAMPAIGN_POLICY_V1", {"campaign_id": self.campaign_id, "uci7_suite_root": self.uci7_suite_root,
            "evaluated_system_commitment": self.evaluated_system_commitment, "strongest_constituent_baseline_commitment": self.strongest_constituent_baseline_commitment,
            "baseline_selection_mode": self.baseline_selection_mode.value, "track_roots": roots})
        if self.campaign_policy_commitment != expected: raise EvaluationCampaignError("CAMPAIGN_POLICY_COMMITMENT_MISMATCH")

    def to_dict(self) -> dict[str, object]:
        return {"campaign_kind": self.campaign_kind, "campaign_id": self.campaign_id, "uci7_suite_root": self.uci7_suite_root,
                "evaluated_system_commitment": self.evaluated_system_commitment,
                "strongest_constituent_baseline_commitment": self.strongest_constituent_baseline_commitment,
                "baseline_selection_mode": self.baseline_selection_mode.value, "tracks": [t.to_dict() for t in self.tracks],
                "campaign_policy_commitment": self.campaign_policy_commitment}

    @property
    def root(self) -> str:
        self.validate(); return canonical_hash("AEGIS_UCI8_EVALUATION_CAMPAIGN_MANIFEST_V1", self.to_dict())


@dataclass(frozen=True)
class CheckerResultAttestationV1:
    run_id: str; task_spec_root: str; trial_index: int; result_root: str; checker_commitment: str; key_id: str; mac_hex: str
    attestation_kind: str = CHECKER_RESULT_ATTESTATION_KIND

    def validate(self) -> None:
        if self.attestation_kind != CHECKER_RESULT_ATTESTATION_KIND: raise EvaluationCampaignError("CHECKER_ATTESTATION_KIND_MISMATCH")
        _require_id("run_id", self.run_id); _require_id("key_id", self.key_id)
        for name in ("task_spec_root", "result_root", "checker_commitment"): _require_hash(name, getattr(self, name))
        if not isinstance(self.trial_index, int) or isinstance(self.trial_index, bool) or self.trial_index < 0: raise EvaluationCampaignError("ATTESTATION_TRIAL_INDEX_INVALID")
        _require_hash("mac_hex", self.mac_hex)

    def unsigned_payload(self) -> dict[str, object]:
        return {"attestation_kind": self.attestation_kind, "run_id": self.run_id, "task_spec_root": self.task_spec_root,
                "trial_index": self.trial_index, "result_root": self.result_root, "checker_commitment": self.checker_commitment, "key_id": self.key_id}
    def to_dict(self) -> dict[str, object]: return {**self.unsigned_payload(), "mac_hex": self.mac_hex}
    @property
    def root(self) -> str: self.validate(); return canonical_hash("AEGIS_UCI8_CHECKER_RESULT_ATTESTATION_V1", self.to_dict())


@dataclass(frozen=True)
class PairVerificationAttestationV1:
    run_id: str; pair_root: str; campaign_root: str; track_root: str; task_trial_unit_root: str
    system_checker_attestation_root: str; baseline_checker_attestation_root: str; key_id: str; mac_hex: str
    attestation_kind: str = PAIR_VERIFICATION_ATTESTATION_KIND

    def validate(self) -> None:
        if self.attestation_kind != PAIR_VERIFICATION_ATTESTATION_KIND: raise EvaluationCampaignError("PAIR_VERIFICATION_ATTESTATION_KIND_MISMATCH")
        _require_id("run_id", self.run_id); _require_id("key_id", self.key_id)
        for name in ("pair_root", "campaign_root", "track_root", "task_trial_unit_root", "system_checker_attestation_root", "baseline_checker_attestation_root", "mac_hex"):
            _require_nonzero_hash(name, getattr(self, name))
    def unsigned_payload(self) -> dict[str, object]:
        return {"attestation_kind": self.attestation_kind, "run_id": self.run_id, "pair_root": self.pair_root,
                "campaign_root": self.campaign_root, "track_root": self.track_root, "task_trial_unit_root": self.task_trial_unit_root,
                "system_checker_attestation_root": self.system_checker_attestation_root,
                "baseline_checker_attestation_root": self.baseline_checker_attestation_root, "key_id": self.key_id}
    def to_dict(self) -> dict[str, object]: return {**self.unsigned_payload(), "mac_hex": self.mac_hex}
    @property
    def root(self) -> str: self.validate(); return canonical_hash("AEGIS_UCI8_PAIR_VERIFICATION_ATTESTATION_V1", self.to_dict())


class PortableCheckerHMACV1:
    """Portable symmetric result/pair attestations; not public-key signatures."""
    def __init__(self, *, key_id: str, secret_key: bytes) -> None:
        _require_id("key_id", key_id)
        if not isinstance(secret_key, bytes) or len(secret_key) < 32: raise EvaluationCampaignError("HMAC_SECRET_KEY_TOO_SHORT")
        self._key_id, self._secret_key = key_id, secret_key
    def _mac_for_payload(self, payload: dict[str, object]) -> str:
        digest = canonical_hash("AEGIS_UCI8_CHECKER_RESULT_ATTESTATION_PAYLOAD_V1", payload)
        return hmac.new(self._secret_key, bytes.fromhex(digest), hashlib.sha256).hexdigest()
    def _pair_mac_for_payload(self, payload: dict[str, object]) -> str:
        digest = canonical_hash("AEGIS_UCI8_PAIR_VERIFICATION_ATTESTATION_PAYLOAD_V1", payload)
        return hmac.new(self._secret_key, bytes.fromhex(digest), hashlib.sha256).hexdigest()
    def issue(self, *, run_id: str, result: CapabilityTrialResultV1) -> CheckerResultAttestationV1:
        _require_id("run_id", run_id); result.validate()
        if not _is_checker_issued_result(result): raise EvaluationCampaignError("ATTESTATION_ISSUER_REQUIRES_CHECKER_ISSUED_RESULT")
        unsigned = {"attestation_kind": CHECKER_RESULT_ATTESTATION_KIND, "run_id": run_id, "task_spec_root": result.task_spec_root,
                    "trial_index": result.trial_index, "result_root": result.root, "checker_commitment": result.checker_commitment, "key_id": self._key_id}
        a = CheckerResultAttestationV1(run_id=run_id, task_spec_root=result.task_spec_root, trial_index=result.trial_index,
            result_root=result.root, checker_commitment=result.checker_commitment, key_id=self._key_id, mac_hex=self._mac_for_payload(unsigned))
        a.validate(); return a
    def verify(self, *, expected_run_id: str, result: CapabilityTrialResultV1, attestation: CheckerResultAttestationV1) -> None:
        _require_id("expected_run_id", expected_run_id); result.validate(); attestation.validate()
        if attestation.run_id != expected_run_id: raise EvaluationCampaignError("ATTESTATION_RUN_ID_MISMATCH")
        if attestation.task_spec_root != result.task_spec_root: raise EvaluationCampaignError("ATTESTATION_TASK_SPEC_ROOT_MISMATCH")
        if attestation.trial_index != result.trial_index: raise EvaluationCampaignError("ATTESTATION_TRIAL_INDEX_MISMATCH")
        if attestation.checker_commitment != result.checker_commitment: raise EvaluationCampaignError("ATTESTATION_CHECKER_COMMITMENT_MISMATCH")
        if attestation.result_root != result.root: raise EvaluationCampaignError("ATTESTATION_RESULT_ROOT_MISMATCH")
        if attestation.key_id != self._key_id: raise EvaluationCampaignError("ATTESTATION_KEY_ID_MISMATCH")
        if not hmac.compare_digest(self._mac_for_payload(attestation.unsigned_payload()), attestation.mac_hex): raise EvaluationCampaignError("ATTESTATION_MAC_INVALID")
    def issue_pair_verification(self, *, run_id: str, pair: PairedBenchmarkTrialV1, system_result: CapabilityTrialResultV1,
                                baseline_result: CapabilityTrialResultV1, system_attestation: CheckerResultAttestationV1,
                                baseline_attestation: CheckerResultAttestationV1) -> PairVerificationAttestationV1:
        _require_id("run_id", run_id); pair.validate()
        if not _is_paired_trial_issued(pair): raise EvaluationCampaignError("PAIR_VERIFICATION_ISSUER_REQUIRES_ISSUED_PAIR")
        self.verify(expected_run_id=run_id, result=system_result, attestation=system_attestation)
        self.verify(expected_run_id=run_id, result=baseline_result, attestation=baseline_attestation)
        if pair.checker_run_id != run_id: raise EvaluationCampaignError("PAIR_VERIFICATION_RUN_ID_MISMATCH")
        if pair.system_result_root != system_result.root: raise EvaluationCampaignError("PAIR_VERIFICATION_SYSTEM_RESULT_ROOT_MISMATCH")
        if pair.baseline_result_root != baseline_result.root: raise EvaluationCampaignError("PAIR_VERIFICATION_BASELINE_RESULT_ROOT_MISMATCH")
        if pair.system_checker_attestation_root != system_attestation.root: raise EvaluationCampaignError("PAIR_VERIFICATION_SYSTEM_ATTESTATION_ROOT_MISMATCH")
        if pair.baseline_checker_attestation_root != baseline_attestation.root: raise EvaluationCampaignError("PAIR_VERIFICATION_BASELINE_ATTESTATION_ROOT_MISMATCH")
        if pair.system_runtime_commitment != system_result.provider_runtime_commitment: raise EvaluationCampaignError("PAIR_VERIFICATION_SYSTEM_RUNTIME_MISMATCH")
        if pair.baseline_runtime_commitment != baseline_result.provider_runtime_commitment: raise EvaluationCampaignError("PAIR_VERIFICATION_BASELINE_RUNTIME_MISMATCH")
        unsigned = {"attestation_kind": PAIR_VERIFICATION_ATTESTATION_KIND, "run_id": run_id, "pair_root": pair.root,
            "campaign_root": pair.campaign_root, "track_root": pair.track_root, "task_trial_unit_root": pair.task_trial_unit_root,
            "system_checker_attestation_root": pair.system_checker_attestation_root,
            "baseline_checker_attestation_root": pair.baseline_checker_attestation_root, "key_id": self._key_id}
        a = PairVerificationAttestationV1(run_id=run_id, pair_root=pair.root, campaign_root=pair.campaign_root,
            track_root=pair.track_root, task_trial_unit_root=pair.task_trial_unit_root,
            system_checker_attestation_root=pair.system_checker_attestation_root,
            baseline_checker_attestation_root=pair.baseline_checker_attestation_root,
            key_id=self._key_id, mac_hex=self._pair_mac_for_payload(unsigned))
        a.validate(); return a
    def verify_pair_verification(self, *, pair: PairedBenchmarkTrialV1, attestation: PairVerificationAttestationV1) -> None:
        pair.validate(); attestation.validate()
        if attestation.pair_root != pair.root: raise EvaluationCampaignError("PAIR_VERIFICATION_PAIR_ROOT_MISMATCH")
        if attestation.run_id != pair.checker_run_id: raise EvaluationCampaignError("PAIR_VERIFICATION_RUN_ID_MISMATCH")
        if attestation.campaign_root != pair.campaign_root: raise EvaluationCampaignError("PAIR_VERIFICATION_CAMPAIGN_ROOT_MISMATCH")
        if attestation.track_root != pair.track_root: raise EvaluationCampaignError("PAIR_VERIFICATION_TRACK_ROOT_MISMATCH")
        if attestation.task_trial_unit_root != pair.task_trial_unit_root: raise EvaluationCampaignError("PAIR_VERIFICATION_TASK_TRIAL_UNIT_ROOT_MISMATCH")
        if attestation.system_checker_attestation_root != pair.system_checker_attestation_root: raise EvaluationCampaignError("PAIR_VERIFICATION_SYSTEM_ATTESTATION_ROOT_MISMATCH")
        if attestation.baseline_checker_attestation_root != pair.baseline_checker_attestation_root: raise EvaluationCampaignError("PAIR_VERIFICATION_BASELINE_ATTESTATION_ROOT_MISMATCH")
        if attestation.key_id != self._key_id: raise EvaluationCampaignError("PAIR_VERIFICATION_KEY_ID_MISMATCH")
        if not hmac.compare_digest(self._pair_mac_for_payload(attestation.unsigned_payload()), attestation.mac_hex): raise EvaluationCampaignError("PAIR_VERIFICATION_MAC_INVALID")


@dataclass(frozen=True)
class PairedBenchmarkTrialV1:
    campaign_root: str; track_root: str; task_trial_unit_root: str; system_result_root: str; baseline_result_root: str
    system_runtime_commitment: str; baseline_runtime_commitment: str; budget_commitment: str; scorer_commitment: str
    checker_run_id: str | None = None
    system_checker_attestation_root: str = ZERO_HASH
    baseline_checker_attestation_root: str = ZERO_HASH
    pair_kind: str = PAIRED_TRIAL_KIND

    @classmethod
    def create(cls, *, campaign: EvaluationCampaignManifestV1, track: BenchmarkTrackSpecV1, system_result: CapabilityTrialResultV1,
               baseline_result: CapabilityTrialResultV1 | None, expected_run_id: str | None = None,
               system_attestation: CheckerResultAttestationV1 | None = None, baseline_attestation: CheckerResultAttestationV1 | None = None,
               attestation_verifier: PortableCheckerHMACV1 | None = None) -> "PairedBenchmarkTrialV1":
        campaign.validate(); track.validate()
        if baseline_result is None: raise EvaluationCampaignError("BASELINE_RESULT_REQUIRED")
        system_result.validate(); baseline_result.validate()
        if system_result.task_spec_root != baseline_result.task_spec_root or system_result.trial_index != baseline_result.trial_index: raise EvaluationCampaignError("PAIRED_TASK_TRIAL_MISMATCH")
        unit = CampaignTaskTrialUnitV1(task_spec_root=system_result.task_spec_root, trial_index=system_result.trial_index)
        if unit.root not in {u.root for u in track.task_trial_units}: raise EvaluationCampaignError("TASK_TRIAL_UNIT_NOT_IN_TRACK")
        if system_result.provider_runtime_commitment != campaign.evaluated_system_commitment: raise EvaluationCampaignError("SYSTEM_RUNTIME_COMMITMENT_MISMATCH")
        if baseline_result.provider_runtime_commitment != campaign.strongest_constituent_baseline_commitment: raise EvaluationCampaignError("BASELINE_RUNTIME_COMMITMENT_MISMATCH")
        if system_result.budget_commitment != track.budget_commitment or baseline_result.budget_commitment != track.budget_commitment: raise EvaluationCampaignError("BUDGET_COMMITMENT_MISMATCH")
        if system_result.checker_commitment != track.scorer_commitment or baseline_result.checker_commitment != track.scorer_commitment: raise EvaluationCampaignError("SCORER_COMMITMENT_MISMATCH")
        if track.root not in {t.root for t in campaign.tracks}: raise EvaluationCampaignError("TRACK_NOT_IN_CAMPAIGN")
        args = (expected_run_id, system_attestation, baseline_attestation, attestation_verifier); requested = any(v is not None for v in args)
        run_id: str | None = None; sys_att_root = ZERO_HASH; base_att_root = ZERO_HASH
        if requested:
            if any(v is None for v in args): raise EvaluationCampaignError("PORTABLE_ATTESTATION_ARGUMENTS_INCOMPLETE")
            assert expected_run_id is not None and system_attestation is not None and baseline_attestation is not None and attestation_verifier is not None
            attestation_verifier.verify(expected_run_id=expected_run_id, result=system_result, attestation=system_attestation)
            attestation_verifier.verify(expected_run_id=expected_run_id, result=baseline_result, attestation=baseline_attestation)
            run_id, sys_att_root, base_att_root = expected_run_id, system_attestation.root, baseline_attestation.root
        elif not _is_checker_issued_result(system_result) or not _is_checker_issued_result(baseline_result):
            raise EvaluationCampaignError("CHECKER_ISSUANCE_OR_PORTABLE_ATTESTATION_REQUIRED")
        pair = cls(campaign_root=campaign.root, track_root=track.root, task_trial_unit_root=unit.root,
                   system_result_root=system_result.root, baseline_result_root=baseline_result.root,
                   system_runtime_commitment=system_result.provider_runtime_commitment,
                   baseline_runtime_commitment=baseline_result.provider_runtime_commitment,
                   budget_commitment=track.budget_commitment, scorer_commitment=track.scorer_commitment,
                   checker_run_id=run_id, system_checker_attestation_root=sys_att_root, baseline_checker_attestation_root=base_att_root)
        pair.validate(); return _register_paired_trial(pair)

    def validate(self) -> None:
        if self.pair_kind != PAIRED_TRIAL_KIND: raise EvaluationCampaignError("PAIRED_TRIAL_KIND_MISMATCH")
        for name in ("campaign_root", "track_root", "task_trial_unit_root", "system_result_root", "baseline_result_root",
                     "system_runtime_commitment", "baseline_runtime_commitment", "budget_commitment", "scorer_commitment"):
            _require_hash(name, getattr(self, name))
        if self.checker_run_id is None:
            if self.system_checker_attestation_root != ZERO_HASH or self.baseline_checker_attestation_root != ZERO_HASH: raise EvaluationCampaignError("ATTESTATION_ROOT_WITHOUT_RUN_ID")
        else:
            _require_id("checker_run_id", self.checker_run_id); _require_nonzero_hash("system_checker_attestation_root", self.system_checker_attestation_root); _require_nonzero_hash("baseline_checker_attestation_root", self.baseline_checker_attestation_root)
    @property
    def portable_checker_attested(self) -> bool: return self.checker_run_id is not None
    def to_dict(self) -> dict[str, object]:
        return {"pair_kind": self.pair_kind, "campaign_root": self.campaign_root, "track_root": self.track_root,
                "task_trial_unit_root": self.task_trial_unit_root, "system_result_root": self.system_result_root,
                "baseline_result_root": self.baseline_result_root, "system_runtime_commitment": self.system_runtime_commitment,
                "baseline_runtime_commitment": self.baseline_runtime_commitment, "budget_commitment": self.budget_commitment,
                "scorer_commitment": self.scorer_commitment, "checker_run_id": self.checker_run_id,
                "system_checker_attestation_root": self.system_checker_attestation_root,
                "baseline_checker_attestation_root": self.baseline_checker_attestation_root}
    @property
    def root(self) -> str: self.validate(); return canonical_hash("AEGIS_UCI8_PAIRED_BENCHMARK_TRIAL_V1", self.to_dict())


_ISSUED_PAIRED_TRIALS_LOCK = threading.RLock()
_ISSUED_PAIRED_TRIALS: dict[int, weakref.ReferenceType[PairedBenchmarkTrialV1]] = {}

def _register_paired_trial(pair: PairedBenchmarkTrialV1) -> PairedBenchmarkTrialV1:
    key = id(pair)
    def cleanup(ref: weakref.ReferenceType[PairedBenchmarkTrialV1], *, object_id: int = key) -> None:
        with _ISSUED_PAIRED_TRIALS_LOCK:
            if _ISSUED_PAIRED_TRIALS.get(object_id) is ref: _ISSUED_PAIRED_TRIALS.pop(object_id, None)
    ref = weakref.ref(pair, cleanup)
    with _ISSUED_PAIRED_TRIALS_LOCK: _ISSUED_PAIRED_TRIALS[key] = ref
    return pair

def _is_paired_trial_issued(pair: PairedBenchmarkTrialV1) -> bool:
    with _ISSUED_PAIRED_TRIALS_LOCK:
        ref = _ISSUED_PAIRED_TRIALS.get(id(pair)); return ref is not None and ref() is pair


@dataclass(frozen=True)
class CampaignEvidenceBundleV1:
    campaign_root: str
    paired_trial_roots: tuple[str, ...]
    pair_verification_roots: tuple[str, ...]
    benchmark_adapter_executable_commitment: str
    runner_environment_commitment: str
    execution_receipt_bundle_commitment: str
    evidence_status: CampaignEvidenceStatus
    bundle_kind: str = CAMPAIGN_EVIDENCE_BUNDLE_KIND

    @classmethod
    def create(cls, *, campaign: EvaluationCampaignManifestV1, pairs: Iterable[PairedBenchmarkTrialV1],
               benchmark_adapter_executable_commitment: str, runner_environment_commitment: str,
               execution_receipt_bundle_commitment: str,
               pair_verifications: Iterable[PairVerificationAttestationV1] = (),
               pair_verification_verifier: PortableCheckerHMACV1 | None = None) -> "CampaignEvidenceBundleV1":
        campaign.validate(); pair_tuple = tuple(pairs); verification_tuple = tuple(pair_verifications)
        portable = bool(verification_tuple) or pair_verification_verifier is not None
        if portable and (pair_verification_verifier is None or len(verification_tuple) != len(pair_tuple)):
            raise EvaluationCampaignError("PAIR_VERIFICATION_ARGUMENTS_INCOMPLETE")
        if len({v.root for v in verification_tuple}) != len(verification_tuple): raise EvaluationCampaignError("DUPLICATE_PAIR_VERIFICATION")
        for name, value in (("benchmark_adapter_executable_commitment", benchmark_adapter_executable_commitment),
                            ("runner_environment_commitment", runner_environment_commitment),
                            ("execution_receipt_bundle_commitment", execution_receipt_bundle_commitment)):
            _require_nonzero_hash(name, value)
        expected_slots = {(t.root, u.root) for t in campaign.tracks for u in t.task_trial_units}; actual_slots: list[tuple[str, str]] = []
        track_roots = {t.root for t in campaign.tracks}; ordered_verification_roots: list[str] = []
        for index, pair in enumerate(pair_tuple):
            pair.validate()
            if pair.campaign_root != campaign.root: raise EvaluationCampaignError("PAIR_CAMPAIGN_ROOT_MISMATCH")
            if pair.track_root not in track_roots: raise EvaluationCampaignError("PAIR_TRACK_NOT_IN_CAMPAIGN")
            if portable:
                assert pair_verification_verifier is not None
                verification = verification_tuple[index]
                pair_verification_verifier.verify_pair_verification(pair=pair, attestation=verification)
                ordered_verification_roots.append(verification.root)
            elif not _is_paired_trial_issued(pair):
                raise EvaluationCampaignError("PAIR_REPLAY_VERIFICATION_REQUIRED")
            actual_slots.append((pair.track_root, pair.task_trial_unit_root))
        if len(pair_tuple) != len(expected_slots) or set(actual_slots) != expected_slots: raise EvaluationCampaignError("PAIR_CARDINALITY_MISMATCH")
        if len(actual_slots) != len(set(actual_slots)): raise EvaluationCampaignError("DUPLICATE_PAIRED_TRIAL")
        contaminations = {t.contamination_class for t in campaign.tracks}; public_dev = any(t.split_privacy is SplitPrivacy.PUBLIC_DEV for t in campaign.tracks)
        if ContaminationClass.SUSPECTED in contaminations or ContaminationClass.EXPOSED in contaminations: status = CampaignEvidenceStatus.INVALIDATED_CONTAMINATION
        elif public_dev or ContaminationClass.PUBLIC in contaminations: status = CampaignEvidenceStatus.DEVELOPMENT_EVIDENCE_ONLY
        elif portable: status = CampaignEvidenceStatus.COLLECTIVE_CONTRIBUTION_EVALUABLE
        else: status = CampaignEvidenceStatus.HELD_OUT_EVIDENCE_COMPLETE
        bundle = cls(campaign_root=campaign.root, paired_trial_roots=tuple(p.root for p in pair_tuple),
                     pair_verification_roots=tuple(ordered_verification_roots),
                     benchmark_adapter_executable_commitment=benchmark_adapter_executable_commitment,
                     runner_environment_commitment=runner_environment_commitment,
                     execution_receipt_bundle_commitment=execution_receipt_bundle_commitment, evidence_status=status)
        bundle.validate(); return bundle

    def validate(self) -> None:
        if self.bundle_kind != CAMPAIGN_EVIDENCE_BUNDLE_KIND: raise EvaluationCampaignError("CAMPAIGN_EVIDENCE_BUNDLE_KIND_MISMATCH")
        _require_hash("campaign_root", self.campaign_root)
        if not self.paired_trial_roots: raise EvaluationCampaignError("PAIRED_TRIAL_ROOTS_EMPTY")
        for root in self.paired_trial_roots: _require_hash("paired_trial_root", root)
        if len(self.paired_trial_roots) != len(set(self.paired_trial_roots)): raise EvaluationCampaignError("DUPLICATE_PAIRED_TRIAL_ROOT")
        for root in self.pair_verification_roots: _require_nonzero_hash("pair_verification_root", root)
        if len(self.pair_verification_roots) != len(set(self.pair_verification_roots)): raise EvaluationCampaignError("DUPLICATE_PAIR_VERIFICATION_ROOT")
        if self.evidence_status is CampaignEvidenceStatus.COLLECTIVE_CONTRIBUTION_EVALUABLE and len(self.pair_verification_roots) != len(self.paired_trial_roots):
            raise EvaluationCampaignError("COLLECTIVE_EVIDENCE_REQUIRES_PAIR_VERIFICATIONS")
        for name in ("benchmark_adapter_executable_commitment", "runner_environment_commitment", "execution_receipt_bundle_commitment"):
            _require_nonzero_hash(name, getattr(self, name))
        if not isinstance(self.evidence_status, CampaignEvidenceStatus): raise EvaluationCampaignError("CAMPAIGN_EVIDENCE_STATUS_INVALID")
    def to_dict(self) -> dict[str, object]:
        return {"bundle_kind": self.bundle_kind, "campaign_root": self.campaign_root, "paired_trial_roots": list(self.paired_trial_roots),
                "pair_verification_roots": list(self.pair_verification_roots),
                "benchmark_adapter_executable_commitment": self.benchmark_adapter_executable_commitment,
                "runner_environment_commitment": self.runner_environment_commitment,
                "execution_receipt_bundle_commitment": self.execution_receipt_bundle_commitment, "evidence_status": self.evidence_status.value}
    @property
    def root(self) -> str: self.validate(); return canonical_hash("AEGIS_UCI8_CAMPAIGN_EVIDENCE_BUNDLE_V1", self.to_dict())
