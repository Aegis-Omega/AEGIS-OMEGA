#!/usr/bin/env python3
"""Regressions for the PR overlap guard.

Every case is drawn from a real collision in this repository's open PR list on
2026-09-03, so the thresholds are checked against what actually happened rather
than against invented shapes.
"""
from __future__ import annotations

import unittest

import pr_overlap_guard as guard


def added(*paths: str) -> list[dict]:
    return [{"filename": p, "status": "added"} for p in paths]


def modified(*paths: str) -> list[dict]:
    return [{"filename": p, "status": "modified"} for p in paths]


class GeneratedPaths(unittest.TestCase):
    def test_refresh_bot_paths_carry_no_signal(self):
        # Every branch rewrites these. Counting them would fire on every PR.
        for path in (".claude.json", "package-lock.json", "INDEX.md", "web/package-lock.json"):
            self.assertTrue(guard.is_generated(path), path)

    def test_ordinary_source_is_not_generated(self):
        for path in ("scripts/pr_overlap_guard.py", "docs/PROOF.md", "src/core/canonicalize.ts"):
            self.assertFalse(guard.is_generated(path), path)

    def test_two_prs_sharing_only_generated_files_do_not_collide(self):
        mine = modified(".claude.json") + added("a/one.py")
        theirs = modified(".claude.json") + added("b/two.py")
        self.assertEqual(guard.collide(mine, [(1, "other", theirs)], min_shared=2, min_jaccard=0.34), [])


#: Directories that already exist on `main`. Adding a file inside one is
#: ordinary work and must never register as territory.
EXISTING = frozenset({".github", "scripts", "docs", "src", "vertex", "sovereign-omega-v2"})


class TerritoryOverlap(unittest.TestCase):
    """The #238 / #243 case: one feature, two implementations, zero shared paths."""

    PR238 = added("production-cookbook/src/App.tsx", "production-cookbook/package.json")
    PR243 = added("production-cookbook/src/main.jsx", "production-cookbook/public/favicon.svg")

    def test_shared_new_directory_collides_with_no_shared_file(self):
        mine = set(e["filename"] for e in self.PR238)
        theirs = set(e["filename"] for e in self.PR243)
        self.assertEqual(mine & theirs, set(), "precondition: the paths genuinely differ")

        found = guard.collide(
            self.PR238,
            [(243, "cookbook", self.PR243)],
            min_shared=2,
            min_jaccard=0.34,
            existing=EXISTING,
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].shared_territory, ("production-cookbook",))
        self.assertIn("both create", found[0].reason())

    def test_adding_files_under_an_existing_directory_is_not_territory(self):
        # The defect the first version shipped with: running it against the live
        # repository reported 67 of 119 open PRs as colliding, because they all
        # add a file under `.github/` or `scripts/`. Both have existed for
        # months. A guard that fires on more than half of all PRs is noise.
        mine = added(".github/workflows/a.yml", "scripts/a.py")
        theirs = added(".github/workflows/b.yml", "scripts/b.py")
        self.assertEqual(guard.territory(mine, EXISTING), set())
        self.assertEqual(
            guard.collide(mine, [(2, "other", theirs)], min_shared=2, min_jaccard=0.34, existing=EXISTING),
            [],
        )

    def test_editing_a_shared_directory_is_not_territory_overlap(self):
        mine = modified("scripts/a.py")
        theirs = modified("scripts/b.py")
        self.assertEqual(
            guard.collide(mine, [(2, "other", theirs)], min_shared=2, min_jaccard=0.34, existing=EXISTING),
            [],
        )

    def test_a_new_top_level_file_claims_no_territory(self):
        self.assertEqual(guard.territory(added("NOTES.md"), EXISTING), set())

    def test_base_directories_reads_the_real_tree(self):
        found = guard.base_directories(".")
        self.assertIn("scripts", found)
        self.assertNotIn(".git", found)


class FileOverlap(unittest.TestCase):
    """The #226 / #229 case: the same documents added by two sessions."""

    SHARED = (
        "docs/EPISTEMIC_AUDIT_AMENDMENT.md",
        "docs/preregistrations/MUSTALAH-ANANA-REPLAY-001.spec.json",
    )

    def test_same_documents_collide(self):
        mine = added(*self.SHARED)
        theirs = added(*self.SHARED, "sovereign-omega-v2/scripts/sample_select.py")
        found = guard.collide(mine, [(229, "epistemic audit", theirs)], min_shared=2, min_jaccard=0.34)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].shared_files, tuple(sorted(self.SHARED)))

    def test_one_shared_file_below_threshold_does_not_collide(self):
        mine = modified("a.py", "b.py", "c.py", "d.py")
        theirs = modified("a.py", "x.py", "y.py", "z.py")
        self.assertEqual(guard.collide(mine, [(3, "other", theirs)], min_shared=2, min_jaccard=0.34), [])

    def test_jaccard_is_symmetric_and_bounded(self):
        a, b = {"x", "y"}, {"y", "z"}
        self.assertEqual(guard.jaccard(a, b), guard.jaccard(b, a))
        self.assertEqual(guard.jaccard(a, a), 1.0)
        self.assertEqual(guard.jaccard(set(), set()), 0.0)


class Reporting(unittest.TestCase):
    def test_clean_report_names_the_pr(self):
        self.assertIn("#7", guard.render(7, []))
        self.assertIn("no open pull request", guard.render(7, []))

    def test_collision_report_names_the_other_pr_and_the_escape_hatch(self):
        found = guard.collide(
            added("x/one.py", "x/two.py"),
            [(243, "cookbook", added("x/three.py"))],
            min_shared=2,
            min_jaccard=0.34,
            existing=EXISTING,
        )
        report = guard.render(238, found)
        self.assertIn("#243", report)
        self.assertIn("cookbook", report)
        self.assertIn(guard.OVERRIDE_LABEL, report)

    def test_territory_collisions_are_reported_before_weaker_file_overlaps(self):
        found = guard.collide(
            added("newdir/a.py", "docs/b.py", "docs/c.py"),
            [
                (10, "file overlap only", modified("docs/b.py", "docs/c.py")),
                (11, "territory", added("newdir/z.py")),
            ],
            min_shared=2,
            min_jaccard=0.34,
            existing=EXISTING,
        )
        self.assertEqual([c.number for c in found], [11, 10])

    def test_determinism(self):
        args = (
            added("d/a.py", "d/b.py"),
            [(1, "one", added("d/c.py")), (2, "two", added("d/d.py"))],
        )
        runs = [
            guard.render(9, guard.collide(*args, min_shared=2, min_jaccard=0.34, existing=EXISTING))
            for _ in range(3)
        ]
        self.assertEqual(len(set(runs)), 1)


if __name__ == "__main__":
    unittest.main()
