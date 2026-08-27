"""
Safety-gate tests for the autonomous swarm path.
EPISTEMIC TIER: T1

Covers the four review findings on the live+autonomous path:
  A. constitutional verdict must be contract-legal (APPROVED|FLAG|QUARANTINE)
     and derived from the run — never an out-of-enum value like 'REJECTED',
     which falls through CONSTITUTIONAL_FACTORS to the 0.85 neutral factor
     and scores BETTER than QUARANTINE.
  B. the gate uses the named COHERENCE_GATE_THRESHOLD constant, not a literal.
  C. departments_collaborated must be the honest ok-count, not the roster size.
  D. max_agents parsing fails CLOSED — malformed input raises, never uncaps.

Pure-helper tests: no bridge server, no model calls, no Supabase.
Run: python tests/test_autonomous_gates.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from platform_helpers import (  # noqa: E402
    PLATFORM_DEPARTMENTS,
    CONSTITUTIONAL_FACTORS,
    COHERENCE_GATE_THRESHOLD,
    autonomous_completion_audit,
    parse_max_agents,
    swarm_collaborate_autonomous,
)

PASS = 0
FAIL = 0


def chk(name, cond, reason=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        print(f'  FAIL  {name}: {reason or "assertion failed"}')


def expect_raises(name, fn):
    try:
        fn()
        chk(name, False, 'expected ValueError, none raised')
    except ValueError:
        chk(name, True)
    except Exception as e:
        chk(name, False, f'expected ValueError, got {type(e).__name__}')


def ok_call(dept, objective, mode, upstream):
    return f"{dept['role']}: contribution ({len(upstream)} upstream)"


OBJ = 'Launch EU fintech in Q4'

# ── D. parse_max_agents fails closed ─────────────────────────────────────────
print('\nparse_max_agents (fail-closed cost ceiling):')
chk('None -> None (no explicit cap)', parse_max_agents(None) is None)
chk('5 -> 5', parse_max_agents(5) == 5)
chk("'7' -> 7 (numeric string ok)", parse_max_agents('7') == 7)
chk('39.0 -> 39 (integral float ok)', parse_max_agents(39.0) == 39)
expect_raises("'ten' raises", lambda: parse_max_agents('ten'))
expect_raises('-1 raises', lambda: parse_max_agents(-1))
expect_raises('0 raises', lambda: parse_max_agents(0))
expect_raises('True raises (bool is not a cap)', lambda: parse_max_agents(True))
expect_raises('5.7 raises (non-integral float)', lambda: parse_max_agents(5.7))
expect_raises('[] raises', lambda: parse_max_agents([]))

# ── A. verdict is contract-legal and derived ─────────────────────────────────
print('\nautonomous_completion_audit (contract-legal verdict):')
CONTRACT_VERDICTS = {'APPROVED', 'FLAG', 'QUARANTINE'}

full = swarm_collaborate_autonomous(OBJ, 'gtm', PLATFORM_DEPARTMENTS, ok_call)
audit_full = autonomous_completion_audit(full)
chk('clean full run -> APPROVED', audit_full['verdict'] == 'APPROVED',
    f"got {audit_full['verdict']}")
chk('clean full run -> no concerns', audit_full['concerns'] == [])

capped = swarm_collaborate_autonomous(OBJ, 'gtm', PLATFORM_DEPARTMENTS, ok_call, max_agents=5)
audit_capped = autonomous_completion_audit(capped)
chk('capped run -> FLAG', audit_capped['verdict'] == 'FLAG',
    f"got {audit_capped['verdict']}")
chk('capped run -> coherence concern names the gate',
    any('coherence gate' in c for c in audit_capped['concerns']),
    str(audit_capped['concerns'])[:120])
chk('capped run -> budget-skipped concern present',
    any('Budget-skipped' in c for c in audit_capped['concerns']))


def boom(dept, objective, mode, upstream):
    if dept['category'] == 'research':
        raise RuntimeError('agent crashed')
    return ok_call(dept, objective, mode, upstream)


errored = swarm_collaborate_autonomous(OBJ, 'gtm', PLATFORM_DEPARTMENTS, boom)
audit_err = autonomous_completion_audit(errored)
chk('errored run -> FLAG', audit_err['verdict'] == 'FLAG')
chk('errored run -> errored concern present',
    any('Errored departments' in c for c in audit_err['concerns']))

for name, audit in (('full', audit_full), ('capped', audit_capped), ('errored', audit_err)):
    chk(f'{name}: verdict in contract enum', audit['verdict'] in CONTRACT_VERDICTS,
        f"got {audit['verdict']}")
    chk(f'{name}: verdict has an explicit CONSTITUTIONAL_FACTORS entry',
        audit['verdict'] in CONSTITUTIONAL_FACTORS,
        'out-of-enum verdicts silently score the 0.85 neutral factor')

# ── B. gate uses the named constant ──────────────────────────────────────────
print('\ncoherence gate wiring:')
chk('threshold constant is phi',
    abs(COHERENCE_GATE_THRESHOLD - (5 ** 0.5 - 1) / 2) < 1e-12)
chk('capped-run concern quotes the constant value',
    any(f'{COHERENCE_GATE_THRESHOLD:.10f}' in c for c in audit_capped['concerns']),
    'gate must reference COHERENCE_GATE_THRESHOLD, not a duplicated literal')
bridge_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bridge.py')
with open(bridge_path, encoding='utf-8') as bridge_file:
    bridge_src = bridge_file.read()
chk("bridge no longer hardcodes a φ literal for the gate",
    '_phi = 0.6180339887' not in bridge_src)
chk("bridge no longer emits out-of-enum 'REJECTED' verdict",
    "'verdict': 'REJECTED'" not in bridge_src)
chk('bridge imports autonomous_completion_audit',
    'autonomous_completion_audit as _autonomous_audit' in bridge_src)
chk('bridge imports parse_max_agents (both parse sites fail closed)',
    'parse_max_agents as _parse_max_agents' in bridge_src
    and bridge_src.count('_parse_max_agents(data.get') == 2)

# ── C. honest collaborated count ─────────────────────────────────────────────
print('\nhonest departments_collaborated:')
chk('executor: capped run ok-count == 5', capped['departments_collaborated'] == 5)
chk('executor: errored run ok-count excludes failures',
    errored['departments_collaborated']
    == len(PLATFORM_DEPARTMENTS) - sum(1 for d in PLATFORM_DEPARTMENTS
                                       if d['category'] == 'research'))
chk('bridge threads the honest count into the result',
    "collaborated_count = swarm['departments_collaborated']" in bridge_src
    and 'collaborated_count if collaborated_count is not None' in bridge_src)

# ── Determinism (repo rule: 3 runs, byte-identical) ──────────────────────────
print('\ndeterminism (3 runs):')
runs = [autonomous_completion_audit(
            swarm_collaborate_autonomous(OBJ, 'gtm', PLATFORM_DEPARTMENTS, ok_call, max_agents=7))
        for _ in range(3)]
chk('audit deterministic across 3 runs', runs[0] == runs[1] == runs[2])

print(f'\n{"=" * 40}')
print(f'PASS: {PASS}  FAIL: {FAIL}')
if FAIL:
    print('RESULT: FAIL — autonomous safety-gate regression')
    sys.exit(1)
print('RESULT: PASS — autonomous safety gates verified')
