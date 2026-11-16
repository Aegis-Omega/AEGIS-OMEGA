import hashlib

from aegis.adapters import (REJECTED, UNKNOWN, VERIFIED, can_promote, check_test_run,
                            data_snapshot, lean_axioms)

HEAD = "a" * 40
OTHER = "b" * 40
V = {"name": "lean", "version": "4.12.0"}
ENV = {"os": "linux"}
BIND = dict(verifier=V, environment=ENV, source_head=HEAD)

STD = "'Foo.bar' depends on axioms: [propext, Classical.choice, Quot.sound]"


# --- proof ---

def test_unconditional_proof_with_standard_axioms_verifies():
    r = lean_axioms(STD, theorem="Foo.bar", claim="unconditional", **BIND)
    assert r["status"] == VERIFIED and can_promote(r, expected_head=HEAD)
    assert "intended target" in r["scope"]


def test_no_axioms_line_verifies():
    out = "'Foo.bar' does not depend on any axioms"
    assert lean_axioms(out, theorem="Foo.bar", claim="unconditional", **BIND)["status"] == VERIFIED


def test_sorry_is_rejected_for_either_claim():
    out = "'Foo.bar' depends on axioms: [propext, sorryAx]"
    for claim in ("unconditional", "conditional"):
        r = lean_axioms(out, theorem="Foo.bar", claim=claim, declared_assumptions=["sorryAx"], **BIND)
        assert r["status"] == REJECTED and not can_promote(r, expected_head=HEAD)


def test_custom_axiom_blocks_unconditional_but_declared_conditional_is_labelled():
    out = "'Foo.bar' depends on axioms: [propext, RH_hypothesis]"
    assert lean_axioms(out, theorem="Foo.bar", claim="unconditional", **BIND)["status"] == REJECTED
    assert lean_axioms(out, theorem="Foo.bar", claim="conditional", **BIND)["status"] == REJECTED
    r = lean_axioms(out, theorem="Foo.bar", claim="conditional",
                    declared_assumptions=["RH_hypothesis"], **BIND)
    assert r["status"] == VERIFIED and r["details"]["claim"] == "conditional"


def test_report_for_another_theorem_or_garbage_is_unknown():
    assert lean_axioms(STD, theorem="Other", claim="unconditional", **BIND)["status"] == UNKNOWN
    assert lean_axioms("error: unknown constant", theorem="Foo.bar", claim="unconditional",
                       **BIND)["status"] == UNKNOWN
    assert lean_axioms(STD, theorem="Foo.bar", claim="proved", **BIND)["status"] == UNKNOWN


# --- tests ---

GOOD = {"command": "pytest -q", "collected": 5, "passed": 4, "failed": 0, "errors": 0, "skipped": 1}


def test_clean_run_verifies_and_failures_reject():
    assert check_test_run(GOOD, **BIND)["status"] == VERIFIED
    assert check_test_run({**GOOD, "failed": 1, "passed": 3}, **BIND)["status"] == REJECTED
    assert check_test_run({**GOOD, "errors": 1}, **BIND)["status"] == REJECTED


def test_empty_inconsistent_or_malformed_runs_are_unknown():
    assert check_test_run({**GOOD, "collected": 0, "passed": 0, "skipped": 0}, **BIND)["status"] == UNKNOWN
    assert check_test_run({**GOOD, "passed": 2}, **BIND)["status"] == UNKNOWN
    assert check_test_run({**GOOD, "passed": True}, **BIND)["status"] == UNKNOWN
    assert check_test_run({"passed": 3}, **BIND)["status"] == UNKNOWN


# --- data ---

CSV = b"id,name\n1,a\n2,b\n"
CONTRACT = {"sha256": hashlib.sha256(CSV).hexdigest(), "columns": ["id", "name"], "rows": 2}


def test_matching_snapshot_verifies():
    assert data_snapshot(CSV, CONTRACT, **BIND)["status"] == VERIFIED


def test_changed_bytes_header_or_rows_reject():
    assert data_snapshot(CSV + b"3,c\n", CONTRACT, **BIND)["status"] == REJECTED
    other = b"id,label\n1,a\n2,b\n"
    c = {**CONTRACT, "sha256": hashlib.sha256(other).hexdigest()}
    r = data_snapshot(other, c, **BIND)
    assert r["status"] == REJECTED and "header_mismatch" in r["reasons"]
    c = {**CONTRACT, "rows": 3}
    assert "row_count_mismatch" in data_snapshot(CSV, c, **BIND)["reasons"]


def test_unreadable_snapshot_or_contract_is_unknown():
    assert data_snapshot(b"\xff\xfe", CONTRACT, **BIND)["status"] == UNKNOWN
    assert data_snapshot(CSV, {"rows": 2}, **BIND)["status"] == UNKNOWN


# --- binding and promotion ---

def test_unbound_evidence_cannot_verify():
    for kw in ({"verifier": None}, {"verifier": {"name": "lean"}}, {"source_head": None},
               {"source_head": "abc"}, {"environment": {}}):
        r = lean_axioms(STD, theorem="Foo.bar", claim="unconditional", **{**BIND, **kw})
        assert r["status"] == UNKNOWN and not can_promote(r, expected_head=HEAD)


def test_stale_head_and_tampered_receipt_are_not_promotable():
    r = lean_axioms(STD, theorem="Foo.bar", claim="unconditional", **BIND)
    assert can_promote(r, expected_head=HEAD)
    assert not can_promote(r, expected_head=OTHER)
    assert not can_promote({**r, "status": VERIFIED, "source_head": OTHER}, expected_head=OTHER)
    assert not can_promote({**r, "scope": "anything"}, expected_head=HEAD)
    assert not can_promote({k: v for k, v in r.items() if k != "receipt_digest"}, expected_head=HEAD)
    assert not can_promote({}, expected_head=HEAD)
    assert not can_promote(r, expected_head="short")


def test_pinned_digest_mismatch_rejects():
    r = lean_axioms(STD, theorem="Foo.bar", claim="unconditional", expected_digest="0" * 64, **BIND)
    assert r["status"] == REJECTED and "artifact_digest_mismatch" in r["reasons"]
    ok = hashlib.sha256(STD.encode()).hexdigest()
    assert lean_axioms(STD, theorem="Foo.bar", claim="unconditional", expected_digest=ok,
                       **BIND)["status"] == VERIFIED


def test_receipt_digest_is_deterministic():
    a = lean_axioms(STD, theorem="Foo.bar", claim="unconditional", **BIND)
    b = lean_axioms(STD, theorem="Foo.bar", claim="unconditional", **BIND)
    assert a == b
