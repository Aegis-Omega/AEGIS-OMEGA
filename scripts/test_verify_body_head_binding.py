#!/usr/bin/env python3
"""Regressions for the body/head provenance gate.

The stale fixture is the real PR #334 description as served by the GitHub API
at 2026-08-29T22:07Z, when its head was aec7f236... but its body still cited
957f18c9... -- the third recurrence of this defect on this repository.
"""

import unittest

from verify_body_head_binding import claims_a_head, verify

REAL_334_BODY = """### Exact-head evidence

- PR head: `957f18c9a3150dbbceb1d500e1918d1765c8fd64`
- source tree: `0d95145237f5203c0f9955fde72c64a0a17d3ef8`
- base: `main@a34d664d66ae9f7c2e729cd4ccb07b74130c660f`

Hosted GitHub Actions on that exact head:

- Constitutional Automaton `33273646297`: **SUCCESS** - all 15 jobs
"""

REAL_334_ACTUAL_HEAD = "aec7f236140ae3b3bd87e6bd52757f7b1da25e18"
REAL_334_CLAIMED_HEAD = "957f18c9a3150dbbceb1d500e1918d1765c8fd64"

NO_CLAIM_BODY = """## Root cause

One line: an ignoreCommand at the root, where the projects actually read from.
Verified against the nine commits pushed today.
"""


class BodyHeadBindingTests(unittest.TestCase):
    def test_real_stale_334_body_is_rejected(self):
        ok, msg = verify(REAL_334_BODY, REAL_334_ACTUAL_HEAD)
        self.assertFalse(ok)
        self.assertIn("STALE_BODY", msg)
        self.assertIn(REAL_334_ACTUAL_HEAD, msg)

    def test_same_body_passes_against_the_head_it_was_written_for(self):
        ok, msg = verify(REAL_334_BODY, REAL_334_CLAIMED_HEAD)
        self.assertTrue(ok)
        self.assertIn("BOUND", msg)

    def test_body_making_no_head_claim_is_not_gated(self):
        ok, msg = verify(NO_CLAIM_BODY, REAL_334_ACTUAL_HEAD)
        self.assertTrue(ok)
        self.assertIn("NO_HEAD_CLAIM", msg)

    def test_base_sha_alone_does_not_satisfy_the_gate(self):
        # a34d664d... is the base; citing it must not count as citing the head
        body = "### Exact-head evidence\nbase: a34d664d66ae9f7c2e729cd4ccb07b74130c660f\n"
        ok, _ = verify(body, REAL_334_ACTUAL_HEAD)
        self.assertFalse(ok)

    def test_secondary_hashes_do_not_cause_false_failure(self):
        body = (
            "## Current exact head\n"
            f"{REAL_334_ACTUAL_HEAD}\n"
            "receipt root d6eb522d8c4cf08c41e00bc22d34dea8235184e558ee1bc24fc631fd48cefa34\n"
            "tree 0d95145237f5203c0f9955fde72c64a0a17d3ef8\n"
        )
        ok, msg = verify(body, REAL_334_ACTUAL_HEAD)
        self.assertTrue(ok, msg)

    def test_markers_are_case_insensitive(self):
        self.assertTrue(claims_a_head("CURRENT EXACT HEAD"))
        self.assertTrue(claims_a_head("### exact-head evidence"))
        self.assertFalse(claims_a_head("just a normal description"))

    def test_malformed_head_fails_closed(self):
        for bad in ("", "deadbeef", "ZZZ" + "0" * 37):
            ok, msg = verify(REAL_334_BODY, bad)
            self.assertFalse(ok)
            self.assertIn("HEAD_SHA_MALFORMED", msg)

    def test_uppercase_sha_in_body_is_not_silently_accepted(self):
        # git shas are lowercase; an uppercase transcription is still stale
        body = "### Exact-head evidence\n" + REAL_334_ACTUAL_HEAD.upper()
        ok, _ = verify(body, REAL_334_ACTUAL_HEAD)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
