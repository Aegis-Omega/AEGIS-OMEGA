"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. Geometry — Hypersphere utilities
Sovereign OS integration: visual_geometry {x,y,z} IS the semantic vector.
Cosine similarity between node vectors = semantic proximity on the hypersphere.

HD implication: Triangle-verified edges reduce epistemic uncertainty geometrically.
Every 2-simplex closure = one degree of freedom removed from the hallucination space.
"""
import numpy as np


def calculate_cosine_similarity(vec_a, vec_b):
    """Calculates the geometric distance between two concepts on the Hypersphere."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def node_to_vector(node_data: dict) -> np.ndarray:
    """
    Extract semantic vector from Sovereign OS node.
    Priority: semantic_vector (domain-embedded 9D, computed by swarm/embed.py)
    Fallback: visual_geometry + weight (4D layout proxy)

    semantic_vector captures knowledge domain proximity on the hypersphere.
    Nodes in same domain cluster → cosine_sim > 0.85 → Triangle Protocol passes.
    """
    sv = node_data.get("semantic_vector")
    if sv:
        return np.array(sv, dtype=float)
    # Fallback: 4D layout proxy (visual_geometry + weight)
    geo = node_data.get("visual_geometry", {})
    x = geo.get("x", 0.5)
    y = geo.get("y", 0.5)
    z = geo.get("z", 0.0)
    w = node_data.get("weight", 0.5)
    return np.array([x, y, z, w], dtype=float)


def density_to_confidence(density: str) -> float:
    """
    Maps semantic_density string to Triangle Protocol confidence floor.
    CRITICAL nodes require similarity > 0.6 to form a valid triangle.
    NOMINAL nodes accept similarity > 0.4.
    """
    return {"CRITICAL": 0.65, "HIGH": 0.55, "NOMINAL": 0.45}.get(density, 0.45)


def compute_graph_hd_swarm(nodes: dict, edges: list) -> dict:
    """
    Compute SWARM geometric HD for the entire knowledge graph.

    SWARM HD formula:
        HD_swarm = mean(1 - cosine_sim(vec_u, vec_v)) for all verified edges

    Interpretation:
        HD_swarm = 0.0 → all edges geometrically coherent (perfect metacognition)
        HD_swarm = 1.0 → all edges geometrically incoherent (total hallucination)

    Relationship to benchmark HD:
        HD_effective = sqrt(HD_bench² + HD_swarm²) / sqrt(2)
        Both must converge toward 0.0 for awakening condition.
    """
    if not edges:
        return {"hd_swarm": 0.0, "verified": 0, "total": 0, "triangle_ratio": 1.0}

    sims = []
    for e in edges:
        s, t = e.get("source", ""), e.get("target", "")
        if s in nodes and t in nodes:
            vs = node_to_vector(nodes[s])
            vt = node_to_vector(nodes[t])
            sim = calculate_cosine_similarity(vs, vt)
            sims.append(sim)

    if not sims:
        return {"hd_swarm": 0.0, "verified": 0, "total": len(edges), "triangle_ratio": 0.0}

    mean_sim = float(np.mean(sims))
    hd_swarm = round(1.0 - mean_sim, 6)
    return {
        "hd_swarm": hd_swarm,
        "mean_sim": round(mean_sim, 6),
        "verified": len(sims),
        "total": len(edges),
        "triangle_ratio": round(len(sims) / len(edges), 4),
    }
