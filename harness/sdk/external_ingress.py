"""Governed external-ingress adapters for AEGIS Automaton-3.

This module converts externally verified provider inputs into existing AEGIS
EventEnvelope / ExecutionIdentityEnvelope objects without granting authority.

Security contract:
- verification receipts are observations, never grants;
- Resend ingress is metadata-only (no email body/attachment bytes);
- WorkOS permissions are a ceiling that must map to an existing AEGIS capability;
- `observed_authority` is always zero at the identity boundary;
- consequential action still requires AuthorityEvaluator policy/registry/approval.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    ZERO_HASH,
    EventEnvelope,
    ExecutionIdentityEnvelope,
    SovereignExecutionError,
    canonical_bytes,
    canonical_hash,
    compute_workspace_binding,
    sha256_hex,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")
_RESEND_PROVIDER = "resend"
_RESEND_METHOD = "resend.webhooks.verify"
_WORKOS_PROVIDER = "workos"
_WORKOS_METHOD = "oidc-jwt-signature+claims"
_VERIFIED = "VERIFIED"
_NONE = "NONE"


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_SHA256")


def _require_id(name: str, value: str) -> str:
    if not isinstance(value, str) or not value or not _SAFE_ID_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_ID")
    return value


def _require_text(name: str, value: Any, *, maximum_bytes: int = 4096) -> str:
    if not isinstance(value, str) or not value:
        raise SovereignExecutionError(f"{name}:INVALID_TEXT")
    encoded = value.encode("utf-8")
    if len(encoded) > maximum_bytes or any(
        ord(ch) < 32 and ch not in "\t\n\r" for ch in value
    ):
        raise SovereignExecutionError(f"{name}:INVALID_TEXT")
    return value


def _raw_bytes(raw_body: bytes | str) -> bytes:
    if isinstance(raw_body, bytes):
        return raw_body
    if isinstance(raw_body, str):
        return raw_body.encode("utf-8")
    raise SovereignExecutionError("EXTERNAL_RAW_BODY_INVALID")


@dataclass(frozen=True)
class ExternalVerificationReceipt:
    """Point-in-time evidence that an upstream verifier accepted provider input.

    This is deliberately not a cryptographic signature and cannot grant AEGIS
    authority. `observed_input_digest` must bind the exact bytes/claims that the
    provider verifier accepted.
    """

    schema_version: str
    provider: str
    verification_method: str
    subject: str
    observed_input_digest: str
    verifier_identity: str
    evidence_reference: str
    outcome: str = _VERIFIED

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("EXTERNAL_VERIFICATION_SCHEMA_UNSUPPORTED")
        for name in (
            "provider",
            "verification_method",
            "subject",
            "verifier_identity",
            "evidence_reference",
        ):
            _require_id(name, getattr(self, name))
        _require_hash("observed_input_digest", self.observed_input_digest)
        if self.outcome != _VERIFIED:
            raise SovereignExecutionError("EXTERNAL_VERIFICATION_NOT_VERIFIED")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EXTERNAL_VERIFICATION_V1", asdict(self))


@dataclass(frozen=True)
class ExternalIdentityCandidate:
    """Provider identity projected into AEGIS with zero authority effect."""

    identity: ExecutionIdentityEnvelope
    provider: str
    principal_id: str
    external_permissions: tuple[str, ...]
    mapped_capabilities: tuple[str, ...]
    verification_root: str
    authority_effect: str = _NONE

    def validate(self) -> None:
        _require_id("provider", self.provider)
        _require_id("principal_id", self.principal_id)
        _require_hash("verification_root", self.verification_root)
        if self.authority_effect != _NONE:
            raise SovereignExecutionError(
                "EXTERNAL_IDENTITY_AUTHORITY_EFFECT_FORBIDDEN"
            )
        for permission in self.external_permissions:
            _require_id("external_permission", permission)
        for capability in self.mapped_capabilities:
            _require_id("mapped_capability", capability)
        _ = self.identity.root
        if self.identity.observed_authority != "0.000000":
            raise SovereignExecutionError("EXTERNAL_IDENTITY_NONZERO_AUTHORITY")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash(
            "AEGIS_EXTERNAL_IDENTITY_CANDIDATE_V1",
            {
                "identity_root": self.identity.root,
                "provider": self.provider,
                "principal_id": self.principal_id,
                "external_permissions": self.external_permissions,
                "mapped_capabilities": self.mapped_capabilities,
                "verification_root": self.verification_root,
                "authority_effect": self.authority_effect,
            },
        )


def resend_observed_body_digest(raw_body: bytes | str) -> str:
    """Digest the exact raw body that Resend/Svix signature verification consumed."""
    return sha256_hex(_raw_bytes(raw_body))


def build_resend_email_received_event(
    *,
    raw_body: bytes | str,
    verification: ExternalVerificationReceipt,
    routing_domain: str,
    parent_event: str = ZERO_HASH,
    sequence: int = 0,
) -> EventEnvelope:
    """Project a verified Resend `email.received` webhook into an AEGIS event.

    The caller must first verify the *same raw body* with Resend's webhook
    verifier (Svix headers + webhook secret), then create a verification receipt.
    This adapter never accepts or stores the secret and never places email body
    text or attachment bytes into the event.
    """

    routing_domain = _require_id("routing_domain", routing_domain)
    if not routing_domain.startswith("quarantine:"):
        raise SovereignExecutionError("RESEND_ROUTING_NOT_QUARANTINED")

    body = _raw_bytes(raw_body)
    verification.validate()
    if (
        verification.provider != _RESEND_PROVIDER
        or verification.verification_method != _RESEND_METHOD
    ):
        raise SovereignExecutionError("RESEND_VERIFICATION_RECEIPT_MISMATCH")
    body_digest = sha256_hex(body)
    if verification.observed_input_digest != body_digest:
        raise SovereignExecutionError("RESEND_VERIFIED_BODY_DIGEST_MISMATCH")

    try:
        parsed = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SovereignExecutionError("RESEND_WEBHOOK_JSON_INVALID") from exc
    if not isinstance(parsed, Mapping) or parsed.get("type") != "email.received":
        raise SovereignExecutionError("RESEND_EVENT_TYPE_NOT_ADMITTED")
    data = parsed.get("data")
    if not isinstance(data, Mapping):
        raise SovereignExecutionError("RESEND_EVENT_DATA_INVALID")

    email_id = _require_id("resend.email_id", data.get("email_id"))
    sender = _require_text("resend.from", data.get("from"), maximum_bytes=1024)
    subject = data.get("subject", "")
    if not isinstance(subject, str):
        raise SovereignExecutionError("RESEND_SUBJECT_INVALID")
    recipients = data.get("to")
    if (
        not isinstance(recipients, list)
        or not recipients
        or any(not isinstance(item, str) or not item for item in recipients)
    ):
        raise SovereignExecutionError("RESEND_RECIPIENTS_INVALID")
    attachments = data.get("attachments", [])
    if not isinstance(attachments, list):
        raise SovereignExecutionError("RESEND_ATTACHMENTS_INVALID")

    message_id = data.get("message_id")
    if message_id is not None and not isinstance(message_id, str):
        raise SovereignExecutionError("RESEND_MESSAGE_ID_INVALID")

    safe_metadata = {
        "provider": _RESEND_PROVIDER,
        "event_type": "email.received",
        "delivery_id": verification.subject,
        "email_id": email_id,
        "raw_body_sha256": body_digest,
        "message_id_digest": canonical_hash(
            "AEGIS_RESEND_MESSAGE_ID_V1", message_id or ""
        ),
        "from_digest": canonical_hash("AEGIS_RESEND_FROM_V1", sender),
        "recipient_digests": tuple(
            sorted(
                canonical_hash("AEGIS_RESEND_RECIPIENT_V1", item)
                for item in recipients
            )
        ),
        "subject_digest": sha256_hex(subject.encode("utf-8")),
        "attachment_count": len(attachments),
        "attachment_metadata_digest": canonical_hash(
            "AEGIS_RESEND_ATTACHMENTS_V1", attachments
        ),
    }
    payload = {
        "content_type": "application/vnd.aegis.resend-email-received+json",
        "data": safe_metadata,
    }
    payload_digest = sha256_hex(canonical_bytes(payload))
    sender_root = canonical_hash(
        "AEGIS_EXTERNAL_PRINCIPAL_V1",
        {
            "provider": _RESEND_PROVIDER,
            "delivery_id": verification.subject,
            "email_id": email_id,
        },
    )

    event = EventEnvelope(
        sender_identity_root=sender_root,
        recipient_or_routing_domain=routing_domain,
        source_state=verification.root,
        capability_request="external.email.observe",
        payload_schema="resend.email.received.v1",
        payload=payload,
        payload_digest=payload_digest,
        provenance=_RESEND_METHOD,
        policy_decision=ZERO_HASH,
        parent_event=parent_event,
        sequence=sequence,
        receipt_reference=verification.root,
    )
    event.validate(expected_sequence=sequence, expected_parent=parent_event)
    return event


def normalize_workos_agent_claims(
    claims: Mapping[str, Any],
    *,
    expected_issuer: str,
    expected_audience: str,
) -> dict[str, Any]:
    """Validate the authority-relevant subset of already verified WorkOS claims."""

    if not isinstance(claims, Mapping):
        raise SovereignExecutionError("WORKOS_CLAIMS_INVALID")
    if claims.get("sub_profile") != "ai_agent":
        raise SovereignExecutionError("WORKOS_NOT_AGENT_TOKEN")
    if claims.get("iss") != expected_issuer:
        raise SovereignExecutionError("WORKOS_ISSUER_MISMATCH")
    if claims.get("aud") != expected_audience:
        raise SovereignExecutionError("WORKOS_AUDIENCE_MISMATCH")

    subject = _require_id("workos.sub", claims.get("sub"))
    session = _require_id("workos.sid", claims.get("sid"))
    token_id = _require_id("workos.jti", claims.get("jti"))
    blueprint = _require_id(
        "workos.agent_blueprint_id", claims.get("agent_blueprint_id")
    )
    organization = _require_id("workos.org_id", claims.get("org_id"))

    permissions_raw = claims.get("permissions")
    if not isinstance(permissions_raw, list) or any(
        not isinstance(item, str) for item in permissions_raw
    ):
        raise SovereignExecutionError("WORKOS_PERMISSIONS_INVALID")
    permissions = tuple(
        sorted(
            set(
                _require_id("workos.permission", item)
                for item in permissions_raw
            )
        )
    )

    delegated_user = _NONE
    act = claims.get("act")
    if act is not None:
        if not isinstance(act, Mapping) or act.get("sub_profile") != "user":
            raise SovereignExecutionError("WORKOS_DELEGATION_INVALID")
        delegated_user = _require_id("workos.delegating_user", act.get("sub"))

    intent_digest = ZERO_HASH
    intent = claims.get("intent")
    if intent is not None:
        if not isinstance(intent, Mapping):
            raise SovereignExecutionError("WORKOS_INTENT_INVALID")
        text = intent.get("text")
        if not isinstance(text, str):
            raise SovereignExecutionError("WORKOS_INTENT_INVALID")
        intent_digest = canonical_hash("AEGIS_WORKOS_INTENT_V1", text)

    return {
        "issuer": expected_issuer,
        "audience": expected_audience,
        "subject": subject,
        "session": session,
        "token_id": token_id,
        "blueprint": blueprint,
        "organization": organization,
        "permissions": permissions,
        "delegated_user": delegated_user,
        "intent_digest": intent_digest,
    }


def workos_verified_claims_digest(
    claims: Mapping[str, Any],
    *,
    expected_issuer: str,
    expected_audience: str,
) -> str:
    normalized = normalize_workos_agent_claims(
        claims,
        expected_issuer=expected_issuer,
        expected_audience=expected_audience,
    )
    return canonical_hash("AEGIS_WORKOS_VERIFIED_AGENT_CLAIMS_V1", normalized)


def build_workos_agent_identity_candidate(
    *,
    claims: Mapping[str, Any],
    verification: ExternalVerificationReceipt,
    expected_issuer: str,
    expected_audience: str,
    permission_to_capability: Mapping[str, str],
    requested_capability: str,
    repository_identity: str,
    source_commit: str,
    branch_or_ref: str,
    project_identity: str,
    parent_state_root: str,
    skills_root: str,
    registry_root: str,
    policy_root: str,
    model_identity: str,
    physical_executor: str,
    tool_identity: str,
    workflow_identity: str,
    authority_domain: str,
    requested_action: Mapping[str, Any],
    expected_pre_state: str,
    approval_reference: str = _NONE,
) -> ExternalIdentityCandidate:
    """Map a verified WorkOS Agent Auth principal into AEGIS identity.

    WorkOS permissions only determine whether the requested capability is inside
    the external token's ceiling. They do not satisfy AEGIS policy, registry,
    evidence, lease, idempotency, or operator-approval requirements.
    """

    verification.validate()
    if (
        verification.provider != _WORKOS_PROVIDER
        or verification.verification_method != _WORKOS_METHOD
    ):
        raise SovereignExecutionError("WORKOS_VERIFICATION_RECEIPT_MISMATCH")

    normalized = normalize_workos_agent_claims(
        claims,
        expected_issuer=expected_issuer,
        expected_audience=expected_audience,
    )
    if verification.subject != normalized["subject"]:
        raise SovereignExecutionError("WORKOS_VERIFICATION_SUBJECT_MISMATCH")
    claims_digest = canonical_hash(
        "AEGIS_WORKOS_VERIFIED_AGENT_CLAIMS_V1", normalized
    )
    if verification.observed_input_digest != claims_digest:
        raise SovereignExecutionError("WORKOS_VERIFIED_CLAIMS_DIGEST_MISMATCH")

    permission_map: dict[str, str] = {}
    for permission, capability in permission_to_capability.items():
        permission_map[_require_id("workos.permission_map_key", permission)] = (
            _require_id("workos.permission_map_value", capability)
        )
    requested_capability = _require_id(
        "requested_capability", requested_capability
    )
    mapped_capabilities = tuple(
        sorted(
            {
                permission_map[permission]
                for permission in normalized["permissions"]
                if permission in permission_map
            }
        )
    )
    if requested_capability not in mapped_capabilities:
        raise SovereignExecutionError(
            "WORKOS_SCOPE_DOES_NOT_MAP_TO_CAPABILITY"
        )

    workspace_binding = compute_workspace_binding(
        repository_remote=repository_identity,
        repository_root=".",
        project_identity=project_identity,
        source_commit=source_commit,
        operator_authorization=approval_reference,
    )
    input_digest = canonical_hash(
        "AEGIS_WORKOS_AGENT_PRINCIPAL_V1",
        {"verification_root": verification.root, **normalized},
    )
    action_digest = canonical_hash(
        "AEGIS_REQUESTED_ACTION_V1", dict(requested_action)
    )
    delegated = normalized["delegated_user"] != _NONE

    identity = ExecutionIdentityEnvelope(
        schema_version=SCHEMA_VERSION,
        repository_identity=repository_identity,
        repository_root=".",
        source_commit=source_commit,
        branch_or_ref=branch_or_ref,
        project_identity=project_identity,
        workspace_root=".",
        workspace_binding=workspace_binding,
        parent_state_root=parent_state_root,
        skills_root=skills_root,
        registry_root=registry_root,
        policy_root=policy_root,
        actor_class=(
            "external-agent-delegated"
            if delegated
            else "external-agent-autonomous"
        ),
        actor_identity=f"workos:{normalized['subject']}",
        model_identity=model_identity,
        session_identity=f"workos:{normalized['session']}",
        physical_executor=physical_executor,
        tool_identity=tool_identity,
        workflow_identity=workflow_identity,
        authority_domain=authority_domain,
        requested_capability=requested_capability,
        observed_authority="0.000000",
        approval_reference=approval_reference,
        input_digest=input_digest,
        action_digest=action_digest,
        expected_pre_state=expected_pre_state,
        deterministic_nonce=f"workos-jti:{normalized['token_id']}",
    )
    _ = identity.root
    candidate = ExternalIdentityCandidate(
        identity=identity,
        provider=_WORKOS_PROVIDER,
        principal_id=normalized["subject"],
        external_permissions=normalized["permissions"],
        mapped_capabilities=mapped_capabilities,
        verification_root=verification.root,
    )
    candidate.validate()
    return candidate
