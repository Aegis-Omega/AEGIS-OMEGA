#!/usr/bin/env python3
"""Pagination regressions for the PR overlap guard.

RED contract: the guard must enumerate every page of open PRs and every page of
changed files. A 100-item first page is not evidence that the collection ends.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import unittest.mock
from urllib.parse import parse_qs, urlsplit

import pr_overlap_guard as guard


class PaginationRegression(unittest.TestCase):
    def test_get_all_follows_a_full_page_until_a_short_page(self):
        page1 = [{"number": i} for i in range(100)]
        page2 = [{"number": 100}]
        responses = [page1, page2]

        with unittest.mock.patch.object(guard, "_get", side_effect=responses) as get:
            found = guard._get_all("https://api.github.com/repos/o/r/pulls?state=open", "token")

        self.assertEqual(len(found), 101)
        self.assertEqual(get.call_count, 2)
        self.assertIn("per_page=100", get.call_args_list[0].args[0])
        self.assertIn("page=1", get.call_args_list[0].args[0])
        self.assertIn("page=2", get.call_args_list[1].args[0])

    def test_get_all_stops_after_one_short_page(self):
        with unittest.mock.patch.object(guard, "_get", return_value=[{"number": 1}]) as get:
            found = guard._get_all("https://api.github.com/repos/o/r/pulls/1/files", "token")

        self.assertEqual(found, [{"number": 1}])
        self.assertEqual(get.call_count, 1)

    def test_fetch_uses_paginated_reads_for_prs_and_files(self):
        open_prs = [
            pr(1),
            pr(2, title="other"),
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
            raise AssertionError(f"unexpected URL: {url}")

        with unittest.mock.patch.object(guard, "_get_all", side_effect=get_all) as paged:
            mine, others = guard.fetch("o/r", "token", 1)

        self.assertEqual(len(mine), 101)
        self.assertEqual(others, [(2, "other", other_files)])
        self.assertGreaterEqual(paged.call_count, 3)


def pr(number, *, title=None, label=False, base_ref="main", base_sha="a" * 40):
    return {
        "number": number, "title": title or f"PR {number}", "state": "open",
        "labels": [{"name": "stacked-pr"}] if label else [],
        "base": {"ref": base_ref, "sha": base_sha, "repo": {"full_name": "o/r"}},
        "head": {"ref": f"branch-{number}", "sha": f"{number:040x}", "repo": {"full_name": "o/r"}},
    }


class API:
    """Replace transport only; execute the shipped pagination and decision code."""
    def __init__(self, prs, files=None, changed=None, comparison=None):
        self.prs = prs
        self.files = files or {p["number"]: [
            {"filename": "scripts/a.py", "status": "modified"},
            {"filename": "scripts/b.py", "status": "modified"},
        ] for p in prs}
        self.changed = changed
        self.comparison = comparison
        self.scans = 0

    def get(self, url, token):
        parsed = urlsplit(url)
        page = int(parse_qs(parsed.query).get("page", ["1"])[0])
        if parsed.path.endswith("/pulls"):
            if page == 1:
                self.scans += 1
            data = self.changed if self.changed is not None and self.scans > 1 else self.prs
        elif "/files" in parsed.path:
            number = int(parsed.path.split("/")[-2])
            data = self.files[number]
        elif "/compare/" in parsed.path:
            return self.comparison or {"status": "diverged", "behind_by": 1,
                                       "merge_base_commit": {"sha": "f" * 40}}
        else:
            raise AssertionError(f"Unexpected transport request: {url}")
        return copy.deepcopy(data[(page - 1) * 100:page * 100])


class CollectionSafety(unittest.TestCase):
    def test_repeated_page_is_not_a_complete_census(self):
        page = [{"number": i} for i in range(100)]
        with unittest.mock.patch.object(guard, "_get", side_effect=[page, page, []]):
            with self.assertRaises(ValueError):
                guard._get_all("https://api.github.com/repos/o/r/pulls", "token")

    def test_malformed_collection_does_not_become_empty_evidence(self):
        with unittest.mock.patch.object(guard, "_get", return_value={"message": "unavailable"}):
            with self.assertRaises(ValueError):
                guard._get_all("https://api.github.com/repos/o/r/pulls", "token")

    def test_malformed_row_is_rejected(self):
        with unittest.mock.patch.object(guard, "_get", return_value=["not an object"]):
            with self.assertRaises(ValueError):
                guard._get_all("https://api.github.com/repos/o/r/pulls", "token")

    def test_github_3000_file_cap_is_not_claimed_complete(self):
        pages = [[{"filename": f"src/{i}.py", "status": "modified"}
                  for i in range(n, n + 100)] for n in range(0, 3000, 100)] + [[]]
        with unittest.mock.patch.object(guard, "_get", side_effect=pages):
            with self.assertRaises(ValueError):
                guard._get_all("https://api.github.com/repos/o/r/pulls/1/files", "token")

    def test_exact_multiple_of_100_requires_terminal_empty_page(self):
        page = [{"number": i} for i in range(100)]
        with unittest.mock.patch.object(guard, "_get", side_effect=[page, []]) as get:
            self.assertEqual(len(guard._get_all("https://api.github.com/repos/o/r/pulls", "token")), 100)
        self.assertEqual(get.call_count, 2)

    def test_late_page_failure_propagates(self):
        with unittest.mock.patch.object(guard, "_get", side_effect=[
            [{"number": i} for i in range(100)], ValueError("page two failed")]):
            with self.assertRaisesRegex(ValueError, "page two"):
                guard._get_all("https://api.github.com/repos/o/r/pulls", "token")


class SnapshotAndStack(unittest.TestCase):
    def run_fetch(self, api):
        with unittest.mock.patch.object(guard, "_get", side_effect=api.get):
            return guard.fetch("o/r", "test-token", 1)

    def test_label_cannot_hide_unrelated_pr(self):
        _, others = self.run_fetch(API([pr(1), pr(2, label=True)]))
        self.assertEqual([n for n, _, _ in others], [2])

    def test_parent_exemption_is_pair_local(self):
        parent = pr(1)
        child = pr(2, label=True, base_ref=parent["head"]["ref"], base_sha=parent["head"]["sha"])
        api = API([parent, child, pr(3, label=True)], comparison={
            "status": "ahead", "behind_by": 0, "merge_base_commit": {"sha": parent["head"]["sha"]}})
        _, others = self.run_fetch(api)
        self.assertEqual([n for n, _, _ in others], [3])

    def test_targeting_a_branch_without_ancestry_is_not_an_exemption(self):
        parent = pr(1)
        child = pr(2, label=True, base_ref=parent["head"]["ref"], base_sha=parent["head"]["sha"])
        _, others = self.run_fetch(API([parent, child]))
        self.assertEqual([n for n, _, _ in others], [2])

    def test_same_branch_name_in_another_repo_is_not_an_exemption(self):
        parent = pr(1)
        child = pr(2, label=True, base_ref=parent["head"]["ref"], base_sha=parent["head"]["sha"])
        child["base"]["repo"]["full_name"] = "elsewhere/r"
        _, others = self.run_fetch(API([parent, child]))
        self.assertEqual([n for n, _, _ in others], [2])

    def test_head_change_during_census_denies_stale_result(self):
        before = [pr(1), pr(2)]
        after = copy.deepcopy(before)
        after[1]["head"]["sha"] = "b" * 40
        with self.assertRaises(ValueError):
            self.run_fetch(API(before, changed=after))

    def test_new_pr_during_census_requires_rescan(self):
        with self.assertRaises(ValueError):
            self.run_fetch(API([pr(1)], changed=[pr(1), pr(2)]))

    def test_missing_candidate_does_not_produce_clean_result(self):
        api = API([pr(2)], files={1: [], 2: []})
        with self.assertRaises(ValueError):
            self.run_fetch(api)

    def test_collision_after_pr_100_is_seen(self):
        prs = [pr(n) for n in range(1, 130)]
        files = {p["number"]: [] for p in prs}
        files[1] = files[129] = [{"filename": f"src/{x}.py", "status": "modified"} for x in (1, 2)]
        mine, others = self.run_fetch(API(prs, files))
        found = guard.collide(mine, others, min_shared=2, min_jaccard=0.34)
        self.assertEqual([c.number for c in found], [129])


class ExecutedWorkflowBoundary(unittest.TestCase):
    def test_python_failure_survives_summary_pipe(self):
        source = (Path(__file__).resolve().parents[1] / ".github/workflows/pr-overlap-guard.yml").read_text()
        block = source.split("- name: Report overlap with open pull requests", 1)[1].split("run: |", 1)[1]
        lines = []
        for line in block.splitlines()[1:]:
            if line and not line.startswith("          "):
                break
            lines.append(line[10:])
        script = "\n".join(lines)
        import re
        script = re.sub(r"\$\{\{.*?\}\}", "1", script)
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp, "python")
            fake.write_text("#!/bin/sh\nexit 2\n")
            fake.chmod(0o755)
            env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"],
                   "GITHUB_STEP_SUMMARY": str(Path(tmp, "summary")),
                   "GITHUB_HEAD_SHA": "1" * 40, "GITHUB_BASE_SHA": "2" * 40}
            result = subprocess.run(["bash", "-e", "-c", script], env=env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr.decode())

    def test_missing_working_directory_is_not_empty_base(self):
        with self.assertRaises((OSError, ValueError)):
            guard.base_directories("/definitely-not-an-aegis-directory")

    def test_exact_base_is_not_candidate_filesystem(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                return subprocess.check_output(["git", "-C", tmp, *args], stderr=subprocess.DEVNULL).decode().strip()
            git("init", "-q")
            git("config", "user.name", "synthetic-test")
            git("config", "user.email", "synthetic@example.invalid")
            Path(tmp, "scripts").mkdir()
            Path(tmp, "scripts", "base.py").write_text("# base\n")
            git("add", ".")
            git("commit", "-qm", "synthetic base")
            base = git("rev-parse", "HEAD")
            Path(tmp, "production-cookbook").mkdir()
            Path(tmp, "production-cookbook", "candidate.py").write_text("# candidate\n")
            git("add", ".")
            git("commit", "-qm", "synthetic candidate")
            with unittest.mock.patch.dict(os.environ, {"GITHUB_BASE_SHA": base}):
                observed = guard.base_directories(tmp)
            self.assertEqual(observed, frozenset({"scripts"}))

    def test_collision_ties_do_not_depend_on_api_order(self):
        files = [{"filename": f"scripts/{n}.py", "status": "modified"} for n in (1, 2)]
        items = [(3, "three", files), (2, "two", files)]
        a = guard.collide(files, items, min_shared=2, min_jaccard=0.34)
        b = guard.collide(files, list(reversed(items)), min_shared=2, min_jaccard=0.34)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
