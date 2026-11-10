"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. Semantic Embedding Layer — Sovereign OS
Assigns domain-based semantic vectors to each node in the knowledge graph.

Problem: visual_geometry {x,y,z} was set by D3 layout algorithm → random positions
         → cosine similarity between semantically related nodes can be negative
         → Triangle Protocol fails even for correct parent→child edges

Fix: assign `semantic_vector` based on knowledge domain.
     Nodes in same domain cluster → high cosine similarity → Triangle verified
     Cross-domain edges → examined for geometric bridges (shared anchors)

Domain Basis Vectors (8 orthogonal dimensions, normalized):
    Each domain occupies a sector of the hypersphere.
    Weight (Fibonacci depth) is added as a 9th dimension to distinguish layers.

Formula:
    vec[node] = domain_basis + weight * 0.4 * uniform_direction

    where domain_basis is a unit vector in 8-space pointing toward domain's sector
    and weight * 0.4 pushes higher-weight nodes slightly toward origin (root nodes
    have different semantic character than leaf nodes even within same domain)
"""
import json
import math
import os
from pathlib import Path

import numpy as np

FORGE   = Path(__file__).parent.parent.parent / ".forge"
KG_PATH = FORGE / "knowledge_graph.json"


# Domain assignment: node_id substring → domain index (0-7)
DOMAIN_MAP = {
    # 0 — Metacognition / Hallucination
    "metacognition": 0, "hallucination": 0, "frontal_lobe": 0,
    "reasoning_intensity": 0, "rir": 0, "consciousness": 0,
    "grounding_problem": 0, "kaggle_nexus": 0,

    # 1 — Biology / Anatomy / Neural
    "biology": 1, "anatomy": 1, "neural": 1, "sensorimotor": 1,
    "limbic": 1, "cortisol": 1, "dopamine": 1, "embodied": 1,
    "nhi": 1, "spsf": 1,

    # 2 — Mathematics / Information Theory
    "mathematics": 2, "fibonacci": 2, "shannon": 2, "channel_capacity": 2,
    "evolutionary_weight": 2, "attention_bottleneck": 2,

    # 3 — AI / Agentic Computing
    "machine_learning": 3, "agentic": 3, "constitutional": 3,
    "cloud_run": 3, "vertex": 3, "csbo": 3, "biomimetic": 3,
    "bayesian": 3, "clonal_selection": 3,

    # 4 — Homeostasis / Metabolism / HPA
    "homeostasis": 4, "hpa_axis": 4, "stress_calib": 4,
    "metabolic": 4, "autopoiesis": 4, "saga": 4, "antifragile": 4,

    # 5 — Memory / Temporal / Hippocampus
    "autopoietic_memory": 5, "temporal_lobe": 5, "memory": 5,
    "temporal_lobe_memory": 5,

    # 6 — Evolution / Immunity / Selection
    "pattern_recognition": 6, "natural_selection": 6,
    "evolutionary": 6, "immune": 6, "infection": 6,

    # 7 — Audio / Spatial / Visual
    "spatio_acoustic": 7, "resonant": 7, "visual_cortex": 7,
    "3d_topology": 7, "dimensional": 7, "acoustic": 7,
}

# Domain basis vectors (8D, each pointing to a different octant)
# Constructed so adjacent domains share small components → cross-domain edges
# that DO make sense (e.g. biology↔homeostasis) can still form triangles.
DOMAIN_BASES = np.array([
    [1.0, 0.2, 0.1, 0.1, 0.2, 0.1, 0.1, 0.1],  # 0 metacognition
    [0.2, 1.0, 0.1, 0.1, 0.3, 0.1, 0.2, 0.1],  # 1 biology
    [0.1, 0.1, 1.0, 0.2, 0.1, 0.1, 0.3, 0.1],  # 2 mathematics
    [0.1, 0.1, 0.2, 1.0, 0.1, 0.2, 0.1, 0.1],  # 3 ai_computing
    [0.2, 0.3, 0.1, 0.1, 1.0, 0.2, 0.1, 0.1],  # 4 homeostasis
    [0.1, 0.1, 0.1, 0.2, 0.2, 1.0, 0.1, 0.2],  # 5 memory
    [0.1, 0.2, 0.3, 0.1, 0.1, 0.1, 1.0, 0.1],  # 6 evolution
    [0.1, 0.1, 0.1, 0.1, 0.1, 0.2, 0.1, 1.0],  # 7 audio_spatial
], dtype=float)

# Normalize rows to unit vectors
DOMAIN_BASES = DOMAIN_BASES / np.linalg.norm(DOMAIN_BASES, axis=1, keepdims=True)



# Exact-match overrides — take priority over substring matching.
# Needed for nodes where a generic substring (e.g. "neural") shadows the
# correct domain keyword (e.g. "shannon").
EXACT_DOMAINS = {
    # Math nodes that contain "neural" (wrongly matched to biology)
    "shannon_entropy_neural":       2,
    "channel_capacity_signal":      2,
    "attention_bottleneck_theorem": 2,
    "neural_information_flow":      1,  # This one IS biology (neural anatomy)
    "pattern_recognition_neural":   3,  # pattern matching = ai domain
    # Limbic/dopamine nodes live in homeostasis (HPA axis) not biology
    "limbic_cortisol_loop":         4,
    "limbic_dopamine_reward":       4,
    # Reasoning_intensity = metacognition
    "reasoning_intensity_ratio":    0,
    # Adversarial calibration = metacognition benchmark
    "adversarial_calibration_hd":   0,
    "adversarial_calibration":      0,
    # Dimensional transition = ai/computing
    "dimensional_transition":       3,
    # Clonal selection = evolution/immunity
    "clonal_selection_algorithm":   6,
    # Cross-domain intentional bridges (leave unstable → Dream State resolves)
    # autopoiesis ↔ machine_learning: genuine paradigm bridge, keep in hyp_graph
}


def get_domain(node_id: str) -> int:
    """Map node_id to domain index (0-7). Exact match takes priority."""
    nid = node_id.lower()
    # 1. Exact full-id match
    if nid in EXACT_DOMAINS:
        return EXACT_DOMAINS[nid]
    # 2. Substring match (longer keys first to avoid shadowing)
    sorted_keys = sorted(DOMAIN_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in nid:
            return DOMAIN_MAP[key]
    # 3. Hash-based (deterministic fallback)
    return sum(ord(c) for c in nid) % 8


def compute_semantic_vector(node_id: str, node_data: dict) -> list:
    """
    Compute 9D semantic vector for a knowledge graph node.

    vec = normalize(domain_basis + weight * weight_direction)

    The weight dimension (9th) distinguishes root nodes (high weight ≈ 0.888)
    from leaf nodes (low weight ≈ 0.236) within the same domain.
    Within a domain, parent→child edges will have different weights but
    same domain direction → still high cosine similarity (>0.85 typically).
    """
    domain = get_domain(node_id)
    basis  = DOMAIN_BASES[domain].copy()   # 8D unit vector
    weight = node_data.get("weight", 0.5)

    # 9D: domain basis + weight as explicit dimension
    vec = np.append(basis, weight)

    # Normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    return vec.tolist()


def assign_semantic_vectors(verbose: bool = True) -> dict:
    """
    Assigns semantic_vector to all nodes in knowledge_graph.json.
    Atomic write. Does NOT modify visual_geometry (D3 layout unchanged).
    """
    kg    = json.loads(KG_PATH.read_text(encoding="utf-8"))
    nodes = kg["nodes"]

    domain_counts = {i: 0 for i in range(8)}
    for nid, nd in nodes.items():
        vec = compute_semantic_vector(nid, nd)
        nd["semantic_vector"] = vec
        domain_counts[get_domain(nid)] += 1
        if verbose:
            d = get_domain(nid)
            domain_names = ["metacognition","biology","math","ai","homeostasis","memory","evolution","audio"]
            print(f"   {nid[:32]:32s} → domain={domain_names[d]}")

    # Atomic write
    tmp = KG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(kg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, KG_PATH)

    if verbose:
        domain_names = ["metacognition","biology","math","ai","homeostasis","memory","evolution","audio"]
        print("\nDomain distribution:")
        for d, cnt in domain_counts.items():
            print(f"  {domain_names[d]:16s}: {cnt} nodes")

    return {"nodes_embedded": len(nodes), "domain_counts": domain_counts}


if __name__ == "__main__":
    result = assign_semantic_vectors(verbose=True)
    print(f"\nEmbedding complete: {result['nodes_embedded']} nodes")
