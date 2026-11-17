"""OPTIMUS V18 source-bound adaptive memory and HOLON checkpoint contracts.

The donor is V15 adaptive_memory.py, but M1, M2, M3, E4, transition
statistics and checkpoint 2.3.0 are from exact V17 parent.  This test
uses a mocked PGCS controller to avoid starting its independent ring.
"""
import mmap
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core_matrix
from adaptive_memory import MIN_ARENA_BYTES, plan_layout
from ledger_persist import CheckpointError, load_checkpoint, save_checkpoint
from test_m123_contracts_v2 import oracle


class AdaptiveHolonV18(unittest.TestCase):
    def make(self, size=MIN_ARENA_BYTES, observer="0"):
        assert size <= 16 * 1024 * 1024, "test allocation limit"
        layout = plan_layout(size)
        pgcs = SimpleNamespace(
            start=Mock(), stop=Mock(),
            snapshot=lambda seq: SimpleNamespace(passes_criterion=True))
        fake_hardware = SimpleNamespace(platform="mock", is_target_hardware=False)
        with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": observer}):
            with patch.object(core_matrix, "configured_arena_layout", return_value=layout):
                with patch.object(core_matrix, "detect_hardware", return_value=fake_hardware):
                    with patch.object(core_matrix, "PGCSController", return_value=pgcs):
                        matrix = core_matrix.CoreMatrix()
        self.addCleanup(self.close_when_possible, matrix)
        return matrix, pgcs

    @staticmethod
    def close_when_possible(matrix):
        if not getattr(matrix, "_closed", False):
            matrix.close()

    def test_real_mmap_instance_and_40_byte_chain_alignment(self):
        matrix, _ = self.make()
        self.assertIsInstance(matrix._array, mmap.mmap)
        self.assertEqual(matrix._layout.total, MIN_ARENA_BYTES)
        self.assertEqual(len(matrix._m1_region) % 40, 0)
        self.assertEqual(len(matrix._m1_region), matrix._layout.m1_size)
        self.assertEqual(len(matrix._m2_region), matrix._layout.m2_size)
        self.assertEqual(len(matrix._m3_region), matrix._layout.m3_size)
        self.assertEqual(matrix._m1_era_capacity, len(matrix._m1_region) // 40)

    def test_m1_digest_preserved_on_actual_mmap(self):
        matrix, _ = self.make()
        inputs = [bytes([i]) * (i % 7) for i in range(23)]
        for i, payload in enumerate(inputs):
            result = matrix.process_event(payload, (b"\x01" if i % 3 == 0 else b""), b"context")
            self.assertEqual(result["sequence"], i + 1)
            self.assertEqual(result["state_hash"], oracle(inputs)[i].hex())
            self.assertFalse(result["gate_accepted"])
        self.assertEqual(matrix._total_processed, len(inputs))

    def test_checkpoint_23_restart_preserves_chain_and_e4_denial(self):
        matrix, _ = self.make()
        control, _ = self.make()
        for i in range(12):
            data = str(i).encode()
            assert matrix.process_event(data, b"", b"")["state_hash"] == (
                control.process_event(data, b"", b"")["state_hash"])
        with tempfile.TemporaryDirectory() as tmp:
            filename = os.path.join(tmp, "checkpoint.json")
            saved = save_checkpoint(matrix, filename)
            self.assertEqual(saved["checkpoint_version"], "2.3.0")
            target, _ = self.make()
            load_checkpoint(target, filename)
            self.assertEqual(target._sequence, 12)
            for i in range(12, 18):
                data = str(i).encode()
                new = target.process_event(data, b"", b"")
                exact = control.process_event(data, b"", b"")
                self.assertEqual(new["state_hash"], exact["state_hash"])
                self.assertFalse(new["gate_accepted"])

    def test_cross_geometry_checkpoint_is_rejected_without_mutation(self):
        source, _ = self.make()
        source.process_event(b"x", b"\x01", b"")
        target, _ = self.make(MIN_ARENA_BYTES * 2)
        with tempfile.TemporaryDirectory() as tmp:
            filename = os.path.join(tmp, "checkpoint.json")
            save_checkpoint(source, filename)
            before = (target._sequence, bytes(target._m1_region[:40]))
            with self.assertRaisesRegex(CheckpointError, "capacity mismatch"):
                load_checkpoint(target, filename)
            self.assertEqual((target._sequence, bytes(target._m1_region[:40])), before)

    def test_real_observer_does_not_change_m123_or_public_telemetry(self):
        control, _ = self.make(observer="0")
        watched, _ = self.make(observer="1")
        for i, outcome in enumerate([b"", b"\x00", b"\x01", b"", b"\x01"]):
            payload = str(i).encode()
            self.assertEqual(
                control.process_event(payload, outcome, b"z"),
                watched.process_event(payload, outcome, b"z"))
        self.assertEqual(bytes(control._m1_region[:200]), bytes(watched._m1_region[:200]))
        self.assertEqual(control.emit_vcg_telemetry(), watched.emit_vcg_telemetry())
        self.assertNotIn("transition_observer_v14", watched.emit_vcg_telemetry())
        self.assertEqual(watched.transition_analytics_snapshot()["sample_count"], 5)

    def test_stop_is_terminal_and_idempotent(self):
        matrix, pgcs = self.make()
        matrix.start()
        matrix.stop()
        matrix.stop()
        pgcs.start.assert_called_once()
        pgcs.stop.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "CORE_MATRIX_CLOSED"):
            matrix.process_event(b"x", b"\x01", b"")
        with self.assertRaisesRegex(RuntimeError, "CORE_MATRIX_CLOSED"):
            matrix.start()
        matrix.close()
        self.assertTrue(matrix._array.closed)
        matrix.close()
        pgcs.stop.assert_called_once()

    def test_exported_view_prevents_close_and_can_retry(self):
        matrix, pgcs = self.make()
        borrowed = memoryview(matrix._array)[:1]
        try:
            with self.assertRaisesRegex(RuntimeError, "CORE_MATRIX_EXPORTED_VIEW"):
                matrix.close()
            self.assertFalse(matrix._closed)
        finally:
            borrowed.release()
        matrix.close()
        self.assertTrue(matrix._closed)
        pgcs.stop.assert_called_once()

    def test_invalid_verifier_fails_before_m1_mutation(self):
        matrix, _ = self.make()
        prior = bytes(matrix._m1_region[:40])
        with self.assertRaises(ValueError):
            matrix.process_event(b"x", b"\x02", b"")
        self.assertEqual(matrix._sequence, 0)
        self.assertEqual(bytes(matrix._m1_region[:40]), prior)


if __name__ == "__main__":
    unittest.main()
