"""A captured body needs an unambiguous HTTP/1.1 completion delimiter.

RFC 9112 6.3: early connection close cannot be distinguished from completion
for close-delimited response bodies. This collector is evidence-producing,
not a permissive browser, so ambiguous completion is denied.
"""
import unittest

from research_collector import CaptureDenied
from test_research_collector import FakeReply, capture


class CloseFramingTests(unittest.TestCase):
    def test_01_close_delimited_partial_body_must_not_be_evidence(self):
        with self.assertRaisesRegex(CaptureDenied, 'UNVERIFIABLE_BODY_COMPLETION'):
            capture(response=FakeReply(body=b'cut', headers={
                'Content-Type': 'text/plain', 'Connection': 'close'}))

    def test_02_close_delimited_full_looking_body_still_not_provable(self):
        with self.assertRaisesRegex(CaptureDenied, 'UNVERIFIABLE_BODY_COMPLETION'):
            capture(response=FakeReply(body=b'Complete-looking document', headers={
                'Content-Type': 'text/plain'}))

    def test_03_signed_capture_does_not_launder_unframed_response(self):
        # A cryptographic MAC proves what was signed, not that HTTP completed.
        with self.assertRaisesRegex(CaptureDenied, 'UNVERIFIABLE_BODY_COMPLETION'):
            capture(response=FakeReply(body=b'could be truncated', headers={
                'Content-Type': 'text/plain', 'Connection': 'close'}),
                signing_key=bytes(range(32)), signing_key_id='synthetic.test',
                capture_binding={'task_id': 'study', 'repo_head': 'a' * 40,
                                 'source_id': 'sample'})

    def test_04_provable_content_length_still_succeeds(self):
        result = capture(response=FakeReply(body=b'complete', headers={
            'Content-Type': 'text/plain', 'Content-Length': '8'}))
        self.assertEqual(result['excerpt'], 'complete')
        self.assertEqual(result['full_bytes'], 8)

if __name__ == '__main__':
    unittest.main()
