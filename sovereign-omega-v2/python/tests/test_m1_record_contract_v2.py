"""
AEGIS M1 record contract v2 — diagnostic/reference regression.

This test intentionally separates two claims:
1. the current production M1 implementation is not a transitive hash chain;
2. the inert reference contract must provide fixed 40-byte entries with
   zero-genesis, previous-chain recurrence, and slot-indexed wrap semantics.

The reference module is not imported by production code.
"""

import ast
import hashlib
import importlib.util
import pathlib
from typing import Tuple

PYTHON_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_MATRIX = PYTHON_DIR / 'core_matrix.py'
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


def _load_current_m1():
    tree = ast.parse(CORE_MATRIX.read_text())
    fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'M1'
    )
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {'hashlib': hashlib, 'Tuple': Tuple}
    exec(compile(module, str(CORE_MATRIX), 'exec'), ns)
    return ns['M1']


def _load_reference():
    if not REFERENCE.exists():
        return None
    spec = importlib.util.spec_from_file_location('m1_record_contract_v2', REFERENCE)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def test_current_m1_non_transitive_witness():
    m1 = _load_current_m1()
    state = memoryview(bytearray(400))

    _, h0 = m1(state, b'a', 0)
    _, h1 = m1(state, b'b', 1)
    _, h2 = m1(state, b'c', 2)

    p0 = _sha(b'a')
    p1 = _sha(b'b')
    p2 = _sha(b'c')
    zero = b'\x00' * 32

    expected_h0 = _sha(zero + p0)
    expected_h1 = _sha(expected_h0 + p1)
    expected_h2 = _sha(expected_h1 + p2)

    _check('current genesis differs from zero-genesis chain', h0 != expected_h0)
    _check('current second hash differs from transitive recurrence', h1 != expected_h1)
    _check('current third hash differs from transitive recurrence', h2 != expected_h2)
    _check('current genesis is self-pair hash', h0 == _sha(p0 + p0))
    _check('current second hash is adjacent payload-hash pair', h1 == _sha(p0 + p1))
    _check('current third hash is adjacent payload-hash pair', h2 == _sha(p1 + p2))


def test_reference_contract_exists_and_is_fixed_width():
    ref = _load_reference()
    _check('reference module exists', ref is not None)
    if ref is None:
        return

    _check('entry width is exactly 40 bytes', ref.M1_ENTRY_BYTES == 40)
    _check('hash width is exactly 32 bytes', ref.M1_HASH_BYTES == 32)
    _check('genesis chain hash is 32 zero bytes', ref.M1_GENESIS_HASH == b'\x00' * 32)

    entry = ref.encode_entry(7, b'\x11' * 32)
    _check('encoded entry is exactly 40 bytes', len(entry) == 40)
    sequence, chain_hash = ref.decode_entry(entry)
    _check('entry round-trip preserves sequence', sequence == 7)
    _check('entry round-trip preserves chain hash', chain_hash == b'\x11' * 32)


def test_reference_contract_transitive_chain():
    ref = _load_reference()
    if ref is None:
        _check('reference transitive chain available', False, 'reference module missing')
        return

    h0 = ref.next_chain_hash(ref.M1_GENESIS_HASH, b'a')
    h1 = ref.next_chain_hash(h0, b'b')
    h2 = ref.next_chain_hash(h1, b'c')

    expected_h0 = _sha(b'\x00' * 32 + _sha(b'a'))
    expected_h1 = _sha(expected_h0 + _sha(b'b'))
    expected_h2 = _sha(expected_h1 + _sha(b'c'))

    _check('reference genesis uses zero hash', h0 == expected_h0)
    _check('reference second link consumes prior chain hash', h1 == expected_h1)
    _check('reference third link consumes prior chain hash', h2 == expected_h2)


def test_reference_slot_wrap_is_record_indexed():
    ref = _load_reference()
    if ref is None:
        _check('reference slot addressing available', False, 'reference module missing')
        return

    for region_bytes in (120, 128, 134_217_728, 2_147_483_648):
        capacity = region_bytes // 40
        if capacity == 0:
            continue
        offset = ref.slot_offset(capacity, capacity)
        _check(
            f'slot wrap returns byte zero for capacity={capacity}',
            offset == 0,
            f'got {offset}',
        )
        last = ref.slot_offset(capacity - 1, capacity)
        _check(
            f'last slot is aligned and fully inside capacity={capacity}',
            last % 40 == 0 and last + 40 <= capacity * 40,
            f'got {last}',
        )


def test_reference_payload_length_does_not_change_record_width():
    ref = _load_reference()
    if ref is None:
        _check('reference payload-independent width available', False, 'reference module missing')
        return

    previous = ref.M1_GENESIS_HASH
    short_hash = ref.next_chain_hash(previous, b'x')
    long_hash = ref.next_chain_hash(previous, b'x' * 100_000)
    short_entry = ref.encode_entry(1, short_hash)
    long_entry = ref.encode_entry(1, long_hash)

    _check('short payload still produces 40-byte record', len(short_entry) == 40)
    _check('long payload still produces 40-byte record', len(long_entry) == 40)
    _check('payload affects digest, not record width', short_hash != long_hash)


if __name__ == '__main__':
    print('AEGIS M1 record contract v2')
    test_current_m1_non_transitive_witness()
    test_reference_contract_exists_and_is_fixed_width()
    test_reference_contract_transitive_chain()
    test_reference_slot_wrap_is_record_indexed()
    test_reference_payload_length_does_not_change_record_width()
    print(f'\nRESULT: {PASS} passed, {FAIL} failed')
    raise SystemExit(0 if FAIL == 0 else 1)
