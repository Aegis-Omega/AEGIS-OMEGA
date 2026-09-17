"""
AEGIS M1 boundary-containment regression after fixed-record cutover.

Reads the production CoreMatrix.process_event method through AST extraction.
The v2 contract stores exactly one 40-byte record per event, so payload length
must not affect M1 slot fit. Fail-closed containment remains for regions that
cannot hold even one complete M1 record.
"""

import ast
import pathlib
import threading
from types import SimpleNamespace
from typing import Dict

CORE_MATRIX = pathlib.Path(__file__).resolve().parents[1] / 'core_matrix.py'
PASS = 0
FAIL = 0


def _check(name: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        print(f'  FAIL  {name}')


def _load_process_event():
    tree = ast.parse(CORE_MATRIX.read_text())
    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == 'CoreMatrix'
    )
    fn = next(
        node for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == 'process_event'
    )
    m1_entry_assignment = next(
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == 'M1_ENTRY_BYTES'
            for target in node.targets
        )
    )
    constants_module = ast.Module(body=[m1_entry_assignment], type_ignores=[])
    ast.fix_missing_locations(constants_module)
    constants = {}
    exec(compile(constants_module, str(CORE_MATRIX), 'exec'), constants)

    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)

    frozen = SimpleNamespace(value='frozen')
    recovering = SimpleNamespace(value='recovering')
    active = SimpleNamespace(value='active')
    epoch_state = SimpleNamespace(
        FROZEN=frozen,
        RECOVERING=recovering,
        ACTIVE=active,
    )
    calls = []

    def m1(_state, payload, sequence):
        calls.append(('M1', sequence, len(payload)))
        return sequence + 1, b'\x11' * 32

    def m2(_state, _verifier, confidence, sequence):
        calls.append(('M2', sequence))
        return 0, confidence

    def m3(_state, context, _w_scale):
        calls.append(('M3', len(context)))
        return context, 0

    namespace = {
        'Dict': Dict,
        'EpochState': epoch_state,
        'M1': m1,
        'M2': m2,
        'M3': m3,
        'M1_ENTRY_BYTES': constants['M1_ENTRY_BYTES'],
        'INT_SCALE': 65536,
        'from_fixed': lambda value: value / 65536,
    }
    exec(compile(module, str(CORE_MATRIX), 'exec'), namespace)
    return namespace['process_event'], epoch_state, calls


class _SizedRegion:
    """Length-only region; avoids allocating Cloud/4GB-sized bytearrays."""

    def __init__(self, length: int):
        self.length = length

    def __len__(self):
        return self.length


class _Calibrator:
    def get_w_scale(self, _name):
        return 65536

    def calibrate_epoch(self, _epoch):
        return None

    def compute_drift_index(self):
        return 0


class _Matrix:
    pass


def _matrix(region, sequence: int, capacity: int):
    process_event, states, calls = _load_process_event()
    matrix = _Matrix()
    matrix._lock = threading.RLock()
    matrix._failsafe = SimpleNamespace(state=states.ACTIVE)
    matrix._m1_region = region
    matrix._m2_region = bytearray(32)
    matrix._m3_region = bytearray(32)
    matrix._sequence = sequence
    matrix._epoch = 9
    matrix._era = 4
    matrix._m1_era_capacity = capacity
    matrix._event_cb = lambda *args: calls.append(('EVENT', args))
    matrix._calibrator = _Calibrator()
    matrix._total_vcg_error_fixed = 0
    matrix._total_processed = 0
    return process_event, matrix, calls


def test_subrecord_region_fails_closed():
    process_event, matrix, calls = _matrix(bytearray(39), 0, 1)
    result = process_event(matrix, b'x' * 100_000, b'\x01', b'')

    _check('region smaller than one record blocks', result['status'] == 'M1_BOUNDARY_BLOCKED')
    _check('subrecord block leaves sequence unchanged', matrix._sequence == 0)
    _check('subrecord block leaves era unchanged', matrix._era == 4)
    _check('subrecord block has no downstream calls', calls == [])


def test_nondivisible_region_wrap_uses_logical_slots():
    process_event, matrix, calls = _matrix(bytearray(128), 3, 3)
    result = process_event(matrix, b'x' * 100_000, b'\x01', b'ctx')

    _check('nondivisible logical wrap succeeds', result['status'] == 'OK')
    _check('nondivisible wrap advances sequence', matrix._sequence == 4)
    _check('nondivisible wrap increments era once', matrix._era == 5)
    _check(
        'nondivisible wrap reaches event plus M1/M2/M3',
        [call[0] for call in calls] == ['EVENT', 'M1', 'M2', 'M3'],
    )


def test_payload_length_does_not_change_slot_fit():
    process_event, matrix, calls = _matrix(bytearray(120), 2, 3)
    result = process_event(matrix, b'x' * 100_000, b'\x01', b'ctx')

    _check('large payload digest fits fixed 40-byte record', result['status'] == 'OK')
    _check('large payload path advances sequence', matrix._sequence == 3)
    _check('large payload path leaves era unchanged before wrap', matrix._era == 4)
    _check(
        'large payload path reaches M1/M2/M3',
        [call[0] for call in calls] == ['M1', 'M2', 'M3'],
    )


def test_cloud_profile_exact_wrap():
    cloud_m1 = 134_217_728
    capacity = cloud_m1 // 40
    process_event, matrix, calls = _matrix(_SizedRegion(cloud_m1), capacity, capacity)
    result = process_event(matrix, b'x' * 100_000, b'\x01', b'ctx')

    _check('Cloud Run exact logical wrap succeeds', result['status'] == 'OK')
    _check('Cloud Run wrap advances sequence', matrix._sequence == capacity + 1)
    _check('Cloud Run wrap increments era once', matrix._era == 5)
    _check(
        'Cloud Run wrap reaches event plus M1/M2/M3',
        [call[0] for call in calls] == ['EVENT', 'M1', 'M2', 'M3'],
    )


def test_cloud_profile_last_slot_large_payload():
    cloud_m1 = 134_217_728
    capacity = cloud_m1 // 40
    process_event, matrix, calls = _matrix(
        _SizedRegion(cloud_m1),
        capacity - 1,
        capacity,
    )
    result = process_event(matrix, b'x' * 100_000, b'\x01', b'ctx')

    _check('Cloud Run last logical slot accepts large payload digest', result['status'] == 'OK')
    _check('Cloud Run last slot advances to wrap sequence', matrix._sequence == capacity)
    _check('Cloud Run last slot leaves era unchanged', matrix._era == 4)
    _check(
        'Cloud Run last slot reaches M1/M2/M3',
        [call[0] for call in calls] == ['M1', 'M2', 'M3'],
    )


def test_normal_path_still_executes():
    process_event, matrix, calls = _matrix(bytearray(128), 1, 3)
    result = process_event(matrix, b'abc', b'\x01', b'ctx')

    _check('ordinary in-bounds path returns OK', result['status'] == 'OK')
    _check('ordinary path increments sequence', matrix._sequence == 2)
    _check(
        'ordinary path reaches M1 then M2 then M3',
        [call[0] for call in calls] == ['M1', 'M2', 'M3'],
    )


if __name__ == '__main__':
    print('AEGIS M1 fixed-record boundary regression')
    test_subrecord_region_fails_closed()
    test_nondivisible_region_wrap_uses_logical_slots()
    test_payload_length_does_not_change_slot_fit()
    test_cloud_profile_exact_wrap()
    test_cloud_profile_last_slot_large_payload()
    test_normal_path_still_executes()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
