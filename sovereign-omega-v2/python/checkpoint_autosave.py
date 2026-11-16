"""Internal epoch-driven checkpoint scheduler, independent of HTTP clients.

No matrix allocation, no clocks in checkpoint contents, no browser authority.
The worker observes state in its own service-managed thread, never from do_GET.
Checkpoint persistence itself remains delegated to ledger_persist.save_checkpoint
(which snapshots CoreMatrix under its own RLock and writes atomically).
"""
from __future__ import annotations

import math
from typing import Callable


def checkpoint_epoch_once(matrix, saver: Callable, previous_epoch: int) -> int:
    """Persist only on epoch progress. Return the epoch *actually saved*.

    On failure the caller keeps previous_epoch unchanged and can retry without
    incorrectly treating a failed checkpoint as durable. The matrix epoch
    and checkpoint receipt are both taken from the real internal state, never
    browser telemetry.
    """
    if type(previous_epoch) is not int or previous_epoch < -1:
        raise ValueError("previous_epoch must be >= -1")
    with matrix._lock:
        observed_epoch = matrix._epoch
    if type(observed_epoch) is not int or observed_epoch < 0:
        raise RuntimeError("INVALID_MATRIX_EPOCH")
    if observed_epoch <= previous_epoch:
        return previous_epoch
    receipt = saver(matrix)
    if (not isinstance(receipt, dict)
            or type(receipt.get("epoch")) is not int
            or receipt["epoch"] < observed_epoch):
        raise RuntimeError("INVALID_CHECKPOINT_RECEIPT")
    return receipt["epoch"]


def checkpoint_autosave_worker(
    stop_event,
    matrix,
    saver: Callable,
    *,
    initial_epoch: int = -1,
    poll_seconds: float = 25.0,
    on_error: Callable | None = None,
) -> None:
    """Use a stop-aware internal interval; never block the HTTP request loop."""
    if type(initial_epoch) is not int or initial_epoch < -1:
        raise ValueError("initial_epoch must be >= -1")
    if (not isinstance(poll_seconds, (int, float))
            or not math.isfinite(poll_seconds) or poll_seconds <= 0):
        raise ValueError("poll_seconds must be finite and positive")
    last_saved = initial_epoch
    while not stop_event.wait(poll_seconds):
        try:
            last_saved = checkpoint_epoch_once(matrix, saver, last_saved)
        except Exception as exc:
            if on_error is not None:
                try:
                    on_error(exc)
                except Exception:
                    pass  # Logging failures cannot mint authority or mark a save.
