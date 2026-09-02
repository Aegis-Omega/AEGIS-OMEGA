"""Fail-closed contract for the QuantumTourbillon provenance-bound MPVC layer."""
import hashlib

import blake3
import pytest
import qiskit

from aegis_omega.tourbillon import (
    AuthorityLevel,
    ClaimState,
    DiagnosticOracleRegistry,
    MANDATORY_GATES,
    Perspective,
    PerspectiveOutcome,
    PerspectiveReceipt,
    QuantumPerspectiveCarousel,
    RECEIPT_VERSION,
    canonical_bytes,
    resolve_claim,
)

P = Perspective
O = PerspectiveOutcome
SOURCE_SHA = "99d3700c2d5a2aab73a756109dda80de439d1baa"
CLAIM_DIGEST = hashlib.sha256(b"AEGIS MPVC hardening claim").hexdigest()
DIAGNOSTIC_EXECUTION = hashlib.sha256(b"qiskit-statevector-local").hexdigest()


def execution_digest(perspective: Perspective) -> str:
    return hashlib.sha256(f"exec:{perspective.value}".encode()).hexdigest()


def receipt(
    p: Perspective,
    o: PerspectiveOutcome,
    *,
    source_sha: str = SOURCE_SHA,
    claim_digest: str = CLAIM_DIGEST,
    execution: str | None = None,
    **evidence,
) -> PerspectiveReceipt:
    return PerspectiveReceipt(
        perspective=p,
        outcome=o,
        source_sha=source_sha,
        claim_digest=claim_digest,
        execution_digest=execution or execution_digest(p),
        evidence=evidence,
    )


def resolve(receipts):
    return resolve_claim(
        receipts,
        expected_source_sha=SOURCE_SHA,
        expected_claim_digest=CLAIM_DIGEST,
    )


def all_pass():
    return [
        receipt(P.P1_COQ_KERNEL, O.PASS, allowlist="closed"),
        receipt(P.P2_EXACT_HEAD, O.PASS, sha=SOURCE_SHA),
        receipt(P.P3_DEPENDENCY_GRAPH, O.PASS, files=29),
        receipt(P.P4_ARITHMETIC_BOUND, O.PASS, bound="finite"),
    ]


def test_quantum_and_open_layers_have_zero_admission_authority():
    q = receipt(P.P_QUANTUM_GROVER, O.PASS, located_index=0)
    assert q.authority is AuthorityLevel.T1_DIAGNOSTIC
    assert resolve([q]).state is ClaimState.UNKNOWN
    assert resolve([*all_pass(), q]).state is ClaimState.ADMITTED

    bad = all_pass()
    bad[0] = receipt(P.P1_COQ_KERNEL, O.FAIL, reason="Axioms: present")
    assert resolve([*bad, q]).state is ClaimState.QUARANTINED

    with pytest.raises(ValueError):
        receipt(P.P5_WEIL_DUALITY, O.PASS)
    p5 = receipt(P.P5_WEIL_DUALITY, O.UNAVAILABLE)
    result = resolve([*all_pass(), p5, q])
    assert result.state is ClaimState.ADMITTED
    assert set(result.ignored) == {P.P5_WEIL_DUALITY.value, P.P_QUANTUM_GROVER.value}


def test_receipt_digest_binds_version_provenance_execution_and_evidence():
    a = receipt(P.P2_EXACT_HEAD, O.PASS, sha=SOURCE_SHA, n=1)
    b = receipt(P.P2_EXACT_HEAD, O.PASS, n=1, sha=SOURCE_SHA)
    assert a.digest() == b.digest()
    assert len(a.digest()) == 64

    expected = blake3.blake3(canonical_bytes({
        "version": RECEIPT_VERSION,
        "source_sha": SOURCE_SHA,
        "claim_digest": CLAIM_DIGEST,
        "execution_digest": execution_digest(P.P2_EXACT_HEAD),
        "perspective": "P2_EXACT_HEAD",
        "authority": "ADMISSION_GATE",
        "outcome": "PASS",
        "evidence": {"n": 1, "sha": SOURCE_SHA},
    })).hexdigest()
    assert a.digest() == expected

    changed_execution = receipt(
        P.P2_EXACT_HEAD,
        O.PASS,
        execution=hashlib.sha256(b"other execution").hexdigest(),
        sha=SOURCE_SHA,
        n=1,
    )
    assert changed_execution.digest() != a.digest()


def test_evidence_is_snapshot_immutable_and_strict_json():
    evidence = {"nested": [1, 2], "ok": True}
    r = PerspectiveReceipt(
        perspective=P.P1_COQ_KERNEL,
        outcome=O.PASS,
        source_sha=SOURCE_SHA,
        claim_digest=CLAIM_DIGEST,
        execution_digest=execution_digest(P.P1_COQ_KERNEL),
        evidence=evidence,
    )
    before = r.digest()
    evidence["nested"].append(3)
    evidence["new"] = "mutation"
    assert r.digest() == before
    assert tuple(r.evidence["nested"]) == (1, 2)
    with pytest.raises(TypeError):
        r.evidence["new"] = "forbidden"
    with pytest.raises(ValueError):
        receipt(P.P1_COQ_KERNEL, O.PASS, non_finite=float("nan"))


def test_exact_head_and_claim_digest_mismatch_quarantine():
    rs = all_pass()
    rs[1] = receipt(P.P2_EXACT_HEAD, O.PASS, source_sha="a" * 40)
    result = resolve(rs)
    assert result.state is ClaimState.QUARANTINED
    assert "SOURCE_SHA_MISMATCH:P2_EXACT_HEAD" in result.violations

    rs = all_pass()
    rs[3] = receipt(P.P4_ARITHMETIC_BOUND, O.PASS, claim_digest="b" * 64)
    result = resolve(rs)
    assert result.state is ClaimState.QUARANTINED
    assert "CLAIM_DIGEST_MISMATCH:P4_ARITHMETIC_BOUND" in result.violations


def test_duplicate_and_authority_tamper_quarantine_not_last_write_wins():
    duplicate = resolve([*all_pass(), receipt(P.P1_COQ_KERNEL, O.PASS)])
    assert duplicate.state is ClaimState.QUARANTINED
    assert "DUPLICATE_PERSPECTIVE:P1_COQ_KERNEL" in duplicate.violations

    rs = all_pass()
    object.__setattr__(rs[2], "authority", AuthorityLevel.T1_DIAGNOSTIC)
    tampered = resolve(rs)
    assert tampered.state is ClaimState.QUARANTINED
    assert "AUTHORITY_MISMATCH:P3_DEPENDENCY_GRAPH" in tampered.violations


def test_missing_unknown_unavailable_fail_and_p4_are_fail_closed():
    assert resolve(all_pass()[:3]).state is ClaimState.UNKNOWN

    rs = all_pass()
    rs[2] = receipt(P.P3_DEPENDENCY_GRAPH, O.UNAVAILABLE)
    assert resolve(rs).state is ClaimState.UNKNOWN

    rs = all_pass()
    rs[3] = receipt(P.P4_ARITHMETIC_BOUND, O.UNKNOWN)
    assert resolve(rs).state is ClaimState.UNKNOWN

    rs = all_pass()
    rs[1] = receipt(P.P2_EXACT_HEAD, O.UNAVAILABLE)
    rs[3] = receipt(P.P4_ARITHMETIC_BOUND, O.FAIL)
    assert resolve(rs).state is ClaimState.QUARANTINED

    assert resolve(all_pass()).state is ClaimState.ADMITTED
    assert MANDATORY_GATES[-1] is P.P4_ARITHMETIC_BOUND


def test_grover_localizes_fault_but_cannot_change_classical_resolution():
    assert qiskit.__version__ == "2.5.2"
    for marked in range(4):
        diag = QuantumPerspectiveCarousel.amplify(marked)
        assert diag.located_index == marked
        assert diag.probability > 0.9999
        assert abs(sum(diag.probabilities) - 1.0) < 1e-9

    rs = all_pass()
    rs[2] = receipt(P.P3_DEPENDENCY_GRAPH, O.FAIL, cycle="A->B->A")
    carousel = QuantumPerspectiveCarousel(
        rs,
        source_sha=SOURCE_SHA,
        claim_digest=CLAIM_DIGEST,
        diagnostic_execution_digest=DIAGNOSTIC_EXECUTION,
    )
    diag = carousel.locate_fault()
    assert diag.marked_index == 2 and diag.located_index == 2
    q = diag.as_receipt(
        source_sha=SOURCE_SHA,
        claim_digest=CLAIM_DIGEST,
        execution_digest=DIAGNOSTIC_EXECUTION,
    )
    assert q.authority is AuthorityLevel.T1_DIAGNOSTIC
    assert q.evidence["admission_authority"] == "NONE"
    assert carousel.resolve().state is ClaimState.QUARANTINED

    clean = QuantumPerspectiveCarousel(
        all_pass(),
        source_sha=SOURCE_SHA,
        claim_digest=CLAIM_DIGEST,
        diagnostic_execution_digest=DIAGNOSTIC_EXECUTION,
    )
    assert clean.locate_fault().marked_index is None
    assert clean.resolve().state is ClaimState.ADMITTED


def test_diagnostic_registry_marks_first_failure_only_as_diagnostic():
    reg = DiagnosticOracleRegistry()
    reg.register("kernel_closed", lambda: True)
    reg.register("head_exact", lambda: 1 / 0)
    reg.register("dag_acyclic", lambda: False)
    diag = reg.locate_fault()
    assert diag.marked_index == 1 and diag.located_index == 1
    assert diag.marked_name == "head_exact"
    q = diag.as_receipt(
        source_sha=SOURCE_SHA,
        claim_digest=CLAIM_DIGEST,
        execution_digest=DIAGNOSTIC_EXECUTION,
    )
    assert q.authority is AuthorityLevel.T1_DIAGNOSTIC
    assert resolve([q]).state is ClaimState.UNKNOWN
    assert resolve([*all_pass(), q]).state is ClaimState.ADMITTED

    full = DiagnosticOracleRegistry()
    for name in "abcd":
        full.register(name, lambda: True)
    with pytest.raises(ValueError):
        full.register("e", lambda: True)
    with pytest.raises(ValueError):
        reg.register("kernel_closed", lambda: True)


def test_invalid_binding_formats_are_rejected_at_construction_boundary():
    with pytest.raises(ValueError):
        receipt(P.P1_COQ_KERNEL, O.PASS, source_sha="99d3700c")
    with pytest.raises(ValueError):
        receipt(P.P1_COQ_KERNEL, O.PASS, claim_digest="cd")
    with pytest.raises(ValueError):
        PerspectiveReceipt(
            perspective=P.P1_COQ_KERNEL,
            outcome=O.PASS,
            source_sha=SOURCE_SHA,
            claim_digest=CLAIM_DIGEST,
            execution_digest="ed1",
        )
    with pytest.raises(ValueError):
        PerspectiveReceipt(
            perspective=P.P1_COQ_KERNEL,
            outcome=O.PASS,
            source_sha=SOURCE_SHA,
            claim_digest=CLAIM_DIGEST,
            execution_digest=execution_digest(P.P1_COQ_KERNEL),
            version="0.0.0",
        )
