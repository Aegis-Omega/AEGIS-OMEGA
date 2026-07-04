#!/usr/bin/env python3
"""
AEGIS-Ω — session certifier (the substrate certifies itself)
============================================================
One command that runs every proof in this substrate and folds the results into
the SAME hash chain, emitting a single reproducible SESSION CERTIFICATE. The
proof that the proofs ran is itself a tamper-evident, replayable artifact —
the system eating its own dogfood.

Each proof contributes an INTEGER exit code and, where it has one, a
deterministic evidence hash. Both are bound into a LineageChain stage. There is
no wall-clock, no RNG, no ordering nondeterminism (the proof list is fixed), so
the session certificate is itself deterministic: run it twice, get the same hash.
`--twice` asserts exactly that.

Exit 0 iff every proof passed AND the chain certifies.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
GENOMICS = os.path.join(ROOT, "genomics")

sys.path.insert(0, HERE)
sys.path.insert(0, GENOMICS)
from chain import LineageChain, canon, sha256_hex  # noqa: E402
from replay_pipeline import run_pipeline, SAMPLE_REFERENCE, SAMPLE_READS  # noqa: E402
from compliance_pipeline import run_decision, SAMPLE_APPLICANT  # noqa: E402

# Deterministic evidence anchors — the terminal hashes the two pipelines must
# produce. Bound into the certificate so a drift in either pipeline is visible
# in the session hash, not just in a green/red exit code.
GENOMICS_ANCHOR = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS).terminal_hash()
COMPLIANCE_ANCHOR = run_decision(SAMPLE_APPLICANT).terminal_hash()

# (label, cwd, argv). Each is an independent proof harness with a boolean verdict.
PROOFS = [
    ("genomics.determinism", GENOMICS, ["python3", "test_replay_proof.py"]),
    ("genomics.governed_interpretation", GENOMICS, ["python3", "interpret_demo.py"]),
    ("verifiable.generality", HERE, ["python3", "test_generality.py"]),
    ("verifiable.cross_runtime", os.path.join(HERE, "cross_language"),
        ["bash", "verify.sh"]),
]


def run_proof(cwd: str, argv: list) -> int:
    """Run one proof harness; return its exit code (integer verdict)."""
    r = subprocess.run(argv, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r.returncode


def build_certificate() -> tuple[LineageChain, bool]:
    chain = LineageChain()
    all_ok = True
    # Bind the deterministic pipeline anchors first — the evidence the harnesses assert on.
    chain.append("ANCHORS", {
        "genomics_terminal": GENOMICS_ANCHOR,
        "compliance_terminal": COMPLIANCE_ANCHOR,
    })
    for label, cwd, argv in PROOFS:
        code = run_proof(cwd, argv)
        ok = code == 0
        all_ok = all_ok and ok
        chain.append(label, {"exit_code": code, "passed": ok})
    return chain, all_ok


def main() -> int:
    twice = "--twice" in sys.argv
    chain, all_ok = build_certificate()
    cert = chain.certify()

    print("AEGIS-Ω — Session Certificate")
    print("=" * 60)
    for rec in chain.records:
        out = rec.output
        if rec.stage == "ANCHORS":
            print(f"  anchors  genomics={out['genomics_terminal'][:16]}… "
                  f"compliance={out['compliance_terminal'][:16]}…")
        else:
            mark = "PASS" if out["passed"] else f"FAIL(exit {out['exit_code']})"
            print(f"  {mark:16s} {rec.stage}")
    print("=" * 60)
    print(f"chain certifies : {cert['is_valid']}")
    print(f"session cert    : {chain.terminal_hash()}")

    if twice:
        chain2, _ = build_certificate()
        same = chain2.terminal_hash() == chain.terminal_hash()
        print(f"reproducible    : {same}  (second run -> {chain2.terminal_hash()[:16]}…)")
        all_ok = all_ok and same

    all_ok = all_ok and cert["is_valid"]
    print("=" * 60)
    print("RESULT:", "all proofs passed; certificate reproducible and self-consistent."
          if all_ok else "one or more proofs failed — see above.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
