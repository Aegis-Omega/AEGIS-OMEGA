"""Source-bound fail-closed tests for epoch-failsafe recovery reset.

Uses the real production controller. No network, hardware, secrets or mock
authorization. This does not prove recovery authorization or concurrency safety.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from epoch_failsafe import EpochFailsafeController, EpochState


class RecoveryResetFailClosedV1(unittest.TestCase):
    def test_reset_is_safe_for_active_partial_failures(self):
        f = EpochFailsafeController()
        f.report_agent_failure("En", "transient", 1)
        f.report_agent_failure("En", "transient", 2)
        self.assertEqual(f.state, EpochState.ACTIVE)
        self.assertEqual(f._consecutive_failures, 2)
        self.assertIsNone(f.reset_after_recovery())
        self.assertEqual(f.state, EpochState.ACTIVE)
        self.assertEqual(f._consecutive_failures, 0)

    def test_unverified_quarantine_reset_is_denied(self):
        f = EpochFailsafeController()
        with f._lock:
            f._state = EpochState.QUARANTINE
            f._consecutive_failures = 2
        before = f.export_checkpoint()
        self.assertIsNone(f.reset_after_recovery())
        self.assertEqual(f.export_checkpoint(), before)
        self.assertEqual(f.state, EpochState.QUARANTINE)

    def test_real_recovering_state_is_not_released(self):
        f = EpochFailsafeController()
        f.set_epoch_snapshot(1, b"known-buffer", 1, 1, 1)
        for n in range(3):
            f.report_agent_failure("En", "crash-loop", n + 1)
        self.assertEqual(f.state, EpochState.RECOVERING)
        before = f.export_checkpoint()
        self.assertIsNone(f.reset_after_recovery())
        self.assertEqual(f.export_checkpoint(), before)
        self.assertEqual(f.state, EpochState.RECOVERING)

    def test_real_frozen_state_is_not_released(self):
        f = EpochFailsafeController()
        for n in range(3):
            f.report_agent_failure("En", "crash-loop", n + 1)
        self.assertEqual(f.state, EpochState.FROZEN)
        before = f.export_checkpoint()
        self.assertIsNone(f.reset_after_recovery())
        self.assertEqual(f.export_checkpoint(), before)
        self.assertEqual(f.corruption_count, 1)

    def test_repeated_reset_never_escapes_quarantine(self):
        f = EpochFailsafeController()
        with f._lock:
            f._state = EpochState.QUARANTINE
            f._consecutive_failures = 1
        for _ in range(20):
            f.reset_after_recovery()
        self.assertEqual(f.state, EpochState.QUARANTINE)
        self.assertEqual(f._consecutive_failures, 1)


if __name__ == "__main__":
    unittest.main()
