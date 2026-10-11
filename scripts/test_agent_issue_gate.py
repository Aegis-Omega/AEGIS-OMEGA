#!/usr/bin/env python3
"""stdlib-only negative and positive regression tests for the issue gate."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from agent_issue_gate import assess, contract_from_body, contract_digest, Invalid

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
    digest = contract_digest(contract_from_body(BODY))
    proof = "AEGIS-WORK-CONTRACT-SHA256: " + digest
    return {"repo": "Aegis-Omega/AEGIS-OMEGA",
            "pr": {"number": 999, "body": "AEGIS-WORK-ISSUE: #888\n" + proof, "base": {"ref": "main"},
                   "head": {"sha": HEAD}, "user": {"login": "builder", "id": 10}, "draft": False, "state": "open"},
            "issue": {"number": 888, "state": "open", "body": BODY},
            "changed_files": ["scripts/agent_issue_gate.py"], "files_complete": True,
            "check_runs": [{"id": 999, "name": "aegis / issue-gate-tests", "head_sha": HEAD,
                            "status": "completed", "conclusion": "success", "app": {"id": 15368}}],
            "checks_complete": True, "check_origins": {"999": True}, "commits": [{"sha": HEAD, "commit": {"verification": {"verified": True}}}],
            "commits_complete": True,
            "reviews": [{"id": 100, "user": {"login": "independent", "id": 20}, "state": "APPROVED", "commit_id": HEAD, "body": proof}],
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

    def test_missing_contract_pin(self):
        x = good(); x["pr"]["body"] = "AEGIS-WORK-ISSUE: #888"
        self.fail_gate(x, "contract_binding")

    def test_issue_contract_change_after_review(self):
        x = good(); x["issue"]["body"] = BODY.replace('"risk": "moderate"', '"risk": "low"')
        self.fail_gate(x, "contract_binding")

    def test_review_did_not_bind_contract(self):
        x = good(); x["reviews"][0]["body"] = "LGTM"
        self.fail_gate(x, "independent_identity_review")

    def test_duplicate_pr_digest(self):
        x = good(); digest = contract_digest(contract_from_body(BODY))
        x["pr"]["body"] += "\nAEGIS-WORK-CONTRACT-SHA256: " + digest
        self.fail_gate(x, "contract_binding")

    def test_stale_review(self):
        x = good(); x["reviews"][0]["commit_id"] = "c" * 40
        self.fail_gate(x, "independent_identity_review")

    def test_revoked_approval(self):
        x = good(); x["reviews"].append({"id": 200, "user": {"login": "independent", "id": 20},
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
        x = good(); x["reviews"].append({"id": 200, "user": {"login": "independent", "id": 20},
                                           "state": "DISMISSED", "commit_id": HEAD})
        self.fail_gate(x, "independent_identity_review")

    def test_single_segment_wildcard_does_not_escape_subfolder(self):
        x = good()
        x["issue"]["body"] = BODY.replace('"docs/**"', '"scripts/*"')
        x["changed_files"] = ["scripts/private/credentials.py"]
        self.fail_gate(x, "declared_scope")

    def test_recursive_double_star_still_matches(self):
        from agent_issue_gate import scope_path_matches
        self.assertTrue(scope_path_matches("scripts/private/deep/file.py", "scripts/**"))
        self.assertTrue(scope_path_matches("scripts/file.py", "scripts/**"))
        self.assertFalse(scope_path_matches("scripts/../secrets", "scripts/**"))

    def test_review_user_id_is_not_independent(self):
        x = good(); x["reviews"][0]["user"].update({"login": "OtherCase", "id": 10})
        self.fail_gate(x, "independent_identity_review")

    def test_review_account_case_is_not_independent(self):
        x = good(); x["reviews"][0]["user"]["login"] = "BUILDER"
        self.fail_gate(x, "independent_identity_review")

    def test_missing_author_identity_cannot_be_approved(self):
        x = good(); x["pr"]["user"] = {}
        self.fail_gate(x, "independent_identity_review")

    def test_missing_reviewer_identity_cannot_be_approved(self):
        x = good(); x["reviews"][0]["user"].pop("id")
        self.fail_gate(x, "independent_identity_review")

    def test_review_array_reordered_cannot_resurrect_approval(self):
        x = good()
        x["reviews"].insert(0, {"id": 200, "user": {"login": "independent", "id": 20},
                                  "state": "DISMISSED", "commit_id": HEAD})
        self.fail_gate(x, "independent_identity_review")

    def test_malformed_additional_review_blocks(self):
        x = good(); x["reviews"].append({"state": "DISMISSED"})
        self.fail_gate(x, "independent_identity_review")

    def test_comment_only_does_not_revoke_approval(self):
        x = good(); x["reviews"].append({"id": 200, "user": {"login": "independent", "id": 20},
                                          "state": "COMMENTED", "commit_id": HEAD})
        self.fail_gate(x, "independent_identity_review")

    def test_same_app_green_check_without_workflow_origin_fails(self):
        x = good(); x["check_origins"] = {}
        self.fail_gate(x, "acceptance:A1")

    def test_explicit_untrusted_workflow_fails(self):
        x = good(); x["check_origins"]["999"] = False
        self.fail_gate(x, "acceptance:A1")

    def test_origin_verifier_rejects_candidate_modified_workflow(self):
        import unittest.mock
        from agent_issue_gate import _trusted_check_origin
        x = good()
        x["pr"]["base"]["sha"] = "b" * 40
        check = x["check_runs"][0]
        check["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "completed", "conclusion": "success", "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 333, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": [{"name": "Run stdlib falsifiers",
                                               "status": "completed", "conclusion": "success"}]}
        replies = [run, job, {"type": "file", "sha": "c" * 40}, {"type": "file", "sha": "d" * 40}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies):
            self.assertFalse(_trusted_check_origin(x["repo"], x["pr"], check, ""))

    def test_origin_verifier_accepts_unchanged_workflow(self):
        import unittest.mock
        from agent_issue_gate import _trusted_check_origin
        x = good(); x["pr"]["base"]["sha"] = "b" * 40
        check = x["check_runs"][0]
        check["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "completed", "conclusion": "success", "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 333, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": [{"name": "Run stdlib falsifiers",
                                               "status": "completed", "conclusion": "success"}]}
        replies = [run, job, {"type": "file", "sha": "c" * 40}, {"type": "file", "sha": "c" * 40}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies):
            self.assertTrue(_trusted_check_origin(x["repo"], x["pr"], check, ""))

    def test_origin_checker_breaks_old_self_dependency_cycle(self):
        import unittest.mock
        from agent_issue_gate import _trusted_check_origin
        x = good(); x["pr"]["base"]["sha"] = "b" * 40
        c = x["check_runs"][0]
        c["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        # Evidence job can still be failing; a successful independent test job
        # must remain eligible for its OWN acceptance criterion.
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "completed", "conclusion": "failure", "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 333, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": [{"name": "Run stdlib falsifiers",
                                               "status": "completed", "conclusion": "success"}]}
        with unittest.mock.patch("agent_issue_gate._api", side_effect=[
            run, job, {"type": "file", "sha": "c" * 40}, {"type": "file", "sha": "c" * 40}]):
            self.assertTrue(_trusted_check_origin(x["repo"], x["pr"], c, ""))

    def test_running_workflow_can_verify_completed_job_without_deadlock(self):
        import unittest.mock
        from agent_issue_gate import _trusted_check_origin
        x = good(); x["pr"]["base"]["sha"] = "b" * 40
        check = x["check_runs"][0]
        check["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "in_progress", "conclusion": None, "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 333, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": [{"name": "Run stdlib falsifiers",
                                               "status": "completed", "conclusion": "success"}]}
        with unittest.mock.patch("agent_issue_gate._api", side_effect=[
            run, job, {"type": "file", "sha": "c" * 40}, {"type": "file", "sha": "c" * 40}]):
            self.assertTrue(_trusted_check_origin(x["repo"], x["pr"], check, ""))

    def test_origin_checker_requires_real_executed_step(self):
        import unittest.mock
        from agent_issue_gate import _trusted_check_origin
        x = good(); x["pr"]["base"]["sha"] = "b" * 40
        c = x["check_runs"][0]
        c["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "completed", "conclusion": "success", "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 333, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": []}
        with unittest.mock.patch("agent_issue_gate._api", side_effect=[run, job]):
            self.assertFalse(_trusted_check_origin(x["repo"], x["pr"], c, ""))

    def test_origin_checker_requires_same_run_id(self):
        import unittest.mock
        from agent_issue_gate import _trusted_check_origin
        x = good(); x["pr"]["base"]["sha"] = "b" * 40
        c = x["check_runs"][0]
        c["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "completed", "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 334, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": [{"name": "Run stdlib falsifiers",
                                               "status": "completed", "conclusion": "success"}]}
        with unittest.mock.patch("agent_issue_gate._api", side_effect=[run, job]):
            self.assertFalse(_trusted_check_origin(x["repo"], x["pr"], c, ""))

    def test_live_snapshot_rejects_changed_reviews_mid_fetch(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        forged = [{**x["reviews"][0], "state": "DISMISSED"}]
        replies = [x["pr"], x["issue"], {"total_count": 1, "check_runs": x["check_runs"]},
                   x["reviews"], x["commits"], [{"filename": x["changed_files"][0]}],
                   x["pr"], x["issue"], forged, {"total_count": 1, "check_runs": x["check_runs"]}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies), \
             unittest.mock.patch("agent_issue_gate._trusted_check_origin", return_value=True):
            with self.assertRaisesRegex(Invalid, "REVIEWS_CHANGED_DURING_SNAPSHOT"):
                live_snapshot(x["repo"], 999, "")

    def test_live_snapshot_rejects_changed_check_mid_fetch(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        new_checks = {"total_count": 1, "check_runs": [{**x["check_runs"][0], "conclusion": "failure"}]}
        replies = [x["pr"], x["issue"], {"total_count": 1, "check_runs": x["check_runs"]},
                   x["reviews"], x["commits"], [{"filename": x["changed_files"][0]}],
                   x["pr"], x["issue"], x["reviews"], new_checks]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies), \
             unittest.mock.patch("agent_issue_gate._trusted_check_origin", return_value=True):
            with self.assertRaisesRegex(Invalid, "CHECKS_CHANGED_DURING_SNAPSHOT"):
                live_snapshot(x["repo"], 999, "")

    def test_workflow_has_read_only_actions_permission(self):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/agent-issue-gate.yml"
        self.assertIn("  actions: read\n", workflow.read_text(encoding="utf-8"))
        self.assertNotIn("  actions: write\n", workflow.read_text(encoding="utf-8"))

    def test_integration_live_snapshot_and_assess(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        x["pr"]["base"]["sha"] = "b" * 40
        x["check_runs"][0]["details_url"] = "https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/333/job/999"
        run = {"path": ".github/workflows/agent-issue-gate.yml", "head_sha": HEAD,
               "status": "completed", "conclusion": "failure", "event": "pull_request", "workflow_id": 22}
        job = {"id": 999, "run_id": 333, "head_sha": HEAD, "status": "completed",
               "conclusion": "success", "steps": [{"name": "Run stdlib falsifiers",
                                               "status": "completed", "conclusion": "success"}]}
        checks = {"total_count": 1, "check_runs": x["check_runs"]}
        files = [{"filename": p} for p in x["changed_files"]]
        responses = [x["pr"], x["issue"], checks, x["reviews"], x["commits"], files,
                     run, job, {"type": "file", "sha": "c"*40}, {"type": "file", "sha": "c"*40},
                     x["pr"], x["issue"], x["reviews"], checks]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=responses) as api:
            snapshot = live_snapshot(x["repo"], 999, "READ_ONLY_TEST_TOKEN")
        self.assertEqual(api.call_count, len(responses))
        self.assertEqual(snapshot["check_origins"], {"999": True})
        self.assertEqual(assess(snapshot)["disposition"], "EVIDENCE_COMPLETE_NOT_ADMITTED")

    def test_origin_verifier_rejects_fake_job_details_url(self):
        from agent_issue_gate import _trusted_check_origin
        x = good(); x["check_runs"][0]["details_url"] = "https://evil.invalid/check/999"
        self.assertFalse(_trusted_check_origin(x["repo"], x["pr"], x["check_runs"][0], ""))

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

    def test_duplicate_json_key_fails_closed(self):
        x = good(); x["issue"]["body"] = BODY.replace('"risk": "moderate"', '"risk": "moderate", "risk": "low"')
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

    def test_offline_snapshot_cli_never_reports_success(self):
        import contextlib
        import io
        import tempfile
        from agent_issue_gate import main
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "forged-success.json"
            path.write_text(json.dumps(good()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as capture:
                exit_code = main(["--snapshot", str(path)])
            result = json.loads(capture.getvalue())
            self.assertEqual(result["disposition"], "OFFLINE_SIMULATION_ONLY")
            self.assertEqual(result["simulated_reducer_disposition"], "EVIDENCE_COMPLETE_NOT_ADMITTED")
            self.assertEqual(result["source"], "caller_supplied_UNTRUSTED")
            self.assertEqual(exit_code, 2)

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
                   {**x["pr"], "head": {"sha": "f" * 40}}, x["issue"], x["reviews"],
                   {"total_count": 1, "check_runs": x["check_runs"]}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies), \
             unittest.mock.patch("agent_issue_gate._trusted_check_origin", return_value=True):
            with self.assertRaisesRegex(Invalid, "PR_CHANGED_DURING_SNAPSHOT"):
                live_snapshot(x["repo"], 999, "")

    def test_live_snapshot_is_stable(self):
        import unittest.mock
        from agent_issue_gate import live_snapshot
        x = good()
        x["pr"]["head"]["repo"] = {"full_name": x["repo"]}
        replies = [x["pr"], x["issue"], {"total_count": 1, "check_runs": x["check_runs"]},
                   x["reviews"], x["commits"], [{"filename": x["changed_files"][0]}],
                   x["pr"], x["issue"], x["reviews"],
                   {"total_count": 1, "check_runs": x["check_runs"]}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies), \
             unittest.mock.patch("agent_issue_gate._trusted_check_origin", return_value=True):
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
                   x["pr"], {**x["issue"], "body": x["issue"]["body"] + "tamper"},
                   x["reviews"], {"total_count": 1, "check_runs": x["check_runs"]}]
        with unittest.mock.patch("agent_issue_gate._api", side_effect=replies), \
             unittest.mock.patch("agent_issue_gate._trusted_check_origin", return_value=True):
            with self.assertRaisesRegex(Invalid, "ISSUE_CHANGED_DURING_SNAPSHOT"):
                live_snapshot(x["repo"], 999, "")


if __name__ == "__main__":
    unittest.main()
