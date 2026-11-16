"""Source-bound adversarial calibration plan/commit tests for AEGIS HOLON.

Uses the real GradientAnchorCalibrator and the existing real-CoreMatrix fixture.
A passing suite means plans are internally consistent under supported APIs,
not that arbitrary writes to private attributes or E4 authority are secure.
"""
import os
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import core_matrix
from gradient_anchor import GradientAnchorCalibrator, DEFAULT_ANCHOR_TOKENS
from hardware_config import INT_SCALE
from test_m123_contracts_v2 import matrix_fixture


class CalibrationPlanIntegrityV1(unittest.TestCase):
    def setUp(self):
        self.calibrator = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)

    def assert_rejected_without_mutation(self, tamper):
        c = self.calibrator
        plan = c.prepare_epoch(1)
        before_scales = dict(c._state.w_scales)
        before_velocities = dict(c._velocities)
        tamper(plan)
        with self.assertRaisesRegex(RuntimeError, "plan modified"):
            c.commit_epoch(plan)
        self.assertEqual(c._state.epoch, 0)
        self.assertEqual(c._state.measurements, [])
        self.assertEqual(c._state.w_scales, before_scales)
        self.assertEqual(c._velocities, before_velocities)

    def test_forged_zero_tolerance_scale_is_denied(self):
        self.assert_rejected_without_mutation(
            lambda plan: plan['scales'].__setitem__('ADVISORY_EXCLUDED', INT_SCALE + 1)
        )

    def test_forged_momentum_velocity_is_denied(self):
        self.assert_rejected_without_mutation(
            lambda plan: plan['velocities'].__setitem__('GATE_ACCEPT_THRESHOLD', 12345)
        )

    def test_forged_drift_sum_is_denied(self):
        self.assert_rejected_without_mutation(
            lambda plan: plan.__setitem__('drift_sum', 1e100)
        )

    def test_forged_measurement_list_is_denied(self):
        self.assert_rejected_without_mutation(
            lambda plan: plan.__setitem__('measurements', [])
        )

    def test_forged_total_adjustments_are_denied(self):
        self.assert_rejected_without_mutation(
            lambda plan: plan.__setitem__('adjustments', 1234)
        )

    def test_unmodified_plan_commits_once_and_cannot_replay(self):
        c = self.calibrator
        canonical = c.prepare_epoch(1)
        measurements = c.commit_epoch(canonical)
        self.assertEqual(c._state.epoch, 1)
        self.assertEqual(len(measurements), len(DEFAULT_ANCHOR_TOKENS))
        with self.assertRaisesRegex(RuntimeError, "changed after epoch"):
            c.commit_epoch(canonical)
        self.assertEqual(c._state.epoch, 1)

    def test_concurrent_calibration_cannot_stale_m1_append(self):
        m = matrix_fixture(4)
        for i in range(99):
            m.process_event(str(i).encode(), b'', b'')
        sequence_before = m._sequence
        self.assertEqual(sequence_before, 99)
        actual_M1 = core_matrix.M1
        started = threading.Event()
        done = threading.Event()
        worker_errors = []
        attempted = threading.Event()
        contender = None

        def concurrent_calibration():
            attempted.set()
            try:
                m._calibrator.calibrate_epoch(1)
                worker_errors.append("concurrent epoch committed")
            except ValueError:
                worker_errors.append("stale epoch refused")
            finally:
                done.set()

        def instrumented_m1(region, payload, sequence):
            nonlocal contender
            if sequence == 99:
                started.set()
                contender = threading.Thread(target=concurrent_calibration, daemon=True)
                contender.start()
                self.assertTrue(attempted.wait(2), 'concurrent contender never started')
                # Under the shared calibration lock, no external calibrator
                # may commit between this event's preparation and M1 append.
                self.assertFalse(done.wait(0.15), 'calibration committed while M1 was held')
            return actual_M1(region, payload, sequence)

        with patch.object(core_matrix, 'M1', side_effect=instrumented_m1):
            result = m.process_event(b'boundary', b'', b'')
        self.assertTrue(started.is_set())
        self.assertEqual(result['status'], 'OK')
        self.assertEqual(m._sequence, 100)
        self.assertEqual(m._total_processed, 100)
        self.assertEqual(m._epoch, 1)
        self.assertEqual(m._calibrator._state.epoch, 1)
        self.assertIsNotNone(contender)
        contender.join(2)
        self.assertFalse(contender.is_alive(), 'calibration lock not released')
        self.assertEqual(worker_errors, ['stale epoch refused'])


if __name__ == '__main__':
    unittest.main()
