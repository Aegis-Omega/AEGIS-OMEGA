"""Verify the actual run_bridge startup path refuses invalid persisted state.

No CoreMatrix allocation, socket binding, network access or file writes.
Only run_bridge's real AST body is executed with controlled dependencies.
"""
from __future__ import annotations

import ast
import json
import os
import sys
import threading
import unittest
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY_ROOT))
from ledger_persist import CheckpointError


class TinyStartupMatrix:
    def __init__(self, *, ready=True):
        self.ready = ready
        self.started = False
        self.stopped = False
        self._lock = threading.RLock()
        self._epoch = 0

    def start(self):
        self.started = True

    def wait_ready(self, timeout):
        if timeout != 5.0:
            raise AssertionError("Unexpected readiness timeout")
        return self.ready

    def stop(self):
        self.stopped = True


def make_actual_run_bridge(*, has_checkpoint, loader, ready=True):
    tree = ast.parse((PY_ROOT / "bridge.py").read_text(encoding="utf-8"))
    functions = [
        n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "run_bridge"
    ]
    if len(functions) != 1:
        raise AssertionError("Expected exact run_bridge source")
    function = functions[0]
    node = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(node)

    calls = {"bound": 0, "saved": 0, "loaded": 0, "registered": 0, "thread_started": 0,
             "served": 0, "server_closed": 0, "thread_joined": 0}
    matrix = TinyStartupMatrix(ready=ready)

    def maybe_load(target):
        calls["loaded"] += 1
        if target is not matrix:
            raise AssertionError("Restore must target actual matrix")
        return loader(target)

    def bind(address, handler_class):
        calls["bound"] += 1
        class FakeServer:
            def serve_forever(self):
                calls["served"] += 1

            def server_close(self):
                calls["server_closed"] += 1
        return FakeServer()

    class FakeThread:
        def __init__(self, *, target, args, kwargs, name, daemon):
            if name != 'aegis-checkpoint-autosave' or not daemon:
                raise AssertionError("Unexpected worker configuration")
            if args[1] is not matrix:
                raise AssertionError("Worker targets wrong matrix")
            self.target = target
            self.kwargs = kwargs

        def start(self):
            calls["thread_started"] += 1

        def join(self):
            calls["thread_joined"] += 1

    class FakeThreading:
        Thread = FakeThread
        Event = threading.Event

    def save(candidate):
        if candidate is not matrix:
            raise AssertionError("Save targets wrong matrix")
        calls["saved"] += 1
        return {"epoch": matrix._epoch}

    class FakeGate:
        def __init__(self):
            self.sealed = False

        def seal(self):
            self.sealed = True

    gate = FakeGate()

    def register():
        calls["registered"] += 1

    namespace = {
        "os": os,
        "json": json,
        "threading": FakeThreading(),
        "_register_handlers": register,
        "matrix": matrix,
        "checkpoint_exists": lambda: has_checkpoint,
        "load_checkpoint": maybe_load,
        "CheckpointError": CheckpointError,
        "checkpoint_autosave_worker": lambda *_a, **_kw: None,
        "_save_checkpoint_serialized": save,
        "_log_checkpoint_autosave_error": lambda exc: None,
        "HTTPServer": bind,
        "BridgeHandler": object,
        "gate": gate,
    }
    exec(compile(node, str(PY_ROOT / "bridge.py"), "exec"), namespace)
    return namespace["run_bridge"], calls, matrix, gate


class TestBridgeStartupFailClosed(unittest.TestCase):
    def test_unready_matrix_fails_before_restore_bind_or_checkpoint_write(self):
        startup, calls, matrix, _gate = make_actual_run_bridge(
            has_checkpoint=True,
            ready=False,
            loader=lambda _: (_ for _ in ()).throw(
                AssertionError("not-ready matrix must not load checkpoint")
            ),
        )
        with self.assertRaisesRegex(RuntimeError, "BRIDGE_START_NOT_READY"):
            startup(port=7899)
        self.assertTrue(matrix.started)
        self.assertTrue(matrix.stopped)
        self.assertEqual(calls["loaded"], 0)
        self.assertEqual(calls["bound"], 0)
        self.assertEqual(calls["thread_started"], 0)
        self.assertEqual(calls["saved"], 0)
        self.assertEqual(calls["served"], 0)

    def test_bad_checkpoint_never_starts_a_server_or_overwrites_disk(self):
        def corrupt(_):
            raise CheckpointError("INTEGRITY_MISMATCH")

        startup, calls, matrix, _gate = make_actual_run_bridge(
            has_checkpoint=True, loader=corrupt
        )
        with self.assertRaisesRegex(CheckpointError, "CHECKPOINT_RESTORE"):
            startup(port=7899)
        self.assertTrue(matrix.started)
        self.assertTrue(matrix.stopped)
        self.assertEqual(calls["bound"], 0)
        self.assertEqual(calls["thread_started"], 0)
        self.assertEqual(calls["saved"], 0)
        self.assertEqual(calls["served"], 0)
        self.assertEqual(calls["loaded"], 1)

    def test_corrupt_json_or_other_restore_exception_is_not_silently_ignored(self):
        def malformed(_):
            raise ValueError("invalid JSON")

        startup, calls, matrix, _gate = make_actual_run_bridge(
            has_checkpoint=True, loader=malformed
        )
        with self.assertRaisesRegex(CheckpointError, "CHECKPOINT_RESTORE"):
            startup(port=7899)
        self.assertTrue(matrix.stopped)
        self.assertEqual(calls["bound"], 0)
        self.assertEqual(calls["saved"], 0)

    def test_valid_restored_checkpoint_precedes_worker_and_server(self):
        def restore(matrix):
            matrix._epoch = 9
            return {"sequence": 122, "epoch": 9, "era": 0}

        startup, calls, matrix, gate = make_actual_run_bridge(
            has_checkpoint=True, loader=restore
        )
        startup(port=7899)
        self.assertEqual(calls["loaded"], 1)
        self.assertEqual(calls["bound"], 1)
        self.assertEqual(calls["served"], 1)
        self.assertEqual(calls["thread_started"], 1)
        self.assertEqual(calls["thread_joined"], 1)
        self.assertEqual(calls["saved"], 1)
        self.assertEqual(calls["server_closed"], 1)
        self.assertTrue(matrix.stopped)
        self.assertTrue(gate.sealed)

    def test_empty_initial_state_is_allowed_only_when_no_checkpoint_exists(self):
        startup, calls, matrix, gate = make_actual_run_bridge(
            has_checkpoint=False,
            loader=lambda _: (_ for _ in ()).throw(AssertionError("must not load")),
        )
        startup(port=7899)
        self.assertEqual(calls["loaded"], 0)
        self.assertEqual(calls["served"], 1)
        self.assertEqual(calls["saved"], 1)
        self.assertTrue(gate.sealed)
        self.assertTrue(matrix.stopped)


if __name__ == "__main__":
    unittest.main(verbosity=2)
