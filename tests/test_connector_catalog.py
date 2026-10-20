"""Regression checks for local connector snapshots in the existing source catalog."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("source_catalog", ROOT / "scripts/source_catalog.py")
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


class ConnectorCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.db, self.manifest, self.connectors = root / "sources.sqlite", root / "sources.json", root / "connectors.json"
        source = {"repository": "example/public", "revision": "a" * 40, "ref": "main",
                  "visibility": "public", "truncated": False,
                  "assets": [{"path": "src/example.py", "blob_sha": "b" * 40}]}
        self.manifest.write_text(json.dumps({"schema_version": 1, "observed_at": "2026-10-20",
                                             "sources": [source]}))
        self.assertEqual(catalog.build(self.manifest, self.db), 1)

    def record(self, **changes):
        item = {"provider": "github", "resource_kind": "pull_request",
                "source_ref": "sha256:" + "c" * 64, "visibility": "public",
                "status": "CONNECTED_AND_VERIFIED", "source_revision": "a" * 40}
        item.update(changes)
        return item

    def write(self, records, at="2026-10-20T02:00:00Z"):
        self.connectors.write_text(json.dumps({"schema_version": 1, "observed_at": at, "connectors": records}))

    def test_join_existing_catalog_no_source_mutation(self):
        self.write([self.record()])
        before = catalog.search(self.db, "example.py")
        self.assertEqual(catalog.ingest_connectors(self.db, self.connectors), 1)
        self.assertEqual(before, catalog.search(self.db, "example.py"))
        self.assertEqual(catalog.search_connectors(self.db, now="2026-10-20T02:01:00Z")[0]["effective_status"],
                         "CONNECTED_AND_VERIFIED")
        self.assertEqual(catalog.search_connectors(self.db, now="2026-10-21T02:01:00Z")[0]["effective_status"],
                         "STALE")
        self.assertEqual(catalog.search_connectors(self.db, provider="supabase"), [])

    def test_denial_supersedes_old_available_observation(self):
        self.write([self.record()])
        catalog.ingest_connectors(self.db, self.connectors)
        self.write([self.record(status="DENIED")])
        catalog.ingest_connectors(self.db, self.connectors)
        results = catalog.search_connectors(self.db, now="2026-10-20T02:01:00Z")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["effective_status"], "DENIED")

    def test_raw_links_and_private_without_consent_fail_closed(self):
        self.write([self.record()])
        catalog.ingest_connectors(self.db, self.connectors)
        for change in (
            {"source_ref": "https://docs.google.com/document/d/private"},
            {"source_ref": "sk-secret"},
            {"provider": "../bad"},
            {"resource_kind": "../../secret"},
            {"source_revision": "main"},
            {"status": "RUNNING"},
            {"visibility": "private"},
            {"source_ref": None},
        ):
            with self.subTest(change=change):
                self.write([self.record(**change)])
                with self.assertRaises(ValueError):
                    catalog.ingest_connectors(self.db, self.connectors)
                self.assertEqual(len(catalog.search_connectors(self.db)), 1)
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM connector_observations").fetchone()[0], 1)

    def test_duplicates_do_not_partially_overwrite(self):
        self.write([self.record()])
        catalog.ingest_connectors(self.db, self.connectors)
        self.write([self.record(status="DENIED"), self.record(status="STALE")])
        with self.assertRaises(ValueError):
            catalog.ingest_connectors(self.db, self.connectors)
        self.assertEqual(catalog.search_connectors(self.db)[0]["status"], "CONNECTED_AND_VERIFIED")

    def test_private_opt_in_and_denied_with_no_resource_id(self):
        self.write([self.record(status="DENIED", source_ref=None, source_revision=None, visibility="private")])
        with self.assertRaises(ValueError):
            catalog.ingest_connectors(self.db, self.connectors)
        self.assertEqual(catalog.ingest_connectors(self.db, self.connectors, allow_private_local=True), 1)
        self.assertEqual(catalog.search_connectors(self.db)[0]["source_ref"], "")

    def test_older_allow_cannot_replace_newer_denial(self):
        self.write([self.record(status="DENIED")], at="2026-10-20T08:00:00Z")
        catalog.ingest_connectors(self.db, self.connectors)
        self.write([self.record(status="CONNECTED_AND_VERIFIED")], at="2026-10-19T08:00:00Z")
        with self.assertRaisesRegex(ValueError, "Older connector snapshot"):
            catalog.ingest_connectors(self.db, self.connectors)
        record = catalog.search_connectors(self.db, now="2026-10-20T08:01:00Z")[0]
        self.assertEqual(record["status"], "DENIED")
        self.assertEqual(record["effective_status"], "DENIED")

    def test_same_timestamp_conflict_rejected_but_idempotent_replay_allowed(self):
        self.write([self.record(status="DENIED")])
        self.assertEqual(catalog.ingest_connectors(self.db, self.connectors), 1)
        self.assertEqual(catalog.ingest_connectors(self.db, self.connectors), 1)
        self.write([self.record(status="CONNECTED_AND_VERIFIED")])
        with self.assertRaisesRegex(ValueError, "Conflicting evidence"):
            catalog.ingest_connectors(self.db, self.connectors)
        self.assertEqual(catalog.search_connectors(self.db)[0]["status"], "DENIED")

    def test_mixed_out_of_order_snapshot_is_atomic(self):
        old = self.record(status="DENIED")
        self.write([old], at="2026-10-20T08:00:00Z")
        catalog.ingest_connectors(self.db, self.connectors)
        new_resource = self.record(provider="supabase", source_ref="sha256:" + "d" * 64)
        self.write([new_resource, self.record(status="CONNECTED_AND_VERIFIED")], at="2026-10-19T08:00:00Z")
        with self.assertRaisesRegex(ValueError, "Older connector snapshot"):
            catalog.ingest_connectors(self.db, self.connectors)
        self.assertEqual(catalog.search_connectors(self.db, provider="supabase"), [])
        self.assertEqual(catalog.search_connectors(self.db, provider="github")[0]["status"], "DENIED")

    def test_two_cloudflare_accounts_do_not_share_state(self):
        # Distinct opaque account handles are not public native Cloudflare IDs.
        first = self.record(provider="cloudflare", resource_kind="account",
                            source_ref="sha256:" + "e" * 64, source_revision=None,
                            visibility="private", status="CONNECTED_AND_VERIFIED")
        second = self.record(provider="cloudflare", resource_kind="account",
                             source_ref="sha256:" + "f" * 64, source_revision=None,
                             visibility="private", status="AVAILABLE_UNTESTED")
        self.write([first, second], at="2026-10-20T02:00:00Z")
        self.assertEqual(catalog.ingest_connectors(self.db, self.connectors,
                                                    allow_private_local=True), 2)
        states = {r["source_ref"]: r["status"] for r in catalog.search_connectors(
            self.db, provider="cloudflare", now="2026-10-20T02:01:00Z")}
        self.assertEqual(states[first["source_ref"]], "CONNECTED_AND_VERIFIED")
        self.assertEqual(states[second["source_ref"]], "AVAILABLE_UNTESTED")
        self.write([self.record(**dict(first, status="DENIED"))],
                   at="2026-10-20T02:02:00Z")
        self.assertEqual(catalog.ingest_connectors(self.db, self.connectors,
                                                    allow_private_local=True), 1)
        after = {r["source_ref"]: r["status"] for r in catalog.search_connectors(
            self.db, provider="cloudflare", now="2026-10-20T02:03:00Z")}
        self.assertEqual(after[first["source_ref"]], "DENIED")
        self.assertEqual(after[second["source_ref"]], "AVAILABLE_UNTESTED")

    def test_read_only_search_does_not_create_missing_database(self):
        missing = Path(self.tmp.name) / "missing.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            catalog.search_connectors(missing)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
