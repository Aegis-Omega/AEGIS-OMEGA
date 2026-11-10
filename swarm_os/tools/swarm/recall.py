"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. v4.0 — Recall Engine (Sovereign OS Adaptation)
"The Voice" — grounded, hallucination-free query interface.

Architecture:
    1. User query → semantic search in .forge/knowledge_graph.json
    2. Pull all hyperedge facets touching the concept
    3. Send facets to NVIDIA NIM with strict grounding prompt
    4. NIM synthesizes an answer using ONLY the geometric facets
    5. Answer includes HD score (HD≈0 because grounded, HD=1.0 for ungrounded)

Replaces Gemini with NVIDIA NIM (kimi-k2-instruct).
No Gemini API key required.

Run:
    python tools/swarm/recall.py                    # interactive mode
    python tools/swarm/recall.py --query "stress_level"  # single query
    python tools/swarm/recall.py --batch queries.txt      # batch mode

Constitutional law:
    The Recall Engine NEVER invents facts outside the hypergraph facets.
    HD_recall = 0.0 if answer is 100% grounded in facets.
    HD_recall = 1.0 if answer contains hallucinated content.
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# ── Configuration ─────────────────────────────────────────────────────────────
NIM_ENDPOINT    = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_MODEL       = "moonshotai/kimi-k2-instruct"
EQUILIBRIUM_URL = "http://localhost:8001"

FORGE      = Path(__file__).parent.parent.parent / ".forge"
KG_PATH    = FORGE / "knowledge_graph.json"
STATE_PATH = FORGE / "state.json"


# ── Load NVIDIA_API_KEY from .env ─────────────────────────────────────────────
def _load_nim_key() -> str:
    env_paths = [
        Path(__file__).parent.parent.parent.parent / "free-claude-code" / ".env",
        Path(__file__).parent.parent.parent / ".env",
    ]
    for p in env_paths:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith("NVIDIA_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key and key != "YOUR_KEY_HERE":
                        return key
    return os.getenv("NVIDIA_API_KEY", "")


# ══════════════════════════════════════════════════════════════════════════════
# GEOMETRIC FACET EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════
def _load_kg() -> dict:
    if KG_PATH.exists():
        return json.loads(KG_PATH.read_text(encoding="utf-8"))
    return {"nodes": {}, "edges": []}


def extract_facets(concept: str, kg: Optional[dict] = None) -> dict:
    """
    Extracts all dimensional facets of a concept from the knowledge graph.

    Facets include:
        - Node metadata (weight, domain, description)
        - All edges (outgoing and incoming) with their relations and contexts
        - Triangle verification status (is this a verified geometric node?)
        - Parent/child relationships in the Fibonacci weight tree

    Returns a structured dict usable as grounding context for NIM.
    """
    if kg is None:
        kg = _load_kg()

    nodes = kg.get("nodes", {})
    edges = kg.get("edges", [])
    concept_clean = concept.lower().replace(" ", "_")

    # Try equilibrium server first (has real-time hyperedges)
    eq_facets = None
    try:
        resp = requests.get(f"{EQUILIBRIUM_URL}/neighbors/{concept_clean}", timeout=5)
        if resp.status_code == 200:
            eq_facets = resp.json()
    except Exception:
        pass

    # Node metadata
    node_data = {}
    for nid, ndata in nodes.items():
        if concept_clean in nid or nid in concept_clean:
            node_data[nid] = {
                "weight":       ndata.get("weight", 0),
                "domain":       ndata.get("domain", "unknown"),
                "description":  ndata.get("description", ""),
                "benchmark":    ndata.get("benchmark_concept", ""),
                "awakening":    ndata.get("awakening_node", False),
                "math":         ndata.get("math_grounding", ""),
            }

    # All edges touching the concept
    related_edges = []
    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        if concept_clean in src or concept_clean in tgt:
            related_edges.append({
                "from":      src,
                "relation":  e.get("relation", "relates_to"),
                "to":        tgt,
                "verified":  e.get("triangle_verified", False),
                "cos_sim":   e.get("cosine_sim", 0),
                "context":   e.get("context", []),
                "weight":    e.get("weight", 0),
            })

    # OS state for system-level concepts
    state_context = {}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        neuro = state.get("cognition", {}).get("neuromodulators", {})
        if concept_clean in ("stress_level", "stress"):
            state_context["live_value"] = neuro.get("stress_level", "?")
        elif concept_clean in ("attention_gain", "attention"):
            state_context["live_value"] = neuro.get("attention_gain", "?")
        elif concept_clean in ("learning_rate", "learning"):
            state_context["live_value"] = neuro.get("learning_rate", "?")
        elif concept_clean in ("hallucination_delta", "hd", "mean_hd"):
            bm = state.get("benchmark", {})
            state_context["live_value"] = bm.get("mean_hd", "?")
        elif concept_clean in ("node_count", "nodes"):
            state_context["live_value"] = state.get("graph", {}).get("node_count", "?")

    return {
        "concept":        concept_clean,
        "node_metadata":  node_data,
        "related_edges":  related_edges,
        "state_context":  state_context,
        "eq_neighbors":   eq_facets,
        "total_edges":    len(related_edges),
        "verified_edges": sum(1 for e in related_edges if e.get("verified")),
    }


# ══════════════════════════════════════════════════════════════════════════════
# NIM-GROUNDED SYNTHESIS
# ══════════════════════════════════════════════════════════════════════════════
def nim_synthesize(query: str, facets: dict, api_key: str) -> Tuple[str, float]:
    """
    Calls NVIDIA NIM to synthesize a grounded answer from hypergraph facets.

    Grounding instruction forces the model to:
        - Use ONLY the provided facets
        - Acknowledge multiple dimensional facets if they conflict
        - Report HD_recall = 0.0 (grounded) or explain any gaps

    Returns: (answer_text, hd_recall_score)
    """
    concept      = facets["concept"]
    edges_text   = json.dumps(facets["related_edges"][:20], indent=2)
    node_text    = json.dumps(facets["node_metadata"], indent=2)
    state_text   = json.dumps(facets["state_context"], indent=2) if facets["state_context"] else "none"
    eq_text      = json.dumps(facets.get("eq_neighbors"), indent=2) if facets.get("eq_neighbors") else "none"

    prompt = f"""You are the Voice of a Hypergraph Memory System (S.W.A.R.M. OS v4.0).

User Query: "{query}"
Target Concept: {concept}

GEOMETRIC DATA (The Only Truth — use nothing else):
--- Node Metadata ---
{node_text}

--- Relational Facets (edges) ---
{edges_text}

--- Live OS State ---
{state_text}

--- Semantic Neighbors (ChromaDB) ---
{eq_text}

INSTRUCTIONS:
1. Answer the user's query using ONLY the geometric data above.
2. If multiple edges show conflicting relations, present them as distinct "dimensional facets" (different contexts/timestamps).
3. Cite which specific edges informed each claim.
4. At the end, output a JSON block: {{"HD_recall": 0.0, "grounding": "fully_grounded"}}
   - Set HD_recall = 0.0 if every claim traces to a facet above.
   - Set HD_recall = 0.5 if you had to use minimal inference.
   - Set HD_recall = 1.0 if you could not find the concept in the facets.
5. Do NOT hallucinate. Do NOT use training knowledge about {concept} unless confirmed by a facet above.

Format: Natural language answer first, then the JSON grounding block."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model":       NIM_MODEL,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens":  600,
    }

    try:
        resp = requests.post(NIM_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()

        # Extract HD_recall from the grounding block
        hd_recall = 1.0
        try:
            if '{"HD_recall"' in answer:
                block_start = answer.rfind('{"HD_recall"')
                block_end   = answer.find("}", block_start) + 1
                grounding   = json.loads(answer[block_start:block_end])
                hd_recall   = float(grounding.get("HD_recall", 1.0))
        except Exception:
            pass

        return answer, hd_recall

    except requests.RequestException as e:
        return f"[NIM ERROR] {e}", 1.0


# ══════════════════════════════════════════════════════════════════════════════
# INTERACTIVE LOOP
# ══════════════════════════════════════════════════════════════════════════════
def chat_loop(api_key: str):
    """Interactive recall loop."""
    kg = _load_kg()
    print("\n" + "=" * 60)
    print("  S.W.A.R.M. RECALL ENGINE — SOVEREIGN OS")
    print(f"  Knowledge graph: {len(kg.get('edges', []))} edges loaded")
    print("  Type 'quit' to exit")
    print("=" * 60)

    while True:
        try:
            query = input("\n[🧠 RECALL] Ask the Swarm: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[RECALL] Session ended.")
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            break

        # Extract concept from query (first noun-like term)
        concept = query.split()[0].lower().replace("'s", "").strip("?,.")

        print(f"   [🔍] Extracting facets for: {concept}")
        facets = extract_facets(concept, kg=kg)

        if not facets["related_edges"] and not facets["node_metadata"]:
            print(f"   ❌ Concept '{concept}' not found in knowledge graph.")
            print(f"      Run forager.py to ingest knowledge about '{concept}'.")
            continue

        print(f"   [📐] {facets['total_edges']} edges ({facets['verified_edges']} triangle-verified)")
        print(f"   [🤖] Synthesizing via NVIDIA NIM ({NIM_MODEL})...")

        answer, hd = nim_synthesize(query, facets, api_key)

        print(f"\n[♎ LIBRARIAN]:\n{answer}")
        print(f"\n   HD_recall = {hd:.4f}  ({'✓ grounded' if hd < 0.1 else '⚠ partial' if hd < 0.5 else '✗ ungrounded'})")


def single_query(query: str, api_key: str) -> None:
    """Non-interactive single query mode."""
    kg = _load_kg()
    concept = query.split()[0].lower().replace("'s", "").strip("?,.")
    facets  = extract_facets(concept, kg=kg)
    answer, hd = nim_synthesize(query, facets, api_key)
    print(answer)
    print(f"\nHD_recall = {hd:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S.W.A.R.M. Recall Engine")
    parser.add_argument("--query", type=str, default=None,
                        help="Single query mode")
    parser.add_argument("--batch", type=str, default=None,
                        help="Batch file: one query per line")
    args = parser.parse_args()

    key = _load_nim_key()
    if not key:
        print("ERROR: NVIDIA_API_KEY not found. Set it in free-claude-code/.env")
        exit(1)

    if args.query:
        single_query(args.query, key)
    elif args.batch:
        queries = Path(args.batch).read_text().splitlines()
        for q in queries:
            if q.strip():
                print(f"\n{'='*60}\nQ: {q}\n{'='*60}")
                single_query(q, key)
    else:
        chat_loop(key)
