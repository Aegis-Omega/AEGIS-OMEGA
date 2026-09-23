from __future__ import annotations

import itertools
import unittest
from itertools import combinations

from epistemic_authority_conservation import AuthorityLevel
from no_free_epistemic_gain import (
    EpistemicStateV1,
    canonical_consensus,
    conservative_meet,
    epistemic_le,
    no_free_gain_certificate,
    verify_canonical_consensus,
)

CLAIMS = ("A", "B", "C")
UNCERTAINTIES = (0, 100, 1000)
LEVELS = tuple(AuthorityLevel)


def powerset(items):
    out = []
    for size in range(len(items) + 1):
        for subset in combinations(items, size):
            out.append(frozenset(subset))
    return tuple(out)


CLAIMSETS = powerset(CLAIMS)
STATES = tuple(
    EpistemicStateV1(claims, authority, uncertainty)
    for claims, authority, uncertainty in itertools.product(
        CLAIMSETS, LEVELS, UNCERTAINTIES
    )
)


class NoFreeEpistemicGainTests(unittest.TestCase):
    def test_order_is_reflexive_exhaustive(self):
        for state in STATES:
            self.assertTrue(epistemic_le(state, state))

    def test_order_is_antisymmetric_exhaustive(self):
        for left, right in itertools.product(STATES, repeat=2):
            if epistemic_le(left, right) and epistemic_le(right, left):
                self.assertEqual(left, right)

    def test_order_is_transitive_exhaustive(self):
        for left, middle, right in itertools.product(STATES, repeat=3):
            if epistemic_le(left, middle) and epistemic_le(middle, right):
                self.assertTrue(epistemic_le(left, right))

    def test_meet_is_common_lower_bound_exhaustive(self):
        for left, right in itertools.product(STATES, repeat=2):
            meet = conservative_meet(left, right)
            self.assertTrue(epistemic_le(meet, left))
            self.assertTrue(epistemic_le(meet, right))

    def test_meet_is_greatest_lower_bound_exhaustive(self):
        for left, right in itertools.product(STATES, repeat=2):
            meet = conservative_meet(left, right)
            for candidate in STATES:
                if epistemic_le(candidate, left) and epistemic_le(
                    candidate, right
                ):
                    self.assertTrue(epistemic_le(candidate, meet))

    def test_meet_never_invents_claims_or_authority(self):
        for left, right in itertools.product(STATES, repeat=2):
            meet = conservative_meet(left, right)
            self.assertEqual(
                meet.claims,
                left.claims & right.claims,
            )
            self.assertLessEqual(meet.authority, left.authority)
            self.assertLessEqual(meet.authority, right.authority)
            self.assertGreaterEqual(
                meet.uncertainty_bps,
                left.uncertainty_bps,
            )
            self.assertGreaterEqual(
                meet.uncertainty_bps,
                right.uncertainty_bps,
            )

    def test_meet_is_commutative_and_idempotent(self):
        for left, right in itertools.product(STATES, repeat=2):
            self.assertEqual(
                conservative_meet(left, right),
                conservative_meet(right, left),
            )
        for state in STATES:
            self.assertEqual(conservative_meet(state, state), state)

    def test_meet_associative_representative_grid(self):
        sample = STATES[::7]
        for x, y, z in itertools.product(sample, repeat=3):
            self.assertEqual(
                conservative_meet(conservative_meet(x, y), z),
                conservative_meet(x, conservative_meet(y, z)),
            )

    def test_optimistic_union_is_not_free_consensus(self):
        left = EpistemicStateV1(
            frozenset({"A", "B"}),
            AuthorityLevel.EXECUTION,
            1000,
        )
        right = EpistemicStateV1(
            frozenset({"A", "C"}),
            AuthorityLevel.EPISTEMIC,
            3000,
        )
        optimistic = EpistemicStateV1(
            frozenset({"A", "B", "C"}),
            AuthorityLevel.EXECUTION,
            1000,
        )
        cert = no_free_gain_certificate(left, right, optimistic)
        self.assertEqual(cert["decision"], "DENY")
        self.assertFalse(cert["candidate_is_common_lower_bound"])

    def test_canonical_consensus_is_order_independent(self):
        inputs = (
            EpistemicStateV1(
                frozenset({"A", "B", "C"}),
                AuthorityLevel.PRODUCTION,
                100,
            ),
            EpistemicStateV1(
                frozenset({"A", "B"}),
                AuthorityLevel.EXECUTION,
                400,
            ),
            EpistemicStateV1(
                frozenset({"A", "D"}),
                AuthorityLevel.EPISTEMIC,
                900,
            ),
        )
        expected = canonical_consensus(inputs)
        for permutation in itertools.permutations(inputs):
            self.assertEqual(
                canonical_consensus(permutation),
                expected,
            )
        self.assertEqual(expected.claims, frozenset({"A"}))
        self.assertEqual(expected.authority, AuthorityLevel.EPISTEMIC)
        self.assertEqual(expected.uncertainty_bps, 900)
        self.assertEqual(
            verify_canonical_consensus(inputs, expected)["decision"],
            "PASS",
        )


if __name__ == "__main__":
    unittest.main()
