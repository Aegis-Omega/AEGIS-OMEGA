"""Composite evidence bundle for the Tameion / Arc demonstration.

This module composes already-bounded evidence objects. It grants no signing,
broadcast, custody, or payment authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.arc_erc20_call import ArcUnsignedTransferCall
from harness.sdk.arc_treasury_execution import ArcTransferPlan
from harness.sdk.arc_treasury_witness import ArcTreasuryWitness
from harness.sdk.notebook_evidence import NotebookEvidenceSummary
from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    ZERO_HASH,
    SovereignExecutionError,
    canonical_hash,
)
from harness.sdk.treasury_calibration import (
    MICROS,
    TreasuryCalibrationRecord,
    calibrate_treasury_outcome,
)


@dataclass(frozen=True)
class TameionEvidenceBundle:
    schema_version: str
    transfer_plan_root: str
    unsigned_call_root: str
    settlement_witness_root: str
    calibration_root: str
    notebook_evidence_root: str
    authority_effect: str = "NONE"
    scope: str = "DEMO_EVIDENCE_CHAIN_ONLY"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("TAMEION_BUNDLE_SCHEMA_UNSUPPORTED")
        for name in (
            "transfer_plan_root",
            "unsigned_call_root",
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
            raise SovereignExecutionError("TAMEION_BUNDLE_AUTHORITY_EFFECT_INVALID")
        if self.scope != "DEMO_EVIDENCE_CHAIN_ONLY":
            raise SovereignExecutionError("TAMEION_BUNDLE_SCOPE_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_EVIDENCE_BUNDLE_V1", asdict(self))


def build_confirmed_tameion_bundle(
    *,
    plan: ArcTransferPlan,
    unsigned_call: ArcUnsignedTransferCall,
    witness: ArcTreasuryWitness,
    claimed_correctness_micros: int,
    notebook: NotebookEvidenceSummary | None = None,
) -> tuple[TameionEvidenceBundle, TreasuryCalibrationRecord]:
    plan.validate()
    unsigned_call.validate()
    witness.validate()
    if notebook is not None:
        notebook.validate()

    if unsigned_call.transfer_plan_root != plan.root:
        raise SovereignExecutionError("TAMEION_BUNDLE_TRANSFER_CALL_MISMATCH")
    if witness.chain_id != plan.chain_id:
        raise SovereignExecutionError("TAMEION_BUNDLE_CHAIN_MISMATCH")
    if witness.intent_root != plan.treasury_intent_root:
        raise SovereignExecutionError("TAMEION_BUNDLE_INTENT_MISMATCH")

    calibration = calibrate_treasury_outcome(
        authority_decision_root=plan.authority_decision_root,
        transfer_plan_root=plan.root,
        settlement_reference_root=witness.root,
        claimed_correctness_micros=claimed_correctness_micros,
        actual_correctness_micros=MICROS,
        outcome_label="CONFIRMED_RECONCILED",
    )

    bundle = TameionEvidenceBundle(
        schema_version=SCHEMA_VERSION,
        transfer_plan_root=plan.root,
        unsigned_call_root=unsigned_call.root,
        settlement_witness_root=witness.root,
        calibration_root=calibration.root,
        notebook_evidence_root=notebook.root if notebook is not None else ZERO_HASH,
    )
    bundle.validate()
    return bundle, calibration
