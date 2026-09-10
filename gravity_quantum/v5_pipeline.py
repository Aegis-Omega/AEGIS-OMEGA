#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum V5 external dataset adapter evidence chain.

V5 proves the external CSV adapter contract against an explicit test fixture only. It does
not claim that author-provided QGI point-level data were found, downloaded, authenticated,
ingested, fitted, or used to select a physical mechanism.
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
from gravity_quantum.v4_pipeline import receipt as v4_receipt
from gravity_quantum.external_adapter_v5 import (
    CONTRACT_CSV_BYTES,
    EXPECTED_COLUMNS,
    build_dataset_candidate,
)

V5_SCHEMA = "AEGIS_GRAVITY_QUANTUM_EVIDENCE_V5"


def parent_evidence() -> dict:
    parent = v4_receipt()
    if not parent["certification"]["is_valid"]:
        raise ValueError("PARENT_V4_CERTIFICATION_FAILED")
    return {
        "schema": parent["schema"],
        "terminal_hash": parent["terminal_hash"],
        "certified": True,
        "binding_semantics": "V4_TERMINAL_HASH_REFERENCE_ONLY",
        "authority_effect": "NONE",
    }


def adapter_policy() -> dict:
    return {
        "schema": "AEGIS_QGI_EXTERNAL_ADAPTER_POLICY_V5",
        "accepted_media_type": "text/csv",
        "exact_columns": list(EXPECTED_COLUMNS),
        "numeric_contract": "BASE10_INTEGER_TEXT_ONLY",
        "source_transport": "CALLER_SUPPLIED_BYTES_ONLY",
        "network_fetch_performed": False,
        "figure_digitization_permitted_as_raw_data": False,
        "source_authentication": "DELEGATED_TO_V4_EXACT_RECEIPT_ENROLLMENT_GATE",
        "adapter_output_authority": "CANDIDATE_ONLY",
        "authority_effect": "NONE",
    }


def v5_disposition(candidate: dict) -> dict:
    if candidate.get("adapter_status") != "CANDIDATE_ONLY":
        raise ValueError("V5_ADAPTER_STATUS_INVALID")
    if candidate.get("release_gate", {}).get("empirical_fit_release") != "BLOCKED":
        raise ValueError("V5_FIXTURE_MUST_NOT_RELEASE_EMPIRICAL_FIT")
    return {
        "decision": "HOLD_RESEARCH_ONLY",
        "adapter_status": "IMPLEMENTED_AND_TESTED",
        "external_dataset_ingress": "NOT_PERFORMED",
        "author_raw_point_level_dataset": "NOT_FOUND_OR_BOUND",
        "empirical_fit_release": "BLOCKED",
        "mechanistic_winner": "NOT_ESTABLISHED",
        "claim_promotion": "BLOCKED",
        "quantum_gravity_status": "NOT_TESTED",
        "reason_codes": [
            "CONTRACT_FIXTURE_ONLY",
            "NO_AUTHOR_RAW_POINT_LEVEL_DATASET_BOUND",
            "NO_TRUSTED_VERIFICATION_RECEIPT_ENROLLED",
        ],
        "next_required_input": [
            "AUTHOR_OR_LAB_POINT_LEVEL_CSV_OR_EQUIVALENT_BYTES",
            "EXACT_SOURCE_URI_AND_RETRIEVAL_PROVENANCE",
            "CALIBRATION_CONFIG_AND_EPOCH",
            "INDEPENDENT_SOURCE_AND_CALIBRATION_VERIFICATION_RECEIPTS",
            "REPOSITORY_ENROLLMENT_OF_EXACT_VERIFICATION_RECEIPT_DIGESTS",
        ],
        "authority_effect": "NONE",
    }


def build_chain() -> LineageChain:
    parent = parent_evidence()
    policy = adapter_policy()
    candidate = build_dataset_candidate(
        CONTRACT_CSV_BYTES,
        evidence_origin="TEST_FIXTURE",
    )

    chain = LineageChain()
    chain.append("PARENT_V4_EVIDENCE", parent)
    chain.append("EXTERNAL_ADAPTER_POLICY", policy)
    chain.append(
        "CSV_CONTRACT_FIXTURE",
        {
            "fixture_sha256": candidate["batch"]["source_binding"]["source_sha256"],
            "fixture_byte_length": len(CONTRACT_CSV_BYTES),
            "fixture_status": "TEST_FIXTURE_NOT_EMPIRICAL_EVIDENCE",
            "authority_effect": "NONE",
        },
    )
    chain.append("ADAPTER_CANDIDATE", candidate)
    chain.append("V5_DISPOSITION", v5_disposition(candidate))
    return chain


def receipt() -> dict:
    parent = parent_evidence()
    chain = build_chain()
    certification = chain.certify()
    if not certification["is_valid"]:
        raise ValueError("V5_CHAIN_CERTIFICATION_FAILED")
    return {
        "schema": V5_SCHEMA,
        "parent_v4_terminal_hash": parent["terminal_hash"],
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
