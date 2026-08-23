#!/usr/bin/env python3
"""Executable falsifiers for SECURITY_EVIDENCE_SET_V1."""

import json
import unittest

from security.glasswing_scanner import GlasswingScanner
from security.security_evidence_set import (
    EVIDENCE_AUTHORITY,
    SecurityDisposition,
    SecurityEvidenceReference,
    build_security_evidence_set,
    glasswing_reference,
    verify_security_evidence_set,
)


class SecurityEvidenceSetTests(unittest.TestCase):
    def _reference(
        self,
        *,
        evidence_kind: str,
        evidence_digest: str,
        disposition: SecurityDisposition = SecurityDisposition.CLEAN_WITHIN_COVERAGE,
        independence: str = "INDEPENDENT_CHECK",
    ) -> SecurityEvidenceReference:
        return SecurityEvidenceReference.create(
            evidence_kind=evidence_kind,
            producer_id=f"{evidence_kind.lower()}-fixture",
            subject_digest="a" * 64,
            evidence_digest=evidence_digest,
            disposition=disposition,
            authority=EVIDENCE_AUTHORITY,
            independence=independence,
            metadata_digest="b" * 64,
        )

    def test_set_digest_is_order_independent_and_member_bound(self):
        glasswing = self._reference(
            evidence_kind="GLASSWING",
            evidence_digest="1" * 64,
        )
        osv = self._reference(
            evidence_kind="OSV",
            evidence_digest="2" * 64,
        )

        first = build_security_evidence_set(
            subject_root="c" * 64,
            members=[glasswing, osv],
            required_kinds=["GLASSWING", "OSV"],
        )
        second = build_security_evidence_set(
            subject_root="c" * 64,
            members=[osv, glasswing],
            required_kinds=["OSV", "GLASSWING"],
        )
        changed = build_security_evidence_set(
            subject_root="c" * 64,
            members=[
                glasswing,
                self._reference(
                    evidence_kind="OSV",
                    evidence_digest="3" * 64,
                ),
            ],
            required_kinds=["GLASSWING", "OSV"],
        )

        self.assertEqual(first.set_digest, second.set_digest)
        self.assertNotEqual(first.set_digest, changed.set_digest)

    def test_offline_verifier_detects_member_tampering(self):
        evidence_set = build_security_evidence_set(
            subject_root="c" * 64,
            members=[
                self._reference(
                    evidence_kind="GLASSWING",
                    evidence_digest="1" * 64,
                )
            ],
            required_kinds=["GLASSWING"],
        )
        payload = evidence_set.to_dict()
        payload["members"][0]["evidence_digest"] = "9" * 64

        receipt = verify_security_evidence_set(payload)

        self.assertFalse(receipt.integrity_valid)
        self.assertIn("MEMBER_ID_MISMATCH", receipt.reasons)
        self.assertEqual(receipt.authority, EVIDENCE_AUTHORITY)

    def test_valid_integrity_does_not_launder_blocking_evidence(self):
        blocked = self._reference(
            evidence_kind="GLASSWING",
            evidence_digest="1" * 64,
            disposition=SecurityDisposition.BLOCKED,
            independence="PRE_SCAN",
        )
        evidence_set = build_security_evidence_set(
            subject_root="c" * 64,
            members=[blocked],
            required_kinds=["GLASSWING"],
        )

        receipt = verify_security_evidence_set(evidence_set.to_dict())

        self.assertTrue(receipt.integrity_valid)
        self.assertTrue(receipt.complete)
        self.assertEqual(receipt.aggregate_disposition, SecurityDisposition.BLOCKED)
        self.assertEqual(receipt.authority, EVIDENCE_AUTHORITY)
        self.assertNotIn("ADMISSION_AUTHORITY", json.dumps(receipt.to_dict()))

    def test_missing_required_kind_is_incomplete_and_fail_closed(self):
        glasswing = self._reference(
            evidence_kind="GLASSWING",
            evidence_digest="1" * 64,
            independence="PRE_SCAN",
        )
        evidence_set = build_security_evidence_set(
            subject_root="c" * 64,
            members=[glasswing],
            required_kinds=["GLASSWING", "OSV"],
        )

        receipt = verify_security_evidence_set(evidence_set.to_dict())

        self.assertTrue(receipt.integrity_valid)
        self.assertFalse(receipt.complete)
        self.assertEqual(receipt.aggregate_disposition, SecurityDisposition.ERROR)
        self.assertIn("MISSING_REQUIRED_KIND:OSV", receipt.reasons)

    def test_glasswing_adapter_binds_report_without_copying_raw_findings(self):
        source = 'password = "security-set-secret"\n'
        report = GlasswingScanner().scan_evidence(source, "fixture.py")

        reference = glasswing_reference(report, independence="PRE_SCAN")
        evidence_set = build_security_evidence_set(
            subject_root="c" * 64,
            members=[reference],
            required_kinds=["GLASSWING"],
        )
        serialized = json.dumps(evidence_set.to_dict(), sort_keys=True)

        self.assertEqual(reference.evidence_digest, report.report_digest)
        self.assertEqual(reference.authority, EVIDENCE_AUTHORITY)
        self.assertNotIn("security-set-secret", serialized)
        self.assertNotIn("findings", serialized)

    def test_non_evidence_authority_is_rejected(self):
        reference = self._reference(
            evidence_kind="OSV",
            evidence_digest="2" * 64,
        )
        evidence_set = build_security_evidence_set(
            subject_root="c" * 64,
            members=[reference],
            required_kinds=["OSV"],
        )
        payload = evidence_set.to_dict()
        payload["members"][0]["authority"] = "ADMISSION_AUTHORITY"

        receipt = verify_security_evidence_set(payload)

        self.assertFalse(receipt.integrity_valid)
        self.assertIn("NON_EVIDENCE_AUTHORITY", receipt.reasons)


if __name__ == "__main__":
    unittest.main()
