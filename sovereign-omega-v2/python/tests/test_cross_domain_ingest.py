import pathlib
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
