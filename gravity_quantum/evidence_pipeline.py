#!/usr/bin/env python3
"""AEGIS Ω Gravity–Quantum Interface evidence lane.

Purpose: bind observation, model-consistency, interpretation, and open quantum-gravity
claims into separate replay-verifiable stages. The pipeline is deliberately incapable
of promoting a measured matter-wave phase into a claim that gravity itself is quantized.

No floating-point values are admitted into hashed state. Experimental numbers, when
added later, must use explicit integer units (for example phase_microrad) plus unit labels.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verifiable.chain import LineageChain

PRIMARY_DOI = "10.1126/sciadv.aec8045"
PRIMARY_TITLE = "Observation of the quantum phase of free fall and the consistency with the equivalence principle"
PRIMARY_JOURNAL = "Science Advances"
PRIMARY_DATE = "2026-09-02"

STATUS = {
    "OBSERVED",
    "SUPPORTED",
    "INTERPRETATION_DEBATE",
    "OPEN",
    "NOT_TESTED",
}

FORBIDDEN_PROMOTIONS = {
    "quantum_gravity_proven": "NOT_TESTED",
    "gravity_quantized": "NOT_TESTED",
    "gravitational_field_superposition_observed": "NOT_TESTED",
    "qm_gr_unified": "NOT_TESTED",
}

ALLOWED_CLAIMS = {
    "predicted_free_fall_quantum_phase_observed": "OBSERVED",
    "equivalence_principle_consistent_in_reported_low_energy_quantum_regime": "SUPPORTED",
    "alternative_phase_interpretation_has_published_comment_and_reply": "INTERPRETATION_DEBATE",
}


def primary_source() -> dict:
    return {
        "source_id": "SCIADV_AEC8045",
        "source_kind": "PRIMARY_PEER_REVIEWED",
        "title": PRIMARY_TITLE,
        "journal": PRIMARY_JOURNAL,
        "published_date": PRIMARY_DATE,
        "doi": PRIMARY_DOI,
    }


def experiment_scope() -> dict:
    return {
        "experiment_id": "QGI_FREE_FALL_PHASE_2026",
        "apparatus_class": "COLD_ATOM_INTERFEROMETER",
        "comparison": ["LAB_FRAME_STATIC_WAVE_PACKET", "FREE_FALL_WAVE_PACKET"],
        "regime": "LOW_ENERGY_EARTH_GRAVITY",
        "measured_object": "RELATIVE_QUANTUM_PHASE",
        "does_not_measure": [
            "GRAVITON",
            "QUANTIZED_GRAVITATIONAL_FIELD",
            "GRAVITATIONAL_FIELD_SUPERPOSITION",
        ],
    }


def observation() -> dict:
    return {
        "claim_id": "predicted_free_fall_quantum_phase_observed",
        "status": "OBSERVED",
        "source_id": "SCIADV_AEC8045",
        "statement": "Reported relative matter-wave phase agrees with the predicted free-fall quantum phase in the tested setup.",
    }


def model_consistency() -> dict:
    return {
        "claim_id": "equivalence_principle_consistent_in_reported_low_energy_quantum_regime",
        "status": "SUPPORTED",
        "source_id": "SCIADV_AEC8045",
        "statement": "The reported observation is consistent with applying the equivalence principle in the authors' low-energy quantum regime.",
        "non_equivalence": "CONSISTENCY_IS_NOT_UNIFICATION",
    }


def interpretation_debate() -> dict:
    return {
        "claim_id": "alternative_phase_interpretation_has_published_comment_and_reply",
        "status": "INTERPRETATION_DEBATE",
        "comment_id": "ARXIV_2504_15409",
        "reply_id": "ARXIV_2504_21626",
        "statement": "A technical comment attributed the phase to magnetic recoil/apparatus forcing; the experiment authors published a reply disputing that conclusion.",
        "authority_effect": "NONE",
    }


def open_boundary() -> dict:
    return {
        "status": "NOT_TESTED",
        "claims": sorted(FORBIDDEN_PROMOTIONS),
        "statement": "This experiment does not, by itself, establish quantization of gravity or a quantum theory of gravity.",
    }


def classify_claim(claim_id: str, evidence_statuses: Iterable[str]) -> dict:
    statuses = list(evidence_statuses)
    unknown = sorted(set(statuses) - STATUS)
    if unknown:
        return {
            "claim_id": claim_id,
            "decision": "DENY",
            "admitted_status": "NOT_TESTED",
            "authority_effect": "NONE",
            "reason_codes": ["UNKNOWN_EVIDENCE_STATUS"],
        }

    if claim_id in FORBIDDEN_PROMOTIONS:
        return {
            "claim_id": claim_id,
            "decision": "DENY",
            "admitted_status": FORBIDDEN_PROMOTIONS[claim_id],
            "authority_effect": "NONE",
            "reason_codes": ["CLAIM_BEYOND_EXPERIMENT_SCOPE", "NO_DIRECT_QUANTUM_GRAVITY_EVIDENCE"],
        }

    required = ALLOWED_CLAIMS.get(claim_id)
    if required is None:
        return {
            "claim_id": claim_id,
            "decision": "DENY",
            "admitted_status": "OPEN",
            "authority_effect": "NONE",
            "reason_codes": ["UNREGISTERED_CLAIM"],
        }

    if required not in statuses:
        return {
            "claim_id": claim_id,
            "decision": "DENY",
            "admitted_status": "OPEN",
            "authority_effect": "NONE",
            "reason_codes": ["REQUIRED_EVIDENCE_STATUS_MISSING"],
        }

    return {
        "claim_id": claim_id,
        "decision": "ADMIT_BOUNDED_CLAIM",
        "admitted_status": required,
        "authority_effect": "EPISTEMIC_ONLY",
        "reason_codes": [],
    }


def build_chain() -> LineageChain:
    chain = LineageChain()
    chain.append("PRIMARY_SOURCE", primary_source())
    chain.append("EXPERIMENT_SCOPE", experiment_scope())
    chain.append("OBSERVATION", observation())
    chain.append("MODEL_CONSISTENCY", model_consistency())
    chain.append("INTERPRETATION_DEBATE", interpretation_debate())
    chain.append("OPEN_BOUNDARY", open_boundary())
    chain.append(
        "CLAIM_DISPOSITION",
        {
            "bounded": classify_claim(
                "equivalence_principle_consistent_in_reported_low_energy_quantum_regime",
                ["OBSERVED", "SUPPORTED", "INTERPRETATION_DEBATE"],
            ),
            "forbidden": classify_claim(
                "quantum_gravity_proven",
                ["OBSERVED", "SUPPORTED"],
            ),
        },
    )
    return chain


def receipt() -> dict:
    chain = build_chain()
    return {
        "schema": "AEGIS_GRAVITY_QUANTUM_EVIDENCE_V1",
        "source_doi": PRIMARY_DOI,
        "terminal_hash": chain.terminal_hash(),
        "certification": chain.certify(),
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
