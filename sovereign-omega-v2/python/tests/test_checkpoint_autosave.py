"""Source-bound checkpoint scheduler and read-only SSE regression tests.

These tests import the actual checkpoint_autosave.py module from the candidate
and execute the actual BridgeHandler.do_GET source extracted from bridge.py.
No 4GB CoreMatrix allocation, network listener, or filesystem write.
"""
from __future__ import annotations

import ast
import io
import json
import math
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PY_ROOT))
from checkpoint_autosave import checkpoint_epoch_once, checkpoint_autosave_worker


class TinyMatrix:
    def __init__(self, epoch=0):
        self._lock = threading.RLock()
        self._epoch = epoch

    def emit_vcg_telemetry(self):
        with self._lock:
            return {"epoch": self._epoch, "sequence": 7}


class SaveRecorder:
    def __init__(self, fail_times=0):
        self.epochs = []
        self.attempts = 0
        self.fail_times = fail_times

    def __call__(self, matrix):
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise OSError("simulated checkpoint failure")
        with matrix._lock:
            epoch = matrix._epoch
        self.epochs.append(epoch)
        return {"epoch": epoch}


class StepStop:
    def __init__(self, matrix, sequence):
        self.matrix = matrix
        self.sequence = iter(sequence)
        self.calls = 0

    def wait(self, seconds):
        if seconds <= 0:
            raise AssertionError("worker should use a positive interval")
        self.calls += 1
        next_epoch = next(self.sequence)
        if next_epoch is None:
            return True
        with self.matrix._lock:
            self.matrix._epoch = next_epoch
        return False


def extract_actual_get(gate, matrix):
    source = (PY_ROOT / "bridge.py").read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    bridge_cls = next(
        n for n in module_ast.body
        if isinstance(n, ast.ClassDef) and n.name == "BridgeHandler"
    )
    get_method = next(
        n for n in bridge_cls.body
        if isinstance(n, ast.FunctionDef) and n.name == "do_GET"
    )
    # Guard the source itself, not a reimplemented stream loop.
    forbidden = {"save_checkpoint", "_save_checkpoint_serialized",
                 "checkpoint_epoch_once", "checkpoint_autosave_worker"}
    called = {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(get_method) if isinstance(n, ast.Call)
        if isinstance(n.func, (ast.Name, ast.Attribute))
    }
    if called.intersection(forbidden):
        raise AssertionError("GET_HANDLER_HAS_CHECKPOINT_WRITE")
    cls = ast.ClassDef(
        name="GetHandlerUnderTest", bases=[], keywords=[],
        body=[get_method], decorator_list=[]
    )
    ast.fix_missing_locations(cls)

    def forbidden_save(_):
        raise AssertionError("UNAUTHORIZED_CHECKPOINT_SAVE_FROM_GET")

    namespace = {
        "json": json, "matrix": matrix, "gate": gate,
        "save_checkpoint": forbidden_save,
        "_save_checkpoint_serialized": forbidden_save,
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]),
                 str(PY_ROOT / "bridge.py"), "exec"), namespace)
    return namespace["GetHandlerUnderTest"]


class StreamWriter:
    def __init__(self, limit=7):
        self.messages = []
        self.limit = limit

    def write(self, data):
        if len(self.messages) >= self.limit:
            raise BrokenPipeError("test closes the SSE stream")
        self.messages.append(data)

    def flush(self):
        pass


class TestAutosave(unittest.TestCase):
    def test_first_progress_writes_once_and_records_real_receipt(self):
        matrix = TinyMatrix(epoch=1)
        saver = SaveRecorder()
        self.assertEqual(checkpoint_epoch_once(matrix, saver, 0), 1)
        self.assertEqual(checkpoint_epoch_once(matrix, saver, 1), 1)
        self.assertEqual(saver.epochs, [1])
        self.assertEqual(saver.attempts, 1)

    def test_restored_epoch_does_not_rewrite_without_progress(self):
        matrix = TinyMatrix(epoch=7)
        saver = SaveRecorder()
        self.assertEqual(checkpoint_epoch_once(matrix, saver, 7), 7)
        self.assertEqual(saver.epochs, [])
        matrix._epoch = 8
        self.assertEqual(checkpoint_epoch_once(matrix, saver, 7), 8)
        self.assertEqual(saver.epochs, [8])

    def test_failed_save_does_not_claim_durability(self):
        matrix = TinyMatrix(epoch=12)
        saver = SaveRecorder(fail_times=1)
        with self.assertRaisesRegex(OSError, "simulated checkpoint failure"):
            checkpoint_epoch_once(matrix, saver, 11)
        self.assertEqual(saver.epochs, [])
        self.assertEqual(checkpoint_epoch_once(matrix, saver, 11), 12)
        self.assertEqual(saver.epochs, [12])
        self.assertEqual(saver.attempts, 2)

    def test_invalid_or_stale_receipt_never_advances_durability(self):
        matrix = TinyMatrix(epoch=9)
        for receipt in (None, {}, {"epoch": 8}, {"epoch": 9.0},
                        {"epoch": "9"}, {"epoch": True}):
            with self.subTest(receipt=receipt):
                with self.assertRaisesRegex(RuntimeError, "INVALID_CHECKPOINT_RECEIPT"):
                    checkpoint_epoch_once(matrix, lambda _: receipt, 8)

    def test_initial_epoch_and_matrix_epoch_validation(self):
        matrix = TinyMatrix(epoch=0)
        saver = SaveRecorder()
        for value in (-2, 1.0, True, "0", None):
            with self.subTest(previous=value):
                with self.assertRaises((ValueError, TypeError)):
                    checkpoint_epoch_once(matrix, saver, value)
        for epoch in (-1, 1.5, True, "5"):
            with self.subTest(epoch=epoch):
                matrix._epoch = epoch
                with self.assertRaisesRegex(RuntimeError, "INVALID_MATRIX_EPOCH"):
                    checkpoint_epoch_once(matrix, saver, -1)

    def test_worker_uses_internal_epoch_not_client_requests(self):
        matrix = TinyMatrix(epoch=2)
        saver = SaveRecorder()
        stop = StepStop(matrix, [2, 3, 3, 4, None])
        checkpoint_autosave_worker(
            stop, matrix, saver, initial_epoch=2, poll_seconds=1.0
        )
        self.assertEqual(saver.epochs, [3, 4])
        self.assertEqual(stop.calls, 5)

    def test_worker_retries_failed_save_and_reports_error(self):
        matrix = TinyMatrix(epoch=1)
        saver = SaveRecorder(fail_times=1)
        errors = []
        stop = StepStop(matrix, [2, 2, None])
        checkpoint_autosave_worker(
            stop, matrix, saver, initial_epoch=1,
            poll_seconds=1.0, on_error=errors.append
        )
        self.assertEqual(saver.epochs, [2])
        self.assertEqual(saver.attempts, 2)
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], OSError)

    def test_error_callback_failure_does_not_mark_checkpoint_saved(self):
        matrix = TinyMatrix(epoch=1)
        saver = SaveRecorder(fail_times=1)

        def broken_logger(_exc):
            raise RuntimeError("logger error")

        checkpoint_autosave_worker(
            StepStop(matrix, [2, 2, None]), matrix, saver,
            initial_epoch=1, poll_seconds=0.5, on_error=broken_logger
        )
        self.assertEqual(saver.epochs, [2])
        self.assertEqual(saver.attempts, 2)

    def test_invalid_worker_intervals_fail_closed(self):
        matrix = TinyMatrix()
        saver = SaveRecorder()
        for interval in (0, -1, math.nan, math.inf, "25"):
            with self.subTest(interval=interval):
                with self.assertRaises((ValueError, TypeError)):
                    checkpoint_autosave_worker(
                        StepStop(matrix, [None]), matrix, saver,
                        poll_seconds=interval
                    )
        self.assertEqual(saver.attempts, 0)

    def test_sse_get_returns_bounded_frame_without_checkpoint_or_wait(self):
        matrix = TinyMatrix(epoch=17)

        class FakeGate:
            @staticmethod
            def telemetry():
                return {"gate_sealed": False}

        cls = extract_actual_get(FakeGate(), matrix)
        handler = cls()
        handler.path = "/telemetry/stream"
        handler.wfile = StreamWriter(limit=7)
        responses, headers = [], []
        handler.send_response = responses.append
        handler._cors_headers = lambda: None
        handler.send_header = lambda key, value: headers.append((key, value))
        handler.end_headers = lambda: None
        # Any attempt to hold the single-threaded HTTP server's request
        # open to sleep for 5s is a regression.
        with patch.object(time, "sleep", side_effect=AssertionError("GET_BLOCKED_SERVER")):
            handler.do_GET()
        self.assertEqual(responses, [200])
        self.assertTrue(handler.close_connection)
        self.assertIn(("Content-Type", "text/event-stream"), headers)
        self.assertIn(("Connection", "close"), headers)
        self.assertEqual(len(handler.wfile.messages), 1)
        body = handler.wfile.messages[0]
        self.assertEqual(int(dict(headers)["Content-Length"]), len(body))
        self.assertTrue(body.startswith(b"retry: 5000\ndata: "))
        self.assertTrue(body.endswith(b"\n\n"))
        self.assertEqual(json.loads(body.split(b"\n")[1][6:]), {
            "epoch": 17, "sequence": 7,
            "gate": {"gate_sealed": False},
        })

    def test_second_sse_get_reads_fresh_epoch_without_replaying_state(self):
        matrix = TinyMatrix(epoch=17)

        class FakeGate:
            @staticmethod
            def telemetry():
                return {"gate_sealed": False}

        cls = extract_actual_get(FakeGate(), matrix)
        payloads = []
        for epoch in (17, 18):
            matrix._epoch = epoch
            handler = cls()
            handler.path = "/telemetry/stream"
            handler.wfile = StreamWriter(limit=2)
            handler.send_response = lambda _code: None
            handler._cors_headers = lambda: None
            handler.send_header = lambda *_args: None
            handler.end_headers = lambda: None
            with patch.object(time, "sleep", side_effect=AssertionError("GET_BLOCKED_SERVER")):
                handler.do_GET()
            self.assertEqual(len(handler.wfile.messages), 1)
            payload = json.loads(handler.wfile.messages[0].split(b"\n")[1][6:])
            payloads.append(payload["epoch"])
            self.assertTrue(handler.close_connection)
        self.assertEqual(payloads, [17, 18])

    def test_sse_broken_pipe_does_not_prolong_request(self):
        matrix = TinyMatrix(epoch=17)

        class FakeGate:
            @staticmethod
            def telemetry():
                return {"gate_sealed": False}

        cls = extract_actual_get(FakeGate(), matrix)
        handler = cls()
        handler.path = "/telemetry/stream"
        handler.wfile = StreamWriter(limit=0)
        replies = []
        handler.send_response = replies.append
        handler._cors_headers = lambda: None
        handler.send_header = lambda *_args: None
        handler.end_headers = lambda: None
        with patch.object(time, "sleep", side_effect=AssertionError("GET_BLOCKED_SERVER")):
            handler.do_GET()
        self.assertEqual(replies, [200])
        self.assertTrue(handler.close_connection)
        self.assertEqual(handler.wfile.messages, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
