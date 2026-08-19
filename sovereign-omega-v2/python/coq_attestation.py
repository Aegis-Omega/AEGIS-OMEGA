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


def inspect_coq_source(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    source = raw.decode("utf-8")
    stripped = strip_coq_comments(source)
    theorem_names = THEOREM_RE.findall(stripped)
    return {
        "source_sha256": _sha256_bytes(raw),
        "theorem_names": theorem_names,
        "theorem_count": len(theorem_names),
        "qed_count": len(QED_RE.findall(stripped)),
        "axiom_statement_count": len(AXIOM_STMT_RE.findall(stripped)),
        "parameter_statement_count": len(PARAMETER_STMT_RE.findall(stripped)),
        "admitted_count": len(ADMITTED_RE.findall(stripped))
        + len(ADMIT_TACTIC_RE.findall(stripped)),
    }


def parse_print_assumptions(output: str) -> dict[str, Any]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if any(line == "Closed under the global context" for line in lines):
        return {
            "parse_status": "CLOSED",
            "closed_under_global_context": True,
            "assumption_lines": [],
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
            "raw_sha256": _sha256_bytes(output.encode("utf-8")),
        }

    return {
        "parse_status": "UNRECOGNIZED",
        "closed_under_global_context": False,
        "assumption_lines": [],
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


def build_receipt(
    *,
    formal_root: Path,
    compile_status_path: Path,
    assumptions_root: Path,
    source_commit: str,
    coq_version: str,
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

    for source_path in sorted(formal_root.rglob("*.v")):
        relative = source_path.relative_to(formal_root)
        relative_key = relative.as_posix()
        manifest = inspect_coq_source(source_path)
        status_entry = compile_status.get(relative_key, {"status": "MISSING", "log_sha256": None})
        compile_state = status_entry.get("status", "MISSING")

        source_axiom_statements += int(manifest["axiom_statement_count"])
        source_parameter_statements += int(manifest["parameter_statement_count"])
        if manifest["admitted_count"]:
            admitted_sources += 1

        theorem_attestations: list[dict[str, Any]] = []
        if compile_state == "COMPILED":
            for theorem in manifest["theorem_names"]:
                log_path = assumptions_root / _assumption_log_name(relative, theorem)
                if log_path.exists():
                    parsed = parse_print_assumptions(log_path.read_text(encoding="utf-8"))
                else:
                    parsed = {
                        "parse_status": "MISSING",
                        "closed_under_global_context": False,
                        "assumption_lines": [],
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

        if compile_state != "COMPILED":
            attestation = "COMPILE_FAILED"
        elif manifest["admitted_count"]:
            attestation = "ADMITTED_SOURCE"
        elif manifest["axiom_statement_count"] or manifest["parameter_statement_count"]:
            attestation = "ASSUMPTION_BEARING"
        elif any(not entry["closed_under_global_context"] for entry in theorem_attestations):
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
        "axiom_free_theorems": axiom_free_theorems,
        "assumption_bearing_theorems": assumption_bearing_theorems,
        "unrecognized_assumption_outputs": unrecognized_assumption_outputs,
    }

    receipt_without_hash = {
        "schema_version": "1.0.0",
        "receipt_kind": RECEIPT_KIND,
        "source_commit": source_commit,
        "coq_version": coq_version,
        "lean_runtime_status": "NOT_PRESENT_IN_REPO",
        "authority": AUTHORITY,
        "files": files,
        "summary": summary,
    }
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
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    receipt = build_receipt(
        formal_root=args.formal_root,
        compile_status_path=args.compile_status,
        assumptions_root=args.assumptions_root,
        source_commit=args.source_commit,
        coq_version=args.coq_version,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
