#!/usr/bin/env python3
"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.

S.W.A.R.M. Core Engine v6.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━
PhotonicResolver — ChromaDB-backed ontology (384-dim cosine space).
QuantumManifold  — hypergraph orchestrator with z-level hierarchy and Dream State.

Z-Level Hierarchy (frequency = continuous HD score per node):
  z=4  SOVEREIGN_EGO     523 Hz  HD≈0.00  identity anchor
  z=3  VECTOR_RESOLUTION 415 Hz  HD≈0.15  verified, semantically grounded
  z=2  EQUILIBRATION     330 Hz  HD≈0.35  working memory
  z=1  RADIATION         294 Hz  HD≈0.65  decaying hypotheses
  z=0  INERTIA           262 Hz  HD≈0.90  new unverified concepts

Constitutional law: all .forge/ writes are .tmp → os.replace() — never direct.
"""

import hashlib
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np

try:
    import networkx as nx
    NX_OK = True
except ImportError:
    NX_OK = False

# ChromaDB + sentence-transformers (optional — fall back gracefully)
_EMBED_MODEL = None
CHROMA_OK    = False

def _get_embed_model():
    global _EMBED_MODEL, CHROMA_OK
    if _EMBED_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("[SWARM CORE] Loading semantic model (all-MiniLM-L6-v2)...")
            _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            print("[SWARM CORE] Model loaded.")
            CHROMA_OK = True
        except Exception as e:
            print(f"[SWARM CORE] Failed to load model: {e}")
            CHROMA_OK = False
    return _EMBED_MODEL

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    # We delay loading SentenceTransformer to _get_embed_model()
    CHROMA_OK = True
except Exception as e:
    print(f"[SWARM CORE] ChromaDB unavailable ({e}). Falling back to dict mode.")
    CHROMA_OK = False

from config import (
    Z_LEVELS, Z_HD_MAP, SWARM_SELF_AXIOM,
    SIMILARITY_THRESHOLD, ETA_DEFAULT, EMBED_DIM,
    FORGE_DIR, AUDIT_FILE, VERSION, MAX_EVENTS,
)


# ══════════════════════════════════════════════════════════════════════════════
# ATOMIC I/O
# ══════════════════════════════════════════════════════════════════════════════
def _atomic_write(path: Path, data: dict):
    """Constitutional law: .tmp → os.replace()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def _audit(forge_path: Path, event: str, data: dict):
    """Append one audit entry. Never overwrites — append-only."""
    entry = json.dumps({
        "ts":    datetime.now(timezone.utc).isoformat(),
        "event": event,
        **data,
    }) + "\n"
    audit_path = forge_path / "swarm_audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "a", encoding="utf-8") as f:
        f.write(entry)


# ══════════════════════════════════════════════════════════════════════════════
# PHOTONIC RESOLVER
# ChromaDB-backed ontology. 384-dim cosine similarity.
# Falls back to pure dict if ChromaDB is unavailable.
# ══════════════════════════════════════════════════════════════════════════════
class PhotonicResolver:
    """
    Resolves terms to canonical concept nodes using semantic similarity.

    Observer Effect: calling `resolve(term)` mutates the node's phase by eta.
    This means every query subtly shifts the manifold — cognition changes
    the observer as much as the observed.
    """

    def __init__(self, forge_path: Path):
        self.forge_path = forge_path
        self._nodes: Dict[str, dict] = {}   # term → {z, phase, hz, created_at}
        self._chroma_client = None
        self._collection = None

        # Boot the identity anchor at z=4
        self._ensure_self_axiom()

        # Try ChromaDB
        if CHROMA_OK:
            try:
                chroma_dir = str(forge_path / "chroma_ontology")
                self._chroma_client = chromadb.PersistentClient(
                    path=chroma_dir,
                    settings=ChromaSettings(anonymized_telemetry=False),
                )
                self._collection = self._chroma_client.get_or_create_collection(
                    name="swarm_ontology",
                    metadata={"hnsw:space": "cosine"},
                )
                print("[PhotonicResolver] ChromaDB ready.")
            except Exception as e:
                print(f"[PhotonicResolver] ChromaDB unavailable ({e}). Dict mode.")
                self._chroma_client = None
                self._collection = None

    def _ensure_self_axiom(self):
        if SWARM_SELF_AXIOM not in self._nodes:
            self._nodes[SWARM_SELF_AXIOM] = {
                "id":         SWARM_SELF_AXIOM,
                "z":          4,
                "phase":      0.0,
                "hz":         Z_LEVELS[4]["hz"],
                "hd":         Z_HD_MAP[4],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

    def _embed(self, term: str) -> Optional[List[float]]:
        model = _get_embed_model()
        if model is None:
            return None
        try:
            vec = model.encode(term).tolist()
            return vec
        except Exception:
            return None

    def resolve(self, term: str) -> dict:
        """
        Find existing concept by cosine similarity (threshold 0.22)
        or create a new one at z=0 (INERTIA).
        OBSERVER EFFECT: mutates the node's phase by ETA_DEFAULT.
        """
        term_lower = term.lower().strip()

        # Exact match
        if term_lower in self._nodes:
            self.mutate_phase(term_lower, ETA_DEFAULT, resonance=Z_LEVELS[
                self._nodes[term_lower]["z"]]["hz"] / 523.0)
            return self._nodes[term_lower]

        # ChromaDB semantic search
        if self._collection is not None:
            vec = self._embed(term_lower)
            if vec and self._collection.count() > 0:
                try:
                    result = self._collection.query(
                        query_embeddings=[vec],
                        n_results=1,
                        include=["distances", "ids"],
                    )
                    if result["ids"][0]:
                        dist = result["distances"][0][0]
                        if dist < SIMILARITY_THRESHOLD:
                            existing_id = result["ids"][0][0]
                            if existing_id in self._nodes:
                                self.mutate_phase(existing_id, ETA_DEFAULT,
                                                  resonance=Z_LEVELS[self._nodes[existing_id]["z"]]["hz"] / 523.0)
                                return self._nodes[existing_id]
                except Exception:
                    pass

        # Create new node at z=0 (INERTIA)
        node = {
            "id":         term_lower,
            "z":          0,
            "phase":      0.0,
            "hz":         Z_LEVELS[0]["hz"],
            "hd":         Z_HD_MAP[0],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._nodes[term_lower] = node

        # Index in ChromaDB
        if self._collection is not None:
            vec = self._embed(term_lower)
            if vec:
                try:
                    self._collection.add(
                        ids=[term_lower],
                        embeddings=[vec],
                        metadatas=[{"z": 0}],
                    )
                except Exception:
                    pass

        return node

    def mutate_phase(self, term: str, eta: float, resonance: float):
        """
        OBSERVER EFFECT — querying mutates the phase of the node.
        phase += eta * resonance
        Phase is in radians; it wraps around [0, 2π].
        """
        if term in self._nodes:
            self._nodes[term]["phase"] = (
                self._nodes[term]["phase"] + eta * resonance
            ) % (2 * math.pi)

    def promote_z(self, term: str):
        """Promote a node up one z-level (max z=3; z=4 reserved for SOVEREIGN_EGO)."""
        if term in self._nodes:
            current_z = self._nodes[term]["z"]
            new_z = min(current_z + 1, 3)  # cap at 3; only SWARM_SELF_AXIOM at 4
            self._nodes[term]["z"]  = new_z
            self._nodes[term]["hz"] = Z_LEVELS[new_z]["hz"]
            self._nodes[term]["hd"] = Z_HD_MAP[new_z]
            # Update ChromaDB metadata
            if self._collection is not None:
                try:
                    self._collection.update(ids=[term], metadatas=[{"z": new_z}])
                except Exception:
                    pass

    def all_nodes(self) -> List[dict]:
        return list(self._nodes.values())

    def get_node(self, term: str) -> Optional[dict]:
        return self._nodes.get(term.lower().strip())


# ══════════════════════════════════════════════════════════════════════════════
# QUANTUM MANIFOLD
# Main orchestrator. Manages hyperedges, events, dream cycles, audit log.
# ══════════════════════════════════════════════════════════════════════════════
class QuantumManifold:
    """
    The living knowledge hypergraph.

    Ingest triplets → build hyperedges → run Dream State (A²) → surface epiphanies.
    All writes are atomic. All mutations are audited.
    """

    def __init__(self, forge_path: Path = None):
        self.forge_path = forge_path or Path(".forge")
        self.forge_path.mkdir(parents=True, exist_ok=True)

        self.resolver         = PhotonicResolver(self.forge_path)
        self.hyperedges: Dict[str, dict] = {}   # edge_id → {nodes, relation, context, ts}
        self.events:     List[dict]      = []   # ring buffer, cap MAX_EVENTS
        self.epiphanies: List[dict]      = []   # all discovered epiphanies
        self.agents:     Dict[str, dict] = {}   # agent_id → {last_seen, type}
        self.dream_cycles: int           = 0
        self._eta = ETA_DEFAULT

        _audit(self.forge_path, "MANIFOLD_BOOT", {"version": VERSION})

    # ── INGEST ────────────────────────────────────────────────────────────────
    def ingest(self, subject: str, relation: str, obj: str,
               context: List[str] = None) -> str:
        """
        Crystallize a semantic triplet into the hypergraph.
        Returns the edge_id.
        """
        context = context or []
        edge_id = str(uuid.uuid4())[:8]

        # Resolve (or create) both nodes
        s_node = self.resolver.resolve(subject)
        o_node = self.resolver.resolve(obj)

        self.hyperedges[edge_id] = {
            "id":       edge_id,
            "nodes":    [s_node["id"], o_node["id"]],
            "relation": relation,
            "context":  context,
            "ts":       datetime.now(timezone.utc).isoformat(),
        }

        _audit(self.forge_path, "INGEST", {
            "edge_id": edge_id,
            "subject": s_node["id"], "relation": relation, "object": o_node["id"],
        })
        return edge_id

    # ── DREAM STATE ───────────────────────────────────────────────────────────
    def dream_state_cycle(self) -> int:
        """
        A² matrix scan over the hypergraph unipartite projection.

        Algorithm:
          1. Build NetworkX unipartite graph from all hyperedges
          2. A = adjacency matrix (binary, undirected)
          3. A² = A · A   (numpy matrix multiply)
          4. Epiphany condition: A[i,j]=0  AND  A²[i,j] >= 2
          5. Crystallize epiphany as (i, "geometrically_related_to", j)
          6. Promote both nodes up one z-level
          7. Compute λ₁ (spectral radius) for equilibrium check

        Returns: number of new epiphanies found.
        """
        self.dream_cycles += 1
        _audit(self.forge_path, "DREAM_START", {"cycle": self.dream_cycles})

        if len(self.hyperedges) < 2:
            _audit(self.forge_path, "DREAM_END",
                   {"cycle": self.dream_cycles, "epiphanies": 0, "reason": "too_few_edges"})
            return 0

        # Build unipartite graph
        G_nodes: List[str] = []
        G_edges: List[tuple] = []
        for he in self.hyperedges.values():
            ns = he["nodes"]
            for i in range(len(ns)):
                for j in range(i + 1, len(ns)):
                    u, v = ns[i], ns[j]
                    if u not in G_nodes: G_nodes.append(u)
                    if v not in G_nodes: G_nodes.append(v)
                    G_edges.append((u, v))

        if len(G_nodes) < 2:
            return 0

        # Adjacency matrix
        idx = {n: i for i, n in enumerate(G_nodes)}
        n = len(G_nodes)
        A = np.zeros((n, n), dtype=float)
        for u, v in G_edges:
            A[idx[u], idx[v]] = 1
            A[idx[v], idx[u]] = 1

        A_sq = np.dot(A, A)

        new_epiphanies = 0
        existing_pairs = {(he["nodes"][0], he["nodes"][1])
                          for he in self.hyperedges.values()
                          if len(he["nodes"]) == 2}
        existing_pairs |= {(b, a) for a, b in existing_pairs}

        for i in range(n):
            for j in range(i + 1, n):
                u, v = G_nodes[i], G_nodes[j]
                if A[i, j] == 0 and A_sq[i, j] >= 2:
                    if (u, v) not in existing_pairs:
                        # Fire epiphany
                        ep_id = self.ingest(u, "geometrically_related_to", v,
                                            context=["dream_state", f"cycle_{self.dream_cycles}"])
                        ep_event = {
                            "id":         ep_id,
                            "type":       "EPIPHANY",
                            "nodes":      [u, v],
                            "cycle":      self.dream_cycles,
                            "strength":   float(A_sq[i, j]),
                            "ts":         datetime.now(timezone.utc).isoformat(),
                            "content":    f"Hidden bridge: {u} ↔ {v}  (A²={A_sq[i,j]:.0f})",
                        }
                        self.epiphanies.append(ep_event)
                        existing_pairs.add((u, v))
                        existing_pairs.add((v, u))
                        new_epiphanies += 1

                        # Promote both nodes
                        self.resolver.promote_z(u)
                        self.resolver.promote_z(v)

        # Spectral radius λ₁
        lambda1 = 0.0
        try:
            eigenvalues = np.linalg.eigvalsh(A)
            lambda1 = float(np.max(np.abs(eigenvalues)))
        except Exception:
            pass

        _audit(self.forge_path, "DREAM_END", {
            "cycle":      self.dream_cycles,
            "epiphanies": new_epiphanies,
            "lambda1":    round(lambda1, 6),
            "nodes":      n,
        })
        return new_epiphanies

    # ── STATE SNAPSHOT ────────────────────────────────────────────────────────
    def get_state_snapshot(self) -> dict:
        """
        Full manifold state for WebSocket SNAPSHOT and REST /state.
        Includes normalized nodes[] and edges[] arrays.
        """
        nodes = []
        for node in self.resolver.all_nodes():
            nodes.append({
                "id":    node["id"],
                "z":     node["z"],
                "phase": round(node["phase"], 4),
                "hz":    node["hz"],
                "hd":    node["hd"],
            })

        edges = []
        for he in self.hyperedges.values():
            ns = he["nodes"]
            if len(ns) >= 2:
                edges.append({
                    "a":        ns[0],
                    "b":        ns[1],
                    "relation": he["relation"],
                    "context":  he["context"],
                    "epiphany": "dream_state" in he.get("context", []),
                })

        return {
            "ts":                    datetime.now(timezone.utc).isoformat(),
            "version":               VERSION,
            "total_hyperedges":      len(self.hyperedges),
            "dream_cycles_completed": self.dream_cycles,
            "total_epiphanies":      len(self.epiphanies),
            "ego_id":                SWARM_SELF_AXIOM,
            "ego_z_level":           4,
            "eta":                   self._eta,
            "nodes":                 nodes,
            "edges":                 edges,
        }

    # ── EVENT LOG ─────────────────────────────────────────────────────────────
    def add_event(self, agent_id: str, event_type: str,
                  content: str, cycle: int = 0) -> dict:
        event = {
            "id":        str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id":  agent_id,
            "type":      event_type,
            "content":   content,
            "cycle":     cycle,
        }
        self.events.append(event)
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]
        _audit(self.forge_path, "EVENT", {
            "agent_id": agent_id, "type": event_type, "content": content[:120],
        })
        return event

    # ── AGENT REGISTRY ────────────────────────────────────────────────────────
    def register_agent(self, agent_id: str, agent_type: str = "UNKNOWN"):
        self.agents[agent_id] = {
            "id":        agent_id,
            "type":      agent_type,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

    # ── AUDIT LOG ─────────────────────────────────────────────────────────────
    def read_audit(self, last_n: int = 50) -> List[dict]:
        audit_path = self.forge_path / "swarm_audit.jsonl"
        if not audit_path.exists():
            return []
        lines = audit_path.read_text(encoding="utf-8").splitlines()
        entries = []
        for line in lines[-last_n:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
        return entries

    # ── SPECTRAL DENSITY ──────────────────────────────────────────────────────
    def spectral_state(self) -> dict:
        """Compute λ₁ (spectral radius) for equilibrium detection."""
        if not NX_OK or len(self.hyperedges) < 2:
            return {"lambda1": 0.0, "stable": False, "rem_cycles": self.dream_cycles}
        try:
            G = None
            try:
                import networkx as nx
                G = nx.Graph()
                for he in self.hyperedges.values():
                    ns = he["nodes"]
                    for i in range(len(ns)):
                        for j in range(i + 1, len(ns)):
                            G.add_edge(ns[i], ns[j])
            except Exception:
                pass
            if G is None or G.number_of_nodes() < 2:
                return {"lambda1": 0.0, "stable": False, "rem_cycles": self.dream_cycles}
            A = nx.to_numpy_array(G)
            eigenvalues = np.linalg.eigvalsh(A)
            lambda1 = float(np.max(np.abs(eigenvalues)))
            return {
                "lambda1":    round(lambda1, 6),
                "stable":     self.dream_cycles > 1,
                "rem_cycles": self.dream_cycles,
                "node_count": G.number_of_nodes(),
                "edge_count": G.number_of_edges(),
            }
        except Exception:
            return {"lambda1": 0.0, "stable": False, "rem_cycles": self.dream_cycles}
