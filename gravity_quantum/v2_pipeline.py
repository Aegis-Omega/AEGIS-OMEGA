#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum Interface V2 evidence chain.

V2 extends, but does not promote, the V1 evidence lane. It binds the V1 terminal
hash, scaled arXiv-v4 numerical evidence, the narrow cubic-prefactor
identifiability result, and a fail-closed model-discrimination disposition.
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
from gravity_quantum.evidence_pipeline import receipt as v1_receipt
from gravity_quantum.measurement_v2 import (
    build_measurement_receipt,
    cubic_prefactor_identity,
    discriminate_published_models,
)

V2_SCHEMA = "AEGIS_GRAVITY_QUANTUM_EVIDENCE_V2"


def parent_evidence() -> dict:
    parent = v1_receipt()
    if not parent["certification"]["is_valid"]:
        raise ValueError("PARENT_V1_CERTIFICATION_FAILED")
    return {
        "schema": parent["schema"],
        "terminal_hash": parent["terminal_hash"],
        "source_doi": parent["source_doi"],
        "certified": True,
        "binding_semantics": "V1_TERMINAL_HASH_REFERENCE_ONLY",
        "authority_effect": "NONE",
    }


def v2_disposition(discrimination: dict) -> dict:
    if discrimination["decision"] != "NO_UNIQUE_MODEL_SELECTION":
        raise ValueError("UNEXPECTED_MODEL_SELECTION_STATE")
    return {
        "decision": "HOLD_RESEARCH_ONLY",
        "execution_release": "BLOCKED",
        "claim_promotion": "BLOCKED",
        "model_selection": discrimination["decision"],
        "mechanistic_winner": discrimination["promotion_boundary"]["mechanistic_winner"],
        "equivalence_principle_status": discrimination["promotion_boundary"]["equivalence_principle_status"],
        "quantum_gravity_status": discrimination["promotion_boundary"]["quantum_gravity_status"],
        "reason_codes": list(discrimination["reason_codes"]),
        "authority_effect": "NONE",
    }


def build_chain() -> LineageChain:
    parent = parent_evidence()
    measurement = build_measurement_receipt()
    identifiability = cubic_prefactor_identity()
    discrimination = discriminate_published_models(measurement)

    chain = LineageChain()
    chain.append("PARENT_EVIDENCE", parent)
    chain.append("SCALED_MEASUREMENT", measurement)
    chain.append("CUBIC_PREFACTOR_IDENTIFIABILITY", identifiability)
    chain.append("MODEL_DISCRIMINATION", discrimination)
    chain.append("V2_DISPOSITION", v2_disposition(discrimination))
    return chain


def receipt() -> dict:
    parent = parent_evidence()
    chain = build_chain()
    certification = chain.certify()
    if not certification["is_valid"]:
        raise ValueError("V2_CHAIN_CERTIFICATION_FAILED")
    return {
        "schema": V2_SCHEMA,
        "parent_v1_terminal_hash": parent["terminal_hash"],
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
