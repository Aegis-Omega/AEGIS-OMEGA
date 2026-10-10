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
        data = '{"total":1,"items":[{"n":735,"t":"CI lock","labels":["task","p0"]}]}'
        with patch.object(ctx, "sh", return_value=data) as call:
            issues, status = ctx.open_issue_board()
            self.assertEqual((len(issues), status), (1, "github"))
            args = call.call_args.args
            self.assertEqual(args[:2], ("gh", "api"))
            self.assertIn("is%3Aissue", args[2])
        with patch.object(ctx, "sh", return_value=""):
            self.assertEqual(ctx.open_issue_board(), ([], "unavailable"))
        with patch.object(ctx, "sh", return_value='{"total":101,"items":[]}'):
            self.assertEqual(ctx.open_issue_board(), ([], "partial"))
        with patch.object(ctx, "sh", return_value='{"total":1,"items":[{"n":"bad"}]}'):
            self.assertEqual(ctx.open_issue_board(), ([], "unavailable"))

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
