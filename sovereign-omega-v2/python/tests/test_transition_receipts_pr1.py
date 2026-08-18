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
)

HASHES = [f"{index:064x}" for index in range(1, 20)]
COMMIT = "a" * 40
REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"


class TransitionReceiptPR1Tests(TestCase):
    def api(self):
        spec = importlib.util.find_spec("harness.sdk.transition_receipts")
        self.assertIsNotNone(spec, "PR-1 transition receipt API is not implemented")
        return importlib.import_module("harness.sdk.transition_receipts")

    def transition(self, **changes):
        api = self.api()
        values = dict(
            schema_version="1.0.0",
            source_commit=COMMIT,
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

    def legacy_receipt(self):
        return MutationReceipt(
            receipt_version=SCHEMA_VERSION,
            execution_identity_root=HASHES[1],
            workspace_binding=HASHES[2],
            policy_decision_root=HASHES[8],
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

    def test_legacy_succeeded_receipt_is_not_effect_evidence(self):
        api = self.api()
        self.assertFalse(api.accept_effect_evidence(self.legacy_receipt()))

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
                effect_witness_digest=HASHES[15],
                pre_state_commitment=HASHES[0],
                post_state_commitment=HASHES[16],
                observation_provenance=HASHES[17],
                adapter_identity="generic-caller",
                adapter_version="1",
            )

    def test_missing_effect_receipt_has_no_legacy_fallback(self):
        api = self.api()
        self.assertFalse(api.accept_effect_evidence(None))
        self.assertFalse(api.accept_effect_evidence(self.legacy_receipt()))

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

    def test_legacy_mutation_receipt_remains_reproducible(self):
        first = self.legacy_receipt()
        second = self.legacy_receipt()
        self.assertEqual(first.root, second.root)

    def test_authority_client_emits_decision_receipt_but_no_effect_receipt(self):
        from harness.sdk.authority_client import authorize_from_environment

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
            branch_or_ref="refs/heads/pr1-test",
            project_identity="AEGIS-OMEGA",
            workspace_root=".",
            workspace_binding=binding,
            parent_state_root=ZERO_HASH,
            skills_root=HASHES[1],
            registry_root=HASHES[2],
            policy_root=HASHES[3],
            actor_class="operator-agent",
            actor_identity="agent-1",
            model_identity="model-1",
            session_identity="session-1",
            physical_executor="test-runner-1",
            tool_identity="aegis_platform_status",
            workflow_identity="pr1-test",
            authority_domain="mcp:status",
            requested_capability="mcp.platform.status",
            observed_authority="0.000000",
            approval_reference=approval_reference,
            input_digest=canonical_hash("AEGIS_PR1_TEST_INPUT_V1", {}),
            action_digest=canonical_hash("AEGIS_REQUESTED_ACTION_V1", action),
            expected_pre_state=ZERO_HASH,
            deterministic_nonce="nonce-client-1",
        )
        with patch.dict(
            "os.environ",
            {"AEGIS_EXECUTION_IDENTITY_JSON": json.dumps(identity.__dict__, sort_keys=True)},
            clear=False,
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
        self.assertEqual(result["decision_receipt"]["receipt_kind"], "DECISION_RECEIPT_V1")
        self.assertEqual(result["decision_receipt"]["decision_outcome"], "PERMIT")
        self.assertEqual(result["transition_id"], result["decision_receipt"]["transition_id"])
        self.assertEqual(result["legacy_receipt_semantics"], "DECISION_DERIVED_NOT_EFFECT_PROOF")
        self.assertNotIn("effect_receipt", result)


if __name__ == "__main__":
    main()
