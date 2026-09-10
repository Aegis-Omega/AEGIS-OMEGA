#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum Interface V4 point-level ingress evidence chain.

V4 proves only that the ingress contract is implemented and replay-verifiable against an
explicit TEST_FIXTURE. It does not claim that real QGI point-level data have been ingested,
that an empirical fit has run, or that any physical mechanism has been selected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verifiable.chain import LineageChain
from gravity_quantum.v3_pipeline import receipt as v3_receipt
from gravity_quantum.ingress_v4 import (
    CONTRACT_FIXTURE_BYTES,
    V4_INGRESS_SCHEMA,
    build_contract_fixture,
    fit_release_gate,
    validate_ingress,
)

V4_SCHEMA = "AEGIS_GRAVITY_QUANTUM_EVIDENCE_V4"


def parent_evidence() -> dict:
    parent = v3_receipt()
    if not parent["certification"]["is_valid"]:
        raise ValueError("PARENT_V3_CERTIFICATION_FAILED")
    return {
        "schema": parent["schema"],
        "terminal_hash": parent["terminal_hash"],
        "certified": True,
        "binding_semantics": "V3_TERMINAL_HASH_REFERENCE_ONLY",
        "authority_effect": "NONE",
    }


def ingress_policy() -> dict:
    return {
        "schema": "AEGIS_QGI_POINT_LEVEL_INGRESS_POLICY_V4",
        "required_batch_schema": V4_INGRESS_SCHEMA,
        "required_source_binding": [
            "source_uri",
            "media_type",
            "evidence_origin",
            "source_sha256",
            "source_byte_length",
        ],
        "required_calibration_binding": [
            "calibration_epoch_id",
            "config_sha256",
            "valid_from",
            "valid_until",
        ],
        "required_point_fields": [
            "point_id",
            "time_us",
            "phase_microrad",
            "phase_sigma_microrad",
            "control_ratio_ppm",
            "calibration_epoch_id",
        ],
        "numeric_contract": "INTEGER_SCALED_UNITS_ONLY_NO_FLOAT",
        "uncertainty_contract": "PHASE_SIGMA_MICRORAD_MUST_BE_POSITIVE",
        "fit_release_requires": [
            "CONTRACT_VALID",
            "EXTERNAL_EXPERIMENTAL_SOURCE",
            "INDEPENDENT_SOURCE_VERIFICATION",
            "INDEPENDENT_CALIBRATION_VERIFICATION",
        ],
        "claim_promotion_from_structural_validation": "FORBIDDEN",
        "authority_effect": "NONE",
    }


def v4_disposition(validation: dict, gate: dict) -> dict:
    if validation.get("decision") != "CONTRACT_VALID":
        raise ValueError("V4_CONTRACT_FIXTURE_VALIDATION_FAILED")
    if gate.get("empirical_fit_release") != "BLOCKED":
        raise ValueError("V4_TEST_FIXTURE_MUST_NOT_RELEASE_EMPIRICAL_FIT")
    return {
        "decision": "HOLD_RESEARCH_ONLY",
        "contract_status": "IMPLEMENTED_AND_TESTED",
        "empirical_point_level_ingress": "NOT_PERFORMED",
        "empirical_fit_release": "BLOCKED",
        "mechanistic_winner": "NOT_ESTABLISHED",
        "claim_promotion": "BLOCKED",
        "quantum_gravity_status": "NOT_TESTED",
        "reason_codes": [
            "TEST_FIXTURE_ONLY",
            "NO_EXTERNAL_POINT_LEVEL_SOURCE_BOUND",
            "INDEPENDENT_SOURCE_VERIFICATION_MISSING",
            "INDEPENDENT_CALIBRATION_VERIFICATION_MISSING",
        ],
        "next_required_evidence": [
            "EXTERNAL_POINT_LEVEL_SOURCE_BYTES",
            "SOURCE_RETRIEVAL_RECEIPT_OR_EQUIVALENT_PROVENANCE",
            "EXPERIMENT_CALIBRATION_EPOCH_BINDING",
            "PER_POINT_PHASE_UNCERTAINTY",
            "INDEPENDENT_SOURCE_AND_CALIBRATION_VERIFICATION",
        ],
        "authority_effect": "NONE",
    }


def build_chain() -> LineageChain:
    parent = parent_evidence()
    policy = ingress_policy()
    fixture = build_contract_fixture()
    validation = validate_ingress(fixture["batch"], CONTRACT_FIXTURE_BYTES)
    gate = fit_release_gate(fixture["batch"], CONTRACT_FIXTURE_BYTES)

    chain = LineageChain()
    chain.append("PARENT_V3_EVIDENCE", parent)
    chain.append("INGRESS_POLICY", policy)
    chain.append("CONTRACT_FIXTURE", fixture)
    chain.append("INGRESS_VALIDATION", validation)
    chain.append("ANALYSIS_RELEASE_GATE", gate)
    chain.append("V4_DISPOSITION", v4_disposition(validation, gate))
    return chain


def receipt() -> dict:
    parent = parent_evidence()
    chain = build_chain()
    certification = chain.certify()
    if not certification["is_valid"]:
        raise ValueError("V4_CHAIN_CERTIFICATION_FAILED")
    return {
        "schema": V4_SCHEMA,
        "parent_v3_terminal_hash": parent["terminal_hash"],
        "terminal_hash": chain.terminal_hash(),
        "certification": certification,
        "stages": [
            {
                "sequence": rec.sequence,
                "stage": rec.stage,
                "stage_hash": rec.stage_hash,
                "previous_hash": rec.previous_hash,
                "output": copy.deepcopy(rec.output),
            }
            for rec in chain.records
        ],
    }


if __name__ == "__main__":
    print(json.dumps(receipt(), indent=2, sort_keys=True, ensure_ascii=False))
