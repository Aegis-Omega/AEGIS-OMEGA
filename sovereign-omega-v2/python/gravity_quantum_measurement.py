"""AEGIS Ω — Gravity/Quantum tabletop measurement gates V1.

This module defines fail-closed receipt semantics only. It does not operate
hardware and does not fabricate physical measurements.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping
import re

HEX64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_NUISANCE_CHANNELS = (
    "electrostatic_patch",
    "magnetic",
    "casimir_dispersion",
    "mechanical_cross_talk",
    "seismic_vibration",
    "laser_readout_cross_talk",
    "thermal_common_bath",
    "residual_gas",
    "feedback_control",
    "gravity_gradient_position",
    "clock_timing",
)


class MeasurementGateError(ValueError):
    pass


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise MeasurementGateError(f"{label}: invalid sha256")
    return value


def _decimal(value: Any, label: str) -> Decimal:
    if not isinstance(value, str):
        raise MeasurementGateError(f"{label}: decimal string required")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise MeasurementGateError(f"{label}: invalid decimal") from exc
    if not result.is_finite():
        raise MeasurementGateError(f"{label}: nonfinite")
    return result


def validate_calibration(receipt: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema",
        "apparatus_id",
        "calibration_epoch_id",
        "geometry_digest",
        "clock_digest",
        "source_configuration_digest",
        "detector_configuration_digest",
        "status",
        "authority_effect",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        raise MeasurementGateError("calibration: field mismatch")
    if receipt["schema"] != "AEGIS_GQ_CALIBRATION_RECEIPT_V1":
        raise MeasurementGateError("calibration: schema")
    for key in (
        "geometry_digest",
        "clock_digest",
        "source_configuration_digest",
        "detector_configuration_digest",
    ):
        _digest(receipt[key], key)
    passed = (
        bool(receipt["apparatus_id"])
        and bool(receipt["calibration_epoch_id"])
        and receipt["status"] == "PASS"
        and receipt["authority_effect"] == "NONE"
    )
    return {
        "status": "PASS" if passed else "DENY",
        "authority_effect": "NONE",
    }


def validate_nuisance(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        raise MeasurementGateError("nuisance: object required")
    if set(receipt) != {"schema", "controls", "authority_effect"}:
        raise MeasurementGateError("nuisance: field mismatch")
    if receipt["schema"] != "AEGIS_GQ_NUISANCE_RECEIPT_V1":
        raise MeasurementGateError("nuisance: schema")
    controls = receipt["controls"]
    if not isinstance(controls, Mapping):
        raise MeasurementGateError("nuisance: controls object required")
    missing = tuple(sorted(set(REQUIRED_NUISANCE_CHANNELS) - set(controls)))
    extra = tuple(sorted(set(controls) - set(REQUIRED_NUISANCE_CHANNELS)))
    failures = []
    for name in REQUIRED_NUISANCE_CHANNELS:
        item = controls.get(name)
        if not isinstance(item, Mapping):
            continue
        if set(item) != {"status", "evidence_sha256"}:
            failures.append((name, "MALFORMED"))
            continue
        try:
            _digest(item["evidence_sha256"], f"{name}.evidence_sha256")
        except MeasurementGateError:
            failures.append((name, "BAD_DIGEST"))
            continue
        if item["status"] != "PASS":
            failures.append((name, f"STATUS:{item['status']}"))
    passed = (
        not missing
        and not extra
        and not failures
        and receipt["authority_effect"] == "NONE"
    )
    return {
        "status": "PASS" if passed else "DENY",
        "missing": missing,
        "extra": extra,
        "failures": tuple(failures),
        "authority_effect": "NONE",
    }


def validate_measurement(receipt: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema",
        "apparatus_id",
        "raw_data_sha256",
        "calibration_receipt_sha256",
        "nuisance_receipt_sha256",
        "preregistration_sha256",
        "analysis_code_sha256",
        "status",
        "authority_effect",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        raise MeasurementGateError("measurement: field mismatch")
    if receipt["schema"] != "AEGIS_GQ_PHYSICAL_MEASUREMENT_RECEIPT_V1":
        raise MeasurementGateError("measurement: schema")
    for key in (
        "raw_data_sha256",
        "calibration_receipt_sha256",
        "nuisance_receipt_sha256",
        "preregistration_sha256",
        "analysis_code_sha256",
    ):
        _digest(receipt[key], key)
    passed = (
        bool(receipt["apparatus_id"])
        and receipt["status"] == "PASS"
        and receipt["authority_effect"] == "NONE"
    )
    return {
        "status": "PASS" if passed else "DENY",
        "authority_effect": "NONE",
    }


def evaluate_witness(receipt: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema",
        "measurement_receipt_sha256",
        "estimate",
        "total_uncertainty",
        "threshold",
        "decision_rule",
        "authority_effect",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        raise MeasurementGateError("witness: field mismatch")
    if receipt["schema"] != "AEGIS_GQ_ENTANGLEMENT_WITNESS_RECEIPT_V1":
        raise MeasurementGateError("witness: schema")
    _digest(receipt["measurement_receipt_sha256"], "measurement_receipt_sha256")
    if receipt["decision_rule"] != "ESTIMATE_PLUS_UNCERTAINTY_LT_THRESHOLD":
        raise MeasurementGateError("witness: unsupported decision rule")
    estimate = _decimal(receipt["estimate"], "estimate")
    uncertainty = _decimal(receipt["total_uncertainty"], "total_uncertainty")
    threshold = _decimal(receipt["threshold"], "threshold")
    if uncertainty < 0:
        raise MeasurementGateError("witness: negative uncertainty")
    upper = estimate + uncertainty
    passed = upper < threshold and receipt["authority_effect"] == "NONE"
    return {
        "status": "PASS" if passed else "DENY",
        "upper_bound": str(upper),
        "threshold": str(threshold),
        "authority_effect": "NONE",
    }


def validate_replication(
    primary: Mapping[str, Any],
    replication: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "schema",
        "status",
        "apparatus_id",
        "analysis_implementation_sha256",
        "same_preregistered_claim",
        "authority_effect",
    }
    if set(primary) != required or set(replication) != required:
        raise MeasurementGateError("replication: field mismatch")
    for item in (primary, replication):
        if item["schema"] != "AEGIS_GQ_REPLICATION_RECEIPT_V1":
            raise MeasurementGateError("replication: schema")
        _digest(
            item["analysis_implementation_sha256"],
            "analysis_implementation_sha256",
        )
    independent = (
        primary["apparatus_id"] != replication["apparatus_id"]
        and primary["analysis_implementation_sha256"]
        != replication["analysis_implementation_sha256"]
    )
    passed = (
        primary["status"] == "PASS"
        and replication["status"] == "PASS"
        and primary["same_preregistered_claim"] is True
        and replication["same_preregistered_claim"] is True
        and independent
        and primary["authority_effect"] == "NONE"
        and replication["authority_effect"] == "NONE"
    )
    return {
        "status": "PASS" if passed else "DENY",
        "independent": independent,
        "authority_effect": "NONE",
    }
