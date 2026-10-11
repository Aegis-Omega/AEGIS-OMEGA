"""Fail-closed correlation of Circle CCTP-v2 sandbox observations to Tameion reservations.

This is an EVIDENCE-ONLY adapter. Request/observation hashes prove deterministic
consistency of supplied data, NOT provider authenticity, source-chain inclusion,
attestation-signature validity, destination settlement or finality. It can never
release budget, trigger a transfer, claim settlement, or grant agent authority.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from harness.sdk.tameion_economic_reservations import (
    EconomicReservationLedger, ReservationDenied, ReservationReceipt, _root,
)

SCHEMA_VERSION = '1.0.0'
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
TX_HASH = re.compile(r'0x[0-9a-f]{64}\Z')
IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/@+\-=]{0,127}\Z')


def _expect(condition: bool, code: str) -> None:
    if not condition:
        raise ReservationDenied(code)


@dataclass(frozen=True)
class CircleReservationBinding:
    """Explicit external correlation claim; *not* proof of claim authenticity.

    Independently verify this binding before passing it to the adapter. Neither
    its hash nor its creation gives permission to spend or unlock budget.
    """
    schema_version: str
    scope: str
    attempt_id: str
    policy_root: str
    transfer_plan_root: str
    economic_boundary_root: str
    circle_request_root: str
    source_domain: int
    source_transaction_hash: str
    authority_effect: str = 'NONE'
    network_effect: str = 'NONE'

    def validate(self) -> None:
        _expect(self.schema_version == SCHEMA_VERSION, 'CIRCLE_BINDING_SCHEMA_INVALID')
        _expect(isinstance(self.scope, str) and IDENT.fullmatch(self.scope) is not None,
                'CIRCLE_BINDING_SCOPE_INVALID')
        _expect(isinstance(self.attempt_id, str) and IDENT.fullmatch(self.attempt_id) is not None,
                'CIRCLE_BINDING_ATTEMPT_INVALID')
        for value in (self.policy_root, self.transfer_plan_root,
                      self.economic_boundary_root, self.circle_request_root):
            _expect(isinstance(value, str) and HEX64.fullmatch(value) is not None,
                    'CIRCLE_BINDING_HASH_INVALID')
        _expect(type(self.source_domain) is int and 0 <= self.source_domain <= 2**32 - 1,
                'CIRCLE_BINDING_DOMAIN_INVALID')
        _expect(isinstance(self.source_transaction_hash, str) and
                TX_HASH.fullmatch(self.source_transaction_hash) is not None,
                'CIRCLE_BINDING_TX_INVALID')
        _expect(self.authority_effect == 'NONE' and self.network_effect == 'NONE',
                'CIRCLE_BINDING_AUTHORITY_FORBIDDEN')

    @property
    def root(self) -> str:
        self.validate()
        return _root('AEGIS_TAMEION_CIRCLE_RESERVATION_BINDING_V1', asdict(self))


@dataclass(frozen=True)
class CircleReconciliationFinding:
    binding_root: str
    observation_root: str
    reservation_receipt_root: str
    outcome: str
    source_status: str
    authority_effect: str = 'NONE'
    network_effect: str = 'NONE'
    settlement_asserted: bool = False
    budget_released: bool = False
    scope: str = 'CORRELATION_EVIDENCE_ONLY'

    @property
    def root(self) -> str:
        return _root('AEGIS_TAMEION_CIRCLE_RECONCILIATION_V1', asdict(self))


def reconcile_circle_v2_observation(
    *, ledger: EconomicReservationLedger, binding: CircleReservationBinding,
    pinned_binding_root: str, request: object, observation: object,
    expected_generation: int,
) -> CircleReconciliationFinding:
    """Correlate CCTP-v2 sandbox observation and hold funds regardless of status.

    Circle read-only evidence alone is not a verified on-chain payment. Require
    single-message responses, exact v2 request and trusted caller-pinned binding.
    No token release/refund/finality transition is implemented.
    """
    from harness.sdk.tameion_circle_attestation import (
        CircleV2MessagesRequest, CircleV2MessagesObservation,
    )

    _expect(isinstance(ledger, EconomicReservationLedger), 'CIRCLE_LEDGER_TYPE_INVALID')
    _expect(isinstance(binding, CircleReservationBinding), 'CIRCLE_BINDING_TYPE_INVALID')
    binding.validate()
    _expect(isinstance(pinned_binding_root, str) and HEX64.fullmatch(pinned_binding_root) is not None,
            'CIRCLE_BINDING_PIN_INVALID')
    _expect(pinned_binding_root == binding.root, 'CIRCLE_BINDING_PIN_MISMATCH')
    _expect(isinstance(request, CircleV2MessagesRequest) and
            isinstance(observation, CircleV2MessagesObservation), 'CIRCLE_SOURCE_TYPE_INVALID')
    try:
        request.validate()
        observation.validate()
    except (ValueError, TypeError, AttributeError) as exc:
        raise ReservationDenied('CIRCLE_SOURCE_INVALID') from exc

    _expect(request.root == binding.circle_request_root,
            'CIRCLE_REQUEST_ROOT_MISMATCH')
    _expect(observation.request_root == request.root,
            'CIRCLE_OBSERVATION_REQUEST_MISMATCH')
    _expect(request.transaction_hash == binding.source_transaction_hash and
            observation.transaction_hash == binding.source_transaction_hash,
            'CIRCLE_SOURCE_TRANSACTION_MISMATCH')
    _expect(request.source_domain == binding.source_domain and
            observation.source_domain == binding.source_domain,
            'CIRCLE_SOURCE_DOMAIN_MISMATCH')
    _expect(observation.endpoint == request.endpoint,
            'CIRCLE_ENDPOINT_MISMATCH')
    _expect(len(observation.statuses) == 1, 'CIRCLE_MULTI_MESSAGE_AMBIGUOUS')

    row = ledger.get_attempt(scope=binding.scope, attempt_id=binding.attempt_id)
    _expect(row.policy_root == binding.policy_root and
            row.intent_root == binding.transfer_plan_root and
            row.boundary_root == binding.economic_boundary_root,
            'CIRCLE_RESERVATION_BINDING_MISMATCH')

    # The *source-tx claim and journal transition* must be one SQLite atomic
    # transaction. A distinct attempt cannot claim the same Circle burn tx.
    correlation_root = _root('AEGIS_TAMEION_CIRCLE_CORRELATION_EVIDENCE_V1', {
        'binding_root': binding.root, 'request_root': request.root,
        'observation_root': observation.root,
    })
    receipt = ledger.record_circle_correlation(
        scope=binding.scope, attempt_id=binding.attempt_id,
        expected_generation=expected_generation,
        source_domain=binding.source_domain,
        source_tx_hash=binding.source_transaction_hash,
        status=observation.statuses[0], correlation_root=correlation_root,
    )
    outcome = ('CIRCLE_COMPLETE_BYTES_CORRELATED_NOT_SETTLED'
               if observation.statuses[0] == 'complete'
               else 'CIRCLE_PENDING_RESERVATION_RETAINED')

    return CircleReconciliationFinding(
        binding_root=binding.root, observation_root=observation.root,
        reservation_receipt_root=receipt.root, outcome=outcome,
        source_status=observation.statuses[0],
    )
