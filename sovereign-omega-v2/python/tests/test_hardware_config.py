"""
SOVEREIGN OMEGA — Hardware Config Tests
EPISTEMIC TIER: T0

Comprehensive tests for hardware_config.py: constants, fixed-point arithmetic,
information-theoretic primitives, and the HardwareProfile dataclass.

Run: python python/tests/test_hardware_config.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hardware_config import (
    RAM_TOTAL_BYTES, VRAM_TOTAL_BYTES, INT_SHIFT_BITS, INT_SCALE, INT_MAX,
    BOUNDED_DELTA_INT_MAX, PGCS_TRIGGER_FRACTION, PGCS_TARGET_FRACTION,
    PGCS_MAX_COMPRESSION, THERMAL_THROTTLE_C, THERMAL_EMERGENCY_C,
    AFSE_R2_THRESHOLD, TGCS_VARIANCE_TARGET,
    to_fixed, from_fixed, fixed_mul, fixed_clamp, fixed_div, fixed_sqrt,
    fixed_exp_decay, popcount32, bit_interleave,
    shannon_entropy_fixed, kl_divergence_fixed, cross_entropy_fixed,
    compression_ratio_fixed,
    HardwareProfile,
)

PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f'  PASS  {name}')


def fail(name: str, reason: str) -> None:
    global FAIL
    FAIL += 1
    print(f'  FAIL  {name}: {reason}')


def _chk(name: str, condition: bool, reason: str = '') -> None:
    if condition:
        ok(name)
    else:
        fail(name, reason or 'assertion failed')


def expect_raises(name: str, exc_type, fn) -> None:
    try:
        fn()
        fail(name, f'expected {exc_type.__name__} but no exception raised')
    except exc_type:
        ok(name)
    except Exception as e:
        fail(name, f'expected {exc_type.__name__} but got {type(e).__name__}: {e}')


# ── Constants ─────────────────────────────────────────────────────────────────

def test_constants():
    print('\nconstants:')

    _chk('RAM_TOTAL_BYTES == 8 * 1024**3', RAM_TOTAL_BYTES == 8 * 1024 ** 3)
    _chk('VRAM_TOTAL_BYTES == 8 * 1024**3', VRAM_TOTAL_BYTES == 8 * 1024 ** 3)
    _chk('INT_SHIFT_BITS == 16', INT_SHIFT_BITS == 16)
    _chk('INT_SCALE == 65536', INT_SCALE == 65536)
    _chk('INT_SCALE == 1 << INT_SHIFT_BITS', INT_SCALE == (1 << INT_SHIFT_BITS))
    _chk('INT_MAX == 2**31 - 1', INT_MAX == 2 ** 31 - 1)
    _chk('INT_MAX is positive', INT_MAX > 0)
    _chk('BOUNDED_DELTA_INT_MAX == INT_SCALE', BOUNDED_DELTA_INT_MAX == INT_SCALE)
    _chk('PGCS_TRIGGER_FRACTION == 0.92', PGCS_TRIGGER_FRACTION == 0.92)
    _chk('PGCS_TARGET_FRACTION == 0.75', PGCS_TARGET_FRACTION == 0.75)
    _chk('PGCS_MAX_COMPRESSION == 50', PGCS_MAX_COMPRESSION == 50)
    _chk('THERMAL_THROTTLE_C == 80', THERMAL_THROTTLE_C == 80)
    _chk('THERMAL_EMERGENCY_C == 90', THERMAL_EMERGENCY_C == 90)
    _chk('AFSE_R2_THRESHOLD == 0.98', AFSE_R2_THRESHOLD == 0.98)
    _chk('TGCS_VARIANCE_TARGET == 0.0', TGCS_VARIANCE_TARGET == 0.0)
    _chk('PGCS_TRIGGER_FRACTION > PGCS_TARGET_FRACTION',
         PGCS_TRIGGER_FRACTION > PGCS_TARGET_FRACTION)
    _chk('THERMAL_EMERGENCY_C > THERMAL_THROTTLE_C',
         THERMAL_EMERGENCY_C > THERMAL_THROTTLE_C)
    _chk('PGCS_MAX_COMPRESSION is int', isinstance(PGCS_MAX_COMPRESSION, int))
    _chk('RAM_TOTAL_BYTES is int', isinstance(RAM_TOTAL_BYTES, int))
    _chk('VRAM_TOTAL_BYTES is int', isinstance(VRAM_TOTAL_BYTES, int))


# ── to_fixed / from_fixed ─────────────────────────────────────────────────────

def test_to_from_fixed():
    print('\nto_fixed / from_fixed:')

    _chk('from_fixed(to_fixed(0.0)) == 0.0', from_fixed(to_fixed(0.0)) == 0.0)
    _chk('from_fixed(to_fixed(1.0)) == 1.0', from_fixed(to_fixed(1.0)) == 1.0)
    _chk('from_fixed(to_fixed(0.5)) == 0.5', from_fixed(to_fixed(0.5)) == 0.5)
    _chk('from_fixed(to_fixed(-1.0)) == -1.0', from_fixed(to_fixed(-1.0)) == -1.0)
    _chk('to_fixed(1.0) == INT_SCALE', to_fixed(1.0) == INT_SCALE)
    _chk('to_fixed(0.0) == 0', to_fixed(0.0) == 0)
    _chk('to_fixed(2.0) == 2 * INT_SCALE', to_fixed(2.0) == 2 * INT_SCALE)
    _chk('to_fixed(0.25) == INT_SCALE // 4', to_fixed(0.25) == INT_SCALE // 4)
    _chk('to_fixed(-0.5) == -INT_SCALE // 2', to_fixed(-0.5) == -(INT_SCALE // 2))
    _chk('from_fixed(INT_SCALE) == 1.0', from_fixed(INT_SCALE) == 1.0)
    _chk('from_fixed(0) == 0.0', from_fixed(0) == 0.0)
    _chk('from_fixed(2 * INT_SCALE) == 2.0', from_fixed(2 * INT_SCALE) == 2.0)
    _chk('from_fixed(-INT_SCALE) == -1.0', from_fixed(-INT_SCALE) == -1.0)
    _chk('to_fixed returns int', isinstance(to_fixed(1.5), int))
    _chk('from_fixed returns float', isinstance(from_fixed(INT_SCALE), float))


# ── fixed_mul ─────────────────────────────────────────────────────────────────

def test_fixed_mul():
    print('\nfixed_mul:')

    _chk('1.0 * 1.0 = 1.0', fixed_mul(INT_SCALE, INT_SCALE) == INT_SCALE)
    _chk('0.5 * 1.0 = 0.5', fixed_mul(INT_SCALE // 2, INT_SCALE) == INT_SCALE // 2)
    _chk('0 * 1.0 = 0', fixed_mul(0, INT_SCALE) == 0)
    _chk('1.0 * 0 = 0', fixed_mul(INT_SCALE, 0) == 0)
    # 0.5 * 0.5 = 0.25; INT_SCALE // 4 = 16384; result should be within 1
    result = fixed_mul(INT_SCALE // 2, INT_SCALE // 2)
    expected = INT_SCALE // 4
    _chk('0.5 * 0.5 ≈ 0.25 (within 1)', abs(result - expected) <= 1,
         f'got {result}, expected ~{expected}')
    _chk('2.0 * 2.0 = 4.0', fixed_mul(2 * INT_SCALE, 2 * INT_SCALE) == 4 * INT_SCALE)
    _chk('fixed_mul returns int', isinstance(fixed_mul(INT_SCALE, INT_SCALE), int))
    _chk('1.0 * 0.5 = 0.5 (commutative)',
         fixed_mul(INT_SCALE, INT_SCALE // 2) == fixed_mul(INT_SCALE // 2, INT_SCALE))
    _chk('0 * 0 = 0', fixed_mul(0, 0) == 0)
    _chk('negative mul: -1.0 * 1.0 = -1.0',
         fixed_mul(-INT_SCALE, INT_SCALE) == -INT_SCALE)


# ── fixed_clamp ───────────────────────────────────────────────────────────────

def test_fixed_clamp():
    print('\nfixed_clamp:')

    _chk('clamp(0, 0, S) == 0', fixed_clamp(0, 0, INT_SCALE) == 0)
    _chk('clamp(S, 0, S) == S', fixed_clamp(INT_SCALE, 0, INT_SCALE) == INT_SCALE)
    _chk('clamp(-1, 0, S) == 0', fixed_clamp(-1, 0, INT_SCALE) == 0)
    _chk('clamp(S+1, 0, S) == S', fixed_clamp(INT_SCALE + 1, 0, INT_SCALE) == INT_SCALE)
    _chk('clamp(S//2, 0, S) == S//2', fixed_clamp(INT_SCALE // 2, 0, INT_SCALE) == INT_SCALE // 2)
    _chk('result always >= lo', fixed_clamp(-1000, 0, INT_SCALE) >= 0)
    _chk('result always <= hi', fixed_clamp(INT_MAX, 0, INT_SCALE) <= INT_SCALE)
    _chk('clamp within range is identity', fixed_clamp(100, 50, 200) == 100)
    _chk('clamp below lo', fixed_clamp(10, 50, 200) == 50)
    _chk('clamp above hi', fixed_clamp(300, 50, 200) == 200)
    _chk('lo == hi: only value possible', fixed_clamp(0, 5, 5) == 5)
    _chk('negative range', fixed_clamp(-3, -10, -1) == -3)
    _chk('clamp below negative range', fixed_clamp(-15, -10, -1) == -10)
    _chk('clamp above negative range', fixed_clamp(0, -10, -1) == -1)


# ── fixed_div ─────────────────────────────────────────────────────────────────

def test_fixed_div():
    print('\nfixed_div:')

    _chk('1.0 / 1.0 = 1.0', fixed_div(INT_SCALE, INT_SCALE) == INT_SCALE)
    _chk('0 / 1.0 = 0', fixed_div(0, INT_SCALE) == 0)
    # 1.0 / 2.0 = 0.5
    result = fixed_div(INT_SCALE, 2 * INT_SCALE)
    _chk('1.0 / 2.0 = 0.5', result == INT_SCALE // 2,
         f'got {result}, expected {INT_SCALE // 2}')
    _chk('div by zero (positive) returns INT_MAX',
         fixed_div(INT_SCALE, 0) == INT_MAX)
    _chk('div by zero (negative) returns -INT_MAX',
         fixed_div(-INT_SCALE, 0) == -INT_MAX)
    # 2.0 / 1.0 = 2.0
    _chk('2.0 / 1.0 = 2.0', fixed_div(2 * INT_SCALE, INT_SCALE) == 2 * INT_SCALE)
    _chk('fixed_div returns int', isinstance(fixed_div(INT_SCALE, INT_SCALE), int))
    _chk('0 / 0 → INT_MAX (0 >= 0)', fixed_div(0, 0) == INT_MAX)


# ── fixed_sqrt ────────────────────────────────────────────────────────────────

def test_fixed_sqrt():
    print('\nfixed_sqrt:')

    _chk('sqrt(0) == 0', fixed_sqrt(0) == 0)
    # sqrt(1.0) = 1.0
    r = fixed_sqrt(INT_SCALE)
    tol = INT_SCALE // 100  # 1%
    _chk('sqrt(1.0) ≈ 1.0 (within 1%)',
         abs(r - INT_SCALE) <= tol, f'got {r}, expected ~{INT_SCALE}')
    # sqrt(4.0) = 2.0
    r4 = fixed_sqrt(4 * INT_SCALE)
    _chk('sqrt(4.0) ≈ 2.0 (within 1%)',
         abs(r4 - 2 * INT_SCALE) <= 2 * tol, f'got {r4}, expected ~{2 * INT_SCALE}')
    _chk('sqrt(-1) == 0 (negative clamped)', fixed_sqrt(-1) == 0)
    _chk('sqrt returns int', isinstance(fixed_sqrt(INT_SCALE), int))
    # sqrt(9.0) = 3.0
    r9 = fixed_sqrt(9 * INT_SCALE)
    _chk('sqrt(9.0) ≈ 3.0 (within 1%)',
         abs(r9 - 3 * INT_SCALE) <= 3 * tol, f'got {r9}, expected ~{3 * INT_SCALE}')
    _chk('sqrt(0.25) ≈ 0.5 (within 1%)',
         abs(fixed_sqrt(INT_SCALE // 4) - INT_SCALE // 2) <= tol)


# ── fixed_exp_decay ───────────────────────────────────────────────────────────

def test_fixed_exp_decay():
    print('\nfixed_exp_decay:')

    # When decay = INT_SCALE (1.0): value * 1.0 + target * 0.0 = value
    val = 10 * INT_SCALE
    target = 5 * INT_SCALE
    r = fixed_exp_decay(val, INT_SCALE, target)
    _chk('decay=1.0 keeps value', r == val, f'got {r}, expected {val}')

    # When decay = 0: value * 0 + target * 1.0 = target
    r0 = fixed_exp_decay(val, 0, target)
    _chk('decay=0 equals target', r0 == target, f'got {r0}, expected {target}')

    # Intermediate decay: result between value and target
    half = INT_SCALE // 2
    r_half = fixed_exp_decay(val, half, target)
    lo = min(val, target)
    hi = max(val, target)
    _chk('intermediate decay result in [target, value]',
         lo <= r_half <= hi, f'got {r_half}, expected in [{lo}, {hi}]')

    # decay=0.9: result closer to value than to target
    decay_90 = INT_SCALE * 9 // 10
    r90 = fixed_exp_decay(val, decay_90, target)
    _chk('decay=0.9 result closer to value than target',
         abs(r90 - val) < abs(r90 - target),
         f'got {r90}, val={val}, target={target}')

    # Self-decay to same target: stationary
    r_same = fixed_exp_decay(val, half, val)
    _chk('decay to self stays the same', r_same == val, f'got {r_same}, expected {val}')

    _chk('fixed_exp_decay returns int', isinstance(fixed_exp_decay(INT_SCALE, INT_SCALE // 2, 0), int))


# ── popcount32 ────────────────────────────────────────────────────────────────

def test_popcount32():
    print('\npopcount32:')

    _chk('popcount32(0) == 0', popcount32(0) == 0)
    _chk('popcount32(1) == 1', popcount32(1) == 1)
    _chk('popcount32(0xFFFFFFFF) == 32', popcount32(0xFFFFFFFF) == 32)
    _chk('popcount32(0x55555555) == 16', popcount32(0x55555555) == 16)
    _chk('popcount32(0xAAAAAAAA) == 16', popcount32(0xAAAAAAAA) == 16)
    _chk('popcount32(2) == 1', popcount32(2) == 1)
    _chk('popcount32(3) == 2', popcount32(3) == 2)
    _chk('popcount32(7) == 3', popcount32(7) == 3)
    _chk('popcount32(8) == 1', popcount32(8) == 1)
    _chk('popcount32(0x0F0F0F0F) == 16', popcount32(0x0F0F0F0F) == 16)
    _chk('popcount32(0xF0F0F0F0) == 16', popcount32(0xF0F0F0F0) == 16)
    _chk('popcount32(0x80000000) == 1', popcount32(0x80000000) == 1)
    _chk('popcount32(0x00010000) == 1', popcount32(0x00010000) == 1)
    _chk('popcount32(0x00FF00FF) == 16', popcount32(0x00FF00FF) == 16)
    # High bits beyond 32 are masked off
    _chk('popcount32 masks beyond 32 bits', popcount32(0xFFFFFFFF + 1) == 0,
         'bit 32 should be masked')
    _chk('popcount32 returns int', isinstance(popcount32(42), int))
    _chk('popcount32(255) == 8', popcount32(255) == 8)
    _chk('popcount32(0x12345678) == known', popcount32(0x12345678) == 13)


# ── bit_interleave ────────────────────────────────────────────────────────────

def test_bit_interleave():
    print('\nbit_interleave:')

    _chk('bit_interleave(0, 0) == 0', bit_interleave(0, 0) == 0)
    _chk('bit_interleave(1, 0) == 1', bit_interleave(1, 0) == 1)
    _chk('bit_interleave(0, 1) == 2', bit_interleave(0, 1) == 2)
    _chk('bit_interleave(1, 1) == 3', bit_interleave(1, 1) == 3)
    _chk('bit_interleave(2, 0) == 4', bit_interleave(2, 0) == 4)
    _chk('bit_interleave(0, 2) == 8', bit_interleave(0, 2) == 8)
    _chk('bit_interleave(3, 0) == 5', bit_interleave(3, 0) == 5)
    _chk('bit_interleave(0, 3) == 10', bit_interleave(0, 3) == 10)
    # 0xFFFF in lower 16 bits of a: even bits of result all set = 0x55555555
    _chk('bit_interleave(0xFFFF, 0) == 0x55555555',
         bit_interleave(0xFFFF, 0) == 0x55555555)
    # 0xFFFF in lower 16 bits of b: odd bits of result all set = 0xAAAAAAAA
    _chk('bit_interleave(0, 0xFFFF) == 0xAAAAAAAA',
         bit_interleave(0, 0xFFFF) == 0xAAAAAAAA)
    _chk('bit_interleave(0xFFFF, 0xFFFF) == 0xFFFFFFFF',
         bit_interleave(0xFFFF, 0xFFFF) == 0xFFFFFFFF)
    _chk('bit_interleave returns int', isinstance(bit_interleave(1, 1), int))
    _chk('bit_interleave(4, 0) == 16', bit_interleave(4, 0) == 16)
    _chk('bit_interleave(0, 4) == 32', bit_interleave(0, 4) == 32)


# ── shannon_entropy_fixed ─────────────────────────────────────────────────────

def test_shannon_entropy():
    print('\nshannon_entropy_fixed:')

    # Certain distribution [INT_SCALE]: entropy == 0
    _chk('entropy of certain dist == 0',
         shannon_entropy_fixed([INT_SCALE]) == 0)

    # Uniform over 2: entropy = 1.0 bit
    half = INT_SCALE // 2
    h2 = shannon_entropy_fixed([half, half])
    _chk('uniform 2-symbol entropy ≈ 1.0 bit (within 1%)',
         abs(h2 - INT_SCALE) <= INT_SCALE // 100,
         f'got {h2}, expected ~{INT_SCALE}')

    # Uniform over 4: entropy = 2.0 bits (within 5%)
    quarter = INT_SCALE // 4
    h4 = shannon_entropy_fixed([quarter, quarter, quarter, quarter])
    _chk('uniform 4-symbol entropy ≈ 2.0 bits (within 5%)',
         abs(h4 - 2 * INT_SCALE) <= INT_SCALE // 10,
         f'got {h4}, expected ~{2 * INT_SCALE}')

    # Zero probs skipped without error
    h_zero = shannon_entropy_fixed([INT_SCALE, 0, 0])
    _chk('zero probs skipped — certain dist returns 0',
         h_zero == 0)

    # Entropy is non-negative
    _chk('entropy non-negative', h2 >= 0)
    _chk('entropy non-negative for 4-symbol', h4 >= 0)

    # Uniform 8: entropy = 3.0 bits (within 5%)
    eighth = INT_SCALE // 8
    h8 = shannon_entropy_fixed([eighth] * 8)
    _chk('uniform 8-symbol entropy ≈ 3.0 bits (within 5%)',
         abs(h8 - 3 * INT_SCALE) <= INT_SCALE // 5,
         f'got {h8}, expected ~{3 * INT_SCALE}')

    # More symbols → higher entropy (monotonicity of uniform distributions)
    _chk('H(uniform 4) > H(uniform 2)', h4 > h2)
    _chk('H(uniform 8) > H(uniform 4)', h8 > h4)

    # Returns int
    _chk('entropy returns int', isinstance(shannon_entropy_fixed([half, half]), int))


# ── kl_divergence_fixed ───────────────────────────────────────────────────────

def test_kl_divergence():
    print('\nkl_divergence_fixed:')

    half = INT_SCALE // 2
    quarter = INT_SCALE // 4

    # KL(P||P) = 0
    _chk('KL(P||P) = 0 for uniform 2',
         kl_divergence_fixed([half, half], [half, half]) == 0)
    _chk('KL(P||P) = 0 for uniform 4',
         kl_divergence_fixed([quarter] * 4, [quarter] * 4) == 0)

    # KL(P||Q) > 0 when P != Q
    kl = kl_divergence_fixed([half, half], [quarter, 3 * quarter])
    _chk('KL(P||Q) > 0 when P != Q', kl > 0, f'got {kl}')

    # q_i = 0 and p_i > 0 → returns INT_MAX
    _chk('KL undefined (q=0, p>0) → INT_MAX',
         kl_divergence_fixed([half, half], [INT_SCALE, 0]) == INT_MAX)

    # p_i = 0 → term skipped (no division by zero concern)
    kl_skip = kl_divergence_fixed([INT_SCALE, 0], [half, half])
    _chk('KL with p_i=0 term skipped does not raise', isinstance(kl_skip, int))

    # Non-negative
    kl2 = kl_divergence_fixed([3 * quarter, quarter], [half, half])
    _chk('KL non-negative', kl2 >= 0, f'got {kl2}')

    # Returns int
    _chk('KL returns int', isinstance(kl_divergence_fixed([half, half], [half, half]), int))


# ── cross_entropy_fixed ───────────────────────────────────────────────────────

def test_cross_entropy():
    print('\ncross_entropy_fixed:')

    half = INT_SCALE // 2
    quarter = INT_SCALE // 4

    # cross_entropy(P, P) ≈ shannon_entropy(P) (within 5%)
    ce = cross_entropy_fixed([half, half], [half, half])
    h = shannon_entropy_fixed([half, half])
    tol = max(1, h // 20)
    _chk('cross_entropy(P,P) ≈ H(P) within 5%',
         abs(ce - h) <= tol, f'ce={ce}, H={h}')

    # cross_entropy ≥ shannon_entropy (non-negativity of KL means H(P,Q) ≥ H(P))
    ce2 = cross_entropy_fixed([half, half], [quarter, 3 * quarter])
    _chk('cross_entropy >= shannon_entropy', ce2 >= h - 1,
         f'ce={ce2}, h={h}')

    # Returns INT_MAX when q=0 and p>0
    _chk('cross_entropy → INT_MAX when q=0, p>0',
         cross_entropy_fixed([half, half], [INT_SCALE, 0]) == INT_MAX)

    # p=0 terms are skipped
    ce3 = cross_entropy_fixed([INT_SCALE, 0], [half, half])
    _chk('cross_entropy with p=0 term skipped returns int', isinstance(ce3, int))

    # Non-negative
    _chk('cross_entropy non-negative', ce >= 0)

    # Returns int
    _chk('cross_entropy returns int', isinstance(ce, int))

    # 4-symbol uniform
    ce4 = cross_entropy_fixed([quarter] * 4, [quarter] * 4)
    h4 = shannon_entropy_fixed([quarter] * 4)
    _chk('cross_entropy(P,P) ≈ H(P) for 4-symbol (within 5%)',
         abs(ce4 - h4) <= max(1, h4 // 20), f'ce={ce4}, h={h4}')


# ── compression_ratio_fixed ───────────────────────────────────────────────────

def test_compression_ratio():
    print('\ncompression_ratio_fixed:')

    # ratio = 1.0 when equal sizes
    _chk('ratio == 1.0 when equal',
         compression_ratio_fixed(100, 100) == INT_SCALE,
         f'got {compression_ratio_fixed(100, 100)}')

    # ratio = 0.5 when compressed is half of original
    r_half = compression_ratio_fixed(200, 100)
    _chk('ratio ≈ 0.5 when compressed=100, original=200',
         abs(r_half - INT_SCALE // 2) <= 2,
         f'got {r_half}, expected {INT_SCALE // 2}')

    # original=0 → INT_SCALE (edge case)
    _chk('ratio == INT_SCALE when original=0',
         compression_ratio_fixed(0, 100) == INT_SCALE)

    # ratio < INT_SCALE when compressed < original
    _chk('ratio < 1.0 when compressed < original',
         compression_ratio_fixed(1000, 500) < INT_SCALE)

    # ratio > INT_SCALE when compressed > original (expansion)
    _chk('ratio > 1.0 when compressed > original',
         compression_ratio_fixed(100, 200) > INT_SCALE)

    # Returns int
    _chk('compression_ratio returns int',
         isinstance(compression_ratio_fixed(100, 50), int))

    # ratio = 2.0 when compressed is double original
    r_double = compression_ratio_fixed(100, 200)
    _chk('ratio = 2.0 when compressed is double',
         abs(r_double - 2 * INT_SCALE) <= 2,
         f'got {r_double}, expected {2 * INT_SCALE}')

    # Ratio with perfect compression (1 byte from 50)
    r_good = compression_ratio_fixed(50, 1)
    _chk('ratio is small for good compression', r_good < INT_SCALE)


# ── HardwareProfile dataclass ─────────────────────────────────────────────────

def test_hardware_profile():
    print('\nHardwareProfile:')

    hw = HardwareProfile(
        ram_bytes=8 * 1024 ** 3,
        vram_bytes=8 * 1024 ** 3,
        cpu_cores=4,
        platform='Linux',
        is_target_hardware=True,
        thermal_path=None,
    )

    _chk('ram_bytes correct', hw.ram_bytes == 8 * 1024 ** 3)
    _chk('vram_bytes correct', hw.vram_bytes == 8 * 1024 ** 3)
    _chk('cpu_cores correct', hw.cpu_cores == 4)
    _chk('platform is string', isinstance(hw.platform, str))
    _chk('platform value correct', hw.platform == 'Linux')
    _chk('is_target_hardware is bool', isinstance(hw.is_target_hardware, bool))
    _chk('is_target_hardware is True', hw.is_target_hardware is True)
    _chk('thermal_path can be None', hw.thermal_path is None)

    # Frozen — cannot mutate
    expect_raises('frozen: cannot set ram_bytes', (AttributeError, TypeError),
                  lambda: setattr(hw, 'ram_bytes', 0))
    expect_raises('frozen: cannot set cpu_cores', (AttributeError, TypeError),
                  lambda: setattr(hw, 'cpu_cores', 99))

    # thermal_path can be a str
    hw2 = HardwareProfile(
        ram_bytes=4 * 1024 ** 3,
        vram_bytes=4 * 1024 ** 3,
        cpu_cores=8,
        platform='Windows',
        is_target_hardware=False,
        thermal_path='/sys/class/hwmon/hwmon0/temp1_input',
    )
    _chk('thermal_path can be str', isinstance(hw2.thermal_path, str))
    _chk('is_target_hardware False', hw2.is_target_hardware is False)
    _chk('different platform', hw2.platform == 'Windows')
    _chk('fewer cpu_cores', hw2.cpu_cores == 8)

    # Equality based on fields
    hw3 = HardwareProfile(
        ram_bytes=8 * 1024 ** 3,
        vram_bytes=8 * 1024 ** 3,
        cpu_cores=4,
        platform='Linux',
        is_target_hardware=True,
        thermal_path=None,
    )
    _chk('equal profiles compare equal', hw == hw3)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== HARDWARE CONFIG TESTS ===')
    test_constants()
    test_to_from_fixed()
    test_fixed_mul()
    test_fixed_clamp()
    test_fixed_div()
    test_fixed_sqrt()
    test_fixed_exp_decay()
    test_popcount32()
    test_bit_interleave()
    test_shannon_entropy()
    test_kl_divergence()
    test_cross_entropy()
    test_compression_ratio()
    test_hardware_profile()
    print(f'\n{"=" * 33}')
    print(f'PASS: {PASS}  FAIL: {FAIL}')
    if FAIL > 0:
        print('RESULT: FAIL')
        sys.exit(1)
    print('RESULT: PASS')
