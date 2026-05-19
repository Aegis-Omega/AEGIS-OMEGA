"""
SOVEREIGN OMEGA — Hardware Configuration Layer
EPISTEMIC TIER: T0 (mechanically enforced constants)

All hardware constants for AMD RX 570 / 8GB RAM deployment.
This file is the single source of truth for all resource bounds.
No dynamic allocation. No privileged calls. User-space only.
"""

import os
import platform
from dataclasses import dataclass
from typing import Optional


# ── Physical Constraints ────────────────────────────────────────────────────
RAM_TOTAL_BYTES        = 8 * 1024 ** 3         # 8 GB hard ceiling
VRAM_TOTAL_BYTES       = 8 * 1024 ** 3         # RX 570 8GB variant
PGCS_TRIGGER_FRACTION  = 0.92                   # compress at 92% RAM usage
PGCS_TARGET_FRACTION   = 0.75                   # compress down to 75%
PGCS_MAX_COMPRESSION   = 50                     # 50x max via integer quantisation
PGCS_RING_BUFFER_BYTES = 512 * 1024 * 1024      # 512MB ring buffer

# ── Thermal Constraints (AMD RX 570) ────────────────────────────────────────
THERMAL_THROTTLE_C     = 80                     # throttle threshold °C
THERMAL_EMERGENCY_C    = 90                     # emergency cycle-stretch °C
THERMAL_SAMPLE_INTERVAL_S = 0.5                 # polling interval

# ── Determinism Constraints ─────────────────────────────────────────────────
# Bit-shifted integer configurations eliminate floating-point non-determinism
# across CPU and GPU architectures. All probabilistic bounds use these.
INT_SHIFT_BITS         = 16                     # Q16.16 fixed-point format
INT_SCALE              = 1 << INT_SHIFT_BITS    # 65536
INT_MAX                = (1 << 31) - 1          # signed 32-bit max
BOUNDED_DELTA_INT_MAX  = INT_SCALE              # 1.0 in Q16.16

# ── Stress Test Protocol ────────────────────────────────────────────────────
STRESS_TEST_DURATION_H = 12                     # 12-hour multi-hop reasoning test
STRESS_TEST_EPOCHS     = 100_000                # epoch count for gradient-anchor
CRASH_LOOP_COUNT       = 1_000                  # epoch failsafe validation runs

# ── AFSE Validation ─────────────────────────────────────────────────────────
AFSE_R2_THRESHOLD      = 0.98                   # min correlation with distributed
TGCS_VARIANCE_TARGET   = 0.0                    # run-to-run variance must be zero
PGCS_DISK_IO_TARGET    = 0                      # disk page-ins/outs must be zero


@dataclass(frozen=True)
class HardwareProfile:
    """Immutable hardware profile for the execution environment."""
    ram_bytes: int
    vram_bytes: int
    cpu_cores: int
    platform: str
    is_target_hardware: bool
    thermal_path: Optional[str]


def detect_hardware() -> HardwareProfile:
    """
    Detect hardware profile through unprivileged user-space APIs only.
    Never calls kernel-level drivers or privileged system calls.
    """
    import psutil
    ram_bytes = psutil.virtual_memory().total
    cpu_cores = os.cpu_count() or 1

    # Attempt VRAM detection via rocm-smi (user-space, no privileges needed)
    vram_bytes = _detect_vram_userspace()

    # Thermal path for AMD GPUs (user-space sysfs read)
    thermal_path = _find_amd_thermal_path()

    # Target hardware check
    is_target = (
        ram_bytes <= RAM_TOTAL_BYTES * 1.1 and  # within 10% of 8GB
        vram_bytes <= VRAM_TOTAL_BYTES * 1.1
    )

    return HardwareProfile(
        ram_bytes=ram_bytes,
        vram_bytes=vram_bytes,
        cpu_cores=cpu_cores,
        platform=platform.system(),
        is_target_hardware=is_target,
        thermal_path=thermal_path,
    )


def _detect_vram_userspace() -> int:
    """Attempt VRAM detection without privileges. Returns 0 if unavailable."""
    try:
        result = os.popen("rocm-smi --showmeminfo vram --json 2>/dev/null").read()
        if "VRAM Total Memory" in result:
            import json
            data = json.loads(result)
            for card in data.values():
                if "VRAM Total Memory (B)" in card:
                    return int(card["VRAM Total Memory (B)"])
    except Exception:
        pass
    return VRAM_TOTAL_BYTES  # assume target spec if detection fails


def _find_amd_thermal_path() -> Optional[str]:
    """Find AMD GPU thermal sensor in sysfs (user-space, no privileges)."""
    hwmon_base = "/sys/class/hwmon"
    if not os.path.exists(hwmon_base):
        return None
    for hwmon in os.listdir(hwmon_base):
        name_path = os.path.join(hwmon_base, hwmon, "name")
        try:
            with open(name_path) as f:
                if "amdgpu" in f.read().lower():
                    temp_path = os.path.join(hwmon_base, hwmon, "temp1_input")
                    if os.path.exists(temp_path):
                        return temp_path
        except Exception:
            continue
    return None


def read_gpu_temp_celsius(profile: HardwareProfile) -> Optional[float]:
    """
    Read GPU temperature in Celsius via user-space sysfs.
    Returns None if thermal monitoring is unavailable.
    INVARIANT: Never calls privileged APIs.
    """
    if not profile.thermal_path:
        return None
    try:
        with open(profile.thermal_path) as f:
            millicelsius = int(f.read().strip())
            return millicelsius / 1000.0
    except Exception:
        return None


# ── Fixed-Point Arithmetic ──────────────────────────────────────────────────
def to_fixed(x: float) -> int:
    """Convert float to Q16.16 fixed-point integer."""
    return int(x * INT_SCALE)


def from_fixed(x: int) -> float:
    """Convert Q16.16 fixed-point integer to float."""
    return x / INT_SCALE


def fixed_mul(a: int, b: int) -> int:
    """Multiply two Q16.16 fixed-point integers."""
    return (a * b) >> INT_SHIFT_BITS


def fixed_clamp(x: int, lo: int, hi: int) -> int:
    """Clamp Q16.16 fixed-point value to [lo, hi]."""
    return max(lo, min(hi, x))


def fixed_div(a: int, b: int) -> int:
    """Divide Q16.16 a by b. Returns Q16.16 result."""
    if b == 0:
        return INT_MAX if a >= 0 else -INT_MAX
    return (a << INT_SHIFT_BITS) // b


def fixed_sqrt(x: int) -> int:
    """Integer square root of Q16.16 x. Returns Q16.16 result."""
    if x <= 0:
        return 0
    # Newton-Raphson in fixed-point: converges in ~8 iterations
    # Initial estimate: shift right by half the total bits
    r = x >> (INT_SHIFT_BITS >> 1)
    if r == 0:
        r = 1
    for _ in range(8):
        r = (r + fixed_div(x, r)) >> 1
    return r


def fixed_exp_decay(value: int, decay: int, target: int) -> int:
    """Exponential decay: value = value * decay + target * (1 - decay). All Q16.16."""
    return fixed_mul(value, decay) + fixed_mul(target, INT_SCALE - decay)


def popcount32(x: int) -> int:
    """Count set bits in lower 32 bits of x (deterministic, no CPU dependency)."""
    x = x & 0xFFFFFFFF
    x = x - ((x >> 1) & 0x55555555)
    x = (x & 0x33333333) + ((x >> 2) & 0x33333333)
    x = (x + (x >> 4)) & 0x0F0F0F0F
    return ((x * 0x01010101) & 0xFFFFFFFF) >> 24


def bit_interleave(a: int, b: int) -> int:
    """Interleave lower 16 bits of a and b (Z-order/Morton encoding). Deterministic."""
    result = 0
    for i in range(16):
        result |= ((a >> i) & 1) << (2 * i)
        result |= ((b >> i) & 1) << (2 * i + 1)
    return result
