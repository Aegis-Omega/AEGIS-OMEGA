#!/usr/bin/env python3
"""Artifact-bound QuantumDNA ClaimsLedger projection; no authority admission.

Hash encoding is versioned deterministic JSON with no float values. It is not
a claim of RFC 8785 conformance. Historical source files retain their raw bytes.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AUDIT_SHA = "074dd2c4afdafb1991a0917ca3b02e881002e72e92d648681839f7abc887fdf8"
RECEIPT_SHA = "a04849923bfd9876b9a5aa7aeedd367af81b2ea1ff21d04b4fbd402ebc2f047d"
SOURCE_COMMIT = "b0a840015f92f39ddae65beb7393bf2c91aa816e"
GENESIS = "0" * 64
SCHEMA = "AEGIS_QDNA_CLAIMS_CHAIN_V1"


class GateError(ValueError):
    pass


def canonical(value):
    def check(v):
        if v is None or type(v) in (str, int, bool):
            return
        if type(v) is list:
            for item in v:
                check(item)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for item in v.values():
                check(item)
            return
        raise GateError("Unsupported value in hash payload; floats are forbidden")
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise GateError("Duplicate JSON key: " + key)
            obj[key] = value
        return obj
    def bad_constant(value):
        raise GateError("Non-finite JSON constant: " + value)
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=bad_constant)
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(str(exc)) from exc


def load_evidence(directory=HERE / "evidence"):
    directory = Path(directory)
    for name, expected in [("source_audit.json", AUDIT_SHA), ("source_receipt.json", RECEIPT_SHA)]:
        if file_sha(directory / name) != expected:
            raise GateError("Pinned source mismatch: " + name)
    audit = read_json(directory / "source_audit.json")
    receipt = read_json(directory / "source_receipt.json")
    if audit["source_receipt_sha256"] != RECEIPT_SHA or audit["source_code_commit"] != SOURCE_COMMIT or receipt["code_git_commit"] != SOURCE_COMMIT:
        raise GateError("Audit/receipt/source commit splice")
    if audit["authority_promotion"] is not False or receipt["all_numerical_gates_pass"] is not True:
        raise GateError("Invalid evidence status")
    expected = {"source_audit.json": AUDIT_SHA, "source_receipt.json": RECEIPT_SHA,
                "source_audit_generator.py": audit["audit_generator_sha256"],
                "experiment_spec.json": receipt["spec_sha256"],
                "Hawke2010_ELM.json": receipt["input_sha256"]["Hawke2010_ELM.json"]}
    for name in ["sweep_metrics.json", "GTG_gamma_0.1.csv", "GTG_gamma_0.5.csv", "reference_1BNA.csv", "reference_Hawke2010.csv"]:
        expected[name] = receipt["output_sha256"][name]
    for name, value in expected.items():
        if file_sha(directory / name) != value:
            raise GateError("Source artifact changed: " + name)
    for gamma in ("0.1", "0.5"):
        with (directory / f"GTG_gamma_{gamma}.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        at25 = [r for r in rows if Decimal(r["time_fs"]) == Decimal(25)]
        observed = next(x for x in audit["GTG_coherence_observations"] if str(x["gamma_eV"]) == gamma)
        if len(at25) != 1 or abs(Decimal(at25[0]["coherence_l1"]) - Decimal(str(observed["C_l1_at_25_fs"]))) > Decimal("1e-12"):
            raise GateError("Coherence observation does not match archived trajectory")
    return audit, receipt, expected


def expected_claims(verified_against, evidence_dir=HERE / "evidence"):
    if not isinstance(verified_against, str) or not re.fullmatch(r"[0-9a-f]{40}", verified_against):
        raise GateError("An exact repository implementation commit is required")
    audit, _, _ = load_evidence(evidence_dir)
    code = "Code: genomics/quantum_dna/claims_gate.py"
    tests = "Test: genomics/quantum_dna/test_claims_gate.py"
    claims = []
    for identifier, proposition in [
        (451, "The QuantumDNA witness ledger binds source bytes, complete claim semantics and ordered previous-entry hashes; verified integrity alone grants no runtime or biological authority."),
        (452, "In the archived six-site one-hole GTG simulation, site-basis C_l1 at 25 fs is 0.21646991105146732 for gamma=0.1 eV and 0.1438771953946045 for gamma=0.5 eV; neither condition meets all preregistered classical-approximation criteria."),
        (453, "The archived 37-state ELM reference runs record sampled ground-population 1-1/e crossings at 541.0821643286573 fs (shipped 1BNA parameters) and 775.5511022044088 fs (Hawke2010); these are distinct parameter replays, not an original-publication trajectory match."),
    ]:
        claims.append({"id": f"CLM-{identifier}", "claim": proposition, "tier": "Verified", "eq": "EQ-A", "dependencies": [],
            "evidence": [code, tests], "fails_if": "A source byte, model scope, claim wording, status, limitation, ordering or parent hash changes without the gate rejecting it; or an unsupported authority promotion passes.",
            "verified_against": verified_against})
    for index, decision in enumerate(audit["claim_decisions"]):
        claims.append({"id": f"CLM-{454+index}", "claim": decision["claim"], "tier": "Removed", "eq": "EQ-D", "dependencies": [],
            "evidence": [code, tests], "removal_reason": decision["correction"] + " This is a bounded witness audit; the second mathematical document was not provided."})
    claims.append({"id": "CLM-463", "claim": "Every traceless Hermitian commutator observable -i[A,B], including the zero operator, has eigenvalues of both signs.",
        "tier": "Removed", "eq": "EQ-D", "dependencies": [], "evidence": [code, tests],
        "removal_reason": "Both signs follow only when the finite-dimensional traceless Hermitian operator is nonzero. The zero commutator has only zero eigenvalues. Neither case supports uniform strict positivity over all states."})
    for identifier, proposition, boundary in [
        (464, "Single-parameter Hamiltonian ablations can distinguish coupling and detuning contributions to the GTG/GCG difference.", "The next-run contract checks allowed matrix changes; no causal ablation has been executed by this integration."),
        (465, "The simulated sequence/dephasing differences have a verified biological consequence in cells.", "Hypothesis only; no cellular measurement, calibrated bath, mutation-rate or trapping experiment is supplied."),
        (466, "The complete second mathematical document can be audited for its commutator, Fourier-decay and zero-exclusion arguments.", "Blocked pending the source document and definitions; only the quoted formulas have been examined."),
    ]:
        claims.append({"id": f"CLM-{identifier}", "claim": proposition, "tier": "Proposed", "eq": "EQ-D", "dependencies": [],
            "evidence": [code], "fails_if": boundary})
    return claims


def build_ledger(verified_against, evidence_dir=HERE / "evidence"):
    _, _, sources = load_evidence(evidence_dir)
    header = {"schema_version": SCHEMA, "kind": "FALSIFICATION_RECORD_WITNESS_AUDIT", "source_run_commit": SOURCE_COMMIT,
        "verified_against": verified_against, "source_sha256": sources,
        "serialization": "SORTED_UTF8_JSON_NO_FLOAT_V1", "authority_promotion": False,
        "control_plane_admission": "NOT_PERFORMED", "mathematical_document": "NOT_PROVIDED_NOT_AUDITED",
        "evidence_scope": "archived artifact subset verified; complete numerical rerun and all 86 original artifacts are not performed by this gate"}
    context = digest(header)
    previous = GENESIS
    entries = []
    for index, claim in enumerate(expected_claims(verified_against, evidence_dir)):
        entry = {"sequence": index, "context_sha256": context, "previous_entry_sha256": previous,
            "claim": claim, "model_scope": "REFERENCE_2P_ELM_GROUND_37D_AND_SEPARATE_SWEEP_ONE_HOLE_ELM_6D",
            "authority": "NONE", "limitations": ["NUMERICAL_MODEL_ONLY", "NO_CLINICAL_ADMISSION", "NO_ORIGINAL_TRAJECTORY_MATCH", "NO_SECOND_DOCUMENT_AUDIT"]}
        entry["entry_sha256"] = digest(entry)
        previous = entry["entry_sha256"]
        entries.append(entry)
    return {"header": header, "entries": entries, "terminal_sha256": previous}


def validate_ledger(ledger, central_claims, evidence_dir=HERE / "evidence"):
    try:
        expected = build_ledger(ledger["header"]["verified_against"], evidence_dir)
    except (KeyError, TypeError) as exc:
        raise GateError("Malformed witness ledger") from exc
    # Reconstruct semantics from pinned evidence and policy, not just supplied hashes.
    if canonical(ledger) != canonical(expected):
        raise GateError("Witness chain, semantic payload or authority boundary mismatch")
    wanted = {e["claim"]["id"]: e["claim"] for e in expected["entries"]}
    selected = [c for c in central_claims if c.get("id") in wanted]
    if len(selected) != len(wanted) or {c["id"]: c for c in selected} != wanted:
        raise GateError("Central ClaimsLedger projection differs from witness ledger")
    return expected["terminal_sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", metavar="EXACT_IMPLEMENTATION_COMMIT")
    args = parser.parse_args()
    path = ROOT / "docs/quantum-dna-witness-ledger.json"
    if args.generate:
        path.write_text(json.dumps(build_ledger(args.generate), indent=2, ensure_ascii=False) + "\n")
        print("Generated witness ledger; central projection must be updated separately")
        return
    ledger = read_json(path)
    claims = read_json(ROOT / "docs/claims.json")["claims"]
    terminal = validate_ledger(ledger, claims)
    commit = ledger["header"]["verified_against"]
    # The implementation pin must resolve inside this repository and cover the actual gate.
    try:
        kind = subprocess.check_output(["git", "cat-file", "-t", commit], cwd=ROOT, stderr=subprocess.DEVNULL).strip()
        if kind != b"commit":
            raise GateError("Implementation pin is not a commit")
        subprocess.check_call(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as exc:
        raise GateError("Implementation commit is unavailable or not an ancestor of HEAD") from exc
    for relative in ["genomics/quantum_dna/claims_gate.py", "genomics/quantum_dna/test_claims_gate.py", "genomics/quantum_dna/run_contract.py", "genomics/quantum_dna/test_run_contract.py"]:
        try:
            bound = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as exc:
            raise GateError("Implementation commit is unavailable or omits gate source") from exc
        if hashlib.sha256(bound).hexdigest() != file_sha(ROOT / relative):
            raise GateError("Implementation source differs from its pinned commit: " + relative)
    print(json.dumps({"status": "PASS", "claims": len(ledger["entries"]), "terminal_sha256": terminal,
        "scope": "REPOSITORY_WITNESS_REGISTRATION_ONLY", "authority_promotion": False}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (GateError, OSError, KeyError, TypeError) as exc:
        raise SystemExit("QuantumDNA gate DENY: " + str(exc))
