#!/usr/bin/env python3
"""Automaton-3 authority abuse, replay, and determinism tests."""
from __future__ import annotations

import json
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
    compute_workspace_binding, verify_workspace,
)

REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"
COMMIT = "a" * 40
HASH = "1" * 64
POLICY = {
    "D0": {"minimum_validated_runs": 0, "approval": "NONE", "external_idempotency": False},
    "D1": {"minimum_validated_runs": 3, "approval": "NONE", "external_idempotency": False},
    "D2": {"minimum_validated_runs": 3, "approval": "EXPLICIT", "external_idempotency": False},
    "D3": {"minimum_validated_runs": 3, "approval": "EXPLICIT", "external_idempotency": True},
    "D4": {"minimum_validated_runs": 3, "approval": "EXPLICIT", "external_idempotency": True},
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
        self.identity = self.make_identity()
        self.capability = CapabilityEvidence(
            capability="repository.mutate", skill_id="gate8_deployment_gate", observation_state="OBSERVED",
            validated_runs=3, confidence_micros=900_000, recency_micros=900_000, failure_rate_micros=0,
            evidence_refs=("evidence/run.json",), allowed_action_classes=(D1, D2, D4), allowed_tools=("git",),
        )
        self.evaluator = AuthorityEvaluator(policy=POLICY, registry={"repository.mutate": self.capability}, repository_root=self.root)

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
                      registry_root=self.registry_root, policy_root=self.policy_root, current_generation=1,
                      approval_reference=self.approval_ref)
        values.update(changes)
        return AuthorityRequest(**values)

    def approval(self, **changes) -> ApprovalGrant:
        values = dict(reference=self.approval_ref, authority_domain="github:contents", action_class=D2, source_commit=COMMIT,
                      workspace_binding=self.binding, valid_through_generation=2, signature_root="4"*64)
        values.update(changes)
        return ApprovalGrant(**values)

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

    def test_07_mismatched_source_commit(self):
        self.assertDenied(self.evaluator.evaluate(self.request(source_commit="b"*40), approval=self.approval()), "APPROVAL_SOURCE_COMMIT_MISMATCH")

    def test_08_mismatched_skills_root(self):
        with self.assertRaisesRegex(SovereignExecutionError, "skills_root:INVALID_SHA256"):
            self.make_identity(skills_root="bad").root

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
        self.assertEqual(manager.authorize_write(**kwargs).outcome, ADMITTED)
        self.assertIn("REPLAYED_AUTHORITATIVE_ACTION", manager.authorize_write(**kwargs).denial_codes)

    def durable(self):
        manager=WriterLeaseManager(); lease,_=manager.acquire(authority_domain="external", holder_identity_root=HASH, source_commit=COMMIT, expected_parent_state=ZERO_HASH)
        registry=DurableExecutionRegistry(manager)
        record=DurableExecutionRecord("wf","operator",COMMIT,self.binding,"plan",("external",),0,"",0,None,"ACTIVE",HASH,ZERO_HASH,ZERO_HASH,"","PLANNED",0)
        registry.register("exec",record); registry.transition("exec",status="RUNNING",phase="execute",transition_sequence=1,receipt_root=HASH)
        return manager,registry,lease

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
        chain=ReceiptChain(); base=dict(receipt_version=SCHEMA_VERSION,execution_identity_root=HASH,workspace_binding=self.binding,policy_decision_root="2"*64,authority_score="0.0",authority_domain="git",action_class=D2,tool="git",target="3"*64,pre_state_digest=ZERO_HASH,requested_action_digest="4"*64,result_digest="5"*64,post_state_digest="6"*64,outcome="SUCCEEDED",denial_code="NONE")
        first=MutationReceipt(**base,parent_receipt=ZERO_HASH,sequence=0); chain.append(first)
        with self.assertRaisesRegex(SovereignExecutionError,"RECEIPT_CHAIN_PARENT_BREAK"): chain.append(MutationReceipt(**base,parent_receipt=ZERO_HASH,sequence=1))

    def test_30_cancellation_during_retry(self):
        manager,registry,lease=self.durable(); registry.transition("exec",status="RETRYING",phase="retry",transition_sequence=2,receipt_root="2"*64); registry.cancel("exec")
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
