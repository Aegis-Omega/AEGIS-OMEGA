#!/usr/bin/env python3
"""AEGIS Ω governance linter (AMPS-v1). Fails closed.

Two layers:
1. Text patterns over agent-authored Coq/Python surfaces.
2. Machine contract binding against the MPVC implementation.

Coq axiom policy is deliberately not re-implemented here; the Coq attestation
lane remains the authority for Print Assumptions and inventory policy.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COQ_PATTERNS = [
    (re.compile(r"\badmit\s*\."), "Coq admit tactic"),
    (re.compile(r"\bAdmitted\s*\."), "Coq Admitted"),
    (re.compile(r"\bTODO\b"), "unfinished marker (TODO)"),
]
PY_PATTERNS = [
    (re.compile(r"\bTODO\b"), "unfinished marker (TODO)"),
    (re.compile(r"\bassert\s+True\s*(==\s*True)?\s*$"), "tautological assertion"),
    (re.compile(r"\bassert\s+(\w+)\s*==\s*\1\s*$"), "tautological assertion"),
    (re.compile(r"pytest\.(skip|xfail)\(|@pytest\.mark\.(skip|skipif|xfail)"), "test skipped or expected to fail"),
]
TARGETS = {
    "coq": ["sovereign-omega-v2/formal/theories/**/*.v", "sovereign-omega-v2/formal/tests/**/*.v"],
    "py": [
        "clients/python/aegis_omega/**/*.py",
        "clients/python/tests/**/*.py",
        "sovereign-omega-v2/scripts/coq_*.py",
    ],
}


def strip_coq_comments(text: str) -> str:
    out, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith("(*", i):
            depth += 1
            i += 2
            continue
        if depth and text.startswith("*)", i):
            depth -= 1
            i += 2
            continue
        if depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out)


def lint_text() -> list[str]:
    errors: list[str] = []
    seen = 0
    for kind, globs in TARGETS.items():
        patterns = COQ_PATTERNS if kind == "coq" else PY_PATTERNS
        for glob in globs:
            for path in sorted(ROOT.glob(glob)):
                seen += 1
                text = path.read_text(encoding="utf-8", errors="replace")
                if kind == "coq":
                    text = strip_coq_comments(text)
                for lineno, line in enumerate(text.splitlines(), 1):
                    for pattern, reason in patterns:
                        if pattern.search(line):
                            errors.append(f"{path.relative_to(ROOT)}:{lineno}: {reason}")
    if seen == 0:
        errors.append("no lint targets found: TARGETS do not match this tree")
    return errors


def lint_contract() -> list[str]:
    errors: list[str] = []
    try:
        contract = json.loads((ROOT / ".agent-contract.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f".agent-contract.json unreadable or invalid: {exc}"]

    sys.path.insert(0, str(ROOT / "clients" / "python"))
    try:
        from aegis_omega import tourbillon as t
    except Exception as exc:
        return [f"contract binding: cannot import aegis_omega.tourbillon ({exc})"]

    want = list(contract["mandatory_gates"])
    have = [perspective.value for perspective in t.MANDATORY_GATES]
    if want != have:
        errors.append(f"mandatory_gates: contract {want} != code {have}")

    tiers = contract["authority_tiers"]
    for perspective, tier in contract["perspective_tiers"].items():
        authority = t.PERSPECTIVE_AUTHORITY[t.Perspective(perspective)]
        if tiers[tier]["admission_gate"] != authority.admission_bearing:
            errors.append(
                f"{perspective}: contract tier {tier} admission={tiers[tier]['admission_gate']} "
                f"!= code {authority.admission_bearing}"
            )

    capacity = 2 ** tiers["T1_DIAGNOSTIC"]["max_qubits_deterministic"]
    if t.DiagnosticOracleRegistry.CAPACITY != capacity:
        errors.append(
            f"T1_DIAGNOSTIC capacity: contract {capacity} != code "
            f"{t.DiagnosticOracleRegistry.CAPACITY}"
        )
    if t.PERSPECTIVE_AUTHORITY[t.Perspective.P_QUANTUM_GROVER].admission_bearing:
        errors.append("P_QUANTUM_GROVER is admission-bearing in code")

    try:
        t.PerspectiveReceipt(
            perspective=t.Perspective.P5_WEIL_DUALITY,
            outcome=t.PerspectiveOutcome.PASS,
        )
        errors.append("OPEN perspective accepted PASS")
    except ValueError:
        pass

    manifest = json.loads(
        (ROOT / contract["bindings"]["mpvc_manifest"]).read_text(encoding="utf-8")
    )
    for key in ("QuantumTourbillon", "QUANTUM_PHYSICAL_ADVANTAGE", "RH"):
        observed = manifest["canonical_status"].get(key)
        expected = contract["canonical_status"][key]
        if observed != expected:
            errors.append(
                f"canonical_status.{key}: manifest {observed!r} != contract {expected!r}"
            )
    if contract["canonical_status"]["UCR"]["machine_established"] is not False:
        errors.append("UCR is marked machine-established; no such attestation exists")
    return errors


def main() -> int:
    errors = lint_text() + lint_contract()
    if errors:
        print("FAIL: agent governance lint (AMPS-v1)", file=sys.stderr)
        for error in errors:
            print(f"  {error}", file=sys.stderr)
        return 1
    print("PASS: agent governance lint (AMPS-v1): text surfaces clean, contract bound to code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
