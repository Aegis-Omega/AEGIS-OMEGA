"""Tests pinning the CCIL loop-holonomy orientation.

The v5 artifact recorded [[0, -1], [1, 0]] for a loop that actually computes to
[[0, 1], [-1, 0]] — the inverse. These tests exist so that annotation can never
drift from the computation again.
"""

import math

import numpy as np

from holonomy_diagnostics import (
    compose_loop,
    diagnose,
    identity_defect,
    orientation_sign,
    rotation_block,
    trace_phase,
)

THETA = math.pi / 4


def test_loop_is_clockwise_quarter_turn():
    """The computed loop is R(-pi/2), NOT the R(+pi/2) the v5 artifact claimed."""
    loop = compose_loop(rotation_block(THETA))
    assert np.allclose(np.real(loop[:2, :2]), [[0, 1], [-1, 0]], atol=1e-12)
    # The annotated matrix is the inverse; assert it is genuinely different.
    assert not np.allclose(np.real(loop[:2, :2]), [[0, -1], [1, 0]], atol=1e-12)


def test_annotated_and_computed_are_inverses():
    """Not a typo: the two matrices are inverse rotations of each other."""
    computed = np.array([[0.0, 1.0], [-1.0, 0.0]])
    annotated = np.array([[0.0, -1.0], [1.0, 0.0]])
    assert np.allclose(computed @ annotated, np.eye(2), atol=1e-12)


def test_trace_phase_cannot_distinguish_them():
    """Why the bug survived review: the v5 scalar is identical for both."""
    computed = np.eye(4, dtype=complex)
    computed[:2, :2] = [[0, 1], [-1, 0]]
    annotated = np.eye(4, dtype=complex)
    annotated[:2, :2] = [[0, -1], [1, 0]]
    assert trace_phase(computed) == trace_phase(annotated) == 0.0
    assert np.trace(computed) == np.trace(annotated) == 2


def test_diagnostics_do_distinguish_them():
    """The two new diagnostics separate what the trace collapses."""
    computed = np.eye(4, dtype=complex)
    computed[:2, :2] = [[0, 1], [-1, 0]]
    annotated = np.eye(4, dtype=complex)
    annotated[:2, :2] = [[0, -1], [1, 0]]
    assert orientation_sign(computed) == 1
    assert orientation_sign(annotated) == -1
    # Same magnitude of defect, opposite winding — orientation is the separator.
    assert math.isclose(identity_defect(computed), identity_defect(annotated))


def test_zero_trace_phase_does_not_imply_trivial_loop():
    """The central point: phase 0.0 while the loop is far from the identity."""
    record = diagnose(THETA)
    assert record["postnikov_k3_phase"] == 0.0
    assert math.isclose(record["identity_defect"], 2.0, abs_tol=1e-12)
    assert record["loop_is_identity"] is False
    assert "nontrivial matrix holonomy" in record["interpretation"]


def test_identity_loop_is_reported_trivial():
    """Control: theta = 0 gives a genuinely trivial loop."""
    record = diagnose(0.0)
    assert record["postnikov_k3_phase"] == 0.0
    assert record["identity_defect"] < 1e-12
    assert record["loop_is_identity"] is True
    assert record["orientation_sign"] == 0


def test_reduction_to_u_squared_holds_for_orthogonal_u():
    """compose_loop == U**2 only because U_adj is U's inverse. Pin that."""
    u = rotation_block(THETA)
    assert np.allclose(compose_loop(u), u @ u, atol=1e-12)
    assert np.allclose(u @ u.conj().T, np.eye(4), atol=1e-12)


def test_orientation_flips_with_theta_sign():
    """Sanity: reversing theta reverses the winding."""
    assert orientation_sign(compose_loop(rotation_block(THETA))) == 1
    assert orientation_sign(compose_loop(rotation_block(-THETA))) == -1
