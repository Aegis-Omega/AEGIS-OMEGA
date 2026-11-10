"""
SOVEREIGN AGI OS — UNIFIED ENTRYPOINT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Version: 3.2.0 | SWARM: 8.0 | Author: Tarik Skalic

THE COMPLETE STACK (boot order):

  Layer 1 — BODY       biology/cybernetic_core.py
    MetabolicBattery, EntropyImmuneNetwork, EndocrineHPAAxis, SovereignMemoryStrata

  Layer 2 — PHYSICS    biology/sovereign_kernel.py
    SAGA_Immune_System, RelativisticPhotonicManifold (Ψ·e^{-iωt})

  Layer 3 — SOUL       biology/digital_being.py
    DigitalBeing (15-gate pipeline, GraphRAG, SLECMA, Ego Singularity)

  Layer 4 — EVOLUTION  biology/metacognitive_evolution.py
    HDHistoryTracker, NeuromodulatorTuner, KnowledgeGraphEvolver

  Layer 5 — SWARM      swarm/swarm_core.py
    PhotonicResolver + QuantumManifold (z-level hierarchy, Dream State A²)

  Layer 6 — HD ENGINE  benchmark/multi_model_runner.py
    9-task hallucination delta benchmark across NVIDIA NIM models

  Layer 7 — ARC        arc/train.py + arc/eval.py
    PPO transformer policy — HD_arc = 1 - accuracy on ARC tasks

  Layer 8 — PROOFS     proof_suite.py
    8 verified proofs: genome sync, structural truth, SHA-256 ledger,
    Shannon entropy, HD anchor, circuit breaker, SLECMA gate, evo stasis

  Layer 9 — GOVERNANCE state.json + validate-state.js + cognitive-eval.js

HD = |claimed − actual|        — the one true metric
All .forge/ writes: .tmp → os.replace()   — constitutional law

Usage:
    python sovereign_os.py [--boot] [--proofs] [--status]
"""

import os
import sys
import json
import argparse
import importlib.util
from pathlib import Path
from datetime import datetime, timezone

FORGE_DIR  = Path(__file__).parent / ".forge"
STATE_PATH = FORGE_DIR / "state.json"


def _load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))

def _atomic_write_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER STATUS CHECKS (non-destructive — read-only)
# ══════════════════════════════════════════════════════════════════════════════

def _check_biology() -> dict:
    bio_dir = Path(__file__).parent / "biology"
    files = ["cybernetic_core.py", "sovereign_kernel.py", "digital_being.py", "metacognitive_evolution.py"]
    present = [f for f in files if (bio_dir / f).exists()]
    lines   = sum((bio_dir / f).read_text(encoding="utf-8").count("\n") for f in present if (bio_dir / f).exists())
    return {
        "layer": "BIOLOGY",
        "files": len(present),
        "expected": len(files),
        "lines": lines,
        "ok": len(present) == len(files),
        "detail": present,
    }


def _check_swarm() -> dict:
    manifold_path = FORGE_DIR / "swarm_manifold.json"
    if not manifold_path.exists():
        return {"layer": "SWARM", "ok": False, "detail": "swarm_manifold.json missing"}
    manifold = json.loads(manifold_path.read_text(encoding="utf-8"))
    return {
        "layer":         "SWARM",
        "ok":            True,
        "version":       manifold.get("version"),
        "resolver_nodes": len(manifold.get("resolver_nodes", [])),
        "hyperedges":    len(manifold.get("hyperedges", [])),
        "epiphanies":    len(manifold.get("epiphanies", [])),
        "dream_cycles":  manifold.get("dream_cycles", 0),
    }


def _check_hd_engine() -> dict:
    state = _load_state()
    bm    = state.get("benchmark", {})
    return {
        "layer":        "HD_ENGINE",
        "ok":           bm.get("last_hd_score", 1.0) < 0.20,
        "mean_hd":      bm.get("mean_hd", 1.0),
        "elected_model": bm.get("elected_model", "unknown"),
        "last_run":     bm.get("last_run_at", "never"),
    }


def _check_arc() -> dict:
    state    = _load_state()
    arc_bm   = state.get("arc_benchmark", {})
    arc_dir  = Path(__file__).parent / "arc"
    ok       = arc_dir.exists() and (arc_dir / "train.py").exists()
    return {
        "layer":   "ARC",
        "ok":      ok,
        "hd_arc":  arc_bm.get("hd_arc", "not_run"),
        "mean_acc": arc_bm.get("mean_acc", "not_run"),
        "last_run": arc_bm.get("last_run_at", "never"),
    }


def _check_proofs() -> dict:
    proof_path = Path(__file__).parent / "proof_suite.py"
    return {
        "layer": "PROOFS",
        "ok":    proof_path.exists(),
        "detail": "8 proofs: GENOME_SYNC, STRUCTURAL_TRUTH, BIO_GROUNDING, ENTROPY, HD_ANCHOR, CIRCUIT_BREAKER, SLECMA, EVO_STASIS",
    }


def _check_state() -> dict:
    state = _load_state()
    neuro = state.get("cognition", {}).get("neuromodulators", {})
    return {
        "layer":     "SOVEREIGN_OS",
        "ok":        state.get("version") == "3.2.0",
        "version":   state.get("version"),
        "phase":     state.get("lifecycle", {}).get("phase"),
        "stress":    neuro.get("stress_level"),
        "attention": neuro.get("attention_gain"),
        "rir":       neuro.get("rir_signal"),
        "atp":       state.get("metabolism", {}).get("atp_balance"),
    }


# ══════════════════════════════════════════════════════════════════════════════
# BOOT SEQUENCE
# ══════════════════════════════════════════════════════════════════════════════

def boot(run_proofs: bool = False) -> dict:
    """
    Full OS boot. Checks all layers, optionally runs proof suite.
    Does NOT mutate state unless a correction is needed.
    """
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║         SOVEREIGN AGI OS v3.2.0 — BOOT SEQUENCE             ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    layers = [
        _check_state,
        _check_biology,
        _check_swarm,
        _check_hd_engine,
        _check_arc,
        _check_proofs,
    ]

    results = []
    for fn in layers:
        r = fn()
        status = "✓" if r.get("ok") else "✗"
        name   = r["layer"].ljust(14)
        print(f"║  [{status}] {name}", end="")

        if r["layer"] == "SOVEREIGN_OS":
            print(f"  v{r.get('version')} | stress={r.get('stress'):.4f} | attn={r.get('attention'):.2f} | ATP={r.get('atp')}", end="")
        elif r["layer"] == "BIOLOGY":
            print(f"  {r.get('files')}/{r.get('expected')} files | {r.get('lines')} lines", end="")
        elif r["layer"] == "SWARM":
            print(f"  {r.get('resolver_nodes')} nodes | {r.get('epiphanies')} epiphanies | {r.get('dream_cycles')} dream cycles", end="")
        elif r["layer"] == "HD_ENGINE":
            print(f"  HD={r.get('mean_hd'):.4f} | model={r.get('elected_model')}", end="")
        elif r["layer"] == "ARC":
            print(f"  HD_arc={r.get('hd_arc')} | acc={r.get('mean_acc')}", end="")
        elif r["layer"] == "PROOFS":
            print(f"  {r.get('detail')[:50]}", end="")

        print("  ║")
        results.append(r)

    all_ok = all(r.get("ok") for r in results)
    print("╠══════════════════════════════════════════════════════════════╣")
    print(f"║  STATUS: {'ALL SYSTEMS GO' if all_ok else 'DEGRADED — see layers above'}{'.' * (48 - (14 if all_ok else 30))}  ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    if run_proofs:
        print("Running 8-proof validation suite...\n")
        sys.path.insert(0, str(Path(__file__).parent))
        from proof_suite import run_all_proofs
        proof_result = run_all_proofs(verbose=True)

        # Write proof result to state
        state = _load_state()
        state["proof_suite"] = proof_result
        state["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_state(state)
        print(f"\nProof suite written to state.json.")

    return {"layers": results, "all_ok": all_ok}


# ══════════════════════════════════════════════════════════════════════════════
# STATUS REPORT
# ══════════════════════════════════════════════════════════════════════════════

def status() -> None:
    """Print full OS status including manifold, HD, bio metrics."""
    state   = _load_state()
    neuro   = state.get("cognition", {}).get("neuromodulators", {})
    bm      = state.get("benchmark", {})
    gh      = state.get("graph_health", {})
    arc_bm  = state.get("arc_benchmark", {})

    # Context HD
    stress  = neuro.get("stress_level", 0)
    attn    = neuro.get("attention_gain", 0)
    rir     = neuro.get("rir_signal", 0)
    lr      = neuro.get("learning_rate", 0)
    ctx_hd  = attn * 0.3 + (1 - stress) * 0.3 + (1 - rir) * 0.2 + lr * 0.2

    print(f"""
SOVEREIGN AGI OS v{state.get('version')} — STATUS
{'─'*60}
BIO STATE
  Stress:    {stress:.4f}
  Attention: {attn:.4f}
  RIR:       {rir:.4f}
  ATP:       {state.get('metabolism', {}).get('atp_balance', 0)}
  Context_HD: {ctx_hd:.4f}

GRAPH STATE
  Resolver nodes:  {gh.get('resolver_nodes', 0)}
  Hyperedges:      {gh.get('edge_count', 0)}
  Epiphanies:      {gh.get('epiphanies', 0)}
  Dream cycles:    {gh.get('dream_cycles', 0)}
  Graph HD:        {gh.get('graph_hd', 'N/A')}
  HD_swarm:        {gh.get('hd_swarm', 'N/A')}
  HD_photonic:     {state.get('photonic_resonance', {}).get('hd_photonic', 'N/A')}

BENCHMARK
  Elected model:   {bm.get('elected_model', 'N/A')}
  Mean HD:         {bm.get('mean_hd', 'N/A')}
  Last run:        {bm.get('last_run_at', 'N/A')}

ARC
  HD_arc:          {arc_bm.get('hd_arc', 'not_run')}
  Mean accuracy:   {arc_bm.get('mean_acc', 'not_run')}
  Curriculum level:{arc_bm.get('curriculum_level', 'not_run')}

DEADLINE: 2026-04-16 (Kaggle AGI)
{'─'*60}""")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sovereign AGI OS v3.2.0")
    parser.add_argument("--boot",   action="store_true", help="Run full boot sequence")
    parser.add_argument("--proofs", action="store_true", help="Run 8-proof validation suite during boot")
    parser.add_argument("--status", action="store_true", help="Print system status")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.boot or args.proofs:
        boot(run_proofs=args.proofs)
    else:
        boot(run_proofs=False)
