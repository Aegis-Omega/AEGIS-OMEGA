from __future__ import annotations

import itertools
import unittest

from conservative_consensus_crdt import (
    convergence_certificate,
    crdt_merge,
    reconcile_nonempty,
    safe_local_update,
    safety_le,
)
from epistemic_authority_conservation import AuthorityLevel
from no_free_epistemic_gain import EpistemicStateV1


def state(claims, authority, uncertainty):
    return EpistemicStateV1(
        frozenset(claims),
        authority,
        uncertainty,
    )


class ConservativeConsensusCRDTTests(unittest.TestCase):
    def setUp(self):
        self.a = state(
            {"A", "B", "C"},
            AuthorityLevel.PRODUCTION,
            100,
        )
        self.b = state(
            {"A", "B"},
            AuthorityLevel.EXECUTION,
            700,
        )
        self.c = state(
            {"A", "C"},
            AuthorityLevel.EPISTEMIC,
            3000,
        )

    def test_merge_is_upper_bound_in_safety_order(self):
        merged = crdt_merge(self.a, self.b)
        self.assertTrue(safety_le(self.a, merged))
        self.assertTrue(safety_le(self.b, merged))

    def test_merge_commutative_associative_idempotent(self):
        self.assertEqual(
            crdt_merge(self.a, self.b),
            crdt_merge(self.b, self.a),
        )
        self.assertEqual(
            crdt_merge(crdt_merge(self.a, self.b), self.c),
            crdt_merge(self.a, crdt_merge(self.b, self.c)),
        )
        self.assertEqual(crdt_merge(self.a, self.a), self.a)

    def test_safe_local_update_can_only_weaken_or_preserve(self):
        weaker = state(
            {"A", "B"},
            AuthorityLevel.EXECUTION,
            500,
        )
        self.assertTrue(safe_local_update(self.a, weaker))

    def test_claim_gain_is_not_crdt_native_update(self):
        old = state(
            {"A"},
            AuthorityLevel.EPISTEMIC,
            1000,
        )
        stronger = state(
            {"A", "B"},
            AuthorityLevel.EPISTEMIC,
            1000,
        )
        self.assertFalse(safe_local_update(old, stronger))

    def test_authority_gain_is_not_crdt_native_update(self):
        old = state(
            {"A"},
            AuthorityLevel.EPISTEMIC,
            1000,
        )
        stronger = state(
            {"A"},
            AuthorityLevel.EXECUTION,
            1000,
        )
        self.assertFalse(safe_local_update(old, stronger))

    def test_uncertainty_reduction_is_not_crdt_native_update(self):
        old = state(
            {"A"},
            AuthorityLevel.EPISTEMIC,
            1000,
        )
        stronger = state(
            {"A"},
            AuthorityLevel.EPISTEMIC,
            500,
        )
        self.assertFalse(safe_local_update(old, stronger))

    def test_same_deliveries_converge_for_all_orders_and_duplicates(self):
        baseline = reconcile_nonempty((self.a, self.b, self.c))
        inputs = (self.a, self.b, self.c)
        for permutation in itertools.permutations(inputs):
            self.assertEqual(
                reconcile_nonempty(permutation),
                baseline,
            )
        self.assertEqual(
            reconcile_nonempty((self.a, self.b, self.b, self.c, self.a)),
            baseline,
        )

    def test_partition_then_heal_converges(self):
        left_partition = reconcile_nonempty((self.a, self.b))
        right_partition = reconcile_nonempty((self.b, self.c))

        healed_left = crdt_merge(left_partition, right_partition)
        healed_right = crdt_merge(right_partition, left_partition)
        global_state = reconcile_nonempty((self.a, self.b, self.c))

        self.assertEqual(healed_left, global_state)
        self.assertEqual(healed_right, global_state)

    def test_convergence_receipt_requires_equal_reconciled_state(self):
        receipt = convergence_certificate(
            (self.a, self.b, self.c),
            (self.c, self.a, self.b, self.b),
        )
        self.assertEqual(receipt["decision"], "PASS")
        self.assertEqual(
            receipt["network_eventual_delivery"],
            "ASSUMED_NOT_VERIFIED",
        )
        self.assertEqual(receipt["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
