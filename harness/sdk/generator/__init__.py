#!/usr/bin/env python3
"""
AEGIS-Ω Harness SDK - Generator Module

The Generator receives tasks from the Planner and executes sprint work.
It generates code, runs tests, and produces artifacts while maintaining
Rasm continuity (no orphaned modules).

Maps to: Node β (Artisan) in Fractal Sovereign Mesh
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
import hashlib
import json
import time


class GenerationStatus(Enum):
    """Status of code generation"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    REJECTED = "rejected"  # Failed Evaluator check


@dataclass
class CodeArtifact:
    """Generated code artifact"""
    path: str
    content: str
    language: str
    hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SprintResult:
    """Result of a sprint execution"""
    task_id: str
    status: GenerationStatus
    artifacts: List[CodeArtifact]
    test_results: List[Dict]
    execution_time_ms: float
    confidence: float


class RalphExecutor:
    """Generate candidate artifacts through an explicit implementation adapter.

    The default is a denied/no-builder result, not synthetic Rust code.
    Compilation is only a syntax check; independent execution evidence is
    required before a sprint can be marked complete.
    """

    def __init__(
        self,
        constraints: Dict[str, bool],
        artifact_builder: Optional[Callable[[str], List[CodeArtifact]]] = None,
    ):
        self.constraints = constraints
        self.artifact_builder = artifact_builder
        self.artifacts: List[CodeArtifact] = []
        self.execution_log: List[Dict] = []

    def execute(self, task_description: str) -> List[CodeArtifact]:
        if self.artifact_builder is None:
            self.execution_log.append({
                "task_digest": hashlib.sha256(task_description.encode()).hexdigest(),
                "outcome": "DENIED_NO_IMPLEMENTATION_ADAPTER",
            })
            return []
        candidates = self.artifact_builder(task_description)
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("IMPLEMENTATION_ADAPTER_PRODUCED_NO_ARTIFACTS")
        seen = set()
        for artifact in candidates:
            if not isinstance(artifact, CodeArtifact):
                raise ValueError("ARTIFACT_TYPE_INVALID")
            if not isinstance(artifact.path, str) or artifact.path.startswith("/") or "\\" in artifact.path or any(p in ("", ".", "..") for p in artifact.path.split("/")):
                raise ValueError("ARTIFACT_PATH_UNSAFE")
            if artifact.path in seen:
                raise ValueError("ARTIFACT_PATH_DUPLICATE")
            seen.add(artifact.path)
            if not isinstance(artifact.content, str) or not artifact.content.strip():
                raise ValueError("ARTIFACT_CONTENT_EMPTY")
            if hashlib.sha256(artifact.content.encode("utf-8")).hexdigest() != artifact.hash:
                raise ValueError("ARTIFACT_HASH_MISMATCH")
        self.artifacts.extend(candidates)
        self.execution_log.append({
            "task_digest": hashlib.sha256(task_description.encode()).hexdigest(),
            "outcome": "CANDIDATE_GENERATED_UNVERIFIED",
            "artifact_hashes": {item.path: item.hash for item in candidates},
        })
        return candidates

    def run_tests(self, artifacts: List[CodeArtifact]) -> List[Dict]:
        """Never invent test passes; require a separate trusted executor."""
        return [{
            "artifact": artifact.path,
            "passed": False,
            "tests_run": 0,
            "tests_passed": 0,
            "reason": "INDEPENDENT_TEST_RUN_NOT_ATTACHED",
        } for artifact in artifacts]

class Generator:
    """
    Generator Module - Node β (Artisan)
    
    Receives atomic tasks from Planner, generates code via RalphExecutor,
    and maintains Rasm continuity (interconnected graph).
    """
    
    def __init__(self, executor: Optional[RalphExecutor] = None):
        self.executor = executor or RalphExecutor(constraints={})
        self.sprint_history: List[SprintResult] = []
        self.rasm_continuity: Dict[str, List[str]] = {}  # task_id -> connected tasks
    
    def execute_sprint(self, task: Dict, context: Optional[Dict] = None) -> SprintResult:
        """
        Execute a sprint for a single task.
        Phase 3 of Khatt Loop: Weave the Rasm.
        """
        start_time = time.time()
        
        task_id = task.get("id", "unknown")
        description = task.get("description", "")
        constraints = task.get("constraints", [])
        
        # Execute code generation
        artifacts = self.executor.execute(description)
        
        # Run tests
        test_results = self.executor.run_tests(artifacts)
        
        # A test adapter can forge `passed`, `tests_run`, and even
        # `independent_receipt_verified=True`. No positive admission exists
        # until a separate verifier checks a trusted, source-bound receipt.
        # The original sprint loop must remain candidate-only.
        verified = False
        confidence = 0.0

        execution_time = (time.time() - start_time) * 1000
        
        result = SprintResult(
            task_id=task_id,
            status=GenerationStatus.COMPLETE if verified else GenerationStatus.REJECTED,
            artifacts=artifacts,
            test_results=test_results,
            execution_time_ms=execution_time,
            confidence=confidence
        )
        
        self.sprint_history.append(result)
        
        # Track Rasm continuity
        self._update_rasm_continuity(task_id, [a.path for a in artifacts])
        
        return result
    
    def _update_rasm_continuity(self, task_id: str, artifact_paths: List[str]):
        """Update Rasm continuity tracking"""
        self.rasm_continuity[task_id] = artifact_paths
    
    def verify_rasm_continuity(self, task_dependencies: Dict[str, List[str]]) -> bool:
        """
        Verify that all tasks have proper ligature connections.
        Ensures no orphaned modules exist.
        """
        for task_id, deps in task_dependencies.items():
            if task_id not in self.rasm_continuity:
                return False
            
            # Check that dependencies are satisfied
            for dep in deps:
                if dep not in self.rasm_continuity:
                    return False
        
        return True
    
    def get_artifact_chain(self, task_ids: List[str]) -> List[CodeArtifact]:
        """Get all artifacts for a chain of tasks"""
        artifacts = []
        for result in self.sprint_history:
            if result.task_id in task_ids:
                artifacts.extend(result.artifacts)
        return artifacts
    
    def export_sprint_result(self, result: SprintResult) -> str:
        """Export sprint result as JSON for Evaluator"""
        return json.dumps({
            "task_id": result.task_id,
            "status": result.status.value,
            "artifacts": [
                {
                    "path": a.path,
                    "content_hash": a.hash,
                    "language": a.language,
                    "metadata": a.metadata
                }
                for a in result.artifacts
            ],
            "test_results": result.test_results,
            "execution_time_ms": result.execution_time_ms,
            "confidence": result.confidence
        }, indent=2)


def create_generator(constraints: Optional[Dict[str, bool]] = None) -> Generator:
    """Factory function to create Generator instance"""
    executor = RalphExecutor(constraints=constraints or {})
    return Generator(executor)


if __name__ == "__main__":
    # Example usage
    generator = create_generator({
        "agpl3_compliance": True,
        "btreemap_deterministic": True,
    })
    
    # Simulate task from Planner
    task = {
        "id": "task_3",
        "description": "Generate continuous causal graph (Rasm)",
        "constraints": ["btreemap_deterministic"],
        "dependencies": ["task_1", "task_2"]
    }
    
    result = generator.execute_sprint(task)
    
    print(f"Task ID: {result.task_id}")
    print(f"Status: {result.status.value}")
    print(f"Artifacts: {len(result.artifacts)}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Execution Time: {result.execution_time_ms:.2f}ms")
    print(f"\nRasm Continuity: {generator.verify_rasm_continuity({'task_3': ['task_1', 'task_2']})}")
