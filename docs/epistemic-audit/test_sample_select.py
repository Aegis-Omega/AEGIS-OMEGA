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

from sample_select import canonical_frame, canonical_spec_hash, rank, select  # noqa: E402

SPEC_HASH = "f1a3e251b88deedc18359f56b93424b9111b3059075cbfa9c3d734252ea4649e"
EVENT_FORM = "sha256:" + SPEC_HASH


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


class SpecHashRepresentation(unittest.TestCase):
    """The §11 digest and the §17 envelope form must select the same sample.

    §11 writes SHA256(spec_hash ‖ case_id) without fixing a representation;
    §17 carries the same value as "sha256:<digest>". Hashing whichever form
    the caller holds would make the draw depend on the spelling of the
    reference, so the two forms are pinned to one canonical digest and every
    other spelling is refused.
    """

    def test_the_event_form_normalizes_to_the_bare_digest(self):
        self.assertEqual(canonical_spec_hash(EVENT_FORM), SPEC_HASH)
        self.assertEqual(canonical_spec_hash(SPEC_HASH), SPEC_HASH)

    def test_the_two_accepted_forms_rank_identically(self):
        # The defect this guards: before canonicalization these differed, so
        # the envelope value and the digest ranked the same case apart.
        self.assertEqual(rank(EVENT_FORM, "case-0001"), rank(SPEC_HASH, "case-0001"))

    def test_the_two_accepted_forms_draw_the_same_hundred(self):
        ids = frame(250)
        self.assertEqual(select(EVENT_FORM, ids), select(SPEC_HASH, ids))

    def test_the_two_accepted_forms_agree_on_the_census(self):
        ids = frame(60)
        self.assertEqual(select(EVENT_FORM, ids), select(SPEC_HASH, ids))

    def test_prefix_stripping_is_exactly_the_event_prefix(self):
        # Only "sha256:" is a declared form. A near-miss must not be shaved
        # off and quietly accepted.
        for bad in ("sha256=" + SPEC_HASH, "sha1:" + SPEC_HASH,
                    "SHA256:" + SPEC_HASH, "sha256::" + SPEC_HASH,
                    "sha256:sha256:" + SPEC_HASH):
            with self.assertRaises(ValueError, msg=bad):
                canonical_spec_hash(bad)

    def test_non_canonical_digests_are_refused_not_reshaped(self):
        for bad in (SPEC_HASH.upper(), SPEC_HASH[:63], SPEC_HASH + "0",
                    SPEC_HASH[:-1] + "g", "", " " + SPEC_HASH, SPEC_HASH + "\n"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                canonical_spec_hash(bad)

    def test_every_regime_validates_including_the_ones_that_never_rank(self):
        # A malformed spec_hash must not pass just because N <= 100 means no
        # ranking happens. Feasibility failure and census are checked too.
        for n in (0, 29, 30, 60, 100, 250):
            with self.assertRaises(ValueError, msg=f"N={n}"):
                select("not-a-digest", frame(n))

    def test_a_valid_but_different_digest_still_draws_differently(self):
        # Canonicalization must collapse representations, not distinct specs.
        ids = frame(250)
        self.assertNotEqual(select(EVENT_FORM, ids)[1], select("0" * 64, ids)[1])


class FrameInvariantsHoldAtBothEntryPoints(unittest.TestCase):
    """The frame rules must bind select(), not only the CLI.

    Both of these lived in `__main__` only, so importing select() skipped
    them. §11 reads its thresholds against N, so a frame whose size and whose
    number of cases disagree puts an undersized frame past the feasibility
    minimum; and an identifier that gets trimmed on the way in is no longer
    the identifier the frame froze.
    """

    def test_a_duplicate_cannot_pad_a_frame_past_the_feasibility_minimum(self):
        # 29 real cases plus one repeat. Thirty entries, twenty-nine cases.
        padded = frame(29) + ["case-0000"]
        self.assertEqual(len(padded), 30)
        self.assertEqual(len(set(padded)), 29)
        with self.assertRaisesRegex(ValueError, "duplicate case_ids"):
            select(SPEC_HASH, padded)

    def test_the_duplicate_is_named(self):
        with self.assertRaisesRegex(ValueError, "case-0000"):
            canonical_frame(frame(40) + ["case-0000"])

    def test_duplicates_are_refused_in_every_regime(self):
        for n in (0, 29, 30, 100, 250):
            with self.assertRaises(ValueError, msg=f"N={n}"):
                select(SPEC_HASH, frame(n) + ["case-0000"] * 2)

    def test_whitespace_bearing_ids_are_refused_not_trimmed(self):
        for bad in ("case-0001 ", " case-0001", "case-0001\t", "\ncase-0001", "   "):
            with self.assertRaisesRegex(ValueError, "whitespace", msg=repr(bad)):
                canonical_frame(frame(40) + [bad])

    def test_empty_and_non_string_ids_are_refused(self):
        for bad in ("", None, 7):
            with self.assertRaisesRegex(ValueError, "non-empty string", msg=repr(bad)):
                canonical_frame(frame(40) + [bad])

    def test_a_clean_frame_passes_through_unchanged(self):
        ids = frame(40)
        self.assertEqual(canonical_frame(ids), ids)

    def test_the_emitted_ids_are_the_frame_ids(self):
        # The whole point of refusing to trim: every id the draw emits must be
        # findable in the frame that was frozen.
        ids = frame(250)
        _, chosen = select(SPEC_HASH, ids)
        self.assertLessEqual(set(chosen), set(ids))


if __name__ == "__main__":
    unittest.main()
