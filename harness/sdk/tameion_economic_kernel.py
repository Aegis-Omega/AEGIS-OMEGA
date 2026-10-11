"""Tameion Economic Kernel v0.1: deterministic, evidence-only boundary audit.

Composition of existing AEGIS authority/Arc/OpenMeter artifacts and a separately
pinned economic policy. This module NEVER evaluates/mints authority, reserves
funds, accesses wallets, signs, calls a network or asserts settlement.

The supplied budget snapshot and pins MUST be independently trusted. The
snapshot check is NOT an atomic multi-agent spending limit or replay lock.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from harness.sdk.arc_erc20_call import ArcUnsignedTransferCall
from harness.sdk.arc_treasury_execution import ArcTransferPlan
from harness.sdk.sovereign_execution import (
    ADMITTED, D3, D4, SCHEMA_VERSION, PolicyDecision, SovereignExecutionError,
    canonical_hash,
)
from harness.sdk.tameion_openmeter_bridge import OpenMeterArcIntentBinding, OpenMeterPaymentObligation
from harness.sdk.tameion_presettlement_bundle import (
    TameionPreSettlementBundle, build_tameion_pre_settlement_bundle,
)

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CAPABILITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}\Z")
ADDRESS = re.compile(r"0x[0-9a-f]{40}\Z")


def _is_uint(value: Any) -> bool:
    return type(value) is int and value >= 0


def _capabilities(value: Any) -> bool:
    return (isinstance(value, tuple)
            and all(isinstance(x, str) and CAPABILITY.fullmatch(x) for x in value)
            and tuple(sorted(set(value))) == value)


def _hash(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


@dataclass(frozen=True)
class EconomicPolicy:
    schema_version: str
    chain_id: str
    asset: str
    destination: str
    budget_microunits: int
    permitted_capabilities: tuple[str, ...]
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("ECON_POLICY_SCHEMA_INVALID")
        if self.chain_id != "5042002" or self.asset != "USDC":
            raise SovereignExecutionError("ECON_POLICY_TESTNET_USDC_ONLY")
        if not isinstance(self.destination, str) or not ADDRESS.fullmatch(self.destination):
            raise SovereignExecutionError("ECON_POLICY_DESTINATION_INVALID")
        if not _is_uint(self.budget_microunits) or self.budget_microunits == 0:
            raise SovereignExecutionError("ECON_POLICY_BUDGET_INVALID")
        if not _capabilities(self.permitted_capabilities):
            raise SovereignExecutionError("ECON_POLICY_CAPABILITIES_INVALID")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("ECON_POLICY_AUTHORITY_EFFECT_FORBIDDEN")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_ECONOMIC_POLICY_V1", asdict(self))


@dataclass(frozen=True)
class EconomicAttempt:
    attempt_id: str
    requested_capabilities: tuple[str, ...]
    confirmed_spend_microunits: int
    reserved_spend_microunits: int
    prior_attempt_ids: tuple[str, ...]

    def validate(self) -> None:
        if not isinstance(self.attempt_id, str) or not CAPABILITY.fullmatch(self.attempt_id):
            raise SovereignExecutionError("ECON_ATTEMPT_ID_INVALID")
        if not _capabilities(self.requested_capabilities) or not _capabilities(self.prior_attempt_ids):
            raise SovereignExecutionError("ECON_ATTEMPT_IDENTIFIERS_INVALID")
        if not _is_uint(self.confirmed_spend_microunits) or not _is_uint(self.reserved_spend_microunits):
            raise SovereignExecutionError("ECON_ATTEMPT_SPEND_INVALID")


@dataclass(frozen=True)
class EconomicBoundaryFinding:
    schema_version: str
    policy_root: str
    authority_decision_root: str
    obligation_root: str
    transfer_plan_root: str
    presettlement_bundle_root: str
    attempt_root: str
    outcome: str
    denial_codes: tuple[str, ...]
    authority_effect: str = "NONE"
    network_effect: str = "NONE"
    settlement_asserted: bool = False
    scope: str = "EVIDENCE_ONLY_NON_AUTHORITATIVE"

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_TAMEION_ECONOMIC_BOUNDARY_FINDING_V1", asdict(self))


def audit_economic_boundary(
    *, policy: EconomicPolicy, attempt: EconomicAttempt,
    obligation: OpenMeterPaymentObligation, binding: OpenMeterArcIntentBinding,
    plan: ArcTransferPlan, unsigned_call: ArcUnsignedTransferCall,
    bundle: TameionPreSettlementBundle, decision: PolicyDecision,
    pinned_policy_root: str, pinned_decision_root: str,
    pinned_mutation_receipt_root: str,
) -> EconomicBoundaryFinding:
    """Produce replayable *evidence findings*, never a payment authorization.

    The pins are provided by an independently trusted caller. Merely computing
    matching hashes here cannot establish authenticity or payment finality.
    A trusted atomic ledger must enforce concurrent budget and replay limits.
    """
    if not isinstance(policy, EconomicPolicy) or not isinstance(attempt, EconomicAttempt):
        raise SovereignExecutionError("ECON_INPUT_TYPE_INVALID")
    policy.validate()
    attempt.validate()
    if not all(_hash(h) for h in (pinned_policy_root, pinned_decision_root, pinned_mutation_receipt_root)):
        raise SovereignExecutionError("ECON_PIN_FORMAT_INVALID")
    if not isinstance(decision, PolicyDecision) or not isinstance(bundle, TameionPreSettlementBundle):
        raise SovereignExecutionError("ECON_SOURCE_TYPE_INVALID")

    reasons: list[str] = []
    # Source object self-validation rejects malformed or authority-escalating plans.
    try:
        obligation.validate()
        binding.validate()
        plan.validate()
        unsigned_call.validate()
        bundle.validate()
        rebuilt = build_tameion_pre_settlement_bundle(
            obligation=obligation, source_binding=binding,
            plan=plan, unsigned_call=unsigned_call,
        )
        if rebuilt.root != bundle.root:
            reasons.append("BUNDLE_ROOT_MISMATCH")
    except (SovereignExecutionError, TypeError, AttributeError):
        reasons.append("SOURCE_EVIDENCE_INVALID")

    if pinned_policy_root != policy.root:
        reasons.append("POLICY_PIN_MISMATCH")
    if pinned_decision_root != decision.decision_root or plan.authority_decision_root != decision.decision_root:
        reasons.append("DECISION_BINDING_MISMATCH")
    if pinned_mutation_receipt_root != bundle.mutation_receipt_root:
        reasons.append("MUTATION_RECEIPT_PIN_MISMATCH")
    if (decision.schema_version != SCHEMA_VERSION or decision.outcome != ADMITTED
        or decision.action_class not in (D3, D4) or decision.authority_domain != "treasury.testnet"
        or decision.requested_capability != "arc.testnet.transfer" or decision.tool != "arc-plan"
        or decision.denial_codes):
        reasons.append("AEGIS_AUTHORITY_NOT_ADMITTED")
    if plan.chain_id != policy.chain_id or plan.asset != policy.asset:
        reasons.append("NETWORK_OR_ASSET_MISMATCH")
    if plan.destination != policy.destination or obligation.destination.lower() != policy.destination:
        reasons.append("RECIPIENT_MISMATCH")
    if plan.amount_microunits != obligation.amount_microunits:
        reasons.append("AMOUNT_MISMATCH")
    if plan.idempotency_key != attempt.attempt_id or attempt.attempt_id in attempt.prior_attempt_ids:
        reasons.append("ATTEMPT_REPLAY_OR_ID_MISMATCH")
    if (attempt.confirmed_spend_microunits + attempt.reserved_spend_microunits
        + plan.amount_microunits > policy.budget_microunits):
        reasons.append("SIMULATED_BUDGET_EXCEEDED")
    if not set(attempt.requested_capabilities).issubset(policy.permitted_capabilities):
        reasons.append("CAPABILITY_ESCALATION")

    unique = tuple(sorted(set(reasons)))
    finding = EconomicBoundaryFinding(
        schema_version=SCHEMA_VERSION,
        policy_root=policy.root,
        authority_decision_root=decision.decision_root,
        obligation_root=obligation.root if "SOURCE_EVIDENCE_INVALID" not in unique else "0" * 64,
        transfer_plan_root=plan.root if "SOURCE_EVIDENCE_INVALID" not in unique else "0" * 64,
        presettlement_bundle_root=bundle.root if "SOURCE_EVIDENCE_INVALID" not in unique else "0" * 64,
        attempt_root=canonical_hash("AEGIS_TAMEION_ECONOMIC_ATTEMPT_V1", asdict(attempt)),
        outcome="BOUNDARY_CHECKS_PASSED" if not unique else "DENIED",
        denial_codes=unique,
    )
    return finding
