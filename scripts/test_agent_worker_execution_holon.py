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
const scenario = process.argv[4] || 'none';
const credential = process.argv[5] || 'none';
let externalCalls = 0;
// Never perform a network call. This is a local model response fixture.
globalThis.fetch = async (_url, _opts) => {
  externalCalls++;
  return new Response(JSON.stringify({
    content:[{type:'text',text:JSON.stringify({
      summary:'test only',
      departments:{Engineering:{analysis:'fixture, not an agent'}},
      constitutional_audit:{verdict:'FLAG',chain_valid:null}
    })}]
  }),{status:200,headers:{'Content-Type':'application/json'}});
};
const headers = {'Content-Type':'application/json'};
if (credential === 'valid') headers['x-api-key'] = 'fixture-platform-key';
if (credential === 'wrong') headers['x-api-key'] = 'wrong-key';
if (credential === 'conflict') {
  headers['x-api-key'] = 'fixture-platform-key';
  headers['authorization'] = 'Bearer mismatched-key';
}
if (credential === 'bearer') headers['authorization'] = 'Bearer fixture-platform-key';
const request = new Request('https://aegis-vertex.aegisomega.com'+route, {
  method,headers,...(method==='POST' ? {body:'{"task":"test-only"}'} : {}),
});
const env = {
  ASSETS: {async fetch(_) {return new Response('ASSET_ONLY',{status:201});}},
  ...(scenario==='model'||scenario==='both'?{ANTHROPIC_API_KEY:'fixture-model-key'}:{}),
  ...(scenario==='both'?{AEGIS_PLATFORM_API_KEY:'fixture-platform-key'}:{}),
};
const response = await worker.fetch(request, env);
const raw = await response.text();
let parsed = null;
try { parsed = JSON.parse(raw) } catch {}
console.log(JSON.stringify({status: response.status, body: parsed, text: raw, externalCalls}));
"""


def invoke_worker(path, method="GET", scenario="none", credential="none"):
    if shutil.which("node") is None:
        raise AssertionError("Node.js required: no Node means no native Worker execution evidence")
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e",
         NODE_TEST, str(WORKER), path, method, scenario, credential],
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
        self.assertEqual(response["status"], 503)
        self.assertEqual(response["body"]["code"], "MODEL_BACKEND_UNAVAILABLE")
        self.assertEqual(response["externalCalls"], 0)

    def test_model_key_alone_denied_before_billing(self):
        response = invoke_worker("/platform/collaborate", "POST", scenario="model")
        self.assertEqual(response["status"], 503)
        self.assertEqual(response["body"]["code"], "PLATFORM_AUTH_UNCONFIGURED")
        self.assertEqual(response["externalCalls"], 0)

    def test_operator_key_missing_denied(self):
        response = invoke_worker("/platform/collaborate", "POST", scenario="both")
        self.assertEqual(response["status"], 401)
        self.assertEqual(response["externalCalls"], 0)

    def test_wrong_and_conflicting_operator_keys_denied(self):
        for v in ("wrong","conflict"):
            with self.subTest(v=v):
                response = invoke_worker("/platform/collaborate","POST",scenario="both",credential=v)
                self.assertEqual(response["status"], 401)
                self.assertEqual(response["externalCalls"], 0)

    def test_valid_operator_key_executes_one_mocked_model_call(self):
        response = invoke_worker("/platform/collaborate","POST",scenario="both",credential="valid")
        self.assertEqual(response["status"],200)
        self.assertEqual(response["externalCalls"],1)
        body = response["body"]["data"]
        self.assertEqual(body["declared_departments"],39)
        self.assertEqual(body["departments_collaborated"],0)
        self.assertEqual(body["individual_agents_executed"],0)
        self.assertEqual(body["department_artifacts_generated"],1)
        self.assertEqual(body["execution_kind"],"single_model_synthesis")

    def test_valid_bearer_operator_key_executes_one_mocked_model_call(self):
        response = invoke_worker("/platform/collaborate","POST",scenario="both",credential="bearer")
        self.assertEqual(response["status"],200)
        self.assertEqual(response["externalCalls"],1)

    def test_static_asset_fallback_is_preserved(self):
        response = invoke_worker("/not-an-agent-path")
        self.assertEqual(response["status"], 201)
        self.assertEqual(response["text"], "ASSET_ONLY")


if __name__ == "__main__":
    unittest.main()
