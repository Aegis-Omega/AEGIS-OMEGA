"""End-to-end metered settlement evidence chain for the Tameion demo.

This layer composes:
OpenMeter metered-event evidence -> pre-settlement AEGIS/Arc packet -> observed
Arc settlement witness -> post-settlement calibration.

It does not grant authority, attach a signer, broadcast a transaction, or move
funds. Settlement evidence must already exist and match the exact admitted plan.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.arc_treasury_execution import ArcTransferPlan
from harness.sdk.arc_treasury_witness import ArcTreasuryWitness
from harness.sdk.notebook_evidence import NotebookEvidenceSummary
from harness.sdk.sovereign_execution import SCHEMA_VERSION, ZERO_HASH, SovereignExecutionError, canonical_hash
from harness.sdk.tameion_presettlement_bundle import TameionPreSettlementBundle
from harness.sdk.treasury_calibration import (
    MICROS,
    TreasuryCalibrationRecord,
    calibrate_treasury_outcome,
)


@dataclass(frozen=True)
class TameionMeteredEvidenceChain:
    schema_version: str
    pre_settlement_bundle_root: str
    settlement_witness_root: str
    calibration_root: str
    notebook_evidence_root: str
    authority_effect: str = "NONE"
    scope: str = "METERED_SETTLEMENT_EVIDENCE_CHAIN_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("TAMEION_METERED_CHAIN_SCHEMA_UNSUPPORTED")
        for name in (
            "pre_settlement_bundle_root",
            "settlement_witness_root",
            "calibration_root",
            "notebook_evidence_root",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or len(value) != 64:
                raise SovereignExecutionError(f"{name}:INVALID_SHA256")
            try:
                int(value, 16)
            except ValueError as exc:
                raise SovereignExecutionError(f"{name}:INVALID_SHA256") from exc
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("TAMEION_METERED_CHAIN_AUTHORITY_EFFECT_INVALID")
        if self.scope != "METERED_SETTLEMENT_EVIDENCE_CHAIN_ONLY":
            raise SovereignExecutionError("TAMEION_METERED_CHAIN_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_METERED_EVIDENCE_CHAIN_V1", asdict(self))


def build_tameion_metered_evidence_chain(
    *,
    pre_settlement: TameionPreSettlementBundle,
    plan: ArcTransferPlan,
    witness: ArcTreasuryWitness,
    claimed_correctness_micros: int,
    notebook: NotebookEvidenceSummary | None = None,
) -> tuple[TameionMeteredEvidenceChain, TreasuryCalibrationRecord]:
    """Close the evidence chain only after an exact matching settlement witness exists."""

    pre_settlement.validate()
    plan.validate()
    witness.validate()
    if notebook is not None:
        notebook.validate()

    if pre_settlement.transfer_plan_root != plan.root:
        raise SovereignExecutionError("TAMEION_METERED_CHAIN_PLAN_MISMATCH")
    if pre_settlement.authority_decision_root != plan.authority_decision_root:
        raise SovereignExecutionError("TAMEION_METERED_CHAIN_AUTHORITY_MISMATCH")
    if witness.chain_id != plan.chain_id:
        raise SovereignExecutionError("TAMEION_METERED_CHAIN_CHAIN_MISMATCH")
    if witness.intent_root != plan.treasury_intent_root:
        raise SovereignExecutionError("TAMEION_METERED_CHAIN_INTENT_MISMATCH")

    calibration = calibrate_treasury_outcome(
        authority_decision_root=plan.authority_decision_root,
        transfer_plan_root=plan.root,
        settlement_reference_root=witness.root,
        claimed_correctness_micros=claimed_correctness_micros,
        actual_correctness_micros=MICROS,
        outcome_label="CONFIRMED_RECONCILED",
    )

    chain = TameionMeteredEvidenceChain(
        schema_version=SCHEMA_VERSION,
        pre_settlement_bundle_root=pre_settlement.root,
        settlement_witness_root=witness.root,
        calibration_root=calibration.root,
        notebook_evidence_root=notebook.root if notebook is not None else ZERO_HASH,
    )
    chain.validate()
    return chain, calibration
