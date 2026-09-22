"""Pre-settlement evidence packet for the Tameion OpenMeter -> Arc lane.

This bundle binds an already-normalized OpenMeter payment obligation to an
already-admitted AEGIS Arc transfer plan and its deterministic unsigned calldata.

It does not create policy authority, attach a signer, call an RPC endpoint,
broadcast a transaction, or move funds.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.arc_erc20_call import ArcUnsignedTransferCall
from harness.sdk.arc_treasury_execution import ArcTransferPlan
from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError, canonical_hash
from harness.sdk.tameion_openmeter_bridge import (
    OpenMeterArcIntentBinding,
    OpenMeterPaymentObligation,
)


@dataclass(frozen=True)
class TameionPreSettlementBundle:
    schema_version: str
    obligation_root: str
    source_binding_root: str
    transfer_plan_root: str
    unsigned_call_root: str
    authority_decision_root: str
    mutation_receipt_root: str
    authority_effect: str = "NONE"
    scope: str = "PRE_SETTLEMENT_EVIDENCE_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("TAMEION_PRESETTLEMENT_SCHEMA_UNSUPPORTED")
        for name in (
            "obligation_root",
            "source_binding_root",
            "transfer_plan_root",
            "unsigned_call_root",
            "authority_decision_root",
            "mutation_receipt_root",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise SovereignExecutionError(f"{name}:INVALID_SHA256")
            try:
                int(value, 16)
            except ValueError as exc:
                raise SovereignExecutionError(f"{name}:INVALID_SHA256") from exc
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("TAMEION_PRESETTLEMENT_AUTHORITY_EFFECT_INVALID")
        if self.scope != "PRE_SETTLEMENT_EVIDENCE_ONLY":
            raise SovereignExecutionError("TAMEION_PRESETTLEMENT_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_PRE_SETTLEMENT_BUNDLE_V1", asdict(self))


def build_tameion_pre_settlement_bundle(
    *,
    obligation: OpenMeterPaymentObligation,
    source_binding: OpenMeterArcIntentBinding,
    plan: ArcTransferPlan,
    unsigned_call: ArcUnsignedTransferCall,
) -> TameionPreSettlementBundle:
    """Bind source evidence to the exact downstream admitted transfer plan."""

    obligation.validate()
    source_binding.validate()
    plan.validate()
    unsigned_call.validate()

    if source_binding.obligation_root != obligation.root:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_OBLIGATION_MISMATCH")
    if source_binding.treasury_intent_root != plan.treasury_intent_root:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_INTENT_MISMATCH")
    if source_binding.authority_decision_root != plan.authority_decision_root:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_AUTHORITY_MISMATCH")
    if unsigned_call.transfer_plan_root != plan.root:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_CALL_MISMATCH")

    if plan.chain_id != obligation.chain_id:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_CHAIN_MISMATCH")
    if plan.asset != obligation.asset:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_ASSET_MISMATCH")
    if plan.amount_microunits != obligation.amount_microunits:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_AMOUNT_MISMATCH")
    if plan.destination.lower() != obligation.destination.lower():
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_DESTINATION_MISMATCH")
    if plan.idempotency_key != obligation.idempotency_key:
        raise SovereignExecutionError("TAMEION_PRESETTLEMENT_IDEMPOTENCY_MISMATCH")

    bundle = TameionPreSettlementBundle(
        schema_version=SCHEMA_VERSION,
        obligation_root=obligation.root,
        source_binding_root=source_binding.root,
        transfer_plan_root=plan.root,
        unsigned_call_root=unsigned_call.root,
        authority_decision_root=plan.authority_decision_root,
        mutation_receipt_root=source_binding.mutation_receipt_root,
    )
    bundle.validate()
    return bundle
