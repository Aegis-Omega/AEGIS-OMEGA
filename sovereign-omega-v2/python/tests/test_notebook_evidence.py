#!/usr/bin/env python3
"""Tests for secret-safe notebook evidence envelopes."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.notebook_evidence import summarize_notebook_bytes  # noqa: E402
from harness.sdk.sovereign_execution import SovereignExecutionError, canonical_bytes  # noqa: E402


class NotebookEvidenceTests(TestCase):
    def notebook(self, source: str = "def calculate_hd(a, b):\n    return abs(a-b)\n") -> bytes:
        payload = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "cells": [
                {"cell_type": "markdown", "source": ["# Evidence book"]},
                {"cell_type": "code", "source": [source], "outputs": []},
            ],
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")

    def test_summary_hashes_complete_bytes_and_catalogs_functions(self) -> None:
        summary = summarize_notebook_bytes(
            self.notebook(),
            source_label="unit.ipynb",
            source_locator="private://unit",
        )
        self.assertEqual(summary.cell_count, 2)
        self.assertEqual(summary.code_cell_count, 1)
        self.assertEqual(summary.markdown_cell_count, 1)
        self.assertEqual(summary.function_names, ("calculate_hd",))
        self.assertEqual(summary.distribution_status, "STRUCTURALLY_SAFE")
        self.assertEqual(summary.authority_effect, "NONE")
        self.assertEqual(len(summary.root), 64)

    def test_secret_is_detected_but_never_persisted(self) -> None:
        secret = "DO_NOT_PERSIST_THIS_VALUE"
        data = self.notebook(f'KAGGLE_KEY = "{secret}"\n')
        summary = summarize_notebook_bytes(
            data,
            source_label="unsafe.ipynb",
            source_locator="private://unsafe",
        )
        self.assertGreater(summary.secret_finding_count, 0)
        self.assertEqual(summary.distribution_status, "REDACTION_REQUIRED")
        serialized = canonical_bytes(asdict(summary))
        self.assertNotIn(secret.encode("utf-8"), serialized)

    def test_source_locator_is_not_stored_raw(self) -> None:
        locator = "https://private.example/notebook/secret-id"
        summary = summarize_notebook_bytes(
            self.notebook(),
            source_label="unit.ipynb",
            source_locator=locator,
        )
        self.assertFalse(hasattr(summary, "source_locator"))
        self.assertNotIn(locator.encode("utf-8"), canonical_bytes(asdict(summary)))

    def test_invalid_json_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "NOTEBOOK_JSON_INVALID"):
            summarize_notebook_bytes(
                b"not-json",
                source_label="bad",
                source_locator="private://bad",
            )

    def test_notebook_cannot_gain_authority(self) -> None:
        summary = summarize_notebook_bytes(
            self.notebook(),
            source_label="unit.ipynb",
            source_locator="private://unit",
        )
        with self.assertRaisesRegex(SovereignExecutionError, "NOTEBOOK_AUTHORITY_EFFECT_INVALID"):
            replace(summary, authority_effect="GRANT").validate()


if __name__ == "__main__":
    main()
