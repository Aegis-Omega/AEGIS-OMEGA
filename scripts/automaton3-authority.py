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

from harness.sdk.principal_binding import (  # noqa: E402
    DPOP_CERT_BOUND,
    MTLS_DPOP_CERT_BOUND,
    VALIDATED_BINDING_EVIDENCE,
    evaluate_execution_principal,
)
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

EXECUTION_PRINCIPAL_CLASSES = frozenset(("D3", "D4"))
DPOP_MODES = frozenset((DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND))


def deny(code: str, detail: str = "") -> dict:
    body = {"schema_version": "1.0.0", "outcome": "DENIED", "denial_codes": [code], "detail_digest": canonical_hash("AEGIS_DENIAL_DETAIL_V1", detail)}
    body["denial_receipt_root"] = canonical_hash("AEGIS_AUTOMATON3_DENIAL_V1", body)
    return body


def deny_principal(principal_decision) -> dict:
    body = {
        "schema_version": "1.0.0",
        "outcome": "DENIED",
        "denial_codes": ["EXECUTION_PRINCIPAL_DENIED", *principal_decision.denial_codes],
        "execution_principal_binding_root": principal_decision.binding_root,
        "execution_principal_decision_root": principal_decision.decision_root,
        "execution_principal_authority_granted": False,
    }
    body["denial_receipt_root"] = canonical_hash("AEGIS_AUTOMATON3_PRINCIPAL_DENIAL_V1", body)
    return body


def evaluate(payload: dict) -> dict:
    try:
        identity = ExecutionIdentityEnvelope(**payload["identity"])
        identity_root = identity.root
    except Exception as exc:
        return deny("IDENTITY_INVALID", str(exc))

    request_payload = payload.get("request", {})
    action = payload.get("action", {})
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
    if identity.action_digest != action_digest:
        return deny("ACTION_DIGEST_MISMATCH")

    try:
        action_class = request_payload["action_class"]
        authority_domain = request_payload["authority_domain"]
        requested_capability = request_payload["requested_capability"]
        tool = request_payload["tool"]
        target = request_payload["target"]
        current_generation = int(request_payload.get("current_generation", 0))
        if current_generation < 0:
            raise ValueError("current_generation must be nonnegative")
    except (KeyError, TypeError, ValueError) as exc:
        return deny("AUTHORITY_REQUEST_MALFORMED", str(exc))
    if identity.requested_capability != requested_capability:
        return deny("IDENTITY_CAPABILITY_MISMATCH")
    if identity.authority_domain != authority_domain:
        return deny("IDENTITY_AUTHORITY_DOMAIN_MISMATCH")
    if identity.tool_identity != tool:
        return deny("IDENTITY_TOOL_MISMATCH")

    principal_decision = None
    crypto_receipt = None
    if action_class in EXECUTION_PRINCIPAL_CLASSES:
        raw_principal = payload.get("execution_principal")
        if raw_principal is None:
            return deny("EXECUTION_PRINCIPAL_UNAVAILABLE")
        crypto_evidence = payload.get("runtime_pop_crypto_evidence")
        if crypto_evidence is None:
            return deny("RUNTIME_POP_CRYPTO_EVIDENCE_UNAVAILABLE")
        if not isinstance(crypto_evidence, dict):
            return deny("RUNTIME_POP_CRYPTO_EVIDENCE_INVALID")
        try:
            # Keep D0-D2 independent of the optional crypto package. D3/D4
            # imports it inside the consequential boundary and fails closed if
            # the runtime dependency is absent.
            from harness.sdk.runtime_pop_authority import (
                SQLiteReplayStore,
                bind_execution_principal_from_crypto,
            )

            replay_store = None
            if crypto_evidence.get("binding_mode") in DPOP_MODES:
                replay_db = request_payload.get("dpop_replay_db")
                if not replay_db:
                    return deny("DPOP_REPLAY_STORE_UNAVAILABLE")
                replay_store = SQLiteReplayStore(replay_db)
            principal, crypto_receipt = bind_execution_principal_from_crypto(
                raw_principal,
                crypto_evidence,
                generation=current_generation,
                replay_store=replay_store,
            )
            principal_decision = evaluate_execution_principal(
                principal,
                action_class=action_class,
                expected_agent_principal=identity.actor_identity,
                expected_runtime_principal=identity.physical_executor,
                expected_session_identity=identity.session_identity,
                expected_action_digest=action_digest,
                expected_capability=requested_capability,
                expected_target_digest=canonical_hash("AEGIS_AUTHORITY_TARGET_V1", target),
            )
        except Exception as exc:
            return deny("RUNTIME_POP_CRYPTO_INVALID", str(exc))
        if principal_decision.outcome != VALIDATED_BINDING_EVIDENCE:
            return deny_principal(principal_decision)

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

    try:
        request = AuthorityRequest(
            action_class=action_class,
            authority_domain=authority_domain,
            requested_capability=requested_capability,
            tool=tool,
            target=target,
            identity_root=identity_root,
            workspace_binding=identity.workspace_binding,
            source_commit=identity.source_commit,
            registry_root=registry_root,
            policy_root=policy_root,
            current_generation=current_generation,
            approval_reference=identity.approval_reference,
            idempotency_key=request_payload.get("idempotency_key", "NONE"),
            compensation_reference=request_payload.get("compensation_reference", "NONE"),
        )
        approval = ApprovalGrant(**payload["approval"]) if payload.get("approval") else None
        decision = AuthorityEvaluator(policy=policy, registry=registry, repository_root=ROOT).evaluate(request, approval=approval)
        receipt = make_mutation_receipt(
            identity_root=identity_root,
            workspace_binding=identity.workspace_binding,
            decision=decision,
            pre_state_digest=request_payload.get("pre_state_digest", ZERO_HASH),
            action_digest=action_digest,
            result={"authority_outcome": decision.outcome},
            post_state_digest=request_payload.get("post_state_digest", request_payload.get("pre_state_digest", ZERO_HASH)),
            parent_receipt=request_payload.get("parent_receipt", ZERO_HASH),
            sequence=int(request_payload.get("sequence", 0)),
        )
        result = {
            "schema_version": "1.0.0",
            "outcome": decision.outcome,
            "execution_identity_root": identity_root,
            "workspace_binding": identity.workspace_binding,
            "workspace_decision_root": workspace.decision_root,
            "policy_decision": decision_dict(decision),
            "mutation_receipt": asdict(receipt),
            "mutation_receipt_root": receipt.root,
            "observation": asdict(workspace.observation),
        }
        if principal_decision is not None:
            result["execution_principal_binding_root"] = principal_decision.binding_root
            result["execution_principal_decision_root"] = principal_decision.decision_root
            result["execution_principal_authority_granted"] = False
        if crypto_receipt is not None:
            result["runtime_pop_crypto_receipt_root"] = crypto_receipt.proof_root
            result["runtime_pop_crypto_verifier_identity"] = crypto_receipt.verifier_identity
        return result
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
