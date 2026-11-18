"""V19 source-bound PGCS resource and append-only ring regressions.

Donor: V15 hardware_config.py and pgcs.py (exact Git blobs).
Preserves V18 CoreMatrix, M1 and checkpoint v2.3.0 unchanged.
"""
import gc
import threading
from concurrent.futures import ThreadPoolExecutor
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


    def test_ring_double_close_is_idempotent_and_writes_fail_closed(self):
        ring = pgcs.CompressionRingBuffer(capacity_bytes=64)
        self.assertTrue(ring.write_segment(b"first", b"x"))
        ring.close()
        ring.close()
        self.assertTrue(ring._buf.closed)
        with self.assertRaisesRegex(RuntimeError, "PGCS_RING_CLOSED"):
            ring.write_segment(b"after", b"oops")
        self.assertEqual(ring._count, 1)

    def test_concurrent_bounded_appends_preserve_exact_records(self):
        record_size = 8 + 5
        limit = 256
        ring = pgcs.CompressionRingBuffer(capacity_bytes=record_size * limit)
        def write_batch(thread_id):
            accepted = []
            for i in range(128):
                payload = bytes([thread_id]) + i.to_bytes(4, "little")
                if ring.write_segment(payload, payload):
                    accepted.append(payload)
            return accepted
        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                accepted = [item for batch in executor.map(write_batch, range(4))
                            for item in batch]
            self.assertEqual(len(accepted), limit)
            self.assertEqual(ring._count, limit)
            self.assertEqual(ring._write_pos, record_size * limit)
            self.assertEqual(ring._total_written, 5 * limit)
            parsed = []
            ring._buf.seek(0)
            for _ in range(limit):
                self.assertEqual(int.from_bytes(ring._buf.read(4), "little"), 5)
                self.assertEqual(int.from_bytes(ring._buf.read(4), "little"), 5)
                parsed.append(ring._buf.read(5))
            self.assertEqual(set(parsed), set(accepted))
            self.assertEqual(len(set(parsed)), limit)
            self.assertFalse(ring.write_segment(b"x", b"x"))
        finally:
            ring.close()

    def test_repeated_monitor_start_does_not_duplicate_threads(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=64):
                controller = pgcs.PGCSController()
        fake_thread = Mock()
        fake_thread.is_alive.return_value = False
        try:
            with patch.object(pgcs.threading, "Thread", return_value=fake_thread) as create:
                controller.start()
                controller.start()
                create.assert_called_once()
                fake_thread.start.assert_called_once()
            controller.stop()
            controller.stop()
            fake_thread.join.assert_called_once()
            self.assertTrue(controller._ring._buf.closed)
            with self.assertRaisesRegex(RuntimeError, "PGCS_MONITOR_CLOSED"):
                controller.start()
        finally:
            controller.stop()

    def test_monitor_join_timeout_never_frees_live_ring(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=64):
                controller = pgcs.PGCSController()
        fake_thread = Mock()
        fake_thread.is_alive.side_effect = [True, False]
        controller._thread = fake_thread
        with self.assertRaisesRegex(RuntimeError, "PGCS_MONITOR_STOP_TIMEOUT"):
            controller.stop()
        self.assertFalse(controller._ring._buf.closed)
        with self.assertRaisesRegex(RuntimeError, "PGCS_MONITOR_CLOSED"):
            controller.start()
        controller.stop()
        self.assertTrue(controller._ring._buf.closed)
        self.assertEqual(fake_thread.join.call_count, 2)

    def test_monitor_start_exception_clears_running_and_thread_reference(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=64):
                controller = pgcs.PGCSController()
        fake_thread = Mock()
        fake_thread.start.side_effect = OSError("test runner thread denied")
        try:
            with patch.object(pgcs.threading, "Thread", return_value=fake_thread):
                with self.assertRaises(OSError):
                    controller.start()
            self.assertFalse(controller._running)
            self.assertIsNone(controller._thread)
        finally:
            controller.stop()
        self.assertTrue(controller._ring._buf.closed)

    def test_monitor_self_join_refuses_unsafe_ring_close(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=64):
                controller = pgcs.PGCSController()
        controller._thread = threading.current_thread()
        with self.assertRaisesRegex(RuntimeError, "PGCS_MONITOR_SELF_JOIN"):
            controller.stop()
        self.assertFalse(controller._ring._buf.closed)
        controller._thread = None
        controller.stop()
        self.assertTrue(controller._ring._buf.closed)


    def test_monitor_sensor_exception_is_a_recorded_terminal_fault(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
                controller = pgcs.PGCSController()
        sensed = threading.Event()
        def fail_sensor():
            sensed.set()
            raise OSError("virtual memory unavailable")
        try:
            with patch.object(pgcs.psutil, "virtual_memory", side_effect=fail_sensor):
                controller.start()
                self.assertTrue(sensed.wait(2.0))
                controller._thread.join(timeout=2.0)
            self.assertFalse(controller._thread.is_alive())
            self.assertEqual(controller._monitor_fault, "OSError")
            self.assertFalse(controller._running)
            with self.assertRaisesRegex(pgcs.PGCSMonitorUnavailable, "PGCS_MONITOR_FAILED"):
                controller.snapshot(1)
            with self.assertRaisesRegex(RuntimeError, "PGCS_MONITOR_CLOSED"):
                controller.start()
        finally:
            controller.stop()
        self.assertTrue(controller._ring._buf.closed)

    def test_monitor_callback_exception_cannot_be_silent(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(0, 0)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
                controller = pgcs.PGCSController(
                    event_callback=lambda name, info: (_ for _ in ()).throw(
                        RuntimeError("callback unavailable")))
        signaled = threading.Event()
        def pressure():
            signaled.set()
            return SimpleNamespace(percent=99.0)
        try:
            with patch.object(pgcs.psutil, "virtual_memory", side_effect=pressure):
                with patch.object(controller, "_trigger_compression", return_value=1):
                    controller.start()
                    self.assertTrue(signaled.wait(2.0))
                    controller._thread.join(timeout=2.0)
            self.assertFalse(controller._thread.is_alive())
            self.assertEqual(controller._monitor_fault, "RuntimeError")
            with self.assertRaisesRegex(pgcs.PGCSMonitorUnavailable, "PGCS_MONITOR_FAILED"):
                controller.snapshot(1)
        finally:
            controller.stop()

    def test_orderly_stop_cannot_be_passed_as_zero_swap(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(20, 30)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
                controller = pgcs.PGCSController()
        controller.stop()
        with self.assertRaisesRegex(pgcs.PGCSMonitorUnavailable, "PGCS_MONITOR_STOPPED"):
            controller.snapshot(3)

    def test_thread_disappears_without_fault_still_denies_snapshot(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(20, 30)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
                controller = pgcs.PGCSController()
        controller._monitor_started = True
        controller._running = True
        controller._thread = Mock()
        controller._thread.is_alive.return_value = False
        try:
            with self.assertRaisesRegex(pgcs.PGCSMonitorUnavailable, "PGCS_MONITOR_NOT_RUNNING"):
                controller.snapshot(4)
        finally:
            controller._thread = None
            controller.stop()

    def test_fault_during_measurement_cannot_return_previous_pass(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(40, 50)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
                controller = pgcs.PGCSController()
        def fail_during_sample():
            controller._monitor_fault = "RuntimeError"
            return (40, 50)
        try:
            with patch.object(pgcs.psutil, "virtual_memory",
                              return_value=SimpleNamespace(used=4, total=64, percent=6.25)):
                with patch.object(controller, "_read_disk_io", side_effect=fail_during_sample):
                    with self.assertRaisesRegex(pgcs.PGCSMonitorUnavailable, "PGCS_MONITOR_FAILED"):
                        controller.snapshot(5)
        finally:
            controller.stop()

    def test_passive_prestart_snapshot_remains_observable_only(self):
        with patch.object(pgcs.PGCSController, "_read_disk_io", return_value=(40, 50)):
            with patch.object(pgcs, "_observed_ring_capacity", return_value=128):
                controller = pgcs.PGCSController()
        try:
            with patch.object(pgcs.psutil, "virtual_memory",
                              return_value=SimpleNamespace(used=4, total=64, percent=6.25)):
                # Keep synthetic baseline and snapshot counters paired.
                # Never substitute host runner counters for mock values.
                with patch.object(controller, "_read_disk_io", return_value=(40, 50)):
                    sample = controller.snapshot(1)
            self.assertEqual((sample.disk_swap_bytes_in, sample.disk_swap_bytes_out), (0, 0))
            self.assertFalse(controller._monitor_started)
        finally:
            controller.stop()


if __name__ == "__main__":
    unittest.main()
