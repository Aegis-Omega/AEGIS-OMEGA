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


def test_preflight_does_not_claim_narrow_diagonal_from_lower_rayleigh_alone():
    r = compute_preflight()
    assert r.narrow_diagonal == F(32, 25)
    assert r.narrow_minus_rayleigh_lower == F(4583, 40000)
