#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.operator_visibility import (  # noqa: E402
    OperatorNotification,
    OperatorVisibilityLedger,
)
from harness.sdk.sovereign_execution import (  # noqa: E402
    SCHEMA_VERSION,
    ZERO_HASH,
    SovereignExecutionError,
    canonical_hash,
)

HASH = "1" * 64
RECEIPT = "2" * 64


class OperatorVisibilityTests(TestCase):
    def test_notification_root_is_deterministic(self) -> None:
        notification = OperatorNotification(
            schema_version=SCHEMA_VERSION,
            execution_identity_root=HASH,
            notification_kind="SECURITY_ALERT",
            authority_domain="github:contents",
            action_class="D4",
            receipt_reference=RECEIPT,
            parent_notification=ZERO_HASH,
            sequence=0,
            payload_digest=canonical_hash("PAYLOAD", {"code": "STALE_WRITER"}),
        )
        roots = [notification.root for _ in range(3)]
        self.assertEqual(len(set(roots)), 1)

    def test_operator_visibility_cannot_be_suppressed(self) -> None:
        notification = OperatorNotification(
            schema_version=SCHEMA_VERSION,
            execution_identity_root=HASH,
            notification_kind="FAILURE",
            authority_domain="workflow:durable",
            action_class="D3",
            receipt_reference=RECEIPT,
            parent_notification=ZERO_HASH,
            sequence=0,
            payload_digest=canonical_hash("PAYLOAD", {"failure": "provider unavailable"}),
            visibility="PEER_ONLY",
        )
        with self.assertRaisesRegex(SovereignExecutionError, "OPERATOR_VISIBILITY_CANNOT_BE_SUPPRESSED"):
            notification.validate()

    def test_authorization_mutation_and_cancellation_are_chained(self) -> None:
        ledger = OperatorVisibilityLedger()
        first = ledger.emit(
            execution_identity_root=HASH,
            notification_kind="AUTHORIZATION_REQUIRED",
            authority_domain="dns:production",
            action_class="D3",
            receipt_reference=RECEIPT,
            payload={"approval_reference": "approval-1"},
        )
        second = ledger.emit(
            execution_identity_root=HASH,
            notification_kind="MUTATION_NOTICE",
            authority_domain="dns:production",
            action_class="D3",
            receipt_reference="3" * 64,
            payload={"target": "record-root"},
        )
        third = ledger.emit(
            execution_identity_root=HASH,
            notification_kind="CANCELLATION",
            authority_domain="dns:production",
            action_class="D3",
            receipt_reference="4" * 64,
            payload={"future_authority": "REVOKED"},
        )
        self.assertEqual(first.parent_notification, ZERO_HASH)
        self.assertEqual(second.parent_notification, first.root)
        self.assertEqual(third.parent_notification, second.root)
        self.assertEqual(ledger.verify(), third.root)

    def test_broken_operator_chain_is_denied(self) -> None:
        ledger = OperatorVisibilityLedger()
        bad = OperatorNotification(
            schema_version=SCHEMA_VERSION,
            execution_identity_root=HASH,
            notification_kind="RECEIPT",
            authority_domain="repository:mutation",
            action_class="D2",
            receipt_reference=RECEIPT,
            parent_notification="9" * 64,
            sequence=0,
            payload_digest=canonical_hash("PAYLOAD", {"receipt": "available"}),
        )
        with self.assertRaisesRegex(SovereignExecutionError, "OPERATOR_NOTIFICATION_PARENT_BREAK"):
            ledger.append(bad)

    def test_sensitive_notification_payload_is_structurally_redacted(self) -> None:
        ledger = OperatorVisibilityLedger()
        notification = ledger.emit(
            execution_identity_root=HASH,
            notification_kind="SECURITY_ALERT",
            authority_domain="secrets:rotation",
            action_class="D4",
            receipt_reference=RECEIPT,
            payload={"secret_token": "not-stored-in-root", "state": "DENIED"},
        )
        self.assertRegex(notification.payload_digest, r"^[0-9a-f]{64}$")
        self.assertEqual(notification.visibility, "OPERATOR")


if __name__ == "__main__":
    main()
