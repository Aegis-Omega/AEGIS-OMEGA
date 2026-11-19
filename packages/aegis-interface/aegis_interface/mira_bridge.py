"""AEGIS MIRA/RH bridge into the *existing* RFC-0001 WIT compiler.

No RH admission, no Lean execution, and no trust in caller-supplied receipts.
The compiler is imported from the original aegis-interface package; if it is
absent, the bridge fails instead of substituting an imitation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .math_rh import ProofHold, canonical, project_wit_receipt

BRIDGE_SCHEMA = "aegis-mira-rh-wit-bridge/v2"
EXPECTED_FIELDS = (
    "kind", "state", "statement_sha256", "receipt_sha256", "scope",
    "authority_class", "lean_kernel_checked", "riemann_hypothesis_proven",
)
EXPECTED_KINDS = ("reflection_polynomial", "finite_gram_sos", "support_prime_cutoff")
EXPECTED_STATES = ("local_exact", "conditional_support", "hold")
WIT_NAME = "MIRAMathReceipt"
SOURCE_PINS = {
    "WeilCriterionCompactSmoothV1.lean": "48039592aa281da1aa514586e09aab09720dd679",
    "WeilPrimeSummabilityV1.lean": "5952cac81f515a5ac784cd51e9b3c187d1727d8a",
    "WeilAutocorrelationRealityV1.lean": "84d389c16b46427d1432f16a3f76baf031fba67c",
    "WeilAutocorrelationClosureV1.lean": "8a578da0d379d2a643c2ce436a97a4ff5e3531eb",
}
SOURCE_COMMIT = "f10d066152dd07fcbe6497566213d91f29e68c5a"
SOURCE_REPO = "Aegis-Omega/AEGIS-OMEGA"
SOURCE_BRANCH_STATUS = "CLOSED_UNMERGED_PR_493"


def git_blob_sha(content: bytes) -> str:
    """Exact Git blob digest, independent of Git CLI and newlines."""
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\x00" + content).hexdigest()


def verify_lean_sources(lean_directory: Path) -> dict[str, str]:
    """Fail closed if even one imported Weil module differs from source pin."""
    checks: dict[str, str] = {}
    for name, expected in SOURCE_PINS.items():
        source = (lean_directory / name)
        try:
            got = git_blob_sha(source.read_bytes())
        except OSError as exc:
            raise ProofHold(f"HOLD_LEAN_SOURCE_MISSING:{name}") from exc
        if got != expected:
            raise ProofHold(f"HOLD_LEAN_SOURCE_BLOB_MISMATCH:{name}:{got}")
        checks[name] = got
    return checks


def _required_upstream_compiler(wit_source: str):
    try:
        from .compiler import compile_source
    except ImportError as exc:
        raise ProofHold("HOLD_REAL_AEGIS_COMPILER_UNAVAILABLE") from exc
    try:
        result = compile_source(wit_source)
        eq = result.equivalence()
    except Exception as exc:
        raise ProofHold("HOLD_REAL_AEGIS_COMPILER_REJECTED_CONTRACT") from exc
    if not eq.ok:
        raise ProofHold("HOLD_RUST_TS_PY_STRUCTURAL_DRIFT:" + eq.text())
    return result


def verify_wit_contract(wit_path: Path) -> dict[str, Any]:
    """Compile through the real WIT->AST->IR->{Rust, TS, Python} pipeline."""
    try:
        raw = wit_path.read_bytes()
        source = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ProofHold("HOLD_WIT_SOURCE_UNAVAILABLE") from exc
    result = _required_upstream_compiler(source)
    rows = [r for r in result.ir.records if r.name == WIT_NAME]
    kinds = [v for v in result.ir.variants if v.name == "MathClaimKind"]
    states = [v for v in result.ir.variants if v.name == "MathClaimState"]
    if len(result.ir.records) != 1 or len(rows) != 1 or len(result.ir.variants) != 2:
        raise ProofHold("HOLD_UNEXPECTED_WIT_DECLARATIONS")
    if len(kinds) != 1 or tuple(kinds[0].cases) != EXPECTED_KINDS:
        raise ProofHold("HOLD_WIT_CLAIM_KIND_DRIFT")
    if len(states) != 1 or tuple(states[0].cases) != EXPECTED_STATES:
        raise ProofHold("HOLD_WIT_CLAIM_STATE_DRIFT")
    if tuple(field.name for field in rows[0].fields) != EXPECTED_FIELDS:
        raise ProofHold("HOLD_WIT_FIELD_DRIFT")
    from .ir import canonical_schema
    schema = canonical_schema(result.ir)
    fields = schema["records"][WIT_NAME]
    expected_types = {
        "kind": "MathClaimKind", "state": "MathClaimState",
        "statement_sha256": "string", "receipt_sha256": "string",
        "scope": "string", "authority_class": "string",
        "lean_kernel_checked": "bool", "riemann_hypothesis_proven": "bool",
    }
    if {f["name"]: f["type"] for f in fields} != expected_types:
        raise ProofHold("HOLD_WIT_TYPE_DRIFT")
    return {
        "wit_sha256": hashlib.sha256(raw).hexdigest(),
        "schema_sha256": hashlib.sha256(result.schema_json.encode("utf-8")).hexdigest(),
        "rust_sha256": hashlib.sha256(result.rust.encode("utf-8")).hexdigest(),
        "typescript_sha256": hashlib.sha256(result.typescript.encode("utf-8")).hexdigest(),
        "python_sha256": hashlib.sha256(result.python.encode("utf-8")).hexdigest(),
        "equivalence": "PASS_ORIGINAL_COMPILER",
    }


def build_bridge(receipt: dict, wit_path: Path, lean_directory: Path | None = None) -> dict:
    """Link arithmetic to WIT and optionally to *exact* historical Lean blobs.

    Does NOT admit a Lean theorem unless a separate real kernel runner is used.
    """
    typed = project_wit_receipt(receipt)
    contract = verify_wit_contract(wit_path)
    evidence: dict = {
        "schema": BRIDGE_SCHEMA,
        "source_repo": SOURCE_REPO,
        "source_commit": SOURCE_COMMIT,
        "source_branch_status": SOURCE_BRANCH_STATUS,
        "source_pins_expected": SOURCE_PINS,
        "lean_source_blobs_verified_locally": None,
        "lean_source_binding": "UNKNOWN_NOT_PRESENT",
        "wit": contract,
        "typed_projection": typed,
        "authority_class": "NONE",
        "lean_kernel_checked": False,
        "riemann_hypothesis_proven": False,
        "open_obligations": [
            "membership in actual WeilCompactSmoothGV1 and two moment conditions",
            "full zero-prime-archimedean explicit formula with unchanged dy normalization",
            "universal sign forall admissible g, not just finite Gram matrices",
            "Lean kernel compile, axioms audit and exact Mathlib RH target replay",
        ],
    }
    if lean_directory is not None:
        evidence["lean_source_blobs_verified_locally"] = verify_lean_sources(lean_directory)
        evidence["lean_source_binding"] = "MATCH_EXACT_GIT_BLOB_PINS_ONLY"
    evidence["bridge_sha256"] = hashlib.sha256(canonical(evidence)).hexdigest()
    return evidence


def verify_bridge(evidence: dict, receipt: dict, wit_path: Path, lean_directory: Path | None = None) -> bool:
    if not isinstance(evidence, dict) or "bridge_sha256" not in evidence:
        raise ProofHold("HOLD_BRIDGE_SCHEMA")
    replay = build_bridge(receipt, wit_path, lean_directory)
    if canonical(replay) != canonical(evidence):
        raise ProofHold("HOLD_BRIDGE_REPLAY_MISMATCH")
    return True
