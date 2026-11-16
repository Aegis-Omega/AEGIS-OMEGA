"""AEGIS V15: memory budget and arena geometry are resource-driven.

No 4 GiB, 8 GiB, RX 570, or specific computer is a runtime requirement.
"""
import mmap
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adaptive_memory as mem


MIB = 1024**2
GIB = 1024**3


class AdaptiveMemoryTests(unittest.TestCase):
    def test_exact_alignment_and_region_cover(self):
        for size in [4*MIB, 8*MIB, 15*MIB, 64*MIB, 256*MIB, GIB, 4*GIB, 12*GIB]:
            # These are simulated resource fixtures, never assumed hardware.
            size -= size % mem.PAGE_ALIGNMENT
            r = mem.plan_layout(size)
            self.assertEqual((r.m2_offset, r.m3_offset), (r.m1_size, r.m1_size+r.m2_size))
            self.assertEqual(r.total, r.m1_size+r.m2_size+r.m3_size)
            self.assertEqual(r.m1_size % mem.M1_RECORD_BYTES, 0)
            for n in (r.m1_size, r.m2_size, r.m3_size, r.total):
                self.assertEqual(n % mem.PAGE_ALIGNMENT, 0)
                self.assertGreater(n, 0)
            self.assertLess(r.m3_offset, r.total)

    def test_arena_under_host_and_cgroup_constraints(self):
        for available, maximum in [(128*MIB, 4*MIB), (512*MIB, 16*MIB),
                                   (8*GIB, 256*MIB), (64*GIB, 2*GIB)]:
            size = mem.select_arena_bytes(available)
            self.assertEqual(size, maximum)
            self.assertLessEqual(size, available//2)
            self.assertEqual(size%mem.PAGE_ALIGNMENT, 0)

    def test_cgroup_takes_minimum_and_never_silently_ignores_zero(self):
        self.assertEqual(mem.effective_available_bytes(8*GIB, 2*GIB), 2*GIB)
        self.assertEqual(mem.effective_available_bytes(2*GIB, 8*GIB), 2*GIB)
        self.assertEqual(mem.effective_available_bytes(4*GIB, None), 4*GIB)
        for bad in [0, -1, True]:
            with self.assertRaises(mem.MemoryBudgetError):
                mem.effective_available_bytes(2*GIB, bad)
        for bad in [0, -1, False]:
            with self.assertRaises(mem.MemoryBudgetError):
                mem.effective_available_bytes(bad, None)

    def test_bounded_decimal_override(self):
        self.assertEqual(mem.select_arena_bytes(512*MIB, "134217728"), 128*MIB)
        for bad in ["", "-1", "1GB", "1.0", " 1024", None if False else "NaN", True]:
            with self.assertRaises(mem.MemoryBudgetError):
                mem.select_arena_bytes(512*MIB, bad)
        with self.assertRaises(mem.MemoryBudgetError):
            mem.select_arena_bytes(512*MIB, 300*MIB)
        with self.assertRaises(mem.MemoryBudgetError):
            mem.select_arena_bytes(16*MIB, 1*MIB)

    def test_reject_malformed_sizes_before_allocation(self):
        for size in [0, -4*MIB, 1*MIB, 4*MIB+1, 4*MIB-mem.PAGE_ALIGNMENT, True]:
            with self.assertRaises(mem.MemoryBudgetError):
                mem.plan_layout(size)
        with self.assertRaises(mem.MemoryBudgetError):
            mem.select_arena_bytes(8*MIB)

    def test_configured_layout_uses_observed_available_not_host_model(self):
        with patch.dict(os.environ, {"AEGIS_ARRAY_BYTES": ""}, clear=False):
            with patch.object(mem, "effective_available_bytes", return_value=512*MIB):
                with self.assertRaises(mem.MemoryBudgetError):  # empty override is invalid
                    mem.configured_arena_layout()
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(mem, "effective_available_bytes", return_value=512*MIB):
                self.assertEqual(mem.configured_arena_layout().total, 16*MIB)
        with patch.dict(os.environ, {"AEGIS_ARRAY_BYTES": str(64*MIB)}, clear=True):
            with patch.object(mem, "effective_available_bytes", return_value=512*MIB):
                self.assertEqual(mem.configured_arena_layout().total, 64*MIB)

    def test_lazy_mmap_sized_from_protocol_layout(self):
        r = mem.plan_layout(4*MIB)
        with mmap.mmap(-1, r.total) as arena:
            view = memoryview(arena)
            try:
                m1 = view[:r.m1_size]
                m2 = view[r.m2_offset:r.m3_offset]
                m3 = view[r.m3_offset:r.total]
                try:
                    self.assertEqual(len(m1), r.m1_size)
                    self.assertEqual(len(m2), r.m2_size)
                    self.assertEqual(len(m3), r.m3_size)
                    m1[0:40] = bytes(range(40))
                    self.assertEqual(bytes(m1[0:40]), bytes(range(40)))
                finally:
                    m1.release(); m2.release(); m3.release()
            finally:
                view.release()

    def test_virtual_mapping_is_not_a_claim_of_physical_memory_or_gpu(self):
        self.assertNotEqual(mem.plan_layout(4*MIB).total, 4*GIB)
        self.assertEqual(mem.M1_ALIGNMENT, 5*mem.PAGE_ALIGNMENT)
        self.assertEqual(mem.M1_ALIGNMENT % mem.M1_RECORD_BYTES, 0)


if __name__ == "__main__":
    unittest.main()
