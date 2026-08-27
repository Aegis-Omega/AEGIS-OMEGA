#!/usr/bin/env python3
"""Regression tests for evidence semantics on the production bridge path."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PYTHON_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("AEGIS_ARRAY_BYTES", "4096")

import bridge
from platform_helpers import fetch_compliance_export, retrieve_swarm_memory


class _JsonResponse:
    def __init__(self, payload: object):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._body


class EpistemicRuntimeSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        with bridge._mc_lock:
            self._prior_chain = list(bridge._metacognitive_chain)
            bridge._metacognitive_chain.clear()

    def tearDown(self) -> None:
        with bridge._mc_lock:
            bridge._metacognitive_chain[:] = self._prior_chain

    def test_hash_chained_model_history_is_raw_memory_not_t1_evidence(self) -> None:
        bridge._mc_observe("CONSCIOUSNESS", "A model generated this response", "T2")

        context = bridge._mc_recent_context(3)

        self.assertIn("RAW_MEMORY", context)
        self.assertIn("does not establish semantic truth", context)
        self.assertNotIn("T1 evidence", context)

    def test_runtime_telemetry_hash_is_integrity_not_semantic_proof(self) -> None:
        context = bridge._build_live_state_context()

        self.assertIn("candidate observation", context)
        self.assertIn("does not prove semantic truth", context)
        self.assertNotIn("You can reference it as T1 evidence", context)
        self.assertNotIn("Gates operational: 605", context)

    def test_persisted_swarm_output_is_raw_memory_and_missing_verdict_is_unknown(self) -> None:
        rows = [{
            "artifacts": [{"role": "Builder", "output": "A prior model said this."}],
            "projection": {"first_year_arr_usd": 123},
            "created_at": "2026-08-24T00:00:00Z",
        }]
        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://memory.example.invalid",
                    "SUPABASE_SERVICE_ROLE_KEY": "test-only-key",
                },
                clear=False,
            ),
            patch("urllib.request.urlopen", return_value=_JsonResponse(rows)),
        ):
            context = retrieve_swarm_memory("objective", "revenue")

        self.assertIn("RAW_MEMORY", context)
        self.assertIn("verdict=UNKNOWN", context)
        self.assertIn("not independent evidence", context)
        self.assertNotIn("T1 evidence", context)

    def test_compliance_export_never_invents_approval_for_missing_verdict(self) -> None:
        rows = [{
            "cycle_id": "cycle-without-verdict",
            "objective": "objective",
            "mode": "revenue",
            "arr_usd": 123,
            "created_at": "2026-08-24T00:00:00Z",
        }]
        with (
            patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://memory.example.invalid",
                    "SUPABASE_SERVICE_ROLE_KEY": "test-only-key",
                },
                clear=False,
            ),
            patch("urllib.request.urlopen", return_value=_JsonResponse(rows)),
        ):
            records = fetch_compliance_export(None, None, 10)

        self.assertEqual(records[0]["constitutional_verdict"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
