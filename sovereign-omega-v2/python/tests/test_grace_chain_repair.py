#!/usr/bin/env python3
"""Regression tests for grace-chain mutation ordering and fitness-read isolation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

import platform_helpers as helpers


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GraceChainRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifacts = [
            {'role': 'Strategy', 'output': 'first'},
            {'role': 'Empty', 'output': '   '},
            {'role': 'Finance', 'output': 'second'},
            {'role': 'Risk', 'output': 'third'},
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

    @staticmethod
    def _payloads(mock_urlopen: MagicMock) -> list[dict]:
        return [
            json.loads(call.args[0].data.decode('utf-8'))
            for call in mock_urlopen.call_args_list
        ]

    @patch('urllib.request.urlopen', return_value=_Response())
    def test_approved_cycle_emits_ordered_chain(self, mock_urlopen: MagicMock) -> None:
        helpers.award_graces_for_cycle('cycle-1', self.artifacts, 'APPROVED')
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(
            self._payloads(mock_urlopen),
            [
                {
                    'p_cycle_id': 'cycle-1',
                    'p_from_dept': None,
                    'p_to_dept': 'Strategy',
                    'p_graces': 1,
                    'p_viability_score': None,
                },
                {
                    'p_cycle_id': 'cycle-1',
                    'p_from_dept': 'Strategy',
                    'p_to_dept': 'Finance',
                    'p_graces': 1,
                    'p_viability_score': None,
                },
                {
                    'p_cycle_id': 'cycle-1',
                    'p_from_dept': 'Finance',
                    'p_to_dept': 'Risk',
                    'p_graces': 1,
                    'p_viability_score': None,
                },
            ],
        )
        for call in mock_urlopen.call_args_list:
            request = call.args[0]
            self.assertEqual(request.full_url, 'https://example.supabase.co/rest/v1/rpc/award_grace')
            self.assertEqual(request.method, 'POST')
            self.assertEqual(call.kwargs['timeout'], 3)

    @patch('urllib.request.urlopen', return_value=_Response())
    def test_flag_cycle_awards_but_quarantine_and_unknown_deny(self, mock_urlopen: MagicMock) -> None:
        helpers.award_graces_for_cycle('cycle-flag', self.artifacts[:1], 'FLAG')
        self.assertEqual(mock_urlopen.call_count, 1)
        helpers.award_graces_for_cycle('cycle-q', self.artifacts, 'QUARANTINE')
        helpers.award_graces_for_cycle('cycle-x', self.artifacts, 'UNKNOWN')
        self.assertEqual(mock_urlopen.call_count, 1)

    @patch('urllib.request.urlopen', return_value=_Response())
    def test_empty_artifacts_and_missing_configuration_emit_nothing(self, mock_urlopen: MagicMock) -> None:
        helpers.award_graces_for_cycle('cycle-empty', [], 'APPROVED')
        helpers.award_graces_for_cycle('cycle-blank', [{'role': 'A', 'output': ''}], 'APPROVED')
        with patch.dict(os.environ, {'SUPABASE_URL': '', 'SUPABASE_SERVICE_ROLE_KEY': ''}, clear=False):
            helpers.award_graces_for_cycle('cycle-no-config', self.artifacts, 'APPROVED')
        self.assertEqual(mock_urlopen.call_count, 0)

    @patch('urllib.request.urlopen', side_effect=RuntimeError('network unavailable'))
    def test_rpc_failures_are_bounded_per_department(self, mock_urlopen: MagicMock) -> None:
        helpers.award_graces_for_cycle('cycle-fail', self.artifacts, 'APPROVED')
        self.assertEqual(mock_urlopen.call_count, 3)
        self.assertEqual(
            [payload['p_to_dept'] for payload in self._payloads(mock_urlopen)],
            ['Strategy', 'Finance', 'Risk'],
        )

    def test_fitness_trend_is_read_only_wrapper(self) -> None:
        expected = {'homeostasis_zone': 'optimal', 'window_size': 7}
        with patch.object(helpers, '_fetch_dept_fitness_stats', return_value=expected) as fetch:
            self.assertEqual(helpers.query_fitness_trend(7), expected)
            fetch.assert_called_once_with(7)


if __name__ == '__main__':
    unittest.main()
