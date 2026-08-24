#!/usr/bin/env python3
"""Regression tests for the commit-bound Integration Ledger generator."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import integration_ledger as ledger


FIXED_META = {
    "schema_version": "1.0.0",
    "repository": "Aegis-Omega/AEGIS-OMEGA",
    "commit_sha": "a" * 40,
    "tree_sha": "b" * 40,
    "source_timestamp": "2026-07-18T00:00:00Z",
    "generator": {
        "path": "scripts/integration_ledger.py",
        "version": "2.0.0",
        "sha256": "c" * 64,
    },
}


class IntegrationLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            ("WIRED", "alpha", "CI"),
            ("LINKED", "beta", "3 ext-ref"),
            ("DORMANT", "gamma", "1 ext-ref"),
            ("ORPHAN", "omega", "no external reference"),
        ]

    def test_json_is_byte_deterministic(self) -> None:
        first = ledger.render_json(ledger.build_document(self.rows, FIXED_META))
        second = ledger.render_json(ledger.build_document(self.rows, FIXED_META))
        self.assertEqual(first, second)
        parsed = json.loads(first)
        self.assertEqual(parsed["commit_sha"], "a" * 40)
        self.assertEqual(parsed["counts"], {
            "DORMANT": 1,
            "LINKED": 1,
            "ORPHAN": 1,
            "WIRED": 1,
        })

    def test_markdown_and_json_share_area_order(self) -> None:
        document = ledger.build_document(self.rows, FIXED_META)
        markdown = ledger.render_md(document)
        json_areas = [item["area"] for item in json.loads(ledger.render_json(document))["areas"]]
        markdown_positions = [markdown.index(f"`{area}`") for area in json_areas]
        self.assertEqual(markdown_positions, sorted(markdown_positions))
        self.assertIn("commit `" + "a" * 40 + "`", markdown)
        self.assertIn("tree `" + "b" * 40 + "`", markdown)

    def test_expected_sha_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "ledger commit mismatch"):
            ledger.validate_expected_sha("a" * 40, "d" * 40)

    def test_invalid_or_unsorted_document_is_rejected(self) -> None:
        document = ledger.build_document(list(reversed(self.rows)), FIXED_META)
        with self.assertRaisesRegex(ValueError, "deterministically ordered"):
            ledger.validate_document(document)

    def test_written_outputs_are_parseable_and_consistent(self) -> None:
        document = ledger.build_document(self.rows, FIXED_META)
        ledger.validate_document(document)
        with tempfile.TemporaryDirectory() as directory:
            markdown_path, json_path = ledger.write_outputs(document, Path(directory))
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertEqual(parsed["area_count"], 4)
            for item in parsed["areas"]:
                self.assertIn(f"| {item['status']} | `{item['area']}` | {item['evidence']} |", markdown)


if __name__ == "__main__":
    unittest.main()
