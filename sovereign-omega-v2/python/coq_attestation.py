#!/usr/bin/env python3
"""AEGIS Coq formal-attestation receipt generator.

This module does not prove mathematics. It records source structure, compiler
outcomes, and `Print Assumptions` evidence so downstream gates can distinguish
compiled/axiom-free theorems from assumption-bearing or failed artifacts.

Classical trust probes are retained as evidence, but they are explicitly
DIAGNOSTIC_ONLY: their imported assumptions are never allowed to become
production authority or baseline-regression inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


RECEIPT_KIND = "COQ_FORMAL_ATTESTATION_RECEIPT_V1"
AUTHORITY = "FORMAL_MATH_EVIDENCE_ONLY"
AUTHORITY_ELIGIBLE = "AUTHORITY_ELIGIBLE"
DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"

# These files intentionally probe the trust surface of classical Coq modules.
# They are compiled and Print-Assumptions evidence is preserved, but they are
# not proof-authority inputs and cannot create/clear production assumption debt.
DIAGNOSTIC_ONLY_PATHS = frozenset(
    {
        "Weil/O0TrustProbeReals.v",
        "Weil/O0TrustProbeFunction.v",
        "Weil/O0TrustProbeCompact.v",
        "Weil/O0TrustProbeContinuity.v",
    }
)

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


def _is_diagnostic_entry(entry: dict[str, Any]) -> bool:
    scope = entry.get("evidence_scope")
    if scope is not None:
        return scope == DIAGNOSTIC_ONLY
    return entry.get("path") in DIAGNOSTIC_ONLY_PATHS


def _assumption_snapshot(files: list[dict[str, Any]]) -> dict[str, Any]:
    declared: dict[str, list[str]] = {}
    theorem_assumptions: dict[str, list[str]] = {}
    admitted: dict[str, int] = {}

    for entry in files:
        # Diagnostic trust probes are observations about imported trust surface,
        # not authority-bearing proof sources. They stay in the receipt but do
        # not participate in the production baseline comparison.
        if _is_diagnostic_entry(entry):
            continue

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
    authority_axiom_free_theorems = 0
    authority_assumption_bearing_theorems = 0
    authority_unrecognized_assumption_outputs = 0
    diagnostic_axiom_free_theorems = 0
    diagnostic_assumption_bearing_theorems = 0
    diagnostic_unrecognized_assumption_outputs = 0
    source_axiom_statements = 0
    source_parameter_statements = 0
    source_axiom_symbols = 0
    source_parameter_symbols = 0

    for source_path in sorted(formal_root.rglob("*.v")):
        relative = source_path.relative_to(formal_root)
        relative_key = relative.as_posix()
        evidence_scope = (
            DIAGNOSTIC_ONLY
            if relative_key in DIAGNOSTIC_ONLY_PATHS
            else AUTHORITY_ELIGIBLE
        )
        manifest = inspect_coq_source(source_path)
        status_entry = compile_status.get(
            relative_key, {"status": "MISSING", "log_sha256": None}
        )
        compile_state = status_entry.get("status", "MISSING")

        source_axiom_statements += int(manifest["axiom_statement_count"])
        source_parameter_statements += int(manifest["parameter_statement_count"])
        source_axiom_symbols += int(manifest["axiom_symbol_count"])
        source_parameter_symbols += int(manifest["parameter_symbol_count"])
        if manifest["admitted_count"] and evidence_scope == AUTHORITY_ELIGIBLE:
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

                is_closed = bool(parsed["closed_under_global_context"])
                is_unrecognized = parsed["parse_status"] in {"UNRECOGNIZED", "MISSING"}
                if is_closed:
                    axiom_free_theorems += 1
                else:
                    assumption_bearing_theorems += 1
                    if is_unrecognized:
                        unrecognized_assumption_outputs += 1

                if evidence_scope == DIAGNOSTIC_ONLY:
                    if is_closed:
                        diagnostic_axiom_free_theorems += 1
                    else:
                        diagnostic_assumption_bearing_theorems += 1
                        if is_unrecognized:
                            diagnostic_unrecognized_assumption_outputs += 1
                else:
                    if is_closed:
                        authority_axiom_free_theorems += 1
                    else:
                        authority_assumption_bearing_theorems += 1
                        if is_unrecognized:
                            authority_unrecognized_assumption_outputs += 1
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
                "evidence_scope": evidence_scope,
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
        "authority_eligible_files": sum(
            entry["evidence_scope"] == AUTHORITY_ELIGIBLE for entry in files
        ),
        "diagnostic_only_files": sum(
            entry["evidence_scope"] == DIAGNOSTIC_ONLY for entry in files
        ),
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
        "authority_axiom_free_theorems": authority_axiom_free_theorems,
        "authority_assumption_bearing_theorems": authority_assumption_bearing_theorems,
        "authority_unrecognized_assumption_outputs": authority_unrecognized_assumption_outputs,
        "diagnostic_axiom_free_theorems": diagnostic_axiom_free_theorems,
        "diagnostic_assumption_bearing_theorems": diagnostic_assumption_bearing_theorems,
        "diagnostic_unrecognized_assumption_outputs": diagnostic_unrecognized_assumption_outputs,
    }

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
        "diagnostic_only_paths": sorted(DIAGNOSTIC_ONLY_PATHS),
        "files": files,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
