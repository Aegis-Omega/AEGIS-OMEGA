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
import hmac
import json
import re


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
    
    def verify(self, original_directive: str) -> bool:
        """Check an actual content digest, not equality to an unrelated seal.

        This establishes input integrity only. The genesis seal is a separate
        authority concept and this hash alone confers no authority.
        """
        return (
            isinstance(original_directive, str)
            and isinstance(self.hash, str)
            and hmac.compare_digest(
                self.hash,
                hashlib.sha256(original_directive.encode("utf-8")).hexdigest(),
            )
        )


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
    confidence: float = 0.0  # No observed outcome evidence at planning time


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
        """Describe unverified obligations; never self-certify compliance.

        Constraint verification must be supplied by an independent external
        verifier at execution/admission time; this planner cannot grant it.
        """
        if not isinstance(constraints, list) or not all(
            isinstance(c, ConstraintType) for c in constraints
        ):
            raise ValueError("CONSTRAINT_TYPE_INVALID")
        return {c.value: False for c in sorted(set(constraints), key=lambda c: c.value)}

    def decompose_directive(self, directive: str, constraints: List[ConstraintType]) -> CausalChain:
        """
        Decompose high-level directive into causal chain.
        Implements the full Khatt Loop protocol.
        """
        if not isinstance(directive, str) or not directive.strip() or len(directive) > 10000:
            raise ValueError("DIRECTIVE_INVALID")
        if not isinstance(constraints, list) or not all(isinstance(c, ConstraintType) for c in constraints):
            raise ValueError("CONSTRAINT_TYPE_INVALID")

        # Phase 1: bind the directive to its content digest (not a seal grant).
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
            confidence=0.0  # No runtime/evaluator observation exists
        )
        
        self.chains.append(chain)
        return chain
    
    def validate_chain(self, chain: CausalChain) -> bool:
        """Validate *structure* only: integrity, DAG, constraints, phase order.

        True is NOT an execution, constitutional or deployment admission.
        """
        if not isinstance(chain, CausalChain):
            return False
        if not chain.nuqta.verify(chain.directive):
            return False
        if chain.confidence != 0.0:
            return False
        if not isinstance(chain.tasks, list) or not chain.tasks:
            return False
        if not isinstance(self.genesis_seal, str) or re.fullmatch(r"[0-9a-f]{64}", self.genesis_seal) is None:
            return False
        ids = [task.id for task in chain.tasks if isinstance(task, Task)]
        if len(ids) != len(chain.tasks) or len(ids) != len(set(ids)):
            return False
        by_id = {task.id: task for task in chain.tasks}
        for task in chain.tasks:
            if not isinstance(task.id, str) or not task.id:
                return False
            if not isinstance(task.khatt_phase, KhattPhase):
                return False
            if not isinstance(task.constraints, list) or not all(
                isinstance(c, ConstraintType) for c in task.constraints
            ):
                return False
            if not isinstance(task.dependencies, list) or len(task.dependencies) != len(set(task.dependencies)):
                return False
            for dep in task.dependencies:
                if not isinstance(dep, str) or dep == task.id or dep not in by_id:
                    return False
                if by_id[dep].khatt_phase.value >= task.khatt_phase.value:
                    return False

        # Refuse every unresolved dependency (including cycles). No implicit
        # fallback to a generated "success" task.
        pending = set(by_id)
        executed: set[str] = set()
        while pending:
            ready = sorted(
                (sid for sid in pending if all(dep in executed for dep in by_id[sid].dependencies)),
                key=lambda sid: (by_id[sid].khatt_phase.value, sid),
            )
            if not ready:
                return False
            for sid in ready:
                pending.remove(sid)
                executed.add(sid)
        return True

    def get_execution_plan(self, chain: CausalChain) -> List[Dict]:
        """Deterministic causal plan, with mandatory independent evidence gates.

        A plan is not proof that any obligation was discharged.
        """
        if not self.validate_chain(chain):
            raise ValueError("CAUSAL_CHAIN_INVALID")
        plan: List[Dict] = []
        executed: set[str] = set()
        pending = {task.id: task for task in chain.tasks}
        while pending:
            ready = sorted(
                (task for task in pending.values()
                 if all(dep in executed for dep in task.dependencies)),
                key=lambda task: (task.khatt_phase.value, task.id),
            )
            if not ready:
                raise ValueError("CAUSAL_CYCLE_OR_BLOCKED")
            task = ready[0]
            plan.append({
                "id": task.id,
                "phase": task.khatt_phase.name,
                "description": task.description,
                "constraints": [c.value for c in sorted(set(task.constraints), key=lambda c: c.value)],
                "dependencies": sorted(task.dependencies),
                "metadata": task.metadata,
                "execution_state": "PENDING_INDEPENDENT_EVIDENCE",
                "admission": "NOT_ADMITTED",
            })
            executed.add(task.id)
            del pending[task.id]
        return plan

    def compile_plan_contract(self, chain: CausalChain) -> Dict[str, Any]:
        """Proof-obligation contract with domain-separated deterministic digest.

        The digest authenticates *neither* the author nor the executor.
        External provenance and authority still must be independently verified.
        """
        plan = self.get_execution_plan(chain)
        body: Dict[str, Any] = {
            "schema_version": "1.0.0",
            "kind": "AEGIS_CAUSAL_BUILD_CONTRACT_V1",
            "directive_sha256": chain.nuqta.hash,
            "planner_genesis_reference": self.genesis_seal,
            "tasks": plan,
            "verified_constraints": [],
            "operational_admission": "NOT_ADMITTED",
            "authority_granted": False,
        }
        canonical = json.dumps({"domain": body["kind"], "body": body},
                               sort_keys=True, separators=(",", ":"), allow_nan=False)
        return {**body, "contract_sha256": hashlib.sha256(canonical.encode()).hexdigest()}

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
