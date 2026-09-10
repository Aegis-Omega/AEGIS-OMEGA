#!/usr/bin/env python3
"""Pagination regressions for the PR overlap guard.

RED contract: the guard must enumerate every page of open PRs and every page of
changed files. A 100-item first page is not evidence that the collection ends.
"""
from __future__ import annotations

import unittest
from unittest import mock

import pr_overlap_guard as guard


class PaginationRegression(unittest.TestCase):
    def test_get_all_follows_a_full_page_until_a_short_page(self):
        page1 = [{"number": i} for i in range(100)]
        page2 = [{"number": 100}]
        responses = [page1, page2]

        with mock.patch.object(guard, "_get", side_effect=responses) as get:
            found = guard._get_all("https://api.github.com/repos/o/r/pulls?state=open", "token")

        self.assertEqual(len(found), 101)
        self.assertEqual(get.call_count, 2)
        self.assertIn("per_page=100", get.call_args_list[0].args[0])
        self.assertIn("page=1", get.call_args_list[0].args[0])
        self.assertIn("page=2", get.call_args_list[1].args[0])

    def test_get_all_stops_after_one_short_page(self):
        with mock.patch.object(guard, "_get", return_value=[{"number": 1}]) as get:
            found = guard._get_all("https://api.github.com/repos/o/r/pulls/1/files", "token")

        self.assertEqual(found, [{"number": 1}])
        self.assertEqual(get.call_count, 1)

    def test_fetch_uses_paginated_reads_for_prs_and_files(self):
        open_prs = [
            {"number": 1, "title": "candidate", "labels": []},
            {"number": 2, "title": "other", "labels": []},
        ]
        candidate_files = [{"filename": f"mine/{i}.py", "status": "modified"} for i in range(101)]
        other_files = [{"filename": "other.py", "status": "modified"}]

        def get_all(url: str, token: str):
            if url.endswith("/pulls?state=open"):
                return open_prs
            if url.endswith("/pulls/1/files"):
                return candidate_files
            if url.endswith("/pulls/2/files"):
                return other_files
            self.fail(f"unexpected URL: {url}")

        with mock.patch.object(guard, "_get_all", side_effect=get_all) as paged:
            mine, others = guard.fetch("o/r", "token", 1)

        self.assertEqual(len(mine), 101)
        self.assertEqual(others, [(2, "other", other_files)])
        self.assertEqual(paged.call_count, 3)


if __name__ == "__main__":
    unittest.main()
