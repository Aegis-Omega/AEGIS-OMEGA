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
        self.assertEqual(found[0].shared_territory, ("production-cookbook/src",))
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

    def test_a_generic_bucket_shared_at_depth_one_is_not_territory(self):
        # 28 of the 61 pairs the first sweep reported came from unrelated PRs
        # each introducing a `research/` folder. Proofs and security scanners
        # are not duplicates for sharing a bucket name; depth 2 separates them.
        proofs = added("research/rh/weil.py")
        scanner = added("research/falsifiers/glasswing.md")
        self.assertEqual(guard.territory(proofs, EXISTING) & guard.territory(scanner, EXISTING), set())
        self.assertEqual(
            guard.collide(proofs, [(1, "other", scanner)], min_shared=2, min_jaccard=0.34, existing=EXISTING),
            [],
        )

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


class CriticalEntrypointOverlap(unittest.TestCase):
    """Flag exact integration-file conflicts even in large mostly disjoint PRs."""

    def test_agent_dispatch_path_does_not_get_diluted(self):
        path = ".github/workflows/agent-dispatch.yml"
        mine = modified(path, *(f"lane_a/part_{i}.py" for i in range(80)))
        theirs = modified(path, *(f"lane_b/part_{i}.py" for i in range(80)))
        found = guard.collide(
            mine, [(342, "integration", theirs)], min_shared=2, min_jaccard=0.34,
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].critical_files, (path,))
        self.assertLess(found[0].jaccard, 0.02)
        self.assertIn(path, found[0].reason())

    def test_console_entrypoint_requires_review(self):
        path = "hub/src/lib/platformConsole.ts"
        mine = modified(path, *(f"mesh/part_{i}.ts" for i in range(80)))
        theirs = modified(path, *(f"glass/part_{i}.ts" for i in range(80)))
        found = guard.collide(
            mine, [(745, "holon", theirs)], min_shared=2, min_jaccard=0.34,
        )
        self.assertEqual([c.number for c in found], [745])
        self.assertEqual(found[0].critical_files, (path,))

    def test_low_similarity_ordinary_overlap_remains_allowed(self):
        shared = ("docs/ordinary_a.md", "docs/ordinary_b.md")
        mine = modified(*shared, *(f"a/file_{i}.py" for i in range(80)))
        theirs = modified(*shared, *(f"b/file_{i}.py" for i in range(80)))
        self.assertEqual(guard.collide(
            mine, [(3, "unrelated", theirs)], min_shared=2, min_jaccard=0.34,
        ), [])

    def test_generated_manifest_still_ignored(self):
        mine = modified(".claude.json", "only/a.py")
        theirs = modified(".claude.json", "only/b.py")
        self.assertEqual(guard.collide(
            mine, [(3, "unrelated", theirs)], min_shared=2, min_jaccard=0.34,
        ), [])


class Reporting(unittest.TestCase):
    def test_clean_report_names_the_pr(self):
        self.assertIn("#7", guard.render(7, []))
        self.assertIn("no open pull request", guard.render(7, []))

    def test_collision_report_names_the_other_pr_and_the_escape_hatch(self):
        found = guard.collide(
            added("x/sub/one.py", "x/sub/two.py"),
            [(243, "cookbook", added("x/sub/three.py"))],
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
            added("newdir/sub/a.py", "docs/b.py", "docs/c.py"),
            [
                (10, "file overlap only", modified("docs/b.py", "docs/c.py")),
                (11, "territory", added("newdir/sub/z.py")),
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


def renamed(pairs: list[tuple[str, str]]) -> list[dict]:
    """GitHub's shape for a rename: one row carrying both paths."""
    return [
        {"filename": new, "previous_filename": old, "status": "renamed"}
        for old, new in pairs
    ]


class RenamesDoNotHideOverlap(unittest.TestCase):
    """A rename must not make a contested path invisible.

    GitHub reports a rename as a single row whose `filename` is the new path
    and `previous_filename` the old one. Counting only `filename` meant a PR
    that moved a file reported no overlap with a PR that edited it -- the one
    case where the conflict is certain rather than probable.
    """

    def test_moving_files_still_collides_with_a_pr_editing_the_originals(self):
        mine = renamed([("src/a.py", "src/x.py"), ("src/b.py", "src/y.py")])
        theirs = modified("src/a.py", "src/b.py")
        found = guard.collide(
            mine, [(7, "edits the originals", theirs)],
            min_shared=2, min_jaccard=0.34, existing=EXISTING,
        )
        self.assertEqual(len(found), 1, "the rename hid a certain conflict")
        self.assertEqual(found[0].shared_files, ("src/a.py", "src/b.py"))

    def test_the_destination_paths_still_collide_too(self):
        mine = renamed([("src/a.py", "src/x.py"), ("src/b.py", "src/y.py")])
        theirs = modified("src/x.py", "src/y.py")
        found = guard.collide(
            mine, [(8, "edits the destinations", theirs)],
            min_shared=2, min_jaccard=0.34, existing=EXISTING,
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].shared_files, ("src/x.py", "src/y.py"))

    def test_touched_reports_both_ends_of_a_rename(self):
        self.assertEqual(
            guard.touched(renamed([("src/a.py", "src/x.py")])),
            {"src/a.py", "src/x.py"},
        )

    def test_touched_ignores_absent_and_non_string_paths(self):
        rows = [
            {"filename": "src/keep.py", "status": "modified"},
            {"filename": "src/also.py", "previous_filename": None, "status": "modified"},
            {"filename": "", "previous_filename": "", "status": "modified"},
        ]
        self.assertEqual(guard.touched(rows), {"src/keep.py", "src/also.py"})

    def test_a_rename_does_not_claim_its_source_directory_as_new_territory(self):
        # territory() is about directories a PR brings into existence. Moving
        # a file out of src/old/ does not create src/old/, so the old path
        # must not enter the territory set even though it is touched.
        rows = renamed([("src/old/a.py", "fresh/new/a.py")])
        self.assertNotIn("src/old", guard.territory(rows, EXISTING))


class MalformedFileEvidenceFailsClosed(unittest.TestCase):
    """A /files row is evidence only when it carries a path and a status."""

    def test_a_row_without_a_filename_is_refused(self):
        with self.assertRaisesRegex(ValueError, "without a filename"):
            guard._file_identity({"number": 101})

    def test_a_row_without_a_status_is_refused(self):
        with self.assertRaisesRegex(ValueError, "without a status: a/b.py"):
            guard._file_identity({"filename": "a/b.py"})

    def test_empty_and_non_string_fields_are_refused(self):
        for bad in ({"filename": "", "status": "added"},
                    {"filename": "a/b.py", "status": ""},
                    {"filename": 7, "status": "added"},
                    {"filename": "a/b.py", "status": 7},
                    {}):
            with self.assertRaises(ValueError, msg=repr(bad)):
                guard._file_identity(bad)

    def test_a_well_formed_row_returns_its_path(self):
        self.assertEqual(
            guard._file_identity({"filename": "a/b.py", "status": "renamed"}),
            "a/b.py",
        )


if __name__ == "__main__":
    unittest.main()
