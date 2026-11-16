"""Source-bound opt-in integration test. Executes actual CoreMatrix class AST.

The real CoreMatrix allocates a 4 GiB arena on normal construction. This test
compiles the exact CoreMatrix class from the checked-out source and supplies
fake hardware collaborators with a 64 KiB region. It never imports core_matrix
with a real production arena or changes the runtime gate semantics.
"""
import ast
import hashlib
import os
import sys
import threading
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transition_observer import TransitionObserver
from transition_info import TransitionStats, entropy_rate_q16, adjacent_mi_q16


class FakeEpoch(Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    RECOVERING = "recovering"


class FakePGCS:
    def __init__(self, **kwargs):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def snapshot(self, seq):
        return SimpleNamespace(passes_criterion=True)


class FakeFailsafe:
    def __init__(self, **kwargs):
        self.state = FakeEpoch.ACTIVE
        self.corruption_count = 0


class FakeCalibrator:
    def __init__(self, *args):
        self.epochs = []

    def get_w_scale(self, _name):
        return 65536

    def compute_drift_index(self):
        return 0

    def passes_criterion(self, n):
        return n == 100_000

    def calibrate_epoch(self, e):
        self.epochs.append(e)


def run_core_class():
    source = (ROOT / "core_matrix.py").read_text(encoding="utf-8")
    syntax = ast.parse(source, filename="core_matrix.py")
    core = next(n for n in syntax.body if isinstance(n, ast.ClassDef) and n.name == "CoreMatrix")
    # Only production class code is compiled; all collaborators are fake.
    compiled = compile(ast.Module(body=[core], type_ignores=[]), "core_matrix.py", "exec")
    def m1(_buf, payload, seq):
        return seq + 1, hashlib.sha256(payload).digest()
    def m2(_buf, verifier, confidence, sequence=0):
        verdict = bool(verifier and verifier[0])
        return 0, 65536 if verdict else 0
    def m3(_buf, context, w_scale):
        return context, 0
    env = {
        "__name__": "aegis_test_source_bound_core",
        "Optional": Optional, "Callable": Callable, "Dict": Dict,
        "os": os, "threading": threading, "EpochState": FakeEpoch,
        "RAM_TOTAL_BYTES": 65536, "ARRAY_TOTAL_BYTES": 65536,
        "M1_OFFSET": 0, "M1_SIZE": 32768, "M2_OFFSET": 32768, "M2_SIZE": 16384,
        "M3_OFFSET": 49152, "M3_SIZE": 16384,
        "PGCSController": FakePGCS, "EpochFailsafeController": FakeFailsafe,
        "GradientAnchorCalibrator": FakeCalibrator, "DEFAULT_ANCHOR_TOKENS": [],
        "detect_hardware": lambda: SimpleNamespace(platform="test", is_target_hardware=False),
        "INT_SCALE": 65536, "from_fixed": lambda n: n/65536,
        "M1": m1, "M2": m2, "M3": m3,
    }
    exec(compiled, env)
    return env["CoreMatrix"]


class CoreObserverIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Core = run_core_class()

    def test_off_by_default_no_telemetry_contract_change(self):
        with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": "0"}):
            core = self.Core()
        self.assertIsNone(core._transition_observer)
        self.assertTrue(core.process_event(b"payload", b"\x01", b"ctx")["gate_accepted"])
        self.assertFalse(core.process_event(b"payload", b"\x00", b"ctx")["gate_accepted"])
        self.assertFalse(core.process_event(b"payload", b"", b"ctx")["gate_accepted"])
        self.assertNotIn("transition_observer_v14", core.emit_vcg_telemetry())
        self.assertEqual(core._total_processed, 3)

    def test_on_observes_only_verifier_outcomes(self):
        with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": "1"}):
            core = self.Core()
        choices = [b"", b"\x00", b"\x01", b"\x01", b"\x00", b"", b"\xff"]
        decisions = []
        for candidate in choices:
            decisions.append(core.process_event(b"ignored", candidate, b"ctx")["gate_accepted"])
        self.assertEqual(decisions, [False, False, True, True, False, False, True])
        summary = core.emit_vcg_telemetry()["transition_observer_v14"]
        symbols = [TransitionObserver.symbol(v) for v in choices]
        expected = TransitionStats.from_iterable(symbols, 3)
        self.assertEqual(summary["sample_count"], len(choices))
        self.assertEqual(summary["transition_count"], len(choices)-1)
        self.assertEqual(summary["entropy_rate_q16"], entropy_rate_q16(expected))
        self.assertEqual(summary["adjacent_mi_q16"], adjacent_mi_q16(expected))
        self.assertEqual(summary["observation_errors"], 0)
        self.assertNotIn("ignored", str(summary))

    def test_failed_observation_does_not_affect_gate(self):
        with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": "1"}):
            core = self.Core()
        class Broken:
            def observe_verifier(self, _x):
                raise RuntimeError("simulated observer failure")
            def snapshot(self):
                raise RuntimeError("simulated metric failure")
        core._transition_observer = Broken()
        result = core.process_event(b"x", b"\x01", b"y")
        self.assertEqual(result["status"], "OK")
        self.assertTrue(result["gate_accepted"])
        self.assertEqual(core._transition_observer_errors, 1)
        observed = core.emit_vcg_telemetry()["transition_observer_v14"]
        self.assertEqual(observed["status"], "UNAVAILABLE")
        self.assertEqual(observed["observation_errors"], 2)

    def test_frozen_returns_early_without_observation(self):
        with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": "1"}):
            core = self.Core()
        core._failsafe.state = FakeEpoch.FROZEN
        self.assertEqual(core.process_event(b"x", b"\x01", b"z"), {"status": "FROZEN", "sequence": 0})
        self.assertEqual(core.emit_vcg_telemetry()["transition_observer_v14"]["sample_count"], 0)

    def test_only_exact_flag_enables_and_no_raw_history(self):
        for flag in ("false", "TRUE", "", "2"):
            with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": flag}):
                self.assertIsNone(self.Core()._transition_observer)
        with patch.dict(os.environ, {"AEGIS_TRANSITION_OBSERVER": "1"}):
            core = self.Core()
        for n in range(2500):
            core.process_event(b"data", [b"", b"\x00", b"\x01"][n%3], b"context")
        self.assertEqual(core.emit_vcg_telemetry()["transition_observer_v14"]["sample_count"], 2500)
        self.assertLessEqual(len(core._transition_observer._stats.edges), 9)
        self.assertFalse(hasattr(core._transition_observer, "_history"))
        self.assertEqual(core._total_processed, 2500)


if __name__ == "__main__":
    unittest.main()
