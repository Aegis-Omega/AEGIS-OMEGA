"""
AEGIS M1 fixed-slot + checkpoint contract regression.

The test extracts M1 directly from production core_matrix.py so no 4 GB
CoreMatrix allocation or hardware imports are required. ledger_persist.py is
safe to import directly and is exercised with small mock M1 regions.
"""

import ast
import hashlib
import os
import pathlib
import sys
import tempfile
import threading

PYTHON_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_MATRIX = PYTHON_DIR / 'core_matrix.py'
sys.path.insert(0, str(PYTHON_DIR))

from ledger_persist import load_checkpoint, save_checkpoint, _last_m1_entry

PASS = 0
FAIL = 0
ENTRY_BYTES = 40


def _check(name: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        print(f'  FAIL  {name}')


def _load_m1():
    tree = ast.parse(CORE_MATRIX.read_text())
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'M1'
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {'hashlib': hashlib, 'Tuple': tuple, 'memoryview': memoryview}
    exec(compile(module, str(CORE_MATRIX), 'exec'), namespace)
    return namespace['M1']


M1 = _load_m1()


class MockMatrix:
    def __init__(self, region_len: int, sequence: int = 0, epoch: int = 0, era: int = 0):
        self._m1_region = bytearray(region_len)
        self._sequence = sequence
        self._epoch = epoch
        self._era = era
        self._lock = threading.RLock()


def _slot_offset(region_len: int, sequence: int) -> int:
    slots = region_len // ENTRY_BYTES
    return ENTRY_BYTES * (sequence % slots)


def test_payload_is_hashed_but_not_spilled_past_entry():
    state = bytearray(128)
    payload = b'abc'
    next_sequence, _ = M1(memoryview(state), payload, 1)
    offset = _slot_offset(len(state), 1)

    _check('M1 advances sequence', next_sequence == 2)
    _check('slot stores sequence', int.from_bytes(state[offset:offset + 8], 'little') == 1)
    _check(
        'slot stores payload hash',
        bytes(state[offset + 8:offset + 40]) == hashlib.sha256(payload).digest(),
    )
    _check('payload does not spill into next slot', bytes(state[80:83]) == b'\x00\x00\x00')


def test_nondivisible_region_wraps_on_slot_count_not_byte_modulo():
    state = bytearray(128)  # three complete 40-byte slots + eight-byte tail
    payload = b'wrap'
    next_sequence, _ = M1(memoryview(state), payload, 3)

    _check('wrap advances sequence', next_sequence == 4)
    _check('sequence 3 wraps to slot zero', int.from_bytes(state[0:8], 'little') == 3)
    _check(
        'wrapped slot stores payload hash',
        bytes(state[8:40]) == hashlib.sha256(payload).digest(),
    )
    _check('unused eight-byte tail remains untouched', bytes(state[120:128]) == b'\x00' * 8)


def test_pre_wrap_state_hash_formula_is_preserved():
    state = bytearray(128)
    previous_payload = b'previous'
    current_payload = b'current'
    previous_hash = hashlib.sha256(previous_payload).digest()
    state[8:40] = previous_hash  # sequence 0 entry

    _, state_hash = M1(memoryview(state), current_payload, 1)
    expected = hashlib.sha256(previous_hash + hashlib.sha256(current_payload).digest()).digest()
    _check('pre-wrap returned state hash remains byte-identical', state_hash == expected)


def test_checkpoint_reads_last_entry_using_runtime_region_geometry():
    matrix = MockMatrix(128, sequence=4, epoch=2, era=1)
    payload_hash = hashlib.sha256(b'wrapped').digest()
    matrix._m1_region[0:8] = (3).to_bytes(8, 'little')
    matrix._m1_region[8:40] = payload_hash

    entry = _last_m1_entry(matrix)
    _check('checkpoint extracts exactly 40 bytes after wrap', len(entry) == 40)
    _check('checkpoint reads wrapped slot zero', entry == bytes(matrix._m1_region[0:40]))


def test_checkpoint_restore_uses_runtime_region_geometry_without_resizing():
    source = MockMatrix(128, sequence=4, epoch=2, era=1)
    source._m1_region[0:8] = (3).to_bytes(8, 'little')
    source._m1_region[8:40] = hashlib.sha256(b'wrapped').digest()

    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    try:
        save_checkpoint(source, path)
        target = MockMatrix(128)
        before_len = len(target._m1_region)
        load_checkpoint(target, path)

        _check('restore preserves runtime region length', len(target._m1_region) == before_len)
        _check('restore writes wrapped last entry to slot zero', target._m1_region[0:40] == source._m1_region[0:40])
        _check('restore sequence matches checkpoint', target._sequence == 4)
        _check('restore epoch matches checkpoint', target._epoch == 2)
        _check('restore era matches checkpoint', target._era == 1)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_restore_preserves_next_m1_digest_across_wrap():
    uninterrupted = MockMatrix(128)
    for sequence, payload in enumerate((b'a', b'b', b'c', b'd')):
        uninterrupted._sequence, _ = M1(
            memoryview(uninterrupted._m1_region), payload, sequence
        )
    uninterrupted._epoch = 1
    uninterrupted._era = 1

    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    try:
        save_checkpoint(uninterrupted, path)
        restored = MockMatrix(128)
        load_checkpoint(restored, path)

        next_payload = b'e'
        seq_a, digest_a = M1(
            memoryview(uninterrupted._m1_region), next_payload, uninterrupted._sequence
        )
        seq_b, digest_b = M1(
            memoryview(restored._m1_region), next_payload, restored._sequence
        )

        _check('restored continuation advances same sequence', seq_a == seq_b == 5)
        _check('restored continuation reproduces next M1 digest', digest_a == digest_b)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


if __name__ == '__main__':
    print('AEGIS M1 fixed-slot persistence contract')
    test_payload_is_hashed_but_not_spilled_past_entry()
    test_nondivisible_region_wraps_on_slot_count_not_byte_modulo()
    test_pre_wrap_state_hash_formula_is_preserved()
    test_checkpoint_reads_last_entry_using_runtime_region_geometry()
    test_checkpoint_restore_uses_runtime_region_geometry_without_resizing()
    test_restore_preserves_next_m1_digest_across_wrap()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
