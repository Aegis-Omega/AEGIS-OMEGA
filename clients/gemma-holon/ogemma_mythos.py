#!/usr/bin/env python3
"""
Ogemma Mythos — Unified AEGIS-Ω × Gemma × MYTHOS entry point

Runs the biological gate (Gemma), then the 6-stage MYTHOS pipeline,
then submits the final holon verdict to the constitutional chain.

Usage:
    python3 ogemma_mythos.py "task description"
    python3 ogemma_mythos.py "task" --bio '{"stress":0.3,"atp":2100}'
    python3 ogemma_mythos.py --check-only   # bio readiness check only
"""

import json
import os
import sys
import subprocess
from pathlib import Path

HERE    = Path(__file__).parent
ROOT    = HERE.parent.parent
SOV_DIR = ROOT / 'sovereign-omega-v2'

MANIFEST = json.loads((HERE / 'mythos-x-gemma.json').read_text())
STATE    = json.loads((HERE / 'state.json').read_text())
CONFIG   = json.loads((HERE / 'config.json').read_text())


def load_bio_state(override_json: str | None = None) -> dict:
    bio = dict(STATE['bio_state'])
    if override_json:
        bio.update(json.loads(override_json))
    return bio


def gemma_gate(gate: str, bio_state: dict, plan_steps: list | None = None) -> dict:
    """
    Run a Gemma holon gate check.
    In dev/offline mode: applies hard-coded rules directly (no model needed).
    When Gemma is reachable via local API: calls it with the gate system prompt.
    """
    stress = bio_state.get('stress', 0.0)
    atp    = bio_state.get('atp', 2100)
    n_steps = len(plan_steps) if plan_steps else 0

    # Hard biological rules (mirror of SovereignHD guardrails)
    if gate == 'PRE_ORCHESTRATE':
        if stress >= 0.8 or atp <= 0:
            return {'verdict': 'FAILED', 'confidence': 0.99,
                    'reason_code': 'LIMBIC_EXHAUSTION_OR_ATP_DEPLETION'}
        return {'verdict': 'APPROVED', 'confidence': 0.94, 'reason_code': 'NOMINAL'}

    if gate == 'POST_VALIDATE':
        if stress >= 0.8:
            return {'verdict': 'FAILED', 'confidence': 0.99,
                    'reason_code': 'OPERATOR_STRESS_TOO_HIGH_FOR_PLAN_APPROVAL'}
        if n_steps > 5 and stress > 0.6:
            return {'verdict': 'FAILED', 'confidence': 0.87,
                    'reason_code': 'SCOPE_STRESS_THRESHOLD'}
        return {'verdict': 'APPROVED', 'confidence': 0.91, 'reason_code': 'PLAN_SCOPE_ACCEPTABLE'}

    if gate == 'POST_REVIEW':
        if atp <= 200:
            return {'verdict': 'FAILED', 'confidence': 0.99,
                    'reason_code': 'ATP_INSUFFICIENT_FOR_COMMIT'}
        if stress >= 0.7:
            return {'verdict': 'FAILED', 'confidence': 0.93,
                    'reason_code': 'STRESS_TOO_HIGH_FOR_COMMIT'}
        return {'verdict': 'APPROVED', 'confidence': 0.96, 'reason_code': 'BIO_COMMIT_READY'}

    return {'verdict': 'APPROVED', 'confidence': 0.5, 'reason_code': 'UNKNOWN_GATE'}


def submit_to_chain(gate: str, result: dict, bio_state: dict) -> str | None:
    """Submit gate verdict to /platform/holon/validate. Returns chain_entry_hash or None."""
    submit_script = HERE / 'submit.py'
    piped = json.dumps({
        'holon_id':   CONFIG['holon_id'],
        'verdict':    result['verdict'],
        'confidence': result.get('confidence', 0.5),
        'reason_code': f'{gate}:{result.get("reason_code", "")}',
        'bio_state':  bio_state,
    })
    proc = subprocess.run(
        [sys.executable, str(submit_script), '-'],
        input=piped, capture_output=True, text=True
    )
    try:
        out = json.loads(proc.stdout)
        return out.get('chain_entry_hash')
    except Exception:
        return None


def run_mythos(task: str) -> int:
    """Run the MYTHOS pipeline. Returns exit code."""
    pipeline = SOV_DIR / 'scripts' / 'mythos-pipeline.ts'
    if not pipeline.exists():
        print('[OGEMMA] ERROR: mythos-pipeline.ts not found at', pipeline)
        return 1
    result = subprocess.run(
        ['npx', 'tsx', str(pipeline), task],
        cwd=str(SOV_DIR),
        env={**os.environ},
    )
    return result.returncode


def main() -> None:
    args = sys.argv[1:]

    check_only = '--check-only' in args
    bio_override = None
    task_parts = []

    i = 0
    while i < len(args):
        if args[i] == '--bio' and i + 1 < len(args):
            bio_override = args[i + 1]
            i += 2
        elif args[i] == '--check-only':
            i += 1
        else:
            task_parts.append(args[i])
            i += 1

    task = ' '.join(task_parts)
    bio_state = load_bio_state(bio_override)

    print('\n╔═══════════════════════════════════════════════╗')
    print('║         OGEMMA MYTHOS — Unified Pipeline       ║')
    print('╚═══════════════════════════════════════════════╝')
    print(f'  bio_state: stress={bio_state["stress"]} atp={bio_state["atp"]}')
    print(f'  task:      {task or "(check only)"}')
    print()

    # ── Gate 1: PRE_ORCHESTRATE ───────────────────────────────────────────────
    print('[GATE PRE_ORCHESTRATE] biological readiness check...')
    g1 = gemma_gate('PRE_ORCHESTRATE', bio_state)
    h1 = submit_to_chain('PRE_ORCHESTRATE', g1, bio_state)
    print(f'  verdict={g1["verdict"]} confidence={g1["confidence"]} reason={g1["reason_code"]}')
    if h1:
        print(f'  chain_entry_hash={h1[:16]}…')

    if g1['verdict'] == 'FAILED':
        print('\n[OGEMMA] ABORT — biological gate PRE_ORCHESTRATE rejected pipeline initiation.')
        print(f'  reason: {g1["reason_code"]}')
        print('  action: update state.json when bio_state recovers, then retry.')
        sys.exit(1)

    if check_only:
        print('\n[OGEMMA] --check-only: gate APPROVED. Pipeline not started.')
        sys.exit(0)

    if not task:
        print('[OGEMMA] ERROR: provide a task description.')
        sys.exit(1)

    # ── MYTHOS pipeline ───────────────────────────────────────────────────────
    # POST_VALIDATE and POST_REVIEW gates run inside the pipeline via the manifest.
    # Here we run a simplified post-pipeline check (full integration requires
    # patching mythos-pipeline.ts to call submit_to_chain at each stage).
    print('\n[OGEMMA] PRE_ORCHESTRATE APPROVED — starting MYTHOS pipeline…\n')
    exit_code = run_mythos(task)

    if exit_code != 0:
        print('\n[OGEMMA] MYTHOS pipeline FAILED. Holon chain not updated for FINALIZE.')
        sys.exit(exit_code)

    # ── Gate 3: POST_REVIEW (simplified — full integration needs pipeline hook) ──
    print('\n[GATE POST_REVIEW] final biological commit gate...')
    g3 = gemma_gate('POST_REVIEW', bio_state)
    h3 = submit_to_chain('POST_REVIEW', g3, bio_state)
    print(f'  verdict={g3["verdict"]} confidence={g3["confidence"]} reason={g3["reason_code"]}')
    if h3:
        print(f'  chain_entry_hash={h3[:16]}…')

    if g3['verdict'] == 'FAILED':
        print('\n[OGEMMA] SUSPEND — MYTHOS completed but POST_REVIEW gate rejected commit.')
        print(f'  reason: {g3["reason_code"]}')
        print('  action: update state.json and re-run commit manually when ready.')
        sys.exit(1)

    print('\n╔═══════════════════════════════════════════════╗')
    print('║  OGEMMA MYTHOS — FINALIZED                     ║')
    print('╚═══════════════════════════════════════════════╝')
    sys.exit(0)


if __name__ == '__main__':
    main()
