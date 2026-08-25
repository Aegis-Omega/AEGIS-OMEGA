import pathlib
import sys
import unittest
from dataclasses import replace

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_ingest as ingest


class FailingTransport:
    def __call__(self, url: str, timeout: float) -> bytes:
        raise TimeoutError("network unavailable")


class StaticTransport:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __call__(self, url: str, timeout: float) -> bytes:
        return self.payload


class CrossDomainIngestTests(unittest.TestCase):
    def test_live_failure_yields_not_established_and_no_snapshot(self):
        outcome = ingest.fetch_json_snapshot(
            registry_id="ncbi-gene",
            registry_version_or_release="observed-live",
            query_key="65010",
            query_key_type="integer-id",
            result_kind="gene-record",
            url="https://example.invalid/65010",
            source_observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
            transport=FailingTransport(),
        )
        self.assertEqual(outcome.status, "NOT_ESTABLISHED")
        self.assertIsNone(outcome.snapshot)

    def test_valid_json_constructs_snapshot(self):
        outcome = ingest.fetch_json_snapshot(
            registry_id="ncbi-gene",
            registry_version_or_release="observed-live",
            query_key="65010",
            query_key_type="integer-id",
            result_kind="gene-record",
            url="https://example.test/65010",
            source_observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
            transport=StaticTransport(b'{"gene_id":65010,"symbol":"SLC26A6"}'),
        )
        self.assertEqual(outcome.status, "ESTABLISHED")
        self.assertIsNotNone(outcome.snapshot)
        self.assertEqual(outcome.snapshot.canonical_result["gene_id"], 65010)

    def test_semantic_live_response_change_changes_snapshot_digest(self):
        common = dict(
            registry_id="ncbi-gene",
            registry_version_or_release="observed-live",
            query_key="65010",
            query_key_type="integer-id",
            result_kind="gene-record",
            url="https://example.test/65010",
            source_observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
        )
        a = ingest.fetch_json_snapshot(
            transport=StaticTransport(b'{"gene_id":65010,"symbol":"SLC26A6"}'),
            **common,
        )
        b = ingest.fetch_json_snapshot(
            transport=StaticTransport(b'{"gene_id":65010,"symbol":"CHANGED"}'),
            **common,
        )
        self.assertNotEqual(a.snapshot.content_sha256, b.snapshot.content_sha256)

    def test_malformed_json_is_not_established_not_negative(self):
        outcome = ingest.fetch_json_snapshot(
            registry_id="unicode",
            registry_version_or_release="observed-live",
            query_key="U+FDF2",
            query_key_type="unicode-codepoint",
            result_kind="assigned-codepoint-record",
            url="https://example.test/FDF2",
            source_observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
            transport=StaticTransport(b'not-json'),
        )
        self.assertEqual(outcome.status, "NOT_ESTABLISHED")
        self.assertIsNone(outcome.snapshot)


class SourceCaptureReceiptTests(unittest.TestCase):
    def test_raw_byte_tampering_breaks_capture_replay(self):
        bundle = ingest.capture_source_bytes(
            source_id="unicode-ucd",
            source_contract_sha256="a" * 64,
            request_identity="unicode://17.0.0/DerivedGeneralCategory.txt",
            request_subject_sha256s=(),
            source_version_or_release="17.0.0",
            response_status=200,
            media_type="text/plain",
            raw_content=b"0041 ; Lu\n0378 ; Cn\n",
            observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
            attempt_index=0,
        )
        ingest.verify_source_capture(bundle)
        with self.assertRaises(ValueError):
            ingest.verify_source_capture(replace(bundle, raw_content=b"tampered"))

    def test_retry_requires_previous_attempt_digest(self):
        first = ingest.capture_source_bytes(
            source_id="ncbi-gene-esearch",
            source_contract_sha256="b" * 64,
            request_identity="batch:1",
            request_subject_sha256s=("c" * 64,),
            source_version_or_release="observed-2026-08-25",
            response_status=503,
            media_type="application/json",
            raw_content=b"{}",
            observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
            attempt_index=0,
        )
        second = ingest.capture_source_bytes(
            source_id="ncbi-gene-esearch",
            source_contract_sha256="b" * 64,
            request_identity="batch:1",
            request_subject_sha256s=("c" * 64,),
            source_version_or_release="observed-2026-08-25",
            response_status=200,
            media_type="application/json",
            raw_content=b"{}",
            observed_at="2026-08-25T00:01:00Z",
            producer_id="test",
            attempt_index=1,
            previous_attempt_sha256=first.receipt.receipt_sha256,
        )
        ingest.verify_source_capture(second)
        with self.assertRaises(ValueError):
            ingest.capture_source_bytes(
                source_id="ncbi-gene-esearch",
                source_contract_sha256="b" * 64,
                request_identity="batch:1",
                request_subject_sha256s=("c" * 64,),
                source_version_or_release="observed-2026-08-25",
                response_status=200,
                media_type="application/json",
                raw_content=b"{}",
                observed_at="2026-08-25T00:01:00Z",
                producer_id="test",
                attempt_index=1,
                previous_attempt_sha256=None,
            )


if __name__ == "__main__":
    unittest.main()
