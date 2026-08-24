#!/usr/bin/env python3
"""RED-first contract for the live platform swarm epistemic boundary.

A provider response, fallback template, persisted model output, or tool-discovery
transport failure is never authority. These tests intentionally fail against the
current main implementation before the production repair is added.
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


class SwarmEpistemicBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.depts = ph.PLATFORM_DEPARTMENTS[:2]

    def assert_quarantined(self, result: dict, reason_fragment: str | None = None):
        audit = result['constitutional_audit']
        self.assertEqual(audit['verdict'], 'QUARANTINE', audit)
        self.assertIsInstance(audit.get('concerns'), list)
        self.assertTrue(audit['concerns'], audit)
        if reason_fragment:
            joined = ' '.join(map(str, audit['concerns'])).upper()
            self.assertIn(reason_fragment.upper(), joined)

    def test_template_fallback_is_quarantined_not_approved(self):
        result = ph._swarm_fallback('objective', 'revenue', self.depts)
        self.assert_quarantined(result, 'UNVERIFIED')
        self.assertEqual(result['projection']['tier'], 'T2')
        self.assertIn('UNVERIFIED', result['projection']['governed_note'].upper())

    def test_malformed_json_is_quarantined(self):
        result = ph._parse_swarm_response('not-json', 'objective', 'analysis', self.depts)
        self.assert_quarantined(result, 'MALFORMED')

    def test_missing_audit_is_quarantined(self):
        payload = json.dumps({
            'departments': [],
            'projection': {'first_year_arr_usd': 1, 'tier': 'T2'},
        })
        result = ph._parse_swarm_response(payload, 'objective', 'analysis', self.depts)
        self.assert_quarantined(result, 'MISSING')

    def test_unknown_audit_verdict_is_quarantined(self):
        payload = json.dumps({
            'departments': [],
            'constitutional_audit': {'verdict': 'MAYBE', 'concerns': []},
            'projection': {'first_year_arr_usd': 1, 'tier': 'T2'},
        })
        result = ph._parse_swarm_response(payload, 'objective', 'analysis', self.depts)
        self.assert_quarantined(result, 'UNKNOWN')

    def test_model_cannot_self_promote_projection_to_t0_or_t1(self):
        payload = json.dumps({
            'departments': [],
            'constitutional_audit': {'verdict': 'APPROVED', 'concerns': []},
            'projection': {
                'first_year_arr_usd': 1,
                'tier': 'T0',
                'governed_note': 'model says proven',
            },
        })
        result = ph._parse_swarm_response(payload, 'objective', 'analysis', self.depts)
        self.assertEqual(result['projection']['tier'], 'T2')
        self.assertNotEqual(result['projection']['governed_note'], 'model says proven')
        self.assertIn('MODEL', result['projection']['governed_note'].upper())

    def test_provider_refusal_is_quarantined(self):
        class Messages:
            def create(self, **kwargs):
                return types.SimpleNamespace(stop_reason='refusal', content=[])

        fake_client = types.SimpleNamespace(messages=Messages())
        fake_module = types.SimpleNamespace(
            get_client=lambda: fake_client,
            make_cached_system=lambda value: value,
        )
        saved = sys.modules.get('anth_client')
        sys.modules['anth_client'] = fake_module
        try:
            result = ph.swarm_collaborate_live(
                'objective', 'analysis', self.depts, memory_context=''
            )
        finally:
            if saved is None:
                sys.modules.pop('anth_client', None)
            else:
                sys.modules['anth_client'] = saved
        self.assert_quarantined(result, 'REFUSAL')

    def test_provider_exception_is_quarantined(self):
        class Messages:
            def create(self, **kwargs):
                raise RuntimeError('provider down')

        fake_client = types.SimpleNamespace(messages=Messages())
        fake_module = types.SimpleNamespace(
            get_client=lambda: fake_client,
            make_cached_system=lambda value: value,
        )
        saved = sys.modules.get('anth_client')
        sys.modules['anth_client'] = fake_module
        try:
            result = ph.swarm_collaborate_live(
                'objective', 'analysis', self.depts, memory_context=''
            )
        finally:
            if saved is None:
                sys.modules.pop('anth_client', None)
            else:
                sys.modules['anth_client'] = saved
        self.assert_quarantined(result, 'PROVIDER')

    def test_persisted_model_memory_is_non_authoritative_context_not_t1_evidence(self):
        rows = [{
            'artifacts': [{'role': 'Research', 'output': 'prior model output'}],
            'projection': {'first_year_arr_usd': 123},
            'constitutional_verdict': 'APPROVED',
            'created_at': '2026-08-24T00:00:00Z',
        }]
        saved_urlopen = urllib.request.urlopen
        urllib.request.urlopen = lambda req, timeout=5: FakeResponse(rows)
        try:
            with patched_env(
                SUPABASE_URL='https://example.supabase.co',
                SUPABASE_SERVICE_ROLE_KEY='test-key',
            ):
                context = ph.retrieve_swarm_memory('objective', 'analysis')
        finally:
            urllib.request.urlopen = saved_urlopen

        self.assertNotIn('T1 evidence', context)
        self.assertIn('MODEL MEMORY', context.upper())
        self.assertIn('NON-AUTHORITATIVE', context.upper())

    def test_query_agent_tools_reads_agent_api_profiles_not_grace_chain(self):
        rows = [{
            'api_name': 'search',
            'endpoint_url': 'https://example.invalid/search',
            'capabilities': ['read'],
            'tier_required': 'operator',
        }]
        captured_urls: list[str] = []
        saved_urlopen = urllib.request.urlopen

        def fake_urlopen(req, timeout=5):
            captured_urls.append(req.full_url)
            return FakeResponse(rows)

        urllib.request.urlopen = fake_urlopen
        try:
            with patched_env(
                SUPABASE_URL='https://example.supabase.co',
                SUPABASE_SERVICE_ROLE_KEY='test-key',
            ):
                result = ph.query_agent_tools('operator')
        finally:
            urllib.request.urlopen = saved_urlopen

        self.assertEqual(result, rows)
        self.assertEqual(len(captured_urls), 1, captured_urls)
        self.assertIn('/rest/v1/agent_api_profiles', captured_urls[0])
        self.assertNotIn('grace_chain_summary', captured_urls[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
