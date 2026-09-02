#!/usr/bin/env python3
"""AEGIS Ω governance linter (AMPS-v1). Fails closed.

Two layers:

1. Text patterns over the agent-authored surfaces (Coq theories, the MPVC
   package and its tests, the governance scripts): admit/Admitted, TODO,
   tautological assertions, skipped/xfail tests.

   Coq axiom policy is deliberately NOT re-implemented here. Section
   `Hypothesis` inside a REQUIRE_AXIOM_FREE file is legitimate (discharged
   on section close) and the attestation lane already decides axiom-freedom
   from `Print Assumptions` against formal/coq-inventory-policy.json. A second,
   cruder authority would only contradict the first.

2. Contract binding: `.agent-contract.json` is loaded and checked against the
   code it describes, so the contract is load-bearing rather than prose:
   mandatory gates, non-admission tiers, the deterministic qubit cap, and the
   canonical status recorded in the MPVC manifest.
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
    # this file defines the forbidden tokens and so necessarily contains them;
    # it is not a lint target.
}


def strip_coq_comments(text: str) -> str:
    out, depth, i = [], 0, 0
    while i < len(text):
        if text.startswith("(*", i):
            depth += 1; i += 2; continue
        if depth and text.startswith("*)", i):
            depth -= 1; i += 2; continue
        if depth == 0:
            out.append(text[i])
        i += 1
    return "".join(out)


def lint_text() -> list[str]:
    errors: list[str] = []
    seen = 0
    for kind, globs in TARGETS.items():
        patterns = COQ_PATTERNS if kind == "coq" else PY_PATTERNS
        for g in globs:
            for path in sorted(ROOT.glob(g)):
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
    except Exception as exc:  # the contract binds to this module; absence is a violation
        return [f"contract binding: cannot import aegis_omega.tourbillon ({exc})"]

    want = list(contract["mandatory_gates"])
    have = [p.value for p in t.MANDATORY_GATES]
    if want != have:
        errors.append(f"mandatory_gates: contract {want} != code {have}")

    tiers = contract["authority_tiers"]
    for perspective, tier in contract["perspective_tiers"].items():
        authority = t.PERSPECTIVE_AUTHORITY[t.Perspective(perspective)]
        if tiers[tier]["admission_gate"] != authority.admission_bearing:
            errors.append(f"{perspective}: contract tier {tier} admission={tiers[tier]['admission_gate']} != code {authority.admission_bearing}")

    cap = 2 ** tiers["T1_DIAGNOSTIC"]["max_qubits_deterministic"]
    if t.DiagnosticOracleRegistry.CAPACITY != cap:
        errors.append(f"T1_DIAGNOSTIC capacity: contract {cap} != code {t.DiagnosticOracleRegistry.CAPACITY}")
    if t.PERSPECTIVE_AUTHORITY[t.Perspective.P_QUANTUM_GROVER].admission_bearing:
        errors.append("P_QUANTUM_GROVER is admission-bearing in code")

    try:
        t.PerspectiveReceipt(perspective=t.Perspective.P5_WEIL_DUALITY, outcome=t.PerspectiveOutcome.PASS)
        errors.append("OPEN perspective accepted PASS")
    except ValueError:
        pass

    manifest = json.loads((ROOT / contract["bindings"]["mpvc_manifest"]).read_text(encoding="utf-8"))
    for key in ("QuantumTourbillon", "QUANTUM_PHYSICAL_ADVANTAGE", "RH"):
        if manifest["canonical_status"].get(key) != contract["canonical_status"][key]:
            errors.append(f"canonical_status.{key}: manifest {manifest['canonical_status'].get(key)!r} != contract {contract['canonical_status'][key]!r}")
    if contract["canonical_status"]["UCR"]["machine_established"] is not False:
        errors.append("UCR is marked machine-established; no such attestation exists")
    return errors


def main() -> int:
    errors = lint_text() + lint_contract()
    if errors:
        print("FAIL: agent governance lint (AMPS-v1)", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    print("PASS: agent governance lint (AMPS-v1): text surfaces clean, contract bound to code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
