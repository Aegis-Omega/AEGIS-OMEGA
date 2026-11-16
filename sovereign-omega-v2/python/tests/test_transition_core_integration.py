"""V14 opt-in CoreMatrix integration: test actual source with small mock hardware.

No runtime PGCS controllers, network, GPU, or 4GB allocation are invoked.
The original CoreMatrix M1/M2/M3/process_event/telemetry functions run unmodified
apart from V14 observational hooks, with mocked hardware subsystem imports.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import TestCase, main, mock
import importlib.util
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class DummyPGCS:
    def __init__(self, event_callback=None):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def snapshot(self, sequence):
        return SimpleNamespace(passes_criterion=True)


class DummyEpochState(Enum):
    ACTIVE = "active"
    RECOVERING = "recovering"
    FROZEN = "frozen"


class DummyFailsafe:
    def __init__(self, event_callback=None):
        self.state = DummyEpochState.ACTIVE
        self.corruption_count = 0


class DummyCalibrator:
    def __init__(self, anchors):
        pass

    def get_w_scale(self, anchor):
        return 65536

    def compute_drift_index(self):
        return 0.0

    def passes_criterion(self, steps):
        return True

    def calibrate_epoch(self, epoch):
        pass


def load_real_core():
    from hardware_config import INT_SCALE
    assert INT_SCALE == 65536
    pgcs = ModuleType("pgcs")
    pgcs.PGCSController = DummyPGCS
    pgcs.PGCSTelemetry = SimpleNamespace
    failsafe = ModuleType("epoch_failsafe")
    failsafe.EpochFailsafeController = DummyFailsafe
    failsafe.EpochState = DummyEpochState
    anchor = ModuleType("gradient_anchor")
    anchor.GradientAnchorCalibrator = DummyCalibrator
    anchor.DEFAULT_ANCHOR_TOKENS = []
    modules = {"pgcs": pgcs, "epoch_failsafe": failsafe, "gradient_anchor": anchor}
    with mock.patch.dict(sys.modules, modules):
        # Resource measurement must NOT happen at import time.
        with mock.patch.dict(os.environ, {"AEGIS_ARRAY_BYTES": "invalid-at-import"}):
            spec = importlib.util.spec_from_file_location("aegis_core_under_test", ROOT / "core_matrix.py")
            core = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(core)
    if hasattr(core, "ARRAY_TOTAL_BYTES"):
        raise AssertionError("IMPORT_TIME_ARENA_LAYOUT_STILL_PRESENT")
    core.detect_hardware = lambda: SimpleNamespace(platform="mock")
    return core


class ObserverCoreIntegration(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_real_core()

    def make_core(self, setting=None):
        with mock.patch.dict(os.environ, {"AEGIS_ARRAY_BYTES": "4194304"}):
            os.environ.pop("AEGIS_TRANSITION_OBSERVER", None)
            if setting is not None:
                os.environ["AEGIS_TRANSITION_OBSERVER"] = setting
            return self.core.CoreMatrix()

    def test_default_off_preserves_original_public_telemetry(self):
        engine = self.make_core()
        self.assertIsNone(engine._transition_observer)
        before = engine.emit_vcg_telemetry()
        self.assertNotIn("transition_observer_v14", before)
        engine.process_event(b"alpha", b"\x01", b"\x01\x02")
        after = engine.emit_vcg_telemetry()
        self.assertNotIn("transition_observer_v14", after)

    def test_non_exact_opt_in_remains_disabled(self):
        for option in ("true", "on", "0", "YES"):
            engine = self.make_core(option)
            self.assertIsNone(engine._transition_observer)

    def test_gate_result_and_all_existing_metrics_identical(self):
        control = self.make_core()
        observed = self.make_core("1")
        results = [b"", b"\x00", b"\x01", b"\xff", b"\x00", b""]
        for i, result in enumerate(results):
            data = (b"payload-" + bytes([i]), result, bytes([i, i + 1]))
            self.assertEqual(control.process_event(*data), observed.process_event(*data))
            before = control.emit_vcg_telemetry()
            after = observed.emit_vcg_telemetry()
            self.assertNotIn("transition_observer_v14", after)
            extra = observed.transition_analytics_snapshot()
            self.assertEqual(before, after)
            self.assertEqual(extra["sample_count"], i + 1)
            self.assertEqual(extra["transition_count"], i)
            self.assertEqual(extra["status"], "PROCESS_LOCAL_NONFORENSIC")
            self.assertEqual(extra["observation_errors"], 0)
        self.assertEqual(control.get_epoch_snapshot(), observed.get_epoch_snapshot())

    def test_failures_do_not_change_governance(self):
        control = self.make_core()
        observed = self.make_core("1")
        observed._transition_observer.observe_verifier = mock.Mock(side_effect=RuntimeError("analytics broken"))
        self.assertEqual(control.process_event(b"x", b"\x01", b"y"),
                         observed.process_event(b"x", b"\x01", b"y"))
        view = observed.transition_analytics_snapshot()
        self.assertEqual(view["sample_count"], 0)
        self.assertEqual(view["observation_errors"], 1)
        observed._transition_observer.snapshot = mock.Mock(side_effect=RuntimeError("unavailable"))
        out = observed.transition_analytics_snapshot()
        self.assertEqual(out["status"], "UNAVAILABLE")
        self.assertEqual(out["observation_errors"], 2)

    def test_frozen_and_recovering_do_not_observe(self):
        engine = self.make_core("1")
        for status in (DummyEpochState.FROZEN, DummyEpochState.RECOVERING):
            engine._failsafe.state = status
            self.assertEqual(engine.process_event(b"x", b"\x01", b"y")["status"], status.name)
        self.assertEqual(engine.transition_analytics_snapshot()["sample_count"], 0)


    def test_independent_instances_remeasure_budget_and_checkpoint_geometry(self):
        # The module is importable without a memory budget; instances must
        # independently resolve their own sizes at construction time.
        import adaptive_memory
        self.assertFalse(hasattr(self.core, "ARRAY_TOTAL_BYTES"))
        instances = []
        try:
            for selected in (4194304, 8388608, 16777216):
                with mock.patch.object(adaptive_memory, "effective_available_bytes",
                                       return_value=512 * 1024**2):
                    with mock.patch.dict(os.environ,
                                         {"AEGIS_ARRAY_BYTES": str(selected)}):
                        matrix = self.core.CoreMatrix()
                instances.append(matrix)
                expected = adaptive_memory.plan_layout(selected)
                self.assertEqual(matrix._layout, expected)
                self.assertEqual(len(matrix._array), selected)
                self.assertEqual(len(matrix._m1_region), expected.m1_size)
                self.assertEqual(len(matrix._m2_region), expected.m2_size)
                self.assertEqual(len(matrix._m3_region), expected.m3_size)
                self.assertEqual(matrix._m1_era_capacity, expected.m1_size // 40)
                self.assertEqual(matrix.process_event(b"x", b"\x01", b"abc")["sequence"], 1)
                self.assertEqual(matrix.get_epoch_snapshot()[-12:-4], (1).to_bytes(8, "little"))
            self.assertEqual([len(x._array) for x in instances],
                             [4194304, 8388608, 16777216])
            self.assertFalse(hasattr(self.core, "ARRAY_TOTAL_BYTES"))
        finally:
            for matrix in instances:
                matrix.close()
                self.assertTrue(matrix._array.closed)

    def test_insufficient_headroom_denies_new_instance_without_mutating_existing(self):
        import adaptive_memory
        with mock.patch.object(adaptive_memory, "effective_available_bytes",
                               return_value=512 * 1024**2):
            with mock.patch.dict(os.environ, {"AEGIS_ARRAY_BYTES": "4194304"}):
                active = self.core.CoreMatrix()
        try:
            self.assertEqual(active.process_event(b"ok", b"\x01", b"c")["sequence"], 1)
            with mock.patch.object(adaptive_memory, "effective_available_bytes",
                                   return_value=6 * 1024**2):
                with mock.patch.dict(os.environ, {"AEGIS_ARRAY_BYTES": "4194304"}):
                    with self.assertRaises(adaptive_memory.MemoryBudgetError):
                        self.core.CoreMatrix()
            self.assertFalse(active._array.closed)
            self.assertEqual(active.process_event(b"ok", b"\x01", b"c")["sequence"], 2)
        finally:
            active.close()


if __name__ == "__main__":
    main()
