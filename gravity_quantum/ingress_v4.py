#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum V4 point-level evidence ingress contract.

This module validates provenance structure for point-level phase data without pretending
that a test fixture is empirical evidence. All numeric values admitted to hashed state are
integers with explicit units. Source bytes and calibration configuration are content-bound
by SHA-256. Fit release is fail-closed for TEST_FIXTURE origin.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable

from verifiable.chain import canon, sha256_hex

V4_INGRESS_SCHEMA = "AEGIS_QGI_POINT_LEVEL_INGRESS_V4"
SOURCE_BINDING_SCHEMA = "AEGIS_QGI_SOURCE_BINDING_V4"
CALIBRATION_BINDING_SCHEMA = "AEGIS_QGI_CALIBRATION_BINDING_V4"
CONTRACT_FIXTURE_BYTES = b"AEGIS_QGI_V4_CONTRACT_FIXTURE_NOT_EMPIRICAL\n"
CONTRACT_FIXTURE_CALIBRATION_BYTES = b"QGI_V4_TEST_CALIBRATION_CONFIG\n"

ALLOWED_EVIDENCE_ORIGINS = {
    "TEST_FIXTURE",
    "EXTERNAL_EXPERIMENTAL_SOURCE",
}


def _require_nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"INVALID_STRING:{name}")
    return value


def _require_int(name: str, value: Any) -> int:
    if type(value) is not int:
        raise ValueError(f"NON_INTEGER_NUMERIC_STATE:{name}")
    return value


def _require_sha256(name: str, value: Any) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"INVALID_SHA256:{name}")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"INVALID_SHA256:{name}") from exc
    return value.lower()


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_float(v) for v in value)
    return False


def build_source_binding(
    source_bytes: bytes,
    *,
    source_uri: str,
    media_type: str,
    evidence_origin: str,
) -> dict:
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ValueError("EMPTY_OR_NONBYTE_SOURCE")
    _require_nonempty_string("source_uri", source_uri)
    _require_nonempty_string("media_type", media_type)
    if evidence_origin not in ALLOWED_EVIDENCE_ORIGINS:
        raise ValueError("UNREGISTERED_EVIDENCE_ORIGIN")
    return {
        "schema": SOURCE_BINDING_SCHEMA,
        "source_uri": source_uri,
        "media_type": media_type,
        "evidence_origin": evidence_origin,
        "source_sha256": sha256_hex(source_bytes),
        "source_byte_length": len(source_bytes),
        "retrieval_status": (
            "TEST_FIXTURE_NOT_EXTERNAL_ATTESTATION"
            if evidence_origin == "TEST_FIXTURE"
            else "CALLER_BOUND_BYTES_REQUIRES_INDEPENDENT_VERIFICATION"
        ),
        "independent_source_verification": "NOT_ESTABLISHED",
        "authority_effect": "NONE",
    }


def build_calibration_binding(
    epoch_id: str,
    config_bytes: bytes,
    *,
    valid_from: str,
    valid_until: str,
    calibration_origin: str,
) -> dict:
    _require_nonempty_string("epoch_id", epoch_id)
    _require_nonempty_string("valid_from", valid_from)
    _require_nonempty_string("valid_until", valid_until)
    _require_nonempty_string("calibration_origin", calibration_origin)
    if not isinstance(config_bytes, bytes) or not config_bytes:
        raise ValueError("EMPTY_OR_NONBYTE_CALIBRATION_CONFIG")
    return {
        "schema": CALIBRATION_BINDING_SCHEMA,
        "calibration_epoch_id": epoch_id,
        "config_sha256": sha256_hex(config_bytes),
        "config_byte_length": len(config_bytes),
        "valid_from": valid_from,
        "valid_until": valid_until,
        "calibration_origin": calibration_origin,
        "independent_calibration_verification": "NOT_ESTABLISHED",
        "authority_effect": "NONE",
    }


def build_point(
    *,
    point_id: str,
    time_us: int,
    phase_microrad: int,
    phase_sigma_microrad: int,
    control_ratio_ppm: int,
    calibration_epoch_id: str,
) -> dict:
    _require_nonempty_string("point_id", point_id)
    _require_nonempty_string("calibration_epoch_id", calibration_epoch_id)
    time_us = _require_int("time_us", time_us)
    phase_microrad = _require_int("phase_microrad", phase_microrad)
    phase_sigma_microrad = _require_int("phase_sigma_microrad", phase_sigma_microrad)
    control_ratio_ppm = _require_int("control_ratio_ppm", control_ratio_ppm)
    if time_us < 0:
        raise ValueError("NEGATIVE_TIME")
    if phase_sigma_microrad <= 0:
        raise ValueError("NONPOSITIVE_PHASE_UNCERTAINTY")
    return {
        "point_id": point_id,
        "time_us": time_us,
        "phase_microrad": phase_microrad,
        "phase_sigma_microrad": phase_sigma_microrad,
        "control_ratio_ppm": control_ratio_ppm,
        "calibration_epoch_id": calibration_epoch_id,
    }


def _validate_point(point: dict, expected_epoch: str) -> None:
    rebuilt = build_point(
        point_id=point.get("point_id"),
        time_us=point.get("time_us"),
        phase_microrad=point.get("phase_microrad"),
        phase_sigma_microrad=point.get("phase_sigma_microrad"),
        control_ratio_ppm=point.get("control_ratio_ppm"),
        calibration_epoch_id=point.get("calibration_epoch_id"),
    )
    if rebuilt["calibration_epoch_id"] != expected_epoch:
        raise ValueError("CALIBRATION_EPOCH_MISMATCH")


def _batch_payload(batch: dict) -> dict:
    return {k: copy.deepcopy(v) for k, v in batch.items() if k != "batch_sha256"}


def build_point_batch(
    source_binding: dict,
    calibration_binding: dict,
    points: Iterable[dict],
) -> dict:
    source = copy.deepcopy(source_binding)
    calibration = copy.deepcopy(calibration_binding)
    point_list = [copy.deepcopy(p) for p in points]
    if not point_list:
        raise ValueError("EMPTY_POINT_BATCH")
    if _contains_float(source) or _contains_float(calibration) or _contains_float(point_list):
        raise ValueError("FLOAT_IN_HASHED_INGRESS_STATE")
    _require_sha256("source_sha256", source.get("source_sha256"))
    _require_sha256("config_sha256", calibration.get("config_sha256"))
    if source.get("schema") != SOURCE_BINDING_SCHEMA:
        raise ValueError("SOURCE_BINDING_SCHEMA_MISMATCH")
    if calibration.get("schema") != CALIBRATION_BINDING_SCHEMA:
        raise ValueError("CALIBRATION_BINDING_SCHEMA_MISMATCH")

    expected_epoch = _require_nonempty_string(
        "calibration_epoch_id", calibration.get("calibration_epoch_id")
    )
    seen = set()
    for point in point_list:
        _validate_point(point, expected_epoch)
        point_id = point["point_id"]
        if point_id in seen:
            raise ValueError("DUPLICATE_POINT_ID")
        seen.add(point_id)

    point_list.sort(key=lambda p: (p["time_us"], p["point_id"]))
    batch = {
        "schema": V4_INGRESS_SCHEMA,
        "source_binding": source,
        "calibration_binding": calibration,
        "point_count": len(point_list),
        "points": point_list,
        "unit_contract": {
            "time": "microsecond",
            "phase": "microradian",
            "phase_uncertainty": "microradian",
            "control_ratio": "parts_per_million",
        },
        "authority_effect": "NONE",
    }
    batch["batch_sha256"] = sha256_hex(canon(batch))
    return batch


def validate_ingress(batch: dict, source_bytes: bytes) -> dict:
    reasons = []
    if not isinstance(batch, dict):
        return {
            "decision": "DENY",
            "reason_codes": ["BATCH_NOT_OBJECT"],
            "authority_effect": "NONE",
        }
    if _contains_float(batch):
        reasons.append("FLOAT_IN_HASHED_INGRESS_STATE")

    source = batch.get("source_binding", {})
    calibration = batch.get("calibration_binding", {})
    points = batch.get("points", [])
    evidence_origin = source.get("evidence_origin", "UNKNOWN")

    try:
        if batch.get("schema") != V4_INGRESS_SCHEMA:
            reasons.append("INGRESS_SCHEMA_MISMATCH")
        source_sha = _require_sha256("source_sha256", source.get("source_sha256"))
        if not isinstance(source_bytes, bytes) or sha256_hex(source_bytes) != source_sha:
            reasons.append("SOURCE_DIGEST_MISMATCH")
        expected_epoch = _require_nonempty_string(
            "calibration_epoch_id", calibration.get("calibration_epoch_id")
        )
        _require_sha256("config_sha256", calibration.get("config_sha256"))
        seen = set()
        for point in points:
            _validate_point(point, expected_epoch)
            if point["point_id"] in seen:
                reasons.append("DUPLICATE_POINT_ID")
            seen.add(point["point_id"])
        if batch.get("point_count") != len(points):
            reasons.append("POINT_COUNT_MISMATCH")
    except (TypeError, ValueError, KeyError):
        reasons.append("STRUCTURAL_CONTRACT_VIOLATION")

    claimed_batch_sha = batch.get("batch_sha256")
    try:
        _require_sha256("batch_sha256", claimed_batch_sha)
        recomputed = sha256_hex(canon(_batch_payload(batch)))
        if claimed_batch_sha != recomputed:
            reasons.append("BATCH_DIGEST_MISMATCH")
    except (TypeError, ValueError):
        reasons.append("BATCH_DIGEST_INVALID")

    reasons = sorted(set(reasons))
    if reasons:
        return {
            "decision": "DENY",
            "evidence_origin": evidence_origin,
            "reason_codes": reasons,
            "authority_effect": "NONE",
        }
    return {
        "decision": "CONTRACT_VALID",
        "evidence_origin": evidence_origin,
        "point_count": len(points),
        "source_sha256": source["source_sha256"],
        "batch_sha256": batch["batch_sha256"],
        "reason_codes": [],
        "authority_effect": "NONE",
    }


def fit_release_gate(batch: dict, source_bytes: bytes) -> dict:
    validation = validate_ingress(batch, source_bytes)
    reasons = list(validation.get("reason_codes", []))
    source = batch.get("source_binding", {}) if isinstance(batch, dict) else {}
    calibration = batch.get("calibration_binding", {}) if isinstance(batch, dict) else {}

    if validation.get("decision") != "CONTRACT_VALID":
        reasons.append("INGRESS_CONTRACT_NOT_VALID")
    if source.get("evidence_origin") == "TEST_FIXTURE":
        reasons.append("TEST_FIXTURE_NOT_EMPIRICAL_SOURCE")
    if source.get("independent_source_verification") != "VERIFIED":
        reasons.append("INDEPENDENT_SOURCE_VERIFICATION_MISSING")
    if calibration.get("independent_calibration_verification") != "VERIFIED":
        reasons.append("INDEPENDENT_CALIBRATION_VERIFICATION_MISSING")

    reasons = sorted(set(reasons))
    if reasons:
        return {
            "decision": "BLOCKED",
            "empirical_fit_release": "BLOCKED",
            "reason_codes": reasons,
            "authority_effect": "NONE",
        }
    return {
        "decision": "ELIGIBLE_FOR_ANALYSIS_ONLY",
        "empirical_fit_release": "ELIGIBLE_FOR_ANALYSIS_ONLY",
        "claim_promotion": "BLOCKED_PENDING_MODEL_VALIDATION",
        "reason_codes": [],
        "authority_effect": "NONE",
    }


def build_contract_fixture() -> dict:
    source = build_source_binding(
        CONTRACT_FIXTURE_BYTES,
        source_uri="fixture://qgi-v4",
        media_type="text/csv",
        evidence_origin="TEST_FIXTURE",
    )
    calibration = build_calibration_binding(
        "CAL-V4-TEST",
        CONTRACT_FIXTURE_CALIBRATION_BYTES,
        valid_from="TEST_ONLY",
        valid_until="TEST_ONLY",
        calibration_origin="TEST_FIXTURE",
    )
    points = [
        build_point(
            point_id="fixture-p0",
            time_us=500,
            phase_microrad=-250000,
            phase_sigma_microrad=10000,
            control_ratio_ppm=500000,
            calibration_epoch_id="CAL-V4-TEST",
        ),
        build_point(
            point_id="fixture-p1",
            time_us=1000,
            phase_microrad=-333333,
            phase_sigma_microrad=12000,
            control_ratio_ppm=1000000,
            calibration_epoch_id="CAL-V4-TEST",
        ),
    ]
    batch = build_point_batch(source, calibration, points)
    return {
        "fixture_status": "TEST_FIXTURE_NOT_EMPIRICAL_EVIDENCE",
        "source_binding": source,
        "calibration_binding": calibration,
        "points": points,
        "batch": batch,
        "authority_effect": "NONE",
    }
