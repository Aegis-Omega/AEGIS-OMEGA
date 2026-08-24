#!/usr/bin/env python3
"""AEGIS Coq formal-attestation receipt generator.

This module does not prove mathematics. It records source structure, compiler
outcomes, and `Print Assumptions` evidence so downstream gates can distinguish
compiled/axiom-free theorems from assumption-bearing or failed artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


RECEIPT_KIND = "COQ_FORMAL_ATTESTATION_RECEIPT_V1"
AUTHORITY = "FORMAL_MATH_EVIDENCE_ONLY"
THEOREM_RE = re.compile(
    r"(?m)^\s*(?:Theorem|Lemma|Corollary|Proposition|Fact|Remark)\s+([A-Za-z_][A-Za-z0-9_']*)\b"
)
QED_RE = re.compile(r"\bQed\s*\.")
AXIOM_STMT_RE = re.compile(r"(?m)^\s*Axioms?\b")
PARAMETER_STMT_RE = re.compile(r"(?m)^\s*Parameters?\b")
DECLARATION_RE = re.compile(r"(?m)^\s*(Axioms?|Parameters?)\s+([^:\n]+?)\s*:")
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
ASSUMPTION_SYMBOL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_'.]*)\s*:")
ADMITTED_RE = re.compile(r"\bAdmitted\s*\.")
ADMIT_TACTIC_RE = re.compile(r"\badmit\s*\.")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def strip_coq_comments(source: str) -> str:
    """Remove nested Coq comments while preserving non-comment text."""
    output: list[str] = []
    depth = 0
    index = 0
    while index < len(source):
        pair = source[index : index + 2]
        if pair == "(*":
            depth += 1
            index += 2
            continue
        if pair == "*)" and depth > 0:
            depth -= 1
            index += 2
            continue
        if depth == 0:
            output.append(source[index])
        index += 1
    return "".join(output)


def _declaration_symbols(source: str) -> tuple[list[str], list[str]]:
    axioms: list[str] = []
    parameters: list[str] = []
    for kind, names_blob in DECLARATION_RE.findall(source):
        names = IDENTIFIER_RE.findall(names_blob)
        if kind.startswith("Axiom"):
            axioms.extend(names)
        else:
            parameters.extend(names)
    return sorted(set(axioms)), sorted(set(parameters))


def inspect_coq_source(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    stripped = strip_coq_comments(source)
    theorem_names = THEOREM_RE.findall(stripped)
    axiom_symbols, parameter_symbols = _declaration_symbols(stripped)
    return {
        "source_sha256": _sha256_bytes(raw),
        "theorem_names": theorem_names,
        "theorem_count": len(theorem_names),
        "qed_count": len(QED_RE.findall(stripped)),
        "axiom_statement_count": len(AXIOM_STMT_RE.findall(stripped)),
        "parameter_statement_count": len(PARAMETER_STMT_RE.findall(stripped)),
        "axiom_symbols": axiom_symbols,
        "parameter_symbols": parameter_symbols,
        "axiom_symbol_count": len(axiom_symbols),
        "parameter_symbol_count": len(parameter_symbols),
        "admitted_count": len(ADMITTED_RE.findall(stripped))
        + len(ADMIT_TACTIC_RE.findall(stripped)),
    }


def _extract_assumption_symbols(lines: list[str]) -> list[str]:
    symbols: list[str] = []
    for line in lines:
        match = ASSUMPTION_SYMBOL_RE.match(line)
        if match:
            symbols.append(match.group(1))
    return sorted(set(symbols))


def parse_print_assumptions(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if any(line == "Closed under the global context" for line in lines):
        return {
            "parse_status": "CLOSED",
            "closed_under_global_context": True,
            "assumption_lines": [],
            "assumption_symbols": [],
            "raw_sha256": _sha256_bytes(output.encode("utf-8")),
        }

    header_index = next(
        (index for index, line in enumerate(lines) if line in {"Axioms:", "Assumptions:"}),
        None,
    )
    if header_index is not None:
        assumption_lines = lines[header_index + 1 :]
        return {
            "parse_status": "ASSUMPTIONS_PRESENT",
            "closed_under_global_context": False,
            "assumption_lines": assumption_lines,
            "assumption_symbols": _extract_assumption_symbols(assumption_lines),
            "raw_sha256": _sha256_bytes(output.encode("utf-8")),
        }

    return {
        "parse_status": "UNRECOGNIZED",
        "closed_under_global_context": False,
        "assumption_lines": [],
        "assumption_symbols": [],
        "raw_sha256": _sha256_bytes(output.encode("utf-8")),
    }


def _assumption_log_name(relative: Path, theorem: str) -> str:
    parts = list(relative.with_suffix("").parts)
    return "__".join(parts + [theorem]) + ".txt"


def _load_compile_status(path: Path) -> dict[str, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("compile status must be a JSON object")
    return value


def _load_baseline(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if value.get("baseline_kind") != "COQ_ASSUMPTION_BASELINE_V1":
        raise ValueError("unsupported Coq assumption baseline")
    return value, _sha256_bytes(raw)


def _assumption_snapshot(files: list[dict[str, Any]]) -> dict[str, Any]:
    declared: dict[str, list[str]] = {}
    theorem_assumptions: dict[str, list[str]] = {}
    admitted: dict[str, int] = {}

    for entry in files:
        declared_symbols = sorted(
            set(entry["axiom_symbols"]) | set(entry["parameter_symbols"])
        )
        if declared_symbols:
            declared[entry["path"]] = declared_symbols
        if entry["admitted_count"]:
            admitted[entry["path"]] = int(entry["admitted_count"])
        for theorem in entry["theorems"]:
            symbols = sorted(set(theorem.get("assumption_symbols", [])))
            if symbols:
                theorem_assumptions[
                    f"{entry['path']}::{theorem['theorem']}"
                ] = symbols

    return {
        "declared_assumptions": declared,
        "theorem_assumptions": theorem_assumptions,
        "admitted_sources": admitted,
    }


# --- Per-theorem axiom policy -------------------------------------------------
#
# compare_assumption_baseline() is a ratchet: it reports what changed. It cannot
# tell a legitimate crossing into R from an axiom introduced to skip a hard
# lemma -- both read as regression: true. The only way past the former is to
# bump the baseline, which silently accepts any of the latter that landed in the
# same commit.
#
# This is the policy layer. Permitted symbols are declared here with a reason;
# everything else is a violation regardless of what the baseline already knows.
#
# Why these two are permitted: Coq's standard Reals axiomatises R rather than
# constructing it, so stating any order predicate on R (0 <= radius), any
# continuity condition, or any compact-support carrier draws in exactly this
# pair. Q_scope theorems draw in neither, which is why the finite bridge reports
# "Closed under the global context" and an analytic theorem never can. That
# boundary is not a defect and must not read as one.
#
# Admitting a symbol here is a foundational decision. It is deliberately not
# configurable at the call site.

CLASSICAL_REAL_FOUNDATION = "CLASSICAL_REAL_ANALYSIS_FOUNDATION"

# A Parameter that abstracts over an implementation asserts nothing. Theorems
# proved against it hold for every instantiation, so it adds no trust surface.
# An Axiom that states a proposition does the opposite. Coq treats the two
# keywords identically, so the distinction is recorded here by symbol, not
# inferred -- which is the point: admitting one is a decision someone made and
# signed for, not a parser's guess.
ABSTRACTION_PARAMETER = "ABSTRACTION_OVER_IMPLEMENTATION"

AXIOM_POLICY: dict[str, dict[str, str]] = {
    "ClassicalDedekindReals.sig_forall_dec": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": (
            "Coq.Reals axiomatises R as classical Dedekind reals; any decidable "
            "order predicate on R draws this in. Standard foundation, used by "
            "mathcomp-analysis and the Coq stdlib."
        ),
    },
    "ClassicalDedekindReals.sig_not_dec": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": "Companion of sig_forall_dec from the same Coq.Reals construction.",
    },
    "FunctionalExtensionality.functional_extensionality_dep": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": (
            "Required to reason about R-valued functions extensionally, which "
            "every continuity or carrier statement needs."
        ),
    },
    "FunctionalExtensionality.functional_extensionality": {
        "category": CLASSICAL_REAL_FOUNDATION,
        "reason": "Non-dependent form of the same principle.",
    },
    "sha256": {
        "category": ABSTRACTION_PARAMETER,
        "reason": (
            "Core/Hash.v abstracts over the hash function rather than asserting "
            "anything about it. Every theorem there holds for any instantiation, "
            "so no property of SHA-256 is assumed."
        ),
    },
    "encode_JS": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the JS encoder; no property asserted.",
    },
    "encode_WASM": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the WASM encoder; no property asserted.",
    },
    "encode_PY": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the Python encoder; no property asserted.",
    },
    "step_JS": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the JS step relation; no property asserted.",
    },
    "step_WASM": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the WASM step relation; no property asserted.",
    },
    "step_PY": {
        "category": ABSTRACTION_PARAMETER,
        "reason": "Bisimulation/ThreeWay.v abstracts over the Python step relation; no property asserted.",
    },
}

# Deliberately NOT in AXIOM_POLICY, and named here so its absence is a decision
# on the record rather than an oversight:
#
#   Bisimulation/ThreeWay.v:5  Axiom cross_runtime_bisimulation
#
# It asserts that the three encoders agree on every state and event -- which is
# the three-way bisimulation claim itself, not a premise of it. That is the same
# shape the Python kernel already refuses under ASSUME_TARGET_CLAIM and
# ASSUME_GLOBAL_WEIL_POSITIVITY. The baseline ratchet never flagged it because it
# has been present since the baseline was taken; only a policy independent of the
# baseline can see it.
TARGET_CLAIM_AXIOM_NOTE = "Bisimulation/ThreeWay.v::cross_runtime_bisimulation"


def _policy_entry(symbol: str) -> dict[str, str] | None:
    return AXIOM_POLICY.get(symbol)


def evaluate_axiom_policy(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify every assumption reaching every theorem against AXIOM_POLICY.

    Fails closed on anything unlisted, on any Axiom/Parameter declared in a
    source file, and on any Admitted proof -- none of which the baseline ratchet
    rejects once it has seen them.
    """
    permitted: list[dict[str, str]] = []
    unpermitted: list[dict[str, str]] = []
    admitted_sources: list[str] = []

    for entry in sorted(files, key=lambda item: item["path"]):
        path = entry["path"]

        if int(entry.get("admitted_count", 0)):
            admitted_sources.append(path)

        # An Axiom in the source is not laundered by never being reached.
        for symbol in sorted(
            set(entry.get("axiom_symbols", [])) | set(entry.get("parameter_symbols", []))
        ):
            record = {"location": path, "symbol": symbol}
            policy = _policy_entry(symbol)
            if policy is None:
                unpermitted.append(record)
            else:
                permitted.append({**record, **policy})

        for theorem in entry.get("theorems", []):
            location = f"{path}::{theorem['theorem']}"
            for symbol in sorted(set(theorem.get("assumption_symbols", []))):
                record = {"location": location, "symbol": symbol}
                policy = _policy_entry(symbol)
                if policy is None:
                    unpermitted.append(record)
                else:
                    permitted.append({**record, **policy})

    return {
        "policy_kind": "COQ_AXIOM_POLICY_V1",
        "permitted_symbols": sorted(AXIOM_POLICY),
        "policy_violation": bool(unpermitted) or bool(admitted_sources),
        "unpermitted_assumptions": unpermitted,
        "permitted_assumptions": permitted,
        "admitted_sources": admitted_sources,
    }


def _set_diff(
    current: dict[str, list[str]], baseline: dict[str, list[str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    added: list[dict[str, str]] = []
    removed: list[dict[str, str]] = []
    for key in sorted(set(current) | set(baseline)):
        current_values = set(current.get(key, []))
        baseline_values = set(baseline.get(key, []))
        for value in sorted(current_values - baseline_values):
            added.append({"location": key, "symbol": value})
        for value in sorted(baseline_values - current_values):
            removed.append({"location": key, "symbol": value})
    return added, removed


def compare_assumption_baseline(
    files: list[dict[str, Any]], baseline: dict[str, Any], baseline_sha256: str
) -> dict[str, Any]:
    current = _assumption_snapshot(files)
    baseline_declared = baseline.get("declared_assumptions", {})
    baseline_theorem = baseline.get("theorem_assumptions", {})
    baseline_admitted = baseline.get("admitted_sources", {})

    new_declared, removed_declared = _set_diff(
        current["declared_assumptions"], baseline_declared
    )
    new_theorem, removed_theorem = _set_diff(
        current["theorem_assumptions"], baseline_theorem
    )

    new_admitted: list[dict[str, Any]] = []
    removed_admitted: list[dict[str, Any]] = []
    for path in sorted(set(current["admitted_sources"]) | set(baseline_admitted)):
        current_count = int(current["admitted_sources"].get(path, 0))
        baseline_count = int(baseline_admitted.get(path, 0))
        if current_count > baseline_count:
            new_admitted.append(
                {
                    "path": path,
                    "baseline_count": baseline_count,
                    "current_count": current_count,
                }
            )
        elif current_count < baseline_count:
            removed_admitted.append(
                {
                    "path": path,
                    "baseline_count": baseline_count,
                    "current_count": current_count,
                }
            )

    regression_count = len(new_declared) + len(new_theorem) + len(new_admitted)
    return {
        "baseline_kind": baseline["baseline_kind"],
        "baseline_source_commit": baseline.get("baseline_source_commit"),
        "baseline_sha256": baseline_sha256,
        "regression": regression_count > 0,
        "regression_count": regression_count,
        "new_declared_assumptions": new_declared,
        "removed_declared_assumptions": removed_declared,
        "new_theorem_assumptions": new_theorem,
        "removed_theorem_assumptions": removed_theorem,
        "new_admitted_sources": new_admitted,
        "removed_admitted_sources": removed_admitted,
    }


def build_receipt(
    *,
    formal_root: Path,
    compile_status_path: Path,
    assumptions_root: Path,
    source_commit: str,
    coq_version: str,
    baseline_path: Path | None = None,
) -> dict[str, Any]:
    compile_status = _load_compile_status(compile_status_path)
    files: list[dict[str, Any]] = []

    compile_failures = 0
    admitted_sources = 0
    axiom_free_theorems = 0
    assumption_bearing_theorems = 0
    unrecognized_assumption_outputs = 0
    source_axiom_statements = 0
    source_parameter_statements = 0
    source_axiom_symbols = 0
    source_parameter_symbols = 0

    for source_path in sorted(formal_root.rglob("*.v")):
        relative = source_path.relative_to(formal_root)
        relative_key = relative.as_posix()
        manifest = inspect_coq_source(source_path)
        status_entry = compile_status.get(
            relative_key, {"status": "MISSING", "log_sha256": None}
        )
        compile_state = status_entry.get("status", "MISSING")

        source_axiom_statements += int(manifest["axiom_statement_count"])
        source_parameter_statements += int(manifest["parameter_statement_count"])
        source_axiom_symbols += int(manifest["axiom_symbol_count"])
        source_parameter_symbols += int(manifest["parameter_symbol_count"])
        if manifest["admitted_count"]:
            admitted_sources += 1

        theorem_attestations: list[dict[str, Any]] = []
        if compile_state == "COMPILED":
            for theorem in manifest["theorem_names"]:
                log_path = assumptions_root / _assumption_log_name(relative, theorem)
                if log_path.exists():
                    parsed = parse_print_assumptions(
                        log_path.read_text(encoding="utf-8")
                    )
                else:
                    parsed = {
                        "parse_status": "MISSING",
                        "closed_under_global_context": False,
                        "assumption_lines": [],
                        "assumption_symbols": [],
                        "raw_sha256": None,
                    }
                theorem_attestations.append({"theorem": theorem, **parsed})
                if parsed["closed_under_global_context"]:
                    axiom_free_theorems += 1
                else:
                    assumption_bearing_theorems += 1
                    if parsed["parse_status"] in {"UNRECOGNIZED", "MISSING"}:
                        unrecognized_assumption_outputs += 1
        else:
            compile_failures += 1

        declaration_status = (
            "DECLARES_ASSUMPTIONS"
            if manifest["axiom_symbol_count"] or manifest["parameter_symbol_count"]
            else "NO_DECLARED_ASSUMPTIONS"
        )

        if compile_state != "COMPILED":
            attestation = "COMPILE_FAILED"
        elif manifest["admitted_count"]:
            attestation = "ADMITTED_SOURCE"
        elif any(
            not entry["closed_under_global_context"]
            for entry in theorem_attestations
        ):
            attestation = "ASSUMPTION_BEARING"
        elif theorem_attestations:
            attestation = "AXIOM_FREE"
        else:
            attestation = "COMPILED_NO_THEOREMS"

        files.append(
            {
                "path": relative_key,
                **manifest,
                "compile_status": compile_state,
                "compile_log_sha256": status_entry.get("log_sha256"),
                "declaration_status": declaration_status,
                "theorems": theorem_attestations,
                "attestation": attestation,
            }
        )

    summary = {
        "file_count": len(files),
        "compiled_files": len(files) - compile_failures,
        "compile_failures": compile_failures,
        "admitted_sources": admitted_sources,
        "source_axiom_statements": source_axiom_statements,
        "source_parameter_statements": source_parameter_statements,
        "source_axiom_symbols": source_axiom_symbols,
        "source_parameter_symbols": source_parameter_symbols,
        "axiom_free_theorems": axiom_free_theorems,
        "assumption_bearing_theorems": assumption_bearing_theorems,
        "unrecognized_assumption_outputs": unrecognized_assumption_outputs,
    }

    axiom_policy = evaluate_axiom_policy(files)
    summary["axiom_policy_violation"] = axiom_policy["policy_violation"]
    summary["unpermitted_assumption_count"] = len(
        axiom_policy["unpermitted_assumptions"]
    )
    summary["permitted_assumption_count"] = len(axiom_policy["permitted_assumptions"])

    baseline_diff = None
    if baseline_path is not None:
        baseline, baseline_sha256 = _load_baseline(baseline_path)
        baseline_diff = compare_assumption_baseline(files, baseline, baseline_sha256)
        summary["baseline_regression_count"] = baseline_diff["regression_count"]

    receipt_without_hash = {
        "schema_version": "1.1.0",
        "receipt_kind": RECEIPT_KIND,
        "source_commit": source_commit,
        "coq_version": coq_version,
        "lean_runtime_status": "NOT_PRESENT_IN_REPO",
        "authority": AUTHORITY,
        "correspondence": "NOT_ESTABLISHED",
        "files": files,
        "axiom_policy": axiom_policy,
        "summary": summary,
    }
    if baseline_diff is not None:
        receipt_without_hash["baseline_diff"] = baseline_diff

    return {
        **receipt_without_hash,
        "receipt_sha256": _canonical_sha256(receipt_without_hash),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--formal-root", required=True, type=Path)
    parser.add_argument("--compile-status", required=True, type=Path)
    parser.add_argument("--assumptions-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--coq-version", required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--enforce-axiom-policy",
        action="store_true",
        help=(
            "Exit non-zero when the receipt records an axiom policy violation. "
            "Off by default so the violation is visible before it is blocking: "
            "Bisimulation/ThreeWay.v currently carries a target-claim axiom that "
            "predates this check, and turning the gate on is a decision about "
            "that file, not about this script."
        ),
    )
    args = parser.parse_args()

    receipt = build_receipt(
        formal_root=args.formal_root,
        compile_status_path=args.compile_status,
        assumptions_root=args.assumptions_root,
        source_commit=args.source_commit,
        coq_version=args.coq_version,
        baseline_path=args.baseline,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    policy = receipt["axiom_policy"]
    if policy["policy_violation"]:
        for item in policy["unpermitted_assumptions"]:
            print(
                f"AXIOM POLICY: unpermitted {item['symbol']} at {item['location']}",
                file=sys.stderr,
            )
        for path in policy["admitted_sources"]:
            print(f"AXIOM POLICY: Admitted proof in {path}", file=sys.stderr)
        if args.enforce_axiom_policy:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
