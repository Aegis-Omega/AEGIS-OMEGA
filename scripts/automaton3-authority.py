#!/usr/bin/env python3
"""Single CLI boundary for Automaton-3 authority evaluation."""
from __future__ import annotations

import argparse
import json
import sys
import time
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
    body = {
        "schema_version": "1.0.0",
        "outcome": "DENIED",
        "denial_codes": [code],
        "detail_digest": canonical_hash("AEGIS_DENIAL_DETAIL_V1", detail),
    }
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


def _load_absolute_json_object(path_value: str, *, path_code: str, object_code: str) -> dict:
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


def evaluate(
    payload: dict,
    *,
    runtime_pop_trust_policy_path: str | None = None,
    dpop_replay_db: str | None = None,
    verification_time_epoch: int | None = None,
    runtime_attestation_evidence_path: str | None = None,
    runtime_attestation_trust_policy_path: str | None = None,
    eat_jwt_token_path: str | None = None,
    eat_jwt_trust_policy_path: str | None = None,
    eat_expected_nonce: str | None = None,
    authorization_receipt_root: str | None = None,
    scitt_authorization_statement_path: str | None = None,
    scitt_authorization_receipt_path: str | None = None,
    scitt_trust_policy_path: str | None = None,
) -> dict:
    try:
        identity = ExecutionIdentityEnvelope(**payload["identity"])
        identity_root = identity.root
    except Exception as exc:
        return deny("IDENTITY_INVALID", str(exc))

    request_payload = payload.get("request", {})
    action = payload.get("action", {})
    action_digest = canonical_hash("AEGIS_REQUESTED_ACTION_V1", action)
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
    target_digest = canonical_hash("AEGIS_AUTHORITY_TARGET_V1", target)

    if identity.action_digest != action_digest:
        return deny("ACTION_DIGEST_MISMATCH")
    if identity.requested_capability != requested_capability:
        return deny("IDENTITY_CAPABILITY_MISMATCH")
    if identity.authority_domain != authority_domain:
        return deny("IDENTITY_AUTHORITY_DOMAIN_MISMATCH")
    if identity.tool_identity != tool:
        return deny("IDENTITY_TOOL_MISMATCH")

    principal_decision = None
    crypto_receipt = None
    trust_policy_root = None
    attestation_receipt = None
    eat_crypto_receipt = None
    scitt_registration_receipt = None
    if action_class in EXECUTION_PRINCIPAL_CLASSES:
        raw_principal = payload.get("execution_principal")
        if raw_principal is None:
            return deny("EXECUTION_PRINCIPAL_UNAVAILABLE")
        if not isinstance(raw_principal, dict):
            return deny("EXECUTION_PRINCIPAL_INVALID")
        crypto_evidence = payload.get("runtime_pop_crypto_evidence")
        if crypto_evidence is None:
            return deny("RUNTIME_POP_CRYPTO_EVIDENCE_UNAVAILABLE")
        if not isinstance(crypto_evidence, dict):
            return deny("RUNTIME_POP_CRYPTO_EVIDENCE_INVALID")
        if not runtime_pop_trust_policy_path:
            return deny("RUNTIME_POP_TRUST_POLICY_UNAVAILABLE")
        try:
            from harness.sdk.runtime_pop_authority import (
                RuntimePoPTrustPolicy,
                SQLiteReplayStore,
                bind_execution_principal_from_crypto,
            )

            trust_policy_mapping = _load_absolute_json_object(
                runtime_pop_trust_policy_path,
                path_code="RUNTIME_POP_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                object_code="RUNTIME_POP_TRUST_POLICY_NOT_OBJECT",
            )
            trust_policy = RuntimePoPTrustPolicy.from_mapping(trust_policy_mapping)

            raw_pop = raw_principal.get("runtime_pop")
            if not isinstance(raw_pop, dict):
                raise ValueError("EXECUTION_RUNTIME_POP_MISSING")
            declared_mode = raw_pop.get("binding_mode")
            replay_store = None
            if declared_mode in DPOP_MODES:
                if not dpop_replay_db:
                    return deny("DPOP_REPLAY_STORE_UNAVAILABLE")
                replay_store = SQLiteReplayStore(dpop_replay_db)

            verified_at = int(time.time()) if verification_time_epoch is None else verification_time_epoch
            principal, crypto_receipt, trust_policy_root = bind_execution_principal_from_crypto(
                raw_principal,
                crypto_evidence,
                trust_policy=trust_policy,
                verification_time_epoch=verified_at,
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
                return deny_principal(principal_decision)

            scitt_mode = any((
                scitt_authorization_statement_path,
                scitt_authorization_receipt_path,
                scitt_trust_policy_path,
            ))
            eat_mode = any((
                eat_jwt_token_path,
                eat_jwt_trust_policy_path,
                eat_expected_nonce,
                authorization_receipt_root,
                scitt_mode,
            ))

            if scitt_mode and authorization_receipt_root:
                return deny("RAW_AUTHORIZATION_RECEIPT_ROOT_FORBIDDEN_WITH_SCITT")
            if scitt_mode:
                if not scitt_authorization_statement_path:
                    return deny("SCITT_AUTHORIZATION_STATEMENT_UNAVAILABLE")
                if not scitt_authorization_receipt_path:
                    return deny("SCITT_AUTHORIZATION_RECEIPT_UNAVAILABLE")
                if not scitt_trust_policy_path:
                    return deny("SCITT_TRUST_POLICY_UNAVAILABLE")

            if eat_mode and runtime_attestation_evidence_path:
                return deny("RUNTIME_ATTESTATION_STRUCTURAL_EVIDENCE_FORBIDDEN_WITH_EAT")
            if (runtime_attestation_evidence_path or eat_mode) and not runtime_attestation_trust_policy_path:
                return deny("RUNTIME_ATTESTATION_TRUST_POLICY_UNAVAILABLE")

            if runtime_attestation_trust_policy_path:
                from harness.sdk.attested_runtime import AttestedRuntimeTrustPolicy

                attestation_policy_mapping = _load_absolute_json_object(
                    runtime_attestation_trust_policy_path,
                    path_code="RUNTIME_ATTESTATION_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                    object_code="RUNTIME_ATTESTATION_TRUST_POLICY_NOT_OBJECT",
                )
                attestation_policy = AttestedRuntimeTrustPolicy.from_mapping(attestation_policy_mapping)

                if eat_mode:
                    if not eat_jwt_token_path:
                        return deny("EAT_JWT_TOKEN_UNAVAILABLE")
                    if not eat_jwt_trust_policy_path:
                        return deny("EAT_JWT_TRUST_POLICY_UNAVAILABLE")
                    if not eat_expected_nonce:
                        return deny("EAT_EXPECTED_NONCE_UNAVAILABLE")

                    from harness.sdk.eat_attestation_authority import verify_eat_bound_attested_runtime_for_execution
                    from harness.sdk.eat_attestation_crypto import EATJWTTrustPolicy

                    raw_eat_token = _load_absolute_text(
                        eat_jwt_token_path,
                        path_code="EAT_JWT_TOKEN_PATH_NOT_ABSOLUTE",
                        empty_code="EAT_JWT_TOKEN_EMPTY",
                    )
                    eat_policy_mapping = _load_absolute_json_object(
                        eat_jwt_trust_policy_path,
                        path_code="EAT_JWT_TRUST_POLICY_PATH_NOT_ABSOLUTE",
                        object_code="EAT_JWT_TRUST_POLICY_NOT_OBJECT",
                    )
                    eat_policy = EATJWTTrustPolicy.from_mapping(eat_policy_mapping)

                    if scitt_mode:
                        from harness.sdk.scitt_authorization import SCITTAuthorizationTrustPolicy
                        from harness.sdk.scitt_authorization_authority import verify_scitt_authorization_for_current_runtime

                        signed_statement = _load_absolute_bytes(
                            scitt_authorization_statement_path,
                            path_code="SCITT_AUTHORIZATION_STATEMENT_PATH_NOT_ABSOLUTE",
                            empty_code="SCITT_AUTHORIZATION_STATEMENT_EMPTY",
                        )
                        scitt_receipt = _load_absolute_bytes(
                            scitt_authorization_receipt_path,
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
                            verification_time_epoch=verified_at,
                        )
                        authorization_receipt_root = scitt_registration_receipt.receipt_root
                    elif not authorization_receipt_root:
                        return deny("AUTHORIZATION_RECEIPT_ROOT_UNAVAILABLE")

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
                        verification_time_epoch=verified_at,
                    )
                else:
                    from harness.sdk.attested_runtime import verify_attested_runtime_for_execution

                    attestation_evidence = {}
                    if runtime_attestation_evidence_path:
                        attestation_evidence = _load_absolute_json_object(
                            runtime_attestation_evidence_path,
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
                        now_epoch=verified_at,
                    )
        except Exception as exc:
            return deny("RUNTIME_POP_CRYPTO_OR_ATTESTATION_INVALID", str(exc))

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
    except Exception as exc:
        return deny("AUTHORITY_EVALUATION_ERROR", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate"])
    parser.add_argument("--input", default="-")
    parser.add_argument("--output", default="-")
    parser.add_argument("--runtime-pop-trust-policy", default=None)
    parser.add_argument("--dpop-replay-db", default=None)
    parser.add_argument("--verification-time-epoch", type=int, default=None)
    parser.add_argument("--runtime-attestation-evidence", default=None)
    parser.add_argument("--runtime-attestation-trust-policy", default=None)
    parser.add_argument("--eat-jwt-token", default=None)
    parser.add_argument("--eat-jwt-trust-policy", default=None)
    parser.add_argument("--eat-expected-nonce", default=None)
    parser.add_argument("--authorization-receipt-root", default=None)
    parser.add_argument("--scitt-authorization-statement", default=None)
    parser.add_argument("--scitt-authorization-receipt", default=None)
    parser.add_argument("--scitt-trust-policy", default=None)
    args = parser.parse_args()
    raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        result = deny("INPUT_JSON_MALFORMED", str(exc))
    else:
        result = evaluate(
            payload,
            runtime_pop_trust_policy_path=args.runtime_pop_trust_policy,
            dpop_replay_db=args.dpop_replay_db,
            verification_time_epoch=args.verification_time_epoch,
            runtime_attestation_evidence_path=args.runtime_attestation_evidence,
            runtime_attestation_trust_policy_path=args.runtime_attestation_trust_policy,
            eat_jwt_token_path=args.eat_jwt_token,
            eat_jwt_trust_policy_path=args.eat_jwt_trust_policy,
            eat_expected_nonce=args.eat_expected_nonce,
            authorization_receipt_root=args.authorization_receipt_root,
            scitt_authorization_statement_path=args.scitt_authorization_statement,
            scitt_authorization_receipt_path=args.scitt_authorization_receipt,
            scitt_trust_policy_path=args.scitt_trust_policy,
        )
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output == "-":
        sys.stdout.write(rendered)
    else:
        Path(args.output).write_text(rendered, encoding="utf-8")
    return 0 if result.get("outcome") == ADMITTED else 3


if __name__ == "__main__":
    raise SystemExit(main())
