#!/usr/bin/env python3
"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.

S.W.A.R.M. Demo Seed
━━━━━━━━━━━━━━━━━━━
Seeds 12 triplets into the running server, then triggers a Dream State REM cycle.
No API key required — uses the local /ingest endpoint only.

Run AFTER start.sh (server must be running):
    python swarm/demo_seed.py
    python swarm/demo_seed.py --url http://localhost:8000
    python swarm/demo_seed.py --url http://localhost:8000 --no-rem
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

# ── 12 triplets: metacognition / hallucination / homeostasis ─────────────────
SEED_TRIPLETS = [
    # Metacognition cluster
    {"subject": "metacognition",       "relation": "measures",          "object": "hallucination_delta",    "context": ["cognition"]},
    {"subject": "hallucination_delta", "relation": "quantifies",        "object": "accuracy_gap",           "context": ["cognition"]},
    {"subject": "accuracy_gap",        "relation": "caused_by",         "object": "overconfidence",         "context": ["cognition"]},
    {"subject": "consciousness",       "relation": "depends_on",        "object": "metacognition",          "context": ["cognition"]},

    # Homeostasis cluster
    {"subject": "homeostasis",         "relation": "maintains",         "object": "equilibrium",            "context": ["biology"]},
    {"subject": "equilibrium",         "relation": "requires",          "object": "feedback_loop",          "context": ["biology"]},
    {"subject": "feedback_loop",       "relation": "regulates",         "object": "stress_level",           "context": ["biology"]},
    {"subject": "stress_level",        "relation": "affects",           "object": "accuracy_gap",           "context": ["cognition", "biology"]},

    # Autopoiesis / Systems cluster
    {"subject": "autopoiesis",         "relation": "produces",          "object": "self_organization",      "context": ["systems"]},
    {"subject": "self_organization",   "relation": "emerges_from",      "object": "complexity",             "context": ["systems"]},
    {"subject": "complexity",          "relation": "generates",         "object": "consciousness",          "context": ["systems"]},
    {"subject": "homeostasis",         "relation": "enables",           "object": "autopoiesis",            "context": ["biology", "systems"]},
]


def _post_json(url: str, data: dict) -> dict:
    body = json.dumps(data).encode("utf-8")
    req  = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode())


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=8) as resp:
        return json.loads(resp.read().decode())


def wait_for_server(base_url: str, retries: int = 12, delay: float = 1.5):
    print(f"[SEED] Waiting for server at {base_url}/health …")
    for i in range(retries):
        try:
            _get_json(f"{base_url}/health")
            print("[SEED] Server is up.")
            return True
        except Exception:
            time.sleep(delay)
    print("[SEED] ✗ Server not responding after retries.")
    return False


def seed(base_url: str, trigger_rem: bool = True):
    # ── 1. Ingest 12 triplets ─────────────────────────────────────────────
    print(f"\n[SEED] Ingesting {len(SEED_TRIPLETS)} triplets →")
    ok = 0
    for t in SEED_TRIPLETS:
        try:
            result = _post_json(f"{base_url}/ingest", t)
            status = result.get("status", "?")
            print(f"       {'✓' if 'crystal' in status or 'ok' in status.lower() else '?'}"
                  f"  {t['subject']} →[{t['relation']}]→ {t['object']}")
            ok += 1
        except Exception as e:
            print(f"       ✗  {t['subject']} → {t['object']} : {e}")
        time.sleep(0.05)

    print(f"\n[SEED] {ok}/{len(SEED_TRIPLETS)} triplets crystallized.\n")

    # ── 2. Show graph snapshot ────────────────────────────────────────────
    try:
        g = _get_json(f"{base_url}/graph")
        edges     = g.get("hyperedges", [])
        node_set  = {n for he in edges for n in he.get("nodes", [])}
        print(f"[SEED] Graph snapshot:")
        print(f"       Nodes : {len(node_set)}")
        print(f"       Edges : {len(edges)}")
    except Exception:
        pass

    # ── 3. Trigger REM cycle ──────────────────────────────────────────────
    if trigger_rem:
        print("\n[SEED] Triggering Dream State REM cycle …")
        try:
            rem_result = _post_json(f"{base_url}/rem", {})
            epiphanies = rem_result.get("epiphanies", 0)
            print(f"[SEED] ✓ REM complete — {epiphanies} epiphany/epiphanies surfaced.\n")
        except Exception as e:
            print(f"[SEED] ✗ REM failed: {e}\n")

    # ── 4. Show spectral state ────────────────────────────────────────────
    try:
        sp = _get_json(f"{base_url}/spectral")
        print(f"[SEED] Spectral state:")
        print(f"       λ₁ (spectral radius) = {sp.get('lambda1', '—')}")
        print(f"       Stable               = {sp.get('stable', '—')}")
        print(f"       REM cycles           = {sp.get('rem_cycles', sp.get('cycles', '—'))}")
    except Exception:
        pass

    print(f"\n[SEED] Done. Visit the canvas:")
    print(f"       {base_url}/\n")


def main():
    parser = argparse.ArgumentParser(description="Sovereign AGI OS — Demo Seed")
    parser.add_argument("--url",    default="http://localhost:8000", help="Server base URL")
    parser.add_argument("--no-rem", action="store_true",             help="Skip REM trigger")
    parser.add_argument("--no-wait", action="store_true",            help="Don't wait for server")
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║   S.W.A.R.M.  DEMO SEED — 12 Triplets (no API key required)                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    if not args.no_wait:
        if not wait_for_server(args.url):
            sys.exit(1)

    seed(args.url, trigger_rem=not args.no_rem)


if __name__ == "__main__":
    main()
