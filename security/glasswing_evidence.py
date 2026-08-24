#!/usr/bin/env python3
"""Canonical evidence-only contract for Glasswing security detectors.

Detector output is evidence, never admission authority.  This module owns the
single disposition function used by legacy Glasswing adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any, Iterable, Optional, Sequence
import json


SCHEMA_VERSION = "GLASSWING_SECURITY_EVIDENCE_V1"
EVIDENCE_AUTHORITY = "EVIDENCE_ONLY"


class SecurityDisposition(str, Enum):
    """Disposition of detector evidence within declared coverage."""

    ERROR = "ERROR"
    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    CLEAN_WITHIN_COVERAGE = "CLEAN_WITHIN_COVERAGE"


BLOCKING_SEVERITIES = frozenset({"critical", "high"})


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(domain: str, value: Any) -> str:
    payload = f"{domain}\x00{_canonical_json(value)}".encode("utf-8")
    return sha256(payload).hexdigest()


def _severity_value(finding: Any) -> str:
    severity = getattr(finding, "severity", "")
    return str(getattr(severity, "value", severity)).lower()


@dataclass(frozen=True)
class SecurityFindingEvidence:
    """Normalized, content-bound security finding."""

    finding_id: str
    vulnerability_type: str
    severity: str
    detector_id: str
    rule_id: str
    source_digest: str
    location: str
    description: str
    redacted_snippet: str
    suggested_fix: Optional[str] = None
    cwe_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        *,
        vulnerability_type: str,
        severity: str,
        detector_id: str,
        rule_id: str,
        source_digest: str,
        location: str,
        description: str,
        redacted_snippet: str,
        suggested_fix: Optional[str] = None,
        cwe_id: Optional[str] = None,
    ) -> "SecurityFindingEvidence":
        normalized_severity = severity.lower()
        identity = {
            "detector_id": detector_id,
            "rule_id": rule_id,
            "source_digest": source_digest,
            "location": location,
            "vulnerability_type": vulnerability_type,
            "severity": normalized_severity,
        }
        return cls(
            finding_id=_digest("AEGIS_GLASSWING_FINDING_V1", identity),
            vulnerability_type=vulnerability_type,
            severity=normalized_severity,
            detector_id=detector_id,
            rule_id=rule_id,
            source_digest=source_digest,
            location=location,
            description=description,
            redacted_snippet=redacted_snippet,
            suggested_fix=suggested_fix,
            cwe_id=cwe_id,
        )

    @classmethod
    def for_test(cls, severity: str = "medium") -> "SecurityFindingEvidence":
        return cls.create(
            vulnerability_type="test_finding",
            severity=severity,
            detector_id="test-detector",
            rule_id="TEST-001",
            source_digest="0" * 64,
            location="fixture.py:1",
            description="test finding",
            redacted_snippet="fixture",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "vulnerability_type": self.vulnerability_type,
            "severity": self.severity,
            "detector_id": self.detector_id,
            "rule_id": self.rule_id,
            "source_digest": self.source_digest,
            "location": self.location,
            "description": self.description,
            "redacted_snippet": self.redacted_snippet,
            "suggested_fix": self.suggested_fix,
            "cwe_id": self.cwe_id,
        }


@dataclass(frozen=True)
class SecurityEvidenceReport:
    """Replayable Glasswing result evidence; it carries no execution authority."""

    schema_version: str
    authority: str
    source_digest: str
    detector_id: str
    rulepack_digest: str
    scan_completed: bool
    coverage_satisfied: bool
    disposition: SecurityDisposition
    findings: tuple[SecurityFindingEvidence, ...]
    error_type: Optional[str]
    error_message: Optional[str]
    report_digest: str

    @property
    def allows_progress(self) -> bool:
        return self.disposition in {
            SecurityDisposition.CLEAN_WITHIN_COVERAGE,
            SecurityDisposition.REVIEW,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "authority": self.authority,
            "source_digest": self.source_digest,
            "detector_id": self.detector_id,
            "rulepack_digest": self.rulepack_digest,
            "scan_completed": self.scan_completed,
            "coverage_satisfied": self.coverage_satisfied,
            "disposition": self.disposition.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "error_type": self.error_type,
            "error_message": self.error_message,
            "report_digest": self.report_digest,
        }


def classify_disposition(
    findings: Iterable[Any],
    *,
    scan_completed: bool = True,
    coverage_satisfied: bool = True,
) -> SecurityDisposition:
    """Single fail-closed disposition function for every Glasswing adapter."""

    if not scan_completed or not coverage_satisfied:
        return SecurityDisposition.ERROR

    findings_tuple = tuple(findings)
    if any(_severity_value(finding) in BLOCKING_SEVERITIES for finding in findings_tuple):
        return SecurityDisposition.BLOCKED
    if findings_tuple:
        return SecurityDisposition.REVIEW
    return SecurityDisposition.CLEAN_WITHIN_COVERAGE


def build_security_evidence_report(
    *,
    source_digest: str,
    detector_id: str,
    rulepack_digest: str,
    findings: Sequence[SecurityFindingEvidence],
    scan_completed: bool = True,
    coverage_satisfied: bool = True,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> SecurityEvidenceReport:
    """Build a deterministic report whose digest binds detector, rules and source."""

    ordered_findings = tuple(sorted(findings, key=lambda finding: finding.finding_id))
    disposition = classify_disposition(
        ordered_findings,
        scan_completed=scan_completed,
        coverage_satisfied=coverage_satisfied,
    )
    body = {
        "schema_version": SCHEMA_VERSION,
        "authority": EVIDENCE_AUTHORITY,
        "source_digest": source_digest,
        "detector_id": detector_id,
        "rulepack_digest": rulepack_digest,
        "scan_completed": scan_completed,
        "coverage_satisfied": coverage_satisfied,
        "disposition": disposition.value,
        "findings": [finding.to_dict() for finding in ordered_findings],
        "error_type": error_type,
        "error_message": error_message,
    }
    report_digest = _digest("AEGIS_GLASSWING_REPORT_V1", body)
    return SecurityEvidenceReport(
        schema_version=SCHEMA_VERSION,
        authority=EVIDENCE_AUTHORITY,
        source_digest=source_digest,
        detector_id=detector_id,
        rulepack_digest=rulepack_digest,
        scan_completed=scan_completed,
        coverage_satisfied=coverage_satisfied,
        disposition=disposition,
        findings=ordered_findings,
        error_type=error_type,
        error_message=error_message,
        report_digest=report_digest,
    )
