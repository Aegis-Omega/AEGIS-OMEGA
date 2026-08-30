from fractions import Fraction

from research.rh.finite_to_global_counterexample import (
    build_refutation_receipt,
    limit_witness_q,
    tail_norm_sq,
    truncation_q,
)


def test_density_alone_shortcut_has_exact_counterexample():
    for n in (1, 2, 4, 8, 16):
        assert truncation_q(n) > 0
        assert tail_norm_sq(n) == Fraction(1, 3 * (4 ** n))

    assert limit_witness_q() == Fraction(-1, 1)
    assert tail_norm_sq(16) < Fraction(1, 10**9)

    receipt = build_refutation_receipt()
    assert receipt["classification"] == "REFUTED_SHORTCUT"
    assert receipt["refutes"] == "DENSITY_ALONE_FINITE_STAGE_POSITIVITY_IMPLIES_CLOSURE_POSITIVITY"
    assert receipt["does_not_refute"] == [
        "CONTINUOUS_Q_EXTENDS_POSITIVITY_FROM_DENSE_SUBSPACE",
        "LOWER_SEMICONTINUOUS_CLOSED_FORM_EXTENDS_POSITIVITY_UNDER_ITS_HYPOTHESES",
    ]
    assert receipt["global_weil_positivity_proven"] is False
    assert receipt["rh_proven"] is False
