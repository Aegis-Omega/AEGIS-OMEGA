from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.sdk.sovereign_execution import (
    AuthorityEvaluator,
    DEFAULT_POLICY,
    ExecutionIdentityEnvelope,
    ZERO_HASH,
    canonical_hash,
    compute_workspace_binding,
)
from harness.sdk.resend_inbound import CAPABILITY, TOOL
from scripts import resend_inbound_ingest as ingest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/resend_inbound/receiving.json"
BASE_SHA = "495bfd85d79abcb2b4f6898fe9c156488492426a"
SECRET = "whsec_" + base64.b64encode(b"synthetic-test-key-not-a-live-secret").decode()


def identity(policy_root: str) -> ExecutionIdentityEnvelope:
    binding = compute_workspace_binding(
        repository_remote="https://github.com/Aegis-Omega/AEGIS-OMEGA.git",
        repository_root=".",
        project_identity="AEGIS-OMEGA",
        source_commit=BASE_SHA,
        operator_authorization="NONE",
    )
    return ExecutionIdentityEnvelope(
        schema_version="1.0.0",
        repository_identity="https://github.com/Aegis-Omega/AEGIS-OMEGA.git",
        repository_root=".", source_commit=BASE_SHA, branch_or_ref="main",
        project_identity="AEGIS-OMEGA", workspace_root=".", workspace_binding=binding,
        parent_state_root=ZERO_HASH, skills_root=ZERO_HASH, registry_root=ZERO_HASH,
        policy_root=policy_root, actor_class="TRANSPORT_ADAPTER", actor_identity="resend-inbound",
        model_identity="NONE", session_identity="local-cli-fixture", physical_executor="local-python",
        tool_identity=TOOL, workflow_identity="inbound-evidence", authority_domain="inbound-email",
        requested_capability=CAPABILITY, observed_authority="NONE", approval_reference="NONE",
        input_digest=ZERO_HASH, action_digest=ZERO_HASH, expected_pre_state=ZERO_HASH,
        deterministic_nonce="unbound",
    )


def signed_request() -> dict:
    event = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
    ts = str(int(time.time()))
    event_id = "msg_cli_synthetic_0001"
    key = base64.b64decode(SECRET.removeprefix("whsec_"))
    signature = base64.b64encode(hmac.new(key, f"{event_id}.{ts}.".encode() + raw, hashlib.sha256).digest()).decode()
    return {
        "raw_body_base64": base64.b64encode(raw).decode(),
        "headers": [
            ["Content-Type", "application/json"],
            ["svix-id", event_id], ["svix-timestamp", ts], ["svix-signature", "v1," + signature],
        ],
        "method": "POST",
    }


class ResendInboundIngestTests(unittest.TestCase):
    def test_missing_trusted_config_fails_closed(self):
        result = ingest.run_ingest(signed_request(), environ={})
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["codes"], ["CONFIGURATION_UNAVAILABLE"])
        self.assertEqual(result["external_effect"], "NOT_EXECUTED")

    def test_malformed_request_fails_before_runtime(self):
        result = ingest.run_ingest({"raw_body_base64": "***", "headers": [], "extra": True}, environ={})
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["codes"], ["REQUEST_INVALID"])

    def test_valid_signed_event_maps_to_existing_authority_and_stays_denied(self):
        policy_root = canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", DEFAULT_POLICY)
        ident = identity(policy_root)
        with tempfile.TemporaryDirectory() as tmp:
            journal = str(Path(tmp) / "journal.sqlite3")
            env = {
                ingest.ENV_IDENTITY: json.dumps(ident.__dict__, separators=(",", ":")),
                ingest.ENV_SECRETS: json.dumps([SECRET]),
                ingest.ENV_ADDRESSES: json.dumps(["inbound@example.test"]),
                ingest.ENV_SCOPE: "fixture-endpoint-v1",
                ingest.ENV_DOMAIN: "inbound-email",
                ingest.ENV_JOURNAL: journal,
            }
            with patch.object(ingest, "load_policy", return_value=(DEFAULT_POLICY, policy_root)), \
                 patch.object(ingest, "load_capability_registry", return_value=({}, ZERO_HASH)):
                result = ingest.run_ingest(signed_request(), environ=env, repo_root=ROOT)
            self.assertEqual(result["status"], "VERIFIED_NOT_ADMITTED")
            self.assertEqual(result["decision"]["outcome"], "DENIED")
            self.assertIn("UNMAPPED_CAPABILITY", result["decision"]["denial_codes"])
            self.assertEqual(result["identity"]["requested_capability"], CAPABILITY)
            self.assertEqual(result["event"]["capability_request"], CAPABILITY)
            self.assertEqual(result["event"]["payload"]["data"]["execution_state"], "NOT_EXECUTED")
            self.assertEqual(result["external_effect"], "NOT_EXECUTED")
            self.assertNotIn("whsec_", json.dumps(result))

    def test_second_delivery_is_deduplicated(self):
        policy_root = canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", DEFAULT_POLICY)
        ident = identity(policy_root)
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                ingest.ENV_IDENTITY: json.dumps(ident.__dict__, separators=(",", ":")),
                ingest.ENV_SECRETS: json.dumps([SECRET]),
                ingest.ENV_ADDRESSES: json.dumps(["inbound@example.test"]),
                ingest.ENV_SCOPE: "fixture-endpoint-v1",
                ingest.ENV_DOMAIN: "inbound-email",
                ingest.ENV_JOURNAL: str(Path(tmp) / "journal.sqlite3"),
            }
            request = signed_request()
            with patch.object(ingest, "load_policy", return_value=(DEFAULT_POLICY, policy_root)), \
                 patch.object(ingest, "load_capability_registry", return_value=({}, ZERO_HASH)):
                first = ingest.run_ingest(request, environ=env, repo_root=ROOT)
                second = ingest.run_ingest(request, environ=env, repo_root=ROOT)
            self.assertEqual(first["status"], "VERIFIED_NOT_ADMITTED")
            self.assertEqual(second["status"], "DUPLICATE")
            self.assertEqual(second["external_effect"], "NOT_EXECUTED")


    def test_cli_main_missing_config_is_structured_fail_closed(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("AEGIS_RESEND_")}
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/resend_inbound_ingest.py")],
            input=json.dumps(signed_request()).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=ROOT, check=True, timeout=5,
        )
        self.assertEqual(proc.stderr, b"")
        parsed = json.loads(proc.stdout)
        self.assertEqual(parsed["status"], "REJECTED")
        self.assertEqual(parsed["codes"], ["CONFIGURATION_UNAVAILABLE"])
        self.assertEqual(parsed["external_effect"], "NOT_EXECUTED")

    def test_contract_matches_current_cli_and_provider_surface(self):
        contract = (ROOT / "docs/resend-inbound-contract-v1.md").read_text(encoding="utf-8")
        self.assertIn("accepts exactly one webhook event type", contract)
        self.assertIn("`email.received`", contract)
        self.assertIn("**rejects** `inbox.email.received`", contract)
        self.assertIn("AEGIS_RESEND_EXECUTION_IDENTITY_JSON", contract)
        self.assertNotIn("AEGIS_EXECUTION_IDENTITY_JSON` — pre-bound", contract)
        self.assertIn("At most **8 metadata records**", contract)

    def test_cli_uses_dedicated_resend_identity_binding(self):
        self.assertEqual(ingest.ENV_IDENTITY, "AEGIS_RESEND_EXECUTION_IDENTITY_JSON")
        self.assertNotEqual(ingest.ENV_IDENTITY, "AEGIS_EXECUTION_IDENTITY_JSON")

    def test_non_post_is_rejected_without_external_effect(self):
        policy_root = canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", DEFAULT_POLICY)
        ident = identity(policy_root)
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                ingest.ENV_IDENTITY: json.dumps(ident.__dict__, separators=(",", ":")),
                ingest.ENV_SECRETS: json.dumps([SECRET]),
                ingest.ENV_ADDRESSES: json.dumps(["inbound@example.test"]),
                ingest.ENV_SCOPE: "fixture-endpoint-v1",
                ingest.ENV_DOMAIN: "inbound-email",
                ingest.ENV_JOURNAL: str(Path(tmp) / "journal.sqlite3"),
            }
            req = signed_request(); req["method"] = "GET"
            with patch.object(ingest, "load_policy", return_value=(DEFAULT_POLICY, policy_root)), \
                 patch.object(ingest, "load_capability_registry", return_value=({}, ZERO_HASH)):
                result = ingest.run_ingest(req, environ=env, repo_root=ROOT)
            self.assertEqual(result["status"], "REJECTED")
            self.assertIn("METHOD_UNSUPPORTED", result["codes"])
            self.assertEqual(result["external_effect"], "NOT_EXECUTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
