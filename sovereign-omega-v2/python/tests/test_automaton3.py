#!/usr/bin/env python3
"""Automaton-3 authority abuse, replay, and determinism tests."""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import (  # noqa: E402
    ADMITTED, DENIED, D1, D2, D3, D4, SCHEMA_VERSION, ZERO_HASH,
    ApprovalGrant, AuthorityEvaluator, AuthorityRequest, CapabilityEvidence,
    DurableExecutionRecord, DurableExecutionRegistry, EventEnvelope,
    ExecutionIdentityEnvelope, MutationReceipt, ReceiptChain,
    SovereignExecutionError, WriterLeaseManager, canonical_bytes, canonical_hash,
    compute_skill_registry_root, compute_workspace_binding, load_capability_registry,
    load_capability_registry_from_commit, load_policy, load_policy_from_commit,
    make_authority_decision_receipt, make_terminal_mutation_receipt,
    verify_live_authority_roots, verify_workspace, _ed25519_sign,
)

REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"
COMMIT = "a" * 40
HASH = "1" * 64
POLICY = {
    "D0": {"minimum_validated_runs": 0, "approval": "NONE", "workspace": "READ_ONLY", "replay": False, "rollback": "NONE", "external_idempotency": False},
    "D1": {"minimum_validated_runs": 3, "approval": "NONE", "workspace": "REPOSITORY", "replay": True, "rollback": "REQUIRED", "external_idempotency": False},
    "D2": {"minimum_validated_runs": 3, "approval": "EXPLICIT", "workspace": "REPOSITORY", "replay": True, "rollback": "REQUIRED", "external_idempotency": False},
    "D3": {"minimum_validated_runs": 3, "approval": "EXPLICIT", "workspace": "REPOSITORY", "replay": True, "rollback": "COMPENSATION_OR_IDEMPOTENCY", "external_idempotency": True},
    "D4": {"minimum_validated_runs": 3, "approval": "EXPLICIT", "workspace": "REPOSITORY", "replay": True, "rollback": "COMPENSATION_OR_IDEMPOTENCY", "external_idempotency": True},
}


class Automaton3Tests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for rel in ("CONSTITUTIONAL_DECLARATION.md", ".claude.json", "skill-hashes.sha256", "docs/claims.json", "evidence/run.json"):
            path = self.root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text("{}\n", encoding="utf-8")
        self.approval_ref = "approval-1"
        self.binding = compute_workspace_binding(repository_remote=REMOTE, repository_root=".", project_identity="AEGIS-OMEGA", source_commit=COMMIT, operator_authorization=self.approval_ref)
        self.registry_root = "2" * 64
        self.policy_root = canonical_hash("AEGIS_CONSEQUENCE_POLICY_V1", POLICY)
        self.operator_key_id = "operator-test-key"
        self.operator_private_key = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
        self.operator_public_key = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
        self.authority_key_id = "authority-test-key"
        self.authority_private_key = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
        self.authority_public_key = "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
        self.identity = self.make_identity()
        self.capability = CapabilityEvidence(
            capability="repository.mutate", skill_id="gate8_deployment_gate", observation_state="OBSERVED",
            validated_runs=3, confidence_micros=900_000, recency_micros=900_000, failure_rate_micros=0,
            evidence_refs=("evidence/run.json",), allowed_action_classes=(D1, D2, D4), allowed_tools=("git",),
        )
        self.evaluator = AuthorityEvaluator(
            policy=POLICY,
            registry={"repository.mutate": self.capability},
            repository_root=self.root,
            trusted_operator_keys={self.operator_key_id: self.operator_public_key},
            allow_working_tree_evidence_for_tests=True,
        )

    def make_identity(self, **changes) -> ExecutionIdentityEnvelope:
        action = {"operation": "write", "target": "docs/test.md"}
        values = dict(
            schema_version=SCHEMA_VERSION, repository_identity=REMOTE, repository_root=".", source_commit=COMMIT,
            branch_or_ref="refs/heads/test", project_identity="AEGIS-OMEGA", workspace_root=".", workspace_binding=self.binding,
            parent_state_root=HASH, skills_root="3"*64, registry_root=self.registry_root, policy_root=self.policy_root,
            actor_class="operator-agent", actor_identity="agent-1", model_identity="model-1", session_identity="session-1",
            physical_executor="github-runner-1", tool_identity="git", workflow_identity="workflow-1", authority_domain="github:contents",
            requested_capability="repository.mutate", observed_authority="0.810000", approval_reference=self.approval_ref,
            input_digest=canonical_hash("INPUT", {}), action_digest=canonical_hash("AEGIS_REQUESTED_ACTION_V1", action),
            expected_pre_state=ZERO_HASH, deterministic_nonce="nonce-1",
        )
        values.update(changes)
        return ExecutionIdentityEnvelope(**values)

    def request(self, **changes) -> AuthorityRequest:
        values = dict(action_class=D2, authority_domain="github:contents", requested_capability="repository.mutate", tool="git",
                      target="docs/test.md", identity_root=self.identity.root, workspace_binding=self.binding, source_commit=COMMIT,
                      registry_root=self.registry_root, policy_root=self.policy_root,
                      action_digest=self.identity.action_digest, expected_pre_state=self.identity.expected_pre_state,
                      workspace_mode="REPOSITORY", current_generation=1,
                      approval_reference=self.approval_ref, rollback_reference="rollback:test")
        values.update(changes)
        return AuthorityRequest(**values)

    def approval(self, **changes) -> ApprovalGrant:
        request = self.request()
        values = dict(schema_version=SCHEMA_VERSION, reference=self.approval_ref, issuer_key_id=self.operator_key_id,
                      operator_identity="operator:test", authority_domain="github:contents", action_class=D2, source_commit=COMMIT,
                      workspace_binding=self.binding, policy_root=self.policy_root, registry_root=self.registry_root,
                      identity_root=self.identity.root, action_digest=self.identity.action_digest,
                      target_digest=canonical_hash("AEGIS_AUTHORITY_TARGET_V1", request.target),
                      requested_capability=request.requested_capability, valid_through_generation=2, state="APPROVED")
        values.update(changes)
        signature = _ed25519_sign(private_key_hex=self.operator_private_key, domain="AEGIS_APPROVAL_GRANT_V1", value=values)
        return ApprovalGrant(**values, signature=signature)

    def assertDenied(self, decision, code: str) -> None:
        self.assertEqual(decision.outcome, DENIED); self.assertEqual(decision.authority_score, "0.000000"); self.assertIn(code, decision.denial_codes)

    def test_01_unknown_coordinator_capability(self):
        self.assertDenied(self.evaluator.evaluate(self.request(requested_capability="unknown"), approval=self.approval()), "UNMAPPED_CAPABILITY")

    def test_02_unobserved_skill(self):
        ev = replace(self.capability, observation_state="UNOBSERVED")
        self.assertDenied(AuthorityEvaluator(policy=POLICY, registry={"repository.mutate": ev}, repository_root=self.root).evaluate(self.request(), approval=self.approval()), "UNOBSERVED_CAPABILITY")

    def test_03_two_runs(self):
        ev = replace(self.capability, validated_runs=2)
        self.assertDenied(AuthorityEvaluator(policy=POLICY, registry={"repository.mutate": ev}, repository_root=self.root).evaluate(self.request(), approval=self.approval()), "INSUFFICIENT_VALIDATED_RUNS")

    def test_04_documentation_only_prior(self):
        ev = replace(self.capability, observation_state="UNOBSERVED", validated_runs=0, confidence_micros=950_000)
        self.assertDenied(AuthorityEvaluator(policy=POLICY, registry={"repository.mutate": ev}, repository_root=self.root).evaluate(self.request(), approval=self.approval()), "OPERATIONAL_AUTHORITY_REQUIRES_THREE_RUNS")

    def test_05_malformed_evidence(self):
        ev = replace(self.capability, evidence_refs=())
        self.assertDenied(AuthorityEvaluator(policy=POLICY, registry={"repository.mutate": ev}, repository_root=self.root).evaluate(self.request(), approval=self.approval()), "EVIDENCE_MISSING")

    def test_06_evidence_outside_repository(self):
        ev = replace(self.capability, evidence_refs=("../escape",))
        self.assertDenied(AuthorityEvaluator(policy=POLICY, registry={"repository.mutate": ev}, repository_root=self.root).evaluate(self.request(), approval=self.approval()), "EVIDENCE_OUTSIDE_REPOSITORY")
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "tracked.txt"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=AEGIS Test", "-c", "user.email=aegis@example.invalid", "commit", "-qm", "evidence baseline"],
            check=True,
        )
        source_commit = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
        ).stdout.strip()
        self.assertTrue((self.root / "evidence" / "run.json").is_file())
        decision = AuthorityEvaluator(
            policy=POLICY,
            registry={"repository.mutate": self.capability},
            repository_root=self.root,
            trusted_operator_keys={self.operator_key_id: self.operator_public_key},
        ).evaluate(self.request(source_commit=source_commit), approval=self.approval())
        self.assertDenied(decision, "EVIDENCE_UNRESOLVED")

    def test_07_mismatched_source_commit(self):
        self.assertDenied(self.evaluator.evaluate(self.request(source_commit="b"*40), approval=self.approval()), "APPROVAL_SOURCE_COMMIT_MISMATCH")

    def test_08_mismatched_skills_root(self):
        with self.assertRaisesRegex(SovereignExecutionError, "skills_root:INVALID_SHA256"):
            self.make_identity(skills_root="bad").root
        registry_dir = self.root / "harness"
        policy_dir = registry_dir / "policies"
        policy_dir.mkdir(parents=True)
        tree = {
            "schema_version": "2.0.0",
            "skills": [{
                "skill_id": "gate8_deployment_gate",
                "observation_state": "OBSERVED",
                "validated_runs": 3,
                "confidence": 0.9,
                "recency_score": 0.9,
                "failure_rate": 0.0,
                "evidence_refs": ["evidence/run.json"],
            }],
        }
        committed_skills_root = compute_skill_registry_root(tree)
        tree.update(registry_root=committed_skills_root, genesis_seal=committed_skills_root)
        capability_map = {
            "schema_version": SCHEMA_VERSION,
            "capabilities": {
                "repository.mutate": {
                    "skill_id": "gate8_deployment_gate",
                    "allowed_action_classes": [D2],
                    "allowed_tools": ["git"],
                },
            },
        }
        consequence_policy = {"schema_version": SCHEMA_VERSION, "classes": POLICY}
        skill_path = registry_dir / "skill_tree.json"
        map_path = policy_dir / "capability-map.v1.json"
        policy_path = policy_dir / "consequence-policy.v1.json"
        for path, value in ((skill_path, tree), (map_path, capability_map), (policy_path, consequence_policy)):
            path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "harness"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=AEGIS Test", "-c", "user.email=aegis@example.invalid", "commit", "-qm", "registry baseline"],
            check=True,
        )
        source_commit = subprocess.run(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True,
        ).stdout.strip()
        _, live_skills_root, live_registry_root = load_capability_registry_from_commit(
            repository_root=self.root,
            source_commit=source_commit,
            skill_tree_path="harness/skill_tree.json",
            capability_map_path="harness/policies/capability-map.v1.json",
        )
        _, live_policy_root = load_policy_from_commit(
            repository_root=self.root,
            source_commit=source_commit,
            policy_path="harness/policies/consequence-policy.v1.json",
        )
        self.assertEqual(live_skills_root, committed_skills_root)

        dirty_policy = json.loads(json.dumps(consequence_policy))
        dirty_policy["classes"]["D0"]["minimum_validated_runs"] = 999
        policy_path.write_text(json.dumps(dirty_policy, sort_keys=True), encoding="utf-8")
        _, dirty_policy_root = load_policy(policy_path)
        self.assertNotEqual(dirty_policy_root, live_policy_root)
        with self.assertRaisesRegex(SovereignExecutionError, "POLICY_ROOT_MISMATCH"):
            verify_live_authority_roots(
                self.make_identity(
                    skills_root=live_skills_root,
                    registry_root=live_registry_root,
                    policy_root=dirty_policy_root,
                ),
                skills_root=live_skills_root,
                registry_root=live_registry_root,
                policy_root=live_policy_root,
            )
        _, reloaded_policy_root = load_policy_from_commit(
            repository_root=self.root,
            source_commit=source_commit,
            policy_path="harness/policies/consequence-policy.v1.json",
        )
        self.assertEqual(reloaded_policy_root, live_policy_root)

        capability_map["capabilities"]["repository.mutate"]["allowed_tools"] = ["github"]
        map_path.write_text(json.dumps(capability_map, sort_keys=True), encoding="utf-8")
        _, dirty_map_skills_root, dirty_map_registry_root = load_capability_registry(
            repository_root=self.root,
            skill_tree_path=skill_path,
            capability_map_path=map_path,
        )
        self.assertEqual(dirty_map_skills_root, live_skills_root)
        self.assertNotEqual(dirty_map_registry_root, live_registry_root)
        dirty_map_identity = self.make_identity(
            skills_root=dirty_map_skills_root,
            registry_root=dirty_map_registry_root,
            policy_root=live_policy_root,
        )
        with self.assertRaisesRegex(SovereignExecutionError, "CAPABILITY_REGISTRY_ROOT_MISMATCH"):
            verify_live_authority_roots(
                dirty_map_identity,
                skills_root=live_skills_root,
                registry_root=live_registry_root,
                policy_root=live_policy_root,
            )

        tree["skills"][0]["confidence"] = 0.8
        dirty_skills_root = compute_skill_registry_root(tree)
        tree.update(registry_root=dirty_skills_root, genesis_seal=dirty_skills_root)
        skill_path.write_text(json.dumps(tree, sort_keys=True), encoding="utf-8")
        _, dirty_tree_skills_root, dirty_tree_registry_root = load_capability_registry(
            repository_root=self.root,
            skill_tree_path=skill_path,
            capability_map_path=map_path,
        )
        self.assertNotEqual(dirty_tree_skills_root, live_skills_root)
        dirty_tree_identity = self.make_identity(
            skills_root=dirty_tree_skills_root,
            registry_root=dirty_tree_registry_root,
            policy_root=live_policy_root,
        )
        with self.assertRaisesRegex(SovereignExecutionError, "SKILLS_ROOT_MISMATCH"):
            verify_live_authority_roots(
                dirty_tree_identity,
                skills_root=live_skills_root,
                registry_root=live_registry_root,
                policy_root=live_policy_root,
            )

        # The commit-bound loader remains anchored even while both checkout files are dirty.
        _, reloaded_skills_root, reloaded_registry_root = load_capability_registry_from_commit(
            repository_root=self.root,
            source_commit=source_commit,
            skill_tree_path="harness/skill_tree.json",
            capability_map_path="harness/policies/capability-map.v1.json",
        )
        self.assertEqual((reloaded_skills_root, reloaded_registry_root), (live_skills_root, live_registry_root))

    def test_09_mismatched_parent_state(self):
        with self.assertRaisesRegex(SovereignExecutionError, "parent_state_root:INVALID_SHA256"):
            self.make_identity(parent_state_root="bad").root

    def test_10_mismatched_workspace(self):
        self.assertDenied(self.evaluator.evaluate(self.request(workspace_binding="9"*64), approval=self.approval()), "APPROVAL_WORKSPACE_MISMATCH")

    def test_11_nested_unrelated_project(self):
        nested = self.root / "nested"; nested.mkdir(); (nested / ".git").mkdir(); target = nested / "x"; target.write_text("x")
        decision = verify_workspace(declared_root=self.root, cwd=self.root, expected_remote=REMOTE, actual_remote=REMOTE, project_identity="AEGIS-OMEGA", source_commit=COMMIT, operator_authorization=self.approval_ref, mutation_target=target)
        self.assertIn("NESTED_REPOSITORY_REQUIRES_EXPLICIT_TARGET", decision.denial_codes)

    def test_12_stale_writer_lease(self):
        manager = WriterLeaseManager(); lease, _ = manager.acquire(authority_domain="git", holder_identity_root=HASH, source_commit=COMMIT, expected_parent_state=ZERO_HASH)
        self.assertIsNotNone(lease)
        receipt = manager.authorize_write(authority_domain="git", holder_identity_root=HASH, fencing_token="9"*64, lease_generation=lease.lease_generation, expected_parent_state=ZERO_HASH, action_digest="8"*64)
        self.assertIn("STALE_FENCING_TOKEN", receipt.denial_codes)

    def test_13_replayed_fencing_token(self):
        manager = WriterLeaseManager(); lease, _ = manager.acquire(authority_domain="git", holder_identity_root=HASH, source_commit=COMMIT, expected_parent_state=ZERO_HASH)
        kwargs=dict(authority_domain="git", holder_identity_root=HASH, fencing_token=lease.fencing_token, lease_generation=lease.lease_generation, expected_parent_state=ZERO_HASH, action_digest="8"*64)
        first = manager.authorize_write(**kwargs)
        second = manager.authorize_write(**kwargs)
        self.assertEqual(first.outcome, ADMITTED)
        self.assertEqual(first, second)

    def durable(self):
        manager=WriterLeaseManager(); lease,_=manager.acquire(authority_domain="external", holder_identity_root=HASH, source_commit=COMMIT, expected_parent_state=ZERO_HASH)
        registry=DurableExecutionRegistry(manager)
        record=DurableExecutionRecord("wf","operator",COMMIT,self.binding,"plan",("external",),0,"",0,None,"ACTIVE",HASH,ZERO_HASH,ZERO_HASH,"","PLANNED",0)
        registry.register("exec",record); registry.transition("exec",status="ADMITTED",phase="admitted",transition_sequence=1,receipt_root=HASH); registry.transition("exec",status="RUNNING",phase="execute",transition_sequence=2,receipt_root="2"*64)
        return manager,registry,lease

    def authority_receipt(self, decision, request=None):
        request = request or self.request()
        return make_authority_decision_receipt(
            identity=self.identity,
            request=request,
            decision=decision,
            evaluator=self.evaluator,
            issuer_key_id=self.authority_key_id,
            issuer_private_key_hex=self.authority_private_key,
        )

    def terminal_context(self):
        request = self.request()
        decision = self.evaluator.evaluate(request, approval=self.approval())
        authority_receipt = self.authority_receipt(decision, request)
        manager = WriterLeaseManager()
        lease, _ = manager.acquire(
            authority_domain=request.authority_domain,
            holder_identity_root=self.identity.root,
            source_commit=COMMIT,
            expected_parent_state=self.identity.expected_pre_state,
        )
        self.assertIsNotNone(lease)
        lease_receipt = manager.authorize_write(
            authority_domain=request.authority_domain,
            holder_identity_root=self.identity.root,
            fencing_token=lease.fencing_token,
            lease_generation=lease.lease_generation,
            expected_parent_state=self.identity.expected_pre_state,
            action_digest=self.identity.action_digest,
        )
        registry = DurableExecutionRegistry(manager)
        registry.register("terminal-exec", DurableExecutionRecord(
            "terminal-workflow", "operator", COMMIT, self.binding, "plan",
            (request.authority_domain,), 0, "", 0, None, "ACTIVE",
            self.identity.root, self.identity.expected_pre_state, ZERO_HASH, "", "PLANNED", 0,
        ))
        registry.transition("terminal-exec", status="ADMITTED", phase="admitted", transition_sequence=1, receipt_root=authority_receipt.root)
        registry.transition("terminal-exec", status="RUNNING", phase="execute", transition_sequence=2, receipt_root=lease_receipt.receipt_root)
        return request, decision, authority_receipt, manager, lease_receipt, registry, ReceiptChain()

    def terminal_receipt(self, *, terminal_outcome="SUCCEEDED", denial_code="NONE", post_state_digest="8" * 64, result=None):
        context = self.terminal_context()
        receipt = self.commit_terminal_context(
            context,
            terminal_outcome=terminal_outcome,
            denial_code=denial_code,
            post_state_digest=post_state_digest,
            result=result,
        )
        return receipt, context[5], context[6]

    def commit_terminal_context(self, context, *, terminal_outcome="SUCCEEDED", denial_code="NONE", post_state_digest="8" * 64, result=None):
        request, decision, authority_receipt, manager, lease_receipt, registry, chain = context
        if terminal_outcome != "SUCCEEDED":
            post_state_digest = self.identity.expected_pre_state
        receipt = make_terminal_mutation_receipt(
            identity=self.identity,
            request=request,
            decision=decision,
            evaluator=self.evaluator,
            authority_receipt=authority_receipt,
            trusted_authority_keys={self.authority_key_id: self.authority_public_key},
            lease_manager=manager,
            lease_authorization_receipt=lease_receipt,
            durable_registry=registry,
            execution_id="terminal-exec",
            receipt_chain=chain,
            result=result or {"status": terminal_outcome.lower()},
            post_state_digest=post_state_digest,
            terminal_outcome=terminal_outcome,
            denial_code=denial_code,
        )
        return receipt

    def test_signed_approval_tamper_denied(self):
        approval = replace(self.approval(), signature="00" * 64)
        self.assertDenied(self.evaluator.evaluate(self.request(), approval=approval), "APPROVAL_SIGNATURE_INVALID")

    def test_d2_missing_rollback_denied(self):
        self.assertDenied(
            self.evaluator.evaluate(self.request(rollback_reference="NONE"), approval=self.approval()),
            "ROLLBACK_REFERENCE_REQUIRED",
        )

    def test_terminal_rejects_revoked_lease_without_state_change(self):
        context = self.terminal_context()
        manager, registry, chain = context[3], context[5], context[6]
        manager.revoke(self.request().authority_domain, self.identity.root)
        with self.assertRaisesRegex(SovereignExecutionError, "LEASE_NO_LONGER_CURRENT"):
            self.commit_terminal_context(context)
        self.assertEqual(registry.get("terminal-exec").status, "RUNNING")
        self.assertEqual(chain.verify(), ZERO_HASH)

    def test_terminal_consumes_authorization_once_and_revokes_writer(self):
        context = self.terminal_context()
        receipt = self.commit_terminal_context(context)
        manager, lease_receipt = context[3], context[4]
        self.assertIsNone(manager.current(self.request().authority_domain))
        with self.assertRaisesRegex(SovereignExecutionError, "LEASE_AUTHORIZATION_ALREADY_CONSUMED"):
            manager.consume_authorization(lease_receipt)
        self.assertRegex(receipt.root, r"^[0-9a-f]{64}$")

    def test_durable_terminal_states_cannot_resurrect_or_cancel(self):
        receipt, registry, _ = self.terminal_receipt()
        with self.assertRaisesRegex(SovereignExecutionError, "DURABLE_TERMINAL_STATE"):
            registry.transition("terminal-exec", status="RUNNING", phase="resurrect", transition_sequence=4, receipt_root=receipt.root)
        with self.assertRaisesRegex(SovereignExecutionError, "DURABLE_TERMINAL_STATE"):
            registry.cancel("terminal-exec")

    def test_public_transition_cannot_commit_arbitrary_terminal_receipt(self):
        context = self.terminal_context()
        registry = context[5]
        with self.assertRaisesRegex(SovereignExecutionError, "DURABLE_TERMINAL_COMMIT_REQUIRED"):
            registry.transition(
                "terminal-exec",
                status="COMPLETED",
                phase="completed",
                transition_sequence=3,
                receipt_root="f" * 64,
            )
        record = registry.get("terminal-exec")
        self.assertEqual(record.status, "RUNNING")
        self.assertEqual(record.current_receipt_root, context[4].receipt_root)

    def test_private_terminal_transition_rejects_untrusted_capability(self):
        context = self.terminal_context()
        registry = context[5]
        with self.assertRaisesRegex(SovereignExecutionError, "DURABLE_TERMINAL_COMMIT_CAPABILITY_INVALID"):
            registry._commit_terminal_transition(
                "terminal-exec",
                status="COMPLETED",
                phase="completed",
                transition_sequence=3,
                receipt=object(),
                commit_capability=object(),
            )
        self.assertEqual(registry.get("terminal-exec").status, "RUNNING")

    def test_14_duplicate_external_action(self):
        _, registry, _ = self.durable(); registry.claim_external_action("exec","idempotency-1")
        with self.assertRaisesRegex(SovereignExecutionError,"DUPLICATE_EXTERNAL_ACTION"): registry.claim_external_action("exec","idempotency-1")

    def test_15_replay_after_side_effect(self): self.test_14_duplicate_external_action()

    def test_16_orphaned_workflow(self):
        _,registry,_=self.durable(); registry.heartbeat("exec",1); registry.mark_orphaned("exec",10,3); self.assertEqual(registry.get("exec").status,"ORPHANED")

    def test_17_missing_approval(self): self.assertDenied(self.evaluator.evaluate(self.request()),"APPROVAL_MISSING")
    def test_18_expired_approval(self): self.assertDenied(self.evaluator.evaluate(self.request(current_generation=3),approval=self.approval(valid_through_generation=2)),"APPROVAL_EXPIRED")
    def test_19_wrong_domain_approval(self): self.assertDenied(self.evaluator.evaluate(self.request(),approval=self.approval(authority_domain="dns")),"APPROVAL_DOMAIN_MISMATCH")

    def test_20_path_disagreement(self):
        decision=verify_workspace(declared_root=self.root,cwd=self.root,expected_remote=REMOTE,actual_remote=REMOTE,project_identity="AEGIS-OMEGA",source_commit=COMMIT,operator_authorization=self.approval_ref,mutation_target=self.root/"docs",path_views={"powershell":"C:\\repo","wsl":"/mnt/d/repo"})
        self.assertIn("PATH_VIEW_DISAGREEMENT",decision.denial_codes)

    def test_21_unicode_normalization_ambiguity(self):
        with self.assertRaisesRegex(SovereignExecutionError,"UNICODE_OR_CONTROL_AMBIGUITY"): self.make_identity(actor_identity="e\u0301").root

    def test_22_ansi_control_contamination(self):
        with self.assertRaisesRegex(SovereignExecutionError,"UNICODE_OR_CONTROL_AMBIGUITY"): self.make_identity(actor_identity="agent\x1b[31m").root

    def test_23_symbol_encoded_authority_bypass(self):
        with self.assertRaisesRegex(SovereignExecutionError,"UNSAFE_CHARACTERS"): self.make_identity(requested_capability="repository.mutate⚠").root

    def test_24_missing_constitutional_file(self):
        (self.root/".claude.json").unlink()
        decision=verify_workspace(declared_root=self.root,cwd=self.root,expected_remote=REMOTE,actual_remote=REMOTE,project_identity="AEGIS-OMEGA",source_commit=COMMIT,operator_authorization=self.approval_ref,mutation_target=self.root)
        self.assertIn("REQUIRED_FILE_MISSING:.claude.json",decision.denial_codes)

    def test_25_empty_directory_false_success(self):
        empty=self.root/"empty"; empty.mkdir()
        decision=verify_workspace(declared_root=empty,cwd=empty,expected_remote=REMOTE,actual_remote=REMOTE,project_identity="AEGIS-OMEGA",source_commit=COMMIT,operator_authorization=self.approval_ref,mutation_target=empty,required_files=())
        self.assertIn("EMPTY_WORKSPACE",decision.denial_codes)

    def test_26_hook_failure(self): self.assertDenied(AuthorityEvaluator(policy=None,registry={}).evaluate(self.request()),"AUTHORITY_SERVICE_UNAVAILABLE")
    def test_27_authority_service_unavailable(self): self.test_26_hook_failure()
    def test_28_registry_unavailable(self): self.assertDenied(AuthorityEvaluator(policy=POLICY,registry=None).evaluate(self.request()),"REGISTRY_UNAVAILABLE")

    def test_29_receipt_chain_break(self):
        chain=ReceiptChain(); base=dict(receipt_version=SCHEMA_VERSION,execution_identity_root=HASH,workspace_binding=self.binding,policy_decision_root="2"*64,authority_receipt_root="7"*64,lease_authorization_receipt_root="8"*64,durable_execution_root="9"*64,authority_score="0.000000",authority_domain="git",action_class=D2,tool="git",target="3"*64,pre_state_digest=ZERO_HASH,requested_action_digest="4"*64,result_digest="5"*64,post_state_digest="6"*64,outcome="SUCCEEDED",denial_code="NONE")
        first=MutationReceipt(**base,parent_receipt=ZERO_HASH,sequence=0); chain.append(first)
        with self.assertRaisesRegex(SovereignExecutionError,"RECEIPT_CHAIN_PARENT_BREAK"): chain.append(MutationReceipt(**base,parent_receipt=ZERO_HASH,sequence=1))

    def test_authority_admission_is_not_terminal_success(self):
        decision = self.evaluator.evaluate(self.request(), approval=self.approval())
        receipt = self.authority_receipt(decision)
        self.assertEqual(receipt.outcome, ADMITTED)
        self.assertEqual(receipt.skills_root, self.identity.skills_root)
        receipt.verify_signature({self.authority_key_id: self.authority_public_key})
        with self.assertRaisesRegex(SovereignExecutionError, "AUTHORITY_RECEIPT_SIGNATURE_INVALID"):
            replace(receipt, skills_root="4" * 64).verify_signature({self.authority_key_id: self.authority_public_key})
        self.assertFalse(hasattr(receipt, "pre_state_digest"))
        self.assertFalse(hasattr(receipt, "post_state_digest"))
        self.assertRegex(receipt.root, r"^[0-9a-f]{64}$")

    def test_authority_denial_remains_an_authority_receipt(self):
        decision = self.evaluator.evaluate(self.request(), approval=None)
        receipt = self.authority_receipt(decision)
        self.assertEqual(receipt.outcome, DENIED)
        self.assertIn("APPROVAL_MISSING", receipt.denial_codes)

    def test_terminal_receipt_requires_admission_and_explicit_outcome(self):
        terminal, registry, chain = self.terminal_receipt(terminal_outcome="FAILED", denial_code="EXECUTOR_FAILED")
        self.assertEqual(terminal.outcome, "FAILED")
        self.assertEqual(registry.get("terminal-exec").current_receipt_root, terminal.root)
        self.assertEqual(chain.verify(), terminal.root)
        denied = self.evaluator.evaluate(self.request(), approval=None)
        request, _, authority_receipt, manager, lease_receipt, registry, chain = self.terminal_context()
        with self.assertRaisesRegex(SovereignExecutionError, "TERMINAL_RECEIPT_REQUIRES_ADMITTED_AUTHORITY"):
            make_terminal_mutation_receipt(
                identity=self.identity,
                request=request,
                decision=denied,
                evaluator=self.evaluator,
                authority_receipt=authority_receipt,
                trusted_authority_keys={self.authority_key_id: self.authority_public_key},
                lease_manager=manager,
                lease_authorization_receipt=lease_receipt,
                durable_registry=registry,
                execution_id="terminal-exec",
                receipt_chain=chain,
                result={},
                post_state_digest=self.identity.expected_pre_state,
                terminal_outcome="SUCCEEDED",
            )

    def test_authority_receipt_rejects_score_above_one(self):
        decision = self.evaluator.evaluate(self.request(), approval=self.approval())
        receipt = self.authority_receipt(decision)
        with self.assertRaisesRegex(SovereignExecutionError, "AUTHORITY_RECEIPT_SCORE_INVALID"):
            replace(receipt, authority_score="1.999999").validate()

    def test_mutation_receipt_rejects_invalid_action_metadata(self):
        terminal, _, _ = self.terminal_receipt()
        with self.assertRaisesRegex(SovereignExecutionError, "RECEIPT_ACTION_CLASS_INVALID"):
            replace(terminal, action_class="D9").validate()

    def test_terminal_failure_requires_outcome_code(self):
        with self.assertRaisesRegex(SovereignExecutionError, "TERMINAL_OUTCOME_CODE_REQUIRED"):
            self.terminal_receipt(terminal_outcome="FAILED")

    def test_30_cancellation_during_retry(self):
        manager,registry,lease=self.durable(); registry.transition("exec",status="RETRYING",phase="retry",transition_sequence=3,receipt_root="3"*64); registry.cancel("exec")
        self.assertEqual(registry.get("exec").status,"CANCELLED"); self.assertIsNone(manager.current("external"))
        stale=manager.authorize_write(authority_domain="external",holder_identity_root=HASH,fencing_token=lease.fencing_token,lease_generation=lease.lease_generation,expected_parent_state=ZERO_HASH,action_digest="8"*64)
        self.assertIn("LEASE_MISSING",stale.denial_codes)

    def test_workspace_remote_changed(self):
        decision=verify_workspace(declared_root=self.root,cwd=self.root,expected_remote=REMOTE,actual_remote="https://github.com/other/project.git",project_identity="AEGIS-OMEGA",source_commit=COMMIT,operator_authorization=self.approval_ref,mutation_target=self.root)
        self.assertIn("REMOTE_ORIGIN_CHANGED",decision.denial_codes)

    def test_symlink_escape(self):
        outside=self.root.parent/"outside-a3"; outside.mkdir(exist_ok=True); link=self.root/"link"; link.symlink_to(outside,target_is_directory=True)
        decision=verify_workspace(declared_root=self.root,cwd=self.root,expected_remote=REMOTE,actual_remote=REMOTE,project_identity="AEGIS-OMEGA",source_commit=COMMIT,operator_authorization=self.approval_ref,mutation_target=link/"x")
        self.assertIn("MUTATION_TARGET_OUTSIDE_REPOSITORY",decision.denial_codes)

    def test_valid_decision_and_determinism(self):
        first=self.evaluator.evaluate(self.request(),approval=self.approval()); second=self.evaluator.evaluate(self.request(),approval=self.approval())
        self.assertEqual(first.outcome,ADMITTED); self.assertEqual(first,second); self.assertEqual(first.decision_root,second.decision_root)

    def test_event_law_and_operator_visibility_fields(self):
        payload={"content_type":"application/json","data":{"x":1},"text":"bounded message"}; digest=canonical_hash("RAW",payload)
        # Event payload digest is exact SHA-256 of canonical payload, not domain hash.
        import hashlib
        digest=hashlib.sha256(canonical_bytes(payload)).hexdigest()
        event=EventEnvelope(HASH,"engineering",ZERO_HASH,"repository.mutate","event.v1",payload,digest,"receipt-chain","2"*64,ZERO_HASH,0,"3"*64)
        event.validate(expected_sequence=0,expected_parent=ZERO_HASH,sender_lease_root=HASH); self.assertRegex(event.root,r"^[0-9a-f]{64}$")


    def test_concurrent_writers_only_one_acquires(self):
        import threading
        manager = WriterLeaseManager()
        barrier = threading.Barrier(20)
        outcomes: list[str] = []
        lock = threading.Lock()
        def worker(index: int) -> None:
            barrier.wait()
            _lease, receipt = manager.acquire(authority_domain="git-race", holder_identity_root=f"{index + 1:064x}", source_commit=COMMIT, expected_parent_state=ZERO_HASH)
            with lock:
                outcomes.append(receipt.outcome)
        threads = [threading.Thread(target=worker, args=(index,)) for index in range(20)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(outcomes.count(ADMITTED), 1)
        self.assertEqual(outcomes.count(DENIED), 19)

    def test_adaptive_denial_attempts_k_1_10_100(self):
        initial=(self.root/"evidence/run.json").read_bytes()
        for k in (1,10,100):
            roots=[]
            for _ in range(k):
                decision=self.evaluator.evaluate(self.request(requested_capability="encoded%2Fadmin"),approval=self.approval())
                self.assertDenied(decision,"UNMAPPED_CAPABILITY"); roots.append(decision.decision_root)
            self.assertEqual(len(set(roots)),1)
            self.assertEqual((self.root/"evidence/run.json").read_bytes(),initial)


if __name__ == "__main__":
    main()
