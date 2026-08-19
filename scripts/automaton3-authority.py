#!/usr/bin/env python3
"""Single CLI boundary for Automaton-3 authority evaluation."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.sdk.sovereign_execution import (  # noqa: E402
    ADMITTED,
    ApprovalGrant,
    AuthorityEvaluator,
    AuthorityRequest,
    ExecutionIdentityEnvelope,
    canonical_hash,
    canonical_remote,
    decision_dict,
    git_head,
    git_remote,
    load_capability_registry_from_commit,
    load_policy_from_commit,
    make_authority_decision_receipt,
    verify_live_authority_roots,
    verify_workspace,
)
from harness.sdk.transition_receipts import (  # noqa: E402
    build_transition_identity,
    decision_receipt_from_policy,
)


def deny(code: str, detail: str = "") -> dict:
    body = {"schema_version": "1.0.0", "outcome": "DENIED", "denial_codes": [code], "detail_digest": canonical_hash("AEGIS_DENIAL_DETAIL_V1", detail)}
    body["denial_receipt_root"] = canonical_hash("AEGIS_AUTOMATON3_DENIAL_V1", body)
    return body


def evaluate(payload: dict) -> dict:
    try:
        identity = ExecutionIdentityEnvelope(**payload["identity"])
        identity_root = identity.root
    except Exception as exc:
        return deny("IDENTITY_INVALID", str(exc))

    workspace_payload = payload.get("workspace", {})
    try:
        live_head = git_head(ROOT)
        live_remote = git_remote(ROOT)
        if live_head != identity.source_commit:
            return deny("SOURCE_COMMIT_MISMATCH")
        claimed_remote = workspace_payload.get("remote_origin")
        if claimed_remote is not None and canonical_remote(claimed_remote) != live_remote:
            return deny("WORKSPACE_REMOTE_CLAIM_MISMATCH")
        workspace = verify_workspace(
            declared_root=ROOT,
            cwd=workspace_payload.get("actual_cwd", ROOT),
            expected_remote=identity.repository_identity,
            actual_remote=live_remote,
            project_identity=identity.project_identity,
            source_commit=identity.source_commit,
            operator_authorization=identity.approval_reference,
            mutation_target=workspace_payload.get("mutation_target", ROOT),
            path_views=workspace_payload.get("path_views", {}),
            selected_nested_root=workspace_payload.get("selected_nested_root"),
        )
    except Exception as exc:
        return deny("WORKSPACE_VERIFICATION_ERROR", str(exc))
    if workspace.outcome != ADMITTED or workspace.workspace_binding != identity.workspace_binding:
        return {
            **deny("WORKSPACE_DENIED", ",".join(workspace.denial_codes)),
            "workspace_decision_root": workspace.decision_root,
            "workspace_denial_codes": list(workspace.denial_codes),
            "observation": asdict(workspace.observation),
        }

    try:
        policy, policy_root = load_policy_from_commit(
            repository_root=ROOT,
            source_commit=identity.source_commit,
            policy_path="harness/policies/consequence-policy.v1.json",
        )
        registry, skills_root, registry_root = load_capability_registry_from_commit(
            repository_root=ROOT,
            source_commit=identity.source_commit,
            skill_tree_path="harness/skill_tree.json",
            capability_map_path="harness/policies/capability-map.v1.json",
        )
    except Exception as exc:
        return deny("AUTHORITY_SERVICE_UNAVAILABLE", str(exc))
    try:
        verify_live_authority_roots(
            identity,
            skills_root=skills_root,
            registry_root=registry_root,
            policy_root=policy_root,
        )
    except Exception as exc:
        return deny(str(exc), "commit-bound authority roots do not match execution identity")

    request_payload = payload.get("request", {})
    action = payload.get("action", {})
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    if identity.action_digest != action_digest:
        return deny("ACTION_DIGEST_MISMATCH")
    try:
        trusted_operator_keys = json.loads(os.environ.get("AEGIS_TRUSTED_OPERATOR_KEYS_JSON", "{}"))
        if not isinstance(trusted_operator_keys, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in trusted_operator_keys.items()):
            raise ValueError("trusted operator key map")
        authority_issuer_key_id = os.environ["AEGIS_AUTHORITY_ISSUER_KEY_ID"]
        authority_signing_key = os.environ["AEGIS_AUTHORITY_SIGNING_KEY_HEX"]
        request = AuthorityRequest(
            action_class=request_payload["action_class"],
            authority_domain=request_payload["authority_domain"],
            requested_capability=request_payload["requested_capability"],
            tool=request_payload["tool"],
            target=request_payload["target"],
            identity_root=identity_root,
            workspace_binding=identity.workspace_binding,
            source_commit=identity.source_commit,
            registry_root=registry_root,
            policy_root=policy_root,
            action_digest=action_digest,
            expected_pre_state=identity.expected_pre_state,
            workspace_mode=request_payload["workspace_mode"],
            current_generation=int(request_payload.get("current_generation", 0)),
            approval_reference=identity.approval_reference,
            rollback_reference=request_payload.get("rollback_reference", "NONE"),
            idempotency_key=request_payload.get("idempotency_key", "NONE"),
            compensation_reference=request_payload.get("compensation_reference", "NONE"),
        )
        approval = ApprovalGrant(**payload["approval"]) if payload.get("approval") else None
        evaluator = AuthorityEvaluator(policy=policy, registry=registry, repository_root=ROOT, trusted_operator_keys=trusted_operator_keys)
        decision = evaluator.evaluate(request, approval=approval)
        authority_receipt = make_authority_decision_receipt(
            identity=identity,
            request=request,
            decision=decision,
            evaluator=evaluator,
            issuer_key_id=authority_issuer_key_id,
            issuer_private_key_hex=authority_signing_key,
        )
        transition = build_transition_identity(
            source_commit=identity.source_commit,
            pre_state_commitment=identity.expected_pre_state,
            identity_root=identity_root,
            approval=approval,
            requested_capability=request.requested_capability,
            registry_root=registry_root,
            action_digest=action_digest,
            deterministic_nonce=identity.deterministic_nonce,
            fence_token=request_payload.get("fencing_token"),
        )
        decision_receipt = decision_receipt_from_policy(transition=transition, decision=decision)
        return {
            "schema_version": "1.0.0",
            "outcome": decision.outcome,
            "execution_identity_root": identity_root,
            "workspace_binding": identity.workspace_binding,
            "workspace_decision_root": workspace.decision_root,
            "policy_decision": decision_dict(decision),
            "authority_receipt": asdict(authority_receipt),
            "authority_receipt_root": authority_receipt.root,
            "transition_id": transition.root,
            "decision_receipt": asdict(decision_receipt),
            "decision_receipt_root": decision_receipt.root,
            "observation": asdict(workspace.observation),
        }
    except Exception as exc:
        return deny("AUTHORITY_EVALUATION_ERROR", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate"])
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    args = parser.parse_args()
    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        result = deny("INPUT_JSON_MALFORMED", str(exc))
    else:
        result = evaluate(payload)
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output == "-":
        sys.stdout.write(rendered)
    else:
        Path(args.output).write_text(rendered, encoding="utf-8")
    return 0 if result.get("outcome") == ADMITTED else 3


if __name__ == "__main__":
    raise SystemExit(main())
