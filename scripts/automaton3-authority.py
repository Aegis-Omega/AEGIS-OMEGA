#!/usr/bin/env python3
"""Single CLI boundary for Automaton-3 authority evaluation."""
from __future__ import annotations

import argparse
import json
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
    ZERO_HASH,
    canonical_hash,
    decision_dict,
    load_capability_registry,
    load_policy,
    make_mutation_receipt,
    verify_workspace,
)
from harness.sdk.transition_receipts import (  # noqa: E402
    build_transition_identity,
    decision_receipt_from_policy,
)

LEGACY_RECEIPT_SEMANTICS = "DECISION_DERIVED_NOT_EFFECT_PROOF"


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
        workspace = verify_workspace(
            declared_root=ROOT,
            cwd=workspace_payload.get("actual_cwd", ROOT),
            expected_remote=identity.repository_identity,
            actual_remote=workspace_payload.get("remote_origin", identity.repository_identity),
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
        policy, policy_root = load_policy(ROOT / "harness" / "policies" / "consequence-policy.v1.json")
        registry, registry_root = load_capability_registry(
            repository_root=ROOT,
            skill_tree_path=ROOT / "harness" / "skill_tree.json",
            capability_map_path=ROOT / "harness" / "policies" / "capability-map.v1.json",
        )
    except Exception as exc:
        return deny("AUTHORITY_SERVICE_UNAVAILABLE", str(exc))

    request_payload = payload.get("request", {})
    action = payload.get("action", {})
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    if identity.action_digest != action_digest:
        return deny("ACTION_DIGEST_MISMATCH")
    try:
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
            current_generation=int(request_payload.get("current_generation", 0)),
            approval_reference=identity.approval_reference,
            idempotency_key=request_payload.get("idempotency_key", "NONE"),
            compensation_reference=request_payload.get("compensation_reference", "NONE"),
        )
        approval = ApprovalGrant(**payload["approval"]) if payload.get("approval") else None
        decision = AuthorityEvaluator(policy=policy, registry=registry, repository_root=ROOT).evaluate(request, approval=approval)
        legacy_pre_state_digest = request_payload.get("pre_state_digest", ZERO_HASH)
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

        # Compatibility-only legacy V1 artifact. Caller-supplied pre/post digests are
        # preserved for format compatibility, but neither participates as authoritative
        # effect evidence. The new TransitionID binds identity.expected_pre_state.
        receipt = make_mutation_receipt(
            identity_root=identity_root,
            workspace_binding=identity.workspace_binding,
            decision=decision,
            pre_state_digest=legacy_pre_state_digest,
            action_digest=action_digest,
            result={"authority_outcome": decision.outcome},
            post_state_digest=request_payload.get("post_state_digest", legacy_pre_state_digest),
            parent_receipt=request_payload.get("parent_receipt", ZERO_HASH),
            sequence=int(request_payload.get("sequence", 0)),
        )
        return {
            "schema_version": "1.0.0",
            "outcome": decision.outcome,
            "execution_identity_root": identity_root,
            "workspace_binding": identity.workspace_binding,
            "workspace_decision_root": workspace.decision_root,
            "policy_decision": decision_dict(decision),
            "transition_id": transition.root,
            "decision_receipt": asdict(decision_receipt),
            "decision_receipt_root": decision_receipt.root,
            "mutation_receipt": asdict(receipt),
            "mutation_receipt_root": receipt.root,
            "legacy_receipt_semantics": LEGACY_RECEIPT_SEMANTICS,
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
