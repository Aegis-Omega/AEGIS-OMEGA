#!/usr/bin/env python3
"""HTTP integration test for the production bridge resident-runtime path."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

PYTHON_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("AEGIS_ARRAY_BYTES", "4096")

import bridge


def _git(*args: str) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


class ResidentLivePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.environment = patch.dict(
            os.environ,
            {
                "AEGIS_RESIDENT_REPOSITORY_ROOT": str(REPO_ROOT),
                "AEGIS_RESIDENT_STATE_ROOT": str(Path(self.tmp.name) / "resident"),
                "SUPABASE_URL": "",
                "SUPABASE_SERVICE_ROLE_KEY": "",
            },
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        if hasattr(bridge, "_resident_runtime_instance"):
            bridge._resident_runtime_instance = None
        self.server = bridge.HTTPServer(("127.0.0.1", 0), bridge.BridgeHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"content-type": "application/json", "x-api-key": "aegis_live_test"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_repository_event_invokes_closed_loop_and_exposes_replay(self) -> None:
        before_status = _git("status", "--porcelain", "--untracked-files=all")
        head = _git("rev-parse", "HEAD")
        event = {
            "event_id": "live-repository-event-1",
            "idempotency_key": "live-repository-event-1",
            "repository_head": head,
            "changed_path": "CLAUDE.md",
            "question": "Verify this repository observation in an isolated experiment.",
            "source": "git",
            "sequence": 1,
            "max_cost_microunits": 100,
            "max_latency_ms": 30_000,
            "requested_authority": "D1",
        }

        status, response = self.request("POST", "/platform/resident/events", event)

        self.assertEqual(status, 200)
        receipt = response["data"]
        self.assertEqual(receipt["knowledge_decision"], "VERIFIED")
        self.assertEqual(receipt["authority_before"], receipt["authority_after"])
        self.assertTrue(receipt["experiment_id"])
        self.assertTrue(receipt["verification_receipt_root"])

        replay_status, replay = self.request(
            "GET",
            f"/platform/resident/runs/{receipt['run_id']}/verify",
        )
        self.assertEqual(replay_status, 200)
        self.assertTrue(replay["data"]["integrity_verified"])
        self.assertTrue(replay["data"]["lineage_verified"])
        self.assertFalse(replay["data"]["semantic_truth_proven"])

        projection_status, projection = self.request("GET", "/platform/resident/status")
        self.assertEqual(projection_status, 200)
        self.assertEqual(projection["data"]["completed_runs"], 1)
        self.assertFalse(projection["data"]["authority_self_escalation"])
        self.assertEqual(_git("status", "--porcelain", "--untracked-files=all"), before_status)

    def test_configured_local_inference_outage_is_exposed_as_unknown(self) -> None:
        head = _git("rev-parse", "HEAD")
        event = {
            "event_id": "live-local-outage-1",
            "idempotency_key": "live-local-outage-1",
            "repository_head": head,
            "changed_path": "CLAUDE.md",
            "question": "Classify this repository observation.",
            "source": "git",
            "sequence": 2,
            "max_cost_microunits": 100,
            "max_latency_ms": 2_000,
            "requested_authority": "D1",
        }
        with patch.dict(
            os.environ,
            {
                "AEGIS_LOCAL_INFERENCE_ENDPOINT": "http://127.0.0.1:1",
                "AEGIS_LOCAL_INFERENCE_PROVIDER_ID": "local-openai-compatible",
                "AEGIS_LOCAL_INFERENCE_MODEL_ID": "unavailable-test-model",
            },
            clear=False,
        ):
            bridge._resident_runtime_instance = None
            status, response = self.request("POST", "/platform/resident/events", event)

        self.assertEqual(status, 200)
        self.assertEqual(response["data"]["knowledge_decision"], "UNKNOWN")
        self.assertIn("LOCAL_MODEL_UNAVAILABLE", response["data"]["reason_codes"])

    def test_failed_sensor_bootstrap_is_unavailable_not_quarantined_or_approved(self) -> None:
        head = _git("rev-parse", "HEAD")
        event = {
            "event_id": "live-bootstrap-outage-1",
            "idempotency_key": "live-bootstrap-outage-1",
            "repository_head": head,
            "changed_path": "CLAUDE.md",
            "question": "Observe only if the resident sensor substrate is available.",
            "source": "git",
            "sequence": 3,
            "max_cost_microunits": 100,
            "max_latency_ms": 2_000,
            "requested_authority": "D1",
        }
        with patch.dict(
            os.environ,
            {"AEGIS_RESIDENT_BOOTSTRAP_STATUS": "UNKNOWN"},
            clear=False,
        ):
            bridge._resident_runtime_instance = None
            status, response = self.request("POST", "/platform/resident/events", event)

        self.assertEqual(status, 503)
        self.assertEqual(response["knowledge_decision"], "UNKNOWN")
        self.assertNotEqual(response["knowledge_decision"], "QUARANTINED")

    def test_generated_claude_response_remains_t2_candidate_output(self) -> None:
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="candidate model statement")],
            usage=SimpleNamespace(input_tokens=11, output_tokens=7),
            stop_reason="end_turn",
        )
        client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=response)))

        with patch("anth_client.get_client", return_value=client):
            status, payload = self.request(
                "POST",
                "/claude",
                {"messages": [{"role": "user", "content": "Generate a hypothesis."}]},
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["envelope"]["epistemic_tier"], "T2")
        self.assertEqual(bridge._metacognitive_chain[-1]["tier"], "T2")


if __name__ == "__main__":
    unittest.main()
