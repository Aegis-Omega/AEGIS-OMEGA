#!/usr/bin/env python3
"""Glasswing Security Scanner - Mythos-class vulnerability detection.

This is a legacy heuristic detector. Its canonical output is
GLASSWING_SECURITY_EVIDENCE_V1 and is always EVIDENCE_ONLY; it never grants
execution or admission authority.
"""

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Dict, List, Optional
import hashlib
import json
import re

from security.glasswing_evidence import (
    SecurityDisposition,
    SecurityFindingEvidence,
    build_security_evidence_report,
    classify_disposition,
)


DETECTOR_ID = "glasswing-regex-v1"


class SeverityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(Enum):
    BUFFER_OVERFLOW = "buffer_overflow"
    CRYPTOGRAPHIC_WEAKNESS = "cryptographic_weakness"
    MEMORY_SAFETY = "memory_safety"
    EPISTEMIC_FIREWALL_BREACH = "epistemic_firewall_breach"
    UNVALIDATED_INPUT = "unvalidated_input"
    HARDCODED_SECRET = "hardcoded_secret"
    DOMAIN_ISOLATION_VIOLATION = "domain_isolation_violation"
    GENESIS_SEAL_COMPROMISE = "genesis_seal_compromise"


@dataclass
class VulnerabilityFinding:
    vuln_type: VulnerabilityType
    severity: SeverityLevel
    location: str
    description: str
    code_snippet: str
    suggested_fix: Optional[str] = None
    cwe_id: Optional[str] = None
    rule_id: Optional[str] = None


@dataclass
class SecurityReport:
    scan_id: str
    files_scanned: int
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings: List[VulnerabilityFinding]
    scan_passed: bool
    auto_fixes_generated: int


class GlasswingScanner:
    """Heuristic detector feeding the canonical evidence-only contract."""

    def __init__(self):
        self.findings: List[VulnerabilityFinding] = []
        self.scan_patterns = self._load_scan_patterns()

    def _load_scan_patterns(self) -> Dict[VulnerabilityType, List[re.Pattern]]:
        """Load Gate-204 rules plus the Gate-205 Artisan-only rules."""
        return {
            VulnerabilityType.BUFFER_OVERFLOW: [
                re.compile(r"\bstrcpy\s*\("),
                re.compile(r"\bstrcat\s*\("),
                re.compile(r"\bsprintf\s*\("),
                re.compile(r"\bgets\s*\("),
            ],
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: [
                re.compile(r"\bMD5\b", re.IGNORECASE),
                re.compile(r"\bSHA1\b", re.IGNORECASE),
                re.compile(r"\brand\s*\(\s*\)"),
                re.compile(r"\brandom\s*\(\s*\)"),
                re.compile(r"srand\s*\("),
            ],
            VulnerabilityType.MEMORY_SAFETY: [
                re.compile(r"\bfree\s*\([^)]+\)\s*;.*\bfree\s*\("),
                re.compile(r"\bmalloc\s*\([^)]+\)[^;]*;[^}]*\bfree\b.*\buse\b"),
                re.compile(r"=\s*NULL\s*;.*\*"),
                re.compile(r"\bunsafe\s*\{"),
                re.compile(r"\bas_mut_ptr\s*\("),
                re.compile(r"\bfrom_raw_parts\b"),
            ],
            VulnerabilityType.HARDCODED_SECRET: [
                re.compile(r"(password|passwd|pwd)\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE),
                re.compile(r"(api_key|apikey|secret|credential)\s*=\s*[\"'][^\"']+[\"']", re.IGNORECASE),
                re.compile(r"(token|auth)\s*=\s*[\"'][A-Za-z0-9+/=]{20,}[\"']", re.IGNORECASE),
            ],
            VulnerabilityType.EPISTEMIC_FIREWALL_BREACH: [
                re.compile(r"D1.*mutate.*D0", re.IGNORECASE),
                re.compile(r"overlay.*write.*core", re.IGNORECASE),
                re.compile(r"semantic_overlay.*=.*axiomatic_core"),
            ],
            VulnerabilityType.GENESIS_SEAL_COMPROMISE: [
                re.compile(r"GENESIS_SEAL\s*=\s*\["),
                re.compile(r"genesis_seal\s*\.copy_from_slice"),
                re.compile(r"modify.*seal", re.IGNORECASE),
            ],
        }

    @staticmethod
    def _rule_id(vuln_type: VulnerabilityType, index: int) -> str:
        return f"GLASSWING-{vuln_type.value.upper()}-{index + 1:02d}"

    def _rulepack_digest(self) -> str:
        rules = []
        for vuln_type in sorted(self.scan_patterns, key=lambda item: item.value):
            for index, pattern in enumerate(self.scan_patterns[vuln_type]):
                rules.append({
                    "vulnerability_type": vuln_type.value,
                    "rule_id": self._rule_id(vuln_type, index),
                    "pattern": pattern.pattern,
                    "flags": pattern.flags,
                    "severity": self._classify_severity(vuln_type).value,
                })
        canonical = json.dumps(rules, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def scan_code(self, code: str, file_path: str = "<unknown>") -> SecurityReport:
        self.findings = []
        lines = code.split("\n")
        for vuln_type, patterns in self.scan_patterns.items():
            for pattern_index, pattern in enumerate(patterns):
                for line_num, line in enumerate(lines, 1):
                    if pattern.search(line):
                        self.findings.append(VulnerabilityFinding(
                            vuln_type=vuln_type,
                            severity=self._classify_severity(vuln_type),
                            location=f"{file_path}:{line_num}",
                            description=self._get_description(vuln_type),
                            code_snippet=self._redact_code_snippet(vuln_type, line.strip()),
                            suggested_fix=self._generate_fix(vuln_type, line),
                            cwe_id=self._get_cwe_id(vuln_type),
                            rule_id=self._rule_id(vuln_type, pattern_index),
                        ))

        critical_count = sum(f.severity == SeverityLevel.CRITICAL for f in self.findings)
        high_count = sum(f.severity == SeverityLevel.HIGH for f in self.findings)
        medium_count = sum(f.severity == SeverityLevel.MEDIUM for f in self.findings)
        low_count = sum(f.severity == SeverityLevel.LOW for f in self.findings)
        disposition = classify_disposition(self.findings)

        return SecurityReport(
            scan_id=hashlib.sha256(code.encode("utf-8")).hexdigest()[:16],
            files_scanned=1,
            total_findings=len(self.findings),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            findings=list(self.findings),
            scan_passed=disposition in {
                SecurityDisposition.CLEAN_WITHIN_COVERAGE,
                SecurityDisposition.REVIEW,
            },
            auto_fixes_generated=sum(f.suggested_fix is not None for f in self.findings),
        )

    def scan_evidence(self, code: str, file_path: str = "<unknown>"):
        legacy_report = self.scan_code(code, file_path)
        source_digest = hashlib.sha256(code.encode("utf-8")).hexdigest()
        normalized = [
            SecurityFindingEvidence.create(
                vulnerability_type=finding.vuln_type.value,
                severity=finding.severity.value,
                detector_id=DETECTOR_ID,
                rule_id=finding.rule_id or "GLASSWING-LEGACY-UNKNOWN",
                source_digest=source_digest,
                location=finding.location,
                description=finding.description,
                redacted_snippet=finding.code_snippet,
                suggested_fix=finding.suggested_fix,
                cwe_id=finding.cwe_id,
            )
            for finding in legacy_report.findings
        ]
        return build_security_evidence_report(
            source_digest=source_digest,
            detector_id=DETECTOR_ID,
            rulepack_digest=self._rulepack_digest(),
            findings=normalized,
        )

    def scan_file(self, file_path: str) -> SecurityReport:
        try:
            with open(file_path, "r", encoding="utf-8") as source_file:
                return self.scan_code(source_file.read(), file_path)
        except (OSError, UnicodeError):
            return SecurityReport(
                scan_id="error", files_scanned=0, total_findings=0,
                critical_count=0, high_count=0, medium_count=0, low_count=0,
                findings=[], scan_passed=False, auto_fixes_generated=0,
            )

    def scan_file_evidence(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as source_file:
                return self.scan_evidence(source_file.read(), file_path)
        except (OSError, UnicodeError) as exc:
            return build_security_evidence_report(
                source_digest=hashlib.sha256(file_path.encode("utf-8")).hexdigest(),
                detector_id=DETECTOR_ID,
                rulepack_digest=self._rulepack_digest(),
                findings=[],
                scan_completed=False,
                coverage_satisfied=False,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    @staticmethod
    def _redact_code_snippet(vuln_type: VulnerabilityType, line: str) -> str:
        if vuln_type != VulnerabilityType.HARDCODED_SECRET:
            return line
        assignment = re.compile(
            r"\b(password|passwd|pwd|api_key|apikey|secret|credential|token|auth)"
            r"(\s*=\s*)([\"'])([^\"']*)([\"'])",
            re.IGNORECASE,
        )
        return assignment.sub(
            lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}[REDACTED]{m.group(5)}",
            line,
        )

    def _classify_severity(self, vuln_type: VulnerabilityType) -> SeverityLevel:
        severity_map = {
            VulnerabilityType.BUFFER_OVERFLOW: SeverityLevel.HIGH,
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: SeverityLevel.CRITICAL,
            VulnerabilityType.MEMORY_SAFETY: SeverityLevel.HIGH,
            VulnerabilityType.EPISTEMIC_FIREWALL_BREACH: SeverityLevel.CRITICAL,
            VulnerabilityType.UNVALIDATED_INPUT: SeverityLevel.MEDIUM,
            VulnerabilityType.HARDCODED_SECRET: SeverityLevel.CRITICAL,
            VulnerabilityType.DOMAIN_ISOLATION_VIOLATION: SeverityLevel.HIGH,
            VulnerabilityType.GENESIS_SEAL_COMPROMISE: SeverityLevel.CRITICAL,
        }
        return severity_map.get(vuln_type, SeverityLevel.MEDIUM)

    @staticmethod
    def _get_description(vuln_type: VulnerabilityType) -> str:
        descriptions = {
            VulnerabilityType.BUFFER_OVERFLOW: "Potential buffer overflow via unsafe string function",
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: "Use of weak or deprecated cryptographic primitive",
            VulnerabilityType.MEMORY_SAFETY: "Memory safety violation detected",
            VulnerabilityType.EPISTEMIC_FIREWALL_BREACH: "Attempted mutation of D0 axiomatic core from D1 overlay",
            VulnerabilityType.UNVALIDATED_INPUT: "Unvalidated external input",
            VulnerabilityType.HARDCODED_SECRET: "Hardcoded credential or secret detected",
            VulnerabilityType.DOMAIN_ISOLATION_VIOLATION: "Domain isolation boundary violation",
            VulnerabilityType.GENESIS_SEAL_COMPROMISE: "Attempted modification of Genesis Seal",
        }
        return descriptions.get(vuln_type, "Unknown vulnerability type")

    @staticmethod
    def _generate_fix(vuln_type: VulnerabilityType, code_line: str) -> Optional[str]:
        del code_line
        fixes = {
            VulnerabilityType.BUFFER_OVERFLOW: "Replace with bounded string operations and verify destination bounds",
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: "Use an approved modern primitive and a cryptographically secure RNG where security-sensitive",
            VulnerabilityType.MEMORY_SAFETY: "Review and prove the unsafe memory lifecycle invariants",
            VulnerabilityType.EPISTEMIC_FIREWALL_BREACH: "Remove attempted write to D0 core; use read-only access via AxiomKey",
            VulnerabilityType.HARDCODED_SECRET: "Move secret to environment variable or secure vault",
            VulnerabilityType.GENESIS_SEAL_COMPROMISE: "Remove mutation attempt; Genesis Seal is immutable",
        }
        return fixes.get(vuln_type)

    @staticmethod
    def _get_cwe_id(vuln_type: VulnerabilityType) -> Optional[str]:
        cwe_map = {
            VulnerabilityType.BUFFER_OVERFLOW: "CWE-120",
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: "CWE-327",
            VulnerabilityType.MEMORY_SAFETY: "CWE-416",
            VulnerabilityType.HARDCODED_SECRET: "CWE-798",
            VulnerabilityType.UNVALIDATED_INPUT: "CWE-20",
        }
        return cwe_map.get(vuln_type)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: glasswing_scanner.py <file> [--json]")
        sys.exit(1)

    target = sys.argv[1]
    output_json = "--json" in sys.argv
    scanner = GlasswingScanner()
    report = scanner.scan_file(target)

    if output_json:
        findings_dict = []
        for finding in report.findings:
            finding_dict = asdict(finding)
            finding_dict["vuln_type"] = finding.vuln_type.value
            finding_dict["severity"] = finding.severity.value
            findings_dict.append(finding_dict)
        output = asdict(report)
        output["findings"] = findings_dict
        print(json.dumps(output, indent=2))
    else:
        print("=== Glasswing Security Scan Report ===")
        print(f"Scan ID: {report.scan_id}")
        print(f"Files Scanned: {report.files_scanned}")
        print(f"Total Findings: {report.total_findings}")
        print(f"  Critical: {report.critical_count}")
        print(f"  High: {report.high_count}")
        print(f"  Medium: {report.medium_count}")
        print(f"  Low: {report.low_count}")
        print(f"Remediation Hints: {report.auto_fixes_generated}")
        print(f"Scan Passed: {'YES' if report.scan_passed else 'NO'}")
        if report.findings:
            print("\n=== Findings ===")
            for index, finding in enumerate(report.findings, 1):
                print(f"\n[{index}] {finding.severity.value.upper()}: {finding.vuln_type.value}")
                print(f"    Location: {finding.location}")
                print(f"    Description: {finding.description}")
                print(f"    Code: {finding.code_snippet[:80]}...")
                if finding.suggested_fix:
                    print(f"    Fix: {finding.suggested_fix}")
                if finding.cwe_id:
                    print(f"    CWE: {finding.cwe_id}")
                if finding.rule_id:
                    print(f"    Rule: {finding.rule_id}")

    sys.exit(0 if report.scan_passed else 1)


if __name__ == "__main__":
    main()
