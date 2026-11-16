"""Atomic matrix + calibrator checkpoint tests on the real modules.

Simulates a concurrent standalone calibration call racing with a checkpoint
save or load. The checkpoint should see an indivisible pair of matrix epoch
and calibrator epoch, not a torn combination. Not a security proof.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import ledger_persist
from ledger_persist import load_checkpoint, save_checkpoint
from test_m123_contracts_v2 import matrix_fixture


class CalibrationCheckpointLockIntegrityV1(unittest.TestCase):
    def test_save_cannot_be_torn_by_standalone_calibration(self):
        matrix = matrix_fixture(3)
        matrix.process_event(b"alpha", b"", b"")
        self.assertEqual(matrix._epoch, 0)
        entered = threading.Event()
        finished = threading.Event()
        outcome = []
        concurrent = []
        original = ledger_persist.snapshot_calibration

        def compete():
            entered.set()
            try:
                matrix._calibrator.calibrate_epoch(1)
                outcome.append("committed_after_snapshot")
            except Exception as exc:
                outcome.append(type(exc).__name__)
            finally:
                finished.set()

        def overlap(calibrator):
            t = threading.Thread(target=compete, daemon=True)
            concurrent.append(t)
            t.start()
            self.assertTrue(entered.wait(2), "concurrent calibrator did not start")
            self.assertFalse(finished.wait(0.15),
                             "calibration committed while checkpoint held locks")
            return original(calibrator)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "checkpoint.json")
            with patch.object(ledger_persist, "snapshot_calibration", side_effect=overlap):
                save_checkpoint(matrix, path)
            for t in concurrent:
                t.join(2)
                self.assertFalse(t.is_alive(), "calibration lock leaked")
            self.assertEqual(outcome, ["committed_after_snapshot"])
            with open(path, encoding="utf-8") as handle:
                checkpoint = json.load(handle)
            self.assertEqual(checkpoint["epoch"], 0)
            self.assertEqual(checkpoint["calibration_snapshot"]["epoch"], 0)
            dest = matrix_fixture(3)
            load_checkpoint(dest, path)
            self.assertEqual(dest._epoch, 0)
            self.assertEqual(dest._calibrator._state.epoch, 0)
            self.assertEqual(dest._sequence, 1)

    def test_restore_excludes_interleaved_calibration(self):
        source = matrix_fixture(3)
        source.process_event(b"alpha", b"", b"")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "checkpoint.json")
            save_checkpoint(source, path)
            dest = matrix_fixture(3)
            entered = threading.Event()
            finished = threading.Event()
            outcomes = []
            concurrent = []
            original = ledger_persist.prepare_calibration_restore

            def compete():
                entered.set()
                try:
                    dest._calibrator.calibrate_epoch(1)
                    outcomes.append("committed_after_load")
                except Exception as exc:
                    outcomes.append(type(exc).__name__)
                finally:
                    finished.set()

            def overlap(*args, **kwargs):
                t = threading.Thread(target=compete, daemon=True)
                concurrent.append(t)
                t.start()
                self.assertTrue(entered.wait(2), "concurrent calibrator did not start")
                self.assertFalse(finished.wait(0.15),
                                 "calibration committed during restoration")
                return original(*args, **kwargs)

            with patch.object(ledger_persist, "prepare_calibration_restore", side_effect=overlap):
                load_checkpoint(dest, path)
            for t in concurrent:
                t.join(2)
                self.assertFalse(t.is_alive(), "restore calibration lock leaked")
            self.assertEqual(outcomes, ["committed_after_load"])
            self.assertEqual(dest._sequence, 1)
            self.assertEqual(dest._epoch, 0)
            self.assertEqual(dest._calibrator._state.epoch, 1)

    def test_chain_only_checkpoint_remains_supported(self):
        source = matrix_fixture(3)
        source._calibrator = None
        source._failsafe = None
        source.process_event(b"z", b"", b"")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "checkpoint.json")
            save_checkpoint(source, path)
            dest = matrix_fixture(3)
            dest._calibrator = None
            dest._failsafe = None
            result = load_checkpoint(dest, path)
            self.assertEqual(result["sequence"], 1)
            self.assertEqual(dest._epoch, 0)


if __name__ == "__main__":
    unittest.main()
