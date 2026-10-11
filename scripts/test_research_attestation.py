"""Adversarial local key-bound collector admission; NOT an external web test."""
import copy
import datetime as dt
import os
import stat
import tempfile
import unittest
from pathlib import Path

from research_attestation import (sign_capture, verify_capture, read_protected_key,
                                  AttestationError, SNAPSHOT_FIELDS)
from research_intelligence import evaluate, ResearchError
from research_collector import acquire, packet_source
from research_benchmark import make_packet, TEST_KEY, TRUST, TEST_NOW
from test_research_collector import FakeConnection, res


class CaptureTrustTests(unittest.TestCase):
    def packet(self):
        return make_packet('valid_openai_langchain', 0)

    def evaluate(self, p, *, trust=TRUST, clock=TEST_NOW):
        return evaluate(p, trusted_keys=trust, verified_now=clock)

    def test_01_no_key_never_ready(self):
        self.assertEqual(evaluate(self.packet())['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_02_correct_external_key_ready_only_for_test(self):
        out = self.evaluate(self.packet())
        self.assertEqual(out['proposals'][0]['status'], 'READY_FOR_INDEPENDENT_TEST')
        self.assertEqual(out['external_claim_verification'], 'NOT_PERFORMED')
        self.assertEqual(out['benchmark_superiority'], 'NOT_ESTABLISHED')
        self.assertEqual(out['collector_attestation'], 'LOCAL_HMAC_VERIFIED_FOR_QUORUM')

    def test_03_fake_capture_flag_without_mac_denied(self):
        p = self.packet()
        for s in p['sources']: s.pop('capture_receipt')
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_04_wrong_key_not_admitted(self):
        out = self.evaluate(self.packet(), trust={'synthetic.test': b'Z'*32})
        self.assertEqual(out['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_05_unknown_key_id_not_admitted(self):
        out = self.evaluate(self.packet(), trust={'other': TEST_KEY})
        self.assertEqual(out['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_06_rebound_source_hostname_denied(self):
        p = self.packet()
        p['sources'][0]['url'] = 'https://docs.anthropic.com/doc'
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_07_rebound_content_with_recomputed_sha_denied(self):
        import hashlib
        p=self.packet();s=p['sources'][0]
        s['content']='counterfeit excerpt';s['sha256']=hashlib.sha256(s['content'].encode()).hexdigest()
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_08_capture_time_changed_within_fresh_window_denied(self):
        p=self.packet();s=p['sources'][0];s['captured_at']='2026-10-11T11:00:00Z'
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_09_attestation_mac_bit_flip_denied(self):
        p=self.packet();a=p['sources'][0]['capture_receipt']['attestation']
        a['mac_sha256'] = ('a' if a['mac_sha256'][0]!='a' else 'b')+a['mac_sha256'][1:]
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_10_snapshot_field_mutation_denied(self):
        p=self.packet();p['sources'][0]['capture_receipt']['resolved_ip']='8.8.8.8'
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_11_attestation_unknown_field_denied(self):
        p=self.packet();p['sources'][0]['capture_receipt']['provider_verified']=True
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_12_source_data_is_never_verification_key(self):
        p=self.packet();p['verification_key']='some_key'
        with self.assertRaisesRegex(ResearchError,'INVALID_OBJECT_FIELDS'):
            self.evaluate(p)

    def test_13_untrusted_asof_backdate_rejected(self):
        p=self.packet();p['as_of_utc']='2026-08-01T12:00:00Z'
        with self.assertRaisesRegex(ResearchError,'UNTRUSTED_AS_OF_CLOCK'):
            self.evaluate(p)

    def test_14_future_asof_rejected(self):
        p=self.packet();p['as_of_utc']='2026-11-01T12:00:00Z'
        with self.assertRaisesRegex(ResearchError,'UNTRUSTED_AS_OF_CLOCK'):
            self.evaluate(p)

    def test_15_clock_drift_tolerance_bounded(self):
        p=self.packet()
        five=TEST_NOW+dt.timedelta(seconds=300)
        self.assertEqual(self.evaluate(p,clock=five)['proposals'][0]['status'],'READY_FOR_INDEPENDENT_TEST')
        beyond=TEST_NOW+dt.timedelta(seconds=301)
        with self.assertRaisesRegex(ResearchError,'UNTRUSTED_AS_OF_CLOCK'):
            self.evaluate(p,clock=beyond)

    def test_16_naive_clock_rejected(self):
        with self.assertRaisesRegex(ResearchError,'TRUSTED_CLOCK_REQUIRED'):
            self.evaluate(self.packet(),clock=dt.datetime(2026,10,11))

    def test_17_local_signer_binds_actual_collector_output(self):
        FakeConnection.response = __import__('test_research_collector').FakeReply()
        snap=acquire('https://docs.example.org/page',('docs.example.org',),
                     resolver=lambda *a,**k:res(),connection_factory=FakeConnection,
                     clock=lambda:TEST_NOW,signing_key=TEST_KEY,signing_key_id='synthetic.test')
        self.assertTrue(verify_capture(snap,TRUST))
        src=packet_source(snap,'ex')
        self.assertEqual(src['capture_receipt']['url'],src['url'])
        self.assertEqual(src['acquisition'],'connector_capture')

    def test_18_unsigned_collector_output_not_signed(self):
        FakeConnection.response = __import__('test_research_collector').FakeReply()
        snap=acquire('https://docs.example.org/page',('docs.example.org',),
                     resolver=lambda *a,**k:res(),connection_factory=FakeConnection,
                     clock=lambda:TEST_NOW)
        self.assertFalse(verify_capture(snap,TRUST))
        self.assertNotIn('capture_receipt',packet_source(snap,'ex'))

    def test_19_owner_only_file_required(self):
        with tempfile.TemporaryDirectory() as td:
            keypath=Path(td)/'local.key';keypath.write_bytes(TEST_KEY)
            keypath.chmod(0o644)
            with self.assertRaisesRegex(AttestationError,'INSECURE_TRUST_KEY_FILE'):
                read_protected_key(str(keypath))
            keypath.chmod(0o600)
            self.assertEqual(read_protected_key(str(keypath)),TEST_KEY)

    def test_20_key_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'secret';path.write_bytes(TEST_KEY);path.chmod(0o600)
            alias=Path(td)/'link';alias.symlink_to(path)
            with self.assertRaises((AttestationError, OSError)):
                read_protected_key(str(alias))

    def test_21_short_keys_refused(self):
        with self.assertRaisesRegex(AttestationError,'INVALID_TRUST_KEY'):
            sign_capture({k:None for k in SNAPSHOT_FIELDS},b'bad','synthetic.test')

    def test_22_invalid_id_refused(self):
        p=self.packet()['sources'][0]['capture_receipt']
        p={k:v for k,v in p.items() if k!='attestation'}
        with self.assertRaisesRegex(AttestationError,'INVALID_TRUST_KEY'):
            sign_capture(p,TEST_KEY,'../../invalid')

    def test_23_no_untrusted_boolean_bypass(self):
        p=self.packet();p['sources'][0]['capture_receipt']['attestation']={'scheme':'aegis.capture.hmac-sha256.v1',
            'key_id':'synthetic.test','mac_sha256':True}
        self.assertEqual(self.evaluate(p)['proposals'][0]['status'],'NEEDS_RESEARCH')

    def test_24_full_suite_model_conclusion_unchanged(self):
        p=self.packet();out=self.evaluate(p)
        self.assertEqual(out['tool_execution'],'NOT_EXECUTED')
        self.assertEqual(out['authority_effect'],'NONE')

if __name__=='__main__':unittest.main()
