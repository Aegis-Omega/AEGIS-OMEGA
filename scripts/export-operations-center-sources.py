#!/usr/bin/env python3
"""Export the read-only Sources-tab projection for AEGIS Omega Labs.

Input is the verified archive coverage document. Output is intentionally small
and presentation-oriented so the UI does not need to reinterpret evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

SCHEMA = "AEGIS_OPERATIONS_CENTER_SOURCES_V1"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _load_archive_validator(root: Path):
    path = root / "harness" / "sdk" / "archive_coverage.py"
    spec = importlib.util.spec_from_file_location("aegis_archive_coverage_export", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load archive coverage validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_projection(root: Path, coverage: dict[str, Any]) -> dict[str, Any]:
    validator = _load_archive_validator(root)
    verified = validator.verify_document(coverage)
    if verified["status"] != "VERIFIED":
        raise ValueError(
            "archive coverage is not verified: "
            + ",".join(verified["reason_codes"])
        )

    projected = validator.project_for_operations_center(coverage)
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "source": {
            "archive_coverage_path": "reports/archive-coverage-v1.json",
            "archive_coverage_root": coverage["coverage_root"],
            "evidence_package_sha256": coverage["evidence_package"]["sha256"],
            "observed_main_head": projected["observed_main_head"],
            "observed_at_utc": projected["observed_at_utc"],
        },
        "cards": [
            {
                "id": "catalogued_sources",
                "label": "Katalogizirani izvori",
                "value": projected["catalogue_source_count"],
                "status": projected["catalogue_completeness"],
                "note": "Odabrani katalog; nije potpuni inventar.",
            },
            {
                "id": "archive_project_files",
                "label": "Arhivske projektne datoteke",
                "value": projected["archive_project_file_count"],
                "status": "VERIFIED_ARCHIVE_COUNT",
                "note": "Projektne datoteke u starom AEGIS arhivu.",
            },
            {
                "id": "coverage_groups",
                "label": "Grupe za dopunu",
                "value": projected["coverage_group_count"],
                "status": "VERIFIED_COVERAGE_FINDINGS",
                "note": (
                    "Identificirane grupe koje nisu potpuno surfaced "
                    "u produkcijskom katalogu."
                ),
            },
            {
                "id": "unsurfaced_no_counterpart",
                "label": "Novi kandidati bez parnjaka",
                "value": projected["unsurfaced_no_counterpart_count"],
                "status": "NO_PATH_OR_IDENTICAL_BLOB_IN_OBSERVED_MAIN_OR_OPEN_PRS",
                "note": (
                    "Bez iste putanje ili identičnog bloba u pregledanom "
                    "main/PR snapshotu."
                ),
            },
        ],
        "warnings": [
            projected["warning"],
            "SEMANTIC_REPLACEMENT_COMPLETENESS_NOT_ESTABLISHED",
        ],
        "navigation": {
            "sources_tab_default_view": "coverage",
            "show_exact_23_paths": True,
            "show_24_findings": True,
        },
        "authority_effect": "NONE",
    }
    result["projection_root"] = sha256_hex(result)
    return result


def render(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coverage",
        default="reports/archive-coverage-v1.json",
    )
    parser.add_argument(
        "--output",
        default="reports/operations-center-sources-v1.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    coverage_path = (root / args.coverage).resolve()
    output_path = (root / args.output).resolve()
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    expected = render(build_projection(root, coverage))

    if args.check:
        actual = output_path.read_text(encoding="utf-8") if output_path.is_file() else None
        if actual != expected:
            raise SystemExit("operations-center source projection is stale")
        print("OPERATIONS_CENTER_SOURCES_V1 VERIFIED")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(expected, encoding="utf-8", newline="\n")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
