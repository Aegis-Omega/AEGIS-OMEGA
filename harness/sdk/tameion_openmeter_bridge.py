"""OpenMeter usage -> Arc Testnet settlement intent bridge for Tameion.

Pure, deterministic evidence construction only.

This module does not call OpenMeter, Circle, Arc, a wallet, an RPC endpoint, or a
signer. It converts an already-observed OpenMeter usage event plus an explicit
testnet settlement policy into a content-addressed payment obligation and then
an ArcTreasuryIntent. Broadcast and real-value authority remain forbidden by
the downstream Arc execution layer.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from harness.sdk.arc_treasury_witness import (
    ARC_TESTNET_CHAIN_ID,
    USDC_ASSET,
    ArcTreasuryIntent,
)
from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    SovereignExecutionError,
    canonical_hash,
)

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")
EVM_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Demo safety bound only. This is not a Circle product limit or financial
# recommendation. It prevents a usage->payment mapping from silently creating
# an unexpectedly large testnet obligation.
MAX_DEMO_SETTLEMENT_MICROUNITS = 1_000_000  # 1 testnet USDC


def _safe_id(name: str, value: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > maximum:
        raise SovereignExecutionError(f"{name}:INVALID")
    if not SAFE_ID_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID")
    return value


def _canonical_address(value: str) -> str:
    if not isinstance(value, str) or not EVM_ADDRESS_RE.fullmatch(value):
        raise SovereignExecutionError("OPENMETER_DESTINATION_INVALID")
    return value.lower()


def _sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise SovereignExecutionError(f"{name}:INVALID_SHA256")
    return value


@dataclass(frozen=True)
class OpenMeterUsageObservation:
    """Normalized evidence that one OpenMeter event was reflected in a meter."""

    schema_version: str
    meter_slug: str
    event_id: str
    subject: str
    usage_units: int
    status: str = "METERED"
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("OPENMETER_USAGE_SCHEMA_UNSUPPORTED")
        _safe_id("meter_slug", self.meter_slug)
        _safe_id("event_id", self.event_id)
        _safe_id("subject", self.subject)
        if (
            not isinstance(self.usage_units, int)
            or isinstance(self.usage_units, bool)
            or self.usage_units <= 0
        ):
            raise SovereignExecutionError("OPENMETER_USAGE_UNITS_INVALID")
        if self.status != "METERED":
            raise SovereignExecutionError("OPENMETER_USAGE_NOT_METERED")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("OPENMETER_USAGE_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_OPENMETER_USAGE_OBSERVATION_V1", asdict(self))


@dataclass(frozen=True)
class OpenMeterSettlementPolicy:
    """Explicit demo pricing and destination policy for one OpenMeter meter."""

    schema_version: str
    meter_slug: str
    unit_price_microunits: int
    destination: str
    max_amount_microunits: int = MAX_DEMO_SETTLEMENT_MICROUNITS
    chain_id: str = ARC_TESTNET_CHAIN_ID
    asset: str = USDC_ASSET
    real_value_allowed: bool = False
    broadcast_allowed: bool = False
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("OPENMETER_POLICY_SCHEMA_UNSUPPORTED")
        _safe_id("meter_slug", self.meter_slug)
        if (
            not isinstance(self.unit_price_microunits, int)
            or isinstance(self.unit_price_microunits, bool)
            or self.unit_price_microunits <= 0
        ):
            raise SovereignExecutionError("OPENMETER_UNIT_PRICE_INVALID")
        if (
            not isinstance(self.max_amount_microunits, int)
            or isinstance(self.max_amount_microunits, bool)
            or self.max_amount_microunits <= 0
            or self.max_amount_microunits > MAX_DEMO_SETTLEMENT_MICROUNITS
        ):
            raise SovereignExecutionError("OPENMETER_MAX_AMOUNT_INVALID")
        _canonical_address(self.destination)
        if self.chain_id != ARC_TESTNET_CHAIN_ID:
            raise SovereignExecutionError("OPENMETER_SETTLEMENT_TESTNET_ONLY")
        if self.asset != USDC_ASSET:
            raise SovereignExecutionError("OPENMETER_SETTLEMENT_ASSET_INVALID")
        if self.real_value_allowed:
            raise SovereignExecutionError("OPENMETER_REAL_VALUE_FORBIDDEN")
        if self.broadcast_allowed:
            raise SovereignExecutionError("OPENMETER_BROADCAST_AUTHORITY_FORBIDDEN")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("OPENMETER_POLICY_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        body = asdict(self)
        body["destination"] = _canonical_address(self.destination)
        return canonical_hash("AEGIS_OPENMETER_SETTLEMENT_POLICY_V1", body)


@dataclass(frozen=True)
class OpenMeterPaymentObligation:
    schema_version: str
    usage_root: str
    settlement_policy_root: str
    event_id: str
    meter_slug: str
    subject: str
    usage_units: int
    unit_price_microunits: int
    amount_microunits: int
    destination: str
    chain_id: str
    asset: str
    idempotency_key: str
    authority_effect: str = "NONE"
    scope: str = "TESTNET_DEMO_OBLIGATION_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("OPENMETER_OBLIGATION_SCHEMA_UNSUPPORTED")
        _sha256("usage_root", self.usage_root)
        _sha256("settlement_policy_root", self.settlement_policy_root)
        _safe_id("event_id", self.event_id)
        _safe_id("meter_slug", self.meter_slug)
        _safe_id("subject", self.subject)
        _safe_id("idempotency_key", self.idempotency_key)
        if (
            not isinstance(self.usage_units, int)
            or isinstance(self.usage_units, bool)
            or self.usage_units <= 0
        ):
            raise SovereignExecutionError("OPENMETER_OBLIGATION_USAGE_INVALID")
        if (
            not isinstance(self.unit_price_microunits, int)
            or isinstance(self.unit_price_microunits, bool)
            or self.unit_price_microunits <= 0
        ):
            raise SovereignExecutionError("OPENMETER_OBLIGATION_PRICE_INVALID")
        expected = self.usage_units * self.unit_price_microunits
        if self.amount_microunits != expected:
            raise SovereignExecutionError("OPENMETER_OBLIGATION_AMOUNT_MISMATCH")
        if self.amount_microunits <= 0 or self.amount_microunits > MAX_DEMO_SETTLEMENT_MICROUNITS:
            raise SovereignExecutionError("OPENMETER_OBLIGATION_AMOUNT_OUT_OF_RANGE")
        _canonical_address(self.destination)
        if self.chain_id != ARC_TESTNET_CHAIN_ID:
            raise SovereignExecutionError("OPENMETER_OBLIGATION_TESTNET_ONLY")
        if self.asset != USDC_ASSET:
            raise SovereignExecutionError("OPENMETER_OBLIGATION_ASSET_INVALID")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("OPENMETER_OBLIGATION_AUTHORITY_EFFECT_INVALID")
        if self.scope != "TESTNET_DEMO_OBLIGATION_ONLY":
            raise SovereignExecutionError("OPENMETER_OBLIGATION_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        body = asdict(self)
        body["destination"] = _canonical_address(self.destination)
        return canonical_hash("AEGIS_OPENMETER_PAYMENT_OBLIGATION_V1", body)


@dataclass(frozen=True)
class OpenMeterArcIntentBinding:
    schema_version: str
    obligation_root: str
    treasury_intent_root: str
    authority_decision_root: str
    mutation_receipt_root: str
    authority_effect: str = "NONE"
    scope: str = "SOURCE_TO_INTENT_BINDING_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("OPENMETER_BINDING_SCHEMA_UNSUPPORTED")
        _sha256("obligation_root", self.obligation_root)
        _sha256("treasury_intent_root", self.treasury_intent_root)
        _sha256("authority_decision_root", self.authority_decision_root)
        _sha256("mutation_receipt_root", self.mutation_receipt_root)
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("OPENMETER_BINDING_AUTHORITY_EFFECT_INVALID")
        if self.scope != "SOURCE_TO_INTENT_BINDING_ONLY":
            raise SovereignExecutionError("OPENMETER_BINDING_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_OPENMETER_ARC_INTENT_BINDING_V1", asdict(self))


def build_openmeter_payment_obligation(
    *,
    usage: OpenMeterUsageObservation,
    policy: OpenMeterSettlementPolicy,
) -> OpenMeterPaymentObligation:
    usage.validate()
    policy.validate()

    if usage.meter_slug != policy.meter_slug:
        raise SovereignExecutionError("OPENMETER_METER_POLICY_MISMATCH")

    amount = usage.usage_units * policy.unit_price_microunits
    if amount > policy.max_amount_microunits:
        raise SovereignExecutionError("OPENMETER_SETTLEMENT_CAP_EXCEEDED")

    obligation = OpenMeterPaymentObligation(
        schema_version=SCHEMA_VERSION,
        usage_root=usage.root,
        settlement_policy_root=policy.root,
        event_id=usage.event_id,
        meter_slug=usage.meter_slug,
        subject=usage.subject,
        usage_units=usage.usage_units,
        unit_price_microunits=policy.unit_price_microunits,
        amount_microunits=amount,
        destination=_canonical_address(policy.destination),
        chain_id=policy.chain_id,
        asset=policy.asset,
        idempotency_key=f"openmeter:{usage.event_id}",
    )
    obligation.validate()
    return obligation


def build_openmeter_arc_intent(
    *,
    obligation: OpenMeterPaymentObligation,
    authority_decision_root: str,
    mutation_receipt_root: str,
) -> tuple[ArcTreasuryIntent, OpenMeterArcIntentBinding]:
    obligation.validate()
    _sha256("authority_decision_root", authority_decision_root)
    _sha256("mutation_receipt_root", mutation_receipt_root)

    intent = ArcTreasuryIntent(
        schema_version=SCHEMA_VERSION,
        chain_id=obligation.chain_id,
        asset=obligation.asset,
        amount_microunits=obligation.amount_microunits,
        destination=obligation.destination,
        purpose="openmeter-metered-event-settlement",
        authority_decision_root=authority_decision_root,
        mutation_receipt_root=mutation_receipt_root,
        idempotency_key=obligation.idempotency_key,
    )
    intent.validate()

    binding = OpenMeterArcIntentBinding(
        schema_version=SCHEMA_VERSION,
        obligation_root=obligation.root,
        treasury_intent_root=intent.root,
        authority_decision_root=authority_decision_root,
        mutation_receipt_root=mutation_receipt_root,
    )
    binding.validate()
    return intent, binding
