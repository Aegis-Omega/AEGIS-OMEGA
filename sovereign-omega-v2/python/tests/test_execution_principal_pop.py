#!/usr/bin/env python3
"""Fail-closed execution-principal and runtime-PoP contract falsifiers.

The contract is intentionally provider-neutral. Vendor-specific mechanisms such as
Google Agent Identity or AWS AgentCore may produce evidence for this contract,
but their presence never makes provider output an authority source.
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.principal_binding import (  # noqa: E402
    BEARER_ONLY,
    DPOP_CERT_BOUND,
    MTLS_CERT_BOUND,
    MTLS_DPOP_CERT_BOUND,
    ON_BEHALF_OF_USER,
    RFC7523_JWT_GRANT,
    RFC8693_TOKEN_EXCHANGE,
    SELF_ACTING,
    VERIFIED,
    DelegationBinding,
    ExecutionPrincipalBinding,
    RuntimePoPVerification,
    canonical_hash,
    compute_task_action_binding,
    detect_credential_downgrade,
    evaluate_execution_principal,
)

HASH = "1" * 64
ACTION_DIGEST = canonical_hash("AEGIS_REQUESTED_ACTION_V1", {"operation": "send", "target": "calendar:event"})
TARGET_DIGEST = canonical_hash("AEGIS_AUTHORITY_TARGET_V1", "calendar:event")
SESSION = "session-1"
CAPABILITY = "external.calendar.write"
AGENT = "spiffe://aegis.example/agent/scheduler-1"
RUNTIME = "spiffe://aegis.example/runtime/gateway-7"
USER = "user:alice@example.test"
TASK_BINDING = compute_task_action_binding(
    session_identity=SESSION,
    action_digest=ACTION_DIGEST,
    requested_capability=CAPABILITY,
    target_digest=TARGET_DIGEST,
)


def pop(**changes) -> RuntimePoPVerification:
    values = dict(
        runtime_principal=RUNTIME,
        binding_mode=MTLS_DPOP_CERT_BOUND,
        verification_state=VERIFIED,
        verifier_identity="aegis:runtime-pop-verifier",
        proof_root="2" * 64,
        evidence_ref="evidence:runtime-pop:receipt-1",
        generation=7,
    )
    values.update(changes)
    return RuntimePoPVerification(**values)


def delegation(**changes) -> DelegationBinding:
    values = dict(
        user_principal=USER,
        agent_principal=AGENT,
        downstream_audience="https://calendar.example.test",
        requested_scopes=("calendar.events.write",),
        exchange_profile=RFC8693_TOKEN_EXCHANGE,
        authorization_server="https://issuer.example.test",
        verification_state=VERIFIED,
        evidence_root="3" * 64,
    )
    values.update(changes)
    return DelegationBinding(**values)


def binding(**changes) -> ExecutionPrincipalBinding:
    values = dict(
        schema_version="1.0.0",
        acting_mode=ON_BEHALF_OF_USER,
        user_principal=USER,
        agent_principal=AGENT,
        runtime_principal=RUNTIME,
        session_identity=SESSION,
        requested_capability=CAPABILITY,
        action_digest=ACTION_DIGEST,
        target_digest=TARGET_DIGEST,
        task_action_binding=TASK_BINDING,
        runtime_pop=pop(),
        delegation=delegation(),
    )
    values.update(changes)
    return ExecutionPrincipalBinding(**values)


def evaluate(value: ExecutionPrincipalBinding, *, action_class: str = "D3"):
    return evaluate_execution_principal(
        value,
        action_class=action_class,
        expected_agent_principal=AGENT,
        expected_runtime_principal=RUNTIME,
        expected_session_identity=SESSION,
        expected_action_digest=ACTION_DIGEST,
        expected_capability=CAPABILITY,
        expected_target_digest=TARGET_DIGEST,
    )


class ExecutionPrincipalPoPTests(TestCase):
    def assertDenied(self, decision, code: str) -> None:
        self.assertEqual(decision.outcome, "DENIED")
        self.assertIn(code, decision.denial_codes)
        self.assertFalse(decision.authority_granted)

    def test_01_three_layer_obo_pop_binding_validates_but_is_not_authority(self):
        decision = evaluate(binding())
        self.assertEqual(decision.outcome, "VALIDATED_BINDING_EVIDENCE")
        self.assertEqual(decision.denial_codes, ())
        self.assertFalse(decision.authority_granted)

    def test_02_agent_principal_is_required(self):
        self.assertDenied(evaluate(binding(agent_principal="NONE")), "AGENT_PRINCIPAL_MISSING")

    def test_03_runtime_principal_is_required(self):
        self.assertDenied(evaluate(binding(runtime_principal="NONE")), "RUNTIME_PRINCIPAL_MISSING")

    def test_04_runtime_principal_must_match_pop_subject(self):
        self.assertDenied(
            evaluate(binding(runtime_pop=pop(runtime_principal="spiffe://aegis.example/runtime/other"))),
            "RUNTIME_POP_SUBJECT_MISMATCH",
        )

    def test_05_runtime_principal_must_match_expected_executor(self):
        self.assertDenied(evaluate(binding(runtime_principal="spiffe://aegis.example/runtime/other")), "RUNTIME_PRINCIPAL_MISMATCH")

    def test_06_agent_principal_must_match_expected_agent(self):
        self.assertDenied(evaluate(binding(agent_principal="spiffe://aegis.example/agent/other")), "AGENT_PRINCIPAL_MISMATCH")

    def test_07_verified_runtime_pop_is_required_for_d3(self):
        self.assertDenied(evaluate(binding(runtime_pop=pop(verification_state="NOT_VERIFIED"))), "RUNTIME_POP_NOT_VERIFIED")

    def test_08_bearer_only_is_denied_for_consequential_execution(self):
        self.assertDenied(evaluate(binding(runtime_pop=pop(binding_mode=BEARER_ONLY))), "RUNTIME_POP_REQUIRED")

    def test_09_mtls_bound_is_accepted_as_pop_evidence(self):
        self.assertEqual(evaluate(binding(runtime_pop=pop(binding_mode=MTLS_CERT_BOUND))).outcome, "VALIDATED_BINDING_EVIDENCE")

    def test_10_dpop_bound_is_accepted_as_pop_evidence(self):
        self.assertEqual(evaluate(binding(runtime_pop=pop(binding_mode=DPOP_CERT_BOUND))).outcome, "VALIDATED_BINDING_EVIDENCE")

    def test_11_zero_or_malformed_pop_root_fails_closed(self):
        self.assertDenied(evaluate(binding(runtime_pop=pop(proof_root="0" * 64))), "RUNTIME_POP_PROOF_MISSING")
        self.assertDenied(evaluate(binding(runtime_pop=pop(proof_root="bad"))), "RUNTIME_POP_PROOF_INVALID")

    def test_12_action_binding_is_exact(self):
        self.assertDenied(evaluate(binding(action_digest="4" * 64)), "ACTION_DIGEST_MISMATCH")

    def test_13_capability_binding_is_exact(self):
        self.assertDenied(evaluate(binding(requested_capability="external.email.send")), "CAPABILITY_BINDING_MISMATCH")

    def test_14_target_binding_is_exact(self):
        self.assertDenied(evaluate(binding(target_digest="5" * 64)), "TARGET_BINDING_MISMATCH")

    def test_15_task_action_binding_is_recomputed_not_trusted(self):
        self.assertDenied(evaluate(binding(task_action_binding="6" * 64)), "TASK_ACTION_BINDING_MISMATCH")

    def test_16_obo_requires_user_principal(self):
        self.assertDenied(evaluate(binding(user_principal="NONE")), "USER_PRINCIPAL_MISSING")

    def test_17_obo_requires_delegation(self):
        self.assertDenied(evaluate(binding(delegation=None)), "DELEGATION_MISSING")

    def test_18_obo_delegation_binds_user_and_agent(self):
        self.assertDenied(evaluate(binding(delegation=delegation(user_principal="user:bob@example.test"))), "DELEGATION_USER_MISMATCH")
        self.assertDenied(evaluate(binding(delegation=delegation(agent_principal="spiffe://aegis.example/agent/other"))), "DELEGATION_AGENT_MISMATCH")

    def test_19_obo_requires_verified_delegation(self):
        self.assertDenied(evaluate(binding(delegation=delegation(verification_state="NOT_VERIFIED"))), "DELEGATION_NOT_VERIFIED")

    def test_20_obo_requires_downstream_audience_and_scope(self):
        self.assertDenied(evaluate(binding(delegation=delegation(downstream_audience="NONE"))), "DELEGATION_AUDIENCE_MISSING")
        self.assertDenied(evaluate(binding(delegation=delegation(requested_scopes=())), "DELEGATION_SCOPE_MISSING")

    def test_21_rfc8693_and_rfc7523_are_distinct_accepted_profiles(self):
        self.assertEqual(evaluate(binding(delegation=delegation(exchange_profile=RFC8693_TOKEN_EXCHANGE))).outcome, "VALIDATED_BINDING_EVIDENCE")
        self.assertEqual(evaluate(binding(delegation=delegation(exchange_profile=RFC7523_JWT_GRANT))).outcome, "VALIDATED_BINDING_EVIDENCE")

    def test_22_unknown_delegation_profile_fails_closed(self):
        self.assertDenied(evaluate(binding(delegation=delegation(exchange_profile="VENDOR_MAGIC"))), "DELEGATION_PROFILE_UNSUPPORTED")

    def test_23_self_acting_agent_does_not_inherit_user_authority(self):
        value = binding(acting_mode=SELF_ACTING, user_principal="NONE", delegation=None)
        decision = evaluate(value)
        self.assertEqual(decision.outcome, "VALIDATED_BINDING_EVIDENCE")
        self.assertFalse(decision.authority_granted)

    def test_24_self_acting_agent_rejects_ambient_user_delegation(self):
        value = binding(acting_mode=SELF_ACTING, user_principal=USER, delegation=delegation())
        self.assertDenied(evaluate(value), "SELF_ACTING_USER_AUTHORITY_PRESENT")

    def test_25_pop_to_bearer_is_security_relevant_downgrade(self):
        transition = detect_credential_downgrade(MTLS_DPOP_CERT_BOUND, BEARER_ONLY)
        self.assertTrue(transition.requires_new_admission)
        self.assertEqual(transition.classification, "SECURITY_RELEVANT_DOWNGRADE")

    def test_26_pop_to_pop_is_not_a_bearer_downgrade(self):
        transition = detect_credential_downgrade(MTLS_CERT_BOUND, DPOP_CERT_BOUND)
        self.assertFalse(transition.requires_new_admission)

    def test_27_unknown_binding_mode_fails_closed(self):
        self.assertDenied(evaluate(binding(runtime_pop=pop(binding_mode="UNKNOWN"))), "RUNTIME_POP_MODE_UNSUPPORTED")

    def test_28_deterministic_binding_and_decision_roots(self):
        first = binding()
        second = binding()
        self.assertEqual(first.root, second.root)
        self.assertEqual(evaluate(first), evaluate(second))

    def test_29_policy_file_locks_bearer_default_to_deny(self):
        policy = json.loads((REPO_ROOT / "harness/policies/principal-binding-policy.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["schema_version"], "1.0.0")
        self.assertEqual(policy["external_effect"]["bearer_mode"], "DENY")
        self.assertTrue(policy["external_effect"]["require_verified_runtime_pop"])
        self.assertTrue(policy["on_behalf_of_user"]["require_verified_delegation"])

    def test_30_both_authority_entrypoints_enforce_principal_preflight(self):
        authority_client = (REPO_ROOT / "harness/sdk/authority_client.py").read_text(encoding="utf-8")
        authority_cli = (REPO_ROOT / "scripts/automaton3-authority.py").read_text(encoding="utf-8")
        for source in (authority_client, authority_cli):
            self.assertIn("evaluate_execution_principal", source)
            self.assertIn("EXECUTION_PRINCIPAL", source)


if __name__ == "__main__":
    main()
