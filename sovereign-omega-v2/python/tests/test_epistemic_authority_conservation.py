from __future__ import annotations

import itertools
import unittest

from epistemic_authority_conservation import (
    AuthorityLevel,
    TransitionGateV1,
    chain_authority,
    conservation_certificate,
    step_authority,
)

LEVELS = tuple(AuthorityLevel)


class EpistemicAuthorityConservationTests(unittest.TestCase):
    def test_single_step_is_non_amplifying_exhaustive(self):
        for source, transform, policy in itertools.product(LEVELS, repeat=3):
            out = step_authority(
                source,
                TransitionGateV1(transform, policy),
            )
            self.assertLessEqual(out, source)
            self.assertLessEqual(out, transform)
            self.assertLessEqual(out, policy)

    def test_two_step_chain_equals_global_meet_exhaustive(self):
        for values in itertools.product(LEVELS, repeat=5):
            initial, t1, p1, t2, p2 = values
            gates = (
                TransitionGateV1(t1, p1),
                TransitionGateV1(t2, p2),
            )
            out = chain_authority(initial, gates)
            expected = min(initial, t1, p1, t2, p2)
            self.assertEqual(out, expected)

    def test_authority_cannot_recover_after_downgrade(self):
        gates = (
            TransitionGateV1(AuthorityLevel.EPISTEMIC, AuthorityLevel.EPISTEMIC),
            TransitionGateV1(AuthorityLevel.PRODUCTION, AuthorityLevel.PRODUCTION),
        )
        out = chain_authority(AuthorityLevel.PRODUCTION, gates)
        self.assertEqual(out, AuthorityLevel.EPISTEMIC)

    def test_zero_is_absorbing(self):
        gates = (
            TransitionGateV1(AuthorityLevel.PRODUCTION, AuthorityLevel.PRODUCTION),
            TransitionGateV1(AuthorityLevel.PRODUCTION, AuthorityLevel.PRODUCTION),
        )
        self.assertEqual(
            chain_authority(AuthorityLevel.NONE, gates),
            AuthorityLevel.NONE,
        )

    def test_certificate_matches_global_meet(self):
        cert = conservation_certificate(
            AuthorityLevel.PRODUCTION,
            (
                TransitionGateV1(AuthorityLevel.EXECUTION, AuthorityLevel.PRODUCTION),
                TransitionGateV1(AuthorityLevel.PRODUCTION, AuthorityLevel.EPISTEMIC),
            ),
        )
        self.assertTrue(cert["equals_global_meet"])
        self.assertTrue(cert["non_amplifying"])
        self.assertEqual(cert["final"], "EPISTEMIC")
        self.assertEqual(cert["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
