"""Environment-bound client for the single Automaton-3 authority evaluator."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness.sdk.sovereign_execution import (
    ADMITTED, ApprovalGrant, AuthorityEvaluator, AuthorityRequest,
    ExecutionIdentityEnvelope, canonical_hash, canonical_remote,
    git_head, git_remote,
    load_capability_registry_from_commit, load_policy_from_commit,
    make_authority_decision_receipt, verify_live_authority_roots, verify_workspace,
)
from harness.sdk.transition_receipts import (
    build_transition_identity,
    decision_receipt_from_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _denial(code: str, detail: str = "") -> dict[str, Any]:
    body = {"outcome": "DENIED", "authority_score": "0.000000", "denial_codes": [code], "detail_digest": canonical_hash("AEGIS_AUTHORITY_CLIENT_DETAIL_V1", detail)}
    body["decision_root"] = canonical_hash("AEGIS_AUTHORITY_CLIENT_DENIAL_V1", body)
    return body


def authorize_from_environment(*, action_class: str, authority_domain: str, requested_capability: str, tool: str, target: str, action: dict[str, Any], current_generation: int = 0, rollback_reference: str = "NONE", idempotency_key: str = "NONE", compensation_reference: str = "NONE") -> dict[str, Any]:
    raw_identity = os.environ.get("AEGIS_EXECUTION_IDENTITY_JSON")
    if not raw_identity:
        return _denial("IDENTITY_UNAVAILABLE")
    try:
        identity = ExecutionIdentityEnvelope(**json.loads(raw_identity))
        identity_root = identity.root
    except Exception as exc:
        return _denial("IDENTITY_INVALID", str(exc))
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    if action_digest != identity.action_digest:
        return _denial("ACTION_DIGEST_MISMATCH")

    try:
        observation = json.loads(os.environ.get("AEGIS_WORKSPACE_OBSERVATION_JSON", "{}"))
        live_head = git_head(REPO_ROOT)
        live_remote = git_remote(REPO_ROOT)
        if live_head != identity.source_commit:
            return _denial("SOURCE_COMMIT_MISMATCH")
        claimed_remote = observation.get("remote_origin")
        if claimed_remote is not None and canonical_remote(claimed_remote) != live_remote:
            return _denial("WORKSPACE_REMOTE_CLAIM_MISMATCH")
        workspace = verify_workspace(
            declared_root=REPO_ROOT,
            cwd=observation.get("actual_cwd", os.getcwd()),
            expected_remote=identity.repository_identity,
            actual_remote=live_remote,
            project_identity=identity.project_identity,
            source_commit=identity.source_commit,
            operator_authorization=identity.approval_reference,
            mutation_target=observation.get("mutation_target", REPO_ROOT),
            path_views=observation.get("path_views", {}),
            selected_nested_root=observation.get("selected_nested_root"),
        )
    except Exception as exc:
        return _denial("WORKSPACE_VERIFICATION_ERROR", str(exc))
    if workspace.outcome != ADMITTED or workspace.workspace_binding != identity.workspace_binding:
        return _denial("WORKSPACE_DENIED", ",".join(workspace.denial_codes))

    try:
        policy, policy_root = load_policy_from_commit(
            repository_root=REPO_ROOT,
            source_commit=identity.source_commit,
            policy_path="harness/policies/consequence-policy.v1.json",
        )
        registry, skills_root, registry_root = load_capability_registry_from_commit(
            repository_root=REPO_ROOT,
            source_commit=identity.source_commit,
            skill_tree_path="harness/skill_tree.json",
            capability_map_path="harness/policies/capability-map.v1.json",
        )
    except Exception as exc:
        return _denial("AUTHORITY_SERVICE_UNAVAILABLE", str(exc))
    try:
        verify_live_authority_roots(
            identity,
            skills_root=skills_root,
            registry_root=registry_root,
            policy_root=policy_root,
        )
    except Exception as exc:
        return _denial(str(exc), "commit-bound authority roots do not match execution identity")

    approval = None
    raw_approval = os.environ.get("AEGIS_APPROVAL_GRANT_JSON")
    if raw_approval:
        try:
            approval = ApprovalGrant(**json.loads(raw_approval))
        except Exception as exc:
            return _denial("APPROVAL_MALFORMED", str(exc))
    request = AuthorityRequest(
        action_class=action_class, authority_domain=authority_domain,
        requested_capability=requested_capability, tool=tool, target=target,
        identity_root=identity_root, workspace_binding=identity.workspace_binding,
        source_commit=identity.source_commit, registry_root=registry_root,
        policy_root=policy_root, action_digest=action_digest,
        expected_pre_state=identity.expected_pre_state,
        workspace_mode="READ_ONLY" if action_class == "D0" else "REPOSITORY",
        current_generation=current_generation,
        approval_reference=identity.approval_reference,
        rollback_reference=rollback_reference,
        idempotency_key=idempotency_key, compensation_reference=compensation_reference,
    )
    try:
        trusted_operator_keys = json.loads(os.environ.get("AEGIS_TRUSTED_OPERATOR_KEYS_JSON", "{}"))
        authority_issuer_key_id = os.environ["AEGIS_AUTHORITY_ISSUER_KEY_ID"]
        authority_signing_key = os.environ["AEGIS_AUTHORITY_SIGNING_KEY_HEX"]
    except Exception as exc:
        return _denial("AUTHORITY_SIGNER_UNAVAILABLE", str(exc))
    evaluator = AuthorityEvaluator(policy=policy, registry=registry, repository_root=REPO_ROOT, trusted_operator_keys=trusted_operator_keys)
    decision = evaluator.evaluate(request, approval=approval)
    authority_receipt = make_authority_decision_receipt(
        identity=identity, request=request, decision=decision, evaluator=evaluator,
        issuer_key_id=authority_issuer_key_id, issuer_private_key_hex=authority_signing_key,
    )
    transition = build_transition_identity(
        source_commit=identity.source_commit,
        pre_state_commitment=identity.expected_pre_state,
        identity_root=identity_root,
        approval=approval,
        requested_capability=requested_capability,
        registry_root=registry_root,
        action_digest=action_digest,
        deterministic_nonce=identity.deterministic_nonce,
        fence_token=os.environ.get("AEGIS_FENCING_TOKEN"),
    )
    decision_receipt = decision_receipt_from_policy(transition=transition, decision=decision)
    return {
        "outcome": decision.outcome,
        "authority_score": decision.authority_score,
        "denial_codes": list(decision.denial_codes),
        "decision_root": decision.decision_root,
        "authority_receipt_root": authority_receipt.root,
        "transition_id": transition.root,
        "decision_receipt": asdict(decision_receipt),
        "decision_receipt_root": decision_receipt.root,
        "execution_identity_root": identity_root,
        "workspace_binding": identity.workspace_binding,
        "observation": asdict(workspace.observation),
    }
