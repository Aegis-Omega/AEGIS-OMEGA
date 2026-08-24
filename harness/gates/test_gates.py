"""Regression suite: every structural failure of 2026-08-24, replayed.

Each test asserts the gate blocks BEFORE the expensive stage, at the cost
recorded in the docstring. The night's measured C_waste for each is in the
comment; the point of the gate is to drive it to zero.
"""
import os
import sys
from contextlib import contextmanager

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from harness.gates import (  # noqa: E402
    PASS, FAIL, ERROR, InvariantViolation, IncompleteRegistry,
    SpectralBasis, admit, digest, gateset,
)
from harness.gates.status import (  # noqa: E402
    Claim, Evidence, IllegalPromotion, ResearchStatus,
)


class _Caught:
    """Stand-in for pytest.ExceptionInfo so the file runs without pytest.

    The CI python job installs flask and numpy, not pytest, and discovers
    nothing -- it runs named scripts. A gate suite that only executes under a
    runner CI does not have is a gate that never fires.
    """

    def __init__(self):
        self.value = None


@contextmanager
def raises(exc):
    caught = _Caught()
    try:
        yield caught
    except exc as e:
        caught.value = e
        return
    raise AssertionError(f"expected {exc.__name__}, nothing was raised")

DODEC_LCF = [10, 7, 4, -4, -7, 10, -4, 7, -7, 4] * 2


def dodecahedron():
    A = np.zeros((20, 20))
    for i in range(20):
        A[i, (i + 1) % 20] = A[(i + 1) % 20, i] = 1
    for i, s in enumerate(DODEC_LCF):
        j = (i + s) % 20
        A[i, j] = A[j, i] = 1
    return A


def run(sig, kind, *args):
    return [g.run(sig, digest(*[str(a) for a in args]), {}, *args)
            for g in gateset(sig, kind)]


# --- REGRESSION 1 -----------------------------------------------------------
# C_waste that night: v3, v4, v5 -- 241 lines, a 7-config c-sweep of 520x520
# generalized eigenproblems, three full experiment cycles. Gate cost: 0.003 ms.
def test_basis_that_cannot_reach_the_first_zero_is_refused() -> None:
    with raises(InvariantViolation) as e:
        SpectralBasis(N_F=12, h=3.5).against(14.134725)
    assert "10.7" in str(e.value) and "14.13" in str(e.value)


def test_basis_that_reaches_is_admitted() -> None:
    b = SpectralBasis(N_F=720, h=3.5).against(541.8474)
    assert all(r.result == PASS for r in b._receipts)


def test_unknown_convention_refuses_rather_than_guessing() -> None:
    """pi/h is convention-specific. Guessing it would manufacture a false law."""
    with raises(IncompleteRegistry):
        SpectralBasis(N_F=720, h=3.5, convention="chebyshev").cutoff


# --- REGRESSION 2 -----------------------------------------------------------
# C_waste: 0 -- caught before running. Kept so it stays caught.
def test_commutator_of_adjacency_with_its_own_laplacian_is_refused() -> None:
    A = dodecahedron()
    L = 3 * np.eye(20) - A
    rs = run("NonCommutingPair", "binary", A, L)
    with raises(InvariantViolation):
        admit(rs)
    assert rs[0].result == FAIL and "0.0" in rs[0].witness


def test_a_genuinely_noncommuting_pair_is_admitted() -> None:
    A = dodecahedron()
    rng = np.random.default_rng(7)
    W = A * (1.0 + 0.5 * rng.standard_normal((20, 20)))
    W = (W + W.T) / 2
    admit(run("NonCommutingPair", "binary", W, 3 * np.eye(20) - A))


# --- REGRESSION 3 -----------------------------------------------------------
# C_waste: 1 script + 1 run (v2). Symptom was lambda_0 identical at kappa=0.1
# and kappa=5 -- a full eigensolve to learn what ||S-A|| says in 0.052 ms.
def test_uniform_edge_sum_is_refused_as_a_decomposition() -> None:
    A = dodecahedron()
    S = np.zeros((20, 20))
    for i in range(20):
        for j in range(i + 1, 20):
            if A[i, j]:
                S[i, j] = S[j, i] = 1
    rs = run("EdgeDecomposition", "unary", (S, A))
    with raises(InvariantViolation):
        admit(rs)


# --- REGRESSION 4 -----------------------------------------------------------
def test_laplacian_coupling_that_annihilates_the_uniform_lift_is_refused() -> None:
    L = 3 * np.eye(20) - dodecahedron()
    rs = run("GraphLaplacian", "unary", L)
    with raises(InvariantViolation):
        admit(rs)


# --- REGRESSION 5 -----------------------------------------------------------
# The elementary one. Any chain needing <x,[Q_C,Q_D]x> >= K > 0 dies here.
def test_positive_lower_bound_on_an_antisymmetric_quadratic_form_is_refused() -> None:
    rng = np.random.default_rng(3)
    X = rng.standard_normal((40, 40))
    rs = run("AntisymmetricOperator", "unary", (X - X.T) / 2)
    with raises(InvariantViolation) as e:
        admit(rs)
    assert "identically" in str(e.value)


# --- REGRESSION 6 -----------------------------------------------------------
# w subset span{u}: nulling the common channel nulls the differential one.
def test_signal_inside_the_nuisance_span_is_refused() -> None:
    rng = np.random.default_rng(11)
    u = rng.standard_normal((3, 30))
    w = [0.4 * u[0] + 0.6 * u[1], 0.9 * u[2] - 0.2 * u[0]]   # entirely inside
    rs = run("SeparableChannels", "binary", w, u)
    with raises(InvariantViolation):
        admit(rs)
    rs2 = run("SeparableChannels", "binary", [rng.standard_normal(30)], u)
    admit(rs2)


# --- THE VACUOUS-PASS HOLE --------------------------------------------------
def test_a_type_with_no_registered_gates_refuses_instead_of_passing() -> None:
    """forall g in {} : g == PASS is true. An empty gate set must not admit."""
    with raises(IncompleteRegistry):
        gateset("SomeAdmissibleTypeNobodyWroteGatesFor")


def test_empty_receipt_list_blocks() -> None:
    with raises(InvariantViolation):
        admit([])


# --- FAIL-CLOSED ------------------------------------------------------------
def test_an_erroring_gate_blocks_exactly_like_a_failing_one() -> None:
    rs = run("GraphLaplacian", "unary", "not a matrix at all")
    assert rs[0].result == ERROR
    with raises(InvariantViolation):
        admit(rs)


# --- RECEIPT IDENTITY -------------------------------------------------------
def test_receipt_does_not_survive_a_change_of_the_object_it_certifies() -> None:
    a = SpectralBasis(N_F=720, h=3.5).against(541.8474)
    b = SpectralBasis(N_F=719, h=3.5).against(541.8474)
    assert a._receipts[0].object_digest != b._receipts[0].object_digest


# --- RESEARCH STATUS: the VERIFIED-without-computation failure --------------
def test_computed_without_a_named_run_is_refused() -> None:
    """The 2026-08-24 defect: three matrix rows read VERIFIED with nothing behind
    them. 2-jet lift on all 15 blockers was never executed at all."""
    c = Claim("2jet-lift", "Delta Phi_D(s) > 0 on all 15 blocker ordinates")
    c.transition(ResearchStatus.TYPE_CHECKED, Evidence(argument="shapes agree"))
    with raises(IllegalPromotion) as e:
        c.transition(ResearchStatus.COMPUTED, Evidence(argument="verified"))
    assert "receipt_digest" in str(e.value) and "recollection" in str(e.value)
    assert c.status is ResearchStatus.TYPE_CHECKED


def test_theorem_cannot_rest_on_a_tolerance() -> None:
    """dim(PV)=2 was called a THEOREM. It held at tol=1e-10 across 300 zeros --
    which makes it COMPUTED. s_min(A_-) then dipped to 6.64e-05."""
    c = Claim("dimPV", "dim(PV) = 2 => eta == 0")
    c.transition(ResearchStatus.TYPE_CHECKED, Evidence(argument="rank gates pass"))
    c.transition(ResearchStatus.COMPUTED,
                 Evidence(receipt_digest=digest("pv", 300), N=300, tol=1e-10))
    with raises(IllegalPromotion) as e:
        c.transition(ResearchStatus.THEOREM,
                     Evidence(tol=1e-10, argument="holds for all 300"))
    assert "moves with a threshold" in str(e.value)


def test_the_real_downgrade_is_legal_and_leaves_a_record() -> None:
    c = Claim("dimPV", "dim(PV) = 2 => eta == 0")
    c.transition(ResearchStatus.TYPE_CHECKED, Evidence(argument="rank gates pass"))
    c.transition(ResearchStatus.COMPUTED,
                 Evidence(receipt_digest=digest("pv", 60), N=60, tol=1e-10))
    c.transition(ResearchStatus.THEOREM,
                 Evidence(argument="g_C,g_D in V => dim(V cap G)=2"))
    c.demote(ResearchStatus.COMPUTED,
             Evidence(receipt_digest=digest("pv", 300), N=300, tol=1e-10),
             reason="s_min(A_-) = 6.64e-05 at gamma_204; independence unproved")
    assert c.status is ResearchStatus.COMPUTED
    assert c.history[-1]["note"].startswith("DEMOTED:")
    assert "6.64e-05" in c.history[-1]["note"]


def test_conjecture_cannot_jump_straight_to_theorem() -> None:
    c = Claim("rh", "all nontrivial zeros have Re(s) = 1/2")
    with raises(IllegalPromotion) as e:
        c.transition(ResearchStatus.THEOREM, Evidence(argument="QED"))
    assert "skips" in str(e.value)
    assert c.status is ResearchStatus.CONJECTURED


def test_a_genuine_theorem_is_admitted() -> None:
    c = Claim("antisym", "A^T = -A => x^T A x = 0 for real x")
    c.transition(ResearchStatus.TYPE_CHECKED, Evidence(argument="AntisymmetricOperator"))
    c.transition(ResearchStatus.COMPUTED,
                 Evidence(receipt_digest=digest("as", 64), N=64, tol=1e-12))
    c.transition(ResearchStatus.THEOREM,
                 Evidence(argument="x^T A x = (x^T A x)^T = -x^T A x"))
    assert c.status is ResearchStatus.THEOREM
    assert c.evidence.tol is None


if __name__ == "__main__":
    tests = sorted(
        (n, f) for n, f in list(globals().items())
        if n.startswith("test_") and callable(f)
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    print("=" * 40)
    print(f"PASS: {passed}  FAIL: {failed}")
    if failed:
        print("RESULT: FAIL")
        sys.exit(1)
    print("RESULT: PASS -- every 2026-08-24 structural failure is gated")
