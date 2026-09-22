"""AEGIS Ω — Gravity/Quantum domain verifiers for Cross-Boundary Authority V1.

This child module extends the verifier registry from PR #535 without changing the
parent cross-boundary mechanics. Every verifier is fail-closed and grants no
runtime, repository, production, or physical authority.

authority_effect = NONE
"""
from __future__ import annotations

from typing import Any, Mapping

import cross_boundary_authority as cba
import research_invariants as ri

F2B_KERNEL_VERIFIER_ID = "GQ_F2B_KERNEL_RECEIPT_VERIFIER_V1"
D2_MODEL_VERIFIER_ID = "GQ_D2_MODEL_FORMULA_VERIFIER_V1"
MEASUREMENT_VERIFIER_ID = "GQ_PHYSICAL_MEASUREMENT_VERIFIER_V1"
NUISANCE_VERIFIER_ID = "GQ_NUISANCE_CONTROL_VERIFIER_V1"
REPLICATION_VERIFIER_ID = "GQ_INDEPENDENT_REPLICATION_VERIFIER_V1"


def _exact_keys(value: Mapping[str, Any], keys: set[str]) -> bool:
    return isinstance(value, Mapping) and set(value) == keys


def _register(verifier_id: str, verifier: cba.BridgeVerifier) -> None:
    registry = cba._REGISTERED_BRIDGE_VERIFIERS
    if verifier_id in registry:
        raise ValueError(f"gravity verifier already registered: {verifier_id}")
    if not isinstance(registry, dict):
        raise TypeError("cross-boundary verifier registry is not mutable in this exact source")
    registry[verifier_id] = verifier


def _receipt(
    gate_id: str,
    relation: ri.RelationBindingV1,
    verifier_id: str,
    passed: bool,
    observation: Mapping[str, Any],
) -> ri.GateReceipt:
    return ri.relation_gate_receipt(
        gate_id=gate_id,
        relation=relation,
        verdict=ri.GateVerdict.PASS if passed else ri.GateVerdict.FAIL,
        observation={"verifier_id": verifier_id, **dict(observation)},
        gate_version="1",
    )


def f2b_kernel_verifier(
    gate_id: str,
    relation: ri.RelationBindingV1,
    evidence: Mapping[str, Any],
) -> ri.GateReceipt:
    ok = (
        _exact_keys(
            evidence,
            {
                "schema",
                "kernel_replay",
                "theorem",
                "source_sha256",
                "axiom_audit",
                "sorryAx_present",
                "authority_effect",
            },
        )
        and evidence.get("schema") == "AEGIS_GQ_F2B_KERNEL_RECEIPT_V1"
        and evidence.get("kernel_replay") == "PASS"
        and evidence.get("theorem")
        == "coeffDet_ne_zero_iff_not_pureProductCoeffs"
        and isinstance(evidence.get("source_sha256"), str)
        and len(evidence["source_sha256"]) == 64
        and evidence.get("axiom_audit") == "PASS"
        and evidence.get("sorryAx_present") is False
        and evidence.get("authority_effect") == "NONE"
    )
    return _receipt(
        gate_id,
        relation,
        F2B_KERNEL_VERIFIER_ID,
        ok,
        {"kernel_receipt_valid": ok},
    )


def d2_model_formula_verifier(
    gate_id: str,
    relation: ri.RelationBindingV1,
    evidence: Mapping[str, Any],
) -> ri.GateReceipt:
    ok = (
        _exact_keys(
            evidence,
            {
                "schema",
                "source_doi",
                "source_arxiv",
                "equations",
                "eq90_condition",
                "phase_flip",
                "physical_measurement",
                "authority_effect",
            },
        )
        and evidence.get("schema") == "AEGIS_GQ_D2_MODEL_FORMULA_RECEIPT_V1"
        and evidence.get("source_doi") == "10.1103/PhysRevLett.134.061501"
        and evidence.get("source_arxiv") == "2309.09105v2"
        and evidence.get("equations") == ("87", "89", "90")
        and evidence.get("eq90_condition") is True
        and evidence.get("phase_flip") == "PASS"
        and evidence.get("physical_measurement") == "NOT_PERFORMED"
        and evidence.get("authority_effect") == "NONE"
    )
    return _receipt(
        gate_id,
        relation,
        D2_MODEL_VERIFIER_ID,
        ok,
        {"published_model_formula_valid": ok},
    )


def physical_measurement_verifier(
    gate_id: str,
    relation: ri.RelationBindingV1,
    evidence: Mapping[str, Any],
) -> ri.GateReceipt:
    ok = (
        _exact_keys(
            evidence,
            {
                "schema",
                "status",
                "raw_data_bound",
                "calibration_pass",
                "nuisance_controls_pass",
                "preregistered",
                "authority_effect",
            },
        )
        and evidence.get("schema") == "AEGIS_GQ_PHYSICAL_MEASUREMENT_RECEIPT_V1"
        and evidence.get("status") == "PASS"
        and evidence.get("raw_data_bound") is True
        and evidence.get("calibration_pass") is True
        and evidence.get("nuisance_controls_pass") is True
        and evidence.get("preregistered") is True
        and evidence.get("authority_effect") == "NONE"
    )
    return _receipt(
        gate_id,
        relation,
        MEASUREMENT_VERIFIER_ID,
        ok,
        {"measurement_receipt_valid": ok},
    )


def nuisance_control_verifier(
    gate_id: str,
    relation: ri.RelationBindingV1,
    evidence: Mapping[str, Any],
) -> ri.GateReceipt:
    required = {
        "mechanical_cross_talk",
        "seismic_vibration",
        "electromagnetic",
        "laser_readout_cross_talk",
        "thermal_common_bath",
        "feedback_control",
        "gravity_gradient_position",
    }
    controls = evidence.get("controls")
    ok = (
        _exact_keys(evidence, {"schema", "controls", "authority_effect"})
        and evidence.get("schema") == "AEGIS_GQ_NUISANCE_RECEIPT_V1"
        and isinstance(controls, Mapping)
        and set(controls) == required
        and all(value == "PASS" for value in controls.values())
        and evidence.get("authority_effect") == "NONE"
    )
    return _receipt(
        gate_id,
        relation,
        NUISANCE_VERIFIER_ID,
        ok,
        {"nuisance_controls_valid": ok},
    )


def independent_replication_verifier(
    gate_id: str,
    relation: ri.RelationBindingV1,
    evidence: Mapping[str, Any],
) -> ri.GateReceipt:
    ok = (
        _exact_keys(
            evidence,
            {
                "schema",
                "status",
                "independent_apparatus",
                "independent_analysis",
                "same_preregistered_claim",
                "authority_effect",
            },
        )
        and evidence.get("schema") == "AEGIS_GQ_REPLICATION_RECEIPT_V1"
        and evidence.get("status") == "PASS"
        and evidence.get("independent_apparatus") is True
        and evidence.get("independent_analysis") is True
        and evidence.get("same_preregistered_claim") is True
        and evidence.get("authority_effect") == "NONE"
    )
    return _receipt(
        gate_id,
        relation,
        REPLICATION_VERIFIER_ID,
        ok,
        {"replication_receipt_valid": ok},
    )


_register(F2B_KERNEL_VERIFIER_ID, f2b_kernel_verifier)
_register(D2_MODEL_VERIFIER_ID, d2_model_formula_verifier)
_register(MEASUREMENT_VERIFIER_ID, physical_measurement_verifier)
_register(NUISANCE_VERIFIER_ID, nuisance_control_verifier)
_register(REPLICATION_VERIFIER_ID, independent_replication_verifier)
