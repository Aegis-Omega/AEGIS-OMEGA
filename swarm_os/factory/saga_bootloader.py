#!/usr/bin/env python3
"""
© 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.

SAGA Factory — Autonomous Bootloader v1.0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Initializes and drives the SAGA self-evolution loop.

Run once to bootstrap:
  python factory/saga_bootloader.py --init

Run continuously (infinite Dream State loop):
  python factory/saga_bootloader.py --dream

Run one evolution cycle:
  python factory/saga_bootloader.py --cycle

Watch live HD scores across all files:
  python factory/saga_bootloader.py --watch
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_HERE        = Path(__file__).parent
PROJECT_ROOT = _HERE.parent
FORGE_DIR    = PROJECT_ROOT / "swarm_os" / ".forge"
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline_manager import (
    build_dependency_dag, compute_hd, detect_hosted_gpus,
    dispatch_to_llm, scan_project, run_task, verify_connectivity,
    _load_json, _atomic_write, _save_db, _load_db, _audit_entry,
    HD_COMMIT_GATE, HD_WARNING_GATE, EGO_ANCHOR, _text_to_wave, HDGate,
)

VERSION = "1.0.0"

# ── SAGA Evolution Targets (ranked by impact on HD score) ──────────────────
# Each target is a specific, achievable improvement before April 16
EVOLUTION_TARGETS = [
    {
        "id":       "EVO_001",
        "priority": 1,
        "title":    "Expand knowledge graph: 80 → 120+ nodes",
        "method":   "Add 40 Layer-2 nodes from swarm_manifold.json (403 nodes available)",
        "impact":   "More KG activations → lower thought HD",
        "files":    ["swarm_os/.forge/knowledge_graph.json"],
        "hd_delta": -0.01,
    },
    {
        "id":       "EVO_002",
        "priority": 2,
        "title":    "Run multi_model_runner.py with all 4 NVIDIA NIM models",
        "method":   "python swarm_os/benchmark/multi_model_runner.py",
        "impact":   "Elect model with lowest HD; update state.json elected_model",
        "files":    ["swarm_os/benchmark/multi_model_runner.py"],
        "hd_delta": -0.02,
    },
    {
        "id":       "EVO_003",
        "priority": 3,
        "title":    "Add external benchmark validation (MMLU metacognition subset)",
        "method":   "Download MMLU professional_psychology + theory_of_mind subsets",
        "impact":   "External proof: HD measured against independent dataset",
        "files":    ["benchmark/external_validation.py"],
        "hd_delta": -0.015,
    },
    {
        "id":       "EVO_004",
        "priority": 4,
        "title":    "Push evolution cycles: 42 → 200+",
        "method":   "Run digital_being.py against all benchmark stimuli repeatedly",
        "impact":   "More NM tuning → stress ↓, attention ↑ → lower HD",
        "files":    ["digital_being.py", "metacognitive_evolution.py"],
        "hd_delta": -0.008,
    },
    {
        "id":       "EVO_005",
        "priority": 5,
        "title":    "Deploy SAGA multi-agent: Architect + Auditor cross-checking",
        "method":   "pipeline_manager.py orchestrates 2 NIM models checking each other",
        "impact":   "Adversarial validation reduces HD via independent verification",
        "files":    ["factory/pipeline_manager.py"],
        "hd_delta": -0.012,
    },
]


def init_factory():
    """Phase 1: Full factory initialization."""
    print("\n" + "═" * 60)
    print("  SAGA FACTORY BOOTLOADER v1.0.0 — INITIALIZING")
    print("═" * 60)

    # Step 1: Verify infrastructure
    print("\n[1/5] Verifying infrastructure...")
    conn = verify_connectivity()
    for k, v in conn.items():
        print(f"      {k:<22}: {v}")
    if conn["nvidia_nim"] == "NO_API_KEY":
        print("\n  ⚠️  NVIDIA API key not found in free-claude-code/.env")
        print("     Add: NVIDIA_API_KEY=nvapi-xxx")
        print("     Continuing with local-only HD audits.")

    # Step 2: Scan project
    print("\n[2/5] Scanning project files...")
    results = scan_project()
    hds = [r["hd"] for r in results if "hd" in r]
    mean_hd = sum(hds) / len(hds) if hds else 1.0
    print(f"      Files scanned: {len(results)}")
    print(f"      Mean HD:       {mean_hd:.4f}")
    print(f"      Best HD:       {min(hds):.4f}" if hds else "")
    print(f"      Above gate:    {sum(1 for h in hds if h > HD_COMMIT_GATE)}/{len(hds)}")

    # Step 3: Build DAG
    print("\n[3/5] Building dependency DAG...")
    dag = build_dependency_dag()
    print(f"      KG nodes: {dag['total_nodes']}  |  Edges: {dag['total_edges']}")
    print(f"      Build order (top 5): {[n['id'] for n in dag['build_order'][:5]]}")

    # Step 4: Load evolution state
    print("\n[4/5] Loading evolution state...")
    evo = _load_json(FORGE_DIR / "evolution_state.json")
    print(f"      Evolution cycles: {evo.get('total_evolutions', 0)}")
    print(f"      Best HD:          {min(evo.get('all_time_hd', [1.0])):.4f}")
    print(f"      Best mean HD:     {evo.get('best_mean_hd', 1.0):.4f}")
    print(f"      Ego updates:      {evo.get('ego_updates', 0)}")
    print(f"      Ego total shift:  {evo.get('ego_total_shift', 0):.4f}")

    # Step 5: Plan evolution targets
    print("\n[5/5] Evolution targets ranked by HD impact:")
    for t in EVOLUTION_TARGETS:
        print(f"      [{t['id']}] P{t['priority']} — {t['title']}")
        print(f"             Expected ΔHD: {t['hd_delta']:.3f}")

    # Update DB
    db = _load_db()
    db["pipeline_state"]["phase"] = "READY"
    _save_db(db)

    _audit_entry("FACTORY_INITIALIZED", {
        "mean_hd": mean_hd,
        "kg_nodes": dag["total_nodes"],
        "evo_cycles": evo.get("total_evolutions", 0),
    })

    print("\n" + "═" * 60)
    print("  ✅ FACTORY INITIALIZED — ready for evolution cycles")
    print(f"  HD gate: {HD_COMMIT_GATE}  |  Target: <0.01 by April 16")
    print("═" * 60)
    return {"status": "INITIALIZED", "mean_hd": mean_hd, "dag_nodes": dag["total_nodes"]}


def run_evolution_cycle() -> dict:
    """One full evolution cycle:
    1. Scan current HD scores
    2. Identify highest-HD files
    3. Run digital_being.py evolution
    4. Push new KG nodes from swarm_manifold.json
    5. Update sovereign_db.json
    """
    print("\n⚙️  Running evolution cycle...")
    start = time.time()

    # 1. Current state
    evo_before = _load_json(FORGE_DIR / "evolution_state.json")
    hd_before  = evo_before.get("best_mean_hd", 1.0)

    # 2. Run aliveness_proof.py to force Digital Being evolution
    print("   Running aliveness_proof.py (2 rounds)...")
    proof_path = PROJECT_ROOT / "benchmark" / "aliveness_proof.py"
    if proof_path.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(proof_path)],
                capture_output=True, text=True, timeout=120,
                cwd=str(PROJECT_ROOT / "swarm_os")
            )
            if "EVOLUTION PROOFS PASS: True" in result.stdout:
                print("   ✅ Evolution proofs PASS")
            elif result.returncode == 0:
                print("   ✅ Proof ran successfully")
            else:
                print(f"   ⚠️  Proof output: {result.stdout[-200:]}")
        except subprocess.TimeoutExpired:
            print("   ⚠️  Proof timed out (120s) — continuing")
        except Exception as e:
            print(f"   ⚠️  Could not run proof: {e}")

    # 3. Promote nodes from swarm_manifold.json → knowledge_graph.json
    promoted = _promote_swarm_nodes(limit=5)
    print(f"   KG promotion: +{promoted} nodes from swarm_manifold")

    # 4. Scan updated project
    results  = scan_project()
    hds      = [r["hd"] for r in results if "hd" in r]
    mean_hd  = sum(hds) / len(hds) if hds else 1.0
    best_hd  = min(hds) if hds else 1.0

    # 5. Load updated evolution state
    evo_after = _load_json(FORGE_DIR / "evolution_state.json")
    hd_after  = evo_after.get("best_mean_hd", mean_hd)
    cycles    = evo_after.get("total_evolutions", 0)

    db = _load_db()
    db["pipeline_state"]["phase"]           = "EVOLVING"
    db["pipeline_state"]["tasks_completed"] += 1
    _save_db(db)

    elapsed = round(time.time() - start, 2)
    record  = {
        "status":       "CYCLE_COMPLETE",
        "hd_before":    hd_before,
        "hd_after":     hd_after,
        "hd_delta":     round(hd_after - hd_before, 4),
        "best_hd":      best_hd,
        "nodes_promoted": promoted,
        "evo_cycles":   cycles,
        "files_scanned": len(results),
        "elapsed":      elapsed,
    }
    _audit_entry("EVOLUTION_CYCLE", record)
    print(f"   HD: {hd_before:.4f} → {hd_after:.4f}  (Δ={hd_after-hd_before:+.4f})")
    print(f"   Evolution cycles: {cycles}")
    print(f"   Elapsed: {elapsed}s")
    return record


def _promote_swarm_nodes(limit: int = 5) -> int:
    """Promote top-weight nodes from swarm_manifold.json → knowledge_graph.json.
    Only promotes if they pass HD gate (weight → quality proxy).
    """
    manifold_path = FORGE_DIR / "swarm_manifold.json"
    kg_path       = FORGE_DIR / "knowledge_graph.json"
    if not manifold_path.exists():
        return 0

    manifold = _load_json(manifold_path)
    kg       = _load_json(kg_path)
    kg_nodes = kg.get("nodes", {})
    kg_edges = kg.get("edges", [])

    # Get manifold nodes sorted by z-level/weight (not already in KG)
    m_nodes = manifold.get("nodes", {}) if isinstance(manifold.get("nodes"), dict) else {}
    if not m_nodes:
        # Try list format
        for item in manifold.get("nodes", []):
            if isinstance(item, dict) and "id" in item:
                m_nodes[item["id"]] = item

    candidates = [
        (nid, data) for nid, data in m_nodes.items()
        if nid not in kg_nodes
        and isinstance(data, dict)
        and data.get("z_level", 0) >= 2
    ]
    candidates.sort(key=lambda x: x[1].get("z_level", 0), reverse=True)

    promoted = 0
    gate = HDGate()
    for nid, data in candidates[:limit]:
        # Quality proxy: compute HD on the node ID + description
        desc = f"{nid}: {data.get('content', data.get('label', nid))}"
        hd, R, E = compute_hd(desc)
        if hd <= HD_WARNING_GATE:  # use warning gate for KG promotion (less strict)
            layer  = min(3, max(1, data.get("z_level", 2) - 1))
            parent = data.get("parent", "metacognition")
            w      = min(0.999, 0.5 + data.get("z_level", 2) * 0.1)
            kg_nodes[nid] = {
                "weight": w,
                "layer":  layer,
                "parent": parent,
                "description": desc[:120],
                "hd_at_promotion": hd,
                "promoted_from": "swarm_manifold",
                "promoted_at": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            }
            promoted += 1

    if promoted > 0:
        kg["nodes"] = kg_nodes
        _atomic_write(kg_path, kg)
        _audit_entry("KG_PROMOTION", {"nodes_added": promoted, "total_now": len(kg_nodes)})

    return promoted


def dream_loop(max_cycles: int = 0, interval_s: int = 300):
    """Continuous Dream State loop. Runs evolution cycles indefinitely.
    max_cycles=0 means infinite. interval_s = seconds between cycles.
    """
    print(f"\n🌙 DREAM STATE LOOP — {'infinite' if max_cycles == 0 else max_cycles} cycles")
    print(f"   Interval: {interval_s}s  |  HD gate: {HD_COMMIT_GATE}")
    print("   Ctrl+C to stop gracefully.\n")

    # Lazy-import the self-evolving metacognition engine
    _sem_engine = None
    def _get_sem():
        nonlocal _sem_engine
        if _sem_engine is None:
            try:
                sem_path = str(PROJECT_ROOT / "benchmark")
                if sem_path not in sys.path:
                    sys.path.insert(0, sem_path)
                from self_evolving_metacognition import SelfEvolvingMetacognition
                _sem_engine = SelfEvolvingMetacognition()
                print("   [SEM] Self-Evolving Metacognition engine loaded")
            except Exception as e:
                print(f"   [SEM] Could not load SEM engine: {e}")
        return _sem_engine

    cycle    = 0
    best_hd  = 1.0
    try:
        while max_cycles == 0 or cycle < max_cycles:
            cycle += 1
            print(f"\n{'═'*60}")
            print(f"  DREAM CYCLE {cycle}  |  {time.strftime('%H:%M:%S')}")
            print(f"{'═'*60}")

            # Standard evolution
            result  = run_evolution_cycle()
            best_hd = min(best_hd, result.get("best_hd", 1.0))

            # Self-evolving metacognition — 3 KG-derived cycles per dream cycle
            sem = _get_sem()
            if sem is not None:
                try:
                    print("   [SEM] Running 3 self-evolving metacognition cycles...")
                    sem_summary = sem.run(n_cycles=3, verbose=False)
                    sem._save_state()
                    print(
                        f"   [SEM] proof={sem_summary['proof_rate']*100:.0f}%  "
                        f"calibration_r={sem_summary['calibration_pearson_r']:.4f}  "
                        f"hebbian={sem_summary['hebbian_updates']}  "
                        f"total_cycles={sem_summary['total_cycles']}"
                    )
                except Exception as e:
                    print(f"   [SEM] cycle error: {e}")

            print(f"\n  All-time best HD this session: {best_hd:.4f}")
            print(f"  Gate:   {HD_COMMIT_GATE}")
            print(f"  To win: HD < 0.01 consistently")
            if best_hd < HD_COMMIT_GATE:
                print(f"\n  ✅ GATE CLEARED — best HD {best_hd:.4f} < {HD_COMMIT_GATE}")
            if max_cycles == 0 or cycle < max_cycles:
                print(f"\n  Sleeping {interval_s}s until next cycle...")
                time.sleep(interval_s)
    except KeyboardInterrupt:
        print(f"\n\n  Dream loop stopped. Cycles completed: {cycle}")
        print(f"  Best HD achieved: {best_hd:.4f}")
        _audit_entry("DREAM_LOOP_STOPPED", {"cycles": cycle, "best_hd": best_hd})


def watch_hd():
    """Live HD monitor — refreshes every 10s."""
    import os as _os
    while True:
        results = scan_project()
        _os.system("clear")
        print(f"  🔬 LIVE HD MONITOR  |  {time.strftime('%H:%M:%S')}  |  gate={HD_COMMIT_GATE}")
        print("─" * 70)
        for r in sorted(results, key=lambda x: x.get("hd", 1.0)):
            if "hd" in r:
                bar_len = int(r["hd"] * 40)
                bar     = "█" * bar_len + "░" * (40 - bar_len)
                gate_s  = "✅" if r["hd"] <= HD_COMMIT_GATE else "❌"
                print(f"  {gate_s} {r['file']:<45} HD={r['hd']:.4f} |{bar}|")
        hds = [r["hd"] for r in results if "hd" in r]
        if hds:
            print(f"\n  Mean: {sum(hds)/len(hds):.4f}  Best: {min(hds):.4f}  "
                  f"Above gate: {sum(1 for h in hds if h > HD_COMMIT_GATE)}/{len(hds)}")
        print("\n  Refreshing in 10s... (Ctrl+C to stop)")
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            break


def main():
    parser = argparse.ArgumentParser(description="SAGA Bootloader v1.0.0")
    parser.add_argument("--init",   action="store_true", help="Initialize factory")
    parser.add_argument("--cycle",  action="store_true", help="Run one evolution cycle")
    parser.add_argument("--dream",  action="store_true", help="Run infinite Dream State loop")
    parser.add_argument("--cycles", type=int, default=0,   help="Max cycles for --dream")
    parser.add_argument("--interval",type=int, default=300, help="Seconds between dream cycles")
    parser.add_argument("--watch",  action="store_true", help="Live HD monitor")
    parser.add_argument("--promote",action="store_true", help="Promote swarm_manifold nodes → KG")
    args = parser.parse_args()

    if args.init:
        init_factory()
    elif args.cycle:
        r = run_evolution_cycle()
        print(f"\n  Result: {r['status']}  HD: {r['hd_before']:.4f} → {r['hd_after']:.4f}")
    elif args.dream:
        dream_loop(max_cycles=args.cycles, interval_s=args.interval)
    elif args.watch:
        watch_hd()
    elif args.promote:
        n = _promote_swarm_nodes(limit=10)
        print(f"  Promoted {n} nodes from swarm_manifold → knowledge_graph")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
