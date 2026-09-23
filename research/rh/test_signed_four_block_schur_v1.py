from fractions import Fraction as F

from research.rh.signed_four_block_schur_v1 import compute_certificate


def test_signed_four_block_schur_gate_passes_exactly():
    c = compute_certificate()
    assert c.shifted_diagonal == F(158, 125)
    assert c.block_diag_far_lower == F(251, 250)
    assert c.block_diag_adj_lower == F(377, 500)
    assert c.block_offdiag_abs_upper == F(87, 100)
    assert c.unshifted_schur_det_lower == F(57, 2000)
    assert c.shifted_schur_det_lower == F(29, 250000)
    assert c.schur_gate_pass is True
    assert c.normalized_inertia == (4, 0, 0)


def test_actual_cross_entries_have_positive_certified_lower_enclosures():
    c = compute_certificate()
    assert c.b1_interval_lower == F(4751, 10000)
    assert c.b2_interval_lower == F(673, 2000)
    assert c.b3_interval_lower == F(4651, 20000)
    assert c.b1_interval_lower > 0
    assert c.b2_interval_lower > 0
    assert c.b3_interval_lower > 0
