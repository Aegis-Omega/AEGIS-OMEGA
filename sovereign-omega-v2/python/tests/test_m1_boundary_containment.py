"""
AEGIS M1 boundary-containment regression.

Reads the production core_matrix.py source and executes only the
CoreMatrix.process_event method through AST extraction. This binds the test to
the production control flow without importing core_matrix.py (which would pull
in hardware dependencies) or allocating its default 4 GB bytearray.
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


def test_small_nondivisible_wrap():
    process_event, matrix, calls = _matrix(bytearray(128), 3, 3)
    before = bytes(matrix._m1_region)
    result = process_event(matrix, b'', b'\x01', b'')

    _check('nondivisible wrap blocks', result['status'] == 'M1_BOUNDARY_BLOCKED')
    _check('blocked sequence unchanged', matrix._sequence == 3)
    _check('blocked era unchanged', matrix._era == 4)
    _check('blocked M1 bytes unchanged', bytes(matrix._m1_region) == before)
    _check('blocked path has no downstream calls', calls == [])


def test_alignment_alone_is_insufficient():
    # 40 divides 120, but sequence=2 starts at byte 80 and a one-byte payload
    # requires 121 bytes. The payload span still crosses the region boundary.
    process_event, matrix, calls = _matrix(bytearray(120), 2, 3)
    result = process_event(matrix, b'x', b'\x01', b'')

    _check('aligned ring payload overrun blocks', result['status'] == 'M1_BOUNDARY_BLOCKED')
    _check('aligned ring era unchanged', matrix._era == 4)
    _check('aligned ring has no downstream calls', calls == [])


def test_cloud_profile_exact_wrap():
    cloud_m1 = 134_217_728  # 256 MiB arena * 0.50
    capacity = cloud_m1 // 40
    process_event, matrix, calls = _matrix(_SizedRegion(cloud_m1), capacity, capacity)
    result = process_event(matrix, b'', b'\x01', b'')

    _check('Cloud Run modulo drift blocks', result['status'] == 'M1_BOUNDARY_BLOCKED')
    _check('Cloud Run drift sequence stable', matrix._sequence == 3_355_443)
    _check('Cloud Run drift has no downstream calls', calls == [])


def test_cloud_profile_payload_blocks_one_slot_earlier():
    cloud_m1 = 134_217_728
    capacity = cloud_m1 // 40
    process_event, matrix, calls = _matrix(
        _SizedRegion(cloud_m1),
        capacity - 1,
        capacity,
    )
    result = process_event(matrix, b'event_3355442', b'\x01', b'')

    _check('Cloud Run payload pre-wrap blocks', result['status'] == 'M1_BOUNDARY_BLOCKED')
    _check('Cloud Run payload sequence stable', matrix._sequence == 3_355_442)
    _check('Cloud Run payload has no downstream calls', calls == [])


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
    print('AEGIS M1 boundary containment regression')
    test_small_nondivisible_wrap()
    test_alignment_alone_is_insufficient()
    test_cloud_profile_exact_wrap()
    test_cloud_profile_payload_blocks_one_slot_earlier()
    test_normal_path_still_executes()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
