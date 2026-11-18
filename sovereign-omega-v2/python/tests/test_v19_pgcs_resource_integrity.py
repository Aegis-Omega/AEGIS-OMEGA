"""V19 source-bound PGCS resource and append-only ring regressions.

Donor: V15 hardware_config.py and pgcs.py (exact Git blobs).
Preserves V18 CoreMatrix, M1 and checkpoint v2.3.0 unchanged.
"""
import gc
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
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


    def test_swap_sample_has_byte_units_not_pages(self):
        # psutil swap counters already represent bytes.
        probe = pgcs.PGCSController.__new__(pgcs.PGCSController)
        sample = SimpleNamespace(sin=8193, sout=12345)
        with patch.object(pgcs.psutil, "swap_memory", return_value=sample):
            self.assertEqual(probe._read_disk_io(), (8193, 12345))

    def test_swap_sample_failure_cannot_fabricate_no_disk_io(self):
        probe = pgcs.PGCSController.__new__(pgcs.PGCSController)
        with patch.object(pgcs.psutil, "swap_memory",
                          side_effect=OSError("swap counters not readable")):
            with self.assertRaisesRegex(pgcs.PGCSDiskIOUnavailable,
                                        "PGCS_SWAP_COUNTER_UNAVAILABLE"):
                probe._read_disk_io()

    def test_invalid_swap_values_cannot_masquerade_as_zero(self):
        probe = pgcs.PGCSController.__new__(pgcs.PGCSController)
        samples = [(None, 0), (-1, 0), (1.0, 0), (False, 0),
                   (0, True), (0, -7), (2, "1")]
        for sin, sout in samples:
            with self.subTest(sin=sin, sout=sout):
                with patch.object(pgcs.psutil, "swap_memory",
                                  return_value=SimpleNamespace(sin=sin, sout=sout)):
                    with self.assertRaisesRegex(pgcs.PGCSDiskIOUnavailable,
                                                "PGCS_SWAP_COUNTER_INVALID"):
                        probe._read_disk_io()

    def test_missing_baseline_denies_controller_before_ring_allocation(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io",
                          side_effect=pgcs.PGCSDiskIOUnavailable("baseline unavailable")):
            with patch.object(pgcs, "CompressionRingBuffer") as ring:
                with self.assertRaises(pgcs.PGCSDiskIOUnavailable):
                    pgcs.PGCSController()
                ring.assert_not_called()

    def test_swap_counter_regression_is_not_clamped_to_zero(self):
        with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
            with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(100, 80)):
                controller = pgcs.PGCSController()
        try:
            with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(99, 80)):
                with self.assertRaisesRegex(pgcs.PGCSDiskIOUnavailable,
                                            "PGCS_SWAP_COUNTER_REGRESSION"):
                    controller.snapshot(1)
        finally:
            controller.stop()

    def test_verified_zero_delta_only_from_equal_valid_counter_samples(self):
        with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
            with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(100, 80)):
                controller = pgcs.PGCSController()
        try:
            ram = SimpleNamespace(used=20, total=100, percent=20.0)
            with patch.object(pgcs.psutil, "virtual_memory", return_value=ram):
                with patch.object(pgcs.PGCSController, "_read_disk_io",
                                  return_value=(100, 80)):
                    sample = controller.snapshot(2)
                    self.assertEqual((sample.disk_swap_bytes_in,
                                      sample.disk_swap_bytes_out), (0, 0))
                    self.assertTrue(sample.passes_criterion)
                with patch.object(pgcs.PGCSController, "_read_disk_io",
                                  return_value=(100, 82)):
                    increased = controller.snapshot(3)
                    self.assertEqual((increased.disk_swap_bytes_in,
                                      increased.disk_swap_bytes_out), (0, 2))
                    self.assertFalse(increased.passes_criterion)
        finally:
            controller.stop()

    def test_snapshot_sample_failure_propagates_without_pass(self):
        with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
            with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(200, 150)):
                controller = pgcs.PGCSController()
        try:
            ram = SimpleNamespace(used=20, total=100, percent=20.0)
            with patch.object(pgcs.psutil, "virtual_memory", return_value=ram):
                with patch.object(pgcs.PGCSController, "_read_disk_io",
                                  side_effect=pgcs.PGCSDiskIOUnavailable("telemetry unavailable")):
                    with self.assertRaises(pgcs.PGCSDiskIOUnavailable):
                        controller.snapshot(4)
        finally:
            controller.stop()


if __name__ == "__main__":
    unittest.main()
