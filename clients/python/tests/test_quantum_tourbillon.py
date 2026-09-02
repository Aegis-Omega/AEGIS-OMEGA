"""RED-first contract for the QuantumTourbillon (MPVC) layer.

Five explicit failure modes:
  1. a quantum diagnostic PASS can never yield ADMITTED (zero admission authority)
  2. receipt hashing is deterministic BLAKE3 over canonical JSON
  3. UNAVAILABLE on a mandatory gate blocks any implicit PASS -> UNKNOWN
  4. real Qiskit 2.5.2 Grover amplification concentrates on the marked failing
     perspective with p > 0.99, on a local statevector, for every marked index
  5. the diagnostic oracle registry marks the first failing named invariant and
     the located fault carries no admission authority

Runs offline.  No cloud backend, no wall-clock time.
"""
import json

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
    canonical_bytes,
    resolve_claim,
)

P = Perspective
O = PerspectiveOutcome


def receipt(p, o, **evidence):
    return PerspectiveReceipt(perspective=p, outcome=o, evidence=evidence)


def all_pass():
    return [
        receipt(P.P1_COQ_KERNEL, O.PASS, allowlist="closed"),
        receipt(P.P2_EXACT_HEAD, O.PASS, sha="7167722108bd"),
        receipt(P.P3_DEPENDENCY_GRAPH, O.PASS, files=29),
        receipt(P.P4_ARITHMETIC_BOUND, O.PASS, bound="finite"),
    ]


# 1 ---------------------------------------------------------------------------

def test_unauthorized_quantum_admission():
    # the quantum perspective is pinned to T1_DIAGNOSTIC and cannot be re-authorised
    q = receipt(P.P_QUANTUM_GROVER, O.PASS, located_index=0)
    assert q.authority is AuthorityLevel.T1_DIAGNOSTIC
    assert not q.authority.admission_bearing

    # quantum PASS with no admission gates at all -> UNKNOWN, never ADMITTED
    res = resolve_claim([q])
    assert res.state is ClaimState.UNKNOWN
    assert res.consulted == ()
    assert res.ignored == (P.P_QUANTUM_GROVER.value,)

    # quantum PASS cannot overrule a failing mandatory gate
    bad = all_pass()
    bad[0] = receipt(P.P1_COQ_KERNEL, O.FAIL, reason="Axioms: present")
    assert resolve_claim([*bad, q]).state is ClaimState.QUARANTINED

    # P5 is OPEN: it may never report PASS, and it never votes
    with pytest.raises(ValueError):
        receipt(P.P5_WEIL_DUALITY, O.PASS)
    p5 = receipt(P.P5_WEIL_DUALITY, O.UNAVAILABLE)
    res = resolve_claim([*all_pass(), p5, q])
    assert res.state is ClaimState.ADMITTED
    assert set(res.ignored) == {P.P5_WEIL_DUALITY.value, P.P_QUANTUM_GROVER.value}


# 2 ---------------------------------------------------------------------------

def test_deterministic_blake3_receipt_hashing():
    a = receipt(P.P2_EXACT_HEAD, O.PASS, sha="7167722108bd", n=1)
    b = receipt(P.P2_EXACT_HEAD, O.PASS, n=1, sha="7167722108bd")  # key order differs
    assert a.digest() == b.digest()
    assert len(a.digest()) == 64

    # the digest is exactly BLAKE3 over canonical JSON, recomputed independently
    expected = blake3.blake3(
        json.dumps(
            {
                "authority": "ADMISSION_GATE",
                "evidence": {"n": 1, "sha": "7167722108bd"},
                "outcome": "PASS",
                "perspective": "P2_EXACT_HEAD",
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    assert a.digest() == expected
    assert canonical_bytes({"b": 1, "a": [1, 2]}) == b'{"a":[1,2],"b":1}'

    # one changed field changes the digest; the chain digest is order-sensitive
    c = receipt(P.P2_EXACT_HEAD, O.PASS, sha="7167722108bd", n=2)
    assert c.digest() != a.digest()
    r1 = resolve_claim(all_pass())
    r2 = resolve_claim(all_pass())
    assert r1.chain_digest == r2.chain_digest
    assert resolve_claim(list(reversed(all_pass()))).chain_digest != r1.chain_digest

    # non-canonical evidence is refused rather than hashed ambiguously
    with pytest.raises(ValueError):
        receipt(P.P1_COQ_KERNEL, O.PASS, obj=object())


# 3 ---------------------------------------------------------------------------

def test_unavailable_blocks_implicit_pass():
    rs = all_pass()
    rs[2] = receipt(P.P3_DEPENDENCY_GRAPH, O.UNAVAILABLE)
    assert resolve_claim(rs).state is ClaimState.UNKNOWN

    rs = all_pass()
    rs[3] = receipt(P.P4_ARITHMETIC_BOUND, O.UNKNOWN)
    assert resolve_claim(rs).state is ClaimState.UNKNOWN

    # a mandatory gate that is simply absent is not an implicit PASS either
    assert resolve_claim(all_pass()[:3]).state is ClaimState.UNKNOWN

    # FAIL dominates UNAVAILABLE
    rs = all_pass()
    rs[1] = receipt(P.P2_EXACT_HEAD, O.UNAVAILABLE)
    rs[3] = receipt(P.P4_ARITHMETIC_BOUND, O.FAIL)
    assert resolve_claim(rs).state is ClaimState.QUARANTINED

    # only the fully passing gate set admits
    assert resolve_claim(all_pass()).state is ClaimState.ADMITTED

    # duplicates are refused, not silently overwritten
    with pytest.raises(ValueError):
        resolve_claim([*all_pass(), receipt(P.P1_COQ_KERNEL, O.PASS)])


# 4 ---------------------------------------------------------------------------

def test_grover_amplification_locates_marked_failing_perspective():
    assert qiskit.__version__ == "2.5.2"

    for marked in range(4):
        diag = QuantumPerspectiveCarousel.amplify(marked)
        assert diag.located_index == marked
        assert diag.probability > 0.9999
        assert abs(sum(diag.probabilities) - 1.0) < 1e-9
        assert diag.circuit_qasm_depth > 0

    # end to end: P3 (index 2) is the failing gate; the carousel marks and finds it
    rs = all_pass()
    rs[2] = receipt(P.P3_DEPENDENCY_GRAPH, O.FAIL, cycle="A->B->A")
    carousel = QuantumPerspectiveCarousel(rs)
    assert carousel.failing_index() == 2
    diag = carousel.locate_fault()
    assert diag.marked_index == 2 and diag.located_index == 2
    q = diag.as_receipt()
    assert q.outcome is O.PASS and q.authority is AuthorityLevel.T1_DIAGNOSTIC
    assert q.evidence["physical_advantage"] == "NOT_ESTABLISHED"

    # the diagnostic PASS is recorded in the chain yet the claim stays QUARANTINED
    res = carousel.resolve()
    assert res.state is ClaimState.QUARANTINED
    assert P.P_QUANTUM_GROVER.value in res.ignored
    assert q.digest() in res.receipt_digests

    # nothing failing -> nothing to mark -> diagnostic UNKNOWN, no circuit run
    clean = QuantumPerspectiveCarousel(all_pass()).locate_fault()
    assert clean.marked_index is None and clean.located_index is None
    assert clean.as_receipt().outcome is O.UNKNOWN


# 5 ---------------------------------------------------------------------------

def test_diagnostic_oracle_registry_marks_first_failing_invariant():
    reg = DiagnosticOracleRegistry()
    reg.register("kernel_closed", lambda: True)
    reg.register("head_exact", lambda: 1 / 0)          # raises -> counts as failing
    reg.register("dag_acyclic", lambda: False)
    assert reg.names == ("kernel_closed", "head_exact", "dag_acyclic")
    assert reg.first_failing_index() == 1

    diag = reg.locate_fault()
    assert diag.marked_index == 1 and diag.located_index == 1
    assert diag.marked_name == "head_exact"
    assert diag.probability > 0.99
    q = diag.as_receipt()
    assert q.authority is AuthorityLevel.T1_DIAGNOSTIC
    assert q.evidence["marked_name"] == "head_exact"

    # a located fault still has no admission authority
    assert resolve_claim([*all_pass(), q]).state is ClaimState.ADMITTED
    assert resolve_claim([q]).state is ClaimState.UNKNOWN

    # all invariants hold -> nothing marked
    clean = DiagnosticOracleRegistry()
    clean.register("a", lambda: True)
    assert clean.locate_fault().marked_index is None

    # the exact 2-qubit locator addresses at most four invariants; duplicates refused
    full = DiagnosticOracleRegistry()
    for name in "abcd":
        full.register(name, lambda: True)
    with pytest.raises(ValueError):
        full.register("e", lambda: True)
    with pytest.raises(ValueError):
        reg.register("kernel_closed", lambda: True)


# 6 ---------------------------------------------------------------------------

def test_p4_bounded_falsification_is_a_mandatory_gate():
    # P4 absent -> UNKNOWN, never an implicit PASS
    p1_p3 = all_pass()[:3]
    assert resolve_claim(p1_p3).state is ClaimState.UNKNOWN
    # P4 FAIL -> QUARANTINED even with P1..P3 PASS
    assert resolve_claim([*p1_p3, receipt(P.P4_ARITHMETIC_BOUND, O.FAIL, bound="violated")]).state is ClaimState.QUARANTINED
    # P4 PASS completes the mandatory set
    assert resolve_claim([*p1_p3, receipt(P.P4_ARITHMETIC_BOUND, O.PASS)]).state is ClaimState.ADMITTED
    # the quantum perspective can never occupy a mandatory slot: authority is
    # derived from the perspective, so the escalation is unrepresentable
    q = receipt(P.P_QUANTUM_GROVER, O.PASS)
    assert q.authority is AuthorityLevel.T1_DIAGNOSTIC and q.perspective not in MANDATORY_GATES
