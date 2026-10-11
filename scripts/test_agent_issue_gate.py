#!/usr/bin/env python3
"""stdlib-only negative and positive regression tests for the issue gate."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_issue_gate import assess, contract_from_body, Invalid

HEAD = "a" * 40
BODY = '<!-- AEGIS_WORK_V1\n' + json.dumps({
    "schema": "aegis.issue-work.v1",
    "objective": "Add exact-head issue gate to this repository",
    "kind": "code", "authority": "branch_only", "risk": "moderate",
    "scope": ["scripts/agent_issue_gate.py", "scripts/test_agent_issue_gate.py", "docs/**"],
    "forbidden": ["Production deployment", "Changing branch protection"],
    "acceptance": [{"id": "A1", "criterion": "Exact source tests pass", "method": "github_check", "check": "aegis / issue-gate-tests", "app_id": 15368}]
}) + '\n-->'


def good():
    return {"repo": "Aegis-Omega/AEGIS-OMEGA",
            "pr": {"number": 999, "body": "AEGIS-WORK-ISSUE: #888", "base": {"ref": "main"},
                   "head": {"sha": HEAD}, "user": {"login": "builder"}, "draft": False, "state": "open"},
            "issue": {"number": 888, "state": "open", "body": BODY},
            "changed_files": ["scripts/agent_issue_gate.py"], "files_complete": True,
            "check_runs": [{"name": "aegis / issue-gate-tests", "head_sha": HEAD,
                            "status": "completed", "conclusion": "success", "app": {"id": 15368}}],
            "checks_complete": True, "commits": [{"sha": HEAD, "commit": {"verification": {"verified": True}}}],
            "commits_complete": True,
            "reviews": [{"user": {"login": "independent"}, "state": "APPROVED", "commit_id": HEAD}],
            "reviews_complete": True}


class GateTests(unittest.TestCase):
    def test_good_snapshot_never_grants_authority(self):
        x = assess(good())
        self.assertEqual(x["disposition"], "EVIDENCE_COMPLETE_NOT_ADMITTED")
        self.assertEqual(x["authority_effect"], "NONE")

    def fail_gate(self, snapshot, gate):
        x = assess(snapshot)
        self.assertEqual(x["disposition"], "NOT_ADMITTED", x)
        self.assertEqual(next(r for r in x["gates"] if r["gate"] == gate)["result"], "FAIL")

    def test_forged_check_publisher(self):
        x = good(); x["check_runs"][0]["app"]["id"] = 123456
        self.fail_gate(x, "acceptance:A1")

    def test_high_risk_cannot_autoadmit(self):
        x = good(); x["issue"]["body"] = BODY.replace('"risk": "moderate"', '"risk": "high"')
        self.fail_gate(x, "human_authority_boundary")

    def test_closed_issue(self):
        x = good(); x["issue"]["state"] = "closed"
        self.fail_gate(x, "issue_open")

    def test_unsigned(self):
        x = good(); x["commits"][0]["commit"]["verification"]["verified"] = False
        self.fail_gate(x, "signed_commits")

    def test_stale_check_sha(self):
        x = good(); x["check_runs"][0]["head_sha"] = "b" * 40
        self.fail_gate(x, "acceptance:A1")

    def test_check_failure(self):
        x = good(); x["check_runs"][0]["conclusion"] = "failure"
        self.fail_gate(x, "acceptance:A1")

    def test_check_unexecuted(self):
        x = good(); x["check_runs"][0]["status"] = "queued"
        self.fail_gate(x, "acceptance:A1")

    def test_incomplete_checks(self):
        x = good(); x["checks_complete"] = False
        self.fail_gate(x, "check_snapshot")

    def test_reviewer_same_account(self):
        x = good(); x["reviews"][0]["user"]["login"] = "builder"
        self.fail_gate(x, "independent_identity_review")

    def test_stale_review(self):
        x = good(); x["reviews"][0]["commit_id"] = "c" * 40
        self.fail_gate(x, "independent_identity_review")

    def test_revoked_approval(self):
        x = good(); x["reviews"].append({"user": {"login": "independent"},
                                         "state": "CHANGES_REQUESTED", "commit_id": HEAD})
        self.fail_gate(x, "independent_identity_review")

    def test_scope_breach(self):
        x = good(); x["changed_files"].append("security/ruleset.json")
        self.fail_gate(x, "declared_scope")

    def test_incomplete_file_pagination(self):
        x = good(); x["files_complete"] = False
        self.fail_gate(x, "declared_scope")

    def test_missing_file_completeness(self):
        x = good(); x.pop("files_complete")
        self.fail_gate(x, "declared_scope")

    def test_closed_pr(self):
        x = good(); x["pr"]["state"] = "closed"
        self.fail_gate(x, "pr_open")

    def test_unsigned_middle_commit(self):
        x = good(); x["commits"] = [{"sha": "b" * 40, "commit": {"verification": {"verified": False}}}, x["commits"][0]]
        self.fail_gate(x, "signed_commits")

    def test_incomplete_commit_pagination(self):
        x = good(); x["commits_complete"] = False
        self.fail_gate(x, "signed_commits")

    def test_dismissed_review(self):
        x = good(); x["reviews"].append({"user": {"login": "independent"},
                                           "state": "DISMISSED", "commit_id": HEAD})
        self.fail_gate(x, "independent_identity_review")

    def test_stacked_branch(self):
        x = good(); x["pr"]["base"]["ref"] = "feat/old"
        self.fail_gate(x, "base_branch")

    def test_mismatched_issue(self):
        x = good(); x["pr"]["body"] = "AEGIS-WORK-ISSUE: #887"
        self.fail_gate(x, "issue_binding")

    def test_operator_authority(self):
        x = good(); x["issue"]["body"] = BODY.replace('"authority": "branch_only"', '"authority": "operator_required"')
        self.fail_gate(x, "human_authority_boundary")

    def test_draft(self):
        x = good(); x["pr"]["draft"] = True
        self.fail_gate(x, "non_draft")

    def test_double_contract(self):
        x = good(); x["issue"]["body"] += "\n" + BODY
        self.assertEqual(assess(x)["contract"], "INVALID")

    def test_missing_acceptance(self):
        x = good(); x["issue"]["body"] = BODY.replace('"acceptance": [{', '"acceptance": {')
        self.assertEqual(assess(x)["contract"], "INVALID")

    def test_unknown_domain_method_fail_closed(self):
        x = good(); x["issue"]["body"] = BODY.replace('"method": "github_check", "check": "aegis / issue-gate-tests", "app_id": 15368',
                        '"method": "domain_evidence"')
        self.fail_gate(x, "acceptance:A1")

    def test_no_fake_checks_by_empty_array(self):
        x = good(); x["check_runs"] = []
        self.fail_gate(x, "acceptance:A1")

    def test_untrusted_input_not_remote_attestation(self):
        x = assess(good())
        self.assertEqual(x["source"], "caller_supplied_UNTRUSTED")

    def test_no_arbitrary_code_execution_field(self):
        x = good(); x["issue"]["body"] = BODY.replace('"check": "aegis / issue-gate-tests"',
                                                       '"check": "$(touch /tmp/evil)"')
        self.fail_gate(x, "acceptance:A1")

    def test_moving_pr_head_live_api(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        replies = [x["pr"], x["issue"], {"total_count": 1, "check_runs": x["check_runs"]},
                   x["reviews"], x["commits"], [{"filename": x["changed_files"][0]}],
                   {**x["pr"], "head": {"sha": "f" * 40}}, x["issue"]]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies):
            with self.assertRaisesRegex(Invalid, "PR_CHANGED_DURING_SNAPSHOT"):
                live_snapshot(x["repo"], 999, "")

    def test_live_snapshot_is_stable(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        replies = [x["pr"], x["issue"], {"total_count": 1, "check_runs": x["check_runs"]},
                   x["reviews"], x["commits"], [{"filename": x["changed_files"][0]}],
                   x["pr"], x["issue"]]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies):
            snap = live_snapshot(x["repo"], 999, "")
        self.assertTrue(snap["files_complete"])
        self.assertEqual(assess(snap)["disposition"], "EVIDENCE_COMPLETE_NOT_ADMITTED")

    def test_mutating_issue_contract_live_api(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        replies = [x["pr"], x["issue"], {"total_count": 1, "check_runs": x["check_runs"]},
                   x["reviews"], x["commits"], [{"filename": x["changed_files"][0]}],
                   x["pr"], {**x["issue"], "body": x["issue"]["body"] + "tamper"}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies):
            with self.assertRaisesRegex(Invalid, "ISSUE_CHANGED_DURING_SNAPSHOT"):
                live_snapshot(x["repo"], 999, "")


if __name__ == "__main__":
    unittest.main()
