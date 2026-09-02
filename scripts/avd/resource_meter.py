from __future__ import annotations

import resource
import time
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PrecisionResourceSnapshot:
    wall_nanoseconds: int
    active_nanoseconds: int
    human_active_nanoseconds: int
    machine_active_nanoseconds: int
    cpu_user_microseconds: int
    cpu_system_microseconds: int
    input_tokens: int
    output_tokens: int
    tool_actions: int
    model_calls: int
    gpu_seconds: str
    cached_tokens: int | str
    api_cost_usd: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PrecisionResourceTracker:
    """Measurement ledger with explicit resolution semantics.

    Wall/active time comes from monotonic_ns(). POSIX getrusage exposes child
    CPU time through floating-point seconds backed by timeval-like counters on
    common platforms, so AVD records CPU in integer microseconds rather than
    pretending nanosecond precision.
    """

    def __init__(self, is_human_arm: bool = False):
        self.is_human_arm = is_human_arm
        self.start_wall_ns: int | None = None
        self.end_wall_ns: int | None = None
        self.active_ns_accumulated = 0
        self._active_window_start: int | None = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.tool_actions = 0
        self.model_calls = 0
        self.initial_rusage = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.final_rusage = self.initial_rusage

    def start_tracking(self) -> None:
        self.initial_rusage = resource.getrusage(resource.RUSAGE_CHILDREN)
        self.start_wall_ns = time.monotonic_ns()

    def stop_tracking(self) -> None:
        if self.start_wall_ns is None:
            raise RuntimeError("TRACKER_NOT_STARTED")
        if self._active_window_start is not None:
            self.stop_active_window()
        self.end_wall_ns = time.monotonic_ns()
        self.final_rusage = resource.getrusage(resource.RUSAGE_CHILDREN)

    def start_active_window(self) -> None:
        if self._active_window_start is None:
            self._active_window_start = time.monotonic_ns()

    def stop_active_window(self) -> None:
        if self._active_window_start is not None:
            self.active_ns_accumulated += time.monotonic_ns() - self._active_window_start
            self._active_window_start = None

    def record_llm_tokens(self, in_tokens: int, out_tokens: int, *, cached_tokens: int | None = None) -> None:
        if in_tokens < 0 or out_tokens < 0 or (cached_tokens is not None and cached_tokens < 0):
            raise ValueError("NEGATIVE_TOKEN_USAGE")
        self.input_tokens += in_tokens
        self.output_tokens += out_tokens
        self.model_calls += 1
        # A single provider-independent cache counter is only valid if callers
        # explicitly report it. Otherwise the receipt remains UNAVAILABLE.
        if cached_tokens is not None:
            current = getattr(self, "_cached_tokens", 0)
            self._cached_tokens = current + cached_tokens

    def record_tool_invocation(self) -> None:
        self.tool_actions += 1

    def compile_snapshot(self) -> PrecisionResourceSnapshot:
        if self.start_wall_ns is None or self.end_wall_ns is None:
            raise RuntimeError("TRACKER_NOT_STOPPED")

        wall_ns = max(0, self.end_wall_ns - self.start_wall_ns)
        active_ns = max(0, self.active_ns_accumulated)
        user_delta = max(0.0, self.final_rusage.ru_utime - self.initial_rusage.ru_utime)
        system_delta = max(0.0, self.final_rusage.ru_stime - self.initial_rusage.ru_stime)

        return PrecisionResourceSnapshot(
            wall_nanoseconds=wall_ns,
            active_nanoseconds=active_ns,
            human_active_nanoseconds=active_ns if self.is_human_arm else 0,
            machine_active_nanoseconds=0 if self.is_human_arm else active_ns,
            cpu_user_microseconds=int(round(user_delta * 1_000_000)),
            cpu_system_microseconds=int(round(system_delta * 1_000_000)),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            tool_actions=self.tool_actions,
            model_calls=self.model_calls,
            gpu_seconds="UNAVAILABLE",
            cached_tokens=getattr(self, "_cached_tokens", "UNAVAILABLE"),
            api_cost_usd="UNAVAILABLE",
        )
