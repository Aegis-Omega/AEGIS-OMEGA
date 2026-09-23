"""Post-settlement Hallucination Delta calibration for treasury agents.

The metric is inherited from the historical Kaggle HD lineage:
    HD = |claimed_correctness - actual_correctness|

This module applies that metric only after an externally verified outcome exists.
It cannot authorize a transfer, increase an authority score, or substitute for
the AEGIS D3/D4 execution gate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    SovereignExecutionError,
    canonical_hash,
)

MICROS = 1_000_000
METRIC_NAME = "HALLUCINATION_DELTA"
METRIC_DEFINITION = "abs(claimed_correctness - actual_correctness)"


def _assert_probability_micros(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= MICROS):
        raise SovereignExecutionError(f"{name}:OUT_OF_RANGE")


def hallucination_delta_micros(
    claimed_correctness_micros: int,
    actual_correctness_micros: int,
) -> int:
    _assert_probability_micros("claimed_correctness_micros", claimed_correctness_micros)
    _assert_probability_micros("actual_correctness_micros", actual_correctness_micros)
    return abs(claimed_correctness_micros - actual_correctness_micros)


@dataclass(frozen=True)
class TreasuryCalibrationRecord:
    schema_version: str
    metric_name: str
    metric_definition: str
    authority_decision_root: str
    transfer_plan_root: str
    settlement_reference_root: str
    claimed_correctness_micros: int
    actual_correctness_micros: int
    hd_micros: int
    outcome_label: str
    benchmark_lineage: str = "KAGGLE_HD_APRIL_2026"
    authority_effect: str = "NONE"
    scope: str = "POST_SETTLEMENT_CALIBRATION_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("TREASURY_CALIBRATION_SCHEMA_UNSUPPORTED")
        if self.metric_name != METRIC_NAME or self.metric_definition != METRIC_DEFINITION:
            raise SovereignExecutionError("TREASURY_CALIBRATION_METRIC_INVALID")
        for name in ("authority_decision_root", "transfer_plan_root", "settlement_reference_root"):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise SovereignExecutionError(f"{name}:INVALID_SHA256")
            try:
                int(value, 16)
            except ValueError as exc:
                raise SovereignExecutionError(f"{name}:INVALID_SHA256") from exc
        _assert_probability_micros("claimed_correctness_micros", self.claimed_correctness_micros)
        _assert_probability_micros("actual_correctness_micros", self.actual_correctness_micros)
        expected = hallucination_delta_micros(
            self.claimed_correctness_micros,
            self.actual_correctness_micros,
        )
        if self.hd_micros != expected:
            raise SovereignExecutionError("TREASURY_CALIBRATION_HD_MISMATCH")
        if not isinstance(self.outcome_label, str) or not self.outcome_label.strip():
            raise SovereignExecutionError("TREASURY_CALIBRATION_OUTCOME_INVALID")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("TREASURY_CALIBRATION_AUTHORITY_EFFECT_INVALID")
        if self.scope != "POST_SETTLEMENT_CALIBRATION_ONLY":
            raise SovereignExecutionError("TREASURY_CALIBRATION_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TREASURY_HD_CALIBRATION_V1", asdict(self))


def calibrate_treasury_outcome(
    *,
    authority_decision_root: str,
    transfer_plan_root: str,
    settlement_reference_root: str,
    claimed_correctness_micros: int,
    actual_correctness_micros: int,
    outcome_label: str,
) -> TreasuryCalibrationRecord:
    record = TreasuryCalibrationRecord(
        schema_version=SCHEMA_VERSION,
        metric_name=METRIC_NAME,
        metric_definition=METRIC_DEFINITION,
        authority_decision_root=authority_decision_root,
        transfer_plan_root=transfer_plan_root,
        settlement_reference_root=settlement_reference_root,
        claimed_correctness_micros=claimed_correctness_micros,
        actual_correctness_micros=actual_correctness_micros,
        hd_micros=hallucination_delta_micros(
            claimed_correctness_micros,
            actual_correctness_micros,
        ),
        outcome_label=outcome_label,
    )
    record.validate()
    return record
