"""Evidence-only Arc treasury settlement binding for AEGIS.

This module DOES NOT sign, submit, broadcast, or fund blockchain transactions.
It binds an already-authorized AEGIS treasury intent to a later observed Arc
transaction using deterministic hashes.

Authority boundary:
- authority_effect = NONE
- no private keys
- no wallet RPC
- no transaction submission
- no custody
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    SovereignExecutionError,
    canonical_hash,
)

ARC_MAINNET_CHAIN_ID = "5042"
ARC_TESTNET_CHAIN_ID = "5042002"
ARC_CHAIN_IDS = (ARC_MAINNET_CHAIN_ID, ARC_TESTNET_CHAIN_ID)
USDC_ASSET = "USDC"
USDC_DECIMALS = 6

EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_KEY_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")


def _assert_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_SHA256")


def _assert_safe_text(name: str, value: str, *, maximum: int = 512) -> None:
    if not isinstance(value, str) or not value.strip():
        raise SovereignExecutionError(f"{name}:EMPTY")
    encoded = value.encode("utf-8")
    if len(encoded) > maximum:
        raise SovereignExecutionError(f"{name}:TOO_LONG")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise SovereignExecutionError(f"{name}:CONTROL_CHARACTER")


def _canonical_address(value: str) -> str:
    if not isinstance(value, str) or not EVM_ADDRESS_RE.fullmatch(value):
        raise SovereignExecutionError("destination:INVALID_EVM_ADDRESS")
    return value.lower()


def _canonical_tx_hash(value: str) -> str:
    if not isinstance(value, str) or not TX_HASH_RE.fullmatch(value):
        raise SovereignExecutionError("tx_hash:INVALID_EVM_TX_HASH")
    return value.lower()


@dataclass(frozen=True)
class ArcTreasuryIntent:
    schema_version: str
    chain_id: str
    asset: str
    amount_microunits: int
    destination: str
    purpose: str
    authority_decision_root: str
    mutation_receipt_root: str
    idempotency_key: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("ARC_INTENT_SCHEMA_UNSUPPORTED")
        if self.chain_id not in ARC_CHAIN_IDS:
            raise SovereignExecutionError("ARC_CHAIN_UNSUPPORTED")
        if self.asset != USDC_ASSET:
            raise SovereignExecutionError("ARC_ASSET_UNSUPPORTED")
        if not isinstance(self.amount_microunits, int) or isinstance(self.amount_microunits, bool) or self.amount_microunits <= 0:
            raise SovereignExecutionError("ARC_AMOUNT_INVALID")
        _canonical_address(self.destination)
        _assert_safe_text("purpose", self.purpose)
        _assert_sha256("authority_decision_root", self.authority_decision_root)
        _assert_sha256("mutation_receipt_root", self.mutation_receipt_root)
        if not isinstance(self.idempotency_key, str) or not SAFE_KEY_RE.fullmatch(self.idempotency_key):
            raise SovereignExecutionError("idempotency_key:INVALID")

    def canonical_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "chain_id": self.chain_id,
            "asset": self.asset,
            "amount_microunits": self.amount_microunits,
            "destination": _canonical_address(self.destination),
            "purpose": self.purpose,
            "authority_decision_root": self.authority_decision_root,
            "mutation_receipt_root": self.mutation_receipt_root,
            "idempotency_key": self.idempotency_key,
        }

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_ARC_TREASURY_INTENT_V1", self.canonical_payload())


@dataclass(frozen=True)
class ArcSettlementObservation:
    schema_version: str
    chain_id: str
    tx_hash: str
    block_number: int
    amount_microunits: int
    destination: str
    status: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("ARC_OBSERVATION_SCHEMA_UNSUPPORTED")
        if self.chain_id not in ARC_CHAIN_IDS:
            raise SovereignExecutionError("ARC_CHAIN_UNSUPPORTED")
        _canonical_tx_hash(self.tx_hash)
        if not isinstance(self.block_number, int) or isinstance(self.block_number, bool) or self.block_number < 0:
            raise SovereignExecutionError("ARC_BLOCK_NUMBER_INVALID")
        if not isinstance(self.amount_microunits, int) or isinstance(self.amount_microunits, bool) or self.amount_microunits <= 0:
            raise SovereignExecutionError("ARC_AMOUNT_INVALID")
        _canonical_address(self.destination)
        if self.status not in ("CONFIRMED", "REVERTED"):
            raise SovereignExecutionError("ARC_SETTLEMENT_STATUS_INVALID")

    def canonical_payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "schema_version": self.schema_version,
            "chain_id": self.chain_id,
            "tx_hash": _canonical_tx_hash(self.tx_hash),
            "block_number": self.block_number,
            "amount_microunits": self.amount_microunits,
            "destination": _canonical_address(self.destination),
            "status": self.status,
        }

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_ARC_SETTLEMENT_OBSERVATION_V1", self.canonical_payload())


@dataclass(frozen=True)
class ArcTreasuryWitness:
    schema_version: str
    intent_root: str
    settlement_root: str
    tx_hash: str
    chain_id: str
    authority_effect: str = "NONE"
    scope: str = "EVIDENCE_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("ARC_WITNESS_SCHEMA_UNSUPPORTED")
        _assert_sha256("intent_root", self.intent_root)
        _assert_sha256("settlement_root", self.settlement_root)
        _canonical_tx_hash(self.tx_hash)
        if self.chain_id not in ARC_CHAIN_IDS:
            raise SovereignExecutionError("ARC_CHAIN_UNSUPPORTED")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("ARC_WITNESS_AUTHORITY_EFFECT_INVALID")
        if self.scope != "EVIDENCE_ONLY":
            raise SovereignExecutionError("ARC_WITNESS_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_ARC_TREASURY_WITNESS_V1", {
            **asdict(self),
            "tx_hash": _canonical_tx_hash(self.tx_hash),
        })


def bind_arc_settlement(intent: ArcTreasuryIntent, observation: ArcSettlementObservation) -> ArcTreasuryWitness:
    """Bind an AEGIS treasury intent to a later on-chain observation.

    This function verifies only deterministic field correspondence. It does not
    independently prove transaction finality, token-contract semantics, signer
    identity, or that AEGIS submitted the transaction.
    """
    intent.validate()
    observation.validate()

    if observation.status != "CONFIRMED":
        raise SovereignExecutionError("ARC_SETTLEMENT_NOT_CONFIRMED")
    if observation.chain_id != intent.chain_id:
        raise SovereignExecutionError("ARC_SETTLEMENT_CHAIN_MISMATCH")
    if observation.amount_microunits != intent.amount_microunits:
        raise SovereignExecutionError("ARC_SETTLEMENT_AMOUNT_MISMATCH")
    if _canonical_address(observation.destination) != _canonical_address(intent.destination):
        raise SovereignExecutionError("ARC_SETTLEMENT_DESTINATION_MISMATCH")

    return ArcTreasuryWitness(
        schema_version=SCHEMA_VERSION,
        intent_root=intent.root,
        settlement_root=observation.root,
        tx_hash=_canonical_tx_hash(observation.tx_hash),
        chain_id=intent.chain_id,
    )
