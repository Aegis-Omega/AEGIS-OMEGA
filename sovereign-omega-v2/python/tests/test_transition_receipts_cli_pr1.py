#!/usr/bin/env python3
"""PR-1 falsifier for the canonical Automaton-3 CLI receipt producer."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import (  # noqa: E402
    SCHEMA_VERSION,
    ZERO_HASH,
    ExecutionIdentityEnvelope,
    canonical_hash,
    compute_workspace_binding,
)

REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"
COMMIT = "a" * 40
HASH = "1" * 64


def load_cli_module():
    path = REPO_ROOT / "scripts" / "automaton3-authority.py"
    spec = importlib.util.spec_from_file_location("aegis_automaton3_authority_pr1", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AUTOMATON3_CLI_IMPORT_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransitionReceiptCliPR1Tests(TestCase):
    def test_cli_emits_decision_receipt_but_no_effect_receipt(self):
        cli = load_cli_module()
        action = {"operation": "status"}
        approval_reference = "approval-none"
        binding = compute_workspace_binding(
            repository_remote=REMOTE,
            repository_root=".",
            project_identity="AEGIS-OMEGA",
            source_commit=COMMIT,
            operator_authorization=approval_reference,
        )
        identity = ExecutionIdentityEnvelope(
            schema_version=SCHEMA_VERSION,
            repository_identity=REMOTE,
            repository_root=".",
            source_commit=COMMIT,
            branch_or_ref="refs/heads/pr1-cli-test",
            project_identity="AEGIS-OMEGA",
            workspace_root=".",
            workspace_binding=binding,
            parent_state_root=HASH,
            skills_root="2" * 64,
            registry_root="3" * 64,
            policy_root="4" * 64,
            actor_class="operator-agent",
            actor_identity="agent-1",
            model_identity="model-1",
            session_identity="session-1",
            physical_executor="test-runner-1",
            tool_identity="aegis_platform_status",
            workflow_identity="pr1-cli-test",
            authority_domain="mcp:status",
            requested_capability="mcp.platform.status",
            observed_authority="0.000000",
            approval_reference=approval_reference,
            input_digest=canonical_hash("AEGIS_PR1_CLI_TEST_INPUT_V1", {}),
            action_digest=canonical_hash("AEGIS_REQUESTED_ACTION_V1", action),
            expected_pre_state=ZERO_HASH,
            deterministic_nonce="nonce-cli-1",
        )
        payload = {
            "identity": identity.__dict__,
            "workspace": {
                "actual_cwd": str(REPO_ROOT),
                "remote_origin": REMOTE,
                "mutation_target": str(REPO_ROOT),
            },
            "request": {
                "action_class": "D0",
                "authority_domain": "mcp:status",
                "requested_capability": "mcp.platform.status",
                "tool": "aegis_platform_status",
                "target": "platform",
                "pre_state_digest": "6" * 64,
                "post_state_digest": "5" * 64,
            },
            "action": action,
        }
        result = cli.evaluate(payload)
        second_payload = {
            **payload,
            "request": {**payload["request"], "pre_state_digest": "7" * 64},
        }
        second = cli.evaluate(second_payload)

        self.assertEqual(result["outcome"], "ADMITTED")
        self.assertEqual(result["decision_receipt"]["receipt_kind"], "DECISION_RECEIPT_V1")
        self.assertEqual(result["decision_receipt"]["decision_outcome"], "PERMIT")
        self.assertEqual(result["transition_id"], result["decision_receipt"]["transition_id"])
        self.assertEqual(result["legacy_receipt_semantics"], "DECISION_DERIVED_NOT_EFFECT_PROOF")
        self.assertEqual(result["mutation_receipt"]["pre_state_digest"], "6" * 64)
        self.assertEqual(second["mutation_receipt"]["pre_state_digest"], "7" * 64)
        self.assertEqual(result["transition_id"], second["transition_id"])
        self.assertEqual(result["mutation_receipt"]["post_state_digest"], "5" * 64)
        self.assertNotIn("effect_receipt", result)
        self.assertNotIn("effect_receipt", second)


if __name__ == "__main__":
    main()
