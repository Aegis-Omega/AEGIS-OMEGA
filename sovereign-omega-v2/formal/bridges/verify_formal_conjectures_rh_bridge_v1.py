#!/usr/bin/env python3
"""Fail-closed validator for the AEGIS ↔ Formal Conjectures RH target bridge v1.

This validator intentionally cannot promote the Riemann Hypothesis. It pins the
external open conjecture and the existing conditional AEGIS Weil theorem and emits
only HOLD or DENY_PROMOTION while the semantic bridge remains unverified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "AEGIS_RH_EXTERNAL_TARGET_V1"
EXPECTED_EXTERNAL = {
    "repository": "google-deepmind/formal-conjectures",
    "revision": "74b736b53ce688f57bad186b5dd862daaeeb708e",
    "coordinate": "FormalConjectures/Millenium/RiemannHypothesis.lean::RiemannHypothesis.riemannHypothesis",
    "lean_toolchain": "leanprover/lean4:v4.33.1",
    "mathlib_revision": "0df444a360eaa60ab8c11dca51a86af692955474",
    "source_statement_sha256": "ca7957df321986a4d0fe6d3bfa78e9ca815ee505e1d93effd6559b8f2476aa25",
    "upstream_category": "research open",
    "upstream_proof_status": "NOT_PROVEN",
}
EXPECTED_AEGIS = {
    "repository": "Aegis-Omega/AEGIS-OMEGA",
    "revision": "41ad4ea70c09eb2b88c8457d3b7185c5db4f986a",
    "coordinate": "sovereign-omega-v2/formal/theories/Weil/Globalization.v::globalization_ready_implies_global_weil_positivity_v1",
    "source_statement_sha256": "52c43c47ecc64f6ca03635ca6cc9231f144e15417e4fecdbdeb31649639837c1",
    "claim_scope": "CONDITIONAL_GLOBAL_WEIL_POSITIVITY_ONLY",
}
REQUIRED_GATES = (
    "external_source_digest_verified",
    "aegis_source_digest_verified",
    "aegis_weil_semantics_mapped_to_mathlib",
    "semantic_implication_to_mathlib_rh_proved",
    "lean_axiom_audit_no_sorryAx",
    "clean_room_independent_replay",
    "independent_authority_receipt_verified",
)
EXPECTED_DISPOSITION = {
    "rh_proved": False,
    "claim_promotion": "BLOCKED",
    "merge": "NOT_PERFORMED",
    "authority_effect": "NONE",
}


class ManifestError(ValueError):
    """The bridge manifest violates the frozen v1 evidence boundary."""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{field} must be an object")
    return value


def _require_exact(actual: dict[str, Any], expected: dict[str, Any], prefix: str) -> None:
    for key, value in expected.items():
        if actual.get(key) != value:
            raise ManifestError(f"{prefix}.{key} is not pinned to the v1 value")


def evaluate(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("schema_version mismatch")
    if manifest.get("namespace") != "mathematics.rh.external_reference":
        raise ManifestError("namespace mismatch")
    if manifest.get("evidence_class") != "EXTERNAL_FORMAL_TARGET":
        raise ManifestError("evidence_class mismatch")

    external = _mapping(manifest.get("external_source"), "external_source")
    aegis = _mapping(manifest.get("aegis_source"), "aegis_source")
    bridge = _mapping(manifest.get("bridge"), "bridge")
    declared = _mapping(manifest.get("declared_disposition"), "declared_disposition")

    _require_exact(external, EXPECTED_EXTERNAL, "external_source")
    _require_exact(aegis, EXPECTED_AEGIS, "aegis_source")
    _require_exact(declared, EXPECTED_DISPOSITION, "declared_disposition")

    external_statement = external.get("source_statement")
    aegis_statement = aegis.get("source_statement")
    if not isinstance(external_statement, str) or not isinstance(aegis_statement, str):
        raise ManifestError("source statements must be UTF-8 strings")
    if _sha256_text(external_statement) != EXPECTED_EXTERNAL["source_statement_sha256"]:
        raise ManifestError("external source statement SHA-256 mismatch")
    if _sha256_text(aegis_statement) != EXPECTED_AEGIS["source_statement_sha256"]:
        raise ManifestError("AEGIS source statement SHA-256 mismatch")
    if "sorry" not in external_statement:
        raise ManifestError("pinned upstream target no longer records its open proof hole")

    # V1 is deliberately incapable of converting metadata into a proof claim.
    # A future bridge version requires actual proof-artifact validation, not a
    # boolean flip in this manifest.
    if bridge.get("status") != "OPEN":
        raise ManifestError("v1 bridge status is frozen OPEN until a proof-artifact validator exists")
    if not isinstance(bridge.get("promotion_requested"), bool):
        raise ManifestError("bridge.promotion_requested must be boolean")

    gates = _mapping(bridge.get("required_gates"), "bridge.required_gates")
    if set(gates) != set(REQUIRED_GATES):
        raise ManifestError("required gate set mismatch")
    if any(not isinstance(gates[name], bool) for name in REQUIRED_GATES):
        raise ManifestError("all required gates must be boolean")

    open_gates = [name for name in REQUIRED_GATES if not gates[name]]
    reason_codes = [
        "UPSTREAM_RH_OPEN_WITH_SORRY",
        "AEGIS_SOURCE_SCOPE_CONDITIONAL_GLOBAL_WEIL_POSITIVITY_ONLY",
        "AEGIS_TO_MATHLIB_RH_SEMANTIC_BRIDGE_OPEN",
    ]
    if open_gates:
        reason_codes.append("OPEN_REQUIRED_GATES")

    promotion_requested = bridge["promotion_requested"]
    decision = "DENY_PROMOTION" if promotion_requested else "HOLD_RESEARCH_ONLY"

    return {
        "schema_version": SCHEMA_VERSION,
        "target_id": manifest.get("target_id"),
        "external_revision": external["revision"],
        "aegis_revision": aegis["revision"],
        "decision": decision,
        "promotion_requested": promotion_requested,
        "open_gates": open_gates,
        "reason_codes": reason_codes,
        "rh_proved": False,
        "claim_promotion": "BLOCKED",
        "merge": "NOT_PERFORMED",
        "authority_effect": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        receipt = evaluate(manifest)
    except (OSError, json.JSONDecodeError, ManifestError) as exc:
        print(json.dumps({"decision": "INVALID_MANIFEST", "error": str(exc)}, sort_keys=True))
        return 2

    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    # Presence of an OPEN research bridge is not a repository failure. A
    # requested promotion is fail-closed and therefore returns a non-zero code.
    return 3 if receipt["decision"] == "DENY_PROMOTION" else 0


if __name__ == "__main__":
    raise SystemExit(main())
