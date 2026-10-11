"""Existing Automaton-3 is the sole challenge-issuer authority, not the agent.

Mock-positive cases verify the adapter contract only; they do not manufacture a
real signed/operator-approved authority envelope or any production entitlement.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import research_challenge as ch
from research_admission import AdmissionDenied
from research_benchmark import TEST_NOW


class CentralIssuerAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.ledger = str(Path(self.folder.name) / 'issued.sqlite3')
        self.kwargs = {'ledger_path': self.ledger, 'task_id': 'task_123',
                       'repo_head': 'a' * 40, 'source_ids': ['two', 'one'],
                       'ttl_seconds': 60, 'verified_now': TEST_NOW}

    def test_01_absent_central_authority_denies_without_ledger_write(self):
        with patch.dict(sys.modules, {'harness': None}):
            with self.assertRaisesRegex(AdmissionDenied, 'CENTRAL_AUTHORITY_DENIED'):
                ch.issue_challenge(**self.kwargs)
        self.assertFalse(Path(self.ledger).exists())

    def test_02_explicit_denial_is_not_overridden(self):
        with patch.object(ch, '_central_authority_decision',
                          return_value={'outcome': 'DENIED', 'decision_root': '0'*64}):
            with self.assertRaisesRegex(AdmissionDenied, 'CENTRAL_AUTHORITY_DENIED'):
                ch.issue_challenge(**self.kwargs)
        self.assertFalse(Path(self.ledger).exists())

    def test_03_self_declared_boolean_and_missing_decision_root_denied(self):
        for invalid in [True, 'ADMITTED', None, {},
                        {'outcome': 'ADMITTED'},
                        {'outcome': 'ADMITTED', 'decision_root': 'not-a-root'},
                        {'outcome': 'ADMITTED', 'decision_root': True},
                        {'outcome': 'accepted', 'decision_root': 'a'*64}]:
            with self.subTest(value=invalid), patch.object(
                ch, '_central_authority_decision', return_value=invalid):
                with self.assertRaisesRegex(AdmissionDenied, 'CENTRAL_AUTHORITY_DENIED'):
                    ch.issue_challenge(**self.kwargs)
        self.assertFalse(Path(self.ledger).exists())

    def test_04_denial_before_nonce_generation_or_any_disk_mutation(self):
        with patch.object(ch, '_central_authority_decision',
                          return_value={'outcome': 'DENIED'}), patch.object(
                            ch.secrets, 'token_hex', side_effect=AssertionError('nonce generated')) as gen:
            with self.assertRaisesRegex(AdmissionDenied, 'CENTRAL_AUTHORITY_DENIED'):
                ch.issue_challenge(**self.kwargs)
            gen.assert_not_called()
        self.assertFalse(Path(self.ledger).exists())

    def test_05_exact_scope_passed_to_automaton_three_adapter(self):
        approved = {'outcome': 'ADMITTED', 'decision_root': 'c'*64}
        with patch.object(ch, '_central_authority_decision', return_value=approved) as gate:
            receipt = ch.issue_challenge(**self.kwargs)
        self.assertEqual(receipt['schema'], 'aegis.research.challenge.v1')
        gate.assert_called_once_with(ledger_path=self.ledger,
            task_id='task_123', repo_head='a'*40, source_ids=('one', 'two'), ttl_seconds=60)
        self.assertTrue(Path(self.ledger).exists())

    def test_06_real_adapter_uses_D2_explicit_approval_not_D0_readonly(self):
        observed = {}
        def fake_sdk(**kw):
            observed.update(kw)
            return {'outcome': 'ADMITTED', 'decision_root': 'd'*64}
        from types import ModuleType
        harness = ModuleType('harness')
        sdk = ModuleType('harness.sdk')
        client = ModuleType('harness.sdk.authority_client')
        client.authorize_from_environment = fake_sdk
        with patch.dict(sys.modules, {'harness': harness, 'harness.sdk': sdk,
                                      'harness.sdk.authority_client': client}):
            r = ch._central_authority_decision(ledger_path=self.ledger,
                task_id='task_123', repo_head='a'*40,
                source_ids=('one','two'), ttl_seconds=60)
        self.assertEqual(r['outcome'],'ADMITTED')
        self.assertEqual(observed['action_class'],'D2')
        self.assertEqual(observed['requested_capability'],'research.challenge.issue')
        self.assertEqual(observed['authority_domain'],'research:challenge:issue')
        self.assertEqual(observed['tool'],'scripts.research_challenge:issue_challenge')
        action = observed['action']
        self.assertEqual(action['task_id'], 'task_123')
        self.assertEqual(action['repo_head'], 'a'*40)
        self.assertEqual(action['source_ids'], ['one', 'two'])
        self.assertEqual(action['ttl_seconds'], 60)
        self.assertEqual(action['ledger_path_sha256'],
                         hashlib.sha256(self.ledger.encode('utf-8')).hexdigest())

    def test_07_target_ledger_change_cannot_reuse_same_action_digest(self):
        first = ch._central_authority_decision
        logs = []
        def stub(**kw):
            logs.append(kw)
            return {'outcome':'ADMITTED','decision_root':'e'*64}
        from types import ModuleType
        harness, sdk, client = (ModuleType(n) for n in
            ['harness', 'harness.sdk', 'harness.sdk.authority_client'])
        client.authorize_from_environment=stub
        with patch.dict(sys.modules, {'harness':harness,'harness.sdk':sdk,
                                      'harness.sdk.authority_client':client}):
            first(ledger_path=self.ledger,task_id='task_123',repo_head='a'*40,
                  source_ids=('one','two'),ttl_seconds=60)
            first(ledger_path=self.ledger+'-other',task_id='task_123',repo_head='a'*40,
                  source_ids=('one','two'),ttl_seconds=60)
        self.assertNotEqual(logs[0]['action']['ledger_path_sha256'],
                            logs[1]['action']['ledger_path_sha256'])

    def test_08_import_error_never_falls_back_to_unapproved_issue(self):
        with patch.dict(sys.modules, {'harness': None}):
            result=ch._central_authority_decision(ledger_path=self.ledger,
                task_id='task_123',repo_head='a'*40,source_ids=('one','two'),ttl_seconds=60)
        self.assertEqual(result['outcome'],'DENIED')
        self.assertIn('AUTHORITY_UNAVAILABLE',result['denial_codes'])

if __name__ == '__main__':
    unittest.main()
