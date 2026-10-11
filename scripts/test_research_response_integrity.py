"""Adversarial response-framing tests: no partial body may be signed."""
import unittest

from research_collector import CaptureDenied
from test_research_collector import capture, FakeReply


class HTTPFramingTests(unittest.TestCase):
    def test_short_body_disagreeing_with_content_length_denied(self):
        with self.assertRaisesRegex(CaptureDenied, 'INCOMPLETE_RESPONSE_BODY'):
            capture(response=FakeReply(body=b'short', headers={
                'Content-Type': 'text/plain', 'Content-Length': '99'}))

    def test_oversized_body_disagreeing_with_content_length_denied(self):
        with self.assertRaisesRegex(CaptureDenied, 'CONTENT_LENGTH_MISMATCH'):
            capture(response=FakeReply(body=b'LONG', headers={
                'Content-Type': 'text/plain', 'Content-Length': '2'}))

    def test_chunked_header_without_actual_decoding_denied(self):
        with self.assertRaisesRegex(CaptureDenied, 'TRANSFER_FRAMING_MISMATCH'):
            capture(response=FakeReply(body=b'Hello', headers={
                'Content-Type': 'text/plain', 'Transfer-Encoding': 'chunked'}))

    def test_unsupported_transfer_coding_denied(self):
        with self.assertRaisesRegex(CaptureDenied, 'UNSUPPORTED_TRANSFER_ENCODING'):
            capture(response=FakeReply(body=b'Hello', headers={
                'Content-Type': 'text/plain', 'Transfer-Encoding': 'gzip'}))

    def test_content_length_and_transfer_encoding_conflict_denied(self):
        with self.assertRaisesRegex(CaptureDenied, 'AMBIGUOUS_TRANSFER_FRAMING'):
            capture(response=FakeReply(body=b'Hello', headers={
                'Content-Type': 'text/plain', 'Content-Length': '5',
                'Transfer-Encoding': 'chunked'}))

    def test_matching_content_length_preserves_hashes(self):
        snap=capture(response=FakeReply(body=b'Hello', headers={
            'Content-Type': 'text/plain','Content-Length': '5'}))
        self.assertEqual(snap['full_bytes'], 5)

    def test_missing_content_length_connection_close_allowed(self):
        snap=capture(response=FakeReply(body=b'Hello', headers={
            'Content-Type': 'text/plain'}))
        self.assertEqual(snap['full_bytes'], 5)

    def test_duplicate_length_header_rejected(self):
        with self.assertRaisesRegex(CaptureDenied, 'RESPONSE_TOO_LARGE'):
            capture(response=FakeReply(body=b'Hello', headers={
                'Content-Type': 'text/plain','Content-Length': '5, 5'}))

if __name__=='__main__': unittest.main()
