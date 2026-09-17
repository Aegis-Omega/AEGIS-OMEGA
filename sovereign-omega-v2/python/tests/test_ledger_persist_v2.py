"""
SOVEREIGN OMEGA — Ledger Persistence Tests (Mock-based, no CoreMatrix)
EPISTEMIC TIER: T1

Checkpoint-v2 regression for ledger_persist.py using a minimal MockMatrix.
The mock writes canonical 40-byte M1_FIXED_CHAIN_V2 entries so persistence
validation is exercised without allocating the real 4 GB CoreMatrix.

Run: python python/tests/test_ledger_persist_v2.py
"""

import hashlib
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ledger_persist import (
    CHECKPOINT_VERSION,
    M1_RECORD_CONTRACT,
    CheckpointError,
    checkpoint_exists,
    load_checkpoint,
    save_checkpoint,
    _M1_ENTRY_BYTES,
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
    except Exception as exc:
        fail(name, f'expected {exc_type.__name__} but got {type(exc).__name__}: {exc}')


def _slot_capacity(matrix) -> int:
    return len(matrix._m1_region) // _M1_ENTRY_BYTES


def _slot_offset(sequence: int, matrix) -> int:
    return _M1_ENTRY_BYTES * (sequence % _slot_capacity(matrix))


def _mock_chain_hash(sequence: int) -> bytes:
    return hashlib.sha256(f'mock-chain:{sequence}'.encode()).digest()


def _canonical_entry(sequence: int) -> bytes:
    return sequence.to_bytes(8, 'little') + _mock_chain_hash(sequence)


class MockMatrix:
    """Minimal CoreMatrix surface required by save/load_checkpoint."""

    def __init__(self, sequence: int = 0, epoch: int = 0, era: int = 0, region_bytes: int = 2000):
        self._sequence = sequence
        self._epoch = epoch
        self._era = era
        self._lock = threading.Lock()
        self._m1_region = bytearray(region_bytes)
        if sequence > 0:
            prev_seq = sequence - 1
            offset = _slot_offset(prev_seq, self)
            self._m1_region[offset:offset + _M1_ENTRY_BYTES] = _canonical_entry(prev_seq)


def _tmp_path(suffix='.json'):
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


def _read(path):
    with open(path, 'r') as f:
        return json.load(f)


def _write(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f)


def _independent_integrity(cp: dict, entry_hex: str | None = None) -> str:
    entry = cp['last_m1_entry_hex'] if entry_hex is None else entry_hex
    material = (
        f'{cp["checkpoint_version"]}:{cp["m1_record_contract"]}:'
        f'{cp["m1_region_bytes"]}:{cp["sequence"]}:{cp["epoch"]}:'
        f'{cp["era"]}:{entry}'
    ).encode()
    return hashlib.sha256(material).hexdigest()


# ── save_checkpoint ───────────────────────────────────────────────────────────

def test_save_returns_metadata():
    print('\nsave_checkpoint return value:')
    mx = MockMatrix(sequence=5, epoch=1, era=0)
    path = _tmp_path()
    try:
        meta = save_checkpoint(mx, path)
        for field in (
            'checkpoint_version', 'm1_record_contract', 'm1_region_bytes',
            'sequence', 'epoch', 'era', 'integrity_hash', 'path',
        ):
            _chk(f'meta has {field}', field in meta)
        _chk('meta checkpoint version is v2', meta['checkpoint_version'] == CHECKPOINT_VERSION)
        _chk('meta contract is M1_FIXED_CHAIN_V2', meta['m1_record_contract'] == M1_RECORD_CONTRACT)
        _chk('meta binds active M1 geometry', meta['m1_region_bytes'] == len(mx._m1_region))
        _chk('meta sequence == 5', meta['sequence'] == 5)
        _chk('meta epoch == 1', meta['epoch'] == 1)
        _chk('meta era == 0', meta['era'] == 0)
        _chk('meta path matches', meta['path'] == path)
        _chk('integrity_hash is 64 hex chars', isinstance(meta['integrity_hash'], str)
             and len(meta['integrity_hash']) == 64)
    finally:
        os.unlink(path)


def test_save_json_contents():
    print('\nsave_checkpoint JSON contents:')
    mx = MockMatrix(sequence=3, epoch=0, era=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        cp = _read(path)
        _chk('checkpoint_version == 2.0.0', cp['checkpoint_version'] == CHECKPOINT_VERSION)
        _chk('m1_record_contract bound', cp['m1_record_contract'] == M1_RECORD_CONTRACT)
        _chk('m1_region_bytes bound', cp['m1_region_bytes'] == len(mx._m1_region))
        _chk('is_replay_reconstructable == True', cp.get('is_replay_reconstructable') is True)
        entry_hex = cp['last_m1_entry_hex']
        _chk('last_m1_entry_hex is 80 hex chars', len(entry_hex) == _M1_ENTRY_BYTES * 2)
        entry = bytes.fromhex(entry_hex)
        _chk('embedded sequence is sequence-1', int.from_bytes(entry[:8], 'little') == 2)
        _chk('entry equals canonical mock entry', entry == _canonical_entry(2))
    finally:
        os.unlink(path)


def test_save_sequence_zero():
    print('\nsave_checkpoint sequence=0:')
    mx = MockMatrix(sequence=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        cp = _read(path)
        _chk('seq=0 last_m1_entry_hex is 80 zeros', cp['last_m1_entry_hex'] == '0' * 80)
        _chk('seq=0 sequence in JSON is 0', cp['sequence'] == 0)
    finally:
        os.unlink(path)


def test_save_sequence_42():
    print('\nsave_checkpoint sequence=42:')
    mx = MockMatrix(sequence=42, epoch=7, era=2)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        cp = _read(path)
        entry = bytes.fromhex(cp['last_m1_entry_hex'])
        _chk('seq=42 entry is canonical sequence 41', entry == _canonical_entry(41))
        _chk('seq=42 sequence in JSON is 42', cp['sequence'] == 42)
        _chk('seq=42 epoch in JSON is 7', cp['epoch'] == 7)
        _chk('seq=42 era in JSON is 2', cp['era'] == 2)
    finally:
        os.unlink(path)


def test_save_integrity_hash_verifies():
    print('\nsave_checkpoint integrity hash:')
    mx = MockMatrix(sequence=10, epoch=2, era=1)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        cp = _read(path)
        _chk(
            'integrity_hash matches independent v2 preimage',
            cp['integrity_hash'] == _independent_integrity(cp),
        )
    finally:
        os.unlink(path)


# ── load_checkpoint round-trip ────────────────────────────────────────────────

def test_load_roundtrip():
    print('\nload_checkpoint round-trip:')
    mx = MockMatrix(sequence=15, epoch=3, era=1)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        mx2 = MockMatrix()
        result = load_checkpoint(mx2, path)
        _chk('load restores sequence', mx2._sequence == 15)
        _chk('load restores epoch', mx2._epoch == 3)
        _chk('load restores era', mx2._era == 1)
        offset = _slot_offset(14, mx2)
        restored_entry = bytes(mx2._m1_region[offset:offset + _M1_ENTRY_BYTES])
        _chk('load restores canonical last M1 entry', restored_entry == _canonical_entry(14))
        _chk('result has sequence', result['sequence'] == 15)
        _chk('result has contract', result['m1_record_contract'] == M1_RECORD_CONTRACT)
        _chk('result has geometry', result['m1_region_bytes'] == len(mx2._m1_region))
        _chk('result path matches', result['path'] == path)
    finally:
        os.unlink(path)


def test_load_seq0_roundtrip():
    print('\nload_checkpoint seq=0 round-trip:')
    mx = MockMatrix(sequence=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        mx2 = MockMatrix(sequence=19, epoch=5, era=3)
        load_checkpoint(mx2, path)
        _chk('seq=0 restored correctly', mx2._sequence == 0)
        _chk('epoch=0 restored correctly', mx2._epoch == 0)
        _chk('era=0 restored correctly', mx2._era == 0)
    finally:
        os.unlink(path)


# ── checkpoint_exists ─────────────────────────────────────────────────────────

def test_checkpoint_exists():
    print('\ncheckpoint_exists:')
    missing = '/tmp/__nonexistent_aegis_test_path_xyz.json'
    try:
        os.unlink(missing)
    except FileNotFoundError:
        pass
    _chk('nonexistent explicit path -> False', checkpoint_exists(missing) is False)

    path = _tmp_path()
    try:
        _chk('existing explicit path -> True', checkpoint_exists(path) is True)
        save_checkpoint(MockMatrix(), path)
        _chk('saved explicit path -> True', checkpoint_exists(path) is True)
    finally:
        os.unlink(path)
    _chk('deleted explicit path -> False', checkpoint_exists(path) is False)


# ── validation failures ───────────────────────────────────────────────────────

def test_checkpoint_error_nonexistent():
    print('\nCheckpointError — nonexistent file:')
    expect_raises(
        'nonexistent -> CheckpointError',
        CheckpointError,
        lambda: load_checkpoint(MockMatrix(), '/tmp/__aegis_no_such_file_xyz.json'),
    )


def _saved_checkpoint(sequence=5, epoch=0, era=0):
    mx = MockMatrix(sequence=sequence, epoch=epoch, era=era)
    path = _tmp_path()
    save_checkpoint(mx, path)
    return mx, path, _read(path)


def test_checkpoint_error_wrong_version():
    print('\nCheckpointError — wrong version:')
    _, path, cp = _saved_checkpoint()
    try:
        cp['checkpoint_version'] = '9.9.9'
        _write(path, cp)
        expect_raises('wrong version -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_wrong_contract():
    print('\nCheckpointError — wrong M1 record contract:')
    _, path, cp = _saved_checkpoint()
    try:
        cp['m1_record_contract'] = 'M1_FIXED_CHAIN_V1'
        _write(path, cp)
        expect_raises('wrong contract -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_wrong_geometry():
    print('\nCheckpointError — wrong M1 geometry:')
    _, path, _ = _saved_checkpoint()
    try:
        expect_raises('active geometry mismatch -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(region_bytes=4000), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_tampered_hash():
    print('\nCheckpointError — tampered integrity_hash:')
    _, path, cp = _saved_checkpoint()
    try:
        cp['integrity_hash'] = 'a' * 64
        _write(path, cp)
        expect_raises('tampered hash -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_not_reconstructable():
    print('\nCheckpointError — is_replay_reconstructable False:')
    _, path, cp = _saved_checkpoint()
    try:
        cp['is_replay_reconstructable'] = False
        _write(path, cp)
        expect_raises('not reconstructable -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_tampered_sequence():
    print('\nCheckpointError — tampered sequence:')
    _, path, cp = _saved_checkpoint()
    try:
        cp['sequence'] = 9999
        _write(path, cp)
        expect_raises('tampered sequence -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_truncated_entry_hex():
    print('\nCheckpointError — truncated last_m1_entry_hex:')
    _, path, cp = _saved_checkpoint()
    try:
        bad_hex = 'aa' * 20
        cp['last_m1_entry_hex'] = bad_hex
        cp['integrity_hash'] = _independent_integrity(cp, bad_hex)
        _write(path, cp)
        expect_raises('truncated entry -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_embedded_sequence():
    print('\nCheckpointError — embedded M1 sequence mismatch:')
    _, path, cp = _saved_checkpoint(sequence=5)
    try:
        entry = (123).to_bytes(8, 'little') + bytes.fromhex(cp['last_m1_entry_hex'])[8:]
        cp['last_m1_entry_hex'] = entry.hex()
        cp['integrity_hash'] = _independent_integrity(cp)
        _write(path, cp)
        expect_raises('embedded sequence mismatch -> CheckpointError', CheckpointError,
                      lambda: load_checkpoint(MockMatrix(), path))
    finally:
        os.unlink(path)


def test_checkpoint_error_matrix_untouched():
    print('\nCheckpointError — matrix untouched on failure:')
    _, path, cp = _saved_checkpoint(sequence=10, epoch=2, era=1)
    try:
        cp['integrity_hash'] = 'b' * 64
        _write(path, cp)
        mx2 = MockMatrix(sequence=5, epoch=1, era=0)
        original_entry = bytes(mx2._m1_region)
        try:
            load_checkpoint(mx2, path)
        except CheckpointError:
            pass
        _chk('sequence unchanged after failure', mx2._sequence == 5)
        _chk('epoch unchanged after failure', mx2._epoch == 1)
        _chk('era unchanged after failure', mx2._era == 0)
        _chk('M1 region unchanged after failure', bytes(mx2._m1_region) == original_entry)
    finally:
        os.unlink(path)


# ── atomicity and determinism ─────────────────────────────────────────────────

def test_atomic_write():
    print('\natomic write behavior:')
    mx = MockMatrix(sequence=7, epoch=1, era=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        _chk('file exists after save', os.path.exists(path))
        _chk('file is valid JSON after save', isinstance(_read(path), dict))
        save_checkpoint(mx, path)
        cp2 = _read(path)
        _chk('overwrite still valid JSON', isinstance(cp2, dict))
        _chk('overwrite has correct checkpoint_version', cp2['checkpoint_version'] == CHECKPOINT_VERSION)
        _chk('overwrite has correct record contract', cp2['m1_record_contract'] == M1_RECORD_CONTRACT)
    finally:
        os.unlink(path)


def test_deterministic_hash():
    print('\ndeterministic integrity hash:')
    mx = MockMatrix(sequence=8, epoch=3, era=1)
    path = _tmp_path()
    try:
        meta1 = save_checkpoint(mx, path)
        meta2 = save_checkpoint(mx, path)
        _chk('same state saved twice -> same integrity_hash',
             meta1['integrity_hash'] == meta2['integrity_hash'])
    finally:
        os.unlink(path)


def test_different_epochs_different_hash():
    print('\ndifferent state -> different hash:')
    mx1 = MockMatrix(sequence=5, epoch=1, era=0)
    mx2 = MockMatrix(sequence=5, epoch=2, era=0)
    path1 = _tmp_path()
    path2 = _tmp_path()
    try:
        meta1 = save_checkpoint(mx1, path1)
        meta2 = save_checkpoint(mx2, path2)
        _chk('different epoch -> different integrity_hash',
             meta1['integrity_hash'] != meta2['integrity_hash'])
    finally:
        os.unlink(path1)
        os.unlink(path2)


def test_multiple_roundtrips():
    print('\nmultiple round-trips:')
    for seq, epoch, era in [(0, 0, 0), (1, 0, 0), (5, 1, 0), (20, 5, 2), (75, 8, 3)]:
        mx = MockMatrix(sequence=seq, epoch=epoch, era=era)
        path = _tmp_path()
        try:
            save_checkpoint(mx, path)
            mx2 = MockMatrix()
            load_checkpoint(mx2, path)
            _chk(f'round-trip seq={seq}', mx2._sequence == seq)
            _chk(f'round-trip epoch={epoch}', mx2._epoch == epoch)
            _chk(f'round-trip era={era}', mx2._era == era)
            if seq > 0:
                offset = _slot_offset(seq - 1, mx2)
                restored = bytes(mx2._m1_region[offset:offset + _M1_ENTRY_BYTES])
                _chk(f'round-trip entry seq={seq}', restored == _canonical_entry(seq - 1))
        finally:
            os.unlink(path)


if __name__ == '__main__':
    print('=== LEDGER PERSIST V2 TESTS (MOCK) ===')
    test_save_returns_metadata()
    test_save_json_contents()
    test_save_sequence_zero()
    test_save_sequence_42()
    test_save_integrity_hash_verifies()
    test_load_roundtrip()
    test_load_seq0_roundtrip()
    test_checkpoint_exists()
    test_checkpoint_error_nonexistent()
    test_checkpoint_error_wrong_version()
    test_checkpoint_error_wrong_contract()
    test_checkpoint_error_wrong_geometry()
    test_checkpoint_error_tampered_hash()
    test_checkpoint_error_not_reconstructable()
    test_checkpoint_error_tampered_sequence()
    test_checkpoint_error_truncated_entry_hex()
    test_checkpoint_error_embedded_sequence()
    test_checkpoint_error_matrix_untouched()
    test_atomic_write()
    test_deterministic_hash()
    test_different_epochs_different_hash()
    test_multiple_roundtrips()
    print(f'\n{"=" * 35}')
    print(f'PASS: {PASS}  FAIL: {FAIL}')
    if FAIL > 0:
        print('RESULT: FAIL')
        sys.exit(1)
    print('RESULT: PASS')
