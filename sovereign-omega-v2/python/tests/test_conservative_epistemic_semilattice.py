from __future__ import annotations

import itertools
import unittest

from conservative_epistemic_semilattice import (
    LossBearingEpistemicStateV1,
    conservative_certificate,
    conservative_merge,
)
from epistemic_authority_conservation import AuthorityLevel

LEVELS = tuple(AuthorityLevel)
UNCERTAINTIES = (0, 1, 100, 5000, 10000)


def state(a, u):
    return LossBearingEpistemicStateV1(a, u)


class ConservativeEpistemicSemilatticeTests(unittest.TestCase):
    def test_commutative_exhaustive_grid(self):
        values = tuple(
            state(authority, uncertainty)
            for authority, uncertainty in itertools.product(
                LEVELS, UNCERTAINTIES
            )
        )
        for left, right in itertools.product(values, repeat=2):
            self.assertEqual(
                conservative_merge(left, right),
                conservative_merge(right, left),
            )

    def test_idempotent_exhaustive_grid(self):
        for authority, uncertainty in itertools.product(
            LEVELS, UNCERTAINTIES
        ):
            item = state(authority, uncertainty)
            self.assertEqual(conservative_merge(item, item), item)

    def test_associative_representative_exhaustive_authority_grid(self):
        uncertainties = (0, 100, 10000)
        values = tuple(
            state(authority, uncertainty)
            for authority, uncertainty in itertools.product(
                LEVELS, uncertainties
            )
        )
        for a, b, c in itertools.product(values, repeat=3):
            self.assertEqual(
                conservative_merge(conservative_merge(a, b), c),
                conservative_merge(a, conservative_merge(b, c)),
            )

    def test_merge_is_conservative_in_both_coordinates(self):
        for a1, a2, u1, u2 in itertools.product(
            LEVELS, LEVELS, UNCERTAINTIES, UNCERTAINTIES
        ):
            left = state(a1, u1)
            right = state(a2, u2)
            out = conservative_merge(left, right)
            self.assertLessEqual(out.authority, left.authority)
            self.assertLessEqual(out.authority, right.authority)
            self.assertGreaterEqual(out.uncertainty_bps, left.uncertainty_bps)
            self.assertGreaterEqual(out.uncertainty_bps, right.uncertainty_bps)

    def test_certificate_equals_global_min_max(self):
        items = (
            state(AuthorityLevel.PRODUCTION, 50),
            state(AuthorityLevel.EXECUTION, 900),
            state(AuthorityLevel.EPISTEMIC, 400),
        )
        cert = conservative_certificate(items)
        self.assertTrue(cert["authority_equals_global_min"])
        self.assertTrue(cert["uncertainty_equals_global_max"])
        self.assertEqual(cert["authority"], "EPISTEMIC")
        self.assertEqual(cert["uncertainty_bps"], 900)
        self.assertEqual(cert["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
