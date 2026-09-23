from __future__ import annotations

import itertools
import unittest
from itertools import combinations

from epistemic_authority_conservation import AuthorityLevel
from multi_agent_conservative_consensus import (
    consensus_certificate,
    is_common_lower_bound,
    multi_agent_consensus,
)
from no_free_epistemic_gain import (
    EpistemicStateV1,
    epistemic_le,
)

CLAIMS = ("A", "B")
LEVELS = tuple(AuthorityLevel)
UNCERTAINTIES = (0, 100, 1000)


def powerset(items):
    out = []
    for size in range(len(items) + 1):
        for subset in combinations(items, size):
            out.append(frozenset(subset))
    return tuple(out)


STATES = tuple(
    EpistemicStateV1(claims, authority, uncertainty)
    for claims, authority, uncertainty in itertools.product(
        powerset(CLAIMS), LEVELS, UNCERTAINTIES
    )
)


class MultiAgentConservativeConsensusTests(unittest.TestCase):
    def test_consensus_is_common_lower_bound_exhaustive_triples(self):
        for states in itertools.product(STATES, repeat=3):
            result = multi_agent_consensus(states)
            self.assertTrue(is_common_lower_bound(result, states))

    def test_consensus_is_greatest_lower_bound_exhaustive_triples(self):
        for states in itertools.product(STATES, repeat=3):
            result = multi_agent_consensus(states)
            for candidate in STATES:
                if is_common_lower_bound(candidate, states):
                    self.assertTrue(epistemic_le(candidate, result))

    def test_order_independent_for_all_permutations_representative(self):
        inputs = (
            EpistemicStateV1(
                frozenset({"A", "B"}),
                AuthorityLevel.PRODUCTION,
                100,
            ),
            EpistemicStateV1(
                frozenset({"A"}),
                AuthorityLevel.EXECUTION,
                700,
            ),
            EpistemicStateV1(
                frozenset({"A", "C"}),
                AuthorityLevel.EPISTEMIC,
                3000,
            ),
            EpistemicStateV1(
                frozenset({"A", "B", "C"}),
                AuthorityLevel.PRODUCTION,
                200,
            ),
        )
        expected = multi_agent_consensus(inputs)
        for permutation in itertools.permutations(inputs):
            self.assertEqual(
                multi_agent_consensus(permutation),
                expected,
            )
        self.assertEqual(expected.claims, frozenset({"A"}))
        self.assertEqual(
            expected.authority,
            AuthorityLevel.EPISTEMIC,
        )
        self.assertEqual(expected.uncertainty_bps, 3000)

    def test_duplicate_agent_is_idempotent(self):
        state = EpistemicStateV1(
            frozenset({"A"}),
            AuthorityLevel.EXECUTION,
            500,
        )
        self.assertEqual(
            multi_agent_consensus((state, state, state)),
            state,
        )

    def test_candidate_with_non_common_claim_denies(self):
        inputs = (
            EpistemicStateV1(
                frozenset({"A", "B"}),
                AuthorityLevel.EXECUTION,
                100,
            ),
            EpistemicStateV1(
                frozenset({"A", "C"}),
                AuthorityLevel.EXECUTION,
                100,
            ),
        )
        candidate = EpistemicStateV1(
            frozenset({"A", "B"}),
            AuthorityLevel.EXECUTION,
            100,
        )
        cert = consensus_certificate(inputs, candidate)
        self.assertEqual(cert["decision"], "DENY")
        self.assertFalse(cert["candidate_is_common_lower_bound"])

    def test_exact_consensus_receipt_is_authority_neutral(self):
        inputs = (
            EpistemicStateV1(
                frozenset({"A", "B"}),
                AuthorityLevel.PRODUCTION,
                100,
            ),
            EpistemicStateV1(
                frozenset({"A"}),
                AuthorityLevel.EPISTEMIC,
                900,
            ),
        )
        expected = multi_agent_consensus(inputs)
        cert = consensus_certificate(inputs, expected)
        self.assertEqual(
            cert["decision"],
            "PASS_CANONICAL_CONSENSUS",
        )
        self.assertEqual(cert["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
