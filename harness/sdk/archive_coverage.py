#!/usr/bin/env python3
"""Validate and project archive-coverage evidence for repository knowledge.

The coverage document is evidence-only. It records what the archived source scan
established; it cannot grant repository, runtime, scientific, or deployment authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA = "AEGIS_ARCHIVE_COVERAGE_V1"
STATUS = "VERIFIED_EVIDENCE_PACKAGE_SNAPSHOT"
NO_AUTHORITY = "NONE"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _add(reasons: list[str], code: str) -> None:
    if code not in reasons:
        reasons.append(code)


def verify_document(document: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []

    if document.get("schema") != SCHEMA:
        _add(reasons, "ARCHIVE_COVERAGE_SCHEMA_MISMATCH")
    if document.get("status") != STATUS:
        _add(reasons, "ARCHIVE_COVERAGE_STATUS_INVALID")
    if document.get("authority_effect") != NO_AUTHORITY:
        _add(reasons, "ARCHIVE_COVERAGE_AUTHORITY_ESCALATION")
    if document.get("repository_mutations") is not False:
        _add(reasons, "ARCHIVE_COVERAGE_REPOSITORY_MUTATION_CLAIM")
    if document.get("production_mutations") is not False:
        _add(reasons, "ARCHIVE_COVERAGE_PRODUCTION_MUTATION_CLAIM")

    package = document.get("evidence_package")
    if not isinstance(package, Mapping):
        _add(reasons, "ARCHIVE_COVERAGE_EVIDENCE_PACKAGE_INVALID")
    else:
        for key in (
            "sha256",
            "verification_receipt_sha256",
            "snapshot_sha256",
            "findings_sha256",
            "production_sources_sha256",
        ):
            if not isinstance(package.get(key), str) or HEX64.fullmatch(package[key]) is None:
                _add(reasons, "ARCHIVE_COVERAGE_EVIDENCE_HASH_INVALID")

    catalogue = document.get("production_catalogue")
    if not isinstance(catalogue, Mapping):
        _add(reasons, "ARCHIVE_COVERAGE_CATALOGUE_INVALID")
    else:
        if catalogue.get("is_complete_inventory") is not False:
            _add(reasons, "ARCHIVE_COVERAGE_FALSE_COMPLETENESS")
        if catalogue.get("completeness") != "INCOMPLETE_SELECTED_SAMPLE":
            _add(reasons, "ARCHIVE_COVERAGE_COMPLETENESS_STATUS_INVALID")
        selected = catalogue.get("selected_source_count")
        verified = catalogue.get("verified_source_hash_count")
        if not isinstance(selected, int) or selected < 0 or verified != selected:
            _add(reasons, "ARCHIVE_COVERAGE_CATALOGUE_COUNT_INVALID")

    coverage = document.get("coverage")
    paths = document.get("new_uncatalogued_no_counterpart_paths")
    findings = document.get("findings")
    if not isinstance(coverage, Mapping):
        _add(reasons, "ARCHIVE_COVERAGE_COUNTS_INVALID")
    if not isinstance(paths, list) or any(not isinstance(path, str) or not path for path in paths):
        _add(reasons, "ARCHIVE_COVERAGE_PATHS_INVALID")
    elif paths != sorted(paths) or len(paths) != len(set(paths)):
        _add(reasons, "ARCHIVE_COVERAGE_PATH_ORDER_INVALID")
    if not isinstance(findings, list):
        _add(reasons, "ARCHIVE_COVERAGE_FINDINGS_INVALID")
    else:
        ids = []
        for finding in findings:
            if not isinstance(finding, Mapping):
                _add(reasons, "ARCHIVE_COVERAGE_FINDINGS_INVALID")
                continue
            ids.append(finding.get("id"))
            if finding.get("authority_effect") != NO_AUTHORITY:
                _add(reasons, "ARCHIVE_COVERAGE_FINDING_AUTHORITY_ESCALATION")
        if any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
            _add(reasons, "ARCHIVE_COVERAGE_FINDING_IDS_INVALID")

    if isinstance(coverage, Mapping) and isinstance(paths, list):
        if coverage.get("new_uncatalogued_no_counterpart_count") != len(paths):
            _add(reasons, "ARCHIVE_COVERAGE_NO_COUNTERPART_COUNT_MISMATCH")
    if isinstance(coverage, Mapping) and isinstance(findings, list):
        if coverage.get("finding_group_count") != len(findings):
            _add(reasons, "ARCHIVE_COVERAGE_FINDING_COUNT_MISMATCH")

    projection = document.get("operational_center_projection")
    if not isinstance(projection, Mapping):
        _add(reasons, "ARCHIVE_COVERAGE_PROJECTION_INVALID")
    elif isinstance(catalogue, Mapping) and isinstance(coverage, Mapping):
        if projection.get("catalogue_metric_value") != catalogue.get("selected_source_count"):
            _add(reasons, "ARCHIVE_COVERAGE_PROJECTION_CATALOGUE_MISMATCH")
        if projection.get("coverage_group_count") != coverage.get("finding_group_count"):
            _add(reasons, "ARCHIVE_COVERAGE_PROJECTION_FINDING_MISMATCH")
        if projection.get("unsurfaced_no_counterpart_count") != coverage.get(
            "new_uncatalogued_no_counterpart_count"
        ):
            _add(reasons, "ARCHIVE_COVERAGE_PROJECTION_UNSURFACED_MISMATCH")
        if projection.get("warning") != "CATALOGUE_IS_SELECTED_SAMPLE_NOT_COMPLETE_INVENTORY":
            _add(reasons, "ARCHIVE_COVERAGE_PROJECTION_WARNING_MISSING")

    supplied_root = document.get("coverage_root")
    unsigned = dict(document)
    unsigned.pop("coverage_root", None)
    if not isinstance(supplied_root, str) or HEX64.fullmatch(supplied_root) is None:
        _add(reasons, "ARCHIVE_COVERAGE_ROOT_INVALID")
    elif supplied_root != digest(unsigned):
        _add(reasons, "ARCHIVE_COVERAGE_ROOT_MISMATCH")

    return {
        "status": "DENIED" if reasons else "VERIFIED",
        "reason_codes": reasons,
    }


def project_for_operations_center(document: Mapping[str, Any]) -> dict[str, Any]:
    verification = verify_document(document)
    if verification["status"] != "VERIFIED":
        return {
            "state": "INVALID",
            "reason_codes": verification["reason_codes"],
            "authority_effect": NO_AUTHORITY,
        }

    catalogue = document["production_catalogue"]
    coverage = document["coverage"]
    archive = document["archive"]
    repo = document["repository_snapshot"]
    projection = document["operational_center_projection"]
    return {
        "state": STATUS,
        "coverage_root": document["coverage_root"],
        "observed_at_utc": document["observed_at_utc"],
        "observed_main_head": repo["main_head"],
        "open_pr_count": repo["open_pr_count"],
        "catalogue_source_count": catalogue["selected_source_count"],
        "catalogue_completeness": catalogue["completeness"],
        "archive_project_file_count": archive["project_file_count"],
        "coverage_group_count": coverage["finding_group_count"],
        "unsurfaced_no_counterpart_count": coverage["new_uncatalogued_no_counterpart_count"],
        "warning": projection["warning"],
        "authority_effect": NO_AUTHORITY,
    }


__all__ = ["project_for_operations_center", "verify_document"]
