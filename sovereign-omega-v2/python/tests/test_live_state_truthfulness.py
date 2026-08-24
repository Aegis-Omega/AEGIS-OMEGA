#!/usr/bin/env python3
"""RED-first behavioral contract for bridge live-state context truthfulness.

The bridge must distinguish current runtime observations from stored/historical CI
facts and from stronger verification claims. This AST-extracts the exact production
`_build_live_state_context` body so the large CoreMatrix module is not imported.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / 'sovereign-omega-v2' / 'python' / 'bridge.py'


def load_builder():
    source = BRIDGE.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(BRIDGE))
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == '_build_live_state_context'
    )
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    ns = {}
    exec(compile(module, str(BRIDGE), 'exec'), ns)
    return ns['_build_live_state_context']


class MatrixStub:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def emit_vcg_telemetry(self):
        if self.error is not None:
            raise self.error
        return dict(self.payload or {})


def run_builder(payload=None, error=None):
    builder = load_builder()
    builder.__globals__['matrix'] = MatrixStub(payload=payload, error=error)
    return builder()


class LiveStateTruthfulnessTests(unittest.TestCase):
    def test_only_current_telemetry_is_reported_as_observation(self):
        text = run_builder({
            'sequence': 17,
            'epoch': 4,
            'corruption_count': 0,
            'drift_index': 0.2,
            'pgcs_passes': True,
        })
        upper = text.upper()
        self.assertIn('RUNTIME OBSERVATION', upper)
        self.assertIn('SEQUENCE: 17', upper)
        self.assertIn('EPOCH: 4', upper)
        self.assertIn('CORRUPTION', upper)
        self.assertIn('PGCS', upper)

    def test_live_context_does_not_embed_stale_ci_test_counts(self):
        text = run_builder({
            'sequence': 1, 'epoch': 1, 'corruption_count': 0,
            'drift_index': 0.0, 'pgcs_passes': True,
        })
        for stale_claim in ('Gates operational: 605', 'Rust tests verified: 6,862', 'TypeScript tests verified: 3,176'):
            self.assertNotIn(stale_claim, text)

    def test_observation_digest_is_not_called_a_certificate(self):
        text = run_builder({
            'sequence': 9, 'epoch': 2, 'corruption_count': 0,
            'drift_index': 0.0, 'pgcs_passes': True,
        })
        lower = text.lower()
        self.assertIn('digest', lower)
        self.assertNotIn('certif', lower)

    def test_runtime_health_does_not_claim_global_chain_or_replay_authority(self):
        text = run_builder({
            'sequence': 9, 'epoch': 2, 'corruption_count': 0,
            'drift_index': 0.0, 'pgcs_passes': True,
        })
        upper = text.upper()
        self.assertNotIn('CHAIN: INTACT', upper)
        self.assertNotIn('REPLAY: SOVEREIGN', upper)
        self.assertNotIn('T0 VERDICT', upper)
        self.assertNotIn('VERIFIED FACTS', upper)
        self.assertIn('DOES NOT ESTABLISH', upper)

    def test_unavailable_telemetry_is_explicit_unknown_not_t2_fabrication(self):
        text = run_builder(error=RuntimeError('offline'))
        upper = text.upper()
        self.assertIn('UNAVAILABLE', upper)
        self.assertIn('UNKNOWN', upper)
        self.assertNotIn('CONSTITUTIONAL MACHINERY NOT CONFIRMED ACTIVE', upper)


if __name__ == '__main__':
    unittest.main(verbosity=2)
