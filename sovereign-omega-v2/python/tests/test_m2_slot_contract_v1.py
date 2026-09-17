"""
AEGIS M2 Slot Contract V1 — diagnostic/reference regression.

Separates the shipped M2 addressing behavior from the smallest coherent
fixed-width slot contract. The reference module is inert and is not imported by
production code.
"""

import ast
import importlib.util
import pathlib
from typing import Tuple

PYTHON_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_MATRIX = PYTHON_DIR / 'core_matrix.py'
REFERENCE = PYTHON_DIR / 'm2_slot_contract_v1.py'

PASS = 0
FAIL = 0
INT_SCALE = 65536


def _check(name: str, condition: bool, detail: str = '') -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        suffix = f': {detail}' if detail else ''
        print(f'  FAIL  {name}{suffix}')


def _load_current_m2():
    tree = ast.parse(CORE_MATRIX.read_text())
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'M2'
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {
        'Tuple': Tuple,
        'INT_SCALE': INT_SCALE,
        'fixed_clamp': lambda value, low, high: max(low, min(high, value)),
    }
    exec(compile(module, str(CORE_MATRIX), 'exec'), ns)
    return ns['M2']


def _load_reference():
    if not REFERENCE.exists():
        return None
    spec = importlib.util.spec_from_file_location('m2_slot_contract_v1', REFERENCE)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record_bytes(vcg_error_fixed: int, gate_lcb_fixed: int) -> bytes:
    return (
        vcg_error_fixed.to_bytes(4, 'little', signed=False)
        + gate_lcb_fixed.to_bytes(4, 'little', signed=False)
    )


def test_current_m2_writes_unaligned_byte_offsets():
    m2 = _load_current_m2()
    state = bytearray(80)  # 10 logical 8-byte records
    vcg, gate = m2(state, b'\x00', 0x1234, sequence=0)
    expected = _record_bytes(vcg, gate)
    current_offset = (0 * 8 + 1) % (len(state) // 8)

    _check('current sequence 0 starts at byte 1', current_offset == 1)
    _check('current sequence 0 start is not 8-byte aligned', current_offset % 8 != 0)
    _check('current M2 actually writes at byte 1', bytes(state[1:9]) == expected)
    _check('canonical slot-zero bytes do not contain the full record', bytes(state[0:8]) != expected)


def test_current_m2_same_sequence_moves_with_verifier_length():
    m2 = _load_current_m2()
    sequence = 2
    state_one = bytearray(80)
    state_two = bytearray(80)

    result_one = m2(state_one, b'\x00', 0x1234, sequence=sequence)
    result_two = m2(state_two, b'\x00\x99', 0x1234, sequence=sequence)
    record_one = _record_bytes(*result_one)
    record_two = _record_bytes(*result_two)
    offset_one = (sequence * 8 + 1) % (len(state_one) // 8)
    offset_two = (sequence * 8 + 2) % (len(state_two) // 8)

    _check('same first verifier byte yields same M2 values', result_one == result_two)
    _check('verifier length changes current byte location', offset_one != offset_two)
    _check('len=1 record appears at current offset', bytes(state_one[offset_one:offset_one + 8]) == record_one)
    _check('len=2 record appears at different current offset', bytes(state_two[offset_two:offset_two + 8]) == record_two)


def test_current_m2_small_ring_collision_witness():
    # For L=80, q=L/8=10 and verifier length 1:
    #   start(n) = (8*n + 1) mod 10
    # so n=0 and n=5 both map to byte 1.
    starts = [((n * 8 + 1) % 10) for n in range(10)]
    _check('current small-ring starts repeat before 10 logical slots', len(set(starts)) < 10)
    _check('sequence 0 and 5 collide exactly', starts[0] == starts[5] == 1)
    _check('all observed starts remain inside first ten bytes', max(starts) < 10)
    _check('all len=1 starts are unaligned', all(offset % 8 != 0 for offset in starts))


def test_live_m2_geometry_has_four_tail_bytes():
    default_m2 = 1_288_490_188
    cloud_m2 = 80_530_636
    _check('default M2 has four non-record tail bytes', default_m2 % 8 == 4)
    _check('Cloud M2 has four non-record tail bytes', cloud_m2 % 8 == 4)
    _check('default M2 slot capacity is exact floor quotient', default_m2 // 8 == 161_061_273)
    _check('Cloud M2 slot capacity is exact floor quotient', cloud_m2 // 8 == 10_066_329)


def test_reference_contract_exists_and_is_fixed_width():
    ref = _load_reference()
    _check('reference M2 slot module exists', ref is not None)
    if ref is None:
        return

    _check('M2 entry width is exactly 8 bytes', ref.M2_ENTRY_BYTES == 8)
    entry = ref.encode_entry(0x12345678, 0x90ABCDEF)
    _check('encoded M2 entry is exactly 8 bytes', len(entry) == 8)
    vcg, gate = ref.decode_entry(entry)
    _check('M2 entry round-trip preserves vcg field', vcg == 0x12345678)
    _check('M2 entry round-trip preserves gate field', gate == 0x90ABCDEF)


def test_reference_slot_address_is_sequence_only():
    ref = _load_reference()
    if ref is None:
        _check('reference slot addressing available', False, 'reference module missing')
        return

    capacity = 10
    offsets = [ref.slot_offset(n, capacity) for n in range(capacity)]
    _check('reference first cycle covers ten distinct slots', len(set(offsets)) == capacity)
    _check('reference offsets are exactly 8-byte aligned', all(offset % 8 == 0 for offset in offsets))
    _check('reference first slot starts at byte zero', offsets[0] == 0)
    _check('reference last slot starts at byte 72', offsets[-1] == 72)
    _check('reference wrap returns to byte zero', ref.slot_offset(capacity, capacity) == 0)

    # Verifier bytes determine the record values, never its address.
    _check('reference address accepts sequence only', ref.slot_offset(7, capacity) == 56)


def test_reference_live_geometry_uses_all_complete_slots():
    ref = _load_reference()
    if ref is None:
        _check('reference live geometry available', False, 'reference module missing')
        return

    for name, region_bytes, expected_capacity in (
        ('default', 1_288_490_188, 161_061_273),
        ('cloud', 80_530_636, 10_066_329),
    ):
        capacity = ref.slot_capacity(region_bytes)
        _check(f'{name}: capacity matches floor quotient', capacity == expected_capacity)
        last = ref.slot_offset(capacity - 1, capacity)
        _check(f'{name}: final record is fully in bounds', last + 8 <= region_bytes)
        _check(f'{name}: exactly four tail bytes remain', region_bytes - (last + 8) == 4)
        _check(f'{name}: logical wrap returns to zero', ref.slot_offset(capacity, capacity) == 0)


if __name__ == '__main__':
    print('AEGIS M2 slot contract v1')
    test_current_m2_writes_unaligned_byte_offsets()
    test_current_m2_same_sequence_moves_with_verifier_length()
    test_current_m2_small_ring_collision_witness()
    test_live_m2_geometry_has_four_tail_bytes()
    test_reference_contract_exists_and_is_fixed_width()
    test_reference_slot_address_is_sequence_only()
    test_reference_live_geometry_uses_all_complete_slots()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
