"""Environment-bound client for the single Automaton-3 authority evaluator."""
from __future__ import annotations

import json
import os
import time
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


def _load_absolute_json_object(path_value: str, *, path_code: str, object_code: str) -> dict[str, Any]:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(path_code)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(object_code)
    return value


def _load_absolute_text(path_value: str, *, path_code: str, empty_code: str) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(path_code)
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(empty_code)
    return value


def _load_absolute_bytes(path_value: str, *, path_code: str, empty_code: str) -> bytes:
    path = Path(path_value)
    if not path.is_absolute():
        raise ValueError(path_code)
    value = path.read_bytes()
    if not value:
        raise ValueError(empty_code)
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
    target_digest = canonical_hash("AEGIS_AUTHORITY_TARGET_V1", target)
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
    trust_policy_root = None
    attestation_receipt = None
    eat_crypto_receipt = None
    scitt_registration_receipt = None
    if action_class in EXECUTION_PRINCIPAL_CLASSES:
        raw_principal = os.environ.get("AEGIS_EXECUTION_PRINCIPAL_JSON")
        if not raw_principal:
            return _denial("EXECUTION_PRINCIPAL_UNAVAILABLE")
        evidence_path = os.environ.get("AEGIS_RUNTIME_POP_CRYPTO_EVIDENCE_PATH")
        if not evidence_path:
            return _denial("RUNTIME_POP_CRYPTO_EVIDENCE_UNAVAILABLE")
        trust_policy_path = os.environ.get("AEGIS_RUNTIME_POP_TRUST_POLICY_PATH")
        if not trust_policy_path:
            return _denial("RUNTIME_POP_TRUST_POLICY_UNAVAILABLE")
        try:
            # Consequential execution uses one verifier-owned time for KeyPoP,
            # SCITT registration, EAT verification and execution attestation.
            from harness.sdk.runtime_pop_authority import (
                RuntimePoPTrustPolicy,
                SQLiteReplayStore,
                bind_execution_principal_from_crypto,
            )

            principal_payload = json.loads(raw_principal)
            if not isinstance(principal_payload, dict):
                raise ValueError("EXECUTION_PRINCIPAL_NOT_OBJECT")
            raw_pop = principal_payload.get("runtime_pop")
            if not isinstance(raw_pop, dict):
                raise ValueError("EXECUTION_RUNTIME_POP_MISSING")
            declared_mode = raw_pop.get("binding_mode")

            crypto_evidence = _load_absolute_json_object(
                evidence_path,
                path_code="RUNTIME_POP_CRYPTO_EVIDENCE_PATH_NOT_ABSOLUTE",
                object_code="RUNTIME_POP_CRYPTO_EVIDENCE_NOT_OBJECT",
            )
            trust_policy_mapping = _load_absolute_json_object(
                trust_policy_path,
                path_code="RUNTIME_POP_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                object_code="RUNTIME_POP_TRUST_POLICY_NOT_OBJECT",
            )
            trust_policy = RuntimePoPTrustPolicy.from_mapping(trust_policy_mapping)

            replay_store = None
            if declared_mode in DPOP_MODES:
                replay_db = os.environ.get("AEGIS_DPOP_REPLAY_DB")
                if not replay_db:
                    return _denial("DPOP_REPLAY_STORE_UNAVAILABLE")
                replay_store = SQLiteReplayStore(replay_db)

            verification_time_epoch = int(time.time())
            principal, crypto_receipt, trust_policy_root = bind_execution_principal_from_crypto(
                principal_payload,
                crypto_evidence,
                trust_policy=trust_policy,
                verification_time_epoch=verification_time_epoch,
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
                expected_target_digest=target_digest,
            )
            if principal_decision.outcome != VALIDATED_BINDING_EVIDENCE:
                return _principal_denial(principal_decision)

            attestation_policy_path = os.environ.get("AEGIS_RUNTIME_ATTESTATION_TRUST_POLICY_PATH")
            attestation_evidence_path = os.environ.get("AEGIS_RUNTIME_ATTESTATION_EVIDENCE_PATH")
            eat_token_path = os.environ.get("AEGIS_EAT_JWT_TOKEN_PATH")
            eat_trust_policy_path = os.environ.get("AEGIS_EAT_JWT_TRUST_POLICY_PATH")
            eat_expected_nonce = os.environ.get("AEGIS_EAT_EXPECTED_NONCE")
            authorization_receipt_root = os.environ.get("AEGIS_AUTHORIZATION_RECEIPT_ROOT")
            scitt_statement_path = os.environ.get("AEGIS_SCITT_AUTHORIZATION_STATEMENT_PATH")
            scitt_receipt_path = os.environ.get("AEGIS_SCITT_AUTHORIZATION_RECEIPT_PATH")
            scitt_trust_policy_path = os.environ.get("AEGIS_SCITT_TRUST_POLICY_PATH")
            scitt_mode = any((scitt_statement_path, scitt_receipt_path, scitt_trust_policy_path))
            eat_mode = any((eat_token_path, eat_trust_policy_path, eat_expected_nonce, authorization_receipt_root, scitt_mode))

            if scitt_mode and authorization_receipt_root:
                return _denial("RAW_AUTHORIZATION_RECEIPT_ROOT_FORBIDDEN_WITH_SCITT")
            if scitt_mode:
                if not scitt_statement_path:
                    return _denial("SCITT_AUTHORIZATION_STATEMENT_UNAVAILABLE")
                if not scitt_receipt_path:
                    return _denial("SCITT_AUTHORIZATION_RECEIPT_UNAVAILABLE")
                if not scitt_trust_policy_path:
                    return _denial("SCITT_TRUST_POLICY_UNAVAILABLE")

            if eat_mode and attestation_evidence_path:
                return _denial("RUNTIME_ATTESTATION_STRUCTURAL_EVIDENCE_FORBIDDEN_WITH_EAT")
            if (attestation_evidence_path or eat_mode) and not attestation_policy_path:
                return _denial("RUNTIME_ATTESTATION_TRUST_POLICY_UNAVAILABLE")

            if attestation_policy_path:
                from harness.sdk.attested_runtime import AttestedRuntimeTrustPolicy

                attestation_policy_mapping = _load_absolute_json_object(
                    attestation_policy_path,
                    path_code="RUNTIME_ATTESTATION_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                    object_code="RUNTIME_ATTESTATION_TRUST_POLICY_NOT_OBJECT",
                )
                attestation_policy = AttestedRuntimeTrustPolicy.from_mapping(attestation_policy_mapping)

                if eat_mode:
                    if not eat_token_path:
                        return _denial("EAT_JWT_TOKEN_UNAVAILABLE")
                    if not eat_trust_policy_path:
                        return _denial("EAT_JWT_TRUST_POLICY_UNAVAILABLE")
                    if not eat_expected_nonce:
                        return _denial("EAT_EXPECTED_NONCE_UNAVAILABLE")

                    from harness.sdk.eat_attestation_authority import verify_eat_bound_attested_runtime_for_execution
                    from harness.sdk.eat_attestation_crypto import EATJWTTrustPolicy

                    raw_eat_token = _load_absolute_text(
                        eat_token_path,
                        path_code="EAT_JWT_TOKEN_PATH_NOT_ABSOLUTE",
                        empty_code="EAT_JWT_TOKEN_EMPTY",
                    )
                    eat_policy_mapping = _load_absolute_json_object(
                        eat_trust_policy_path,
                        path_code="EAT_JWT_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                        object_code="EAT_JWT_TRUST_POLICY_NOT_OBJECT",
                    )
                    eat_policy = EATJWTTrustPolicy.from_mapping(eat_policy_mapping)

                    if scitt_mode:
                        from harness.sdk.scitt_authorization import SCITTAuthorizationTrustPolicy
                        from harness.sdk.scitt_authorization_authority import verify_scitt_authorization_for_current_runtime

                        signed_statement = _load_absolute_bytes(
                            scitt_statement_path,
                            path_code="SCITT_AUTHORIZATION_STATEMENT_PATH_NOT_ABSOLUTE",
                            empty_code="SCITT_AUTHORIZATION_STATEMENT_EMPTY",
                        )
                        scitt_receipt = _load_absolute_bytes(
                            scitt_receipt_path,
                            path_code="SCITT_AUTHORIZATION_RECEIPT_PATH_NOT_ABSOLUTE",
                            empty_code="SCITT_AUTHORIZATION_RECEIPT_EMPTY",
                        )
                        scitt_policy_mapping = _load_absolute_json_object(
                            scitt_trust_policy_path,
                            path_code="SCITT_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                            object_code="SCITT_TRUST_POLICY_NOT_OBJECT",
                        )
                        scitt_policy = SCITTAuthorizationTrustPolicy.from_mapping(scitt_policy_mapping)
                        scitt_registration_receipt = verify_scitt_authorization_for_current_runtime(
                            signed_statement=signed_statement,
                            receipt=scitt_receipt,
                            scitt_trust_policy=scitt_policy,
                            runtime_pop_crypto_receipt=crypto_receipt,
                            eat_trust_policy=eat_policy,
                            attested_runtime_trust_policy=attestation_policy,
                            verification_time_epoch=verification_time_epoch,
                        )
                        authorization_receipt_root = scitt_registration_receipt.receipt_root
                    elif not authorization_receipt_root:
                        return _denial("AUTHORIZATION_RECEIPT_ROOT_UNAVAILABLE")

                    eat_crypto_receipt, attestation_receipt = verify_eat_bound_attested_runtime_for_execution(
                        action_class=action_class,
                        runtime_principal=principal.runtime_principal,
                        runtime_pop_crypto_receipt=crypto_receipt,
                        trust_bound_key_pop_root=principal.runtime_pop.proof_root,
                        raw_eat_token=raw_eat_token,
                        eat_trust_policy=eat_policy,
                        attested_runtime_trust_policy=attestation_policy,
                        expected_nonce=eat_expected_nonce,
                        authorization_receipt_root=authorization_receipt_root,
                        session_identity=principal.session_identity,
                        action_digest=action_digest,
                        target_digest=target_digest,
                        verification_time_epoch=verification_time_epoch,
                    )
                else:
                    from harness.sdk.attested_runtime import verify_attested_runtime_for_execution

                    attestation_evidence = {}
                    if attestation_evidence_path:
                        attestation_evidence = _load_absolute_json_object(
                            attestation_evidence_path,
                            path_code="RUNTIME_ATTESTATION_EVIDENCE_PATH_NOT_ABSOLUTE",
                            object_code="RUNTIME_ATTESTATION_EVIDENCE_NOT_OBJECT",
                        )
                    attestation_receipt = verify_attested_runtime_for_execution(
                        action_class=action_class,
                        runtime_principal=principal.runtime_principal,
                        key_pop_proof_root=principal.runtime_pop.proof_root,
                        attestation_evidence=attestation_evidence,
                        trust_policy=attestation_policy,
                        session_identity=principal.session_identity,
                        action_digest=action_digest,
                        target_digest=target_digest,
                        now_epoch=verification_time_epoch,
                    )
        except Exception as exc:
            return _denial("RUNTIME_POP_CRYPTO_OR_ATTESTATION_INVALID", str(exc))

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
    if trust_policy_root is not None:
        result["runtime_pop_trust_policy_root"] = trust_policy_root
    if scitt_registration_receipt is not None:
        result["runtime_scitt_authorization_receipt_root"] = scitt_registration_receipt.receipt_root
        result["runtime_scitt_authorization_trust_policy_root"] = scitt_registration_receipt.trust_policy_root
        result["runtime_scitt_authorization_authority_granted"] = False
    if eat_crypto_receipt is not None:
        result["runtime_eat_crypto_receipt_root"] = eat_crypto_receipt.receipt_root
        result["runtime_eat_trust_policy_root"] = eat_crypto_receipt.trust_policy_root
        result["runtime_eat_subject_jkt"] = eat_crypto_receipt.subject_jkt
        result["runtime_eat_authority_granted"] = False
    if attestation_receipt is not None:
        result["runtime_attestation_execution_receipt_root"] = attestation_receipt.receipt_root
        result["runtime_attestation_trust_policy_root"] = attestation_receipt.trust_policy_root
        result["runtime_attestation_authority_granted"] = False
    return result
