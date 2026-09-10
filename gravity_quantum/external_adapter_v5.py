#!/usr/bin/env python3
"""Strict CSV-to-V4 adapter for externally supplied QGI point-level datasets.

The adapter performs syntax, unit and content binding only. It never authenticates a source
and never upgrades evidence authority. Even an EXTERNAL_EXPERIMENTAL_SOURCE candidate remains
blocked until V4 exact verification-receipt digests are repository-enrolled.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from gravity_quantum.ingress_v4 import (
    build_calibration_binding,
    build_point,
    build_point_batch,
    build_source_binding,
    fit_release_gate,
)

V5_ADAPTER_SCHEMA = "AEGIS_QGI_EXTERNAL_DATASET_ADAPTER_V5"
EXPECTED_COLUMNS = [
    "point_id",
    "time_us",
    "phase_microrad",
    "phase_sigma_microrad",
    "control_ratio_ppm",
    "calibration_epoch_id",
]
INTEGER_RE = re.compile(r"^-?[0-9]+$")
CONTRACT_CALIBRATION_BYTES = b"QGI_V5_CONTRACT_CALIBRATION_CONFIG\n"
CONTRACT_CSV_BYTES = (
    b"point_id,time_us,phase_microrad,phase_sigma_microrad,control_ratio_ppm,calibration_epoch_id\n"
    b"fixture-p0,500,-250000,10000,500000,CAL-V5-TEST\n"
    b"fixture-p1,1000,-333333,12000,1000000,CAL-V5-TEST\n"
)


def _parse_int(field: str, value: Any) -> int:
    if not isinstance(value, str) or not INTEGER_RE.fullmatch(value):
        raise ValueError(f"NON_INTEGER_CSV_VALUE:{field}")
    return int(value, 10)


def parse_point_csv(source_bytes: bytes) -> list[dict]:
    if not isinstance(source_bytes, bytes) or not source_bytes:
        raise ValueError("EMPTY_OR_NONBYTE_CSV_SOURCE")
    try:
        text = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV_NOT_UTF8") from exc
    if "\x00" in text:
        raise ValueError("CSV_NUL_BYTE")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != EXPECTED_COLUMNS:
        raise ValueError("CSV_HEADER_CONTRACT_MISMATCH")

    points = []
    for row_number, row in enumerate(reader, start=2):
        if None in row or any(row.get(col) in (None, "") for col in EXPECTED_COLUMNS):
            raise ValueError(f"CSV_ROW_SHAPE_MISMATCH:{row_number}")
        point = build_point(
            point_id=row["point_id"],
            time_us=_parse_int("time_us", row["time_us"]),
            phase_microrad=_parse_int("phase_microrad", row["phase_microrad"]),
            phase_sigma_microrad=_parse_int(
                "phase_sigma_microrad", row["phase_sigma_microrad"]
            ),
            control_ratio_ppm=_parse_int("control_ratio_ppm", row["control_ratio_ppm"]),
            calibration_epoch_id=row["calibration_epoch_id"],
        )
        points.append(point)

    if not points:
        raise ValueError("CSV_CONTAINS_NO_POINTS")
    return points


def build_dataset_candidate(
    source_bytes: bytes,
    *,
    evidence_origin: str,
    source_uri: str = "fixture://qgi-v5-contract",
    calibration_config_bytes: bytes = CONTRACT_CALIBRATION_BYTES,
    calibration_epoch_id: str = "CAL-V5-TEST",
    calibration_valid_from: str = "UNVERIFIED",
    calibration_valid_until: str = "UNVERIFIED",
) -> dict:
    points = parse_point_csv(source_bytes)
    source = build_source_binding(
        source_bytes,
        source_uri=source_uri,
        media_type="text/csv",
        evidence_origin=evidence_origin,
    )
    calibration = build_calibration_binding(
        calibration_epoch_id,
        calibration_config_bytes,
        valid_from=calibration_valid_from,
        valid_until=calibration_valid_until,
        calibration_origin=(
            "TEST_FIXTURE" if evidence_origin == "TEST_FIXTURE" else "CALLER_SUPPLIED_UNVERIFIED"
        ),
    )
    batch = build_point_batch(source, calibration, points)
    gate = fit_release_gate(batch, source_bytes)
    return {
        "schema": V5_ADAPTER_SCHEMA,
        "adapter_status": "CANDIDATE_ONLY",
        "evidence_origin": evidence_origin,
        "point_count": len(points),
        "batch": batch,
        "release_gate": gate,
        "non_equivalence": "PARSE_AND_CONTENT_BINDING_IS_NOT_SOURCE_AUTHENTICATION",
        "authority_effect": "NONE",
    }
