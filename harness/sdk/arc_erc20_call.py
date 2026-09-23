"""Deterministic Arc USDC ERC-20 calldata encoding.

Pure encoding only. No RPC, signing, key handling, gas estimation, submission,
or broadcast authority is present in this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.arc_treasury_execution import (
    ARC_TESTNET_NETWORK,
    ARC_USDC_INTERFACE,
    ArcTransferPlan,
)
from harness.sdk.sovereign_execution import SovereignExecutionError, canonical_hash

TRANSFER_SELECTOR = "a9059cbb"  # transfer(address,uint256)
HEX_RE = set("0123456789abcdefABCDEF")


def _hex_address(value: str) -> str:
    if not isinstance(value, str) or len(value) != 42 or not value.startswith("0x"):
        raise SovereignExecutionError("ARC_CALL_ADDRESS_INVALID")
    body = value[2:]
    if any(ch not in HEX_RE for ch in body):
        raise SovereignExecutionError("ARC_CALL_ADDRESS_INVALID")
    return body.lower()


def _uint256_word(value: int) -> str:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value >= 2**256:
        raise SovereignExecutionError("ARC_CALL_UINT256_INVALID")
    return value.to_bytes(32, "big").hex()


def encode_transfer_calldata(destination: str, amount_microunits: int) -> str:
    address_word = _hex_address(destination).rjust(64, "0")
    amount_word = _uint256_word(amount_microunits)
    return "0x" + TRANSFER_SELECTOR + address_word + amount_word


@dataclass(frozen=True)
class ArcUnsignedTransferCall:
    network: str
    chain_id: str
    to: str
    value: int
    data: str
    transfer_plan_root: str
    broadcast_allowed: bool = False
    signer_attached: bool = False
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.network != ARC_TESTNET_NETWORK:
            raise SovereignExecutionError("ARC_CALL_NETWORK_INVALID")
        if self.to.lower() != ARC_USDC_INTERFACE:
            raise SovereignExecutionError("ARC_CALL_TARGET_INVALID")
        if self.value != 0:
            raise SovereignExecutionError("ARC_CALL_VALUE_MUST_BE_ZERO")
        if not isinstance(self.data, str) or not self.data.startswith("0x" + TRANSFER_SELECTOR):
            raise SovereignExecutionError("ARC_CALL_DATA_INVALID")
        if len(self.data) != 2 + 8 + 64 + 64:
            raise SovereignExecutionError("ARC_CALL_DATA_LENGTH_INVALID")
        if self.broadcast_allowed:
            raise SovereignExecutionError("ARC_CALL_BROADCAST_AUTHORITY_FORBIDDEN")
        if self.signer_attached:
            raise SovereignExecutionError("ARC_CALL_SIGNER_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("ARC_CALL_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        body = asdict(self)
        body["to"] = self.to.lower()
        body["data"] = self.data.lower()
        return canonical_hash("AEGIS_ARC_UNSIGNED_TRANSFER_CALL_V1", body)


def build_unsigned_transfer_call(plan: ArcTransferPlan) -> ArcUnsignedTransferCall:
    plan.validate()
    return ArcUnsignedTransferCall(
        network=plan.network,
        chain_id=plan.chain_id,
        to=ARC_USDC_INTERFACE,
        value=0,
        data=encode_transfer_calldata(plan.destination, plan.amount_microunits),
        transfer_plan_root=plan.root,
    )
