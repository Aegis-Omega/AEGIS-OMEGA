#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import TestCase, main

HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "classify-ci-execution.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ci_execution_signature", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load classifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = load_module()


def run_fixture(conclusion: str) -> dict:
    return {
        "id": 35496413154,
        "name": "fixture",
        "conclusion": conclusion,
        "created_at": "2026-09-20T07:16:11Z",
        "head_sha": "a" * 40,
    }


def zero_step_job() -> dict:
    return {
        "id": 106040082285,
        "status": "completed",
        "conclusion": "failure",
        "started_at": "2026-09-20T07:16:11Z",
        "completed_at": "2026-09-20T07:16:13Z",
        "steps": [],
    }


class CIExecutionSignatureTests(TestCase):
    def test_run_conclusion_is_not_execution_authority(self) -> None:
        masked = M.build_signature(run_fixture("success"), zero_step_job(), log_status=404)
        red = M.build_signature(run_fixture("failure"), zero_step_job(), log_status=404)

        self.assertEqual(masked["execution_state"], "NOT_EXECUTED")
        self.assertEqual(red["execution_state"], "NOT_EXECUTED")
        self.assertEqual(masked["outcome"], "NOT_APPLICABLE")
        self.assertEqual(red["outcome"], "NOT_APPLICABLE")
        self.assertEqual(
            masked["execution_signature_sha256"],
            red["execution_signature_sha256"],
        )

    def test_continue_on_error_mask_is_detected(self) -> None:
        result = M.build_signature(run_fixture("success"), zero_step_job(), log_status=404)
        self.assertTrue(result["masked_job_failure"])
        self.assertEqual(result["run_conclusion_semantic_role"], "PROVENANCE_ONLY")
        self.assertEqual(result["observables"]["step_count"], 0)
        self.assertEqual(result["observables"]["queue_delay_ms"], 0)
        self.assertEqual(result["observables"]["log_status"], 404)

    def test_real_executed_success_can_be_pass(self) -> None:
        job = zero_step_job()
        job["conclusion"] = "success"
        job["steps"] = [{"name": "test", "status": "completed", "conclusion": "success"}]
        result = M.build_signature(run_fixture("success"), job, log_status=200)
        self.assertEqual(result["execution_state"], "EXECUTED")
        self.assertEqual(result["outcome"], "PASS")

    def test_real_executed_failure_can_be_fail(self) -> None:
        job = zero_step_job()
        job["steps"] = [{"name": "test", "status": "completed", "conclusion": "failure"}]
        result = M.build_signature(run_fixture("failure"), job, log_status=200)
        self.assertEqual(result["execution_state"], "EXECUTED")
        self.assertEqual(result["outcome"], "FAIL")

    def test_missing_steps_fails_closed_to_unknown(self) -> None:
        job = zero_step_job()
        del job["steps"]
        result = M.build_signature(run_fixture("failure"), job, log_status=404)
        self.assertEqual(result["execution_state"], "UNKNOWN")
        self.assertEqual(result["outcome"], "NOT_APPLICABLE")

    def test_skipped_job_is_not_executed_not_failed(self) -> None:
        job = zero_step_job()
        job["conclusion"] = "skipped"
        result = M.build_signature(run_fixture("success"), job, log_status=None)
        self.assertEqual(result["execution_state"], "NOT_EXECUTED")
        self.assertEqual(result["execution_reason"], "JOB_SKIPPED")
        self.assertEqual(result["outcome"], "NOT_APPLICABLE")

    def test_receipt_is_deterministic(self) -> None:
        a = M.build_signature(run_fixture("success"), zero_step_job(), log_status=404)
        b = M.build_signature(run_fixture("success"), zero_step_job(), log_status=404)
        self.assertEqual(a, b)
        self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])


if __name__ == "__main__":
    main()
