"""Deterministic operator-visibility channel for Automaton-3.

Peer-message mediation never applies to this channel. Consequential authorization,
mutation, security, failure, cancellation, and receipt notices remain operator-visible
and are chained independently from EventEnvelope peer traffic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from harness.sdk.sovereign_execution import (
    ACTION_CLASSES,
    SCHEMA_VERSION,
    ZERO_HASH,
    SovereignExecutionError,
    _assert_authority_string,
    _assert_hash,
    canonical_hash,
    deterministic_redaction,
)

OPERATOR_NOTIFICATION_KINDS = (
    "AUTHORIZATION_REQUIRED",
    "MUTATION_NOTICE",
    "SECURITY_ALERT",
    "FAILURE",
    "CANCELLATION",
    "RECEIPT",
)


@dataclass(frozen=True)
class OperatorNotification:
    schema_version: str
    execution_identity_root: str
    notification_kind: str
    authority_domain: str
    action_class: str
    receipt_reference: str
    parent_notification: str
    sequence: int
    payload_digest: str
    visibility: str = "OPERATOR"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("OPERATOR_NOTIFICATION_SCHEMA_UNSUPPORTED")
        for name in (
            "execution_identity_root",
            "receipt_reference",
            "parent_notification",
            "payload_digest",
        ):
            _assert_hash(name, getattr(self, name))
        if self.notification_kind not in OPERATOR_NOTIFICATION_KINDS:
            raise SovereignExecutionError("OPERATOR_NOTIFICATION_KIND_INVALID")
        _assert_authority_string("authority_domain", self.authority_domain)
        if self.action_class not in ACTION_CLASSES:
            raise SovereignExecutionError("OPERATOR_NOTIFICATION_ACTION_CLASS_INVALID")
        if self.sequence < 0:
            raise SovereignExecutionError("OPERATOR_NOTIFICATION_SEQUENCE_INVALID")
        if self.visibility != "OPERATOR":
            raise SovereignExecutionError("OPERATOR_VISIBILITY_CANNOT_BE_SUPPRESSED")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash(
            "AEGIS_OPERATOR_NOTIFICATION_V1",
            deterministic_redaction(asdict(self)),
        )


class OperatorVisibilityLedger:
    """Append-only operator channel, independent of peer-message restrictions."""

    def __init__(self) -> None:
        self._notifications: list[OperatorNotification] = []

    def append(self, notification: OperatorNotification) -> str:
        notification.validate()
        expected_sequence = len(self._notifications)
        expected_parent = self._notifications[-1].root if self._notifications else ZERO_HASH
        if notification.sequence != expected_sequence:
            raise SovereignExecutionError("OPERATOR_NOTIFICATION_SEQUENCE_BREAK")
        if notification.parent_notification != expected_parent:
            raise SovereignExecutionError("OPERATOR_NOTIFICATION_PARENT_BREAK")
        self._notifications.append(notification)
        return notification.root

    def emit(
        self,
        *,
        execution_identity_root: str,
        notification_kind: str,
        authority_domain: str,
        action_class: str,
        receipt_reference: str,
        payload: Mapping[str, Any],
    ) -> OperatorNotification:
        parent = self._notifications[-1].root if self._notifications else ZERO_HASH
        notification = OperatorNotification(
            schema_version=SCHEMA_VERSION,
            execution_identity_root=execution_identity_root,
            notification_kind=notification_kind,
            authority_domain=authority_domain,
            action_class=action_class,
            receipt_reference=receipt_reference,
            parent_notification=parent,
            sequence=len(self._notifications),
            payload_digest=canonical_hash(
                "AEGIS_OPERATOR_NOTIFICATION_PAYLOAD_V1",
                deterministic_redaction(payload),
            ),
        )
        self.append(notification)
        return notification

    def verify(self) -> str:
        previous = ZERO_HASH
        for index, notification in enumerate(self._notifications):
            notification.validate()
            if notification.sequence != index:
                raise SovereignExecutionError("OPERATOR_NOTIFICATION_CHAIN_BROKEN")
            if notification.parent_notification != previous:
                raise SovereignExecutionError("OPERATOR_NOTIFICATION_CHAIN_BROKEN")
            previous = notification.root
        return previous

    def snapshot(self) -> tuple[OperatorNotification, ...]:
        return tuple(self._notifications)
