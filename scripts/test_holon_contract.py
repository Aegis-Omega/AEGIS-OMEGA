import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from holon_contract import VERSION, assess, canonical_hash, main


def task(domain="engineering", mode="contribute", issue=734, **extra):
    t={"schema": VERSION,"id":"task-734","operator_goal":"Create evidence-backed portable collective workflow",
       "domain":domain,"mode":mode,"issue":issue,
       "acceptance":[{"id":"a1","criterion":"Receipt is machine-readable and fail-closed"}]}
    t.update(extra)
    return t


def state(labels=None, **other):
    s={"main_freshness":{"state":"FRESH","sha":"a"*40},"source":"github",
       "issue_source":"github","ci_billing_locked":False,
       "holon_disposition":"ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED",
       "issue_matches":[{"number":734,"title":"Holon","labels":labels or ["task"]}],"overlaps":[]}
    s.update(other)
    return s


class HolonContractTests(unittest.TestCase):
    def test_ready_means_review_not_authorization(self):
        r=assess(task(),state())
        self.assertEqual((r["disposition"],r["admission"],r["authorization"]),
                         ("READY_FOR_ASSIGNMENT_REVIEW","NOT_ADMITTED","NOT_VERIFIED"))
        self.assertEqual(r["accepted_evidence_count"],0)

    def test_any_domain_uses_same_contract(self):
        for domain in ("engineering","research","design","operations","writing","general"):
            self.assertEqual(assess(task(domain),state())["disposition"],"READY_FOR_ASSIGNMENT_REVIEW")

    def test_inspect_works_offline_but_cannot_write(self):
        r=assess(task(mode="inspect",issue=None),{})
        self.assertEqual(r["disposition"],"READ_ONLY_INSPECTION")
        self.assertEqual(r["admission"],"NOT_ADMITTED")

    def test_missing_main_sha(self):
        r=assess(task(),state(main_freshness={"state":"FRESH","sha":"not-a-sha"}))
        self.assertIn("MAIN_EXACT_HEAD_NOT_VERIFIED",r["blockers"])

    def test_upstream_hold_is_not_ready_even_if_individual_fields_look_good(self):
        for disposition in (
            "HOLD_INCOMPLETE_SHARED_STATE", "HOLD_UNVERIFIED_MAIN",
            "OPERATOR_ACTION_REQUIRED", "HOLD_CLAIMED_WORK_COORDINATE",
            "REVIEW_EXISTING_PR_FIRST",
        ):
            with self.subTest(disposition=disposition):
                result = assess(task(), state(holon_disposition=disposition))
                self.assertEqual(result["disposition"], "HOLD")
                self.assertIn("UPSTREAM_COORDINATION_NOT_CLEAR", result["blockers"])
                self.assertEqual(result["authorization"], "NOT_VERIFIED")

    def test_missing_unknown_or_malformed_upstream_disposition_holds(self):
        for value in (None, "", "READY", 1, True, [], {}):
            with self.subTest(value=value):
                result = assess(task(), state(holon_disposition=value))
                self.assertEqual(result["disposition"], "HOLD")
                self.assertIn("UPSTREAM_COORDINATION_NOT_CLEAR", result["blockers"])
        data = state()
        del data["holon_disposition"]
        result = assess(task(), data)
        self.assertEqual(result["disposition"], "HOLD")

    def test_legitimate_assignment_review_remains_non_authorizing(self):
        result = assess(task(), state(holon_disposition="ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED"))
        self.assertEqual(result["disposition"], "READY_FOR_ASSIGNMENT_REVIEW")
        self.assertEqual(result["admission"], "NOT_ADMITTED")
        self.assertEqual(result["authorization"], "NOT_VERIFIED")

    def test_stale_or_quick_main(self):
        for status in ("UNVERIFIED_QUICK","FETCH_FAILED","REF_DIVERGED","STALE"):
            r=assess(task(),state(main_freshness={"state":status,"sha":"a"*40}))
            self.assertEqual(r["disposition"],"HOLD")

    def test_cached_prs_are_not_current(self):
        r=assess(task(),state(source="cache"))
        self.assertIn("PR_INVENTORY_NOT_VERIFIED",r["blockers"])

    def test_partial_issue_board_is_not_current(self):
        r=assess(task(),state(issue_source="partial"))
        self.assertIn("ISSUE_BOARD_NOT_VERIFIED",r["blockers"])

    def test_does_not_hide_multiple_independent_blockers(self):
        r=assess(task(mode="release"),state(labels=["claimed","needs-operator"],source="partial",ci_billing_locked=None,overlaps=[{"pr":732}]))
        for b in ("PR_INVENTORY_NOT_VERIFIED","CI_HEALTH_NOT_VERIFIED","OPERATOR_ACTION_REQUIRED",
                  "EXISTING_CLAIM_REQUIRES_COORDINATION","EXISTING_PR_REQUIRES_REVIEW",
                  "RELEASE_REQUIRES_EXTERNAL_OPERATOR_ADMISSION"):
            self.assertIn(b,r["blockers"])
        self.assertEqual(r["admission"],"NOT_ADMITTED")

    def test_claimed_issue_is_not_open_assignment(self):
        self.assertIn("EXISTING_CLAIM_REQUIRES_COORDINATION",assess(task(),state(labels=["claimed"]))["blockers"])

    def test_operator_required_not_defeated_by_fresh_state(self):
        self.assertIn("OPERATOR_ACTION_REQUIRED",assess(task(),state(labels=["needs-operator"]))["blockers"])

    def test_missing_issue_match(self):
        r=assess(task(),state(issue_matches=[]))
        self.assertIn("TASK_ISSUE_NOT_RESOLVED",r["blockers"])

    def test_duplicate_issue_matches(self):
        hit={"number":734,"labels":["task"]}
        self.assertIn("TASK_ISSUE_NOT_RESOLVED",assess(task(),state(issue_matches=[hit,hit]))["blockers"])

    def test_malformed_labels_hold(self):
        r=assess(task(),state(issue_matches=[{"number":734,"labels":None}]))
        self.assertIn("ISSUE_LABELS_NOT_VERIFIED",r["blockers"])

    def test_missing_overlap_list_hold(self):
        self.assertIn("PR_OVERLAPS_UNAVAILABLE",assess(task(),state(overlaps=None))["blockers"])

    def test_dependencies_cannot_be_assumed(self):
        self.assertIn("DEPENDENCY_EVIDENCE_NOT_VERIFIED",assess(task(dependencies=["task-1"]),state())["blockers"])

    def test_cyclic_dependency_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(dependencies=["task-734"]),state())

    def test_duplicate_criterion_is_rejected(self):
        t=task();t["acceptance"].append(dict(t["acceptance"][0]))
        with self.assertRaises(ValueError):assess(t,state())

    def test_no_criteria_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(acceptance=[]),state())

    def test_no_goal_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(operator_goal="  "),state())

    def test_no_issue_for_mutation_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(issue=None),state())

    def test_arbitrary_new_domains_supported(self):
        for d in ("genomics", "fluid-dynamics", "medicine", "architecture", "finance", "astronomy"):
            self.assertEqual(assess(task(domain=d), state())["disposition"], "READY_FOR_ASSIGNMENT_REVIEW")

    def test_unknown_fields_fail_closed(self):
        with self.assertRaises(ValueError):assess(task(authorized=True),state())

    def test_empty_domain_fail_closed(self):
        with self.assertRaises(ValueError):assess(task(domain=" "),state())

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"task.json";b=Path(td)/"context.json"
            a.write_text('{"schema":"bad","schema":"aegis.holon.task/1"}',encoding="utf8")
            b.write_text(json.dumps(state()),encoding="utf8")
            out=io.StringIO()
            with contextlib.redirect_stdout(out):code=main([str(a),str(b),"--json"])
        self.assertEqual(code,2)
        self.assertIn("duplicate JSON key",json.loads(out.getvalue())["error"])

    def test_bool_issue_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(issue=True),state())

    def test_unknown_schema_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(schema="newest/unknown"),state())

    def test_self_asserted_operator_approval_is_rejected(self):
        with self.assertRaises(ValueError):assess(task(operator_approval=True),state())

    def test_ignores_malicious_unverified_context_approval(self):
        r=assess(task(),state(approved=True,verified=True,model="GPT-99 Superintelligence"))
        self.assertEqual(r["authorization"],"NOT_VERIFIED")

    def test_readiness_digest_is_order_stable(self):
        t=task();u=dict(reversed(list(t.items())))
        self.assertEqual(canonical_hash(t),canonical_hash(u))

    def test_cli_json_ready_structural_only(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"task.json";b=Path(td)/"context.json"
            a.write_text(json.dumps(task()),encoding="utf8");b.write_text(json.dumps(state()),encoding="utf8")
            out=io.StringIO()
            with contextlib.redirect_stdout(out):code=main([str(a),str(b),"--json"])
        obj=json.loads(out.getvalue())
        self.assertEqual(code,0)
        self.assertEqual(obj["admission"],"NOT_ADMITTED")

    def test_cli_exit_nonzero_when_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"task.json";b=Path(td)/"context.json"
            a.write_text(json.dumps(task()),encoding="utf8");b.write_text(json.dumps(state(source="cache")),encoding="utf8")
            with contextlib.redirect_stdout(io.StringIO()):code=main([str(a),str(b)])
        self.assertEqual(code,2)

    def test_cli_rejects_nan(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"task.json";b=Path(td)/"context.json"
            a.write_text('{"invalid":NaN}',encoding="utf8");b.write_text(json.dumps(state()),encoding="utf8")
            out=io.StringIO()
            with contextlib.redirect_stdout(out):code=main([str(a),str(b),"--json"])
        self.assertEqual(code,2)
        self.assertIn("INVALID_OR_UNVERIFIED_INPUT",json.loads(out.getvalue())["blockers"])

    def test_readonly_cannot_claim_acceptance(self):
        r=assess(task(mode="inspect",issue=None),{})
        self.assertEqual((r["accepted_evidence_count"],r["claim_truth"]),(0,"NOT_VERIFIED"))


if __name__=="__main__":unittest.main()