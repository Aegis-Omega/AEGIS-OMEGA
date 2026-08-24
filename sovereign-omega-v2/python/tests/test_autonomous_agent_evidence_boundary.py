#!/usr/bin/env python3
"""RED-first contract for autonomous agent execution evidence.

Provider failure/refusal must not become a successful agent artifact, and missing
stored constitutional state must not be exported as APPROVED.
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest
import urllib.request
from contextlib import contextmanager
from pathlib import Path

PYTHON_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_DIR))

import platform_helpers as ph


@contextmanager
def patched_env(**values: str):
    saved = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class AutonomousAgentEvidenceBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.dept = ph.PLATFORM_DEPARTMENTS[0]

    def _with_anth_client(self, fake_module, fn):
        saved = sys.modules.get('anth_client')
        sys.modules['anth_client'] = fake_module
        try:
            return fn()
        finally:
            if saved is None:
                sys.modules.pop('anth_client', None)
            else:
                sys.modules['anth_client'] = saved

    def test_missing_provider_does_not_count_template_as_successful_agent(self):
        fake_module = types.SimpleNamespace(
            get_client=lambda: (_ for _ in ()).throw(RuntimeError('provider unavailable')),
            make_cached_system=lambda value: value,
        )

        def run():
            call = ph.make_autonomous_agent_call()
            return ph.swarm_collaborate_autonomous(
                'objective', 'analysis', [self.dept], call, max_agents=1
            )

        result = self._with_anth_client(fake_module, run)
        artifact = result['artifacts'][0]
        self.assertNotEqual(artifact['status'], 'ok', artifact)
        self.assertEqual(artifact['output'], '', artifact)
        self.assertEqual(result['departments_collaborated'], 0, result)

    def test_provider_refusal_does_not_count_template_as_successful_agent(self):
        class Messages:
            def create(self, **kwargs):
                return types.SimpleNamespace(stop_reason='refusal', content=[])

        fake_client = types.SimpleNamespace(messages=Messages())
        fake_module = types.SimpleNamespace(
            get_client=lambda: fake_client,
            make_cached_system=lambda value: value,
        )

        def run():
            call = ph.make_autonomous_agent_call()
            return ph.swarm_collaborate_autonomous(
                'objective', 'analysis', [self.dept], call, max_agents=1
            )

        result = self._with_anth_client(fake_module, run)
        artifact = result['artifacts'][0]
        self.assertNotEqual(artifact['status'], 'ok', artifact)
        self.assertEqual(artifact['output'], '', artifact)
        self.assertEqual(result['departments_collaborated'], 0, result)

    def test_compliance_export_missing_verdict_is_not_approved(self):
        rows = [{
            'cycle_id': 'cycle-1',
            'objective': 'objective',
            'mode': 'analysis',
            'arr_usd': 1,
            'created_at': '2026-08-24T00:00:00Z',
        }]
        saved_urlopen = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=8: FakeResponse(rows)
        try:
            with patched_env(
                SUPABASE_URL='https://example.supabase.co',
                SUPABASE_SERVICE_ROLE_KEY='test-key',
            ):
                records = ph.fetch_compliance_export(None, None, 10)
        finally:
            urllib.request.urlopen = saved_urlopen

        self.assertEqual(len(records), 1)
        self.assertNotEqual(records[0]['constitutional_verdict'], 'APPROVED', records[0])
        self.assertIn(records[0]['constitutional_verdict'], ('UNKNOWN', 'QUARANTINE'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
