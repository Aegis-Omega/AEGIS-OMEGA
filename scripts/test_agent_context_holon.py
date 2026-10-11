"""Read-only holon preflight tests; no GitHub calls or paid inference.

Run: python3 -m unittest discover -s scripts -p test_agent_context_holon.py -v
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().with_name("agent_context.py")
SPEC = importlib.util.spec_from_file_location("aegis_agent_context_holon", SOURCE)
ctx = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ctx)


class HolonContextTests(unittest.TestCase):
    def test_closing_issue_ref_detects_pr_with_unrelated_title(self):
        pr = {"n": 732, "t": "Refactor core", "h": "claude/transport",
              "b": "main", "s": "a" * 40, "body": "Closes #734\nChecks"}
        matches = ctx.overlaps([pr], "#734")
        self.assertEqual(len(matches), 1)
        self.assertIn("#734", matches[0][2])

    def test_issue_ref_outranks_title_keyword_overlap(self):
        closing = {"n": 732, "t": "Other work", "h": "branch/z",
                   "body": "Fixes #734"}
        similar = {"n": 733, "t": "holon transport",
                   "h": "holon/transport", "body": ""}
        matches = ctx.overlaps([similar, closing], "holon transport #734")
        self.assertEqual(matches[0][1]["n"], 732)

    def test_unrelated_issue_mention_is_not_closing_claim(self):
        pr = {"n": 732, "t": "Other work", "h": "branch/z",
              "body": "See #734 for context. Closes #999"}
        self.assertEqual(ctx.overlaps([pr], "#734"), [])

    def test_missing_or_invalid_body_never_fabricates_issue_match(self):
        pr = {"n": 732, "t": "Other work", "h": "branch/z"}
        self.assertEqual(ctx.overlaps([pr], "#734"), [])
        pr["body"] = None
        self.assertEqual(ctx.overlaps([pr], "#734"), [])

    def test_pr_page_query_includes_bounded_body(self):
        import tempfile
        record = {"n": 732, "t": "Other work", "h": "branch/z",
                  "b": "main", "s": "a" * 40, "body": "Resolves #734"}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(ctx, "git_dir", return_value=folder), \
                 patch.object(ctx, "sh", return_value=json.dumps([record])) as call:
                prs, source = ctx.open_prs()
        self.assertEqual((len(prs), source), (1, "github"))
        self.assertIn("body:", call.call_args_list[0].args[4])

    def test_holon_vector_never_hides_operator_and_peer_blockers(self):
        claimed = {"n": 739, "t": "Receipts", "labels": ["claimed", "needs-operator"]}
        overlap = [(2, {"n": 743, "t": "Receipts", "h": "a", "b": "main"}, ["receipts"])]
        actual = ctx.holon_blockers("cache", "partial", "UNVERIFIED_QUICK",
                                   overlap, [(claimed, ["receipts"])])
        self.assertEqual(actual, [
            "HOLD_UNVERIFIED_MAIN",
            "HOLD_INCOMPLETE_PR_INVENTORY",
            "HOLD_INCOMPLETE_ISSUE_BOARD",
            "OPERATOR_ACTION_REQUIRED",
            "HOLD_CLAIMED_WORK_COORDINATE",
            "REVIEW_EXISTING_PR_FIRST",
        ])

    def test_holon_vector_fresh_and_unclaimed_is_empty(self):
        self.assertEqual(ctx.holon_blockers("github", "github", "FRESH", [], []), [])

    def test_holon_vector_unknown_main_keeps_operator_action(self):
        item = {"n": 735, "t": "GitHub billing", "labels": ["needs-operator"]}
        self.assertEqual(ctx.holon_blockers("github", "github", "FETCH_FAILED",
                                           [], [(item, ["billing"])]),
                         ["HOLD_UNVERIFIED_MAIN", "OPERATOR_ACTION_REQUIRED"])

    def test_holon_vector_does_not_mutate_source_records(self):
        item = {"n": 739, "t": "Receipts", "labels": ["claimed"]}
        original = list(item["labels"])
        for _ in range(2):
            self.assertEqual(ctx.holon_blockers("github", "github", "FRESH",
                                               [], [(item, [])]),
                             ["HOLD_CLAIMED_WORK_COORDINATE"])
        self.assertEqual(item["labels"], original)

    def test_operator_claim_and_stale_sources_are_all_retained(self):
        claimed = {"n": 739, "t": "Receipts", "labels": ["claimed", "needs-operator"]}
        overlap = [(3, {"n": 743, "t": "Receipts SDK", "h": "receipts",
                        "b": "main", "s": "a" * 40}, ["receipts"])]
        blocks = ctx.coordination_blockers(
            {"state": "FETCH_FAILED", "sha": None}, "partial", "unavailable",
            overlap, [(claimed, ["receipts"])])
        self.assertEqual(blocks, [
            "MAIN_FRESHNESS_UNVERIFIED",
            "PR_INVENTORY_INCOMPLETE",
            "ISSUE_BOARD_INCOMPLETE",
            "OPERATOR_ACTION_REQUIRED",
            "CLAIMED_ISSUE_COORDINATION",
            "POSSIBLE_PR_TITLE_OVERLAP",
        ])

    def test_unresolved_task_is_not_a_free_task(self):
        blocks = ctx.coordination_blockers(
            {"state": "FRESH", "sha": "a" * 40}, "github", "github", [], [])
        self.assertEqual(blocks, ["ISSUE_NOT_RESOLVED"])

    def test_clean_advisory_board_does_not_create_authority(self):
        issue = {"n": 734, "t": "Holon", "labels": ["task"]}
        blocks = ctx.coordination_blockers(
            {"state": "FRESH", "sha": "a" * 40}, "github", "github",
            [], [(issue, ["holon"])])
        self.assertEqual(blocks, [])
        self.assertEqual(ctx.holon_disposition("github", "github", [], [(issue, [])]),
                         "ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED")

    def test_main_preserves_distinct_blocker_vectors_without_duplicate_json_keys(self):
        issue = {"n": 735, "t": "CI billing lock",
                 "labels": ["needs-operator", "claimed"]}
        out = io.StringIO()
        with patch.object(ctx, "sh", return_value=""), \
             patch.object(ctx, "verify_main_freshness",
                          return_value={"state": "FETCH_FAILED", "sha": None}), \
             patch.object(ctx, "open_prs", return_value=([], "partial")), \
             patch.object(ctx, "open_issue_board", return_value=([issue], "github")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "#735"]):
            with contextlib.redirect_stdout(out):
                ctx.main()

        def reject_duplicate_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise AssertionError(f"Duplicate JSON key: {key}")
                result[key] = value
            return result

        receipt = json.loads(out.getvalue(), object_pairs_hook=reject_duplicate_pairs)
        self.assertEqual(receipt["holon_blockers"], [
            "HOLD_UNVERIFIED_MAIN", "HOLD_INCOMPLETE_PR_INVENTORY",
            "OPERATOR_ACTION_REQUIRED", "HOLD_CLAIMED_WORK_COORDINATE"])
        self.assertEqual(receipt["coordination_blockers"], [
            "MAIN_FRESHNESS_UNVERIFIED", "PR_INVENTORY_INCOMPLETE",
            "OPERATOR_ACTION_REQUIRED", "CLAIMED_ISSUE_COORDINATION"])
        self.assertEqual(receipt["holon_disposition"], "HOLD_UNVERIFIED_MAIN")

    def test_unknown_peers_are_never_empty_board(self):
        self.assertEqual(ctx.holon_disposition("unavailable", "unavailable", [], []),
                         "HOLD_INCOMPLETE_SHARED_STATE")
        self.assertEqual(ctx.holon_disposition("branches", "github", [], []),
                         "HOLD_INCOMPLETE_SHARED_STATE")
        self.assertEqual(ctx.holon_disposition("github", "partial", [], []),
                         "HOLD_INCOMPLETE_SHARED_STATE")

    def test_claimed_issue_requires_coordination(self):
        i = {"n": 739, "t": "AEGIS receipts", "labels": ["task", "p1", "claimed"]}
        self.assertEqual(ctx.holon_disposition("github", "github", [], [(i, ["receipts"])]),
                         "HOLD_CLAIMED_WORK_COORDINATE")

    def test_operator_only_task_never_delegated(self):
        i = {"n": 735, "t": "Fix GitHub billing", "labels": ["p0", "needs-operator"]}
        self.assertEqual(ctx.holon_disposition("github", "github", [], [(i, ["billing"])]),
                         "OPERATOR_ACTION_REQUIRED")

    def test_overlapping_pr_requires_existing_work_review(self):
        hits = [(2, {"n": 730, "t": "evidence ranked dispatch", "h": "x", "b": "main"},
                 ["dispatch"])]
        self.assertEqual(ctx.holon_disposition("github", "github", hits, []),
                         "REVIEW_EXISTING_PR_FIRST")
        self.assertEqual(ctx.holon_disposition("github", "github", [], []),
                         "ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED")

    def test_explicit_issue_id_is_match_even_without_keywords(self):
        items = [{"n": 735, "t": "Actions billing lock", "labels": ["p0"]},
                 {"n": 739, "t": "Receipts SDK", "labels": ["p1", "claimed"]}]
        found = ctx.relevant_issues(items, "Please inspect #739")
        self.assertEqual([i["n"] for i, _ in found], [739])

    def test_issue_board_api_success_and_unknown(self):
        data = '{"total":1,"incomplete":false,"items":[{"n":735,"t":"CI lock","labels":["task","p0"]}]}'
        with patch.object(ctx, "sh", return_value=data) as call:
            issues, status = ctx.open_issue_board()
            self.assertEqual((len(issues), status), (1, "github"))
            args = call.call_args.args
            self.assertEqual(args[:2], ("gh", "api"))
            self.assertIn("is%3Aissue", args[2])
        with patch.object(ctx, "sh", return_value=""):
            self.assertEqual(ctx.open_issue_board(), ([], "unavailable"))
        with patch.object(ctx, "sh", return_value='{"total":101,"incomplete":false,"items":[]}'):
            self.assertEqual(ctx.open_issue_board(), ([], "partial"))
        with patch.object(ctx, "sh", return_value='{"total":0,"incomplete":true,"items":[]}'):
            self.assertEqual(ctx.open_issue_board(), ([], "partial"))
        with patch.object(ctx, "sh", return_value='{"total":0,"items":[]}'):
            self.assertEqual(ctx.open_issue_board(), ([], "partial"))
        with patch.object(ctx, "sh", return_value='{"total":1,"items":[{"n":"bad"}]}'):
            self.assertEqual(ctx.open_issue_board(), ([], "unavailable"))

    def test_exact_100_page_drift_is_incomplete(self):
        """100 + [] must still re-read page 1 before a complete receipt."""
        import tempfile
        def record(n):
            return {"n": n, "t": f"PR {n}", "h": f"feature/{n}",
                    "b": "main", "s": "a" * 40}
        first = [record(n) for n in range(200, 100, -1)]
        changed = [record(201)] + first[:-1]
        calls = []
        def response(*args, **_kwargs):
            if args[:2] != ("gh", "api"):
                return ""
            page = 1 if args[2].endswith("&page=1") else 2
            calls.append(page)
            if page == 2:
                return "[]"
            return json.dumps(changed if calls.count(1) > 1 else first)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ctx, "git_dir", return_value=directory), \
             patch.object(ctx, "sh", side_effect=response):
            rows, status = ctx.open_prs()
        self.assertEqual((len(rows), status), (100, "partial"))
        self.assertEqual(calls, [1, 2, 1])

    def test_exact_100_stable_page_is_complete(self):
        import tempfile
        def record(n):
            return {"n": n, "t": f"PR {n}", "h": f"feature/{n}",
                    "b": "main", "s": "a" * 40}
        first = [record(n) for n in range(200, 100, -1)]
        calls = []
        def response(*args, **_kwargs):
            if args[:2] != ("gh", "api"):
                return ""
            page = 1 if args[2].endswith("&page=1") else 2
            calls.append(page)
            return "[]" if page == 2 else json.dumps(first)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ctx, "git_dir", return_value=directory), \
             patch.object(ctx, "sh", side_effect=response):
            rows, status = ctx.open_prs()
        self.assertEqual((len(rows), status), (100, "github"))
        self.assertEqual(calls, [1, 2, 1])

    def test_duplicate_across_pages_is_not_a_complete_shared_snapshot(self):
        import re
        import tempfile
        def rec(n):
            return {"n": n, "t": f"PR {n}", "h": f"feature/{n}",
                    "b": "main", "s": "a" * 40}
        first = [rec(i) for i in range(200, 100, -1)]
        def response(*args, **_kwargs):
            if args[:2] != ("gh", "api"):
                return ""
            page = int(re.search(r"&page=(\d+)", args[2]).group(1))
            return json.dumps(first if page == 1 else [rec(101)])
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ctx, "git_dir", return_value=directory), \
             patch.object(ctx, "sh", side_effect=response):
            records, state = ctx.open_prs()
        self.assertEqual(state, "partial")
        self.assertEqual(len(records), 100)

    def test_first_page_changes_during_pagination_is_not_complete(self):
        import re
        import tempfile
        def rec(n):
            return {"n": n, "t": f"PR {n}", "h": f"feature/{n}",
                    "b": "main", "s": "a" * 40}
        first = [rec(i) for i in range(200, 100, -1)]
        shifted = [rec(201)] + first[:-1]
        first_reads = [0]
        def response(*args, **_kwargs):
            if args[:2] != ("gh", "api"):
                return ""
            page = int(re.search(r"&page=(\d+)", args[2]).group(1))
            if page == 2:
                return json.dumps([rec(100)])
            first_reads[0] += 1
            return json.dumps(first if first_reads[0] == 1 else shifted)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ctx, "git_dir", return_value=directory), \
             patch.object(ctx, "sh", side_effect=response):
            records, state = ctx.open_prs()
        self.assertEqual(state, "partial")
        self.assertEqual(len(records), 101)
        self.assertEqual(first_reads[0], 2)

    def test_stable_multipage_snapshot_rechecks_first_page(self):
        import re
        import tempfile
        def rec(n):
            return {"n": n, "t": f"PR {n}", "h": f"feature/{n}",
                    "b": "main", "s": "a" * 40}
        first = [rec(i) for i in range(200, 100, -1)]
        first_reads = [0]
        def response(*args, **_kwargs):
            if args[:2] != ("gh", "api"):
                return ""
            page = int(re.search(r"&page=(\d+)", args[2]).group(1))
            if page == 1:
                first_reads[0] += 1
            return json.dumps(first if page == 1 else [rec(100)])
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(ctx, "git_dir", return_value=directory), \
             patch.object(ctx, "sh", side_effect=response):
            records, state = ctx.open_prs()
        self.assertEqual((len(records), state, first_reads[0]), (101, "github", 2))

    def test_pr_second_page_outage_is_partial_not_complete(self):
        """One good page followed by network failure must not clear collisions."""
        import tempfile
        first = [{"n": i + 1, "t": "task", "h": "head",
                  "b": "main", "s": "a" * 40} for i in range(100)]
        with tempfile.TemporaryDirectory() as directory:
            def response(*args, **_kwargs):
                if args[:2] == ("gh", "api") and args[2].endswith("&page=1"):
                    return json.dumps(first, indent=2)
                return ""
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=response):
                entries, source = ctx.open_prs()
        self.assertEqual(len(entries), 100)
        self.assertEqual(source, "partial")
        self.assertEqual(ctx.holon_disposition(source, "github", [], []),
                         "HOLD_INCOMPLETE_SHARED_STATE")

    def test_pr_complete_two_pages_is_accepted(self):
        import tempfile
        first = [{"n": i + 1, "t": "task", "h": "head",
                  "b": "main", "s": "a" * 40} for i in range(100)]
        second = {"n": 101, "t": "end", "h": "head", "b": "main", "s": "b" * 40}
        with tempfile.TemporaryDirectory() as directory:
            def response(*args, **_kwargs):
                if args[:2] == ("gh", "api"):
                    return (json.dumps(first, indent=2)
                            if args[2].endswith("&page=1") else json.dumps([second], indent=2))
                return ""
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=response):
                entries, source = ctx.open_prs()
        self.assertEqual((len(entries), source), (101, "github"))

    def test_empty_github_pr_array_is_really_complete(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            def answer(*args, **_kwargs):
                return "[]" if args[:2] == ("gh", "api") else ""
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=answer):
                self.assertEqual(ctx.open_prs(), ([], "github"))

    def test_pretty_json_is_parsed_as_one_github_page(self):
        import tempfile
        record = {"n": 732, "t": "holon", "h": "claude/agent-ground-truth",
                  "b": "main", "s": "a" * 40}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", return_value=json.dumps([record], indent=2)):
                self.assertEqual(ctx.open_prs(), ([record], "github"))

    def test_invalid_cached_pr_does_not_become_authority(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "aegis-open-prs.json").write_text(
                json.dumps([{"n": 1, "t": "fake"}]), encoding="utf-8")
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", return_value=""):
                prs, source = ctx.open_prs()
        self.assertEqual((prs, source), ([], "unavailable"))

    def test_quick_preflight_never_uses_remote_pr_listing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=AssertionError("network called")):
                self.assertEqual(ctx.open_prs(quick=True), ([], "unavailable"))

    def test_git_dir_lookup_is_bounded(self):
        with patch.object(ctx, "sh", return_value="/tmp/.git") as sh:
            self.assertEqual(ctx.git_dir(quick=True), "/tmp/.git")
        sh.assert_called_once_with("git", "rev-parse",
                                   "--absolute-git-dir", timeout=2)

    def test_full_git_dir_keeps_original_timeout(self):
        with patch.object(ctx, "sh", return_value="/tmp/.git") as sh:
            self.assertEqual(ctx.git_dir(quick=False), "/tmp/.git")
        sh.assert_called_once_with("git", "rev-parse",
                                   "--absolute-git-dir", timeout=30)

    def test_quick_uses_bounded_local_git_timeout(self):
        output = io.StringIO()
        with patch.object(ctx, "sh", return_value="") as git, \
             patch.object(ctx, "verify_main_freshness",
                          return_value={"state": "UNVERIFIED_QUICK", "sha": None}), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "--quick", "#734"]), \
             contextlib.redirect_stdout(output):
            ctx.main()
        requests = [call for call in git.call_args_list
                    if call.args and call.args[0] == "git"]
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(call.kwargs.get("timeout") == 2 for call in requests))
        self.assertEqual(json.loads(output.getvalue())["holon_disposition"],
                         "HOLD_UNVERIFIED_MAIN")

    def test_corrupt_local_git_epoch_is_unknown_not_crash(self):
        def local_git(*args, **kwargs):
            return "invalid-epoch" if "--format=%ct" in args else ""
        output = io.StringIO()
        with patch.object(ctx, "sh", side_effect=local_git), \
             patch.object(ctx, "verify_main_freshness",
                          return_value={"state": "FETCH_FAILED", "sha": None}), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "#734"]), \
             contextlib.redirect_stdout(output):
            ctx.main()
        report = json.loads(output.getvalue())
        self.assertIsNone(report["local_main_age_days"])
        self.assertIsNone(report["main_age_days"])
        self.assertEqual(report["holon_disposition"], "HOLD_UNVERIFIED_MAIN")

    def test_quick_main_skips_fetch_scanning_and_billing_calls(self):
        buf = io.StringIO()
        with patch.object(ctx, "sh", return_value="") as sh, \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")) as prs, \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")) as issues, \
             patch.object(ctx, "existing_code", side_effect=AssertionError("expensive grep")), \
             patch.object(ctx, "billing_locked", side_effect=AssertionError("remote status")), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "--quick", "#735"]):
            with contextlib.redirect_stdout(buf):
                ctx.main()
        obj = json.loads(buf.getvalue())
        self.assertIsNone(obj["ci_billing_locked"])
        self.assertIsNone(obj["open"])
        self.assertEqual(obj["holon_disposition"], "HOLD_UNVERIFIED_MAIN")
        prs.assert_called_once_with(quick=True)
        issues.assert_called_once_with(timeout=4)
        self.assertFalse(any(args.args[:3] == ("git", "fetch", "-q")
                             for args in sh.call_args_list))

    def test_legacy_plain_list_cache_is_not_complete_evidence(self):
        import tempfile
        valid = {"n": 734, "t": "existing", "h": "head", "b": "main",
                 "s": "a" * 40}
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "aegis-open-prs.json").write_text(
                json.dumps([valid]), encoding="utf-8")
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", return_value=""):
                self.assertEqual(ctx.open_prs(quick=True), ([], "unavailable"))

    def test_v2_empty_complete_snapshot_is_a_valid_quick_cache(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "aegis-open-prs.json").write_text(
                json.dumps({"format": "AEGIS_PR_SNAPSHOT_V2",
                            "complete": True, "prs": []}), encoding="utf-8")
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=AssertionError("unexpected network call")):
                self.assertEqual(ctx.open_prs(quick=True), ([], "cache"))
        self.assertEqual(ctx.holon_disposition("cache", "github", [], []),
                         "HOLD_INCOMPLETE_SHARED_STATE")

    def test_v2_empty_incomplete_snapshot_is_not_a_quick_cache(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "aegis-open-prs.json").write_text(
                json.dumps({"format": "AEGIS_PR_SNAPSHOT_V2",
                            "complete": False, "prs": []}), encoding="utf-8")
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=AssertionError("unexpected network call")):
                self.assertEqual(ctx.open_prs(quick=True), ([], "unavailable"))

    def test_v2_complete_snapshot_can_support_bounded_hook(self):
        import tempfile
        valid = {"n": 734, "t": "existing", "h": "head", "b": "main",
                 "s": "a" * 40}
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "aegis-open-prs.json").write_text(
                json.dumps({"format": "AEGIS_PR_SNAPSHOT_V2",
                            "complete": True, "prs": [valid]}), encoding="utf-8")
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=AssertionError("network called")):
                self.assertEqual(ctx.open_prs(quick=True), ([valid], "cache"))

    def test_fresh_preflight_does_not_trust_cached_pr_snapshot(self):
        """A new PR may have appeared after the last cache refresh."""
        import tempfile
        saved = {"n": 734, "t": "existing", "h": "head", "b": "main",
                 "s": "a" * 40}
        with tempfile.TemporaryDirectory() as directory:
            pathlib.Path(directory, "aegis-open-prs.json").write_text(
                json.dumps({"format": "AEGIS_PR_SNAPSHOT_V2",
                            "complete": True, "prs": [saved]}), encoding="utf-8")
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", return_value="") as sh:
                self.assertEqual(ctx.open_prs(quick=False), ([], "unavailable"))
                self.assertTrue(sh.called)

    def test_cache_never_authorizes_new_work(self):
        self.assertEqual(ctx.holon_disposition("cache", "github", [], []),
                         "HOLD_INCOMPLETE_SHARED_STATE")
        self.assertEqual(ctx.holon_disposition("github", "github", [], []),
                         "ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED")

    def test_nonbilling_failed_check_is_not_evidence_that_billing_is_unlocked(self):
        pr = [{"n": 732, "t": "holon", "h": "head", "b": "main",
               "s": "a" * 40}]
        with patch.object(ctx, "sh", side_effect=["114260308704", "[]"]):
            self.assertIsNone(ctx.billing_locked(pr))

    def test_sampled_nonbilling_annotations_cannot_certify_global_ci_health(self):
        pr = [{"n": 732, "t": "holon", "h": "head", "b": "main",
               "s": "a" * 40}]
        with patch.object(ctx, "sh", side_effect=["11\n12\n13", "[]", "[]", "[]"]):
            self.assertIsNone(ctx.billing_locked(pr))

    def test_unavailable_billing_annotations_are_unknown(self):
        pr = [{"n": 735, "t": "task", "h": "head", "b": "main",
               "s": "a" * 40}]
        with patch.object(ctx, "sh", return_value=""):
            self.assertIsNone(ctx.billing_locked(pr))
        with patch.object(ctx, "sh", side_effect=["114260308704", ""]):
            self.assertIsNone(ctx.billing_locked(pr))
        with patch.object(ctx, "sh", side_effect=[
            "114260308704", "The job was not started because your account is locked due to a billing issue."
        ]):
            self.assertIs(ctx.billing_locked(pr), True)

    def test_failed_git_fetch_never_verifies_main(self):
        import subprocess
        failed = subprocess.CompletedProcess(args=["git"], returncode=128,
                                             stdout="", stderr="network unavailable")
        with patch.object(ctx.subprocess, "run", return_value=failed), \
             patch.object(ctx, "sh", return_value="https://github.com/Aegis-Omega/AEGIS-OMEGA.git"):
            self.assertEqual(ctx.verify_main_freshness()["state"], "FETCH_FAILED")

    def test_same_origin_and_fetch_head_sha_verifies_main(self):
        import subprocess
        ok = subprocess.CompletedProcess(args=["git"], returncode=0,
                                         stdout="", stderr="")
        with patch.object(ctx.subprocess, "run", return_value=ok), \
             patch.object(ctx, "sh", side_effect=["https://github.com/Aegis-Omega/AEGIS-OMEGA.git", "a" * 40, "a" * 40, "a" * 40]):
            receipt = ctx.verify_main_freshness()
        self.assertEqual(receipt, {"state": "FRESH", "sha": "a" * 40})

    def test_diverged_or_malformed_local_head_fails_closed(self):
        import subprocess
        ok = subprocess.CompletedProcess(args=["git"], returncode=0,
                                         stdout="", stderr="")
        with patch.object(ctx.subprocess, "run", return_value=ok), \
             patch.object(ctx, "sh", side_effect=["https://github.com/Aegis-Omega/AEGIS-OMEGA.git", "a" * 40, "b" * 40]):
            self.assertEqual(ctx.verify_main_freshness()["state"], "REF_DIVERGED")
        with patch.object(ctx.subprocess, "run", return_value=ok), \
             patch.object(ctx, "sh", side_effect=["https://github.com/Aegis-Omega/AEGIS-OMEGA.git", "a" * 40, ""]):
            self.assertEqual(ctx.verify_main_freshness()["state"], "REF_UNVERIFIED")

    def test_local_git_refs_matching_but_github_main_different_is_hold(self):
        import subprocess
        ok = subprocess.CompletedProcess(args=["git"], returncode=0,
                                         stdout="", stderr="")
        with patch.object(ctx.subprocess, "run", return_value=ok), \
             patch.object(ctx, "sh", side_effect=[
                 "https://github.com/Aegis-Omega/AEGIS-OMEGA.git",
                 "a" * 40, "a" * 40, "b" * 40
             ]) as calls:
            self.assertEqual(ctx.verify_main_freshness(),
                             {"state": "GITHUB_HEAD_DIVERGED", "sha": None})
        self.assertIn("git/ref/heads/main", calls.call_args_list[-1].args[2])

    def test_github_main_lookup_unavailable_cannot_certify_local_main(self):
        import subprocess
        ok = subprocess.CompletedProcess(args=["git"], returncode=0,
                                         stdout="", stderr="")
        with patch.object(ctx.subprocess, "run", return_value=ok), \
             patch.object(ctx, "sh", side_effect=[
                 "https://github.com/Aegis-Omega/AEGIS-OMEGA.git",
                 "a" * 40, "a" * 40, ""
             ]):
            self.assertEqual(ctx.verify_main_freshness(),
                             {"state": "GITHUB_HEAD_UNVERIFIED", "sha": None})

    def test_wrong_repo_origin_does_not_fetch_or_certify_main(self):
        for remote in (
            "https://github.com/attacker/AEGIS-OMEGA.git",
            "git@github.com:untrusted/AEGIS-OMEGA.git",
            "https://github.com.evil.test/Aegis-Omega/AEGIS-OMEGA.git",
            "https://github.com/Aegis-Omega/AEGIS-OMEGA-attacker.git",
            "",
        ):
            with self.subTest(remote=remote), \
                 patch.object(ctx, "sh", return_value=remote), \
                 patch.object(ctx.subprocess, "run",
                              side_effect=AssertionError("untrusted fetch executed")):
                self.assertEqual(
                    ctx.verify_main_freshness(),
                    {"state": "REMOTE_IDENTITY_UNVERIFIED", "sha": None},
                )

    def test_verified_origin_ssh_can_fetch_matching_main(self):
        import subprocess
        ok = subprocess.CompletedProcess(args=["git"], returncode=0,
                                         stdout="", stderr="")
        with patch.object(ctx.subprocess, "run", return_value=ok), \
             patch.object(ctx, "sh", side_effect=[
                 "git@github.com:Aegis-Omega/AEGIS-OMEGA.git",
                 "b" * 40, "b" * 40, "b" * 40
             ]):
            self.assertEqual(ctx.verify_main_freshness(),
                             {"state": "FRESH", "sha": "b" * 40})

    def test_quick_mode_does_not_fetch_or_claim_fresh_head(self):
        with patch.object(ctx.subprocess, "run", side_effect=AssertionError("network prohibited")):
            self.assertEqual(ctx.verify_main_freshness(quick=True),
                             {"state": "UNVERIFIED_QUICK", "sha": None})

    def test_failed_fetch_keeps_stale_sha_only_under_local_main(self):
        out = io.StringIO()
        def git_report(*args, **kwargs):
            if args[:3] == ("git", "log", "-1"):
                return ("deadbee 2026-10-01" if "--format=%h %cs" in args
                        else "1790812800")
            if args[:2] == ("git", "rev-list"):
                return "2"
            return ""
        with patch.object(ctx, "sh", side_effect=git_report), \
             patch.object(ctx, "verify_main_freshness",
                          return_value={"state": "FETCH_FAILED", "sha": None}), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "#734"]), \
             contextlib.redirect_stdout(out):
            ctx.main()
        receipt = json.loads(out.getvalue())
        self.assertIsNone(receipt["main"])
        self.assertIsNone(receipt["main_exact_sha"])
        self.assertIsNone(receipt["main_date"])
        self.assertIsNone(receipt["main_age_days"])
        self.assertIsNone(receipt["behind_main"])
        self.assertEqual(receipt["local_main"], "deadbee")
        self.assertEqual(receipt["local_behind_main"], "2")
        self.assertEqual(receipt["holon_disposition"], "HOLD_UNVERIFIED_MAIN")

    def test_successful_exact_fetch_exposes_verified_main_with_provenance(self):
        out = io.StringIO()
        def git_report(*args, **kwargs):
            if args[:3] == ("git", "log", "-1"):
                return ("aaaaaaa 2026-10-01" if "--format=%h %cs" in args
                        else "1790812800")
            if args[:2] == ("git", "rev-list"):
                return "2"
            return ""
        with patch.object(ctx, "sh", side_effect=git_report), \
             patch.object(ctx, "verify_main_freshness",
                          return_value={"state": "FRESH", "sha": "a" * 40}), \
             patch.object(ctx, "open_prs", return_value=([], "github")), \
             patch.object(ctx, "open_issue_board", return_value=([], "github")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "#734"]), \
             contextlib.redirect_stdout(out):
            ctx.main()
        receipt = json.loads(out.getvalue())
        self.assertEqual(receipt["main"], "aaaaaaa")
        self.assertEqual(receipt["main_exact_sha"], "a" * 40)
        self.assertEqual(receipt["main_date"], "2026-10-01")
        self.assertEqual(receipt["behind_main"], "2")
        self.assertEqual(receipt["local_main"], "aaaaaaa")

    def test_json_does_not_claim_zero_on_disconnected_github(self):
        buf = io.StringIO()
        with patch.object(ctx, "sh", return_value=""), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(ctx, "verify_main_freshness", return_value={"state": "FETCH_FAILED", "sha": None}), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "holon"]):
            with contextlib.redirect_stdout(buf):
                ctx.main()
        obj = json.loads(buf.getvalue())
        self.assertIsNone(obj["open"])
        self.assertIsNone(obj["issue_count"])
        self.assertIsNone(obj["ci_billing_locked"])
        self.assertEqual(obj["holon_disposition"], "HOLD_UNVERIFIED_MAIN")

    def test_human_output_explains_unknown_vs_no_overlap(self):
        buf = io.StringIO()
        with patch.object(ctx, "sh", return_value=""), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(ctx, "verify_main_freshness", return_value={"state": "FETCH_FAILED", "sha": None}), \
             patch.object(sys, "argv", ["agent_context.py", "holon"]):
            with contextlib.redirect_stdout(buf):
                ctx.main()
        text = buf.getvalue()
        self.assertIn("OPEN PR COUNT UNKNOWN", text)
        self.assertIn("ISSUE BOARD UNKNOWN", text)
        self.assertIn("file-path overlap NOT ruled out", text)


if __name__ == "__main__":
    unittest.main()
