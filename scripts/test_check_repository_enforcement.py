#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "enforcement", HERE / "check_repository_enforcement.py"
)
assert SPEC and SPEC.loader
enforcement = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = enforcement
SPEC.loader.exec_module(enforcement)

REPO = "Aegis-Omega/AEGIS-OMEGA"
BRANCH = "main"
APP = 15368
CONTEXTS = (
    "aegis / automaton-3",
    "aegis / automaton-2",
    "Body cites current head",
    "aegis / kernel-one",
    "scan-pr / osv-scan",
    "Main branch enforcement",
)
POLICY = enforcement.Policy(
    ruleset_name="AEGIS Main Enforcement",
    required_approving_review_count=0,
    dismiss_stale_reviews_on_push=False,
    require_last_push_approval=False,
    require_code_owner_review=False,
    require_conversation_resolution=True,
    require_extra_approval_for_unattributed_changes=True,
    require_branches_up_to_date=True,
    required_status_check_integration_id=APP,
    required_status_check_contexts=CONTEXTS,
)


def ruleset_inventory():
    return [{
        "id":4242,
        "name":"AEGIS Main Enforcement",
        "target":"branch",
        "source_type":"Repository",
        "source":REPO,
        "enforcement":"active",
    }]


def active_rules(
    bindings=None,
    *,
    strict=True,
    extra_approval=True,
):
    if bindings is None:
        bindings=[(c,APP) for c in CONTEXTS]
    checks=[]
    for context,integration_id in bindings:
        row={"context":context}
        if integration_id is not None:
            row["integration_id"]=integration_id
        checks.append(row)
    return [
        {"type":"deletion","ruleset_id":4242},
        {"type":"non_fast_forward","ruleset_id":4242},
        {"type":"required_signatures","ruleset_id":4242},
        {
            "type":"pull_request","ruleset_id":4242,
            "parameters":{
                "dismiss_stale_reviews_on_push":False,
                "require_code_owner_review":False,
                "require_last_push_approval":False,
                "required_approving_review_count":0,
                "required_review_thread_resolution":True,
                "require_extra_approval_for_unattributed_changes":extra_approval,
            },
        },
        {
            "type":"required_status_checks","ruleset_id":4242,
            "parameters":{
                "required_status_checks":checks,
                "strict_required_status_checks_policy":strict,
            },
        },
    ]


def run_with(rules):
    def fake_get(path, token):
        if path == f"/repos/{REPO}/branches/{BRANCH}":
            return 200, {"protected":True}
        if path == f"/repos/{REPO}/rulesets?per_page=100&targets=branch":
            return 200, ruleset_inventory()
        if path == f"/repos/{REPO}/rules/branches/{BRANCH}?per_page=100":
            return 200, rules
        raise AssertionError(path)
    with patch.object(enforcement,"_get",side_effect=fake_get):
        return enforcement.verify(REPO,BRANCH,"token",POLICY)


class Tests(unittest.TestCase):
    def test_exact_live_contract_passes(self):
        r=run_with(active_rules())
        self.assertTrue(r.ok)
        self.assertTrue(r.required_status_check_bindings_exact)
        self.assertTrue(r.extra_approval_for_unattributed_changes_matches)

    def test_extra_unmodeled_context_fails(self):
        b=[(c,APP) for c in CONTEXTS]+[("unexpected / check",APP)]
        r=run_with(active_rules(b))
        self.assertFalse(r.ok)
        self.assertEqual(
            r.unexpected_required_status_check_bindings,
            (("unexpected / check",APP),),
        )

    def test_missing_automaton3_fails(self):
        b=[(c,APP) for c in CONTEXTS if c!="aegis / automaton-3"]
        r=run_with(active_rules(b))
        self.assertFalse(r.ok)
        self.assertIn(
            ("aegis / automaton-3",APP),
            r.missing_required_status_check_bindings,
        )

    def test_wrong_publisher_fails_exact_binding(self):
        b=[(c,(99999 if c=="aegis / kernel-one" else APP)) for c in CONTEXTS]
        r=run_with(active_rules(b))
        self.assertFalse(r.ok)
        self.assertIn(
            ("aegis / kernel-one",APP),
            r.missing_required_status_check_bindings,
        )
        self.assertIn(
            ("aegis / kernel-one",99999),
            r.unexpected_required_status_check_bindings,
        )

    def test_extra_approval_mismatch_fails(self):
        r=run_with(active_rules(extra_approval=False))
        self.assertFalse(r.ok)
        self.assertFalse(r.extra_approval_for_unattributed_changes_matches)

    def test_non_strict_fails(self):
        r=run_with(active_rules(strict=False))
        self.assertFalse(r.ok)
        self.assertFalse(r.branches_up_to_date_required)


if __name__=="__main__":
    unittest.main(verbosity=2)