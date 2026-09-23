from fractions import Fraction as F

from research.rh.signed_four_block_preflight_v1 import compute_preflight


def test_signed_four_block_old_diagonal_budget_is_rigorously_insufficient():
    r = compute_preflight()
    assert r.adjacent_lower == F(4751, 10000)
    assert r.next_lower == F(673, 2000)
    assert r.far_lower == F(4651, 20000)
    assert r.all_ones_rayleigh_lower == F(46617, 40000)
    assert r.old_certificate_gap == F(5417, 40000)
    assert r.old_certificate_sufficient is False


def test_comparison_matrix_exact_ldlt_inertia_transition():
    r = compute_preflight()
    assert r.old_comparison_ldlt_pivots == (
        -F(103, 100),
        -F(2002, 2575),
        -F(236161, 800800),
        F(14004033, 4723220),
    )
    assert r.old_comparison_inertia == (1, 3, 0)

    assert r.narrow_comparison_ldlt_pivots == (
        -F(32, 25),
        -F(13783, 12800),
        -F(269534, 344575),
        -F(82023, 1134880),
    )
    assert r.narrow_comparison_inertia == (0, 4, 0)


def test_lower_rayleigh_receipt_is_not_actual_matrix_identity():
    r = compute_preflight()
    assert r.narrow_diagonal == F(32, 25)
    assert r.narrow_minus_rayleigh_lower == F(4583, 40000)
