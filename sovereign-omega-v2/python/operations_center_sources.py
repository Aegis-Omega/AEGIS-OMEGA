#!/usr/bin/env python3
"""Read-only loader for the AEGIS Operations Center Sources projection.

The runtime image ships this module and its adjacent generated JSON mirror.
No network access, repository mutation, admission, or authority grant occurs here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "AEGIS_OPERATIONS_CENTER_SOURCES_V1"
NO_AUTHORITY = "NONE"
DATA_PATH = Path(__file__).with_name("operations_center_sources_v1.json")


class OperationsCenterSourcesError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def projection_root(value: dict[str, Any]) -> str:
    body = dict(value)
    body.pop("projection_root", None)
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OperationsCenterSourcesError("SOURCES_PROJECTION_NOT_OBJECT")
    if value.get("schema") != SCHEMA:
        raise OperationsCenterSourcesError("SOURCES_SCHEMA_MISMATCH")
    if value.get("authority_effect") != NO_AUTHORITY:
        raise OperationsCenterSourcesError("SOURCES_AUTHORITY_ESCALATION")

    supplied_root = value.get("projection_root")
    if not isinstance(supplied_root, str) or len(supplied_root) != 64:
        raise OperationsCenterSourcesError("SOURCES_PROJECTION_ROOT_INVALID")
    if supplied_root != projection_root(value):
        raise OperationsCenterSourcesError("SOURCES_PROJECTION_ROOT_MISMATCH")

    cards = value.get("cards")
    if not isinstance(cards, list):
        raise OperationsCenterSourcesError("SOURCES_CARDS_INVALID")
    expected_ids = (
        "catalogued_sources",
        "archive_project_files",
        "coverage_groups",
        "unsurfaced_no_counterpart",
    )
    got_ids = tuple(
        card.get("id") for card in cards if isinstance(card, dict)
    )
    if got_ids != expected_ids:
        raise OperationsCenterSourcesError("SOURCES_CARD_SET_MISMATCH")
    expected_values = (38, 1163, 24, 23)
    got_values = tuple(card.get("value") for card in cards)
    if got_values != expected_values:
        raise OperationsCenterSourcesError("SOURCES_CARD_VALUE_MISMATCH")

    findings = value.get("findings")
    paths = value.get("unsurfaced_paths")
    if not isinstance(findings, list) or len(findings) != 24:
        raise OperationsCenterSourcesError("SOURCES_FINDINGS_MISMATCH")
    if not isinstance(paths, list) or len(paths) != 23:
        raise OperationsCenterSourcesError("SOURCES_UNSURFACED_PATHS_MISMATCH")

    consumer = value.get("consumer_contract")
    if not isinstance(consumer, dict):
        raise OperationsCenterSourcesError("SOURCES_CONSUMER_CONTRACT_MISSING")
    if consumer.get("legacy_label_to_replace") != "38 arhiva + Git":
        raise OperationsCenterSourcesError("SOURCES_LEGACY_LABEL_CONTRACT_MISMATCH")
    if consumer.get("invalid_source_behavior") != (
        "SHOW_INVALID_OR_STALE; DO_NOT_FALL_BACK_TO_COMPLETE_INVENTORY_CLAIM"
    ):
        raise OperationsCenterSourcesError("SOURCES_FAIL_CLOSED_CONTRACT_MISMATCH")

    return value


def load_operations_center_sources(path: Path | None = None) -> dict[str, Any]:
    source = path or DATA_PATH
    try:
        raw = source.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise OperationsCenterSourcesError(
            f"SOURCES_PROJECTION_UNAVAILABLE:{type(exc).__name__}"
        ) from exc
    return validate_projection(payload)


def response_payload() -> tuple[int, dict[str, Any]]:
    """Return an HTTP-ready read-only response without raising into the bridge."""
    try:
        payload = load_operations_center_sources()
    except OperationsCenterSourcesError as exc:
        return 503, {
            "schema": SCHEMA,
            "state": "INVALID_OR_STALE",
            "error_code": str(exc).split(":", 1)[0],
            "authority_effect": NO_AUTHORITY,
        }
    return 200, payload


__all__ = [
    "OperationsCenterSourcesError",
    "load_operations_center_sources",
    "projection_root",
    "response_payload",
    "validate_projection",
]
