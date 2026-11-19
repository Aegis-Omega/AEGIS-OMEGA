"""Authority-neutral read surface over recovered AEGIS archive runtimes.

The recovered SWARM/ARC sources retain their historical script-oriented import
layout. This adapter provides a bounded compatibility layer without granting
network, repository, deployment, or mutation authority.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

AUTHORITY_EFFECT = "NONE"
SCOPE = "LOCAL_EPHEMERAL_READ_COMPUTE_ONLY"


class ArchiveRuntimeError(RuntimeError):
    pass


class ArchiveRuntimeAdapter:
    def __init__(self, repository_root: str | Path) -> None:
        self.repository_root = Path(repository_root).resolve()
        self.swarm_root = self.repository_root / "swarm_os"
        required = [
            self.swarm_root / "arc" / "dsl" / "vm.py",
            self.swarm_root / "swarm" / "swarm_core.py",
            self.swarm_root / "biology" / "cybernetic_core.py",
        ]
        missing = [str(p.relative_to(self.repository_root)) for p in required if not p.is_file()]
        if missing:
            raise ArchiveRuntimeError("RECOVERED_RUNTIME_MISSING:" + ",".join(missing))

    def arc_transform(self, *, operation_id: int, grid: list[list[int]]) -> dict[str, Any]:
        if not isinstance(operation_id, int) or isinstance(operation_id, bool):
            raise ArchiveRuntimeError("ARC_OPERATION_ID_INVALID")
        if not grid or not all(isinstance(row, list) and row for row in grid):
            raise ArchiveRuntimeError("ARC_GRID_INVALID")
        width = len(grid[0])
        if any(len(row) != width for row in grid):
            raise ArchiveRuntimeError("ARC_GRID_NON_RECTANGULAR")
        if any(isinstance(v, bool) or not isinstance(v, int) for row in grid for v in row):
            raise ArchiveRuntimeError("ARC_GRID_VALUE_INVALID")

        import numpy as np
        from swarm_os.arc.dsl.vocab import TOKENS
        from swarm_os.arc.dsl.vm import DSLVM

        if operation_id not in TOKENS:
            raise ArchiveRuntimeError("ARC_OPERATION_UNKNOWN")
        source = np.asarray(grid, dtype=int)
        result = DSLVM().run([operation_id], source)
        return {
            "schema": "AEGIS_ARCHIVE_ARC_TRANSFORM_V1",
            "operation_id": operation_id,
            "operation": TOKENS[operation_id],
            "input_shape": list(source.shape),
            "output": result.tolist(),
            "scope": SCOPE,
            "authority_effect": AUTHORITY_EFFECT,
        }

    def swarm_observe(self, *, subject: str, relation: str, obj: str) -> dict[str, Any]:
        if not all(isinstance(v, str) and v for v in (subject, relation, obj)):
            raise ArchiveRuntimeError("SWARM_INPUT_INVALID")
        from swarm_os.swarm.swarm_core import QuantumManifold

        with tempfile.TemporaryDirectory(prefix="aegis-archive-swarm-") as td:
            manifold = QuantumManifold(Path(td))
            manifold.register_agent("archive-runtime-adapter", "read-compute")
            edge_id = manifold.ingest(subject, relation, obj, ["archive-runtime-adapter"])
            manifold.add_event("archive-runtime-adapter", "observation", "bounded adapter probe", 0)
            snapshot = manifold.get_state_snapshot()
            audit = manifold.read_audit()

        return {
            "schema": "AEGIS_ARCHIVE_SWARM_OBSERVATION_V1",
            "edge_id_present": bool(edge_id),
            "version": snapshot.get("version"),
            "node_count": len(snapshot.get("nodes", [])),
            "edge_count": len(snapshot.get("edges", [])),
            "audit_entry_count": len(audit),
            "persistent_state": False,
            "network_access": False,
            "scope": SCOPE,
            "authority_effect": AUTHORITY_EFFECT,
        }

    def biology_probe(self, *, stimulus: str) -> dict[str, Any]:
        if not isinstance(stimulus, str) or not stimulus:
            raise ArchiveRuntimeError("BIOLOGY_STIMULUS_INVALID")
        from swarm_os.biology.cybernetic_core import (
            EndocrineHPAAxis,
            ImmuneNetwork,
            SensoryCompressionGate,
        )

        sensory = SensoryCompressionGate().ingest_stimulus(stimulus)
        immune = ImmuneNetwork()
        entropy = immune.calculate_shannon_entropy(stimulus)
        pathogen = immune.detect_pathogen(stimulus)
        hpa = EndocrineHPAAxis()
        hpa_status = hpa.secrete_hormone(0.5)
        context_hd = hpa.compute_context_hd()

        return {
            "schema": "AEGIS_ARCHIVE_BIOLOGY_PROBE_V1",
            "sensory_output": sensory,
            "entropy": float(entropy),
            "pathogen_detected": bool(pathogen),
            "hpa_status": hpa_status,
            "context_hd": float(context_hd),
            "scope": SCOPE,
            "authority_effect": AUTHORITY_EFFECT,
        }


__all__ = ["ArchiveRuntimeAdapter", "ArchiveRuntimeError", "AUTHORITY_EFFECT", "SCOPE"]
