"""V20: fail-closed stress-harness evidence contract.

These bounded tests use mock components and virtual monotonic time. They do
not claim that the 12-hour hardware protocol was run, or that TGCS passed.
"""
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stress_test


@contextmanager
def fake_dependencies(matrix=None, afse_r2=0.99, swap_passes=True):
    sequence = []
    matrix = matrix or Mock()
    matrix.start.side_effect = lambda: sequence.append("start")
    matrix.emit_vcg_telemetry.side_effect = lambda: (
        sequence.append("snapshot") or {"pgcs_passes": swap_passes})
    matrix.stop.side_effect = lambda: sequence.append("stop")
    matrix.process_event.return_value = {"status": "OK"}
    matrix.get_epoch_snapshot.return_value = b""
    calibrator = Mock()
    calibrator.compute_drift_index.return_value = 0
    calibrator.passes_criterion.return_value = True
    failsafe = Mock()
    failsafe.passes_t0_criterion.return_value = True
    afse = Mock()
    afse.get_r2.return_value = afse_r2
    with patch.object(stress_test, "CoreMatrix", return_value=matrix), \
         patch.object(stress_test, "GradientAnchorCalibrator",
                      return_value=calibrator), \
         patch.object(stress_test, "EpochFailsafeController",
                      return_value=failsafe), \
         patch.object(stress_test, "AFSEController", return_value=afse):
        yield matrix, calibrator, failsafe, sequence


class StressAdmissionV20(unittest.TestCase):
    def test_final_telemetry_before_pgcs_terminal_stop(self):
        with fake_dependencies() as (matrix, cal, fail, order):
            outcome = stress_test.run_stress_test(0.0, 0)
        self.assertLess(order.index("snapshot"), order.index("stop"))
        self.assertTrue(matrix.stop.called)
        self.assertFalse(outcome.overall_pass)

    def test_quick_smoke_cannot_count_as_twelve_hour_pgcs_pass(self):
        with fake_dependencies(swap_passes=True):
            outcome = stress_test.run_stress_test(0.0, 0)
        self.assertFalse(outcome.pgcs_passes)
        self.assertFalse(outcome.tgcs_passes)
        self.assertFalse(outcome.epoch_failsafe_passes)
        self.assertFalse(outcome.gradient_anchor_passes)
        self.assertFalse(outcome.overall_pass)
        self.assertIn("HOLD / NOT ADMITTED", outcome.report())

    def test_no_reported_tgcs_without_independent_variance_evidence(self):
        # Even a synthetic full-duration clock and positive subsystem mocks
        # cannot satisfy an unimplemented TGCS variance measurement.
        duration = 12 * 3600.0
        with fake_dependencies() as (matrix, cal, fail, order):
            with patch.object(stress_test.time, "monotonic",
                              side_effect=[100.0, 100.0 + duration + 1,
                                           100.0 + duration + 1]):
                outcome = stress_test.run_stress_test(duration, 1000)
        self.assertTrue(outcome.pgcs_passes)
        self.assertFalse(outcome.tgcs_passes)
        self.assertFalse(outcome.overall_pass)
        self.assertIn("UNVERIFIED", outcome.report())
        cal.passes_criterion.assert_not_called()  # no 100k epochs

    def test_interruption_cannot_be_admitted(self):
        with fake_dependencies() as (matrix, cal, fail, order):
            matrix.process_event.side_effect = KeyboardInterrupt()
            with patch.object(stress_test.time, "monotonic",
                              side_effect=[200.0, 200.0, 200.1]):
                outcome = stress_test.run_stress_test(60.0, 0)
        self.assertFalse(outcome.overall_pass)
        self.assertFalse(outcome.pgcs_passes)
        self.assertTrue(matrix.stop.called)
        self.assertLess(order.index("snapshot"), order.index("stop"))

    def test_snapshot_failure_propagates_without_fabricated_pass(self):
        with fake_dependencies() as (matrix, cal, fail, order):
            matrix.emit_vcg_telemetry.side_effect = RuntimeError("monitor failed")
            with self.assertRaisesRegex(RuntimeError, "monitor failed"):
                stress_test.run_stress_test(0.0, 0)
        self.assertTrue(matrix.stop.called)

    def test_stop_failure_also_prevents_success_receipt(self):
        with fake_dependencies() as (matrix, cal, fail, order):
            matrix.stop.side_effect = RuntimeError("monitor alive")
            with self.assertRaisesRegex(RuntimeError, "monitor alive"):
                stress_test.run_stress_test(0.0, 0)

    def test_partial_epochs_never_call_lowered_calibrator_threshold(self):
        with fake_dependencies() as (matrix, cal, fail, order):
            outcome = stress_test.run_stress_test(0.0, 0)
        cal.passes_criterion.assert_not_called()
        self.assertFalse(outcome.gradient_anchor_passes)

    def test_short_crash_simulations_not_promoted_to_t0(self):
        with fake_dependencies() as (matrix, cal, fail, order):
            outcome = stress_test.run_stress_test(0.0, 1)
        self.assertFalse(outcome.epoch_failsafe_passes)
        self.assertFalse(outcome.overall_pass)
        self.assertTrue(fail.report_agent_failure.called)


if __name__ == "__main__":
    unittest.main()
