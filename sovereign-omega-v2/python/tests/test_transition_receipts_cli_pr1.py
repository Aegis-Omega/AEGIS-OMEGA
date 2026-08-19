#!/usr/bin/env python3
"""PR-5A modernization of the PR-1 CLI receipt-separation falsifier.

The fixture preserves the PR-1 theorem under the stronger PR-264 commit-bound,
signed authority model; it does not reintroduce the old decision-derived
MutationReceipt producer whose name now belongs to a stronger terminal contract.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import (  # noqa: E402
    SCHEMA_VERSION,
    ZERO_HASH,
    ExecutionIdentityEnvelope,
    canonical_hash,
    compute_workspace_binding,
    git_head,
    git_remote,
    load_capability_registry_from_commit,
    load_policy_from_commit,
)

SIGNER_PRIVATE = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"


def load_cli_module():
    path = REPO_ROOT / "scripts" / "automaton3-authority.py"
    spec = importlib.util.spec_from_file_location("aegis_automaton3_authority_pr5a", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("AUTOMATON3_CLI_IMPORT_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TransitionReceiptCliPR1Tests(TestCase):
    def test_cli_emits_signed_authority_and_separate_decision_receipt_but_no_effect_receipt(self):
        cli = load_cli_module()
        action = {"operation": "status"}
        source_commit = git_head(REPO_ROOT)
        remote = git_remote(REPO_ROOT)
        _, policy_root = load_policy_from_commit(
            repository_root=REPO_ROOT,
            source_commit=source_commit,
            policy_path="harness/policies/consequence-policy.v1.json",
        )
        _, skills_root, registry_root = load_capability_registry_from_commit(
            repository_root=REPO_ROOT,
            source_commit=source_commit,
            skill_tree_path="harness/skill_tree.json",
            capability_map_path="harness/policies/capability-map.v1.json",
        )
        approval_reference = "approval-none"
        binding = compute_workspace_binding(
            repository_remote=remote,
            repository_root=".",
            project_identity="AEGIS-OMEGA",
            source_commit=source_commit,
            operator_authorization=approval_reference,
        )
        identity = ExecutionIdentityEnvelope(
            schema_version=SCHEMA_VERSION,
            repository_identity=remote,
            repository_root=".",
            source_commit=source_commit,
            branch_or_ref="refs/heads/pr5a-cli-test",
            project_identity="AEGIS-OMEGA",
            workspace_root=".",
            workspace_binding=binding,
            parent_state_root=ZERO_HASH,
            skills_root=skills_root,
            registry_root=registry_root,
            policy_root=policy_root,
            actor_class="operator-agent",
            actor_identity="agent-1",
            model_identity="model-1",
            session_identity="session-1",
            physical_executor="test-runner-1",
            tool_identity="aegis_platform_status",
            workflow_identity="pr5a-cli-test",
            authority_domain="mcp:status",
            requested_capability="mcp.platform.status",
            observed_authority="0.000000",
            approval_reference=approval_reference,
            input_digest=canonical_hash("AEGIS_PR5A_CLI_TEST_INPUT_V1", {}),
            action_digest=canonical_hash("AEGIS_REQUESTED_ACTION_V1", action),
            expected_pre_state=ZERO_HASH,
            deterministic_nonce="nonce-cli-pr5a",
        )
        payload = {
            "identity": identity.__dict__,
            "workspace": {
                "actual_cwd": str(REPO_ROOT),
                "remote_origin": remote,
                "mutation_target": str(REPO_ROOT),
            },
            "request": {
                "action_class": "D0",
                "authority_domain": "mcp:status",
                "requested_capability": "mcp.platform.status",
                "tool": "aegis_platform_status",
                "target": "platform",
                "workspace_mode": "READ_ONLY",
                "rollback_reference": "NONE",
                "idempotency_key": "pr5a-cli-status-0001",
            },
            "action": action,
        }
        with patch.dict(os.environ, {
            "AEGIS_TRUSTED_OPERATOR_KEYS_JSON": "{}",
            "AEGIS_AUTHORITY_ISSUER_KEY_ID": "pr5a-test-authority",
            "AEGIS_AUTHORITY_SIGNING_KEY_HEX": SIGNER_PRIVATE,
        }, clear=False):
            result = cli.evaluate(payload)
            second = cli.evaluate(payload)

        self.assertEqual(result["outcome"], "ADMITTED")
        self.assertRegex(result["authority_receipt_root"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["decision_receipt"]["receipt_kind"], "DECISION_RECEIPT_V1")
        self.assertEqual(result["decision_receipt"]["decision_outcome"], "PERMIT")
        self.assertEqual(result["transition_id"], result["decision_receipt"]["transition_id"])
        self.assertEqual(result["transition_id"], second["transition_id"])
        self.assertEqual(result["decision_receipt_root"], second["decision_receipt_root"])
        self.assertNotIn("mutation_receipt", result)
        self.assertNotIn("effect_receipt", result)
        self.assertNotIn("effect_receipt", second)


if __name__ == "__main__":
    main()
