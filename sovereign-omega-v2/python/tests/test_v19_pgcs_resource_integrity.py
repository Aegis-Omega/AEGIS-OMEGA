"""V19 source-bound PGCS resource and append-only ring regressions.

Donor: V15 hardware_config.py and pgcs.py (exact Git blobs).
Preserves V18 CoreMatrix, M1 and checkpoint v2.3.0 unchanged.
"""
import gc
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hardware_config as hw
import pgcs

MIB = 1024 ** 2


class PGCSResourceCoherenceV19(unittest.TestCase):
    def test_measured_headroom_bounds_ring_policy(self):
        with patch.object(hw, "effective_available_bytes", return_value=128 * MIB):
            self.assertEqual(hw._observed_ring_capacity(), MIB)
        with patch.object(hw, "effective_available_bytes", return_value=16 * MIB):
            self.assertEqual(hw._observed_ring_capacity(), 128 * 1024)

    def test_unknown_budget_uses_structural_minimum_only(self):
        with patch.object(hw, "effective_available_bytes",
                          side_effect=hw.MemoryBudgetError("unavailable")):
            self.assertEqual(hw._observed_ring_capacity(), hw.PAGE_ALIGNMENT)
        self.assertEqual(hw.VRAM_TOTAL_BYTES, 0)

    def test_ring_constructor_reobserves_capacity_per_instance(self):
        with patch.object(pgcs, "_observed_ring_capacity", return_value=128) as budget:
            ring = pgcs.CompressionRingBuffer()
        try:
            budget.assert_called_once_with()
            self.assertEqual(ring._capacity, 128)
            self.assertNotEqual(ring._capacity, 512 * MIB)
        finally:
            ring.close()

    def test_bad_capacity_rejected_prior_to_allocation(self):
        for capacity in (0, -1, True, 3.5, "64", 7, None if False else []):
            with self.subTest(capacity=repr(capacity)):
                with self.assertRaises((TypeError, ValueError)):
                    pgcs.CompressionRingBuffer(capacity)

    def test_append_only_ring_refuses_overwrite(self):
        ring = pgcs.CompressionRingBuffer(capacity_bytes=32)
        try:
            self.assertTrue(ring.write_segment(b"first", b"x" * 16))
            ring._buf.seek(0)
            original = ring._buf.read(24)
            self.assertFalse(ring.write_segment(b"second", b"y" * 4))
            self.assertEqual(ring._count, 1)
            self.assertEqual(ring._write_pos, 24)
            ring._buf.seek(0)
            self.assertEqual(ring._buf.read(24), original)
        finally:
            ring.close()

    def test_pgcs_full_ring_records_rejections_instead_of_forging_continuity(self):
        events = []
        with patch.object(pgcs, "_observed_ring_capacity", return_value=20):
            with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
                controller = pgcs.PGCSController(
                    on_compress=lambda data: data,
                    event_callback=lambda name, info: events.append((name, info)),
                )
        try:
            with patch.object(gc, "collect", return_value=5):
                with patch.object(pgcs.ctypes, "CDLL", return_value=Mock()):
                    self.assertEqual(controller._trigger_compression(), 5)
                    controller._ring._buf.seek(0)
                    first = controller._ring._buf.read(17)
                    self.assertEqual(controller._trigger_compression(), 5)
            self.assertEqual(controller._ring._count, 1)
            self.assertEqual(controller._ring._write_pos, 17)
            controller._ring._buf.seek(0)
            self.assertEqual(controller._ring._buf.read(17), first)
            self.assertEqual(controller._compressions, 2)
            self.assertEqual(controller._bytes_compressed, 9)
            self.assertEqual(controller._ring_marker_rejections, 1)
            self.assertEqual(events, [
                ("PGCS_RING_MARKER_REJECTED", {"rejections": 1})
            ])
        finally:
            controller.stop()

    def test_unknown_gpu_is_not_fabricated(self):
        with patch.object(hw.os, "popen", return_value=Mock(read=Mock(return_value="{}"))):
            self.assertEqual(hw._detect_vram_userspace(), 0)


if __name__ == "__main__":
    unittest.main()
