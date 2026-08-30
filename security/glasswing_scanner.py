#!/usr/bin/env python3
"""
Glasswing Security Scanner - Mythos-class vulnerability detection

Scans code for security vulnerabilities before Evaluator review.
Automatically generates fixes via Claude Security harness.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import re
import hashlib


class SeverityLevel(Enum):
    """Vulnerability severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class VulnerabilityType(Enum):
    """Types of vulnerabilities detected"""
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
    """Single vulnerability finding"""
    vuln_type: VulnerabilityType
    severity: SeverityLevel
    location: str  # File:line
    description: str
    code_snippet: str
    suggested_fix: Optional[str] = None
    cwe_id: Optional[str] = None


@dataclass
class SecurityReport:
    """Complete security scan report"""
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
    """
    Mythos-class vulnerability scanner for AEGIS Sovereign Automaton.
    
    Integration Points:
    1. Pre-Generation: Scan sprint specifications
    2. Post-Generation: Code analysis before Evaluator review
    3. Continuous: Runtime integrity monitoring
    """
    
    def __init__(self):
        self.findings: List[VulnerabilityFinding] = []
        self.scan_patterns = self._load_scan_patterns()
    
    def _load_scan_patterns(self) -> Dict[VulnerabilityType, List[re.Pattern]]:
        """Load regex patterns for vulnerability detection"""
        return {
            VulnerabilityType.BUFFER_OVERFLOW: [
                re.compile(r'\bstrcpy\s*\('),
                re.compile(r'\bstrcat\s*\('),
                re.compile(r'\bsprintf\s*\('),
                re.compile(r'\bgets\s*\('),
            ],
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: [
                re.compile(r'\bMD5\b', re.IGNORECASE),
                re.compile(r'\bSHA1\b', re.IGNORECASE),
                re.compile(r'\brand\s*\(\s*\)'),
                re.compile(r'srand\s*\('),
            ],
            VulnerabilityType.MEMORY_SAFETY: [
                re.compile(r'\bfree\s*\([^)]+\)\s*;.*\bfree\s*\('),  # Double free
                re.compile(r'\bmalloc\s*\([^)]+\)[^;]*;[^}]*\bfree\b.*\buse\b'),  # Use after free
                re.compile(r'=\s*NULL\s*;.*\*'),  # Null pointer dereference
            ],
            VulnerabilityType.HARDCODED_SECRET: [
                re.compile(r'(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
                re.compile(r'(api_key|apikey|secret)\s*=\s*["\'][^"\']+["\']', re.IGNORECASE),
                re.compile(r'(token|auth)\s*=\s*["\'][A-Za-z0-9+/=]{20,}["\']'),
            ],
            VulnerabilityType.EPISTEMIC_FIREWALL_BREACH: [
                re.compile(r'D1.*mutate.*D0', re.IGNORECASE),
                re.compile(r'overlay.*write.*core', re.IGNORECASE),
                re.compile(r'semantic_overlay.*=.*axiomatic_core'),
            ],
            VulnerabilityType.GENESIS_SEAL_COMPROMISE: [
                re.compile(r'GENESIS_SEAL\s*=\s*\['),
                re.compile(r'genesis_seal\s*\.copy_from_slice'),
                re.compile(r'modify.*seal', re.IGNORECASE),
            ],
        }
    
    def scan_code(self, code: str, file_path: str = "<unknown>") -> SecurityReport:
        """
        Scan code for vulnerabilities.
        
        Args:
            code: Source code to scan
            file_path: Path for error reporting
        
        Returns:
            SecurityReport with all findings
        """
        self.findings = []
        lines = code.split('\n')
        
        for vuln_type, patterns in self.scan_patterns.items():
            for pattern in patterns:
                for line_num, line in enumerate(lines, 1):
                    if pattern.search(line):
                        finding = VulnerabilityFinding(
                            vuln_type=vuln_type,
                            severity=self._classify_severity(vuln_type),
                            location=f"{file_path}:{line_num}",
                            description=self._get_description(vuln_type),
                            code_snippet=line.strip(),
                            suggested_fix=self._generate_fix(vuln_type, line),
                            cwe_id=self._get_cwe_id(vuln_type),
                        )
                        self.findings.append(finding)
        
        # Count by severity
        critical_count = sum(1 for f in self.findings if f.severity == SeverityLevel.CRITICAL)
        high_count = sum(1 for f in self.findings if f.severity == SeverityLevel.HIGH)
        medium_count = sum(1 for f in self.findings if f.severity == SeverityLevel.MEDIUM)
        low_count = sum(1 for f in self.findings if f.severity == SeverityLevel.LOW)
        
        # Generate scan ID
        scan_id = hashlib.sha256(code.encode()).hexdigest()[:16]
        
        # Determine if scan passed (no critical or high findings)
        scan_passed = critical_count == 0 and high_count == 0
        
        return SecurityReport(
            scan_id=scan_id,
            files_scanned=1,
            total_findings=len(self.findings),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            findings=self.findings,
            scan_passed=scan_passed,
            auto_fixes_generated=sum(1 for f in self.findings if f.suggested_fix is not None),
        )
    
    def scan_file(self, file_path: str) -> SecurityReport:
        """Scan a file for vulnerabilities"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            return self.scan_code(code, file_path)
        except Exception as e:
            return SecurityReport(
                scan_id="error",
                files_scanned=0,
                total_findings=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                findings=[],
                scan_passed=False,
                auto_fixes_generated=0,
            )
    
    def _classify_severity(self, vuln_type: VulnerabilityType) -> SeverityLevel:
        """Classify vulnerability severity"""
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
    
    def _get_description(self, vuln_type: VulnerabilityType) -> str:
        """Get human-readable description"""
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
    
    def _generate_fix(self, vuln_type: VulnerabilityType, code_line: str) -> Optional[str]:
        """Generate suggested fix for vulnerability"""
        fixes = {
            VulnerabilityType.BUFFER_OVERFLOW: "Replace with safe alternative (strncpy, strncat, snprintf)",
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: "Use SHA-256 or SHA-3 for hashing, secure RNG for randomness",
            VulnerabilityType.MEMORY_SAFETY: "Ensure proper memory lifecycle management",
            VulnerabilityType.EPISTEMIC_FIREWALL_BREACH: "Remove attempted write to D0 core; use read-only access via AxiomKey",
            VulnerabilityType.HARDCODED_SECRET: "Move secret to environment variable or secure vault",
            VulnerabilityType.GENESIS_SEAL_COMPROMISE: "CRITICAL: Remove any modification attempts; Genesis Seal must remain immutable",
        }
        return fixes.get(vuln_type)
    
    def _get_cwe_id(self, vuln_type: VulnerabilityType) -> Optional[str]:
        """Get CWE ID for vulnerability type"""
        cwe_map = {
            VulnerabilityType.BUFFER_OVERFLOW: "CWE-120",
            VulnerabilityType.CRYPTOGRAPHIC_WEAKNESS: "CWE-327",
            VulnerabilityType.MEMORY_SAFETY: "CWE-416",
            VulnerabilityType.HARDCODED_SECRET: "CWE-798",
            VulnerabilityType.UNVALIDATED_INPUT: "CWE-20",
        }
        return cwe_map.get(vuln_type)


def main():
    """CLI entry point"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: glasswing_scanner.py <file_or_directory> [--json]")
        sys.exit(1)
    
    target = sys.argv[1]
    output_json = "--json" in sys.argv
    
    scanner = GlasswingScanner()
    
    # For now, scan single file
    report = scanner.scan_file(target)
    
    if output_json:
        import json
        from dataclasses import asdict
        
        # Convert enums to strings
        findings_dict = []
        for f in report.findings:
            fd = asdict(f)
            fd['vuln_type'] = f.vuln_type.value
            fd['severity'] = f.severity.value
            findings_dict.append(fd)
        
        output = asdict(report)
        output['findings'] = findings_dict
        print(json.dumps(output, indent=2))
    else:
        print(f"=== Glasswing Security Scan Report ===")
        print(f"Scan ID: {report.scan_id}")
        print(f"Files Scanned: {report.files_scanned}")
        print(f"Total Findings: {report.total_findings}")
        print(f"  Critical: {report.critical_count}")
        print(f"  High: {report.high_count}")
        print(f"  Medium: {report.medium_count}")
        print(f"  Low: {report.low_count}")
        print(f"Auto-Fixes Generated: {report.auto_fixes_generated}")
        print(f"Scan Passed: {'YES' if report.scan_passed else 'NO'}")
        print()
        
        if report.findings:
            print("=== Findings ===")
            for i, finding in enumerate(report.findings, 1):
                print(f"\n[{i}] {finding.severity.value.upper()}: {finding.vuln_type.value}")
                print(f"    Location: {finding.location}")
                print(f"    Description: {finding.description}")
                print(f"    Code: {finding.code_snippet[:80]}...")
                if finding.suggested_fix:
                    print(f"    Fix: {finding.suggested_fix}")
                if finding.cwe_id:
                    print(f"    CWE: {finding.cwe_id}")
        
        sys.exit(0 if report.scan_passed else 1)


if __name__ == "__main__":
    main()
