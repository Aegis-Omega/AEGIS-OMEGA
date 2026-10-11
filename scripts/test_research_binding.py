"""The same valid captured bytes must not move between unrelated tasks/repos/IDs."""
import unittest
from research_benchmark import make_packet, TRUST, TEST_NOW
from research_intelligence import evaluate
from research_attestation import sign_capture, verify_capture, AttestationError
from research_collector import acquire, CaptureDenied, packet_source
from test_research_collector import FakeConnection

class ReplayAcrossAuthorityBoundary(unittest.TestCase):
    def ready(self, obj):
        return evaluate(obj, trusted_keys=TRUST, verified_now=TEST_NOW)['proposals'][0]['status']
    def test_legacy_v1_scheme_denied(self):
        obj=make_packet('valid_openai_langchain',0)
        receipt=obj['sources'][0]['capture_receipt']
        receipt['attestation']['scheme']='aegis.capture.hmac-sha256.v1'
        self.assertNotEqual(self.ready(obj),'READY_FOR_INDEPENDENT_TEST')

    def test_old_unbound_signer_api_refused(self):
        obj=make_packet('valid_openai_langchain',0)
        snap={k:v for k,v in obj['sources'][0]['capture_receipt'].items() if k!='attestation'}
        with self.assertRaisesRegex(AttestationError,'CAPTURE_BINDING_REQUIRED'):
            sign_capture(snap, TRUST['synthetic.test'], 'synthetic.test')

    def test_tampered_signed_context_denied(self):
        obj=make_packet('valid_openai_langchain',0)
        obj['sources'][0]['capture_receipt']['attestation']['binding']['task_id']='forged'
        self.assertNotEqual(self.ready(obj),'READY_FOR_INDEPENDENT_TEST')

    def test_invalid_binding_denied_before_any_dns(self):
        called=[]
        def resolver(*args, **kwargs):
            called.append(args)
            raise AssertionError('DNS happened before binding validation')
        with self.assertRaisesRegex(AttestationError,'CAPTURE_BINDING_REQUIRED'):
            acquire('https://docs.example.org/test', ('docs.example.org',),
                    resolver=resolver, connection_factory=FakeConnection,
                    signing_key=TRUST['synthetic.test'], signing_key_id='synthetic.test')
        self.assertEqual(called, [])

    def test_packet_source_rejects_other_bound_source_id(self):
        obj=make_packet('valid_openai_langchain',0)
        with self.assertRaisesRegex(CaptureDenied,'SOURCE_ID_BINDING_MISMATCH'):
            packet_source(obj['sources'][0]['capture_receipt'],'other_source')

    def test_verifier_requires_supplied_expected_context(self):
        obj=make_packet('valid_openai_langchain',0)
        receipt=obj['sources'][0]['capture_receipt']
        self.assertFalse(verify_capture(receipt,TRUST))
        self.assertTrue(verify_capture(receipt,TRUST, expected_binding={
            'task_id':obj['task_id'], 'repo_head':obj['repo_head'],'source_id':'one'}))

    def test_rebinding_task_fails(self):
        obj=make_packet('valid_openai_langchain',0)
        obj['task_id']='DIFFERENT_TASK'
        self.assertNotEqual(self.ready(obj),'READY_FOR_INDEPENDENT_TEST')
    def test_rebinding_repo_head_fails(self):
        obj=make_packet('valid_openai_langchain',0)
        obj['repo_head']='c'*40
        self.assertNotEqual(self.ready(obj),'READY_FOR_INDEPENDENT_TEST')
    def test_rebinding_source_id_fails(self):
        obj=make_packet('valid_openai_langchain',0)
        obj['sources'][0]['id']='different'
        obj['proposals'][0]['source_ids'][0]='different'
        self.assertNotEqual(self.ready(obj),'READY_FOR_INDEPENDENT_TEST')
