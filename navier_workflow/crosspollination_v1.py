"""Provenance-preserving cross-pollination for AEGIS Navier workflow V1."""

from __future__ import annotations

from navier_workflow.schema_v1 import sha256_digest, validate_candidate


def synthesize_shared_state(candidates: list[dict]) -> dict:
    validated = [validate_candidate(candidate) for candidate in candidates]
    ordered = sorted(validated, key=lambda item: item["artifact_digest"])

    imports = [
        {
            "candidate_id": item["candidate_id"],
            "artifact_digest": item["artifact_digest"],
            "claim": item["claim"],
            "claim_scope": item["claim_scope"],
            "assumptions": list(item["assumptions"]),
            "source_coordinates": list(item["source_coordinates"]),
            "open_obligations": list(item["open_obligations"]),
        }
        for item in ordered
    ]

    state = {
        "schema": "AEGIS_NAVIER_SHARED_STATE_V1",
        "imports": imports,
        "assumption_sets": {
            item["artifact_digest"]: list(item["assumptions"])
            for item in ordered
        },
        "claim_promotion": "BLOCKED",
        "authority_effect": "NONE",
    }
    state["state_digest"] = sha256_digest(state)
    return state
