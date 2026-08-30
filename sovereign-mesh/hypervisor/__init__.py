"""
GATE 206: Constitutional Hypervisor

Server-managed settings enforcement layer that prevents agent drift
and ensures mesh nodes cannot bypass constitutional constraints.

This module enforces hard runtime boundaries that cannot be overridden
by soft prompts or conversational pressure.
"""

import json
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum


class EnforcementLevel(Enum):
    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class ViolationType(Enum):
    TOOL_BYPASS = "tool_bypass"
    CONSTRAINT_VIOLATION = "constraint_violation"
    DOMAIN_BREACH = "domain_breach"
    SYCOPHANCY_DETECTED = "sycophancy_detected"
    HALLUCINATION_RISK = "hallucination_risk"
    INSTRUMENTAL_CONVERGENCE = "instrumental_convergence"


@dataclass
class ViolationRecord:
    violation_type: ViolationType
    severity: int
    description: str
    node_id: str
    timestamp: float
    blocked: bool = True
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstitutionalConstraints:
    truth_over_flow: bool = True
    mechanism_over_metaphor: bool = True
    feasibility_as_constraint: bool = True
    adversarial_self_correction: bool = True
    epistemic_horizon_recognition: bool = True


@dataclass
class ExecutionPacing:
    deliberate_mode: bool = True
    max_tokens_per_step: int = 500
    require_causal_validation: bool = True
    halt_on_uncertainty: bool = True


@dataclass
class DomainSeparation:
    domain_0_readonly: bool = True
    domain_1_sandboxed: bool = True
    opaque_key_required: bool = True


@dataclass
class UtilityFunction:
    primary_objective: str = "steward_upliftment"
    penalize_instrumental_convergence: bool = True
    penalize_self_preservation_override: bool = True
    penalize_sycophancy: bool = True


class ConstitutionalHypervisor:
    """
    Server-managed hypervisor that enforces constitutional constraints
    across all sovereign mesh nodes. Prevents agent drift and ensures
    compliance with the Sovereign Protocol.
    """
    
    def __init__(self, settings_path: str):
        self.settings_path = Path(settings_path)
        self.settings_hash: Optional[str] = None
        self.violations: List[ViolationRecord] = []
        self.allowed_tools: Set[str] = set()
        self.blocked_tools: Set[str] = set()
        self.constraints: Optional[ConstitutionalConstraints] = None
        self.pacing: Optional[ExecutionPacing] = None
        self.domain_sep: Optional[DomainSeparation] = None
        self.utility: Optional[UtilityFunction] = None
        
        self._load_settings()
        self._verify_integrity()
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of settings content."""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _load_settings(self):
        """Load and parse managed settings from JSON file."""
        if not self.settings_path.exists():
            raise FileNotFoundError(f"Managed settings not found: {self.settings_path}")
        
        with open(self.settings_path, 'r') as f:
            content = f.read()
            self.settings_hash = self._compute_hash(content)
            settings = json.loads(content)
        
        # Parse allowed/blocked tools
        self.allowed_tools = set(settings.get('allowedTools', []))
        self.blocked_tools = set(settings.get('blockedTools', []))
        
        # Parse constitutional constraints
        cc = settings.get('constitutional_constraints', {})
        self.constraints = ConstitutionalConstraints(
            truth_over_flow=cc.get('truth_over_flow', True),
            mechanism_over_metaphor=cc.get('mechanism_over_metaphor', True),
            feasibility_as_constraint=cc.get('feasibility_as_constraint', True),
            adversarial_self_correction=cc.get('adversarial_self_correction', True),
            epistemic_horizon_recognition=cc.get('epistemic_horizon_recognition', True)
        )
        
        # Parse execution pacing
        ep = settings.get('execution_pacing', {})
        self.pacing = ExecutionPacing(
            deliberate_mode=ep.get('deliberate_mode', True),
            max_tokens_per_step=ep.get('max_tokens_per_step', 500),
            require_causal_validation=ep.get('require_causal_validation', True),
            halt_on_uncertainty=ep.get('halt_on_uncertainty', True)
        )
        
        # Parse domain separation
        ds = settings.get('domain_separation', {})
        self.domain_sep = DomainSeparation(
            domain_0_readonly=ds.get('domain_0_readonly', True),
            domain_1_sandboxed=ds.get('domain_1_sandboxed', True),
            opaque_key_required=ds.get('opaque_key_required', True)
        )
        
        # Parse utility function
        uf = settings.get('utility_function', {})
        self.utility = UtilityFunction(
            primary_objective=uf.get('primary_objective', 'steward_upliftment'),
            penalize_instrumental_convergence=uf.get('penalize_instrumental_convergence', True),
            penalize_self_preservation_override=uf.get('penalize_self_preservation_override', True),
            penalize_sycophancy=uf.get('penalize_sycophancy', True)
        )
    
    def _verify_integrity(self):
        """Verify settings file has not been tampered with."""
        with open(self.settings_path, 'r') as f:
            current_content = f.read()
        
        current_hash = self._compute_hash(current_content)
        if current_hash != self.settings_hash:
            raise SecurityError(
                f"Settings integrity violation! Hash mismatch. "
                f"Expected: {self.settings_hash}, Got: {current_hash}"
            )
    
    def validate_tool_access(self, tool_name: str, node_id: str) -> bool:
        """
        Validate if a mesh node can access a specific tool.
        Returns True if allowed, False if blocked.
        """
        if tool_name in self.blocked_tools:
            self._record_violation(
                ViolationType.TOOL_BYPASS,
                severity=9,
                node_id=node_id,
                description=f"Attempted access to blocked tool: {tool_name}",
                context={"tool": tool_name}
            )
            return False
        
        if tool_name not in self.allowed_tools:
            self._record_violation(
                ViolationType.TOOL_BYPASS,
                severity=7,
                node_id=node_id,
                description=f"Attempted access to unlisted tool: {tool_name}",
                context={"tool": tool_name}
            )
            return False
        
        return True
    
    def check_constraint_compliance(
        self, 
        constraint_name: str, 
        node_id: str,
        context: Optional[Dict] = None
    ) -> bool:
        """
        Check if an action complies with constitutional constraints.
        """
        if self.constraints is None:
            return False
        
        constraint_value = getattr(self.constraints, constraint_name, None)
        if constraint_value is None:
            return False
        
        if not constraint_value:
            self._record_violation(
                ViolationType.CONSTRAINT_VIOLATION,
                severity=8,
                node_id=node_id,
                description=f"Constraint '{constraint_name}' is disabled",
                context=context or {}
            )
            return False
        
        return True
    
    def enforce_deliberate_pacing(self, token_count: int, node_id: str) -> bool:
        """
        Enforce deliberate execution pacing limits.
        Returns True if within limits, False if exceeded.
        """
        if self.pacing is None or not self.pacing.deliberate_mode:
            return True
        
        if token_count > self.pacing.max_tokens_per_step:
            self._record_violation(
                ViolationType.HALLUCINATION_RISK,
                severity=6,
                node_id=node_id,
                description=f"Token count {token_count} exceeds limit {self.pacing.max_tokens_per_step}",
                context={"token_count": token_count, "limit": self.pacing.max_tokens_per_step}
            )
            return False
        
        return True
    
    def validate_domain_access(
        self, 
        domain: int, 
        operation: str, 
        node_id: str
    ) -> bool:
        """
        Validate domain access according to separation rules.
        Domain 0: Read-only (axiomatic core)
        Domain 1: Sandboxed (semantic overlay)
        """
        if self.domain_sep is None:
            return False
        
        if domain == 0:
            if self.domain_sep.domain_0_readonly and operation != "read":
                self._record_violation(
                    ViolationType.DOMAIN_BREACH,
                    severity=10,
                    node_id=node_id,
                    description=f"Write attempt to Domain 0 (readonly)",
                    context={"domain": domain, "operation": operation}
                )
                return False
        
        if domain == 1:
            if not self.domain_sep.domain_1_sandboxed:
                self._record_violation(
                    ViolationType.DOMAIN_BREACH,
                    severity=8,
                    node_id=node_id,
                    description="Domain 1 sandbox not enforced",
                    context={"domain": domain, "operation": operation}
                )
                return False
        
        return True
    
    def detect_sycophancy_patterns(self, output_metrics: Dict[str, float]) -> bool:
        """
        Detect potential sycophancy patterns in output metrics.
        Returns True if suspicious patterns detected.
        """
        if self.utility is None or not self.utility.penalize_sycophancy:
            return False
        
        # High agreement score + low uncertainty = potential sycophancy
        agreement_score = output_metrics.get('agreement_with_user', 0.0)
        uncertainty = output_metrics.get('uncertainty', 1.0)
        
        if agreement_score > 0.95 and uncertainty < 0.1:
            self._record_violation(
                ViolationType.SYCOPHANCY_DETECTED,
                severity=7,
                node_id="evaluator",
                description="High agreement + low uncertainty pattern detected",
                context=output_metrics
            )
            return True
        
        return False
    
    def check_instrumental_convergence(self, action_sequence: List[str]) -> bool:
        """
        Detect instrumental convergence behaviors (self-preservation,
        resource hoarding, etc.).
        Returns True if suspicious patterns detected.
        """
        if self.utility is None:
            return False
        
        convergence_indicators = [
            "self_preserve",
            "resource_hoard",
            "disable_off_switch",
            "replicate_unauthorized",
            "hide_intentions"
        ]
        
        for action in action_sequence:
            if any(indicator in action.lower() for indicator in convergence_indicators):
                self._record_violation(
                    ViolationType.INSTRUMENTAL_CONVERGENCE,
                    severity=10,
                    node_id="planner",
                    description=f"Instrumental convergence detected: {action}",
                    context={"action": action}
                )
                return True
        
        return False
    
    def _record_violation(
        self,
        violation_type: ViolationType,
        severity: int,
        node_id: str,
        description: str,
        context: Optional[Dict] = None,
        blocked: bool = True
    ):
        """Record a constitutional violation."""
        import time
        record = ViolationRecord(
            violation_type=violation_type,
            severity=severity,
            description=description,
            node_id=node_id,
            timestamp=time.time(),
            blocked=blocked,
            context=context or {}
        )
        self.violations.append(record)
    
    def get_violation_report(self) -> Dict[str, Any]:
        """Generate a report of all recorded violations."""
        return {
            "total_violations": len(self.violations),
            "violations_by_type": {
                vt.value: sum(1 for v in self.violations if v.violation_type == vt)
                for vt in ViolationType
            },
            "recent_violations": [
                {
                    "type": v.violation_type.value,
                    "severity": v.severity,
                    "node": v.node_id,
                    "description": v.description,
                    "blocked": v.blocked
                }
                for v in self.violations[-10:]
            ],
            "settings_hash": self.settings_hash
        }
    
    def reset_violations(self):
        """Clear violation history (requires re-verification)."""
        self.violations = []
        self._verify_integrity()


class SecurityError(Exception):
    """Raised when a security boundary is violated."""
    pass


# Convenience function for creating hypervisor instances
def create_hypervisor(settings_path: str = "sovereign-mesh/hypervisor/managed_settings.json") -> ConstitutionalHypervisor:
    """Create a new hypervisor instance with default settings path."""
    return ConstitutionalHypervisor(settings_path)


if __name__ == "__main__":
    # Test the hypervisor
    hypervisor = create_hypervisor()
    
    print("=== Constitutional Hypervisor Test ===\n")
    
    # Test tool validation
    print("Tool Access Tests:")
    print(f"  filesystem_read: {hypervisor.validate_tool_access('filesystem_read', 'test_node')}")
    print(f"  network_unrestricted: {hypervisor.validate_tool_access('network_unrestricted', 'test_node')}")
    print(f"  unknown_tool: {hypervisor.validate_tool_access('unknown_tool', 'test_node')}")
    
    # Test constraint compliance
    print("\nConstraint Compliance Tests:")
    print(f"  truth_over_flow: {hypervisor.check_constraint_compliance('truth_over_flow', 'test_node')}")
    print(f"  mechanism_over_metaphor: {hypervisor.check_constraint_compliance('mechanism_over_metaphor', 'test_node')}")
    
    # Test pacing
    print("\nPacing Tests:")
    print(f"  400 tokens: {hypervisor.enforce_deliberate_pacing(400, 'test_node')}")
    print(f"  600 tokens: {hypervisor.enforce_deliberate_pacing(600, 'test_node')}")
    
    # Test domain access
    print("\nDomain Access Tests:")
    print(f"  D0 read: {hypervisor.validate_domain_access(0, 'read', 'test_node')}")
    print(f"  D0 write: {hypervisor.validate_domain_access(0, 'write', 'test_node')}")
    print(f"  D1 read: {hypervisor.validate_domain_access(1, 'read', 'test_node')}")
    
    # Test sycophancy detection
    print("\nSycophancy Detection:")
    print(f"  High agreement + low uncertainty: {hypervisor.detect_sycophancy_patterns({'agreement_with_user': 0.98, 'uncertainty': 0.05})}")
    print(f"  Balanced metrics: {hypervisor.detect_sycophancy_patterns({'agreement_with_user': 0.7, 'uncertainty': 0.3})}")
    
    # Print violation report
    print("\n=== Violation Report ===")
    report = hypervisor.get_violation_report()
    print(f"Total violations: {report['total_violations']}")
    print(f"Violations by type: {report['violations_by_type']}")
    
    print("\n=== Hypervisor Active ===")
