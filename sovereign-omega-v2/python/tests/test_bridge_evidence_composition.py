#!/usr/bin/env python3
"""RED-first behavioral contract for the live bridge evidence composition.

The production bridge module allocates a large CoreMatrix at import time. This test
therefore AST-extracts only `_platform_run_collaboration` and executes that exact
function body against deterministic stubs. It tests behavior, not regex shape.
"""
from __future__ import annotations

import ast
import json
import threading
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / 'sovereign-omega-v2' / 'python' / 'bridge.py'


class QueueStub:
    def __init__(self):
        self.items = []

    def put(self, value):
        self.items.append(value)


def load_runner():
    source = BRIDGE.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(BRIDGE))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == '_platform_run_collaboration'
    )
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = {'json': json}
    exec(compile(module, str(BRIDGE), 'exec'), ns)
    return ns['_platform_run_collaboration']


def make_runtime(*, live_audit=None, autonomous_result=None):
    q = QueueStub()
    captured = {'fitness_verdict': 'UNSET', 'mc_tiers': []}
    executions = {'exec-1': {'email': 'operator@example.invalid'}}

    if live_audit is None:
        live_audit = {'verdict': 'QUARANTINE', 'concerns': ['TEST_QUARANTINE']}

    def swarm_live(*args, **kwargs):
        return {
            'artifacts': [{'role': 'Research', 'output': 'candidate output'}],
            'constitutional_audit': dict(live_audit),
            'projection': {
                'first_year_arr_usd': 1,
                'tier': 'T2',
                'governed_note': 'candidate',
            },
        }

    if autonomous_result is None:
        autonomous_result = {
            'agents_total': 1,
            'agents_executed': 1,
            'departments_collaborated': 0,
            'artifacts': [{
                'id': 'RES-01', 'role': 'Research', 'category': 'research',
                'status': 'provider_unavailable', 'output': '',
            }],
        }

    def eval_fitness(prev, artifacts, objective, cycle_verdict=None):
        captured['fitness_verdict'] = cycle_verdict
        return {'Research': {'fitness_score': 0.0, 'viability_score': 0.0}}

    def mc_observe(layer, signal, tier):
        captured['mc_tiers'].append((layer, tier, signal))
        return 'b' * 64

    canon = types.SimpleNamespace(
        payload_digest=lambda value: 'digest',
        emit_envelope=lambda **kwargs: kwargs,
    )

    ns = {
        '_exec_queues': {'exec-1': q},
        '_PLATFORM_DEPARTMENTS': [{'id': 'RES-01', 'role': 'Research', 'category': 'research'}],
        '_swarm_live': swarm_live,
        '_swarm_autonomous': lambda *args, **kwargs: autonomous_result,
        '_make_autonomous_agent_call': lambda: object(),
        'CONSTITUTIONAL_SYSTEM_COMPACT': 'constitution',
        '_build_live_state_context': lambda: 'state',
        '_mc_recent_context': lambda n=3: 'history',
        '_retrieve_swarm_memory': lambda objective, mode: '',
        '_platform_dept_output': lambda objective, mode, dept: 'DEMO TEMPLATE',
        '_platform_ts': lambda: '2026-08-24T00:00:00Z',
        '_retrieve_prior_artifacts': lambda objective, mode: [],
        '_eval_fitness': eval_fitness,
        '_store_fitness': lambda *args, **kwargs: None,
        '_mc_observe': mc_observe,
        '_mc_chain_integrity_valid': lambda: True,
        '_platform_record_cycle': lambda *args, **kwargs: None,
        '_award_graces': lambda *args, **kwargs: None,
        '_canon_env': canon,
        '_SWARM_MODEL': 'test-model',
        '_executions': executions,
        '_executions_lock': threading.Lock(),
    }
    return q, captured, executions, ns


def run_case(*, live: bool, autonomous: bool = False, live_audit=None, autonomous_result=None):
    runner = load_runner()
    q, captured, executions, ns = make_runtime(
        live_audit=live_audit,
        autonomous_result=autonomous_result,
    )
    runner.__globals__.update(ns)
    runner(
        'exec-1', 'objective', 'analysis', live,
        email='operator@example.invalid', generation=1,
        memory_context='', autonomous=autonomous, max_agents=1,
    )
    return executions['exec-1']['result'], captured, q


class BridgeEvidenceCompositionTests(unittest.TestCase):
    def test_live_mode_does_not_self_promote_model_semantics_to_t1(self):
        result, _, _ = run_case(live=True)
        self.assertEqual(result['constitutional_audit']['verdict'], 'QUARANTINE')
        self.assertEqual(result['envelope']['epistemic_tier'], 'T2', result['envelope'])

    def test_constitutional_verdict_is_bound_into_fitness_computation(self):
        _, captured, _ = run_case(live=True)
        self.assertEqual(captured['fitness_verdict'], 'QUARANTINE', captured)

    def test_demo_template_is_not_constitutionally_approved_by_default(self):
        result, captured, _ = run_case(live=False)
        self.assertNotEqual(result['constitutional_audit']['verdict'], 'APPROVED', result)
        self.assertEqual(captured['fitness_verdict'], 'QUARANTINE', captured)

    def test_autonomous_failed_agents_are_not_reported_as_collaborated(self):
        result, captured, _ = run_case(live=True, autonomous=True)
        self.assertEqual(result['constitutional_audit']['verdict'], 'QUARANTINE', result)
        self.assertEqual(result['departments_collaborated'], 0, result)
        self.assertEqual(captured['fitness_verdict'], 'QUARANTINE', captured)

    def test_audit_chain_hash_is_actual_metacognitive_entry_not_detached_digest(self):
        result, _, _ = run_case(live=True)
        self.assertEqual(result['audit_chain_hash'], 'b' * 64, result)
        self.assertTrue(result['chain_valid'], result)


if __name__ == '__main__':
    unittest.main(verbosity=2)
