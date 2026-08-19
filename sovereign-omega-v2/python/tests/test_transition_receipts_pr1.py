#!/usr/bin/env python3
"""PR-1 falsification tests for transition binding and receipt separation."""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import (  # noqa: E402
    D2,
    SCHEMA_VERSION,
    ZERO_HASH,
    ExecutionIdentityEnvelope,
    MutationReceipt,
    canonical_hash,
    compute_workspace_binding,
    git_head,
    git_remote,
    load_capability_registry_from_commit,
    load_policy_from_commit,
)

HASHES = [f"{index:064x}" for index in range(1, 32)]
SIGNER_PRIVATE = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"


class TransitionReceiptPR1Tests(TestCase):
    def api(self):
        spec = importlib.util.find_spec("harness.sdk.transition_receipts")
        self.assertIsNotNone(spec, "PR-1 transition receipt API is not implemented")
        return importlib.import_module("harness.sdk.transition_receipts")

    def transition(self, **changes):
        api = self.api()
        values = dict(
            schema_version="1.0.0",
            source_commit="a" * 40,
            pre_state_commitment=HASHES[0],
            identity_root=HASHES[1],
            delegation_commitment=HASHES[2],
            capability_commitment=HASHES[3],
            action_digest=HASHES[4],
            deterministic_nonce="nonce-1",
            fence_commitment=HASHES[5],
            verifier_policy_commitment=HASHES[6],
            admission_policy_commitment=HASHES[7],
        )
        values.update(changes)
        return api.TransitionIdentity(**values)

    def decision(self, transition=None, outcome=None):
        api = self.api()
        transition = transition or self.transition()
        return api.DecisionReceipt(
            receipt_kind=api.DECISION_RECEIPT_KIND,
            transition_id=transition.root,
            decision_outcome=outcome or api.PERMIT,
            policy_decision_root=HASHES[8],
        )

    def execution(self, transition=None):
        api = self.api()
        transition = transition or self.transition()
        return api.ExecutionReceipt(
            receipt_kind=api.EXECUTION_RECEIPT_KIND,
            transition_id=transition.root,
            execution_instance_id="exec-1",
            outcome=api.EXECUTION_SUCCEEDED,
            result_digest=HASHES[9],
        )

    def terminal_receipt(self):
        """Real post-#264 terminal/provenance receipt; still never effect evidence."""
        return MutationReceipt(
            receipt_version=SCHEMA_VERSION,
            execution_identity_root=HASHES[1],
            workspace_binding=HASHES[2],
            policy_decision_root=HASHES[8],
            authority_receipt_root=HASHES[15],
            lease_authorization_receipt_root=HASHES[16],
            durable_execution_root=HASHES[17],
            authority_score="1.000000",
            authority_domain="github:contents",
            action_class=D2,
            tool="git",
            target=HASHES[3],
            pre_state_digest=ZERO_HASH,
            requested_action_digest=HASHES[4],
            result_digest=HASHES[9],
            post_state_digest=HASHES[10],
            parent_receipt=ZERO_HASH,
            sequence=0,
            outcome="SUCCEEDED",
            denial_code="NONE",
        )

    def test_terminal_succeeded_receipt_is_not_effect_evidence(self):
        api = self.api()
        self.assertFalse(api.accept_effect_evidence(self.terminal_receipt()))

    def test_decision_permit_does_not_imply_execution_success(self):
        api = self.api()
        receipt = self.decision(outcome=api.PERMIT)
        self.assertTrue(api.decision_satisfies_authority(receipt.decision_outcome))
        self.assertFalse(api.accept_effect_evidence(receipt))

    def test_execution_success_does_not_imply_effect_success(self):
        api = self.api()
        receipt = self.execution()
        self.assertEqual(receipt.outcome, api.EXECUTION_SUCCEEDED)
        self.assertFalse(api.accept_effect_evidence(receipt))

    def test_defer_routes_to_waiting_and_never_authorizes_execution(self):
        api = self.api()
        receipt = self.decision(outcome=api.DEFER)
        self.assertEqual(api.decision_route(receipt.decision_outcome), api.WAITING)
        self.assertFalse(api.decision_satisfies_authority(receipt.decision_outcome))
        self.assertFalse(api.decision_execution_allowed(receipt.decision_outcome))

    def test_cross_transition_decision_execution_splicing_fails(self):
        api = self.api()
        left = self.transition(deterministic_nonce="nonce-left")
        right = self.transition(deterministic_nonce="nonce-right")
        self.assertFalse(api.verify_transition_binding(left, self.decision(left), self.execution(right)))

    def test_transition_binding_rejects_wrong_action_digest(self):
        api = self.api()
        transition = self.transition()
        self.assertFalse(api.verify_transition_binding(replace(transition, action_digest=HASHES[11]), self.decision(transition)))

    def test_transition_binding_rejects_wrong_nonce(self):
        api = self.api()
        transition = self.transition()
        self.assertFalse(api.verify_transition_binding(replace(transition, deterministic_nonce="nonce-2"), self.decision(transition)))

    def test_transition_binding_rejects_wrong_fence(self):
        api = self.api()
        transition = self.transition()
        self.assertFalse(api.verify_transition_binding(replace(transition, fence_commitment=HASHES[12]), self.decision(transition)))

    def test_transition_binding_rejects_wrong_verifier_policy_commitment(self):
        api = self.api()
        transition = self.transition()
        self.assertFalse(api.verify_transition_binding(replace(transition, verifier_policy_commitment=HASHES[13]), self.decision(transition)))

    def test_transition_binding_rejects_wrong_admission_policy_commitment(self):
        api = self.api()
        transition = self.transition()
        self.assertFalse(api.verify_transition_binding(replace(transition, admission_policy_commitment=HASHES[14]), self.decision(transition)))

    def test_caller_cannot_construct_effect_receipt_from_post_state(self):
        api = self.api()
        self.assertFalse(hasattr(api, "make_effect_receipt"))
        with self.assertRaises(TypeError):
            api.EffectReceipt(
                receipt_kind=api.EFFECT_RECEIPT_KIND,
                transition_id=self.transition().root,
                execution_instance_id="exec-1",
                effect_witness_digest=HASHES[18],
                pre_state_commitment=HASHES[0],
                post_state_commitment=HASHES[19],
                observation_provenance=HASHES[20],
                adapter_identity="generic-caller",
                adapter_version="1",
            )
        with self.assertRaises(api.TransitionReceiptError):
            api.EffectReceipt().validate()

    def test_missing_effect_receipt_has_no_terminal_fallback(self):
        api = self.api()
        self.assertFalse(api.accept_effect_evidence(None))
        self.assertFalse(api.accept_effect_evidence(self.terminal_receipt()))

    def test_receipt_kind_is_nominal_and_const_bound(self):
        api = self.api()
        transition = self.transition()
        with self.assertRaises(ValueError):
            api.DecisionReceipt(
                receipt_kind=api.EXECUTION_RECEIPT_KIND,
                transition_id=transition.root,
                decision_outcome=api.PERMIT,
                policy_decision_root=HASHES[8],
            )

    def test_serialized_receipt_kinds_and_hash_domains_are_distinct(self):
        api = self.api()
        schema_expectations = {
            "decision-receipt.v1.schema.json": api.DECISION_RECEIPT_KIND,
            "execution-receipt.v1.schema.json": api.EXECUTION_RECEIPT_KIND,
            "effect-receipt.v1.schema.json": api.EFFECT_RECEIPT_KIND,
        }
        for filename, expected_kind in schema_expectations.items():
            schema = json.loads((REPO_ROOT / "schemas" / filename).read_text(encoding="utf-8"))
            self.assertEqual(schema["properties"]["receipt_kind"]["const"], expected_kind)
        payload = {"semantic_payload": "identical"}
        roots = {
            canonical_hash("AEGIS_DECISION_RECEIPT_V1", payload),
            canonical_hash("AEGIS_EXECUTION_RECEIPT_V1", payload),
            canonical_hash("AEGIS_EFFECT_RECEIPT_V1", payload),
        }
        self.assertEqual(len(roots), 3)

    def test_terminal_mutation_receipt_remains_reproducible(self):
        first = self.terminal_receipt()
        second = self.terminal_receipt()
        self.assertEqual(first.root, second.root)

    def test_authority_client_emits_signed_authority_and_separate_decision_receipt_but_no_effect_receipt(self):
        from harness.sdk.authority_client import authorize_from_environment

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
            branch_or_ref="refs/heads/pr5a-test",
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
            workflow_identity="pr5a-test",
            authority_domain="mcp:status",
            requested_capability="mcp.platform.status",
            observed_authority="0.000000",
            approval_reference=approval_reference,
            input_digest=canonical_hash("AEGIS_PR5A_TEST_INPUT_V1", {}),
            action_digest=canonical_hash("AEGIS_REQUESTED_ACTION_V1", action),
            expected_pre_state=ZERO_HASH,
            deterministic_nonce="nonce-client-pr5a",
        )
        workspace_observation = {
            "actual_cwd": str(REPO_ROOT),
            "remote_origin": remote,
            "mutation_target": str(REPO_ROOT),
            "path_views": {},
        }
        with patch.dict(
            "os.environ",
            {
                "AEGIS_EXECUTION_IDENTITY_JSON": json.dumps(identity.__dict__, sort_keys=True),
                "AEGIS_WORKSPACE_OBSERVATION_JSON": json.dumps(workspace_observation, sort_keys=True),
                "AEGIS_TRUSTED_OPERATOR_KEYS_JSON": "{}",
                "AEGIS_AUTHORITY_ISSUER_KEY_ID": "pr5a-test-authority",
                "AEGIS_AUTHORITY_SIGNING_KEY_HEX": SIGNER_PRIVATE,
            },
            clear=True,
        ):
            result = authorize_from_environment(
                action_class="D0",
                authority_domain="mcp:status",
                requested_capability="mcp.platform.status",
                tool="aegis_platform_status",
                target="platform",
                action=action,
            )
        self.assertEqual(result["outcome"], "ADMITTED")
        self.assertRegex(result["authority_receipt_root"], r"^[0-9a-f]{64}$")
        self.assertEqual(result["decision_receipt"]["receipt_kind"], "DECISION_RECEIPT_V1")
        self.assertEqual(result["decision_receipt"]["decision_outcome"], "PERMIT")
        self.assertEqual(result["transition_id"], result["decision_receipt"]["transition_id"])
        self.assertNotIn("mutation_receipt", result)
        self.assertNotIn("effect_receipt", result)


if __name__ == "__main__":
    main()
