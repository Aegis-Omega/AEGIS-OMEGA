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

    def test_pr_second_page_outage_is_partial_not_complete(self):
        """One good page followed by network failure must not clear collisions."""
        import tempfile
        first = [{"n": i + 1, "t": "task", "h": "head",
                  "b": "main", "s": "a" * 40} for i in range(100)]
        with tempfile.TemporaryDirectory() as directory:
            def response(*args, **_kwargs):
                if args[:2] == ("gh", "api") and "page=1" in args[2]:
                    return "\n".join(json.dumps(p) for p in first)
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
                    return ("\n".join(json.dumps(p) for p in first)
                            if "page=1" in args[2] else json.dumps(second))
                return ""
            with patch.object(ctx, "git_dir", return_value=directory), \
                 patch.object(ctx, "sh", side_effect=response):
                entries, source = ctx.open_prs()
        self.assertEqual((len(entries), source), (101, "github"))

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
        self.assertEqual(obj["holon_disposition"], "HOLD_INCOMPLETE_SHARED_STATE")
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

    def test_json_does_not_claim_zero_on_disconnected_github(self):
        buf = io.StringIO()
        with patch.object(ctx, "sh", return_value=""), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "--json", "holon"]):
            with contextlib.redirect_stdout(buf):
                ctx.main()
        obj = json.loads(buf.getvalue())
        self.assertIsNone(obj["open"])
        self.assertIsNone(obj["issue_count"])
        self.assertIsNone(obj["ci_billing_locked"])
        self.assertEqual(obj["holon_disposition"], "HOLD_INCOMPLETE_SHARED_STATE")

    def test_human_output_explains_unknown_vs_no_overlap(self):
        buf = io.StringIO()
        with patch.object(ctx, "sh", return_value=""), \
             patch.object(ctx, "open_prs", return_value=([], "unavailable")), \
             patch.object(ctx, "open_issue_board", return_value=([], "unavailable")), \
             patch.object(ctx, "existing_code", return_value=[]), \
             patch.object(sys, "argv", ["agent_context.py", "holon"]):
            with contextlib.redirect_stdout(buf):
                ctx.main()
        text = buf.getvalue()
        self.assertIn("OPEN PR COUNT UNKNOWN", text)
        self.assertIn("ISSUE BOARD UNKNOWN", text)
        self.assertIn("file-path overlap NOT ruled out", text)


if __name__ == "__main__":
    unittest.main()
