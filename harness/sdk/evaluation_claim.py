"""UCI-8 falsifiable structural-value claim reference contract.

This module does not define or test AGI. It admits only the narrow claim that a
preregistered AEGIS configuration outperforms a compute-matched naive baseline
on an exact task population under exact budget and metric commitments.

The SQLite run ledger is a local append-only reference mechanism. It is not an
authenticated, tamper-resistant, distributed, or externally timestamped ledger.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from harness.sdk.evaluation_campaign import EvaluationCampaignError
from harness.sdk.sovereign_execution import canonical_hash

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")

COMPUTE_BUDGET_KIND = "COMPUTE_BUDGET_V1"
COMPUTE_MATCHED_BASELINE_KIND = "COMPUTE_MATCHED_BASELINE_SPEC_V1"
BASELINE_NOISE_CALIBRATION_KIND = "BASELINE_NOISE_CALIBRATION_V1"
METRIC_COMPARISON_KIND = "METRIC_COMPARISON_V1"
STRUCTURAL_VALUE_CLAIM_KIND = "PREREGISTERED_STRUCTURAL_VALUE_CLAIM_V1"
STRUCTURAL_VALUE_EVALUATION_KIND = "STRUCTURAL_VALUE_CLAIM_EVALUATION_V1"


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EvaluationCampaignError(f"{name}:INVALID_SHA256")


def _require_nonzero_hash(name: str, value: str) -> None:
    _require_hash(name, value)
    if value == "0" * 64:
        raise EvaluationCampaignError(f"{name}:ZERO_HASH_NOT_ALLOWED")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise EvaluationCampaignError(f"{name}:INVALID_ID")


def _require_nonnegative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise EvaluationCampaignError(f"{name}:INVALID_NONNEGATIVE_INTEGER")


class BaselineStrategy(str, Enum):
    BEST_OF_N_DETERMINISTIC_CHECKER = "BEST_OF_N_DETERMINISTIC_CHECKER"
    SELF_CONSISTENCY_DETERMINISTIC_AGGREGATOR = "SELF_CONSISTENCY_DETERMINISTIC_AGGREGATOR"


class CollectiveClaimStatus(str, Enum):
    SATISFIED = "SATISFIED"
    FALSIFIED = "FALSIFIED"


@dataclass(frozen=True)
class ComputeBudgetV1:
    max_input_tokens: int
    max_output_tokens: int
    max_model_calls: int
    max_tool_calls: int
    budget_kind: str = COMPUTE_BUDGET_KIND

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.budget_kind != COMPUTE_BUDGET_KIND:
            raise EvaluationCampaignError("COMPUTE_BUDGET_KIND_MISMATCH")
        _require_nonnegative_int("max_input_tokens", self.max_input_tokens)
        _require_nonnegative_int("max_output_tokens", self.max_output_tokens)
        _require_nonnegative_int("max_model_calls", self.max_model_calls)
        _require_nonnegative_int("max_tool_calls", self.max_tool_calls)
        if self.max_input_tokens == 0 and self.max_output_tokens == 0:
            raise EvaluationCampaignError("COMPUTE_BUDGET_TOKEN_LIMIT_EMPTY")
        if self.max_model_calls == 0:
            raise EvaluationCampaignError("COMPUTE_BUDGET_MODEL_CALL_LIMIT_EMPTY")

    def to_dict(self) -> dict[str, object]:
        return {
            "budget_kind": self.budget_kind,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_COMPUTE_BUDGET_V1", self.to_dict())


@dataclass(frozen=True)
class ComputeMatchedBaselineSpecV1:
    campaign_root: str
    strongest_constituent_runtime_commitment: str
    baseline_runtime_commitment: str
    system_total_budget: ComputeBudgetV1
    baseline_total_budget: ComputeBudgetV1
    strategy: BaselineStrategy
    strategy_commitment: str
    spec_kind: str = COMPUTE_MATCHED_BASELINE_KIND

    @classmethod
    def create(
        cls,
        *,
        campaign_root: str,
        strongest_constituent_runtime_commitment: str,
        baseline_runtime_commitment: str,
        system_total_budget: ComputeBudgetV1,
        baseline_total_budget: ComputeBudgetV1,
        strategy: BaselineStrategy,
        strategy_commitment: str,
    ) -> "ComputeMatchedBaselineSpecV1":
        spec = cls(
            campaign_root=campaign_root,
            strongest_constituent_runtime_commitment=strongest_constituent_runtime_commitment,
            baseline_runtime_commitment=baseline_runtime_commitment,
            system_total_budget=system_total_budget,
            baseline_total_budget=baseline_total_budget,
            strategy=strategy,
            strategy_commitment=strategy_commitment,
        )
        spec.validate()
        return spec

    def validate(self) -> None:
        if self.spec_kind != COMPUTE_MATCHED_BASELINE_KIND:
            raise EvaluationCampaignError("COMPUTE_MATCHED_BASELINE_KIND_MISMATCH")
        for name in (
            "campaign_root",
            "strongest_constituent_runtime_commitment",
            "baseline_runtime_commitment",
            "strategy_commitment",
        ):
            _require_nonzero_hash(name, getattr(self, name))
        self.system_total_budget.validate()
        self.baseline_total_budget.validate()
        if self.baseline_runtime_commitment != self.strongest_constituent_runtime_commitment:
            raise EvaluationCampaignError("COMPUTE_MATCH_BASELINE_RUNTIME_MISMATCH")
        if (
            self.system_total_budget.max_input_tokens != self.baseline_total_budget.max_input_tokens
            or self.system_total_budget.max_output_tokens != self.baseline_total_budget.max_output_tokens
        ):
            raise EvaluationCampaignError("COMPUTE_MATCH_TOKEN_BUDGET_MISMATCH")
        if (
            self.system_total_budget.max_model_calls != self.baseline_total_budget.max_model_calls
            or self.system_total_budget.max_tool_calls != self.baseline_total_budget.max_tool_calls
        ):
            raise EvaluationCampaignError("COMPUTE_MATCH_CALL_BUDGET_MISMATCH")
        if not isinstance(self.strategy, BaselineStrategy):
            raise EvaluationCampaignError("BASELINE_STRATEGY_INVALID")

    def to_dict(self) -> dict[str, object]:
        return {
            "spec_kind": self.spec_kind,
            "campaign_root": self.campaign_root,
            "strongest_constituent_runtime_commitment": self.strongest_constituent_runtime_commitment,
            "baseline_runtime_commitment": self.baseline_runtime_commitment,
            "system_total_budget": self.system_total_budget.to_dict(),
            "baseline_total_budget": self.baseline_total_budget.to_dict(),
            "strategy": self.strategy.value,
            "strategy_commitment": self.strategy_commitment,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_COMPUTE_MATCHED_BASELINE_SPEC_V1", self.to_dict())


@dataclass(frozen=True)
class BaselineNoiseCalibrationV1:
    metric_id: str
    unit_id: str
    calibration_run_ids: tuple[str, ...]
    baseline_values: tuple[int, ...]
    calibration_split_commitment: str
    calibration_evidence_commitment: str
    delta_floor: int
    floor_rule: str = "MAX_OBSERVED_RANGE_V1"
    calibration_kind: str = BASELINE_NOISE_CALIBRATION_KIND

    @classmethod
    def create(
        cls,
        *,
        metric_id: str,
        unit_id: str,
        calibration_run_ids: Iterable[str],
        baseline_values: Iterable[int],
        calibration_split_commitment: str,
        calibration_evidence_commitment: str,
    ) -> "BaselineNoiseCalibrationV1":
        run_ids = tuple(calibration_run_ids)
        values = tuple(baseline_values)
        if len(run_ids) < 3:
            raise EvaluationCampaignError("BASELINE_NOISE_REQUIRES_AT_LEAST_THREE_RUNS")
        if len(run_ids) != len(values):
            raise EvaluationCampaignError("BASELINE_NOISE_RUN_VALUE_CARDINALITY_MISMATCH")
        if len(set(run_ids)) != len(run_ids):
            raise EvaluationCampaignError("DUPLICATE_CALIBRATION_RUN_ID")
        for run_id in run_ids:
            _require_id("calibration_run_id", run_id)
        for value in values:
            if not isinstance(value, int) or isinstance(value, bool):
                raise EvaluationCampaignError("BASELINE_NOISE_VALUE_INVALID")
        calibration = cls(
            metric_id=metric_id,
            unit_id=unit_id,
            calibration_run_ids=run_ids,
            baseline_values=values,
            calibration_split_commitment=calibration_split_commitment,
            calibration_evidence_commitment=calibration_evidence_commitment,
            delta_floor=max(values) - min(values),
        )
        calibration.validate()
        return calibration

    def validate(self) -> None:
        if self.calibration_kind != BASELINE_NOISE_CALIBRATION_KIND:
            raise EvaluationCampaignError("BASELINE_NOISE_CALIBRATION_KIND_MISMATCH")
        _require_id("metric_id", self.metric_id)
        _require_id("unit_id", self.unit_id)
        _require_nonzero_hash("calibration_split_commitment", self.calibration_split_commitment)
        _require_nonzero_hash("calibration_evidence_commitment", self.calibration_evidence_commitment)
        if self.floor_rule != "MAX_OBSERVED_RANGE_V1":
            raise EvaluationCampaignError("BASELINE_NOISE_FLOOR_RULE_INVALID")
        if len(self.calibration_run_ids) < 3:
            raise EvaluationCampaignError("BASELINE_NOISE_REQUIRES_AT_LEAST_THREE_RUNS")
        if len(self.calibration_run_ids) != len(self.baseline_values):
            raise EvaluationCampaignError("BASELINE_NOISE_RUN_VALUE_CARDINALITY_MISMATCH")
        if len(set(self.calibration_run_ids)) != len(self.calibration_run_ids):
            raise EvaluationCampaignError("DUPLICATE_CALIBRATION_RUN_ID")
        expected_floor = max(self.baseline_values) - min(self.baseline_values)
        if self.delta_floor != expected_floor:
            raise EvaluationCampaignError("BASELINE_NOISE_DELTA_FLOOR_MISMATCH")

    def to_dict(self) -> dict[str, object]:
        return {
            "calibration_kind": self.calibration_kind,
            "metric_id": self.metric_id,
            "unit_id": self.unit_id,
            "calibration_run_ids": list(self.calibration_run_ids),
            "baseline_values": list(self.baseline_values),
            "calibration_split_commitment": self.calibration_split_commitment,
            "calibration_evidence_commitment": self.calibration_evidence_commitment,
            "delta_floor": self.delta_floor,
            "floor_rule": self.floor_rule,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_BASELINE_NOISE_CALIBRATION_V1", self.to_dict())


@dataclass(frozen=True)
class MetricComparisonV1:
    metric_id: str
    unit_id: str
    system_value: int
    baseline_value: int
    comparison_kind: str = METRIC_COMPARISON_KIND

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.comparison_kind != METRIC_COMPARISON_KIND:
            raise EvaluationCampaignError("METRIC_COMPARISON_KIND_MISMATCH")
        _require_id("metric_id", self.metric_id)
        _require_id("unit_id", self.unit_id)
        for name, value in (("system_value", self.system_value), ("baseline_value", self.baseline_value)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise EvaluationCampaignError(f"{name}:INVALID_INTEGER")

    @property
    def delta(self) -> int:
        self.validate()
        return self.system_value - self.baseline_value

    def to_dict(self) -> dict[str, object]:
        return {
            "comparison_kind": self.comparison_kind,
            "metric_id": self.metric_id,
            "unit_id": self.unit_id,
            "system_value": self.system_value,
            "baseline_value": self.baseline_value,
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_METRIC_COMPARISON_V1", self.to_dict())


@dataclass(frozen=True)
class StructuralValueClaimEvaluationV1:
    claim_root: str
    status: CollectiveClaimStatus
    failing_metric_ids: tuple[str, ...]
    evaluation_kind: str = STRUCTURAL_VALUE_EVALUATION_KIND

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_kind": self.evaluation_kind,
            "claim_root": self.claim_root,
            "status": self.status.value,
            "failing_metric_ids": list(self.failing_metric_ids),
        }


@dataclass(frozen=True)
class PreregisteredStructuralValueClaimV1:
    campaign_root: str
    comparison_task_population_commitment: str
    compute_matched_baseline: ComputeMatchedBaselineSpecV1
    calibrations: tuple[BaselineNoiseCalibrationV1, ...]
    claim_kind: str = STRUCTURAL_VALUE_CLAIM_KIND

    @classmethod
    def create(
        cls,
        *,
        campaign_root: str,
        comparison_task_population_commitment: str,
        compute_matched_baseline: ComputeMatchedBaselineSpecV1,
        calibrations: Iterable[BaselineNoiseCalibrationV1],
    ) -> "PreregisteredStructuralValueClaimV1":
        claim = cls(
            campaign_root=campaign_root,
            comparison_task_population_commitment=comparison_task_population_commitment,
            compute_matched_baseline=compute_matched_baseline,
            calibrations=tuple(calibrations),
        )
        claim.validate()
        return claim

    def validate(self) -> None:
        if self.claim_kind != STRUCTURAL_VALUE_CLAIM_KIND:
            raise EvaluationCampaignError("STRUCTURAL_VALUE_CLAIM_KIND_MISMATCH")
        _require_nonzero_hash("campaign_root", self.campaign_root)
        _require_nonzero_hash(
            "comparison_task_population_commitment", self.comparison_task_population_commitment
        )
        self.compute_matched_baseline.validate()
        if self.compute_matched_baseline.campaign_root != self.campaign_root:
            raise EvaluationCampaignError("COMPUTE_MATCH_CAMPAIGN_ROOT_MISMATCH")
        if not self.calibrations:
            raise EvaluationCampaignError("CLAIM_CALIBRATIONS_EMPTY")
        metric_ids = [calibration.metric_id for calibration in self.calibrations]
        if len(metric_ids) != len(set(metric_ids)):
            raise EvaluationCampaignError("DUPLICATE_CLAIM_METRIC")
        for calibration in self.calibrations:
            calibration.validate()
            if calibration.calibration_split_commitment == self.comparison_task_population_commitment:
                raise EvaluationCampaignError("CALIBRATION_COMPARISON_POPULATION_COLLISION")

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_kind": self.claim_kind,
            "campaign_root": self.campaign_root,
            "comparison_task_population_commitment": self.comparison_task_population_commitment,
            "compute_matched_baseline_root": self.compute_matched_baseline.root,
            "calibration_roots": [calibration.root for calibration in self.calibrations],
        }

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_UCI8_PREREGISTERED_STRUCTURAL_VALUE_CLAIM_V1", self.to_dict())

    def evaluate(self, comparisons: Iterable[MetricComparisonV1]) -> StructuralValueClaimEvaluationV1:
        self.validate()
        comparison_tuple = tuple(comparisons)
        calibration_by_metric = {calibration.metric_id: calibration for calibration in self.calibrations}
        comparison_ids = [comparison.metric_id for comparison in comparison_tuple]
        required_ids = [calibration.metric_id for calibration in self.calibrations]
        if len(comparison_ids) != len(set(comparison_ids)) or set(comparison_ids) != set(required_ids):
            raise EvaluationCampaignError("CLAIM_METRIC_SET_MISMATCH")
        comparison_by_metric = {comparison.metric_id: comparison for comparison in comparison_tuple}
        failing: list[str] = []
        for metric_id in required_ids:
            comparison = comparison_by_metric[metric_id]
            comparison.validate()
            calibration = calibration_by_metric[metric_id]
            if comparison.unit_id != calibration.unit_id:
                raise EvaluationCampaignError("CLAIM_METRIC_UNIT_MISMATCH")
            if comparison.delta < calibration.delta_floor:
                failing.append(metric_id)
        return StructuralValueClaimEvaluationV1(
            claim_root=self.root,
            status=CollectiveClaimStatus.FALSIFIED if failing else CollectiveClaimStatus.SATISFIED,
            failing_metric_ids=tuple(failing),
        )


@dataclass(frozen=True)
class CampaignRunAttemptV1:
    run_id: str
    seed_commitment: str
    terminal_status: str
    reason: str | None


class CampaignRunLedgerV1:
    """Local append-only SQLite campaign-attempt ledger reference."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._db = sqlite3.connect(str(self.path))
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_kind TEXT NOT NULL,
                campaign_root TEXT,
                claim_root TEXT,
                object_root TEXT,
                run_id TEXT,
                seed_commitment TEXT,
                result_commitment TEXT,
                reason TEXT,
                reason_commitment TEXT
            )
            """
        )
        self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS one_run_start ON events(run_id) WHERE event_kind='RUN_STARTED'"
        )
        self._db.commit()

    def _append(self, **values: object) -> None:
        columns = tuple(values.keys())
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT INTO events ({','.join(columns)}) VALUES ({placeholders})"
        with self._db:
            self._db.execute(sql, tuple(values[column] for column in columns))

    def record_calibration(self, calibration: BaselineNoiseCalibrationV1) -> None:
        calibration.validate()
        row = self._db.execute(
            "SELECT 1 FROM events WHERE event_kind='CALIBRATION_RECORDED' AND object_root=?",
            (calibration.root,),
        ).fetchone()
        if row is not None:
            raise EvaluationCampaignError("CALIBRATION_ALREADY_RECORDED")
        self._append(event_kind="CALIBRATION_RECORDED", object_root=calibration.root)

    def freeze_claim(self, claim: PreregisteredStructuralValueClaimV1) -> None:
        claim.validate()
        existing = self._db.execute(
            "SELECT 1 FROM events WHERE event_kind='CLAIM_FROZEN' AND claim_root=?",
            (claim.root,),
        ).fetchone()
        if existing is not None:
            raise EvaluationCampaignError("CLAIM_ALREADY_FROZEN")
        for calibration in claim.calibrations:
            row = self._db.execute(
                "SELECT 1 FROM events WHERE event_kind='CALIBRATION_RECORDED' AND object_root=?",
                (calibration.root,),
            ).fetchone()
            if row is None:
                raise EvaluationCampaignError("CALIBRATION_MUST_PRECEDE_CLAIM_FREEZE")
        self._append(
            event_kind="CLAIM_FROZEN",
            campaign_root=claim.campaign_root,
            claim_root=claim.root,
            object_root=claim.root,
        )

    def _require_frozen(self, claim: PreregisteredStructuralValueClaimV1) -> None:
        row = self._db.execute(
            "SELECT 1 FROM events WHERE event_kind='CLAIM_FROZEN' AND campaign_root=? AND claim_root=?",
            (claim.campaign_root, claim.root),
        ).fetchone()
        if row is None:
            raise EvaluationCampaignError("CLAIM_FREEZE_REQUIRED")

    def start_run(
        self,
        *,
        run_id: str,
        claim: PreregisteredStructuralValueClaimV1,
        seed_commitment: str,
    ) -> None:
        _require_id("run_id", run_id)
        _require_nonzero_hash("seed_commitment", seed_commitment)
        claim.validate()
        self._require_frozen(claim)
        try:
            self._append(
                event_kind="RUN_STARTED",
                campaign_root=claim.campaign_root,
                claim_root=claim.root,
                run_id=run_id,
                seed_commitment=seed_commitment,
            )
        except sqlite3.IntegrityError as exc:
            raise EvaluationCampaignError("RUN_ID_ALREADY_STARTED") from exc

    def _run_start(self, run_id: str) -> tuple[str, str, str]:
        row = self._db.execute(
            "SELECT campaign_root, claim_root, seed_commitment FROM events WHERE event_kind='RUN_STARTED' AND run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise EvaluationCampaignError("RUN_START_REQUIRED")
        return str(row[0]), str(row[1]), str(row[2])

    def _require_no_terminal(self, run_id: str) -> None:
        row = self._db.execute(
            "SELECT 1 FROM events WHERE run_id=? AND event_kind IN ('RUN_COMPLETED','RUN_ABANDONED')",
            (run_id,),
        ).fetchone()
        if row is not None:
            raise EvaluationCampaignError("RUN_ALREADY_TERMINAL")

    def complete_run(self, *, run_id: str, result_commitment: str) -> None:
        campaign_root, claim_root, _seed = self._run_start(run_id)
        self._require_no_terminal(run_id)
        _require_nonzero_hash("result_commitment", result_commitment)
        self._append(
            event_kind="RUN_COMPLETED",
            campaign_root=campaign_root,
            claim_root=claim_root,
            run_id=run_id,
            result_commitment=result_commitment,
        )

    def abandon_run(
        self,
        *,
        run_id: str,
        reason: str,
        reason_commitment: str,
    ) -> None:
        campaign_root, claim_root, _seed = self._run_start(run_id)
        self._require_no_terminal(run_id)
        _require_id("reason", reason)
        _require_nonzero_hash("reason_commitment", reason_commitment)
        self._append(
            event_kind="RUN_ABANDONED",
            campaign_root=campaign_root,
            claim_root=claim_root,
            run_id=run_id,
            reason=reason,
            reason_commitment=reason_commitment,
        )

    def attempts(self, campaign_root: str) -> tuple[CampaignRunAttemptV1, ...]:
        _require_nonzero_hash("campaign_root", campaign_root)
        starts = self._db.execute(
            "SELECT seq, run_id, seed_commitment FROM events WHERE event_kind='RUN_STARTED' AND campaign_root=? ORDER BY seq",
            (campaign_root,),
        ).fetchall()
        attempts: list[CampaignRunAttemptV1] = []
        for _seq, run_id, seed in starts:
            terminal = self._db.execute(
                "SELECT event_kind, reason FROM events WHERE run_id=? AND event_kind IN ('RUN_COMPLETED','RUN_ABANDONED') ORDER BY seq LIMIT 1",
                (run_id,),
            ).fetchone()
            if terminal is None:
                status, reason = "STARTED", None
            elif terminal[0] == "RUN_COMPLETED":
                status, reason = "COMPLETED", None
            else:
                status, reason = "ABANDONED", terminal[1]
            attempts.append(
                CampaignRunAttemptV1(
                    run_id=str(run_id),
                    seed_commitment=str(seed),
                    terminal_status=status,
                    reason=None if reason is None else str(reason),
                )
            )
        return tuple(attempts)

    def close(self) -> None:
        self._db.close()
