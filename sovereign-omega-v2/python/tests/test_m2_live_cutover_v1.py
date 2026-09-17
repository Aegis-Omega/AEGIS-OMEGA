"""
AEGIS M2 live cutover v1 — preregistered acceptance tests.

Binds production M2 via AST extraction and compares storage against the inert
M2 Slot Contract V1. The returned calibration values are checked independently
so the live transition changes addressing only.
"""

import ast
import hashlib
import importlib.util
import pathlib
import threading
from types import SimpleNamespace
from typing import Dict, Tuple

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


class SparseRegion:
    """Sparse mutable byte sequence with a large logical length."""

    def __init__(self, length: int):
        self.length = length
        self.data = {}

    def __len__(self):
        return self.length

    def _bounds(self, key):
        if not isinstance(key, slice) or key.step not in (None, 1):
            raise TypeError('SparseRegion supports contiguous slices only')
        start = 0 if key.start is None else key.start
        stop = self.length if key.stop is None else key.stop
        if start < 0 or stop < start or stop > self.length:
            raise IndexError(f'slice out of bounds: {start}:{stop} length={self.length}')
        return start, stop

    def __getitem__(self, key):
        start, stop = self._bounds(key)
        return bytes(self.data.get(i, 0) for i in range(start, stop))

    def __setitem__(self, key, value):
        start, stop = self._bounds(key)
        value = bytes(value)
        if len(value) != stop - start:
            raise ValueError('slice assignment length mismatch')
        for offset, byte in enumerate(value, start):
            if byte:
                self.data[offset] = byte
            else:
                self.data.pop(offset, None)


def _load_reference():
    spec = importlib.util.spec_from_file_location('m2_slot_contract_v1', REFERENCE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_m2():
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


def _expected_values(verifier_result: bytes, confidence_fixed: int) -> tuple[int, int]:
    confidence = max(0, min(INT_SCALE, confidence_fixed))
    actual_correct = int(verifier_result[0]) if verifier_result else 0
    actual_fixed = INT_SCALE if actual_correct else 0
    vcg_error = abs(confidence - actual_fixed)
    gate_lcb = max(0, confidence - ((2 * vcg_error) >> 1))
    return vcg_error, gate_lcb


def test_m2_values_unchanged_and_storage_matches_reference():
    ref = _load_reference()
    m2 = _load_m2()

    cases = (
        (b'', 0, 0),
        (b'\x00', 0x1234, 1),
        (b'\x01', INT_SCALE, 2),
        (b'\x00\x99', INT_SCALE // 2, 9),
        (b'\x01\x02\x03', INT_SCALE + 999, 10),
    )

    for verifier, confidence, sequence in cases:
        state = bytearray(80)
        actual = m2(state, verifier, confidence, sequence)
        expected = _expected_values(verifier, confidence)
        offset = ref.slot_offset(sequence, ref.slot_capacity(len(state)))
        expected_entry = ref.encode_entry(*expected)

        _check(f'seq={sequence}: return values unchanged', actual == expected)
        _check(f'seq={sequence}: canonical slot bytes match', bytes(state[offset:offset + 8]) == expected_entry)
        _check(f'seq={sequence}: canonical slot is aligned', offset % 8 == 0)


def test_same_sequence_is_independent_of_verifier_length():
    ref = _load_reference()
    m2 = _load_m2()
    sequence = 7
    capacity = 10
    expected_offset = ref.slot_offset(sequence, capacity)

    one = bytearray(80)
    two = bytearray(80)
    result_one = m2(one, b'\x00', 0x1234, sequence)
    result_two = m2(two, b'\x00\x99', 0x1234, sequence)

    _check('same first verifier byte keeps return values identical', result_one == result_two)
    _check('same sequence produces byte-identical M2 state across verifier lengths', bytes(one) == bytes(two))
    _check('same sequence record is at reference slot', bytes(one[expected_offset:expected_offset + 8]) == ref.encode_entry(*result_one))


def test_consecutive_sequences_cover_disjoint_slots_until_wrap():
    ref = _load_reference()
    m2 = _load_m2()
    state = bytearray(80)
    capacity = ref.slot_capacity(len(state))

    for sequence in range(capacity):
        values = m2(state, bytes([sequence % 2]), 0x1234 + sequence, sequence)
        offset = ref.slot_offset(sequence, capacity)
        _check(
            f'seq={sequence}: record occupies its unique slot',
            bytes(state[offset:offset + 8]) == ref.encode_entry(*values),
        )

    offsets = [ref.slot_offset(sequence, capacity) for sequence in range(capacity)]
    _check('first cycle has one unique offset per sequence', len(set(offsets)) == capacity)
    _check('all first-cycle offsets are aligned', all(offset % 8 == 0 for offset in offsets))

    wrapped_values = m2(state, b'\x01', 0x1234, capacity)
    _check('sequence capacity wraps exactly to byte zero', ref.slot_offset(capacity, capacity) == 0)
    _check('wrapped record is written at byte zero', bytes(state[0:8]) == ref.encode_entry(*wrapped_values))


def test_live_geometries_use_last_complete_slot_and_leave_tail_untouched():
    ref = _load_reference()
    m2 = _load_m2()

    for name, region_bytes in (
        ('default', 1_288_490_188),
        ('cloud', 80_530_636),
    ):
        region = SparseRegion(region_bytes)
        capacity = ref.slot_capacity(region_bytes)
        last_sequence = capacity - 1
        values = m2(region, b'\x01', INT_SCALE, last_sequence)
        last_offset = ref.slot_offset(last_sequence, capacity)
        _check(f'{name}: last complete slot contains record', bytes(region[last_offset:last_offset + 8]) == ref.encode_entry(*values))
        _check(f'{name}: last record ends four bytes before region end', region_bytes - (last_offset + 8) == 4)
        _check(f'{name}: four tail bytes remain untouched', bytes(region[region_bytes - 4:region_bytes]) == b'\x00' * 4)

        wrap_values = m2(region, b'\x00', 0x1234, capacity)
        _check(f'{name}: wrap writes byte-zero slot', bytes(region[0:8]) == ref.encode_entry(*wrap_values))


class _Calibrator:
    def get_w_scale(self, _name):
        return INT_SCALE

    def calibrate_epoch(self, _epoch):
        return None

    def compute_drift_index(self):
        return 0


class _FailsafeState:
    value = 'active'


class _Failsafe:
    state = _FailsafeState()


def _load_controller_methods(m2):
    tree = ast.parse(CORE_MATRIX.read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'CoreMatrix')
    wanted = {'process_event', 'receive_gate_signal'}
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.Module(body=methods, type_ignores=[])
    ast.fix_missing_locations(module)

    frozen = SimpleNamespace(value='frozen')
    recovering = SimpleNamespace(value='recovering')
    active = _FailsafeState()
    epoch_state = SimpleNamespace(FROZEN=frozen, RECOVERING=recovering, ACTIVE=active)

    def m1_stub(_state, _payload, sequence):
        return sequence + 1, b'\x11' * 32

    def m3_stub(_state, context, _w_scale):
        return context, 0

    ns = {
        'Dict': Dict,
        'EpochState': epoch_state,
        'M1': m1_stub,
        'M2': m2,
        'M3': m3_stub,
        'M1_ENTRY_BYTES': 40,
        'INT_SCALE': INT_SCALE,
        'from_fixed': lambda value: value / INT_SCALE,
    }
    exec(compile(module, str(CORE_MATRIX), 'exec'), ns)
    return ns['process_event'], ns['receive_gate_signal'], active


def test_process_event_and_gate_signal_share_returned_sequence_slot():
    ref = _load_reference()
    m2 = _load_m2()
    process_event, receive_gate_signal, active = _load_controller_methods(m2)

    matrix = SimpleNamespace(
        _lock=threading.RLock(),
        _failsafe=SimpleNamespace(state=active),
        _m1_region=bytearray(80),
        _m2_region=bytearray(80),
        _m3_region=bytearray(80),
        _sequence=4,
        _epoch=0,
        _era=0,
        _m1_era_capacity=1000,
        _event_cb=None,
        _calibrator=_Calibrator(),
        _total_vcg_error_fixed=0,
        _total_processed=0,
    )

    result = process_event(matrix, b'payload', b'\x01', b'ctx')
    logical_sequence = result['sequence']
    capacity = ref.slot_capacity(len(matrix._m2_region))
    offset = ref.slot_offset(logical_sequence, capacity)
    before_gate_signal = bytes(matrix._m2_region)

    _check('process_event returns incremented logical sequence', logical_sequence == 5)
    _check('process_event writes returned sequence slot', before_gate_signal[offset:offset + 8] == ref.encode_entry(0, INT_SCALE))

    receive_gate_signal(matrix, 'proposal', False, logical_sequence)
    after_gate_signal = bytes(matrix._m2_region)
    _check('gate signal overwrites the same logical sequence slot', after_gate_signal[offset:offset + 8] == ref.encode_entry(0, 0))
    _check('bytes outside the shared slot remain unchanged', before_gate_signal[:offset] == after_gate_signal[:offset] and before_gate_signal[offset + 8:] == after_gate_signal[offset + 8:])


if __name__ == '__main__':
    print('AEGIS M2 live cutover v1')
    test_m2_values_unchanged_and_storage_matches_reference()
    test_same_sequence_is_independent_of_verifier_length()
    test_consecutive_sequences_cover_disjoint_slots_until_wrap()
    test_live_geometries_use_last_complete_slot_and_leave_tail_untouched()
    test_process_event_and_gate_signal_share_returned_sequence_slot()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
