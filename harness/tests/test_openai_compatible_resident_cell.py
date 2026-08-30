from __future__ import annotations

from dataclasses import replace
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest

from harness.sdk.resident_runtime import (
    AnalysisPacketV1,
    OpenAICompatibleResidentCell,
)


class _InferenceHandler(BaseHTTPRequestHandler):
    response_content = "{}"
    response_status = 200
    active = 0
    max_active = 0
    lock = threading.Lock()
    requests: list[dict] = []
    delay_seconds = 0.0

    def log_message(self, *_args):
        return

    def do_GET(self):
        if self.path == "/health":
            self._reply(200, {"status": "ok"})
        elif self.path == "/v1/models":
            self._reply(200, {"object": "list", "data": [{"id": "local-test-model"}]})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        with type(self).lock:
            type(self).active += 1
            type(self).max_active = max(type(self).max_active, type(self).active)
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            type(self).requests.append(payload)
            if type(self).delay_seconds:
                time.sleep(type(self).delay_seconds)
            if type(self).response_status != 200:
                self._reply(type(self).response_status, {"error": "provider unavailable"})
                return
            self._reply(
                200,
                {
                    "id": "completion-1",
                    "choices": [
                        {"message": {"role": "assistant", "content": type(self).response_content}}
                    ],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
                },
            )
        finally:
            with type(self).lock:
                type(self).active -= 1

    def _reply(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class OpenAICompatibleResidentCellTests(unittest.TestCase):
    def setUp(self) -> None:
        _InferenceHandler.response_content = json.dumps(
            {
                "classification": "repository_integrity",
                "hypothesis": "The isolated checkout will reproduce the observed digest.",
                "predicted_content_sha256": "b" * 64,
                "confidence_bps": 7000,
                "escalation_reason": None,
            }
        )
        _InferenceHandler.response_status = 200
        _InferenceHandler.requests = []
        _InferenceHandler.active = 0
        _InferenceHandler.max_active = 0
        _InferenceHandler.delay_seconds = 0.0
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _InferenceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}"
        self.packet = AnalysisPacketV1(
            run_id="run-test",
            task_id="task-test",
            repository_head="a" * 40,
            changed_path="observed.txt",
            question="Classify the observed repository change.",
            observed_content_sha256="b" * 64,
            observation_root="c" * 64,
            expected_information_gain_bps=5000,
            budget_microunits=1_000,
        )

    def cell(self, **overrides) -> OpenAICompatibleResidentCell:
        values = dict(
            endpoint=self.endpoint,
            provider_id="local-openai-compatible",
            model_id="local-test-model",
            timeout_ms=2_000,
            max_parallelism=2,
            circuit_breaker_failures=2,
            microunits_per_1k_tokens=100,
        )
        values.update(overrides)
        return OpenAICompatibleResidentCell(**values)

    def test_structured_response_is_evidence_only_and_provenance_bound(self) -> None:
        cell = self.cell()
        result = cell.analyze(self.packet)

        self.assertEqual(result.status, "SUCCEEDED")
        self.assertEqual(result.authority, "EVIDENCE_ONLY")
        self.assertEqual(result.evidence_roots, (self.packet.observation_root,))
        self.assertEqual(result.input_tokens, 11)
        self.assertEqual(result.output_tokens, 7)
        self.assertEqual(result.cost_microunits, 2)
        self.assertEqual(_InferenceHandler.requests[0]["model"], "local-test-model")
        self.assertEqual(
            _InferenceHandler.requests[0]["response_format"],
            {"type": "json_object"},
        )
        self.assertEqual(_InferenceHandler.requests[0]["max_completion_tokens"], 512)

    def test_malformed_model_json_never_becomes_success(self) -> None:
        _InferenceHandler.response_content = "not-json"
        result = self.cell().analyze(self.packet)
        self.assertEqual(result.status, "MALFORMED")
        self.assertEqual(result.hypothesis, "")
        self.assertEqual(result.evidence_roots, (self.packet.observation_root,))

    def test_provider_outage_opens_circuit_and_never_fabricates_output(self) -> None:
        _InferenceHandler.response_status = 503
        cell = self.cell(circuit_breaker_failures=2)
        first = cell.analyze(self.packet)
        second = cell.analyze(self.packet)
        requests_before_open_call = len(_InferenceHandler.requests)
        third = cell.analyze(self.packet)
        self.assertEqual((first.status, second.status, third.status), ("UNAVAILABLE",) * 3)
        self.assertEqual(third.hypothesis, "")
        self.assertEqual(len(_InferenceHandler.requests), requests_before_open_call)

    def test_health_and_capability_discovery_use_openai_compatible_boundaries(self) -> None:
        cell = self.cell()
        self.assertEqual(cell.health()["status"], "ok")
        discovery = cell.discover_models()
        self.assertEqual(discovery["data"][0]["id"], "local-test-model")

    def test_bounded_concurrency_never_exceeds_configured_slots(self) -> None:
        _InferenceHandler.delay_seconds = 0.05
        cell = self.cell(max_parallelism=2)
        results = []
        threads = [
            threading.Thread(target=lambda: results.append(cell.analyze(self.packet)))
            for _ in range(5)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(result.status == "SUCCEEDED" for result in results))
        self.assertLessEqual(_InferenceHandler.max_active, 2)

    def test_provider_response_bytes_are_bounded_and_fail_closed(self) -> None:
        _InferenceHandler.response_content = "x" * 4_096

        result = self.cell(max_response_bytes=512).analyze(self.packet)

        self.assertEqual(result.status, "MALFORMED")
        self.assertEqual(result.hypothesis, "")

    def test_worst_case_provider_cost_over_budget_stops_before_call(self) -> None:
        result = self.cell().analyze(replace(self.packet, budget_microunits=0))

        self.assertEqual(result.status, "BUDGET_EXHAUSTED")
        self.assertEqual(_InferenceHandler.requests, [])


if __name__ == "__main__":
    unittest.main()
