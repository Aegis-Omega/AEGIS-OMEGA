#!/usr/bin/env python3
"""Regression tests for fail-closed model-response admission."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import platform_helpers as helpers


class EpistemicFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.departments = [
            {'id': 'EPI-01', 'role': 'Epistemics', 'category': 'cognitive'},
        ]
        self.environment = patch.dict(
            os.environ,
            {
                'SUPABASE_URL': 'https://example.supabase.co',
                'SUPABASE_SERVICE_ROLE_KEY': 'service-key',
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @patch('urllib.request.urlopen')
    def test_malformed_model_json_is_quarantined_and_cannot_award_grace(
        self,
        mock_urlopen,
    ) -> None:
        result = helpers._parse_swarm_response(
            'not valid json',
            'inspect repository event',
            'technical',
            self.departments,
        )

        self.assertEqual(result['constitutional_audit']['verdict'], 'QUARANTINE')
        helpers.award_graces_for_cycle(
            'cycle-malformed',
            result['artifacts'],
            result['constitutional_audit']['verdict'],
        )
        mock_urlopen.assert_not_called()

    @patch('urllib.request.urlopen')
    def test_unknown_model_verdict_is_quarantined_and_cannot_award_grace(
        self,
        mock_urlopen,
    ) -> None:
        response = json.dumps(
            {
                'departments': [
                    {'id': 'EPI-01', 'output': 'candidate analysis only'},
                ],
                'constitutional_audit': {
                    'verdict': 'MODEL_SAYS_YES',
                    'concerns': [],
                },
                'projection': {
                    'first_year_arr_usd': 0,
                    'tier': 'T2',
                    'governed_note': 'candidate',
                },
            }
        )

        result = helpers._parse_swarm_response(
            response,
            'inspect repository event',
            'technical',
            self.departments,
        )

        self.assertEqual(result['constitutional_audit']['verdict'], 'QUARANTINE')
        helpers.award_graces_for_cycle(
            'cycle-unknown',
            result['artifacts'],
            result['constitutional_audit']['verdict'],
        )
        mock_urlopen.assert_not_called()

    @patch('urllib.request.urlopen')
    def test_allowed_model_approval_is_candidate_only_and_cannot_award_grace(
        self,
        mock_urlopen,
    ) -> None:
        response = json.dumps(
            {
                'departments': [
                    {'id': 'EPI-01', 'output': 'plausible generated analysis'},
                ],
                'constitutional_audit': {
                    'verdict': 'APPROVED',
                    'concerns': [],
                },
                'projection': {
                    'first_year_arr_usd': 0,
                    'tier': 'T2',
                    'governed_note': 'candidate',
                },
            }
        )

        result = helpers._parse_swarm_response(
            response,
            'inspect repository event',
            'technical',
            self.departments,
        )

        audit = result['constitutional_audit']
        self.assertEqual(audit['candidate_verdict'], 'APPROVED')
        self.assertEqual(audit['verdict'], 'QUARANTINE')
        helpers.award_graces_for_cycle('cycle-model-approved', result['artifacts'], audit['verdict'])
        mock_urlopen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
