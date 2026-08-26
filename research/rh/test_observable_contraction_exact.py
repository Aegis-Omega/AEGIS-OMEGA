"""Exact regressions for the Observable Contraction Freeze v1.

These tests intentionally use Fraction arithmetic only. They distinguish the
operator seen through A_- from unobservable directions of a prescribed T,
lock the exact PSD decision boundary, and preserve the singular-Y Layer-1
cross-coupling counterexample.
"""
from fractions import Fraction as F
import unittest

from observable_contraction_exact import (
    det_affine_2x2_coefficients,
    difference,
    dot,
    is_psd,
    matmul,
    matvec,
    observable_contraction_holds,
    project_onto_row_space,
    transpose,
)


class ObservableContractionExactTests(unittest.TestCase):
    def test_psd_requires_all_principal_minors_not_only_leading(self):
        # Leading principal minors are 0 and 0, but the {2} principal minor is -1.
        a = [[F(0), F(0)], [F(0), F(-1)]]
        self.assertFalse(is_psd(a))

    def test_psd_rejects_nonsymmetric_matrix(self):
        b = [[F(1), F(1)], [F(0), F(1)]]
        self.assertFalse(is_psd(b))

    def test_layer1_singular_y_cross_coupling_has_no_finite_psd_threshold(self):
        # ker(Y)=span(e2) and e2^T X e2 = 0, so the kernel condition holds.
        # Yet det(X-lambda Y) == -1 for every lambda, hence no member of the
        # affine family can be PSD.  Polynomial coefficients are ordered
        # constant, lambda, lambda^2 and are computed exactly.
        x = [[F(0), F(1)], [F(1), F(0)]]
        y = [[F(1), F(0)], [F(0), F(0)]]
        e2 = [F(0), F(1)]
        self.assertEqual(matvec(y, e2), [F(0), F(0)])
        self.assertEqual(dot(e2, matvec(x, e2)), F(0))
        self.assertEqual(det_affine_2x2_coefficients(x, y), (F(-1), F(0), F(0)))

    def test_rank_deficient_prescribed_T_need_not_be_global_contraction(self):
        A = [[F(1), F(0)]]
        T = [[F(1), F(0)], [F(0), F(2)]]
        Aplus = matmul(A, T)
        self.assertEqual(Aplus, A)
        self.assertTrue(is_psd(difference(A, T)))
        # e2 is invisible to A but is expanded by T^T by factor 2.
        self.assertEqual(matvec(transpose(T), [F(0), F(1)]), [F(0), F(2)])
        self.assertTrue(observable_contraction_holds(A, T))

    def test_full_column_rank_recovers_global_equivalence(self):
        A = [[F(1), F(0)], [F(0), F(1)]]
        good = [[F(1), F(0)], [F(0), F(1, 2)]]
        bad = [[F(3, 2), F(0)], [F(0), F(1, 2)]]
        self.assertTrue(is_psd(difference(A, good)))
        self.assertTrue(observable_contraction_holds(A, good))
        self.assertFalse(is_psd(difference(A, bad)))
        self.assertFalse(observable_contraction_holds(A, bad))

    def test_compression_can_contract_while_global_norm_exceeds_one(self):
        A = [[F(1), F(0)]]
        T = [[F(1, 2), F(0)], [F(0), F(2)]]
        self.assertEqual(difference(A, T), [[F(3, 4)]])
        self.assertTrue(observable_contraction_holds(A, T))
        # Observable direction e1 has gain 1/2; null direction e2 has gain 2.
        self.assertEqual(matvec(transpose(T), [F(1), F(0)]), [F(1, 2), F(0)])
        self.assertEqual(matvec(transpose(T), [F(0), F(1)]), [F(0), F(2)])

    def test_zero_defect_is_projected_eigencondition_not_global_one(self):
        A = [[F(1), F(0)]]
        T = [[F(1), F(0)], [F(1), F(1)]]
        TTt = matmul(T, transpose(T))
        z = [F(1), F(0)]
        self.assertEqual(difference(A, T), [[F(0)]])
        self.assertTrue(observable_contraction_holds(A, T))
        global_image = matvec(TTt, z)
        self.assertEqual(global_image, [F(1), F(1)])
        self.assertNotEqual(global_image, z)
        self.assertEqual(project_onto_row_space(A, global_image), z)


if __name__ == "__main__":
    unittest.main()
