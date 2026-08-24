"""Provider-neutral execution-principal binding evidence for consequential work.

This module validates *binding evidence*. It never grants authority. A caller may
use a successful result as a necessary precondition before the existing
Automaton-3 authority evaluator, but only that authority path can admit work.

`verification_state=VERIFIED` means an upstream verifier claims to have checked
its bound evidence. This reference module validates the structure and exact
bindings; it does not itself perform X.509, mTLS, DPoP, OAuth, SPIFFE/SPIRE, or
vendor credential verification.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

SCHEMA_VERSION = "1.0.0"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ZERO_HASH = "0" * 64

BEARER_ONLY = "BEARER_ONLY"
MTLS_CERT_BOUND = "MTLS_CERT_BOUND"
DPOP_CERT_BOUND = "DPOP_CERT_BOUND"
MTLS_DPOP_CERT_BOUND = "MTLS_DPOP_CERT_BOUND"
POP_BOUND_MODES = frozenset((MTLS_CERT_BOUND, DPOP_CERT_BOUND, MTLS_DPOP_CERT_BOUND))
KNOWN_BINDING_MODES = POP_BOUND_MODES | {BEARER_ONLY}

ON_BEHALF_OF_USER = "ON_BEHALF_OF_USER"
SELF_ACTING = "SELF_ACTING"
KNOWN_ACTING_MODES = frozenset((ON_BEHALF_OF_USER, SELF_ACTING))

RFC8693_TOKEN_EXCHANGE = "RFC8693_TOKEN_EXCHANGE"
RFC7523_JWT_GRANT = "RFC7523_JWT_GRANT"
ACCEPTED_DELEGATION_PROFILES = frozenset((RFC8693_TOKEN_EXCHANGE, RFC7523_JWT_GRANT))

VERIFIED = "VERIFIED"
VALIDATED_BINDING_EVIDENCE = "VALIDATED_BINDING_EVIDENCE"
DENIED = "DENIED"


class PrincipalBindingError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_hash(domain: str, value: Any) -> str:
    return hashlib.sha256(canonical_bytes({"domain": domain, "value": value})).hexdigest()


def _is_missing_principal(value: str) -> bool:
    return not isinstance(value, str) or not value.strip() or value == "NONE"


def _valid_hash(value: str) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def compute_task_action_binding(
    *,
    session_identity: str,
    action_digest: str,
    requested_capability: str,
    target_digest: str,
) -> str:
    return canonical_hash(
        "AEGIS_TASK_ACTION_BINDING_V1",
        {
            "session_identity": session_identity,
            "action_digest": action_digest,
            "requested_capability": requested_capability,
            "target_digest": target_digest,
        },
    )


@dataclass(frozen=True)
class RuntimePoPVerification:
    runtime_principal: str
    binding_mode: str
    verification_state: str
    verifier_identity: str
    proof_root: str
    evidence_ref: str
    generation: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimePoPVerification":
        return cls(
            runtime_principal=str(value["runtime_principal"]),
            binding_mode=str(value["binding_mode"]),
            verification_state=str(value["verification_state"]),
            verifier_identity=str(value["verifier_identity"]),
            proof_root=str(value["proof_root"]),
            evidence_ref=str(value["evidence_ref"]),
            generation=int(value["generation"]),
        )


@dataclass(frozen=True)
class DelegationBinding:
    user_principal: str
    agent_principal: str
    downstream_audience: str
    requested_scopes: tuple[str, ...]
    exchange_profile: str
    authorization_server: str
    verification_state: str
    evidence_root: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DelegationBinding":
        raw_scopes = value.get("requested_scopes", ())
        if not isinstance(raw_scopes, (list, tuple)):
            raise PrincipalBindingError("DELEGATION_SCOPES_INVALID")
        return cls(
            user_principal=str(value["user_principal"]),
            agent_principal=str(value["agent_principal"]),
            downstream_audience=str(value["downstream_audience"]),
            requested_scopes=tuple(str(item) for item in raw_scopes),
            exchange_profile=str(value["exchange_profile"]),
            authorization_server=str(value["authorization_server"]),
            verification_state=str(value["verification_state"]),
            evidence_root=str(value["evidence_root"]),
        )


@dataclass(frozen=True)
class ExecutionPrincipalBinding:
    schema_version: str
    acting_mode: str
    user_principal: str
    agent_principal: str
    runtime_principal: str
    session_identity: str
    requested_capability: str
    action_digest: str
    target_digest: str
    task_action_binding: str
    runtime_pop: RuntimePoPVerification
    delegation: DelegationBinding | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExecutionPrincipalBinding":
        if not isinstance(value, Mapping):
            raise PrincipalBindingError("EXECUTION_PRINCIPAL_NOT_OBJECT")
        raw_pop = value.get("runtime_pop")
        if not isinstance(raw_pop, Mapping):
            raise PrincipalBindingError("RUNTIME_POP_MISSING")
        raw_delegation = value.get("delegation")
        delegation = None
        if raw_delegation is not None:
            if not isinstance(raw_delegation, Mapping):
                raise PrincipalBindingError("DELEGATION_INVALID")
            delegation = DelegationBinding.from_mapping(raw_delegation)
        return cls(
            schema_version=str(value["schema_version"]),
            acting_mode=str(value["acting_mode"]),
            user_principal=str(value.get("user_principal", "NONE")),
            agent_principal=str(value["agent_principal"]),
            runtime_principal=str(value["runtime_principal"]),
            session_identity=str(value["session_identity"]),
            requested_capability=str(value["requested_capability"]),
            action_digest=str(value["action_digest"]),
            target_digest=str(value["target_digest"]),
            task_action_binding=str(value["task_action_binding"]),
            runtime_pop=RuntimePoPVerification.from_mapping(raw_pop),
            delegation=delegation,
        )

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_EXECUTION_PRINCIPAL_BINDING_V1", asdict(self))


@dataclass(frozen=True)
class PrincipalBindingDecision:
    outcome: str
    denial_codes: tuple[str, ...]
    binding_root: str
    decision_root: str
    authority_granted: bool = False


@dataclass(frozen=True)
class CredentialTransition:
    previous_mode: str
    next_mode: str
    classification: str
    requires_new_admission: bool


def detect_credential_downgrade(previous_mode: str, next_mode: str) -> CredentialTransition:
    if previous_mode not in KNOWN_BINDING_MODES or next_mode not in KNOWN_BINDING_MODES:
        return CredentialTransition(
            previous_mode=previous_mode,
            next_mode=next_mode,
            classification="UNKNOWN_BINDING_TRANSITION",
            requires_new_admission=True,
        )
    if previous_mode in POP_BOUND_MODES and next_mode == BEARER_ONLY:
        return CredentialTransition(
            previous_mode=previous_mode,
            next_mode=next_mode,
            classification="SECURITY_RELEVANT_DOWNGRADE",
            requires_new_admission=True,
        )
    return CredentialTransition(
        previous_mode=previous_mode,
        next_mode=next_mode,
        classification="NO_BEARER_DOWNGRADE",
        requires_new_admission=False,
    )


def _decision(binding: ExecutionPrincipalBinding, denial_codes: list[str]) -> PrincipalBindingDecision:
    codes = tuple(sorted(set(denial_codes)))
    try:
        binding_root = binding.root
    except Exception:
        binding_root = ZERO_HASH
    body = {
        "outcome": VALIDATED_BINDING_EVIDENCE if not codes else DENIED,
        "denial_codes": list(codes),
        "binding_root": binding_root,
        "authority_granted": False,
    }
    return PrincipalBindingDecision(
        outcome=body["outcome"],
        denial_codes=codes,
        binding_root=binding_root,
        decision_root=canonical_hash("AEGIS_EXECUTION_PRINCIPAL_DECISION_V1", body),
        authority_granted=False,
    )


def evaluate_execution_principal(
    binding: ExecutionPrincipalBinding,
    *,
    action_class: str,
    expected_agent_principal: str,
    expected_runtime_principal: str,
    expected_session_identity: str,
    expected_action_digest: str,
    expected_capability: str,
    expected_target_digest: str,
) -> PrincipalBindingDecision:
    """Validate exact principal/binding evidence without granting authority."""
    denial: list[str] = []

    if binding.schema_version != SCHEMA_VERSION:
        denial.append("EXECUTION_PRINCIPAL_SCHEMA_UNSUPPORTED")
    if binding.acting_mode not in KNOWN_ACTING_MODES:
        denial.append("ACTING_MODE_UNSUPPORTED")

    if _is_missing_principal(binding.agent_principal):
        denial.append("AGENT_PRINCIPAL_MISSING")
    elif binding.agent_principal != expected_agent_principal:
        denial.append("AGENT_PRINCIPAL_MISMATCH")

    if _is_missing_principal(binding.runtime_principal):
        denial.append("RUNTIME_PRINCIPAL_MISSING")
    elif binding.runtime_principal != expected_runtime_principal:
        denial.append("RUNTIME_PRINCIPAL_MISMATCH")

    if binding.session_identity != expected_session_identity:
        denial.append("SESSION_IDENTITY_MISMATCH")
    if binding.action_digest != expected_action_digest:
        denial.append("ACTION_DIGEST_MISMATCH")
    if binding.requested_capability != expected_capability:
        denial.append("CAPABILITY_BINDING_MISMATCH")
    if binding.target_digest != expected_target_digest:
        denial.append("TARGET_BINDING_MISMATCH")

    if not _valid_hash(binding.action_digest):
        denial.append("ACTION_DIGEST_INVALID")
    if not _valid_hash(binding.target_digest):
        denial.append("TARGET_DIGEST_INVALID")
    if not _valid_hash(binding.task_action_binding):
        denial.append("TASK_ACTION_BINDING_INVALID")
    expected_task_binding = compute_task_action_binding(
        session_identity=binding.session_identity,
        action_digest=binding.action_digest,
        requested_capability=binding.requested_capability,
        target_digest=binding.target_digest,
    )
    if binding.task_action_binding != expected_task_binding:
        denial.append("TASK_ACTION_BINDING_MISMATCH")

    pop = binding.runtime_pop
    if pop.binding_mode not in KNOWN_BINDING_MODES:
        denial.append("RUNTIME_POP_MODE_UNSUPPORTED")
    if pop.runtime_principal != binding.runtime_principal:
        denial.append("RUNTIME_POP_SUBJECT_MISMATCH")
    if pop.verification_state != VERIFIED:
        denial.append("RUNTIME_POP_NOT_VERIFIED")
    if pop.proof_root == ZERO_HASH:
        denial.append("RUNTIME_POP_PROOF_MISSING")
    elif not _valid_hash(pop.proof_root):
        denial.append("RUNTIME_POP_PROOF_INVALID")
    if _is_missing_principal(pop.verifier_identity):
        denial.append("RUNTIME_POP_VERIFIER_MISSING")
    if _is_missing_principal(pop.evidence_ref):
        denial.append("RUNTIME_POP_EVIDENCE_MISSING")
    if pop.generation < 0:
        denial.append("RUNTIME_POP_GENERATION_INVALID")

    # D3/D4 are consequential/external-effect classes in the current AEGIS
    # consequence policy. Bearer-only credentials cannot satisfy RuntimePoP.
    if action_class in ("D3", "D4") and pop.binding_mode == BEARER_ONLY:
        denial.append("RUNTIME_POP_REQUIRED")

    if binding.acting_mode == ON_BEHALF_OF_USER:
        if _is_missing_principal(binding.user_principal):
            denial.append("USER_PRINCIPAL_MISSING")
        if binding.delegation is None:
            denial.append("DELEGATION_MISSING")
        else:
            delegated = binding.delegation
            if delegated.user_principal != binding.user_principal:
                denial.append("DELEGATION_USER_MISMATCH")
            if delegated.agent_principal != binding.agent_principal:
                denial.append("DELEGATION_AGENT_MISMATCH")
            if delegated.verification_state != VERIFIED:
                denial.append("DELEGATION_NOT_VERIFIED")
            if delegated.exchange_profile not in ACCEPTED_DELEGATION_PROFILES:
                denial.append("DELEGATION_PROFILE_UNSUPPORTED")
            if _is_missing_principal(delegated.downstream_audience):
                denial.append("DELEGATION_AUDIENCE_MISSING")
            if not delegated.requested_scopes or any(not scope.strip() for scope in delegated.requested_scopes):
                denial.append("DELEGATION_SCOPE_MISSING")
            if _is_missing_principal(delegated.authorization_server):
                denial.append("DELEGATION_AUTHORIZATION_SERVER_MISSING")
            if delegated.evidence_root == ZERO_HASH:
                denial.append("DELEGATION_EVIDENCE_MISSING")
            elif not _valid_hash(delegated.evidence_root):
                denial.append("DELEGATION_EVIDENCE_INVALID")
    elif binding.acting_mode == SELF_ACTING:
        if not _is_missing_principal(binding.user_principal) or binding.delegation is not None:
            denial.append("SELF_ACTING_USER_AUTHORITY_PRESENT")

    return _decision(binding, denial)
