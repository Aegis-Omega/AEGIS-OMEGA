"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. TemporalLibrarian — Sovereign OS adaptation.
Reads/writes .forge/knowledge_graph.json and .forge/hypothesis_graph.json
using ATOMIC WRITE PROTOCOL (constitutional law: .tmp → rename).

Core mechanics:
  Triangle Protocol  → 2-simplex closure verification (geometric proof per edge)
  Temporal Mutation  → mutable_relations update in-place (no contradictions accumulate)
  Hypothesis Quarantine → unstable edges decay over time (don't delete, decay)
  Curiosity Protocol → unstable geometry logs to audit.jsonl (FATAL_BLOCKER escalation)
"""
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .geometry import calculate_cosine_similarity, node_to_vector, density_to_confidence

FORGE     = Path(__file__).parent.parent.parent / ".forge"
KG_PATH   = FORGE / "knowledge_graph.json"
HYP_PATH  = FORGE / "hypothesis_graph.json"
AUDIT_PATH = FORGE / "audit.jsonl"

# Relations that describe mutable state — can change over time without contradiction
MUTABLE_RELATIONS = {
    "has_state", "located_in", "is_currently", "current_value",
    "stress_level", "attention_level", "atp_balance", "elected_model",
}


def _atomic_write(path: Path, data: dict):
    """Constitutional law: all .forge writes are .tmp → rename."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _load_kg():
    if KG_PATH.exists():
        return json.loads(KG_PATH.read_text(encoding="utf-8"))
    return {"nodes": {}, "edges": []}


def _load_hypothesis():
    if HYP_PATH.exists():
        return json.loads(HYP_PATH.read_text(encoding="utf-8"))
    return {"edges": []}


def _log_audit(event: str, data: dict):
    entry = json.dumps({"ts": time.time(), "event": event, **data}) + "\n"
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


class SovereignOrchestrator:
    """
    S.W.A.R.M. TemporalLibrarian adapted for Sovereign OS.
    Operates on .forge/ state files rather than in-memory nx.Graph.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self._kg   = _load_kg()
        self._hyp  = _load_hypothesis()

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    @property
    def nodes(self) -> dict:
        return self._kg["nodes"]

    @property
    def edges(self) -> list:
        return self._kg["edges"]

    def _edge_exists(self, source: str, target: str) -> Optional[dict]:
        for e in self.edges:
            if (e["source"] == source and e["target"] == target) or \
               (e["source"] == target and e["target"] == source):
                return e
        return None

    # ── Temporal Mutation ────────────────────────────────────────────────────
    def handle_temporal_mutation(self, subject: str, relation: str, new_object_value: str) -> bool:
        """
        For mutable relations: update in-place rather than accumulating contradictions.
        Returns True if mutation was handled (caller should not also ingest normally).
        """
        if relation not in MUTABLE_RELATIONS:
            return False

        for e in self.edges:
            if e.get("source") == subject and e.get("relation") == relation:
                old_val = e["target"]
                if old_val == new_object_value:
                    return True  # unchanged
                self._log(f"   [🕰️ MUTATION] [{subject}].{relation}: [{old_val}] → [{new_object_value}]")
                e["target"]    = new_object_value
                e["timestamp"] = time.time()
                _log_audit("temporal_mutation", {
                    "subject": subject, "relation": relation,
                    "old": old_val, "new": new_object_value,
                })
                return True
        return False

    # ── Triangle Protocol ────────────────────────────────────────────────────
    def triangle_protocol(self, source: str, target: str) -> tuple[bool, str, float]:
        """
        Checks whether source↔target forms a rigid 2-simplex with existing knowledge.

        Valid triangle = ANY of:
          (a) shared neighbor exists in verified graph (structural closure)
          (b) cosine_similarity(vec_source, vec_target) > density threshold

        Returns (is_valid, reason, similarity_score)
        """
        nodes = self.nodes

        # Ensure both nodes exist (add with random geometry if novel)
        for nid in [source, target]:
            if nid not in nodes:
                nodes[nid] = {
                    "weight": 0.236,
                    "weight_fixed": 236000,
                    "semantic_density": "NOMINAL",
                    "audio_resonance": "432.00 Hz",
                    "visual_geometry": {
                        "x": float(np.random.rand()),
                        "y": float(np.random.rand()),
                        "z": float(np.random.rand() * 0.2 - 0.1),
                    },
                    "z3_status": 1,
                    "p_score_fixed": 900_000,
                    "hd_fixed": 100_000,
                    "description": f"Auto-registered novel node: {nid}",
                    "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                self._log(f"   [🌱 NOVEL NODE] Registered: {nid}")

        vec_s = node_to_vector(nodes[source])
        vec_t = node_to_vector(nodes[target])
        sim   = calculate_cosine_similarity(vec_s, vec_t)

        # Check for shared anchor (structural triangulation)
        neighbors_s = {e["target"] for e in self.edges if e["source"] == source}
        neighbors_s |= {e["source"] for e in self.edges if e["target"] == source}
        neighbors_t = {e["target"] for e in self.edges if e["source"] == target}
        neighbors_t |= {e["source"] for e in self.edges if e["target"] == target}
        shared = neighbors_s & neighbors_t

        # Confidence floor based on semantic density of target node
        density    = nodes[target].get("semantic_density", "NOMINAL")
        conf_floor = density_to_confidence(density)

        if len(shared) > 0:
            anchors = list(shared)[:3]
            return True, f"Triangle via shared anchors: {anchors} (sim={sim:.3f})", sim

        if sim >= conf_floor:
            return True, f"Direct cosine bridge (sim={sim:.3f} ≥ {conf_floor})", sim

        return False, f"Geometry unstable (sim={sim:.3f} < {conf_floor}, 0 shared anchors)", sim

    # ── Curiosity Protocol ───────────────────────────────────────────────────
    def curiosity_protocol(self, source: str, target: str, reason: str) -> tuple[bool, str]:
        """
        When geometry is unstable: log FATAL_BLOCKER to audit.jsonl.
        In Sovereign OS, human operator reviews audit log rather than stdin input.
        Returns (quarantine_edge, message)
        """
        self._log(f"\n   [❓ CURIOSITY] Cannot bridge [{source}] ↔ [{target}]")
        self._log(f"   Reason: {reason}")
        self._log(f"   → Edge quarantined. Review .forge/hypothesis_graph.json")
        _log_audit("curiosity_protocol", {
            "source": source, "target": target,
            "reason": reason, "status": "QUARANTINED",
            "operator_action_required": True,
        })
        return True, "QUARANTINED"

    # ── Main Ingestion ───────────────────────────────────────────────────────
    def ingest_edge(self, source: str, relation: str, target: str,
                    weight: float = 0.382, skip_triangle: bool = False) -> dict:
        """
        Main routing function. Routes incoming edge through:
          1. Temporal mutation check
          2. Duplicate check
          3. Triangle Protocol verification
          4. Accept → verified graph OR Quarantine → hypothesis_graph
        """
        self._log(f"\n[🧠 SWARM] Processing: '{source}' --({relation})--> '{target}'")

        # Step 1: Temporal mutation
        if self.handle_temporal_mutation(source, relation, target):
            self._save()
            return {"status": "MUTATED", "source": source, "relation": relation, "target": target}

        # Step 2: Duplicate check
        existing = self._edge_exists(source, target)
        if existing:
            self._log(f"   ⚠️  Edge already exists (relation={existing.get('relation')}). Skipping.")
            return {"status": "DUPLICATE", "source": source, "target": target}

        # Step 3: Triangle Protocol
        if skip_triangle:
            is_valid, reason, sim = True, "SKIP_TRIANGLE (forced)", 1.0
        else:
            is_valid, reason, sim = self.triangle_protocol(source, target)

        if is_valid:
            self._kg["edges"].append({
                "source":           source,
                "target":           target,
                "relation":         relation,
                "weight":           round(weight, 6),
                "p_score_fixed":    int(round(weight * 1_000_000)),
                "triangle_verified": True,
                "cosine_sim":       round(sim, 4),
                "triangle_reason":  reason,
                "ingested_at":      time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            self._log(f"   ✅ TRIANGLE VERIFIED: {reason}")
            _log_audit("edge_verified", {
                "source": source, "target": target, "relation": relation,
                "weight": weight, "cosine_sim": sim, "reason": reason,
            })
            self._save()
            return {"status": "VERIFIED", "source": source, "target": target,
                    "cosine_sim": sim, "reason": reason}
        else:
            # Quarantine
            _, msg = self.curiosity_protocol(source, target, reason)
            self._hyp["edges"].append({
                "source":   source,
                "target":   target,
                "relation": relation,
                "weight":   round(weight, 6),
                "decay":    5,
                "reason":   reason,
                "cosine_sim": round(sim, 4),
                "quarantined_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            })
            self._save()
            return {"status": "QUARANTINED", "source": source, "target": target,
                    "cosine_sim": sim, "reason": reason}

    def _save(self):
        _atomic_write(KG_PATH, self._kg)
        _atomic_write(HYP_PATH, self._hyp)

    def reload(self):
        """Reload both graphs from disk (after external writes)."""
        self._kg  = _load_kg()
        self._hyp = _load_hypothesis()

    def stats(self) -> dict:
        verified  = sum(1 for e in self.edges if e.get("triangle_verified", False))
        total     = len(self.edges)
        quarantined = len(self._hyp.get("edges", []))
        ratio     = round(verified / total, 4) if total else 0.0
        return {
            "nodes":          len(self.nodes),
            "edges_verified": verified,
            "edges_total":    total,
            "edges_quarantined": quarantined,
            "triangle_ratio": ratio,
        }
