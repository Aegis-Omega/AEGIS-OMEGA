#!/usr/bin/env python3
"""Behavioral contract for one live proof-carrying platform transition."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import asdict, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.complete_verifier import TRUE  # noqa: E402
from harness.sdk.effect_adapters import EFFECT_WITNESS_KIND, EffectAdapterError  # noqa: E402
from harness.sdk.effect_verifier import FALSE, EffectVerifier  # noqa: E402
from harness.sdk.proof_carrying_platform_execution import (  # noqa: E402
    PlatformExecutionDispatcher,
    ProofCarryingPlatformExecutionError,
    execute_platform_start_from_environment,
    execute_verified_platform_start,
)
from harness.sdk.platform_effect_adapter import (  # noqa: E402
    PlatformExecutionEffectAdapter,
    request_platform_json,
)
from harness.sdk.sovereign_execution import (  # noqa: E402
    SCHEMA_VERSION,
    ZERO_HASH,
    ApprovalGrant,
    ExecutionIdentityEnvelope,
    canonical_hash,
    compute_workspace_binding,
    load_capability_registry,
    load_policy,
)
from harness.sdk.transition_receipts import (  # noqa: E402
    DECISION_RECEIPT_KIND,
    PERMIT,
    DecisionReceipt,
    TransitionIdentity,
    admission_policy_commitment,
    verifier_policy_commitment,
)

ACTION = {
    "operation": "start-execution",
    "objective": "Create one independently verified durable execution",
    "mode": "analysis",
    "live": False,
}
NONCE = "live-platform-transition-001"
ACTION_DIGEST = canonical_hash("AEGIS_REQUESTED_ACTION_V1", ACTION)
EXECUTION_DIGEST = canonical_hash(
    "AEGIS_PLATFORM_EXECUTION_INSTANCE_V1",
    {"action_digest": ACTION_DIGEST, "deterministic_nonce": NONCE},
)
EXECUTION_ID = f"aegis-{EXECUTION_DIGEST[:32]}"
TARGET = f"/platform/executions/{EXECUTION_ID}"
ABSENT_PRE_STATE = canonical_hash(
    "AEGIS_PLATFORM_EXECUTION_STATE_V1",
    {"target_identity": TARGET, "exists": False},
)
REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"


class PlatformFixture:
    def __init__(self) -> None:
        self.exists = False
        self.get_count = 0
        self.post_count = 0
        self.post_body: dict[str, object] | None = None
        self.git_sha = "b" * 40
        self.git_sha_after_post: str | None = None
        self.redirect_target_count = 0
        self.redirect_target_api_key: str | None = None

    def handler(self):
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def respond(self, status: int, payload: dict[str, object]) -> None:
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Contract-Version", "1.0.0")
                self.send_header("X-Git-SHA", fixture.git_sha)
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/redirect":
                    host, port = self.server.server_address
                    self.send_response(307)
                    self.send_header("Location", f"http://{host}:{port}/redirect-target")
                    self.end_headers()
                    return
                if self.path == "/redirect-target":
                    fixture.redirect_target_count += 1
                    fixture.redirect_target_api_key = self.headers.get("X-API-Key")
                    self.respond(200, {"redirected": True})
                    return
                fixture.get_count += 1
                if self.path != TARGET:
                    self.respond(404, {"error": "execution not found", "code": "NOT_FOUND", "execution_id": "wrong-target"})
                    return
                if not fixture.exists:
                    self.respond(404, {"error": "execution not found", "code": "NOT_FOUND", "execution_id": EXECUTION_ID})
                    return
                self.respond(200, {
                    "contract_version": "1.0.0",
                    "execution_id": EXECUTION_ID,
                    "timestamp": "2026-08-26T00:00:00Z",
                    "is_replay_reconstructable": True,
                    "data": {"execution_id": EXECUTION_ID, "status": "running"},
                })

            def do_POST(self):
                fixture.post_count += 1
                length = int(self.headers.get("Content-Length", "0"))
                fixture.post_body = json.loads(self.rfile.read(length).decode("utf-8"))
                if self.path != "/platform/executions":
                    self.respond(404, {"error": "not found"})
                    return
                if getattr(fixture, "materialize_on_post", True):
                    fixture.exists = True
                self.respond(202, {
                    "contract_version": "1.0.0",
                    "execution_id": EXECUTION_ID,
                    "timestamp": "2026-08-26T00:00:00Z",
                    "is_replay_reconstructable": True,
                    "data": {
                        "execution_id": EXECUTION_ID,
                        "stream_url": f"/platform/executions/live?id={EXECUTION_ID}",
                        "status": "pending",
                    },
                })
                if fixture.git_sha_after_post is not None:
                    fixture.git_sha = fixture.git_sha_after_post

        return Handler


class LivePlatformEffectChainTests(TestCase):
    def setUp(self) -> None:
        self.fixture = PlatformFixture()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.fixture.handler())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    @staticmethod
    def transition_and_decision() -> tuple[TransitionIdentity, DecisionReceipt]:
        transition = TransitionIdentity(
            schema_version=SCHEMA_VERSION,
            source_commit="b" * 40,
            pre_state_commitment=ABSENT_PRE_STATE,
            identity_root="1" * 64,
            delegation_commitment="2" * 64,
            capability_commitment="3" * 64,
            action_digest=ACTION_DIGEST,
            deterministic_nonce=NONCE,
            fence_commitment="4" * 64,
            verifier_policy_commitment=verifier_policy_commitment(),
            admission_policy_commitment=admission_policy_commitment(),
        )
        return transition, DecisionReceipt(
            receipt_kind=DECISION_RECEIPT_KIND,
            transition_id=transition.root,
            decision_outcome=PERMIT,
            policy_decision_root="5" * 64,
        )

    def run_reference_slice(self):
        transition, decision = self.transition_and_decision()
        bridge_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return execute_verified_platform_start(
            transition=transition,
            decision_receipt=decision,
            action=ACTION,
            dispatcher=PlatformExecutionDispatcher(bridge_url=bridge_url, api_key="aegis_test"),
            effect_adapter=PlatformExecutionEffectAdapter(bridge_url=bridge_url, api_key="aegis_test"),
        )

    def test_start_execution_requires_independent_effect_observation_before_complete_verification(self) -> None:
        bundle = self.run_reference_slice()

        self.assertEqual(EXECUTION_ID, bundle.execution_receipt.execution_instance_id)
        self.assertEqual(EFFECT_WITNESS_KIND, bundle.effect_witness.witness_kind)
        self.assertTrue(bundle.effect_witness.effect_changed)
        self.assertEqual(TRUE, bundle.effect_verification.status)
        self.assertEqual(TRUE, bundle.complete_verification.status)
        self.assertEqual("b" * 40, bundle.platform_artifact_provenance.git_sha)
        self.assertEqual("1.0.0", bundle.platform_artifact_provenance.contract_version)
        self.assertEqual(TARGET, bundle.platform_artifact_provenance.target_identity)
        self.assertEqual(1, self.fixture.post_count)
        self.assertEqual(3, self.fixture.get_count)  # one pre-state read + two independent post-state reads
        self.assertEqual(EXECUTION_ID, self.fixture.post_body["execution_id"])

    def test_redirect_is_explicitly_rejected_without_forwarding_platform_credential(self) -> None:
        bridge_url = f"http://127.0.0.1:{self.server.server_address[1]}"

        with self.assertRaisesRegex(EffectAdapterError, "PLATFORM_REDIRECT_REJECTED"):
            request_platform_json(
                bridge_url=bridge_url,
                api_key="redirect-secret",
                method="GET",
                path="/redirect",
            )

        self.assertEqual(0, self.fixture.redirect_target_count)
        self.assertIsNone(self.fixture.redirect_target_api_key)

    def test_post_acceptance_without_observed_record_cannot_create_effect_or_complete_receipt(self) -> None:
        self.fixture.materialize_on_post = False

        with self.assertRaises(ProofCarryingPlatformExecutionError) as raised:
            self.run_reference_slice()

        self.assertIn("PLATFORM_EFFECT_NOT_OBSERVED", str(raised.exception))
        self.assertEqual("ADMITTED", raised.exception.authority_outcome)
        self.assertEqual("UNKNOWN", raised.exception.external_effect)
        self.assertEqual(1, self.fixture.post_count)
        self.assertEqual(3, self.fixture.get_count)

    def test_bridge_revision_mismatch_is_rejected_before_dispatch(self) -> None:
        self.fixture.git_sha = "c" * 40

        with self.assertRaises(ProofCarryingPlatformExecutionError) as raised:
            self.run_reference_slice()

        self.assertIn("PLATFORM_SOURCE_COMMIT_MISMATCH", str(raised.exception))
        self.assertEqual("ADMITTED", raised.exception.authority_outcome)
        self.assertEqual("NOT_EXECUTED", raised.exception.external_effect)
        self.assertEqual(0, self.fixture.post_count)
        self.assertEqual(1, self.fixture.get_count)

    def test_revision_change_after_dispatch_cannot_issue_effect_receipt(self) -> None:
        self.fixture.git_sha_after_post = "c" * 40

        with self.assertRaises(ProofCarryingPlatformExecutionError) as raised:
            self.run_reference_slice()

        self.assertIn("PLATFORM_ARTIFACT_PROVENANCE_CHANGED", str(raised.exception))
        self.assertEqual("ADMITTED", raised.exception.authority_outcome)
        self.assertEqual("UNKNOWN", raised.exception.external_effect)
        self.assertEqual(1, self.fixture.post_count)
        self.assertEqual(2, self.fixture.get_count)

    def test_copied_platform_witness_is_not_adapter_issued_evidence(self) -> None:
        bundle = self.run_reference_slice()
        copied_witness = replace(bundle.effect_witness)

        result = EffectVerifier().verify_effect(
            transition=bundle.transition,
            execution_receipt=bundle.execution_receipt,
            witness=copied_witness,
        )

        self.assertEqual(FALSE, result.status)

    def test_unobserved_live_capability_denies_before_any_platform_effect(self) -> None:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
        approval_reference = "approval-live-platform-001"
        workspace_binding = compute_workspace_binding(
            repository_remote=REMOTE,
            repository_root=".",
            project_identity="AEGIS-OMEGA",
            source_commit=source_commit,
            operator_authorization=approval_reference,
        )
        _, policy_root = load_policy(REPO_ROOT / "harness/policies/consequence-policy.v1.json")
        _, registry_root = load_capability_registry(
            repository_root=REPO_ROOT,
            skill_tree_path=REPO_ROOT / "harness/skill_tree.json",
            capability_map_path=REPO_ROOT / "harness/policies/capability-map.v1.json",
        )
        identity = ExecutionIdentityEnvelope(
            schema_version=SCHEMA_VERSION,
            repository_identity=REMOTE,
            repository_root=".",
            source_commit=source_commit,
            branch_or_ref="refs/heads/fix/live-effect-chain-v1",
            project_identity="AEGIS-OMEGA",
            workspace_root=".",
            workspace_binding=workspace_binding,
            parent_state_root=ZERO_HASH,
            skills_root="6" * 64,
            registry_root=registry_root,
            policy_root=policy_root,
            actor_class="operator-agent",
            actor_identity="agent-live-platform",
            model_identity="deterministic-test",
            session_identity="session-live-platform",
            physical_executor="runner-live-platform",
            tool_identity="aegis_start_execution",
            workflow_identity="proof-carrying-platform-start",
            authority_domain="workflow:durable",
            requested_capability="mcp.execution.start",
            observed_authority="0.900000",
            approval_reference=approval_reference,
            input_digest=canonical_hash("AEGIS_OPERATOR_INTENT_V1", ACTION["objective"]),
            action_digest=ACTION_DIGEST,
            expected_pre_state=ABSENT_PRE_STATE,
            deterministic_nonce=NONCE,
        )
        approval = ApprovalGrant(
            reference=approval_reference,
            authority_domain="workflow:durable",
            action_class="D2",
            source_commit=source_commit,
            workspace_binding=workspace_binding,
            valid_through_generation=1,
            signature_root="7" * 64,
        )
        workspace = {
            "actual_cwd": str(REPO_ROOT),
            "remote_origin": REMOTE,
            "mutation_target": str(REPO_ROOT),
            "path_views": {},
        }
        bridge_url = f"http://127.0.0.1:{self.server.server_address[1]}"

        with patch.dict(
            os.environ,
            {
                "AEGIS_EXECUTION_IDENTITY_JSON": json.dumps(asdict(identity), sort_keys=True),
                "AEGIS_APPROVAL_GRANT_JSON": json.dumps(asdict(approval), sort_keys=True),
                "AEGIS_WORKSPACE_OBSERVATION_JSON": json.dumps(workspace, sort_keys=True),
            },
            clear=True,
        ):
            with self.assertRaisesRegex(
                ProofCarryingPlatformExecutionError,
                "INSUFFICIENT_VALIDATED_RUNS",
            ):
                execute_platform_start_from_environment(
                    action=ACTION,
                    bridge_url=bridge_url,
                    api_key="aegis_test",
                )

        self.assertEqual(0, self.fixture.post_count)
        self.assertEqual(0, self.fixture.get_count)


if __name__ == "__main__":
    main()
