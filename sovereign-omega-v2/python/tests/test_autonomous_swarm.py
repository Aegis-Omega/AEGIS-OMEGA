"""
Contract tests for the autonomous per-agent swarm executor.
EPISTEMIC TIER: T1

Verifies the orchestration itself — dependency ordering, per-layer knowledge
transfer, the budget cap, determinism, and error isolation — using a fake
agent_call so no model access is required. Run: python tests/test_autonomous_swarm.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import platform_helpers as p  # noqa: E402

PASS = 0
FAIL = 0


def chk(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        print(f'  FAIL  {name}')


def fake_call(record):
    def _call(dept, objective, mode, upstream):
        record.append((dept['id'], dept['category'], len(upstream)))
        return f"{dept['role']}: {len(upstream)} upstream -> contribution"
    return _call


ROSTER = p.PLATFORM_DEPARTMENTS
OBJ = 'Launch EU fintech in Q4'

# 1 — full run: every agent executes exactly once, in order
rec = []
r = p.swarm_collaborate_autonomous(OBJ, 'gtm', ROSTER, fake_call(rec))
chk('all agents executed', r['agents_executed'] == len(ROSTER))
chk('all collaborated ok', r['departments_collaborated'] == len(ROSTER))
chk('one call per agent', len(rec) == len(ROSTER))
chk('artifact count == roster', len(r['artifacts']) == len(ROSTER))
chk('execution tagged autonomous', r['execution'] == 'autonomous-per-agent')

# 2 — knowledge transfer: first layer sees nothing, later layers see upstream
research_up = [u for (_i, c, u) in rec if c == 'research']
gov_up = [u for (_i, c, u) in rec if c in ('governance', 'constitutional')]
chk('research layer has 0 upstream', len(research_up) > 0 and all(u == 0 for u in research_up))
chk('governance layer sees upstream', len(gov_up) > 0 and all(u > 0 for u in gov_up))

# 3 — upstream is exactly the agents in strictly-earlier layers (frozen per layer)
gov_layer = p._layer_index('governance')
expected_gov_upstream = sum(1 for d in ROSTER if p._layer_index(d['category']) < gov_layer)
chk('governance upstream == all prior-layer agents', all(u == expected_gov_upstream for u in gov_up))

# 4 — same-layer peers are NOT visible to each other (layer isolation)
chk('same-layer agents share identical upstream', len(set(research_up)) == 1)

# 5 — budget cap: only N run, the rest are skipped, only N calls happen
rec2 = []
r2 = p.swarm_collaborate_autonomous(OBJ, 'gtm', ROSTER, fake_call(rec2), max_agents=5)
chk('cap: 5 executed', r2['agents_executed'] == 5)
chk('cap: 5 collaborated', r2['departments_collaborated'] == 5)
chk('cap: only 5 calls made', len(rec2) == 5)
chk('cap: remainder skipped', sum(1 for a in r2['artifacts'] if a['status'] == 'skipped') == len(ROSTER) - 5)

# 6 — determinism: identical inputs produce byte-identical artifacts (3 runs)
runs = [p.swarm_collaborate_autonomous(OBJ, 'gtm', ROSTER, fake_call([]))['artifacts'] for _ in range(3)]
chk('deterministic across 3 runs', runs[0] == runs[1] == runs[2])

# 7 — error isolation: a raising agent is captured, run completes, failures
#     never enter the upstream store (downstream agents don't see them)
def boom(dept, objective, mode, upstream):
    if dept['category'] == 'research':
        raise RuntimeError('agent crashed')
    return f"{dept['role']}: ok ({len(upstream)} upstream)"

r3 = p.swarm_collaborate_autonomous(OBJ, 'gtm', ROSTER, boom)
errors = [a for a in r3['artifacts'] if a['status'].startswith('error')]
n_research = sum(1 for d in ROSTER if d['category'] == 'research')
chk('failing agents captured as error', len(errors) == n_research)
chk('run completes despite failures', r3['agents_executed'] == len(ROSTER))
chk('ok count excludes failures', r3['departments_collaborated'] == len(ROSTER) - n_research)

# 8 — scales with a dynamic roster (ties to the de-hardcode): +2 agents -> +2 executed
big = ROSTER + [
    {'id': 'GRW-01', 'role': 'Growth', 'category': 'marketing'},
    {'id': 'AIX-01', 'role': 'AgentOps', 'category': 'engineering'},
]
r4 = p.swarm_collaborate_autonomous(OBJ, 'gtm', big, fake_call([]))
chk('scales beyond default roster', r4['agents_executed'] == len(ROSTER) + 2)

print(f'\nPASS: {PASS}  FAIL: {FAIL}')
print('RESULT:', 'PASS — autonomous executor verified' if FAIL == 0 else 'FAIL')
sys.exit(1 if FAIL else 0)
