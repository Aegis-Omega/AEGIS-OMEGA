#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum Interface V3 counterfactual evidence chain.

V3 binds the V2 terminal hash to exact-rational published-formula comparisons. It may
establish that algebraically discriminating parameter regions exist, but it cannot turn
that simulation into an empirical model selection without point-level measurements and
apparatus-systematics propagation.
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
from gravity_quantum.v2_pipeline import receipt as v2_receipt
from gravity_quantum.counterfactual_v3 import (
    build_counterfactual_grid,
    published_formula_binding,
)

V3_SCHEMA = "AEGIS_GRAVITY_QUANTUM_EVIDENCE_V3"


def parent_evidence() -> dict:
    parent = v2_receipt()
    if not parent["certification"]["is_valid"]:
        raise ValueError("PARENT_V2_CERTIFICATION_FAILED")
    return {
        "schema": parent["schema"],
        "terminal_hash": parent["terminal_hash"],
        "certified": True,
        "binding_semantics": "V2_TERMINAL_HASH_REFERENCE_ONLY",
        "authority_effect": "NONE",
    }


def divergence_analysis(grid: dict) -> dict:
    rows = grid.get("rows", [])
    divergent = [row for row in rows if row.get("formula_divergence") is True]
    levitation_controls = [row for row in rows if row.get("levitation_condition") is True]

    return {
        "schema": "AEGIS_QGI_FORMULA_DIVERGENCE_ANALYSIS_V3",
        "simulation_result": (
            "DISCRIMINATING_PARAMETER_REGIONS_EXIST"
            if divergent
            else "NO_DIVERGENCE_FOUND_IN_PREREGISTERED_GRID"
        ),
        "divergent_row_count": len(divergent),
        "total_row_count": len(rows),
        "levitation_control_count": len(levitation_controls),
        "divergent_r_values": [copy.deepcopy(row["r"]) for row in divergent],
        "interpretation_boundary": (
            "ALGEBRAIC_DIVERGENCE_BETWEEN_PUBLISHED_FORMULA_FORMS;_"
            "COMMENT_OFF_LEVITATION_EXTENSION_IS_CONTESTED_BY_REPLY"
        ),
        "empirical_model_selection": "BLOCKED",
        "authority_effect": "NONE",
    }


def v3_disposition(analysis: dict) -> dict:
    if analysis["simulation_result"] != "DISCRIMINATING_PARAMETER_REGIONS_EXIST":
        raise ValueError("V3_PREREGISTERED_GRID_DID_NOT_DISCRIMINATE")
    return {
        "decision": "HOLD_RESEARCH_ONLY",
        "simulation_result": analysis["simulation_result"],
        "empirical_model_selection": "BLOCKED",
        "mechanistic_winner": "NOT_ESTABLISHED",
        "execution_release": "BLOCKED",
        "claim_promotion": "BLOCKED",
        "quantum_gravity_status": "NOT_TESTED",
        "reason_codes": [
            "SIMULATION_ONLY_NO_POINT_LEVEL_DATA",
            "COMMENT_EQ6_OFF_LEVITATION_DOMAIN_CONTESTED",
            "APPARATUS_SYSTEMATICS_NOT_PROPAGATED",
        ],
        "next_required_evidence": [
            "POINT_LEVEL_PHASE_VS_TIME_DATA",
            "INDEPENDENT_MAGNETIC_GRADIENT_BINDING",
            "CLOSING_CONDITION_VERIFICATION_OFF_LEVITATION",
            "APPARATUS_NUISANCE_PROPAGATION",
        ],
        "authority_effect": "NONE",
    }


def build_chain() -> LineageChain:
    parent = parent_evidence()
    binding = published_formula_binding()
    grid = build_counterfactual_grid()
    analysis = divergence_analysis(grid)

    chain = LineageChain()
    chain.append("PARENT_V2_EVIDENCE", parent)
    chain.append("PUBLISHED_FORMULA_BINDING", binding)
    chain.append("COUNTERFACTUAL_GRID", grid)
    chain.append("FORMULA_DIVERGENCE_ANALYSIS", analysis)
    chain.append("V3_DISPOSITION", v3_disposition(analysis))
    return chain


def receipt() -> dict:
    parent = parent_evidence()
    chain = build_chain()
    certification = chain.certify()
    if not certification["is_valid"]:
        raise ValueError("V3_CHAIN_CERTIFICATION_FAILED")
    return {
        "schema": V3_SCHEMA,
        "parent_v2_terminal_hash": parent["terminal_hash"],
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
