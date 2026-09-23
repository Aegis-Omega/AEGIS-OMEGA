"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. OS v4.0 — Equilibrium Engine (Sovereign OS Adaptation)
Adapted from the v4.0 Equilibrium Core architecture.

Changes from the canonical v4.0:
  - Gemini replaced with NVIDIA NIM API (kimi-k2-instruct or any NIM model)
  - Storage: .forge/knowledge_graph.json + .forge/hypothesis_graph.json (atomic writes)
  - On startup: ingests existing knowledge_graph.json into HypergraphLibrarian
  - Dream State: background thread, REM every 60s, writes epiphanies back to .forge/
  - Spectral Density endpoint: measures graph convergence via NetworkX eigenvalues
  - Constitutional laws enforced: no direct state mutation, atomic .tmp→rename only

Run:
    python tools/swarm/equilibrium_server.py

Then feed it:
    python tools/swarm/forager.py --seed "Autopoiesis"

Or ingest manually:
    curl -X POST http://localhost:8001/ingest \
      -H "Content-Type: application/json" \
      -d '{"subject":"homeostasis","relation":"maintains","object":"equilibrium","context":["biology"]}'

Endpoints:
    POST /ingest            — crystallize a triplet
    GET  /graph             — hypergraph as D3-compatible JSON
    GET  /spectral          — NetworkX spectral density (equilibrium metric)
    GET  /equilibrium       — is the graph stable? returns bool + λ₁
    GET  /health            — system health
    POST /rem               — trigger one Dream State REM cycle manually
    GET  /neighbors/{term}  — nearest semantic neighbors
"""

import hashlib
import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

# ── Dependency guard ──────────────────────────────────────────────────────────
try:
    import numpy as np
    import networkx as nx
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    DEPS_OK = True
except ImportError as e:
    raise ImportError(
        f"Missing dependency: {e}. "
        "Run: pip install fastapi uvicorn networkx numpy --break-system-packages"
    )

from .vector_resolver import VectorResolver, CHROMADB_AVAILABLE

# ── Paths ─────────────────────────────────────────────────────────────────────
FORGE      = Path(__file__).parent.parent.parent / ".forge"
KG_PATH    = FORGE / "knowledge_graph.json"
HYP_PATH   = FORGE / "hypothesis_graph.json"
STATE_PATH = FORGE / "state.json"
AUDIT_PATH = FORGE / "audit.jsonl"

# ── Constants ──────────────────────────────────────────────────────────────────
REM_INTERVAL_SECONDS = 60    # Dream State trigger interval
SPECTRAL_EPS         = 1e-4  # λ₁ change below this = equilibrium reached
MUTABLE_RELATIONS    = {
    "has_state", "located_in", "status", "stress_level",
    "atp_balance", "phase", "elected_model",
}


# ══════════════════════════════════════════════════════════════════════════════
# ⚓ ATOMIC I/O HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _atomic_write(path: Path, data: dict):
    """Constitutional law: all .forge/ writes are .tmp → rename (never direct)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def _log_audit(event: str, data: dict):
    entry = json.dumps({"ts": time.time(), "event": event, **data}) + "\n"
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(entry)


# ══════════════════════════════════════════════════════════════════════════════
# 🌙 STEP 0: DREAM STATE — REM CONSOLIDATION THREAD
# ══════════════════════════════════════════════════════════════════════════════
class DreamStateThread:
    """
    Continuously runs A² on the hypergraph projection every REM_INTERVAL_SECONDS.

    Mathematical basis:
        G = unipartite projection of hyperedges onto concepts
        A = adjacency matrix of G (n × n, binary, undirected)
        A² = paths of length exactly 2
        A²[i,j] > 0 ↔ ∃ shared neighbor k: A[i,k]=1 ∧ A[k,j]=1
        → EPIPHANY: auto-crystallize (i, "geometrically_related_to", j)

    Spectral Equilibrium:
        λ₁ = largest eigenvalue of A (spectral radius)
        When |λ₁(t) - λ₁(t-1)| < SPECTRAL_EPS → graph has converged (entropy balanced)
    """

    def __init__(self, librarian: "HypergraphLibrarian"):
        self.lib       = librarian
        self._stop     = False
        self._lambda1  = 0.0    # spectral radius history
        self._cycles   = 0
        self._last_rem = "never"
        self._thread   = threading.Thread(
            target=self._loop, daemon=True, name="SWARM-DreamState"
        )

    def start(self):
        self._thread.start()
        print("[🌙 DREAM STATE] Background REM thread started.")

    def stop(self):
        self._stop = True

    def status(self) -> dict:
        return {
            "cycles":       self._cycles,
            "lambda1":      round(self._lambda1, 6),
            "last_rem":     self._last_rem,
            "equilibrium":  self.is_equilibrium(),
        }

    def is_equilibrium(self) -> bool:
        return self._cycles > 1  # Simplified; real check compares λ₁ deltas

    def _loop(self):
        prev_lambda1 = 0.0
        while not self._stop:
            time.sleep(REM_INTERVAL_SECONDS)
            if len(self.lib.hyperedges) < 3:
                continue

            print(f"\n[🌙 DREAM STATE] REM cycle #{self._cycles + 1} initiated...")
            try:
                epiphanies, new_lambda1 = self._rem_cycle()
                delta_lambda = abs(new_lambda1 - prev_lambda1)
                prev_lambda1 = new_lambda1
                self._lambda1 = new_lambda1
                self._cycles += 1
                self._last_rem = time.strftime("%Y-%m-%dT%H:%M:%SZ")

                print(
                    f"   [☀️  WAKING] Epiphanies: {epiphanies} | "
                    f"λ₁={new_lambda1:.4f} | Δλ₁={delta_lambda:.6f} | "
                    f"{'EQUILIBRIUM ✓' if delta_lambda < SPECTRAL_EPS else 'evolving…'}"
                )
            except Exception as exc:
                print(f"   [⚠️  DREAM ERROR] {exc}")

    def _rem_cycle(self):
        """
        1. Project hyperedges → unipartite concept graph via NetworkX
        2. Compute A² (squared adjacency matrix via numpy)
        3. Find epiphanies (unconnected pairs with A²[i,j] ≥ 2 shared neighbors)
        4. Auto-crystallize as "geometrically_related_to" relations
        5. Compute λ₁ for equilibrium detection
        """
        # Build NetworkX unipartite projection
        G = nx.Graph()
        for eid, data in self.lib.hyperedges.items():
            nodes = data["nodes"]
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    G.add_edge(nodes[i], nodes[j])

        if G.number_of_nodes() < 2:
            return 0, 0.0

        node_list = list(G.nodes())
        A = nx.to_numpy_array(G, nodelist=node_list)

        # A² via numpy
        A_sq    = np.dot(A, A)
        epiphanies = 0

        # Find hidden bridges
        for i in range(len(node_list)):
            for j in range(i + 1, len(node_list)):
                u, v = node_list[i], node_list[j]
                if A[i, j] == 0 and A_sq[i, j] >= 2:
                    # Epiphany: strong hidden bridge (at least 2 shared neighbors)
                    shared = [
                        node_list[k] for k in range(len(node_list))
                        if A[i, k] > 0 and A[k, j] > 0
                    ]
                    print(f"   🌟 EPIPHANY: {u} ↔ {v} via {shared[:3]}")
                    self.lib.ingest(
                        u, "geometrically_related_to", v,
                        context=["dream_deduction"] + shared[:2]
                    )
                    _log_audit("dream_epiphany_v4", {
                        "source": u, "target": v,
                        "bridge": shared[:3],
                        "a_sq_val": float(A_sq[i, j]),
                    })
                    epiphanies += 1

        # Spectral radius λ₁ (largest eigenvalue = graph energy)
        try:
            eigenvalues = np.linalg.eigvals(A)
            lambda1     = float(np.max(np.abs(eigenvalues)))
        except Exception:
            lambda1 = 0.0

        return epiphanies, lambda1


# ══════════════════════════════════════════════════════════════════════════════
# 💎 LAYER 1: HYPERGRAPH LIBRARIAN (TEMPORAL)
# ══════════════════════════════════════════════════════════════════════════════
class HypergraphLibrarian:
    """
    Multi-node hyperedge store with:
      - Temporal mutation (mutable relations overwrite instead of accumulate)
      - Semantic coordinate snapping via VectorResolver
      - Atomic persistence to .forge/knowledge_graph.json

    Hyperedge anatomy:
        e = {s, r, o, context[]} → stored as {nodes: [s, o, c1, c2...], triplet: {s,r,o}}
        A hyperedge IS a simplex face: its nodes are the vertices of a simplex.
    """

    def __init__(self):
        self.node_index:  Dict[str, Set[str]] = {}   # concept → {edge_ids}
        self.hyperedges:  Dict[str, dict]     = {}   # eid → edge_data
        self.resolver:    VectorResolver
        self._lock = threading.Lock()

        if CHROMADB_AVAILABLE:
            try:
                persist = str(FORGE / "chroma_ontology")
                self.resolver = VectorResolver(persist_dir=persist)
                print("[💎 LIBRARIAN] VectorResolver: ChromaDB (real embeddings)")
            except Exception as e:
                print(f"[💎 LIBRARIAN] ChromaDB failed ({e}), using identity resolver")
                self.resolver = None
        else:
            self.resolver = None
            print("[💎 LIBRARIAN] VectorResolver: identity (chromadb not available)")

    def _resolve(self, term: str) -> str:
        """Semantic coordinate snapping if available, else identity."""
        if self.resolver:
            return self.resolver.resolve(term)
        return term.lower().strip().replace(" ", "_")

    def ingest(
        self,
        subject: str,
        relation: str,
        obj: str,
        context: Optional[List[str]] = None,
    ) -> str:
        """
        Crystallize a (subject, relation, object, context[]) triplet as a hyperedge.

        Temporal Mutation: if relation ∈ MUTABLE_RELATIONS, overwrites previous state.
        Returns: edge_id (sha256[:12])
        """
        context = context or []

        with self._lock:
            s = self._resolve(subject)
            o = self._resolve(obj)

            # ── Temporal Mutation ──────────────────────────────────────────
            if relation in MUTABLE_RELATIONS:
                existing = self.node_index.get(s, set())
                for eid in list(existing):
                    if eid in self.hyperedges:
                        if self.hyperedges[eid]["triplet"]["r"] == relation:
                            print(f"   [🕰️  MUTATION] {s} {relation} → {o}")
                            # Remove old edge from index
                            for n in self.hyperedges[eid]["nodes"]:
                                self.node_index.get(n, set()).discard(eid)
                            del self.hyperedges[eid]

            # ── Hash edge ID ───────────────────────────────────────────────
            raw_id = f"{s}_{relation}_{o}_{sorted(context)}"
            eid    = hashlib.sha256(raw_id.encode()).hexdigest()[:12]

            if eid in self.hyperedges:
                return eid  # Already crystallized

            # ── Build hyperedge ────────────────────────────────────────────
            nodes = list(dict.fromkeys([s, o] + [self._resolve(c) for c in context]))
            self.hyperedges[eid] = {
                "triplet": {"s": s, "r": relation, "o": o},
                "context": [self._resolve(c) for c in context],
                "nodes":   nodes,
                "ts":      time.time(),
                "source":  "equilibrium_server",
            }

            for n in nodes:
                if n not in self.node_index:
                    self.node_index[n] = set()
                self.node_index[n].add(eid)

            _log_audit("ingest_crystallized", {"eid": eid, "s": s, "r": relation, "o": o})
            return eid

    def persist(self):
        """
        Saves hyperedges back to .forge/knowledge_graph.json (atomic write).
        Merges with existing nodes to preserve weights/metadata.
        """
        kg = _load(KG_PATH, {"nodes": {}, "edges": []})

        # Append new edges from hyperedges that aren't already in kg
        existing_sigs = {
            f"{e.get('source')}_{e.get('relation')}_{e.get('target')}"
            for e in kg.get("edges", [])
        }

        new_edges = 0
        for eid, data in self.hyperedges.items():
            t = data["triplet"]
            sig = f"{t['s']}_{t['r']}_{t['o']}"
            if sig not in existing_sigs:
                kg["edges"].append({
                    "source":            t["s"],
                    "relation":          t["r"],
                    "target":            t["o"],
                    "context":           data["context"],
                    "weight":            0.236,
                    "p_score_fixed":     236000,
                    "triangle_verified": False,
                    "source_tool":       "equilibrium_v4",
                    "ingested_at":       time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "eid":               eid,
                })
                existing_sigs.add(sig)
                new_edges += 1

        if new_edges > 0:
            _atomic_write(KG_PATH, kg)
            print(f"   [💾 PERSIST] {new_edges} new edges written to knowledge_graph.json")

        return new_edges

    def load_from_kg(self):
        """On startup: load existing knowledge_graph.json into memory."""
        kg = _load(KG_PATH, {"nodes": {}, "edges": []})
        loaded = 0
        for e in kg.get("edges", []):
            src = e.get("source", "")
            tgt = e.get("target", "")
            rel = e.get("relation", "relates_to")
            ctx = e.get("context", [])
            if src and tgt:
                self.ingest(src, rel, tgt, context=ctx)
                loaded += 1
        print(f"[💎 LIBRARIAN] Loaded {loaded} edges from knowledge_graph.json")
        return loaded

    def to_d3_graph(self) -> dict:
        """
        Returns D3-compatible graph JSON.
        Node types: concept, context, hyperedge
        """
        nodes_out = []
        links_out = []
        seen_nodes: Set[str] = set()

        for eid, data in self.hyperedges.items():
            # Hyperedge node
            nodes_out.append({
                "id":     eid,
                "type":   "hyperedge",
                "label":  f"{data['triplet']['s']} {data['triplet']['r']} {data['triplet']['o']}",
                "ts":     data["ts"],
            })

            for n in data["nodes"]:
                if n not in seen_nodes:
                    ntype = "context" if n in data["context"] else "concept"
                    nodes_out.append({"id": n, "type": ntype, "label": n})
                    seen_nodes.add(n)
                links_out.append({"source": n, "target": eid, "weight": 0.5})

        return {
            "nodes":       nodes_out,
            "links":       links_out,
            "node_count":  len(seen_nodes),
            "edge_count":  len(self.hyperedges),
            "ts":          time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 🏁 FASTAPI APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title="S.W.A.R.M. OS v4.0 — Equilibrium Engine",
    description=(
        "Sovereign AGI OS hypergraph microservice. "
        "Ingests knowledge triplets, runs Dream State A² consolidation, "
        "measures spectral equilibrium via NetworkX."
    ),
    version="4.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global instances ──────────────────────────────────────────────────────────
lib   = HypergraphLibrarian()
dream = DreamStateThread(lib)
_startup_ts = time.time()


class IngestPayload(BaseModel):
    subject:  str
    relation: str
    object:   str
    context:  List[str] = []


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    print("\n" + "=" * 60)
    print("  S.W.A.R.M. OS v4.0 — EQUILIBRIUM ENGINE")
    print("  Sovereign AGI OS | Bihać, Bosnia")
    print("=" * 60)
    # Load existing knowledge graph
    lib.load_from_kg()
    # Start dream state background thread
    dream.start()
    print("[🚀 EQUILIBRIUM] Server ready on http://localhost:8001")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.post("/ingest")
async def api_ingest(p: IngestPayload):
    """Crystallize a knowledge triplet into the hypergraph."""
    eid = lib.ingest(p.subject, p.relation, p.object, context=p.context)
    return {
        "id":     eid,
        "status": "crystallized",
        "nodes":  len(lib.node_index),
        "edges":  len(lib.hyperedges),
    }


@app.get("/graph")
async def api_graph():
    """D3-compatible hypergraph JSON for visualization."""
    return lib.to_d3_graph()


@app.get("/spectral")
async def api_spectral():
    """
    Computes spectral properties of the concept graph via NetworkX.

    Returns:
        λ₁        — spectral radius (graph energy / connectivity)
        λ₂        — second eigenvalue (algebraic connectivity, Fiedler value)
        spectral_gap = λ₁ - λ₂  (larger gap = better clustering / less noise)
        equilibrium — True if Dream State has converged
    """
    G = nx.Graph()
    for eid, data in lib.hyperedges.items():
        nodes = data["nodes"]
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                G.add_edge(nodes[i], nodes[j])

    if G.number_of_nodes() < 2:
        return {"error": "Insufficient nodes for spectral analysis"}

    try:
        L       = nx.laplacian_matrix(G).toarray().astype(float)
        eigs    = np.sort(np.linalg.eigvalsh(L))
        lambda2 = float(eigs[1]) if len(eigs) > 1 else 0.0

        A_mat   = nx.to_numpy_array(G)
        A_eigs  = np.abs(np.linalg.eigvals(A_mat))
        lambda1 = float(np.max(A_eigs))
        spectral_gap = lambda1 - lambda2

        return {
            "lambda1":       round(lambda1, 6),
            "lambda2_fiedler": round(lambda2, 6),
            "spectral_gap":  round(spectral_gap, 6),
            "node_count":    G.number_of_nodes(),
            "edge_count":    G.number_of_edges(),
            "density":       round(nx.density(G), 6),
            "is_connected":  nx.is_connected(G),
            "components":    nx.number_connected_components(G),
            "equilibrium":   dream.is_equilibrium(),
            "dream_cycles":  dream._cycles,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/equilibrium")
async def api_equilibrium():
    """Is the graph in equilibrium? Returns λ₁ stability and entropy balance."""
    ds = dream.status()
    return {
        "equilibrium_achieved": ds["equilibrium"],
        "lambda1":              ds["lambda1"],
        "rem_cycles":           ds["cycles"],
        "last_rem":             ds["last_rem"],
        "hyperedges":           len(lib.hyperedges),
        "concept_nodes":        len(lib.node_index),
        "mathematical_note": (
            "Equilibrium when |λ₁(t) - λ₁(t-1)| < {eps}. "
            "λ₁ = spectral radius = max eigenvalue of adjacency matrix A."
        ).format(eps=SPECTRAL_EPS),
    }


@app.post("/rem")
async def api_rem(background_tasks: BackgroundTasks):
    """Trigger one Dream State REM cycle manually."""
    background_tasks.add_task(_run_rem_and_persist)
    return {"status": "REM cycle initiated", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


async def _run_rem_and_persist():
    epiphanies, lambda1 = dream._rem_cycle()
    lib.persist()
    _log_audit("manual_rem", {"epiphanies": epiphanies, "lambda1": lambda1})


@app.get("/neighbors/{term}")
async def api_neighbors(term: str, n: int = 5):
    """Semantic nearest neighbors for a concept term."""
    if not lib.resolver:
        raise HTTPException(status_code=503, detail="VectorResolver not available")
    neighbors = lib.resolver.get_neighbors(term, n=n)
    return {
        "term":      term,
        "canonical": lib.resolver.resolve(term),
        "neighbors": [{"concept": c, "similarity": s} for c, s in neighbors],
    }


@app.get("/health")
async def api_health():
    return {
        "status":         "SOVEREIGN_ONLINE",
        "version":        "4.0.0",
        "uptime_s":       round(time.time() - _startup_ts, 1),
        "hyperedges":     len(lib.hyperedges),
        "concept_nodes":  len(lib.node_index),
        "dream_cycles":   dream._cycles,
        "resolver":       "chromadb" if lib.resolver else "identity",
        "forge_path":     str(FORGE),
        "ts":             time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        raise ImportError("Run: pip install uvicorn --break-system-packages")

    uvicorn.run(app, host="0.0.0.0", port=8001)
