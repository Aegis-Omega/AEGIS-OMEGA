#!/usr/bin/env python3
"""Fail-closed Coq axiom policy independent of the assumption baseline.

The baseline answers "what changed?".  This policy answers the orthogonal
question "is this dependency admissible at all?".  Diagnostic trust probes are
retained as evidence but are never promoted into theorem authority.
"""

from __future__ import annotations

from typing import Any

AUTHORITY_ELIGIBLE = "AUTHORITY_ELIGIBLE"
DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
CLASSICAL_REAL_FOUNDATION = "CLASSICAL_REAL_ANALYSIS_FOUNDATION"
ABSTRACTION_PARAMETER = "ABSTRACTION_OVER_IMPLEMENTATION"

DIAGNOSTIC_ONLY_PATHS = frozenset(
    {
        "Weil/O0TrustProbeReals.v",
        "Weil/O0TrustProbeFunction.v",
        "Weil/O0TrustProbeCompact.v",
        "Weil/O0TrustProbeContinuity.v",
    }
)

# Parameters abstract over implementations; they are not proposition-valued
# shortcuts.  Source Axioms are handled separately and can never enter through
# this allowlist merely by reusing an allowed parameter name.
SOURCE_PARAMETER_POLICY: dict[str, dict[str, str]] = {
    "sha256": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Core/Hash.v abstracts over the hash implementation.",
    },
    "encode_JS": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the JS encoder.",
    },
    "encode_WASM": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the WASM encoder.",
    },
    "encode_PY": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the Python encoder.",
    },
    "step_JS": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the JS transition function.",
    },
    "step_WASM": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the WASM transition function.",
    },
    "step_PY": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the Python transition function.",
    },
}

# Imported theorem assumptions are classified separately from source
# declarations.  The constructive O0 authority files are required by their
# dedicated gate to remain CLOSED; these classical entries exist for other
# explicitly classical analysis surfaces and cannot weaken that stronger gate.
THEOREM_ASSUMPTION_POLICY: dict[str, dict[str, str]] = {
    "ClassicalDedekindReals.sig_forall_dec": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": "Standard-library classical Dedekind-real foundation.",
    },
    "ClassicalDedekindReals.sig_not_dec": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": "Companion decision principle from the same real foundation.",
    },
    "FunctionalExtensionality.functional_extensionality_dep": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": "Dependent functional extensionality used by classical function-space reasoning.",
    },
    "FunctionalExtensionality.functional_extensionality": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": "Functional extensionality used by classical function-space reasoning.",
    },
    "Hash.sha256": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Reducer theorem is parametric in the abstract hash implementation.",
    },
}

TARGET_CLAIM_AXIOM_NOTE = "Bisimulation/ThreeWay.v::cross_runtime_bisimulation"


def _scope(entry: dict[str, Any]) -> str:
    explicit = entry.get("evidence_scope")
    if explicit in {AUTHORITY_ELIGIBLE, DIAGNOSTIC_ONLY}:
        return explicit
    return DIAGNOSTIC_ONLY if entry.get("path") in DIAGNOSTIC_ONLY_PATHS else AUTHORITY_ELIGIBLE


def _record(location: str, symbol: str, kind: str) -> dict[str, str]:
    return {"location": location, "symbol": symbol, "kind": kind}


def evaluate_axiom_policy(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify source declarations and theorem assumptions fail-closed.

    Diagnostic entries are preserved in ``diagnostic_observations`` but cannot
    authorize, clear, or create production assumption debt.  Any Admitted proof
    is a violation in every scope.  Any source Axiom in an authority-eligible
    file is a violation regardless of its symbol.  Only explicitly named source
    Parameters and imported theorem assumptions can be permitted.
    """

    permitted: list[dict[str, str]] = []
    unpermitted: list[dict[str, str]] = []
    diagnostic: list[dict[str, str]] = []
    admitted_sources: list[str] = []

    for entry in sorted(files, key=lambda item: str(item.get("path", ""))):
        path = str(entry.get("path", ""))
        scope = _scope(entry)

        if int(entry.get("admitted_count", 0)):
            admitted_sources.append(path)

        for symbol in sorted(set(entry.get("axiom_symbols", []))):
            record = _record(path, symbol, "SOURCE_AXIOM")
            if scope == DIAGNOSTIC_ONLY:
                diagnostic.append(record)
            else:
                unpermitted.append(record)

        for symbol in sorted(set(entry.get("parameter_symbols", []))):
            record = _record(path, symbol, "SOURCE_PARAMETER")
            if scope == DIAGNOSTIC_ONLY:
                diagnostic.append(record)
                continue
            policy = SOURCE_PARAMETER_POLICY.get(symbol)
            if policy is None:
                unpermitted.append(record)
            else:
                permitted.append({**record, **policy})

        for theorem in entry.get("theorems", []):
            theorem_name = str(theorem.get("theorem", ""))
            location = f"{path}::{theorem_name}"
            for symbol in sorted(set(theorem.get("assumption_symbols", []))):
                record = _record(location, symbol, "THEOREM_ASSUMPTION")
                if scope == DIAGNOSTIC_ONLY:
                    diagnostic.append(record)
                    continue
                policy = THEOREM_ASSUMPTION_POLICY.get(symbol)
                if policy is None:
                    unpermitted.append(record)
                else:
                    permitted.append({**record, **policy})

    return {
        "policy_kind": "COQ_AXIOM_POLICY_V2",
        "policy_violation": bool(unpermitted) or bool(admitted_sources),
        "unpermitted_assumptions": unpermitted,
        "permitted_assumptions": permitted,
        "diagnostic_observations": diagnostic,
        "admitted_sources": sorted(set(admitted_sources)),
        "target_claim_axiom_note": TARGET_CLAIM_AXIOM_NOTE,
    }
