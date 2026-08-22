"""Environment-bound client for the single Automaton-3 authority evaluator."""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness.sdk.principal_binding import (
    DPOP_CERT_BOUND,
    MTLS_DPOP_CERT_BOUND,
    VALIDATED_BINDING_EVIDENCE,
    evaluate_execution_principal,
)
from harness.sdk.sovereign_execution import (
    ADMITTED, ApprovalGrant, AuthorityEvaluator, AuthorityRequest,
    ExecutionIdentityEnvelope, ZERO_HASH, canonical_hash,
    load_capability_registry, load_policy, make_mutation_receipt,
    verify_workspace,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTION_PRINCIPAL_CLASSES = frozenset(("D3", "D4"))
DPOP_MODES = frozenset((DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND))


def _denial(code: str, detail: str = "") -> dict[str, Any]:
    body = {"outcome": "DENIED", "authority_score": "0.000000", "denial_codes": [code], "detail_digest": canonical_hash("AEGIS_AUTHORITY_CLIENT_DETAIL_V1", detail)}
    body["decision_root"] = canonical_hash("AEGIS_AUTHORITY_CLIENT_DENIAL_V1", body)
    return body


def _principal_denial(principal_decision) -> dict[str, Any]:
    codes = ["EXECUTION_PRINCIPAL_DENIED", *principal_decision.denial_codes]
    body = {
        "outcome": "DENIED",
        "authority_score": "0.000000",
        "denial_codes": codes,
        "execution_principal_binding_root": principal_decision.binding_root,
        "execution_principal_decision_root": principal_decision.decision_root,
    }
    body["decision_root"] = canonical_hash("AEGIS_AUTHORITY_CLIENT_PRINCIPAL_DENIAL_V1", body)
    return body


def _load_crypto_evidence(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError("RUNTIME_POP_CRYPTO_EVIDENCE_PATH_NOT_ABSOLUTE")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("RUNTIME_POP_CRYPTO_EVIDENCE_NOT_OBJECT")
    return value


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
    if identity.requested_capability != requested_capability:
        return _denial("IDENTITY_CAPABILITY_MISMATCH")
    if identity.authority_domain != authority_domain:
        return _denial("IDENTITY_AUTHORITY_DOMAIN_MISMATCH")
    if identity.tool_identity != tool:
        return _denial("IDENTITY_TOOL_MISMATCH")

    principal_decision = None
    crypto_receipt = None
    if action_class in EXECUTION_PRINCIPAL_CLASSES:
        raw_principal = os.environ.get("AEGIS_EXECUTION_PRINCIPAL_JSON")
        if not raw_principal:
            return _denial("EXECUTION_PRINCIPAL_UNAVAILABLE")
        evidence_path = os.environ.get("AEGIS_RUNTIME_POP_CRYPTO_EVIDENCE_PATH")
        if not evidence_path:
            return _denial("RUNTIME_POP_CRYPTO_EVIDENCE_UNAVAILABLE")
        try:
            # Crypto is an optional process dependency for D0-D2 but mandatory
            # and fail-closed once consequential D3/D4 evaluation is requested.
            from harness.sdk.runtime_pop_authority import (
                SQLiteReplayStore,
                bind_execution_principal_from_crypto,
            )

            principal_payload = json.loads(raw_principal)
            if not isinstance(principal_payload, dict):
                raise ValueError("EXECUTION_PRINCIPAL_NOT_OBJECT")
            crypto_evidence = _load_crypto_evidence(evidence_path)
            replay_store = None
            if crypto_evidence.get("binding_mode") in DPOP_MODES:
                replay_db = os.environ.get("AEGIS_DPOP_REPLAY_DB")
                if not replay_db:
                    return _denial("DPOP_REPLAY_STORE_UNAVAILABLE")
                replay_store = SQLiteReplayStore(replay_db)
            principal, crypto_receipt = bind_execution_principal_from_crypto(
                principal_payload,
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
            return _denial("RUNTIME_POP_CRYPTO_INVALID", str(exc))
        if principal_decision.outcome != VALIDATED_BINDING_EVIDENCE:
            return _principal_denial(principal_decision)

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
    result = {
        "outcome": decision.outcome,
        "authority_score": decision.authority_score,
        "denial_codes": list(decision.denial_codes),
        "decision_root": decision.decision_root,
        "receipt_root": receipt.root,
        "execution_identity_root": identity_root,
        "workspace_binding": identity.workspace_binding,
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
