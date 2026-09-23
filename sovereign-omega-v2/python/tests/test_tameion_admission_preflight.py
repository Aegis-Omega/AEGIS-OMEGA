#!/usr/bin/env python3
"""Tests for fail-closed Tameion capability admission preflight."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError  # noqa: E402
from harness.sdk.tameion_admission_preflight import (  # noqa: E402
    TameionAdmissionEvidence,
    evaluate_tameion_admission_preflight,
)

COMMIT = "a" * 40
H1 = "1" * 64
H2 = "2" * 64


class TameionAdmissionPreflightTests(TestCase):
    def evidence(self, **changes) -> TameionAdmissionEvidence:
        values = dict(
            schema_version=SCHEMA_VERSION,
            source_commit=COMMIT,
            validated_runs=0,
            openmeter_observation_root=None,
            operator_approval_root=None,
            hosted_replay_executed=False,
            runner_pre_step_failures=2,
        )
        values.update(changes)
        return TameionAdmissionEvidence(**values)

    def test_current_missing_prerequisites_remain_not_admitted(self) -> None:
        result = evaluate_tameion_admission_preflight(self.evidence())
        self.assertEqual(result.outcome, "NOT_ADMITTED")
        self.assertIn("INSUFFICIENT_VALIDATED_RUNS", result.denial_codes)
        self.assertIn("OPENMETER_OBSERVATION_MISSING", result.denial_codes)
        self.assertIn("OPERATOR_APPROVAL_MISSING", result.denial_codes)
        self.assertIn("HOSTED_REPLAY_NOT_EXECUTED", result.denial_codes)
        self.assertIn("RUNNER_PRE_STEP_FAILURE_OBSERVED", result.denial_codes)
        self.assertEqual(result.authority_effect, "NONE")

    def test_three_runs_alone_are_not_enough(self) -> None:
        result = evaluate_tameion_admission_preflight(self.evidence(validated_runs=3))
        self.assertEqual(result.outcome, "NOT_ADMITTED")
        self.assertIn("OPENMETER_OBSERVATION_MISSING", result.denial_codes)
        self.assertIn("OPERATOR_APPROVAL_MISSING", result.denial_codes)

    def test_runner_failures_do_not_count_as_validated_runs(self) -> None:
        result = evaluate_tameion_admission_preflight(
            self.evidence(validated_runs=0, runner_pre_step_failures=99)
        )
        self.assertIn("INSUFFICIENT_VALIDATED_RUNS", result.denial_codes)
        self.assertIn("RUNNER_PRE_STEP_FAILURE_OBSERVED", result.denial_codes)

    def test_complete_prerequisites_only_reach_authority_evaluation(self) -> None:
        result = evaluate_tameion_admission_preflight(
            self.evidence(
                validated_runs=3,
                openmeter_observation_root=H1,
                operator_approval_root=H2,
                hosted_replay_executed=True,
                runner_pre_step_failures=0,
            )
        )
        self.assertEqual(result.outcome, "READY_FOR_AUTHORITY_EVALUATION")
        self.assertEqual(result.denial_codes, ())
        self.assertEqual(result.authority_effect, "NONE")

    def test_preflight_itself_cannot_be_relabelled_as_admitted_authority(self) -> None:
        ready = evaluate_tameion_admission_preflight(
            self.evidence(
                validated_runs=3,
                openmeter_observation_root=H1,
                operator_approval_root=H2,
                hosted_replay_executed=True,
                runner_pre_step_failures=0,
            )
        )
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PREFLIGHT_OUTCOME_INVALID"):
            replace(ready, outcome="ADMITTED").validate()

    def test_preflight_cannot_gain_authority(self) -> None:
        denied = evaluate_tameion_admission_preflight(self.evidence())
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PREFLIGHT_AUTHORITY_EFFECT_INVALID"):
            replace(denied, authority_effect="GRANT").validate()


if __name__ == "__main__":
    main()
