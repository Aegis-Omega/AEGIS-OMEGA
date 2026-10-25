"""Run the actual Cloudflare Worker TypeScript handler without external services.

Node strips TypeScript types; calls the real exported fetch() handler. The test
installs a network-deny global fetch, with no platform/model credentials.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker-src/index.ts"

NODE_TEST = r"""
import { pathToFileURL } from 'node:url';
const worker = (await import(pathToFileURL(process.argv[1]).href)).default;
globalThis.fetch = async () => { throw new Error('EXTERNAL_NETWORK_DENIED_IN_TEST'); };
const route = process.argv[2];
const method = process.argv[3];
const request = new Request('https://aegis-vertex.aegisomega.com'+route, {
  method,
  ...(method==='POST' ? {headers:{'Content-Type':'application/json'},body:'{"task":"test-only"}'} : {}),
});
const env = {
  ASSETS: {
    async fetch(_) { return new Response('ASSET_ONLY', {status: 201}); }
  },
  // No ANTHROPIC_API_KEY or execution backend is supplied.
};
const response = await worker.fetch(request, env);
const raw = await response.text();
let parsed = null;
try { parsed = JSON.parse(raw) } catch {}
console.log(JSON.stringify({status: response.status, body: parsed, text: raw}));
"""


def invoke_worker(path, method="GET"):
    if shutil.which("node") is None:
        raise AssertionError("Node.js required: no Node means no native Worker execution evidence")
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e",
         NODE_TEST, str(WORKER), path, method],
        cwd=ROOT, capture_output=True, text=True, timeout=25,
    )
    if result.returncode:
        raise AssertionError(
            f"Worker execution failed: {result.returncode}: {result.stderr[-2000:]}"
        )
    return json.loads(result.stdout.strip().splitlines()[-1])


class AgentWorkerExecutionHolonTests(unittest.TestCase):
    def test_no_fake_pending_execution_on_post(self):
        response = invoke_worker("/platform/executions", "POST")
        self.assertEqual(response["status"], 503)
        self.assertEqual(response["body"]["code"], "EXECUTION_BACKEND_UNAVAILABLE")
        self.assertNotIn("pending", response["text"])
        self.assertNotIn("stream_url", response["text"])

    def test_nonexistent_execution_stream_is_explicit(self):
        response = invoke_worker("/platform/executions/live?id=nonexistent", "GET")
        self.assertEqual(response["status"], 501)
        self.assertEqual(response["body"]["code"], "EXECUTION_STREAM_UNAVAILABLE")
        self.assertNotIn("ASSET_ONLY", response["text"])

    def test_status_distinguishes_declared_departments_from_real_workers(self):
        response = invoke_worker("/platform/status")
        self.assertEqual(response["status"], 200)
        details = response["body"]["data"]
        self.assertEqual(details["declared_departments"], 39)
        self.assertEqual(details["total_agents"], 0)
        self.assertEqual(details["operational_agents"], 0)
        self.assertFalse(details["available"])
        self.assertFalse(details["inference_backend_configured"])
        self.assertEqual(details["execution_backend"], "unavailable_at_edge")

    def test_existing_health_endpoint_remains_accessible_and_unverified(self):
        response = invoke_worker("/health")
        self.assertEqual(response["status"], 200)
        self.assertFalse(response["body"]["verified"])
        self.assertEqual(response["body"]["verification"], "no_gate_at_edge")

    def test_no_key_cannot_spend_on_collaboration(self):
        response = invoke_worker("/platform/collaborate", "POST")
        self.assertEqual(response["status"], 401)
        self.assertEqual(response["body"]["code"], "UNAUTHORIZED")

    def test_static_asset_fallback_is_preserved(self):
        response = invoke_worker("/not-an-agent-path")
        self.assertEqual(response["status"], 201)
        self.assertEqual(response["text"], "ASSET_ONLY")


if __name__ == "__main__":
    unittest.main()
