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

    def test_read_only_search_does_not_create_missing_database(self):
        missing = Path(self.tmp.name) / "missing.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            catalog.search_connectors(missing)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
