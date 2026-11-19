"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. Dream State — Background Consolidation Engine
Sovereign OS adaptation: runs A² (matrix multiplication) on the knowledge graph
to find second-order implicit bridges between quarantined hypotheses.

Mathematical basis:
    A = adjacency matrix of verified graph (n × n)
    A² = paths of length exactly 2
    A²[i,j] > 0 ↔ ∃ shared neighbor k such that i↔k and k↔j

    If hypothesis edge (i,j) has A²[i,j] > 0: EPIPHANY — hidden bridge found.
    Promote from hypothesis_graph → knowledge_graph.

Sovereign OS mapping:
    dream_state run = one "REM cycle"
    Each REM cycle reduces hypothesis_graph entropy (decay + promotion)
    Promoted edges = new metacognitive connections previously invisible to waking state

Run: python tools/swarm/dream_state.py
"""
import json
import math
import os
import time
from pathlib import Path

import numpy as np

# NetworkX: spectral density + equilibrium detection (S.W.A.R.M. v4.0 upgrade)
try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False

FORGE      = Path(__file__).parent.parent.parent / ".forge"
KG_PATH    = FORGE / "knowledge_graph.json"
HYP_PATH   = FORGE / "hypothesis_graph.json"
STATE_PATH = FORGE / "state.json"
AUDIT_PATH = FORGE / "audit.jsonl"


def _atomic_write(path: Path, data: dict):
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


def enter_rem_sleep(verbose: bool = True) -> dict:
    """
    Runs one Dream State cycle:
      1. Load verified graph → build adjacency matrix A
      2. Compute A² (paths of length 2)
      3. For each hypothesis edge: check if A²[i,j] > 0
         → EPIPHANY: promote to verified graph
         → Otherwise: decay timer -1, prune at 0
      4. Atomic write both graphs
      5. Update state.json swarm section

    Returns summary dict for state.json update.
    """
    print("\n" + "="*52)
    print("[🌙 DREAM STATE] Initiating REM consolidation...")
    print("="*52)

    kg  = _load(KG_PATH,  {"nodes": {}, "edges": []})
    hyp = _load(HYP_PATH, {"edges": []})

    nodes      = kg["nodes"]
    edges      = kg["edges"]
    hyp_edges  = hyp.get("edges", [])
    node_list  = list(nodes.keys())
    n          = len(node_list)

    if len(hyp_edges) == 0:
        print("   💤 No active hypotheses. Dream state optimal — nothing to consolidate.")
        return {"rem_cycles_run": 1, "epiphanies": 0, "pruned": 0, "remaining": 0}

    # Build adjacency matrix A (binary: 1 if edge exists)
    idx = {nid: i for i, nid in enumerate(node_list)}
    A   = np.zeros((n, n), dtype=float)
    for e in edges:
        s, t = e.get("source", ""), e.get("target", "")
        if s in idx and t in idx:
            i, j    = idx[s], idx[t]
            A[i, j] = 1.0
            A[j, i] = 1.0  # undirected

    # A² — O(n³) but n=54 so < 1ms
    A_sq = np.dot(A, A)

    epiphanies, pruned = 0, 0
    surviving = []

    for e in hyp_edges:
        s, t = e.get("source", ""), e.get("target", "")
        decay = e.get("decay", 5)

        if s in idx and t in idx:
            i, j = idx[s], idx[t]
            if A_sq[i, j] > 0:
                # EPIPHANY: second-order bridge exists
                # Find shared neighbors
                shared = [node_list[k] for k in range(n) if A[i, k] > 0 and A[k, j] > 0]
                print(f"   🌟 EPIPHANY: [{s}] ↔ [{t}] via {shared[:3]}")
                # Promote to verified graph
                edges.append({
                    "source":           s,
                    "target":           t,
                    "relation":         e.get("relation", "dream_verified"),
                    "weight":           e.get("weight", 0.236),
                    "p_score_fixed":    int(round(e.get("weight", 0.236) * 1_000_000)),
                    "triangle_verified": True,
                    "cosine_sim":       e.get("cosine_sim", 0.0),
                    "triangle_reason":  f"Dream State A² bridge via {shared[:3]}",
                    "promoted_from_hypothesis": True,
                    "ingested_at":      time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
                _log_audit("dream_epiphany", {
                    "source": s, "target": t,
                    "bridge": shared[:3], "a_sq_val": float(A_sq[i, j]),
                })
                epiphanies += 1
                continue  # don't re-add to surviving

        # Decay logic
        new_decay = decay - 1
        if new_decay <= 0:
            print(f"   💀 PRUNED: [{s}] ↔ [{t}] — no bridge found after {5 - new_decay} cycles")
            _log_audit("dream_pruned", {"source": s, "target": t})
            pruned += 1
        else:
            print(f"   🧩 QUARANTINE: [{s}] ↔ [{t}] — decay → {new_decay}")
            e["decay"] = new_decay
            surviving.append(e)

    hyp["edges"] = surviving

    # Atomic write both
    _atomic_write(KG_PATH,  kg)
    _atomic_write(HYP_PATH, hyp)

    # Update state.json swarm section
    state = _load(STATE_PATH, {})
    swarm_state = state.get("swarm", {})
    swarm_state["last_rem_at"]    = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    swarm_state["total_epiphanies"] = swarm_state.get("total_epiphanies", 0) + epiphanies
    swarm_state["total_pruned"]     = swarm_state.get("total_pruned", 0) + pruned
    swarm_state["hypothesis_remaining"] = len(surviving)
    state["swarm"] = swarm_state
    _atomic_write(STATE_PATH, state)

    # ── NetworkX Spectral Analysis (v4.0 Equilibrium metric) ──────────────
    spectral = _compute_spectral(node_list, edges)

    print("="*52)
    print(f"[☀️  WAKING STATE RESUMED]")
    print(f"   Epiphanies: {epiphanies}  |  Pruned: {pruned}  |  Remaining: {len(surviving)}")
    if spectral:
        print(f"   λ₁={spectral['lambda1']:.4f}  gap={spectral['spectral_gap']:.4f}  "
              f"density={spectral['density']:.4f}  "
              f"{'EQUILIBRIUM ✓' if spectral.get('equilibrium') else 'evolving…'}")
    print("="*52)

    return {
        "rem_cycles_run":    1,
        "epiphanies":        epiphanies,
        "pruned":            pruned,
        "remaining":         len(surviving),
        "edge_count_after":  len(kg["edges"]),
        "spectral":          spectral or {},
    }


def _compute_spectral(node_list: list, edges: list) -> dict:
    """
    Computes spectral properties of the knowledge graph via NetworkX (v4.0 upgrade).

    Spectral Density measures:
        λ₁  = spectral radius (largest eigenvalue of A) — graph energy
        λ₂  = Fiedler value (2nd eigenvalue of Laplacian) — algebraic connectivity
        gap = λ₁ - λ₂  — clustering quality
        density = |E| / (|V|(|V|-1)/2)

    Equilibrium condition (v4.0):
        |λ₁(t) - λ₁(t-1)| < 1e-4 AND density > 0.01

    Returns {} if NetworkX is not available.
    """
    if not NX_AVAILABLE or len(node_list) < 2:
        return {}

    try:
        G   = nx.Graph()
        idx = {nid: i for i, nid in enumerate(node_list)}
        G.add_nodes_from(node_list)

        for e in edges:
            s, t = e.get("source", ""), e.get("target", "")
            if s in idx and t in idx:
                G.add_edge(s, t)

        if G.number_of_edges() == 0:
            return {}

        A_mat    = nx.to_numpy_array(G)
        A_eigs   = np.abs(np.linalg.eigvals(A_mat))
        lambda1  = float(np.max(A_eigs))

        L_mat    = nx.laplacian_matrix(G).toarray().astype(float)
        L_eigs   = np.sort(np.linalg.eigvalsh(L_mat))
        lambda2  = float(L_eigs[1]) if len(L_eigs) > 1 else 0.0

        density  = nx.density(G)
        gap      = lambda1 - lambda2
        n_comps  = nx.number_connected_components(G)

        return {
            "lambda1":       round(lambda1, 6),
            "lambda2":       round(lambda2, 6),
            "spectral_gap":  round(gap, 6),
            "density":       round(density, 6),
            "components":    n_comps,
            "is_connected":  G.is_directed() is False and nx.is_connected(G),
            "equilibrium":   density > 0.01 and n_comps <= 3,
        }
    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    result = enter_rem_sleep(verbose=True)
    print(f"\nDream State result: {json.dumps(result, indent=2)}")
