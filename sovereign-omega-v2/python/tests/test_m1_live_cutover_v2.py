"""
AEGIS M1 live cutover v2 — preregistered acceptance tests.

The tests avoid allocating 4 GB / 256 MiB by using a sparse byte-region with
real logical length. They bind production M1 and process_event via AST extraction,
and bind ledger_persist.py directly.
"""

import ast
import hashlib
import importlib.util
import pathlib
import tempfile
import threading
from types import SimpleNamespace
from typing import Dict, Tuple

PYTHON_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_MATRIX = PYTHON_DIR / 'core_matrix.py'
LEDGER_PERSIST = PYTHON_DIR / 'ledger_persist.py'
REFERENCE = PYTHON_DIR / 'm1_record_contract_v2.py'

PASS = 0
FAIL = 0


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
    spec = importlib.util.spec_from_file_location('m1_record_contract_v2', REFERENCE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_ledger():
    spec = importlib.util.spec_from_file_location('ledger_persist_live_test', LEDGER_PERSIST)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_production_m1_namespace():
    tree = ast.parse(CORE_MATRIX.read_text())
    constant_names = {
        'M1_SEQUENCE_BYTES',
        'M1_HASH_BYTES',
        'M1_ENTRY_BYTES',
        'M1_GENESIS_HASH',
    }
    body = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = {
                target.id for target in node.targets
                if isinstance(target, ast.Name)
            }
            if targets & constant_names:
                body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == 'M1':
            body.append(node)
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {'hashlib': hashlib, 'Tuple': Tuple}
    exec(compile(module, str(CORE_MATRIX), 'exec'), ns)
    return ns


def _extract_m1():
    return _load_production_m1_namespace()['M1']


def _extract_process_event(m1):
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
    epoch_state = SimpleNamespace(FROZEN=frozen, RECOVERING=recovering, ACTIVE=active)
    calls = []

    def traced_m1(state, payload, sequence):
        calls.append(('M1', sequence, len(payload)))
        return m1(state, payload, sequence)

    def m2(_state, _verifier, confidence, sequence):
        calls.append(('M2', sequence))
        return 0, confidence

    def m3(_state, context, _w_scale):
        calls.append(('M3', len(context)))
        return context, 0

    production_ns = _load_production_m1_namespace()
    ns = {
        'Dict': Dict,
        'EpochState': epoch_state,
        'M1': traced_m1,
        'M2': m2,
        'M3': m3,
        'M1_ENTRY_BYTES': production_ns['M1_ENTRY_BYTES'],
        'INT_SCALE': 65536,
        'from_fixed': lambda value: value / 65536,
    }
    exec(compile(module, str(CORE_MATRIX), 'exec'), ns)
    return ns['process_event'], epoch_state, calls


class _Calibrator:
    def get_w_scale(self, _name):
        return 65536

    def calibrate_epoch(self, _epoch):
        return None

    def compute_drift_index(self):
        return 0


class Matrix:
    def __init__(self, region, sequence=0, epoch=0, era=0):
        self._m1_region = region
        self._m2_region = bytearray(32)
        self._m3_region = bytearray(32)
        self._sequence = sequence
        self._epoch = epoch
        self._era = era
        self._lock = threading.RLock()
        self._failsafe = SimpleNamespace(state=SimpleNamespace(value='active'))
        self._calibrator = _Calibrator()
        self._event_cb = None
        self._total_vcg_error_fixed = 0
        self._total_processed = 0
        self._m1_era_capacity = max(1, len(region) // 40)


def _seed_previous(ref, region, sequence, chain_hash):
    capacity = len(region) // ref.M1_ENTRY_BYTES
    prev_sequence = sequence - 1
    offset = ref.slot_offset(prev_sequence, capacity)
    region[offset:offset + ref.M1_ENTRY_BYTES] = ref.encode_entry(prev_sequence, chain_hash)


def test_production_m1_matches_reference_contract():
    ref = _load_reference()
    m1 = _extract_m1()
    state = SparseRegion(400)
    previous = ref.M1_GENESIS_HASH

    for sequence, payload in enumerate((b'a', b'b', b'c')):
        expected = ref.next_chain_hash(previous, payload)
        next_sequence, actual = m1(state, payload, sequence)
        capacity = len(state) // ref.M1_ENTRY_BYTES
        offset = ref.slot_offset(sequence, capacity)
        entry = bytes(state[offset:offset + ref.M1_ENTRY_BYTES])

        _check(f'M1 sequence {sequence} increments once', next_sequence == sequence + 1)
        _check(f'M1 sequence {sequence} hash matches reference', actual == expected)
        _check(
            f'M1 sequence {sequence} stores canonical chain entry',
            entry == ref.encode_entry(sequence, expected),
        )
        previous = expected


def test_process_event_fixed_record_wrap_accepts_large_payload():
    ref = _load_reference()
    m1 = _extract_m1()
    process_event, states, calls = _extract_process_event(m1)
    cloud_bytes = 134_217_728
    capacity = cloud_bytes // ref.M1_ENTRY_BYTES
    region = SparseRegion(cloud_bytes)
    _seed_previous(ref, region, capacity - 1, b'\x33' * 32)

    matrix = Matrix(region, sequence=capacity - 1, epoch=7, era=2)
    matrix._failsafe = SimpleNamespace(state=states.ACTIVE)
    result = process_event(matrix, b'x' * 100_000, b'\x01', b'ctx')

    _check('last logical slot accepts large payload digest', result['status'] == 'OK')
    _check('last logical slot advances to wrap sequence', matrix._sequence == capacity)
    _check('last logical slot reaches M1/M2/M3', [c[0] for c in calls] == ['M1', 'M2', 'M3'])

    calls.clear()
    result2 = process_event(matrix, b'y' * 100_000, b'\x01', b'ctx')
    _check('exact logical wrap accepts large payload digest', result2['status'] == 'OK')
    _check('exact logical wrap advances sequence', matrix._sequence == capacity + 1)
    _check('exact logical wrap reaches M1/M2/M3', [c[0] for c in calls] == ['M1', 'M2', 'M3'])


def _restart_equivalence(profile_name: str, region_bytes: int):
    ref = _load_reference()
    m1 = _extract_m1()
    ledger = _load_ledger()
    capacity = region_bytes // ref.M1_ENTRY_BYTES

    # Cross at least one logical wrap so hard-coded default-profile geometry
    # cannot accidentally pass the Cloud profile.
    sequence = 2 * capacity - 1
    seed = b'\x44' * 32
    payload_a = f'{profile_name}-before-checkpoint'.encode()
    payload_b = f'{profile_name}-after-checkpoint'.encode()

    live_region = SparseRegion(region_bytes)
    _seed_previous(ref, live_region, sequence, seed)
    next_sequence, chain_a = m1(live_region, payload_a, sequence)
    expected_a = ref.next_chain_hash(seed, payload_a)
    _check(f'{profile_name}: pre-checkpoint hash matches reference', chain_a == expected_a)

    capacity_now = len(live_region) // ref.M1_ENTRY_BYTES
    entry_offset = ref.slot_offset(sequence, capacity_now)
    entry = bytes(live_region[entry_offset:entry_offset + ref.M1_ENTRY_BYTES])
    _check(
        f'{profile_name}: persisted live slot contains chain hash',
        entry == ref.encode_entry(sequence, chain_a),
    )

    matrix = Matrix(live_region, sequence=next_sequence, epoch=3, era=1)
    tmp = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
    path = tmp.name
    tmp.close()

    try:
        save_ok = True
        try:
            ledger.save_checkpoint(matrix, path)
        except Exception as exc:
            save_ok = False
            _check(f'{profile_name}: checkpoint save succeeds', False, type(exc).__name__ + ': ' + str(exc))
        if not save_ok:
            return
        _check(f'{profile_name}: checkpoint save succeeds', True)

        restored = Matrix(SparseRegion(region_bytes))
        load_ok = True
        try:
            ledger.load_checkpoint(restored, path)
        except Exception as exc:
            load_ok = False
            _check(f'{profile_name}: checkpoint restore succeeds', False, type(exc).__name__ + ': ' + str(exc))
        if not load_ok:
            return
        _check(f'{profile_name}: checkpoint restore succeeds', True)
        _check(f'{profile_name}: sequence restored exactly', restored._sequence == next_sequence)

        _, uninterrupted_next = m1(live_region, payload_b, next_sequence)
        _, restored_next = m1(restored._m1_region, payload_b, restored._sequence)
        _check(
            f'{profile_name}: save/restore next hash equals uninterrupted execution',
            restored_next == uninterrupted_next,
        )
        _check(
            f'{profile_name}: next hash matches reference recurrence',
            restored_next == ref.next_chain_hash(chain_a, payload_b),
        )
    finally:
        pathlib.Path(path).unlink(missing_ok=True)


def test_default_profile_restart_equivalence():
    _restart_equivalence('default-4gb', 2_147_483_648)


def test_cloud_profile_restart_equivalence():
    _restart_equivalence('cloud-256mib', 134_217_728)


if __name__ == '__main__':
    print('AEGIS M1 live cutover v2')
    test_production_m1_matches_reference_contract()
    test_process_event_fixed_record_wrap_accepts_large_payload()
    test_default_profile_restart_equivalence()
    test_cloud_profile_restart_equivalence()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
