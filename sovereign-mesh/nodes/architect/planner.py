"""
Node α (Architect) - The Planner Agent
Part of the AEGIS Sovereign Automaton Fractal Mesh

Responsibilities:
- Receive high-level directives from human operators
- Decompose directives into causal chains using Khatt Loop protocol
- Enforce Sovereign Constitution at specification level
- Generate sprint contracts with explicit success criteria
- Apply Tanasub scaling to match task complexity

Model Assignment: Qwen-Max / Claude Opus 4.7
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class Nuqta:
    """Atomic truth unit - T0 Verified Fact"""
    data: bytes
    seal: str  # SHA-256 hash
    
    @classmethod
    def create(cls, data: bytes) -> 'Nuqta':
        seal = hashlib.sha256(data).hexdigest()
        return cls(data=data, seal=seal)
    
    def verify(self) -> bool:
        """Verify cryptographic seal"""
        return hashlib.sha256(self.data).hexdigest() == self.seal


@dataclass
class Alif:
    """Hard constraint / invariant axis"""
    name: str
    description: str
    violation_action: str  # e.g., "REJECT", "REROLL", "EXIT"
    
    CONSTRAINTS = {
        "AGPL3_COMPLIANCE": "All code must be AGPL-3.0 licensed",
        "ZERO_ALLOCATION": "Hot paths must avoid heap allocation",
        "GENESIS_SEAL": "T0 ledger must match cryptographic seal",
        "DOMAIN_ISOLATION": "D0 core cannot be mutated by D1 overlay",
        "NO_TOKIO": "Runtime must use std::thread only",
        "BTREE_MAP": "Use BTreeMap for deterministic iteration",
    }


@dataclass
class SprintContract:
    """Contract between Architect and Artisan nodes"""
    sprint_id: str
    directive: str
    specifications: List[str]
    success_criteria: List[str]
    constraints: List[str]
    complexity_lambda: int  # 1-10 scale
    nuqta_seal: str
    alif_references: List[str]
    created_at: str
    expires_at: str


class ConstitutionalEnforcer:
    """Enforce Sovereign Constitution at specification level"""
    
    CONSTITUTION = {
        "epistemic_sovereignty": "Truth over Flow. Uncertainty is preserved, never collapsed.",
        "causal_architecture": "Mechanism over Metaphor. Explicit causal chains replace narrative.",
        "operational_realism": "Feasibility as Constraint. Hard constraints dominate soft constraints.",
        "adversarial_self_correction": "Continuous Internal Audit. System seeks its own failure modes."
    }
    
    def validate_directive(self, directive: str) -> Dict[str, Any]:
        """Validate directive against constitutional principles"""
        violations = []
        
        # Check for narrative framing (violates causal_architecture)
        narrative_patterns = [
            "imagine that", "let's pretend", "suppose that",
            "in a world where", "picture this"
        ]
        for pattern in narrative_patterns:
            if pattern.lower() in directive.lower():
                violations.append({
                    "principle": "causal_architecture",
                    "issue": f"Narrative framing detected: '{pattern}'",
                    "severity": "HIGH"
                })
        
        # Check for false certainty (violates epistemic_sovereignty)
        certainty_patterns = [
            "always works", "never fails", "guaranteed to",
            "100% certain", "absolutely sure"
        ]
        for pattern in certainty_patterns:
            if pattern.lower() in directive.lower():
                violations.append({
                    "principle": "epistemic_sovereignty",
                    "issue": f"False certainty detected: '{pattern}'",
                    "severity": "MEDIUM"
                })
        
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "directive_sanitized": self._sanitize_directive(directive, violations)
        }
    
    def _sanitize_directive(self, directive: str, violations: List[Dict]) -> str:
        """Remove narrative framing and false certainty"""
        sanitized = directive
        # Remove narrative patterns
        for pattern in ["imagine that", "let's pretend", "suppose that"]:
            sanitized = sanitized.replace(pattern, "consider")
        # Remove false certainty
        for pattern in ["always works", "guaranteed to"]:
            sanitized = sanitized.replace(pattern, "typically achieves")
        return sanitized


class SpecExpander:
    """Expand prompts into detailed specifications using Khatt Loop"""
    
    def expand(self, directive: str, complexity_lambda: int) -> Dict[str, Any]:
        """
        Expand directive using 5-phase Khatt Loop:
        1. Nuqta: Identify atomic truth
        2. Alif: Establish hard constraints
        3. Rasm: Weave causal flow
        4. Tashkeel: Apply uncertainty metadata
        5. Tanasub: Scale proportionally
        """
        # Phase 1: Nuqta
        nuqta = Nuqta.create(directive.encode('utf-8'))
        
        # Phase 2: Alif
        alifs = self._identify_constraints(directive, complexity_lambda)
        
        # Phase 3: Rasm
        rasm = self._weave_causal_flow(directive, alifs)
        
        # Phase 4: Tashkeel
        tashkeel = self._apply_uncertainty_metadata(directive)
        
        # Phase 5: Tanasub
        tanasub = self._scale_proportionally(rasm, complexity_lambda)
        
        return {
            "nuqta": {"seal": nuqta.seal, "verified": nuqta.verify()},
            "alifs": [asdict(a) for a in alifs],
            "rasm": rasm,
            "tashkeel": tashkeel,
            "tanasub": tanasub
        }
    
    def _identify_constraints(self, directive: str, lambda_level: int) -> List[Alif]:
        """Identify hard constraints based on directive and complexity"""
        constraints = []
        
        # Always enforce core invariants
        constraints.append(Alif(
            name="AGPL3_COMPLIANCE",
            description=Alif.CONSTRAINTS["AGPL3_COMPLIANCE"],
            violation_action="REJECT"
        ))
        
        constraints.append(Alif(
            name="GENESIS_SEAL",
            description=Alif.CONSTRAINTS["GENESIS_SEAL"],
            violation_action="EXIT"
        ))
        
        # Add complexity-dependent constraints
        if lambda_level >= 7:
            constraints.append(Alif(
                name="ZERO_ALLOCATION",
                description=Alif.CONSTRAINTS["ZERO_ALLOCATION"],
                violation_action="REROLL"
            ))
        
        if lambda_level >= 5:
            constraints.append(Alif(
                name="DOMAIN_ISOLATION",
                description=Alif.CONSTRAINTS["DOMAIN_ISOLATION"],
                violation_action="REJECT"
            ))
        
        return constraints
    
    def _weave_causal_flow(self, directive: str, alifs: List[Alif]) -> List[str]:
        """Create continuous causal dependency graph"""
        flow = []
        flow.append(f"INPUT: {directive}")
        
        for alif in alifs:
            flow.append(f"CONSTRAINT: {alif.name} → {alif.description}")
        
        flow.append("PROCESS: Apply constitutional enforcer")
        flow.append("PROCESS: Expand into modular components")
        flow.append("PROCESS: Generate test harness")
        flow.append("OUTPUT: Complete sprint deliverable")
        
        return flow
    
    def _apply_uncertainty_metadata(self, directive: str) -> Dict[str, Any]:
        """Tag assumptions and confidence intervals"""
        return {
            "confidence": 0.85,  # Default confidence
            "assumptions": [
                "Directive is well-formed",
                "Required dependencies are available",
                "Execution environment is stable"
            ],
            "risk_factors": [],
            "unknowns": []
        }
    
    def _scale_proportionally(self, rasm: List[str], lambda_level: int) -> Dict[str, Any]:
        """Apply Golden Ratio proportional scaling"""
        phi = 1.618033988749895
        
        # O(log_φ(n)) complexity instead of O(n)
        base_effort = 1.0
        scaled_effort = base_effort * (phi ** (lambda_level / 10))
        
        return {
            "complexity_lambda": lambda_level,
            "scaled_effort": round(scaled_effort, 2),
            "estimated_tokens": int(1000 * scaled_effort),
            "fractal_depth": lambda_level,
            "golden_ratio_applied": True
        }


class ArchitectNode:
    """Node α: The Architect - Planner Agent"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.enforcer = ConstitutionalEnforcer()
        self.expander = SpecExpander()
        self.state_dir = Path(self.config.get("state_dir", "./state/architect"))
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load node configuration"""
        default_config = {
            "node_id": "architect-alpha-001",
            "model": "qwen-max",
            "state_dir": "./state/architect",
            "max_complexity": 10,
            "constitution_version": "1.0.0"
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                loaded = json.load(f)
                default_config.update(loaded)
        
        return default_config
    
    def process_directive(self, directive: str, complexity_lambda: int = 5) -> SprintContract:
        """
        Process incoming directive and generate sprint contract
        
        Args:
            directive: High-level user prompt or trigger
            complexity_lambda: Task complexity (1-10)
        
        Returns:
            SprintContract ready for Artisan node
        """
        # Validate against constitution
        validation = self.enforcer.validate_directive(directive)
        
        if not validation["valid"]:
            # Log violations but continue with sanitized directive
            self._log_violations(validation["violations"])
            directive = validation["directive_sanitized"]
        
        # Expand using Khatt Loop
        expanded = self.expander.expand(directive, complexity_lambda)
        
        # Generate sprint contract
        sprint_id = self._generate_sprint_id()
        now = datetime.utcnow()
        
        contract = SprintContract(
            sprint_id=sprint_id,
            directive=directive,
            specifications=expanded["rasm"],
            success_criteria=self._derive_success_criteria(expanded),
            constraints=[a["name"] for a in expanded["alifs"]],
            complexity_lambda=complexity_lambda,
            nuqta_seal=expanded["nuqta"]["seal"],
            alif_references=[a["name"] for a in expanded["alifs"]],
            created_at=now.isoformat(),
            expires_at=(now.replace(hour=23, minute=59, second=59)).isoformat()
        )
        
        # Persist contract
        self._persist_contract(contract, expanded)
        
        return contract
    
    def _generate_sprint_id(self) -> str:
        """Generate unique sprint identifier"""
        timestamp = datetime.utcnow().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:12]
    
    def _derive_success_criteria(self, expanded: Dict) -> List[str]:
        """Derive measurable success criteria from expansion"""
        criteria = []
        
        # Nuqta verification
        criteria.append(f"T0 Genesis Seal verified: {expanded['nuqta']['seal'][:8]}...")
        
        # Alif compliance
        for alif in expanded["alifs"]:
            criteria.append(f"Constraint {alif['name']} enforced")
        
        # Rasm completion
        criteria.append(f"Causal flow completed: {len(expanded['rasm'])} steps")
        
        # Tanasub scaling
        criteria.append(f"Proportional scaling applied: λ={expanded['tanasub']['complexity_lambda']}")
        
        return criteria
    
    def _persist_contract(self, contract: SprintContract, expanded: Dict) -> None:
        """Persist contract to state directory"""
        contract_file = self.state_dir / f"{contract.sprint_id}.json"
        
        data = {
            "contract": asdict(contract),
            "expansion": expanded,
            "metadata": {
                "node_id": self.config["node_id"],
                "constitution_version": self.config["constitution_version"]
            }
        }
        
        with open(contract_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _log_violations(self, violations: List[Dict]) -> None:
        """Log constitutional violations for NLA analysis"""
        log_file = self.state_dir / "violations.log"
        
        with open(log_file, 'a') as f:
            timestamp = datetime.utcnow().isoformat()
            for v in violations:
                f.write(f"[{timestamp}] {v['principle']}: {v['issue']} ({v['severity']})\n")


def main():
    """Main entry point for Architect Node"""
    import sys
    
    # Initialize node
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    architect = ArchitectNode(config_path)
    
    # Example directive
    directive = "Implement a zero-allocation memory pool for the runtime substrate"
    complexity = 7
    
    print(f"Processing directive: {directive}")
    print(f"Complexity λ: {complexity}")
    
    # Generate sprint contract
    contract = architect.process_directive(directive, complexity)
    
    print(f"\nSprint Contract Generated:")
    print(f"  ID: {contract.sprint_id}")
    print(f"  Constraints: {len(contract.constraints)}")
    print(f"  Success Criteria: {len(contract.success_criteria)}")
    print(f"  Nuqta Seal: {contract.nuqta_seal[:16]}...")
    
    return contract


if __name__ == "__main__":
    main()
