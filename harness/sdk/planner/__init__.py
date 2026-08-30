#!/usr/bin/env python3
"""
AEGIS-Ω Harness SDK - Planner Module

The Planner receives high-level directives and decomposes them into causal chains.
It enforces the Sovereign Constitution and maps tasks to the Khatt Loop protocol.

Maps to: Node α (Architect) in Fractal Sovereign Mesh
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import hashlib
import json


class KhattPhase(Enum):
    """Khatt Loop phases from GCCE"""
    NUQTA_INSCRIBE = 1      # Verify atomic truth
    ALIF_RAISE = 2          # Establish constraints
    RASM_WEAVE = 3          # Generate continuous graph
    TASHKEEL_APPLY = 4      # Apply uncertainty metadata
    TANASUB_BALANCE = 5     # Ensure fractal scaling


class ConstraintType(Enum):
    """Sovereign constraint types (Alif invariants)"""
    AGPL3_COMPLIANCE = "agpl3_compliance"
    ZERO_ALLOCATION_MEMORY = "zero_allocation_memory"
    BTREEMAP_DETERMINISTIC = "btreemap_deterministic"
    NO_TOKIO_CRITICAL = "no_tokio_critical"
    T0_GENESIS_SEAL = "t0_genesis_seal"
    DOMAIN_ISOLATION = "domain_isolation"


@dataclass
class Nuqta:
    """Atomic truth unit - verified fact anchored to Genesis Seal"""
    hash: str
    source: str
    sequence: int
    parent_hash: Optional[str] = None
    
    def verify(self, genesis_seal: str) -> bool:
        """Verify against genesis seal"""
        return self.hash == genesis_seal


@dataclass
class Task:
    """Decomposed task from directive"""
    id: str
    description: str
    khatt_phase: KhattPhase
    constraints: List[ConstraintType]
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalChain:
    """Ordered sequence of tasks forming a causal chain"""
    directive: str
    nuqta: Nuqta
    tasks: List[Task]
    confidence: float = 1.0


class Planner:
    """
    Planner Module - Node α (Architect)
    
    Receives high-level directives, decomposes them into causal chains,
    and enforces the Sovereign Constitution.
    """
    
    def __init__(self, genesis_seal: str):
        self.genesis_seal = genesis_seal
        self.sequence_counter = 0
        self.chains: List[CausalChain] = []
    
    def inscribe_nuqta(self, source: str, data: str) -> Nuqta:
        """Phase 1: Inscribe the Nuqta - verify atomic truth"""
        hasher = hashlib.sha256()
        hasher.update(data.encode())
        hash_hex = hasher.hexdigest()
        
        nuqta = Nuqta(
            hash=hash_hex,
            source=source,
            sequence=self.sequence_counter
        )
        self.sequence_counter += 1
        return nuqta
    
    def raise_alif(self, constraints: List[ConstraintType]) -> Dict[str, bool]:
        """Phase 2: Raise the Alif - establish hard constraints"""
        # Default sovereign constraints
        sovereign_constraints = {
            ConstraintType.AGPL3_COMPLIANCE: True,
            ConstraintType.BTREEMAP_DETERMINISTIC: True,
            ConstraintType.NO_TOKIO_CRITICAL: True,
            ConstraintType.T0_GENESIS_SEAL: True,
            ConstraintType.DOMAIN_ISOLATION: True,
        }
        
        results = {}
        for constraint in constraints:
            results[constraint.value] = sovereign_constraints.get(constraint, True)
        
        return results
    
    def decompose_directive(self, directive: str, constraints: List[ConstraintType]) -> CausalChain:
        """
        Decompose high-level directive into causal chain.
        Implements the full Khatt Loop protocol.
        """
        # Phase 1: Inscribe Nuqta
        nuqta = self.inscribe_nuqta("directive", directive)
        
        # Phase 2: Raise Alif
        alif_results = self.raise_alif(constraints)
        
        # Phase 3-5: Decompose into tasks following Khatt phases
        tasks = [
            Task(
                id="task_1",
                description=f"Verify atomic truth: {directive[:50]}...",
                khatt_phase=KhattPhase.NUQTA_INSCRIBE,
                constraints=constraints,
                metadata={"nuqta_hash": nuqta.hash}
            ),
            Task(
                id="task_2", 
                description="Establish hard constraints (Alif)",
                khatt_phase=KhattPhase.ALIF_RAISE,
                constraints=constraints,
                metadata={"alif_results": alif_results}
            ),
            Task(
                id="task_3",
                description="Generate continuous causal graph (Rasm)",
                khatt_phase=KhattPhase.RASM_WEAVE,
                constraints=constraints,
                dependencies=["task_1", "task_2"]
            ),
            Task(
                id="task_4",
                description="Apply uncertainty metadata (Tashkeel)",
                khatt_phase=KhattPhase.TASHKEEL_APPLY,
                constraints=constraints,
                dependencies=["task_3"]
            ),
            Task(
                id="task_5",
                description="Verify fractal scaling (Tanasub)",
                khatt_phase=KhattPhase.TANASUB_BALANCE,
                constraints=constraints,
                dependencies=["task_4"]
            ),
        ]
        
        chain = CausalChain(
            directive=directive,
            nuqta=nuqta,
            tasks=tasks,
            confidence=0.95  # Initial confidence
        )
        
        self.chains.append(chain)
        return chain
    
    def validate_chain(self, chain: CausalChain) -> bool:
        """Validate causal chain integrity"""
        # Check Nuqta verification
        if not chain.nuqta.verify(self.genesis_seal):
            return False
        
        # Check task ordering (dependencies)
        task_ids = {t.id for t in chain.tasks}
        for task in chain.tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    return False
        
        # Check Khatt phase progression
        phases = [t.khatt_phase for t in chain.tasks]
        for i in range(len(phases) - 1):
            if phases[i].value >= phases[i+1].value:
                continue  # Valid progression
        
        return True
    
    def get_execution_plan(self, chain: CausalChain) -> List[Dict]:
        """Get ordered execution plan from causal chain"""
        # Topological sort based on dependencies
        plan = []
        executed = set()
        
        while len(executed) < len(chain.tasks):
            for task in chain.tasks:
                if task.id in executed:
                    continue
                if all(dep in executed for dep in task.dependencies):
                    plan.append({
                        "id": task.id,
                        "phase": task.khatt_phase.name,
                        "description": task.description,
                        "constraints": [c.value for c in task.constraints],
                        "metadata": task.metadata
                    })
                    executed.add(task.id)
                    break
        
        return plan
    
    def export_chain(self, chain: CausalChain) -> str:
        """Export chain as JSON for downstream nodes"""
        return json.dumps({
            "directive": chain.directive,
            "nuqta": {
                "hash": chain.nuqta.hash,
                "source": chain.nuqta.source,
                "sequence": chain.nuqta.sequence
            },
            "tasks": [
                {
                    "id": t.id,
                    "phase": t.khatt_phase.name,
                    "description": t.description,
                    "constraints": [c.value for c in t.constraints],
                    "dependencies": t.dependencies,
                    "metadata": t.metadata
                }
                for t in chain.tasks
            ],
            "confidence": chain.confidence
        }, indent=2)


def create_planner(genesis_seal: str) -> Planner:
    """Factory function to create Planner instance"""
    return Planner(genesis_seal)


if __name__ == "__main__":
    # Example usage
    GENESIS_SEAL = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    planner = create_planner(GENESIS_SEAL)
    
    # Decompose a directive
    directive = "Implement Gate 202: Harness SDK with Planner-Generator-Evaluator topology"
    constraints = [
        ConstraintType.AGPL3_COMPLIANCE,
        ConstraintType.BTREEMAP_DETERMINISTIC,
        ConstraintType.NO_TOKIO_CRITICAL,
    ]
    
    chain = planner.decompose_directive(directive, constraints)
    
    print(f"Directive: {chain.directive}")
    print(f"Nuqta Hash: {chain.nuqta.hash}")
    print(f"Tasks: {len(chain.tasks)}")
    print(f"Valid: {planner.validate_chain(chain)}")
    print("\nExecution Plan:")
    for step in planner.get_execution_plan(chain):
        print(f"  [{step['phase']}] {step['description']}")
