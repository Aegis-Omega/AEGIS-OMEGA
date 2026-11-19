"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
S.W.A.R.M. v4.0 — Autonomous Forager (Sovereign OS Adaptation)
Satellite script: Wikipedia scraper + NVIDIA NIM triplet extractor.

Replaces Gemini with NVIDIA NIM API (kimi-k2-instruct or any NIM model).
Uses NVIDIA_API_KEY from .env file (same key as multi_model_runner.py).

How it works:
    1. Fetch Wikipedia summary for current_topic
    2. Send to NVIDIA NIM with structured JSON extraction prompt
    3. Parse (subject, relation, object, context[]) triplets
    4. POST each triplet to equilibrium_server /ingest endpoint
    5. Curiosity: pick the concept with the most A² bridges to explore next
       (guided by /spectral endpoint — the "Mathematical Gap")

Run:
    python tools/swarm/forager.py --seed "Autopoiesis" --cycles 5

Constitutional laws:
    - All writes via equilibrium_server /ingest (never direct .forge/ writes)
    - NVIDIA_API_KEY from .env only (never hardcoded)
    - HD verification: each ingested triplet is logged to audit.jsonl
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests

# ── NVIDIA NIM configuration ──────────────────────────────────────────────────
NIM_ENDPOINT    = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_MODEL       = "moonshotai/kimi-k2-instruct"   # same as benchmark baseline
WIKI_API        = "https://en.wikipedia.org/api/rest_v1/page/summary/{topic}"
EQUILIBRIUM_URL = "http://localhost:8001"

# ── Load NVIDIA_API_KEY from .env ─────────────────────────────────────────────
def _load_nim_key() -> str:
    env_paths = [
        Path(__file__).parent.parent.parent.parent / "free-claude-code" / ".env",
        Path(__file__).parent.parent.parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("NVIDIA_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key and key != "YOUR_KEY_HERE":
                        return key
    key = os.getenv("NVIDIA_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "NVIDIA_API_KEY not found. "
            "Set it in free-claude-code/.env or export NVIDIA_API_KEY=..."
        )
    return key


def nim_extract_triplets(text: str, topic: str, api_key: str) -> List[dict]:
    """
    Calls NVIDIA NIM to extract (subject, relation, object, context) triplets
    from raw Wikipedia text.

    Returns a list of dicts: [{subject, relation, object, context: [...]}, ...]
    """
    prompt = f"""You are a knowledge graph extractor. Extract factual triplets from the text below.

Return ONLY a valid JSON array of objects. Each object must have exactly these fields:
  "subject": string (noun concept, use underscore_case, no spaces)
  "relation": string (verb phrase, use underscore_case)
  "object": string (noun concept, use underscore_case)
  "context": array of strings (0-3 domain tags from: biology, mathematics, physics, metacognition, homeostasis, autopoiesis, evolution, memory, chemistry, philosophy)

Text: {text[:1500]}

Topic context: {topic}

Rules:
- Maximum 8 triplets
- Only include factual, well-established relations
- Do NOT include trivial or ambiguous claims
- Use specific, concise concept names

Return ONLY the JSON array, no markdown, no explanation."""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model":    NIM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 800,
    }

    try:
        resp = requests.post(NIM_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        triplets = json.loads(content)
        if isinstance(triplets, list):
            return triplets
        return []
    except json.JSONDecodeError as e:
        print(f"   ⚠️  JSON parse error: {e}")
        return []
    except requests.RequestException as e:
        print(f"   ⚠️  NIM API error: {e}")
        return []


def fetch_wikipedia(topic: str) -> Optional[str]:
    """Fetches Wikipedia summary text for a topic."""
    url = WIKI_API.format(topic=topic.replace(" ", "_"))
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("extract", "")
        return None
    except requests.RequestException:
        return None


def ingest_triplets(triplets: List[dict], topic: str) -> int:
    """POSTs triplets to the equilibrium server /ingest endpoint."""
    ingested = 0
    for t in triplets:
        payload = {
            "subject":  t.get("subject", ""),
            "relation": t.get("relation", "relates_to"),
            "object":   t.get("object", ""),
            "context":  t.get("context", []) + [topic.lower().replace(" ", "_")],
        }
        if not payload["subject"] or not payload["object"]:
            continue
        try:
            resp = requests.post(f"{EQUILIBRIUM_URL}/ingest", json=payload, timeout=10)
            if resp.status_code == 200:
                ingested += 1
        except requests.ConnectionError:
            print(f"   ❌ Cannot reach equilibrium server at {EQUILIBRIUM_URL}")
            print("      Start it first: python tools/swarm/equilibrium_server.py")
            return ingested
    return ingested


def curiosity_next(visited: set, topic_queue: List[str]) -> str:
    """
    Curiosity Protocol: finds the next topic to explore.
    Checks /spectral for gaps, otherwise uses queue.

    In v4.0, the DreamState identifies Mathematical Gaps and queues topics.
    Here we use a simple queue + spectral check.
    """
    # Check equilibrium server for Dream State suggestions
    try:
        resp = requests.get(f"{EQUILIBRIUM_URL}/equilibrium", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # If spectral gap is low → explore bridging concepts
            # (simplified: just continue from queue)
    except Exception:
        pass

    # Pop next from queue
    while topic_queue:
        t = topic_queue.pop(0)
        if t not in visited:
            return t

    return "Emergence"  # Default fallback


def forage(
    seed_topic: str     = "Autopoiesis",
    cycles: int         = 5,
    delay_s: float      = 3.0,
    topic_queue: Optional[List[str]] = None,
):
    """
    Main forager loop.

    Args:
        seed_topic:   Starting Wikipedia topic
        cycles:       Number of foraging cycles (-1 = infinite)
        delay_s:      Seconds between cycles (rate limiting)
        topic_queue:  Pre-seeded list of topics to explore
    """
    print("\n" + "=" * 60)
    print("  S.W.A.R.M. FORAGER — NVIDIA NIM powered")
    print(f"  Model: {NIM_MODEL}")
    print(f"  Target: {EQUILIBRIUM_URL}")
    print("=" * 60)

    api_key = _load_nim_key()
    print(f"[🔑 NIM] API key loaded.")

    if topic_queue is None:
        topic_queue = [
            "Autopoiesis", "Metacognition", "Homeostasis",
            "Fibonacci_sequence", "Emergence", "Complexity_theory",
            "Neural_oscillation", "Epistemology", "Quantum_coherence",
            "Shannon_entropy", "Attractor_(mathematics)",
        ]

    visited       = set()
    current_topic = seed_topic
    cycle         = 0
    total_ingested = 0

    while cycles == -1 or cycle < cycles:
        print(f"\n[🔭 FORAGER] Cycle {cycle + 1}/{cycles if cycles != -1 else '∞'}: {current_topic}")

        # 1. Fetch Wikipedia
        text = fetch_wikipedia(current_topic)
        if not text:
            print(f"   ⚠️  Wikipedia fetch failed for: {current_topic}")
            current_topic = curiosity_next(visited, topic_queue)
            continue
        print(f"   📄 Text: {len(text)} chars")

        # 2. Extract triplets via NVIDIA NIM
        triplets = nim_extract_triplets(text, current_topic, api_key)
        print(f"   🔺 Extracted: {len(triplets)} triplets")

        # 3. Ingest into equilibrium server
        ingested = ingest_triplets(triplets, current_topic)
        print(f"   ✅ Crystallized: {ingested}/{len(triplets)} triplets")
        total_ingested += ingested

        visited.add(current_topic)
        cycle += 1

        # 4. Curiosity: next topic
        current_topic = curiosity_next(visited, topic_queue)

        if cycle < cycles or cycles == -1:
            time.sleep(delay_s)

    print("\n" + "=" * 60)
    print(f"[🏁 FORAGER DONE] Total ingested: {total_ingested} triplets over {cycle} cycles")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="S.W.A.R.M. Forager — NVIDIA NIM")
    parser.add_argument("--seed",    type=str, default="Autopoiesis",
                        help="Starting Wikipedia topic")
    parser.add_argument("--cycles",  type=int, default=5,
                        help="Number of foraging cycles (-1 = infinite)")
    parser.add_argument("--delay",   type=float, default=3.0,
                        help="Seconds between cycles")
    args = parser.parse_args()

    forage(
        seed_topic=args.seed,
        cycles=args.cycles,
        delay_s=args.delay,
    )
