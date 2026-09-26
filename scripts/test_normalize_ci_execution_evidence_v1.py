#!/usr/bin/env python3
import importlib.util
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("normalizer",HERE/"normalize_ci_execution_evidence_v1.py")
assert spec and spec.loader
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
H="1"*40
OLD="2"*40

class Tests(unittest.TestCase):
    def test_provider_failure_zero_steps_is_not_run(self):
        r=m.normalize_github_job(expected_head_sha=H,observed_head_sha=H,steps_count=0,conclusion="failure",runner_id=0)
        self.assertEqual(r.normalized,m.NormalizedExecution.NOT_RUN)

    def test_success_old_head_is_historical(self):
        r=m.normalize_github_job(expected_head_sha=H,observed_head_sha=OLD,steps_count=9,conclusion="success",runner_id=123)
        self.assertEqual(r.normalized,m.NormalizedExecution.HISTORICAL)

    def test_executed_failure_is_failure(self):
        r=m.normalize_github_job(expected_head_sha=H,observed_head_sha=H,steps_count=4,conclusion="failure",runner_id=123)
        self.assertEqual(r.normalized,m.NormalizedExecution.EXECUTED_FAIL)

    def test_executed_success_is_pass(self):
        r=m.normalize_github_job(expected_head_sha=H,observed_head_sha=H,steps_count=4,conclusion="success",runner_id=123)
        self.assertEqual(r.normalized,m.NormalizedExecution.EXECUTED_PASS)

    def test_cancelled_after_steps_is_incomplete(self):
        r=m.normalize_github_job(expected_head_sha=H,observed_head_sha=H,steps_count=2,conclusion="cancelled",runner_id=123)
        self.assertEqual(r.normalized,m.NormalizedExecution.EXECUTED_INCOMPLETE)

    def test_preview_is_transport_only(self):
        r=m.normalize_preview_transport({"state":"READY"},expected_head_sha=H,observed_head_sha=H)
        self.assertEqual(r["normalized"],m.NormalizedExecution.TRANSPORT_ONLY.value)

if __name__=="__main__":
    unittest.main(verbosity=2)