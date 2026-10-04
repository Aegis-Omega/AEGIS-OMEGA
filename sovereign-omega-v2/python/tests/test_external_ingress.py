#!/usr/bin/env python3
"""External-ingress quarantine, identity, and scope-boundary tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.external_ingress import (  # noqa: E402
    ExternalVerificationReceipt,
    build_resend_email_received_event,
    build_workos_agent_identity_candidate,
    resend_observed_body_digest,
    workos_verified_claims_digest,
)
from harness.sdk.sovereign_execution import (  # noqa: E402
    SCHEMA_VERSION,
    ZERO_HASH,
    SovereignExecutionError,
)

REMOTE = "https://github.com/Aegis-Omega/AEGIS-OMEGA.git"
COMMIT = "a" * 40
HASH = "1" * 64


def raw_email(subject: str = "Need action") -> str:
    return json.dumps(
        {
            "type": "email.received",
            "created_at": "2026-10-04T06:00:00Z",
            "data": {
                "email_id": "56761188-7520-42d8-8898-ff6fc54ce618",
                "created_at": "2026-10-04T05:59:59Z",
                "from": "Alice <alice@example.com>",
                "to": ["ops@aegisomega.com"],
                "cc": [],
                "bcc": [],
                "message_id": "<m-1@example.com>",
                "subject": subject,
                "attachments": [
                    {
                        "id": "att-1",
                        "filename": "x.pdf",
                        "content_type": "application/pdf",
                    }
                ],
            },
        },
        separators=(",", ":"),
    )


def resend_receipt(
    raw: str, outcome: str = "VERIFIED"
) -> ExternalVerificationReceipt:
    return ExternalVerificationReceipt(
        schema_version=SCHEMA_VERSION,
        provider="resend",
        verification_method="resend.webhooks.verify",
        subject="msg_01",
        observed_input_digest=resend_observed_body_digest(raw),
        verifier_identity="aegis-resend-verifier",
        evidence_reference="runtime:svix",
        outcome=outcome,
    )


def workos_claims(delegated: bool = True) -> dict[str, object]:
    claims: dict[str, object] = {
        "iss": "https://aegis.authkit.app",
        "aud": "client_123",
        "sub": "agent_01",
        "sub_profile": "ai_agent",
        "sid": "agent_session_01",
        "jti": "jti_01",
        "agent_blueprint_id": "agent_blueprint_01",
        "org_id": "org_01",
        "permissions": ["crm:read", "email:send"],
        "intent": {"text": "triage-inbox"},
    }
    if delegated:
        claims["act"] = {"sub": "user_01", "sub_profile": "user"}
    return claims


def workos_receipt(
    claims: dict[str, object],
) -> ExternalVerificationReceipt:
    issuer = str(claims["iss"])
    audience = str(claims["aud"])
    return ExternalVerificationReceipt(
        schema_version=SCHEMA_VERSION,
        provider="workos",
        verification_method="oidc-jwt-signature+claims",
        subject=str(claims["sub"]),
        observed_input_digest=workos_verified_claims_digest(
            claims,
            expected_issuer=issuer,
            expected_audience=audience,
        ),
        verifier_identity="aegis-workos-oidc",
        evidence_reference="runtime:jwks",
        outcome="VERIFIED",
    )


class ExternalIngressTests(TestCase):
    def test_resend_metadata_only_quarantine_event(self) -> None:
        raw = raw_email()
        event = build_resend_email_received_event(
            raw_body=raw,
            verification=resend_receipt(raw),
            routing_domain="quarantine:inbound-email",
        )
        self.assertEqual(event.policy_decision, ZERO_HASH)
        self.assertEqual(event.capability_request, "external.email.observe")
        rendered = json.dumps(event.payload, sort_keys=True)
        self.assertNotIn("Need action", rendered)
        self.assertNotIn("alice@example.com", rendered)
        self.assertNotIn("x.pdf", rendered)
        self.assertEqual(event.payload["data"]["attachment_count"], 1)
        event.validate(expected_sequence=0, expected_parent=ZERO_HASH)

    def test_resend_requires_verified_receipt(self) -> None:
        raw = raw_email()
        with self.assertRaisesRegex(SovereignExecutionError, "NOT_VERIFIED"):
            build_resend_email_received_event(
                raw_body=raw,
                verification=resend_receipt(raw, "FAILED"),
                routing_domain="quarantine:inbound-email",
            )

    def test_resend_receipt_binds_exact_raw_body(self) -> None:
        raw = raw_email()
        receipt = resend_receipt(raw)
        with self.assertRaisesRegex(
            SovereignExecutionError, "BODY_DIGEST_MISMATCH"
        ):
            build_resend_email_received_event(
                raw_body=raw_email("changed"),
                verification=receipt,
                routing_domain="quarantine:inbound-email",
            )

    def test_resend_wrong_event_type_rejected(self) -> None:
        raw = raw_email().replace("email.received", "email.sent")
        with self.assertRaisesRegex(
            SovereignExecutionError, "TYPE_NOT_ADMITTED"
        ):
            build_resend_email_received_event(
                raw_body=raw,
                verification=resend_receipt(raw),
                routing_domain="quarantine:inbound-email",
            )

    def test_resend_operational_routing_forbidden(self) -> None:
        raw = raw_email()
        with self.assertRaisesRegex(
            SovereignExecutionError, "ROUTING_NOT_QUARANTINED"
        ):
            build_resend_email_received_event(
                raw_body=raw,
                verification=resend_receipt(raw),
                routing_domain="company:inbound-email",
            )

    def candidate(
        self,
        *,
        claims: dict[str, object] | None = None,
        capability: str = "external.email.send",
        approval: str = "NONE",
    ):
        claims = claims or workos_claims()
        return build_workos_agent_identity_candidate(
            claims=claims,
            verification=workos_receipt(claims),
            expected_issuer=str(claims["iss"]),
            expected_audience=str(claims["aud"]),
            permission_to_capability={
                "email:send": "external.email.send",
                "crm:read": "external.crm.read",
            },
            requested_capability=capability,
            repository_identity=REMOTE,
            source_commit=COMMIT,
            branch_or_ref="refs/heads/test",
            project_identity="AEGIS-OMEGA",
            parent_state_root=HASH,
            skills_root="2" * 64,
            registry_root="3" * 64,
            policy_root="4" * 64,
            model_identity="model-1",
            physical_executor="runner-1",
            tool_identity="resend",
            workflow_identity="company-inbox",
            authority_domain="external:email",
            requested_action={"op": "send", "target": "contact-1"},
            expected_pre_state=ZERO_HASH,
            approval_reference=approval,
        )

    def test_workos_identity_has_zero_authority(self) -> None:
        candidate = self.candidate()
        self.assertEqual(candidate.authority_effect, "NONE")
        self.assertEqual(candidate.identity.observed_authority, "0.000000")
        self.assertEqual(candidate.identity.approval_reference, "NONE")
        self.assertEqual(
            candidate.identity.actor_class, "external-agent-delegated"
        )
        self.assertEqual(
            candidate.mapped_capabilities,
            ("external.crm.read", "external.email.send"),
        )
        self.assertRegex(candidate.root, r"^[0-9a-f]{64}$")

    def test_workos_scope_cannot_widen_to_repository(self) -> None:
        with self.assertRaisesRegex(
            SovereignExecutionError, "SCOPE_DOES_NOT_MAP"
        ):
            self.candidate(capability="repository.mutate")

    def test_workos_user_token_rejected(self) -> None:
        claims = workos_claims()
        claims["sub_profile"] = "user"
        with self.assertRaisesRegex(
            SovereignExecutionError, "NOT_AGENT_TOKEN"
        ):
            workos_verified_claims_digest(
                claims,
                expected_issuer=str(claims["iss"]),
                expected_audience=str(claims["aud"]),
            )

    def test_workos_verification_binds_claims(self) -> None:
        claims = workos_claims()
        receipt = workos_receipt(claims)
        changed = dict(claims)
        changed["permissions"] = ["crm:read"]
        with self.assertRaisesRegex(
            SovereignExecutionError, "CLAIMS_DIGEST_MISMATCH"
        ):
            build_workos_agent_identity_candidate(
                claims=changed,
                verification=receipt,
                expected_issuer=str(changed["iss"]),
                expected_audience=str(changed["aud"]),
                permission_to_capability={
                    "crm:read": "external.crm.read"
                },
                requested_capability="external.crm.read",
                repository_identity=REMOTE,
                source_commit=COMMIT,
                branch_or_ref="refs/heads/test",
                project_identity="AEGIS-OMEGA",
                parent_state_root=HASH,
                skills_root="2" * 64,
                registry_root="3" * 64,
                policy_root="4" * 64,
                model_identity="model-1",
                physical_executor="runner-1",
                tool_identity="crm",
                workflow_identity="company-crm",
                authority_domain="external:crm",
                requested_action={"op": "read"},
                expected_pre_state=ZERO_HASH,
            )

    def test_workos_autonomous_identity_is_distinct(self) -> None:
        claims = workos_claims(False)
        candidate = self.candidate(claims=claims)
        self.assertEqual(
            candidate.identity.actor_class, "external-agent-autonomous"
        )

    def test_workos_scope_does_not_mint_aegis_approval(self) -> None:
        candidate = self.candidate(approval="approval-123")
        self.assertEqual(
            candidate.identity.approval_reference, "approval-123"
        )
        self.assertNotEqual(
            candidate.identity.approval_reference, "email:send"
        )


if __name__ == "__main__":
    main()
