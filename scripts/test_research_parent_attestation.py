"""Signed collector bytes must be MAC-verified by the *publishing parent*."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import research_collector as rc
from research_attestation import sign_capture, verify_capture
from test_research_collector import capture

KEY = bytes(range(32))  # deterministic local fixture ONLY; never a production key
KEY_ID = 'synthetic.test'
BINDING = {'task_id': 'study_123', 'repo_head': 'a' * 40, 'source_id': 'sample'}


class PublishingParentAttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key_file = self.root / 'local.key'
        self.key_file.write_bytes(KEY)
        self.key_file.chmod(0o600)
        self.output = self.root / 'capture.json'
        self.snapshot = sign_capture(capture(), KEY, KEY_ID, binding=BINDING)
        self.args = [
            'https://docs.example.org/page', '--allow-host', 'docs.example.org',
            '--allow-network', '--signing-key-file', str(self.key_file),
            '--signing-key-id', KEY_ID, '--task-id', BINDING['task_id'],
            '--repo-head', BINDING['repo_head'], '--source-id', BINDING['source_id'],
            '--output', str(self.output),
        ]

    def run_worker_result(self, response):
        with patch.object(rc, '_run_bounded_worker', return_value=response):
            return rc.main(self.args)

    def assert_denied_no_output(self, response):
        with self.assertRaises(SystemExit) as rejected:
            self.run_worker_result(response)
        self.assertEqual(rejected.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_valid_signed_worker_accepted_only_after_parent_verification(self):
        self.assertEqual(self.run_worker_result(self.snapshot), 0)
        published = json.loads(self.output.read_text())
        self.assertTrue(verify_capture(published, {KEY_ID: KEY}, expected_binding=BINDING))
        self.assertEqual(published['excerpt'], 'Hello public page')

    def test_structurally_coherent_tampered_body_cannot_be_published(self):
        tampered = copy.deepcopy(self.snapshot)
        tampered['excerpt'] = 'Fakeo public page'  # same byte length
        digest = hashlib.sha256(tampered['excerpt'].encode()).hexdigest()
        tampered['excerpt_sha256'] = digest
        tampered['full_body_sha256'] = digest
        self.assert_denied_no_output(tampered)

    def test_forged_mac_cannot_be_published(self):
        forged = copy.deepcopy(self.snapshot)
        forged['attestation']['mac_sha256'] = '0' * 64
        self.assert_denied_no_output(forged)

    def test_signature_from_wrong_key_cannot_be_published(self):
        wrong = sign_capture(capture(), b'Z' * 32, KEY_ID, binding=BINDING)
        self.assert_denied_no_output(wrong)

    def test_signed_for_other_repository_head_cannot_be_published(self):
        bound_elsewhere = sign_capture(capture(), KEY, KEY_ID,
                                       binding={**BINDING, 'repo_head': 'b' * 40})
        self.assert_denied_no_output(bound_elsewhere)

    def test_tampering_tls_digest_without_new_mac_cannot_be_published(self):
        tampered = copy.deepcopy(self.snapshot)
        tampered['tls_peer_cert_sha256'] = 'a' * 64
        self.assert_denied_no_output(tampered)

    def test_insecure_signer_keyfile_denied_at_parent_before_publishing(self):
        self.key_file.chmod(0o644)
        self.assert_denied_no_output(self.snapshot)

    def test_key_rotation_between_capture_and_parent_verification_denied(self):
        def switch_secret(argv, *, deadline_seconds):
            self.key_file.write_bytes(b'Z' * 32)
            return self.snapshot
        with patch.object(rc, '_run_bounded_worker', side_effect=switch_secret):
            with self.assertRaises(SystemExit) as rejected:
                rc.main(self.args)
        self.assertEqual(rejected.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_signed_claim_in_unsigned_request_is_denied(self):
        plain_args = [
            'https://docs.example.org/page', '--allow-host', 'docs.example.org',
            '--allow-network', '--output', str(self.output),
        ]
        with patch.object(rc, '_run_bounded_worker', return_value=self.snapshot):
            with self.assertRaises(SystemExit) as denied:
                rc.main(plain_args)
        self.assertEqual(denied.exception.code, 2)
        self.assertFalse(self.output.exists())

    def test_valid_unsigned_capture_remains_explicitly_unattested(self):
        plain_args = [
            'https://docs.example.org/page', '--allow-host', 'docs.example.org',
            '--allow-network', '--output', str(self.output),
        ]
        with patch.object(rc, '_run_bounded_worker', return_value=capture()):
            self.assertEqual(rc.main(plain_args), 0)
        self.assertNotIn('attestation', json.loads(self.output.read_text()))


if __name__ == '__main__':
    unittest.main()
