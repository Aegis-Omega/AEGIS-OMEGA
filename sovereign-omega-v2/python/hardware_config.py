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
#
# Scale domains (settled — do not "reconcile" with Q32.32, they are separate):
#   Q16.16 (this, INT_SCALE=65536) = Python hardware-inference domain. The TS
#     side uses the SAME scale (src/environment/.../introspection.ts
#     FIXED_SCALE = 1<<16 = 65536) for its entropy-budget fields, so the two
#     agree by construction.
#   Q32.32 (src/core/fixedpoint.ts) = a DIFFERENT domain: JS<->WASM governance
#     math (Bernstein/VCG). It never crosses into Python — the bridge exchanges
#     floats, not raw fixed-point — so the two scales never need to match.
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
    """Integer square root of Q16.16 x. Returns Q16.16 result.

    For Q16.16 (x represents v * 65536): sqrt(v) in Q16.16 = isqrt(x) << 8.
    Uses integer Newton-Raphson on the raw fixed-point value.
    """
    if x <= 0:
        return 0
    # Integer sqrt of raw value via Newton-Raphson on integers
    r = x
    while True:
        r1 = (r + x // r) >> 1
        if r1 >= r:
            break
        r = r1
    # r = isqrt(x); convert to Q16.16 by shifting up by SHIFT/2
    return r << (INT_SHIFT_BITS >> 1)


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


# ── Information-Theoretic Primitives (Cycles 1–10) ──────────────────────────
# Shannon entropy and related measures are the mathematical substrate for
# self-aware calibration. All functions use Q16.16 fixed-point arithmetic.
# Inputs are probability vectors (list of Q16.16 values summing to INT_SCALE).

import math as _math

def _log2_fixed(x: int) -> int:
    """log2(x) in Q16.16 where x is a Q16.16 probability. Returns Q16.16."""
    if x <= 0:
        return -INT_MAX
    # Convert to float, compute log2, convert back to Q16.16
    # This is the only permissible float use — information measures inherently
    # require logarithms, which have no integer closed form.
    flt = x / INT_SCALE
    return int(_math.log2(flt) * INT_SCALE)


def shannon_entropy_fixed(probs: list) -> int:
    """
    Shannon entropy H(P) = -Σ p_i * log2(p_i). Returns Q16.16 bits.
    probs: list of Q16.16 values (must sum to INT_SCALE).
    H=0 = certain, H=INT_SCALE*log2(n) = uniform over n.
    """
    total = 0
    for p in probs:
        if p <= 0:
            continue
        log2_p = _log2_fixed(p)
        # H += -p * log2(p), both in Q16.16; result in Q16.32 → shift back
        total += -fixed_mul(p, log2_p)
    return total


def kl_divergence_fixed(p_probs: list, q_probs: list) -> int:
    """
    KL divergence D_KL(P||Q) = Σ p_i * log2(p_i / q_i). Returns Q16.16.
    Undefined (returns INT_MAX) where q_i=0 and p_i>0.
    """
    total = 0
    for p, q in zip(p_probs, q_probs):
        if p <= 0:
            continue
        if q <= 0:
            return INT_MAX
        log2_ratio = _log2_fixed(p) - _log2_fixed(q)
        total += fixed_mul(p, log2_ratio)
    return total


def cross_entropy_fixed(p_probs: list, q_probs: list) -> int:
    """
    Cross-entropy H(P, Q) = -Σ p_i * log2(q_i). Returns Q16.16 bits.
    Equal to H(P) + D_KL(P||Q).
    """
    total = 0
    for p, q in zip(p_probs, q_probs):
        if p <= 0:
            continue
        if q <= 0:
            return INT_MAX
        total += -fixed_mul(p, _log2_fixed(q))
    return total


def mutual_information_fixed(joint: list, p_marginal: list, q_marginal: list) -> int:
    """
    Mutual information I(X;Y) = Σ p(x,y) * log2(p(x,y) / p(x)*p(y)).
    joint: flat list of Q16.16 joint probabilities (len = |X| * |Y|).
    p_marginal, q_marginal: marginals over X and Y respectively.
    Returns Q16.16.
    """
    n_x = len(p_marginal)
    n_y = len(q_marginal)
    total = 0
    for i, pxy in enumerate(joint):
        if pxy <= 0:
            continue
        x = i // n_y
        y = i % n_y
        px = p_marginal[x] if x < len(p_marginal) else 0
        py = q_marginal[y] if y < len(q_marginal) else 0
        if px <= 0 or py <= 0:
            continue
        log2_ratio = _log2_fixed(pxy) - _log2_fixed(fixed_mul(px, py))
        total += fixed_mul(pxy, log2_ratio)
    return total


def entropy_rate_fixed(symbol_seq: list, alphabet_size: int) -> int:
    """
    Empirical entropy rate from a symbol sequence (bigram model).
    Returns H(X_n | X_{n-1}) in Q16.16 bits.
    """
    if len(symbol_seq) < 2 or alphabet_size <= 0:
        return 0
    # Count bigram and unigram frequencies
    bigram: dict = {}
    unigram: dict = {}
    for i in range(len(symbol_seq) - 1):
        a, b = symbol_seq[i], symbol_seq[i + 1]
        bigram[(a, b)] = bigram.get((a, b), 0) + 1
        unigram[a] = unigram.get(a, 0) + 1
    total_pairs = len(symbol_seq) - 1
    rate = 0
    for (a, b), count in bigram.items():
        p_ab = (count * INT_SCALE) // total_pairs
        p_a = (unigram[a] * INT_SCALE) // total_pairs
        if p_a <= 0:
            continue
        p_b_given_a = fixed_div(p_ab, p_a)
        if p_b_given_a <= 0:
            continue
        rate += -fixed_mul(p_ab, _log2_fixed(p_b_given_a))
    return rate


def compression_ratio_fixed(original_len: int, compressed_len: int) -> int:
    """Compression ratio as Q16.16: compressed/original. Lower = better compression."""
    if original_len <= 0:
        return INT_SCALE
    return fixed_div(compressed_len * INT_SCALE, original_len * INT_SCALE)
