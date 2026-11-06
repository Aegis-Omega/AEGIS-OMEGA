#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for extra in (
    ROOT,
    ROOT / "swarm_os" / "arc",
    ROOT / "swarm_os" / "swarm",
    ROOT / "swarm_os" / "biology",
):
    value = str(extra)
    if value not in sys.path:
        sys.path.insert(0, value)

from swarm_os.arc.dsl.vocab import TOKENS
from swarm_os.arc.dsl.vm import DSLVM
from swarm_os.arc.grammar.macro_library import MacroLibrary
from swarm_os.swarm.swarm_core import QuantumManifold
from swarm_os.biology.cybernetic_core import SensoryCompressionGate, ImmuneNetwork, EndocrineHPAAxis
from swarm_os.biology.metacognitive_evolution import HDHistoryTracker


def run() -> dict:
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        vm = DSLVM()
        grid = np.array([[1, 2], [3, 4]], dtype=int)
        dsl = []
        for op_id, name in sorted(TOKENS.items()):
            out = vm.run([op_id], grid)
            if out.shape != grid.shape:
                raise AssertionError(f"DSL shape drift for {name}: {out.shape}")
            dsl.append({"id": int(op_id), "name": name, "shape": list(out.shape), "sum": int(out.sum())})

        macros = MacroLibrary()
        if len(macros) != 11 or macros.vocab_size() != 11:
            raise AssertionError("ARC primitive macro library drift")

        with tempfile.TemporaryDirectory() as td:
            q = QuantumManifold(Path(td))
            q.register_agent("restore-smoke", "test")
            edge_id = q.ingest("alpha", "relates_to", "beta", ["archive-restoration"])
            event = q.add_event("restore-smoke", "observation", "runtime smoke", 1)
            snap = q.get_state_snapshot()
            audit = q.read_audit()
            if len(snap.get("nodes", [])) != 3:
                raise AssertionError("unexpected SWARM node count")
            if len(snap.get("edges", [])) != 1:
                raise AssertionError("unexpected SWARM edge count")
            if len(audit) < 3:
                raise AssertionError("SWARM audit trail not emitted")
            swarm = {
                "edge_id_present": bool(edge_id),
                "event_type": event.get("type"),
                "nodes": len(snap.get("nodes", [])),
                "edges": len(snap.get("edges", [])),
                "audit_entries": len(audit),
                "version": snap.get("version"),
            }

        sensory = SensoryCompressionGate().ingest_stimulus("abc123")
        immune = ImmuneNetwork()
        entropy = immune.calculate_shannon_entropy("aaaaabbbbb")
        pathogen = immune.detect_pathogen("normal input")
        hpa = EndocrineHPAAxis()
        hpa_status = hpa.secrete_hormone(0.5)
        context_hd = hpa.compute_context_hd()

        tracker = HDHistoryTracker(window=4)
        for row in [
            (0.4, 0.3, 0.8, ["a"]),
            (0.3, 0.2, 0.9, ["a", "b"]),
            (0.2, 0.2, 0.9, ["b"]),
            (0.1, 0.1, 0.95, ["c"]),
        ]:
            tracker.record(*row)
        hd = tracker.summary()

    if sensory != "abc123":
        raise AssertionError("sensory compression smoke drift")
    if pathogen:
        raise AssertionError("benign immune smoke unexpectedly flagged")
    if abs(float(hd["rolling_mean"]) - 0.25) > 1e-12:
        raise AssertionError("HD rolling mean drift")

    return {
        "schema": "AEGIS_ARCHIVE_SWARM_RUNTIME_SMOKE_V1",
        "status": "PASS",
        "arc": {
            "dsl_primitive_count": len(dsl),
            "macro_primitive_count": len(macros),
            "operations": dsl,
        },
        "swarm": swarm,
        "biology_metacognition": {
            "sensory_roundtrip": sensory,
            "entropy": float(entropy),
            "benign_pathogen_detected": bool(pathogen),
            "hpa_status": hpa_status,
            "context_hd": float(context_hd),
            "hd_summary": hd,
        },
        "captured_stdout_lines": [line for line in captured.getvalue().splitlines() if line.strip()],
        "production_wiring": "NOT_PERFORMED",
        "authority_effect": "NONE",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
