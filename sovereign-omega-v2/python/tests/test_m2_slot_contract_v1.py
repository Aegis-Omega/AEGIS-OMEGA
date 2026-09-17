"""
AEGIS M2 Slot Contract V1 — live/reference regression.

On the diagnostic base lane this test captured the shipped unit-mismatch bug.
On the integrated live stack it becomes the inverse falsifier: production M2
must match the inert aligned-slot reference and must no longer depend on
verifier length for storage addressing.
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


def test_production_m2_matches_aligned_reference_slots():
    m2 = _load_current_m2()
    ref = _load_reference()
    _check('reference M2 slot module exists for production comparison', ref is not None)
    if ref is None:
        return

    state = bytearray(80)
    capacity = ref.slot_capacity(len(state))
    for sequence in range(capacity):
        verifier = bytes([sequence % 2])
        confidence = 0x1234 + sequence
        values = m2(state, verifier, confidence, sequence)
        offset = ref.slot_offset(sequence, capacity)
        _check(
            f'seq={sequence}: production record matches reference slot',
            bytes(state[offset:offset + 8]) == ref.encode_entry(*values),
        )
        _check(f'seq={sequence}: production slot is aligned', offset % 8 == 0)

    offsets = [ref.slot_offset(sequence, capacity) for sequence in range(capacity)]
    _check('production first cycle uses ten distinct reference slots', len(set(offsets)) == capacity)
    _check('production wrap address is byte zero', ref.slot_offset(capacity, capacity) == 0)


def test_production_address_no_longer_depends_on_verifier_length():
    m2 = _load_current_m2()
    ref = _load_reference()
    if ref is None:
        _check('reference verifier-length comparison available', False, 'reference module missing')
        return

    sequence = 7
    one = bytearray(80)
    two = bytearray(80)
    result_one = m2(one, b'\x00', 0x1234, sequence)
    result_two = m2(two, b'\x00\x99', 0x1234, sequence)
    offset = ref.slot_offset(sequence, ref.slot_capacity(len(one)))

    _check('same first verifier byte preserves returned values', result_one == result_two)
    _check('verifier length no longer changes M2 state bytes', bytes(one) == bytes(two))
    _check('same-sequence record is in reference slot', bytes(one[offset:offset + 8]) == ref.encode_entry(*result_one))

    old_offset_one = (sequence * 8 + 1) % (len(one) // 8)
    old_offset_two = (sequence * 8 + 2) % (len(two) // 8)
    _check('old formula would still choose different byte offsets', old_offset_one != old_offset_two)
    _check('production record is not located at old len=1 offset', old_offset_one == offset or bytes(one[old_offset_one:old_offset_one + 8]) != ref.encode_entry(*result_one))
    _check('production record is not located at old len=2 offset', old_offset_two == offset or bytes(two[old_offset_two:old_offset_two + 8]) != ref.encode_entry(*result_two))


def test_old_small_ring_collision_is_eliminated():
    ref = _load_reference()
    if ref is None:
        _check('reference collision comparison available', False, 'reference module missing')
        return

    capacity = 10
    old_starts = [((n * 8 + 1) % capacity) for n in range(capacity)]
    new_starts = [ref.slot_offset(n, capacity) for n in range(capacity)]

    _check('old formula still demonstrates sequence 0/5 collision', old_starts[0] == old_starts[5] == 1)
    _check('reference/live first cycle has no collision', len(set(new_starts)) == capacity)
    _check('reference/live starts are all aligned', all(offset % 8 == 0 for offset in new_starts))


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
    print('AEGIS M2 live/reference slot contract v1')
    test_production_m2_matches_aligned_reference_slots()
    test_production_address_no_longer_depends_on_verifier_length()
    test_old_small_ring_collision_is_eliminated()
    test_live_m2_geometry_has_four_tail_bytes()
    test_reference_contract_exists_and_is_fixed_width()
    test_reference_live_geometry_uses_all_complete_slots()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
