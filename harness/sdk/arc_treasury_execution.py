"""Governed, non-broadcast Arc Testnet transfer planning.

This layer converts an already-admitted AEGIS D3/D4 policy decision plus an
ArcTreasuryIntent into a deterministic execution plan. It intentionally does
not load keys, sign, submit, or broadcast transactions.

The signer / provider adapter is a later boundary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.arc_treasury_witness import (
    ARC_TESTNET_CHAIN_ID,
    USDC_ASSET,
    ArcTreasuryIntent,
)
from harness.sdk.sovereign_execution import (
    ADMITTED,
    D3,
    D4,
    PolicyDecision,
    SovereignExecutionError,
    canonical_hash,
)

ARC_USDC_INTERFACE = "0x3600000000000000000000000000000000000000"
ARC_TESTNET_NETWORK = "ARC-TESTNET"


def _canonical_address(value: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise SovereignExecutionError("ARC_EXECUTION_ADDRESS_INVALID")
    try:
        int(value[2:], 16)
    except ValueError as exc:
        raise SovereignExecutionError("ARC_EXECUTION_ADDRESS_INVALID") from exc
    return value.lower()


@dataclass(frozen=True)
class ArcTransferPlan:
    schema_version: str
    chain_id: str
    network: str
    asset: str
    token_interface: str
    sender: str
    destination: str
    amount_microunits: int
    idempotency_key: str
    purpose: str
    authority_decision_root: str
    treasury_intent_root: str
    broadcast_allowed: bool = False
    real_value_allowed: bool = False
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.chain_id != ARC_TESTNET_CHAIN_ID:
            raise SovereignExecutionError("ARC_EXECUTION_TESTNET_ONLY")
        if self.network != ARC_TESTNET_NETWORK:
            raise SovereignExecutionError("ARC_EXECUTION_NETWORK_INVALID")
        if self.asset != USDC_ASSET:
            raise SovereignExecutionError("ARC_EXECUTION_ASSET_INVALID")
        if self.token_interface.lower() != ARC_USDC_INTERFACE:
            raise SovereignExecutionError("ARC_EXECUTION_TOKEN_INTERFACE_INVALID")
        _canonical_address(self.sender)
        _canonical_address(self.destination)
        if not isinstance(self.amount_microunits, int) or isinstance(self.amount_microunits, bool) or self.amount_microunits <= 0:
            raise SovereignExecutionError("ARC_EXECUTION_AMOUNT_INVALID")
        if self.broadcast_allowed:
            raise SovereignExecutionError("ARC_EXECUTION_BROADCAST_AUTHORITY_FORBIDDEN")
        if self.real_value_allowed:
            raise SovereignExecutionError("ARC_EXECUTION_REAL_VALUE_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("ARC_EXECUTION_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        body = asdict(self)
        body["sender"] = _canonical_address(self.sender)
        body["destination"] = _canonical_address(self.destination)
        body["token_interface"] = self.token_interface.lower()
        return canonical_hash("AEGIS_ARC_TRANSFER_PLAN_V1", body)


def plan_arc_testnet_transfer(
    *,
    intent: ArcTreasuryIntent,
    decision: PolicyDecision,
    sender: str,
) -> ArcTransferPlan:
    """Create a deterministic testnet transfer plan from admitted AEGIS state.

    This proves only that an admitted policy decision and a treasury intent agree
    on the authority root and can be transformed into a canonical Arc Testnet
    transfer request. It does not authorize a signer or network broadcast.
    """
    intent.validate()

    if intent.chain_id != ARC_TESTNET_CHAIN_ID:
        raise SovereignExecutionError("ARC_EXECUTION_TESTNET_ONLY")
    if decision.outcome != ADMITTED:
        raise SovereignExecutionError("ARC_EXECUTION_REQUIRES_ADMITTED_DECISION")
    if decision.action_class not in (D3, D4):
        raise SovereignExecutionError("ARC_EXECUTION_REQUIRES_D3_OR_D4")
    if decision.decision_root != intent.authority_decision_root:
        raise SovereignExecutionError("ARC_EXECUTION_AUTHORITY_ROOT_MISMATCH")

    return ArcTransferPlan(
        schema_version=intent.schema_version,
        chain_id=intent.chain_id,
        network=ARC_TESTNET_NETWORK,
        asset=intent.asset,
        token_interface=ARC_USDC_INTERFACE,
        sender=_canonical_address(sender),
        destination=_canonical_address(intent.destination),
        amount_microunits=intent.amount_microunits,
        idempotency_key=intent.idempotency_key,
        purpose=intent.purpose,
        authority_decision_root=decision.decision_root,
        treasury_intent_root=intent.root,
    )
