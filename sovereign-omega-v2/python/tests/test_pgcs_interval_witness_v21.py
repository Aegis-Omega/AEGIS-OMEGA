"""V21: sampled PGCS window witness, no synthetic hardware attestation.

All tests use deterministic synthetic evidence and prove software gate behavior
only. Real 12-hour host/cgroup swap I/O remains OPEN and cannot be inferred.
"""
import math
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stress_test
from test_stress_admission_v20 import fake_dependencies

TWELVE_HOURS = 12 * 60 * 60


def sample(w, seconds, passes=True):
    w.observe(seconds, {"pgcs_passes": passes})


class PGCSIntervalWitnessV21(unittest.TestCase):
    def test_two_far_apart_zero_swap_samples_are_not_coverage(self):
        w = stress_test.PGCSIntervalWitness()
        sample(w, 0)
        sample(w, TWELVE_HOURS)
        self.assertFalse(w.passes_window(TWELVE_HOURS, TWELVE_HOURS, False))
        self.assertEqual(w.first_rejection, "PGCS_SAMPLE_GAP")
        self.assertEqual(w.max_gap_s, TWELVE_HOURS)

    def test_full_thirty_second_synthetic_schedule_meets_only_sample_gate(self):
        w = stress_test.PGCSIntervalWitness()
        for sec in range(0, TWELVE_HOURS + 1, 30):
            sample(w, sec)
        self.assertEqual(w.sample_count, 1441)
        self.assertEqual(w.max_gap_s, 30)
        self.assertIsNone(w.first_rejection)
        # Synthetic unit-test acceptance is NOT evidence that 12 h of
        # physical hardware activity or TGCS variance has been measured.
        self.assertTrue(w.passes_window(TWELVE_HOURS, TWELVE_HOURS, False))
        self.assertFalse(w.passes_window(TWELVE_HOURS, TWELVE_HOURS, True))

    def test_zero_at_end_cannot_erase_one_failed_intermediate_sample(self):
        w = stress_test.PGCSIntervalWitness()
        sample(w, 0)
        sample(w, 30, False)
        sample(w, 60)
        self.assertEqual(w.first_rejection, "PGCS_SAMPLE_UNVERIFIED")
        self.assertFalse(w.passes_window(TWELVE_HOURS, 60, False))

    def test_unreadable_and_truthy_nonbool_sample_fail_closed(self):
        for invalid in (None, {}, {"pgcs_passes": 1},
                        {"pgcs_passes": "true"}, {"pgcs_passes": False}):
            with self.subTest(value=repr(invalid)):
                w = stress_test.PGCSIntervalWitness()
                w.observe(0, invalid)
                self.assertEqual(w.first_rejection, "PGCS_SAMPLE_UNVERIFIED")

    def test_gap_limit_is_inclusive_at_sixty_seconds(self):
        w = stress_test.PGCSIntervalWitness()
        sample(w, 0)
        sample(w, 60)
        self.assertIsNone(w.first_rejection)
        sample(w, 120.01)
        self.assertEqual(w.first_rejection, "PGCS_SAMPLE_GAP")
        self.assertAlmostEqual(w.max_gap_s, 60.01)

    def test_regressing_monotonic_clock_sticky_failure(self):
        w = stress_test.PGCSIntervalWitness()
        sample(w, 0)
        sample(w, 30)
        sample(w, 29)
        self.assertEqual(w.first_rejection, "PGCS_CLOCK_REGRESSION")
        sample(w, 45)
        self.assertEqual(w.first_rejection, "PGCS_CLOCK_REGRESSION")

    def test_missing_initial_sample_never_passes(self):
        w = stress_test.PGCSIntervalWitness()
        for sec in range(30, TWELVE_HOURS + 1, 30):
            sample(w, sec)
        self.assertIsNone(w.first_rejection)
        self.assertFalse(w.passes_window(TWELVE_HOURS, TWELVE_HOURS, False))

    def test_invalid_timestamps_denied(self):
        for value in (float("nan"), float("inf"), -1, "0", None, True):
            with self.subTest(value=repr(value)):
                w = stress_test.PGCSIntervalWitness()
                w.observe(value, {"pgcs_passes": True})
                self.assertEqual(w.first_rejection, "PGCS_INVALID_MONOTONIC_TIME")

    def test_short_or_truncated_window_never_passes(self):
        w = stress_test.PGCSIntervalWitness()
        for sec in range(0, TWELVE_HOURS + 1, 30):
            sample(w, sec)
        self.assertFalse(w.passes_window(60, TWELVE_HOURS, False))
        self.assertFalse(w.passes_window(TWELVE_HOURS, TWELVE_HOURS - 30, False))

    def test_integration_samples_during_run_and_before_stop(self):
        order = []
        with fake_dependencies() as (matrix, calibrator, failsafe, steps):
            # 0 start; 1 loop; 31 loop (30 s sample); 61 deadline;
            # 61 final sample. One mocked positive telemetry per sample.
            with patch.object(stress_test.time, "monotonic",
                              side_effect=[0.0, 1.0, 31.0, 61.0, 61.0]):
                result = stress_test.run_stress_test(60.0, 0)
        self.assertEqual(result.pgcs_sample_count, 3)
        self.assertEqual(result.pgcs_max_sample_gap_s, 31)
        self.assertIsNone(result.pgcs_first_rejection)
        self.assertEqual(steps.count("snapshot"), 3)
        self.assertLess(max(i for i,x in enumerate(steps) if x == "snapshot"),
                        steps.index("stop"))
        self.assertFalse(result.pgcs_passes)
        self.assertFalse(result.overall_pass)

    def test_integration_negative_sample_persists_until_final(self):
        with fake_dependencies() as (matrix, calibrator, failsafe, steps):
            matrix.emit_vcg_telemetry.side_effect = iter([
                {"pgcs_passes": True},
                {"pgcs_passes": False},
                {"pgcs_passes": True},
            ])
            with patch.object(stress_test.time, "monotonic",
                              side_effect=[0.0, 1.0, 31.0, 61.0, 61.0]):
                result = stress_test.run_stress_test(60.0, 0)
        self.assertEqual(result.pgcs_first_rejection, "PGCS_SAMPLE_UNVERIFIED")
        self.assertFalse(result.pgcs_passes)
        self.assertFalse(result.overall_pass)

    def test_integration_missing_gap_denies_evidence(self):
        with fake_dependencies() as (matrix, calibrator, failsafe, steps):
            with patch.object(stress_test.time, "monotonic",
                              side_effect=[0.0, 1.0, 100.0, 100.0]):
                result = stress_test.run_stress_test(80.0, 0)
        self.assertEqual(result.pgcs_first_rejection, "PGCS_SAMPLE_GAP")
        self.assertEqual(result.pgcs_max_sample_gap_s, 100.0)
        self.assertFalse(result.pgcs_passes)
        self.assertFalse(result.overall_pass)


if __name__ == "__main__":
    unittest.main()
