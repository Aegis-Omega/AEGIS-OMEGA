"""Environment-bound client for the single Automaton-3 authority evaluator."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness.sdk.sovereign_execution import (
    ADMITTED, ApprovalGrant, AuthorityEvaluator, AuthorityRequest,
    ExecutionIdentityEnvelope, ZERO_HASH, canonical_hash,
    load_capability_registry, load_policy, make_mutation_receipt,
    verify_workspace,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _denial(code: str, detail: str = "") -> dict[str, Any]:
    body = {"outcome": "DENIED", "authority_score": "0.000000", "denial_codes": [code], "detail_digest": canonical_hash("AEGIS_AUTHORITY_CLIENT_DETAIL_V1", detail)}
    body["decision_root"] = canonical_hash("AEGIS_AUTHORITY_CLIENT_DENIAL_V1", body)
    return body


def authorize_from_environment(*, action_class: str, authority_domain: str, requested_capability: str, tool: str, target: str, action: dict[str, Any], current_generation: int = 0, idempotency_key: str = "NONE", compensation_reference: str = "NONE") -> dict[str, Any]:
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
        workspace = verify_workspace(
            declared_root=REPO_ROOT,
            cwd=observation.get("actual_cwd", os.getcwd()),
            expected_remote=identity.repository_identity,
            actual_remote=observation.get("remote_origin", identity.repository_identity),
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
        policy, policy_root = load_policy(REPO_ROOT / "harness/policies/consequence-policy.v1.json")
        registry, registry_root = load_capability_registry(
            repository_root=REPO_ROOT,
            skill_tree_path=REPO_ROOT / "harness/skill_tree.json",
            capability_map_path=REPO_ROOT / "harness/policies/capability-map.v1.json",
        )
    except Exception as exc:
        return _denial("AUTHORITY_SERVICE_UNAVAILABLE", str(exc))

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
        policy_root=policy_root, current_generation=current_generation,
        approval_reference=identity.approval_reference,
        idempotency_key=idempotency_key, compensation_reference=compensation_reference,
    )
    decision = AuthorityEvaluator(policy=policy, registry=registry, repository_root=REPO_ROOT).evaluate(request, approval=approval)
    receipt = make_mutation_receipt(
        identity_root=identity_root, workspace_binding=identity.workspace_binding,
        decision=decision, pre_state_digest=identity.expected_pre_state,
        action_digest=action_digest, result={"authority_outcome": decision.outcome},
        post_state_digest=identity.expected_pre_state, parent_receipt=ZERO_HASH, sequence=0,
    )
    return {
        "outcome": decision.outcome,
        "authority_score": decision.authority_score,
        "denial_codes": list(decision.denial_codes),
        "decision_root": decision.decision_root,
        "receipt_root": receipt.root,
        "execution_identity_root": identity_root,
        "workspace_binding": identity.workspace_binding,
        "observation": asdict(workspace.observation),
    }
