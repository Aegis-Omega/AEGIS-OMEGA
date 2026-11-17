"""Resource-aware memory layout for AEGIS. No machine-specific GB constants.

Capacity is calculated from *available* host memory and bounded container
headroom, or from an explicit operator override. The minimum arena and 64 KiB
alignment are software record-format requirements, not claims about a GPU.

The arena is a virtually mapped working set; it does not need to be eagerly
committed. No memory or device probe is used as a proof of hardware fitness.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import lcm
from pathlib import Path
import os


PAGE_ALIGNMENT = 1 << 16
M1_RECORD_BYTES = 40
M1_ALIGNMENT = lcm(PAGE_ALIGNMENT, M1_RECORD_BYTES)
# A minimum operating arena is a *software protocol bound*, not a host model.
MIN_ARENA_BYTES = 64 * PAGE_ALIGNMENT
DEFAULT_BUDGET_DIVISOR = 32  # 1/32 of observed free memory, not physical size.


class MemoryBudgetError(ValueError):
    """Fail closed if the effective memory ceiling cannot be measured."""


def _integer_file(path: str) -> int | None:
    try:
        value = Path(path).read_text(encoding="ascii").strip()
        if not value.isdecimal():
            return None
        n = int(value)
        if n >= (1 << 60):  # cgroup-v1 "unlimited" sentinel
            return None
        return n
    except (OSError, ValueError, UnicodeError):
        return None


def cgroup_remaining_bytes() -> int | None:
    """Discover cgroup v2 or v1 memory headroom; None means unrestricted/unknown."""
    for limit_file, current_file in (
        ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory.current"),
        ("/sys/fs/cgroup/memory/memory.limit_in_bytes",
         "/sys/fs/cgroup/memory/memory.usage_in_bytes"),
    ):
        limit = _integer_file(limit_file)
        if limit is None:
            try:
                raw = Path(limit_file).read_text(encoding="ascii").strip()
            except FileNotFoundError:
                continue
            except (OSError, UnicodeError) as exc:
                raise MemoryBudgetError("CGROUP_MEMORY_LIMIT_UNREADABLE") from exc
            if raw == "max" or (raw.isdecimal() and int(raw) >= (1 << 60)):
                continue
            raise MemoryBudgetError("CGROUP_MEMORY_LIMIT_INVALID")
        current = _integer_file(current_file)
        if current is None:
            raise MemoryBudgetError("CGROUP_MEMORY_CURRENT_UNKNOWN")
        return max(0, limit - current)
    return None


def host_memory_bytes() -> tuple[int, int]:
    """Return (total, available); optional psutil, then OS-level fallback."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        if vm.total > 0 and vm.available > 0:
            return int(vm.total), int(vm.available)
    except (ImportError, OSError, AttributeError):
        pass

    total = 0
    try:
        total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, AttributeError):
        pass

    available = 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
                break
    except (OSError, ValueError):
        pass
    if not available:
        try:
            available = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, AttributeError):
            pass
    if total <= 0 or available <= 0:
        raise MemoryBudgetError("HOST_AVAILABLE_MEMORY_UNKNOWN")
    return int(total), int(available)


def effective_available_bytes(
    host_available: int | None = None,
    cgroup_remaining: int | None = None,
) -> int:
    if host_available is None:
        _, host_available = host_memory_bytes()
        if cgroup_remaining is None:
            cgroup_remaining = cgroup_remaining_bytes()
    if type(host_available) is not int or host_available <= 0:
        raise MemoryBudgetError("HOST_AVAILABLE_MEMORY_INVALID")
    if cgroup_remaining is None:
        return host_available
    if type(cgroup_remaining) is not int or cgroup_remaining < 0:
        raise MemoryBudgetError("CGROUP_MEMORY_INVALID")
    if cgroup_remaining == 0:
        raise MemoryBudgetError("CGROUP_MEMORY_EXHAUSTED")
    return min(host_available, cgroup_remaining)


def select_arena_bytes(available_bytes: int, override: int | str | None = None) -> int:
    """Resolve explicit budget or conservative automatic allocation.

    Override must fit at most half the effective currently-available memory,
    leaving room for runtime, dependencies, scheduler and monitor. This is a
    fail-closed configuration rule, not a silently clipped size.
    """
    if type(available_bytes) is not int or available_bytes <= 0:
        raise MemoryBudgetError("AVAILABLE_MEMORY_INVALID")
    if override is None:
        selected = available_bytes // DEFAULT_BUDGET_DIVISOR
    else:
        if type(override) is str:
            if not override.isdecimal():
                raise MemoryBudgetError("AEGIS_ARRAY_BYTES_NOT_DECIMAL")
            selected = int(override)
        elif type(override) is int:
            selected = override
        else:
            raise MemoryBudgetError("AEGIS_ARRAY_BYTES_BAD_TYPE")
        if selected > available_bytes // 2:
            raise MemoryBudgetError("AEGIS_ARRAY_BYTES_EXCEEDS_SAFE_HEADROOM")
    selected -= selected % PAGE_ALIGNMENT
    if selected < MIN_ARENA_BYTES:
        raise MemoryBudgetError("INSUFFICIENT_MEMORY_FOR_ARENA")
    return selected


@dataclass(frozen=True)
class ArenaLayout:
    total: int
    m1_size: int
    m2_size: int
    m3_size: int

    @property
    def m2_offset(self) -> int:
        return self.m1_size

    @property
    def m3_offset(self) -> int:
        return self.m1_size + self.m2_size


def plan_layout(total: int) -> ArenaLayout:
    """Exact integer partition: M1 40-byte slots, all boundaries 64 KiB aligned."""
    if type(total) is not int or total < MIN_ARENA_BYTES or total % PAGE_ALIGNMENT:
        raise MemoryBudgetError("ARENA_SIZE_UNALIGNED_OR_TOO_SMALL")
    m1 = ((total // 2) // M1_ALIGNMENT) * M1_ALIGNMENT
    m2 = (((total * 3) // 10) // PAGE_ALIGNMENT) * PAGE_ALIGNMENT
    m3 = total - m1 - m2
    if min(m1, m2, m3) < PAGE_ALIGNMENT or m1 % M1_RECORD_BYTES:
        raise MemoryBudgetError("ARENA_REGION_INVALID")
    if m1 % PAGE_ALIGNMENT or m2 % PAGE_ALIGNMENT or m3 % PAGE_ALIGNMENT:
        raise MemoryBudgetError("ARENA_REGION_UNALIGNED")
    return ArenaLayout(total, m1, m2, m3)


def configured_arena_layout() -> ArenaLayout:
    available = effective_available_bytes()
    return plan_layout(select_arena_bytes(available, os.environ.get("AEGIS_ARRAY_BYTES")))
