#!/usr/bin/env python3
"""Executable falsifiers for GLASSWING_SECURITY_EVIDENCE_V1."""

import json
import unittest

from security.glasswing_evidence import (
    EVIDENCE_AUTHORITY,
    SecurityDisposition,
    SecurityFindingEvidence,
    build_security_evidence_report,
    classify_disposition,
)
from security.glasswing_scanner import GlasswingScanner


class GlasswingEvidenceContractTests(unittest.TestCase):
    def test_disposition_is_canonical_and_fail_closed(self):
        high = SecurityFindingEvidence.for_test(severity="high")
        medium = SecurityFindingEvidence.for_test(severity="medium")

        self.assertEqual(
            classify_disposition([high]), SecurityDisposition.BLOCKED
        )
        self.assertEqual(
            classify_disposition([medium]), SecurityDisposition.REVIEW
        )
        self.assertEqual(
            classify_disposition([]), SecurityDisposition.CLEAN_WITHIN_COVERAGE
        )
        self.assertEqual(
            classify_disposition([], scan_completed=False), SecurityDisposition.ERROR
        )
        self.assertEqual(
            classify_disposition([], coverage_satisfied=False), SecurityDisposition.ERROR
        )

    def test_secret_is_redacted_and_report_is_deterministic(self):
        source = 'password = "glasswing-super-secret"\n'
        scanner = GlasswingScanner()

        first = scanner.scan_evidence(source, "fixture.py")
        second = scanner.scan_evidence(source, "fixture.py")

        self.assertEqual(first.authority, EVIDENCE_AUTHORITY)
        self.assertEqual(first.disposition, SecurityDisposition.BLOCKED)
        self.assertEqual(first.report_digest, second.report_digest)
        self.assertEqual(
            [finding.finding_id for finding in first.findings],
            [finding.finding_id for finding in second.findings],
        )

        serialized = json.dumps(first.to_dict(), sort_keys=True)
        self.assertNotIn("glasswing-super-secret", serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_report_digest_binds_detector_rulepack_and_source(self):
        finding = SecurityFindingEvidence.for_test(severity="high")
        a = build_security_evidence_report(
            source_digest="a" * 64,
            detector_id="glasswing-regex-v1",
            rulepack_digest="b" * 64,
            findings=[finding],
        )
        b = build_security_evidence_report(
            source_digest="c" * 64,
            detector_id="glasswing-regex-v1",
            rulepack_digest="b" * 64,
            findings=[finding],
        )
        c = build_security_evidence_report(
            source_digest="a" * 64,
            detector_id="glasswing-regex-v2",
            rulepack_digest="b" * 64,
            findings=[finding],
        )

        self.assertNotEqual(a.report_digest, b.report_digest)
        self.assertNotEqual(a.report_digest, c.report_digest)

    def test_evidence_never_claims_admission_authority(self):
        report = build_security_evidence_report(
            source_digest="a" * 64,
            detector_id="glasswing-regex-v1",
            rulepack_digest="b" * 64,
            findings=[],
        )
        serialized = json.dumps(report.to_dict(), sort_keys=True)

        self.assertEqual(report.authority, "EVIDENCE_ONLY")
        self.assertNotIn("ADMISSION_AUTHORITY", serialized)
        self.assertNotIn("AUTHORITY_GRANTED", serialized)


if __name__ == "__main__":
    unittest.main()
