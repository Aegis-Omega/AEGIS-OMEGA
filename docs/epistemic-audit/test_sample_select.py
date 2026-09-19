#!/usr/bin/env python3
"""Regressions for the MUSTALAH-ANANA-REPLAY-001 sampler.

EPISTEMIC TIER: T0. Every assertion below is mechanically determined by
amendment §11 and by SHA-256; none of it is a judgement call.

The sampler had no test, and the gap was not theoretical: its docstring
claimed hash rank order for all output while the census branch emitted
case_id order. A consumer trusting the stated contract would have read the
census in the wrong order and had no way to notice. The ordering tests below
exist so the two branches can never silently diverge from what §11 says
again.

    python3 test_sample_select.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sample_select import rank, select  # noqa: E402

SPEC_HASH = "f1a3e251b88deedc18359f56b93424b9111b3059075cbfa9c3d734252ea4649e"


def frame(n: int) -> list[str]:
    """n case_ids whose case_id order and hash order are both well defined."""
    return [f"case-{i:04d}" for i in range(n)]


class FeasibilityBoundary(unittest.TestCase):
    """§11: N < 30 stops; 30 is the first admissible frame."""

    def test_below_thirty_is_a_feasibility_failure_with_no_selection(self):
        for n in (0, 1, 29):
            verdict, chosen = select(SPEC_HASH, frame(n))
            self.assertEqual(verdict, "FEASIBILITY_FAILURE", f"N={n}")
            self.assertEqual(chosen, [], f"N={n}")

    def test_thirty_is_admissible(self):
        verdict, chosen = select(SPEC_HASH, frame(30))
        self.assertEqual(verdict, "FULL_CENSUS")
        self.assertEqual(len(chosen), 30)


class CensusRegime(unittest.TestCase):
    """§11: 30 <= N <= 100 uses the full census, 100 inclusive."""

    def test_the_whole_frame_is_returned(self):
        for n in (30, 64, 100):
            verdict, chosen = select(SPEC_HASH, frame(n))
            self.assertEqual(verdict, "FULL_CENSUS", f"N={n}")
            self.assertEqual(sorted(chosen), sorted(frame(n)), f"N={n}")

    def test_census_is_emitted_in_case_id_order_not_hash_order(self):
        # The documented contract. §11 prescribes the hash ranking for the
        # N > 100 draw only; the census draws nothing, so it stays in case_id
        # order. Asserting both halves, because an implementation that used
        # hash order here would still satisfy a length-only check.
        _, chosen = select(SPEC_HASH, frame(60))
        self.assertEqual(chosen, sorted(frame(60)))
        hash_order = sorted(frame(60), key=lambda c: rank(SPEC_HASH, c))
        self.assertNotEqual(chosen, hash_order, "precondition: the orders differ")

    def test_input_order_does_not_change_the_census(self):
        ids = frame(45)
        self.assertEqual(select(SPEC_HASH, ids)[1], select(SPEC_HASH, ids[::-1])[1])


class DeterministicDraw(unittest.TestCase):
    """§11: N > 100 selects the 100 smallest SHA256(spec_hash || case_id)."""

    def test_one_hundred_and_one_draws_exactly_one_hundred(self):
        verdict, chosen = select(SPEC_HASH, frame(101))
        self.assertEqual(verdict, "DETERMINISTIC_100")
        self.assertEqual(len(chosen), 100)

    def test_the_draw_is_the_hundred_smallest_hashes_in_ascending_order(self):
        ids = frame(250)
        _, chosen = select(SPEC_HASH, ids)
        expected = sorted(ids, key=lambda c: rank(SPEC_HASH, c))[:100]
        self.assertEqual(chosen, expected)
        ranks = [rank(SPEC_HASH, c) for c in chosen]
        self.assertEqual(ranks, sorted(ranks), "emitted in ascending hash order")
        # Nothing outside the draw may out-rank something inside it.
        excluded = set(ids) - set(chosen)
        self.assertLess(max(ranks), min(rank(SPEC_HASH, c) for c in excluded))

    def test_input_order_does_not_change_the_draw(self):
        ids = frame(250)
        self.assertEqual(select(SPEC_HASH, ids)[1], select(SPEC_HASH, ids[::-1])[1])

    def test_a_different_spec_hash_draws_a_different_sample(self):
        # The spec hash is bound into the ranking, so freezing a new spec must
        # not reproduce the previous draw.
        ids = frame(250)
        other = "0" * 64
        self.assertNotEqual(select(SPEC_HASH, ids)[1], select(other, ids)[1])


class Ranking(unittest.TestCase):
    def test_rank_is_sha256_of_spec_hash_concatenated_with_case_id(self):
        import hashlib

        expected = hashlib.sha256((SPEC_HASH + "case-0001").encode("utf-8")).hexdigest()
        self.assertEqual(rank(SPEC_HASH, "case-0001"), expected)

    def test_rank_is_stable_across_calls(self):
        first = rank(SPEC_HASH, "case-0001")
        self.assertEqual({first, rank(SPEC_HASH, "case-0001"), rank(SPEC_HASH, "case-0001")}, {first})


if __name__ == "__main__":
    unittest.main()
