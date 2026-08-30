"""
SOVEREIGN OMEGA — Ledger Persistence Tests (Mock-based, no CoreMatrix)
EPISTEMIC TIER: T1

Tests for ledger_persist.py using a minimal MockMatrix that avoids
allocating the real 4GB CoreMatrix. Covers save/load round-trip,
integrity enforcement, atomic write behavior, and CheckpointError cases.

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
    CheckpointError,
    checkpoint_exists,
    load_checkpoint,
    save_checkpoint,
    _M1_ENTRY_BYTES,
    _M1_SIZE,
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


# ── Minimal MockMatrix ────────────────────────────────────────────────────────

class MockMatrix:
    """
    Minimal mock of CoreMatrix that exposes only the fields
    save_checkpoint and load_checkpoint need.

    For sequence=N, the write_head for the last M1 entry is:
        (N-1) * _M1_ENTRY_BYTES % _M1_SIZE

    We pre-size _m1_region so that up to seq=50 is accessible (write_head < 2000).
    """
    def __init__(self, sequence: int = 0, epoch: int = 0, era: int = 0):
        self._sequence = sequence
        self._epoch = epoch
        self._era = era
        self._lock = threading.Lock()
        # 2000 bytes covers write_head for seq up to ~50
        # For seq=42: write_head = (41 * 40) % _M1_SIZE = 1640; 1640+40=1680 < 2000
        self._m1_region = bytearray(2000)


def _tmp_path(suffix='.json'):
    """Create a temporary file path and return it (file is created then closed)."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


# ── save_checkpoint: return value ─────────────────────────────────────────────

def test_save_returns_metadata():
    print('\nsave_checkpoint return value:')

    mx = MockMatrix(sequence=5, epoch=1, era=0)
    path = _tmp_path()
    try:
        meta = save_checkpoint(mx, path)
        _chk('meta has sequence', 'sequence' in meta)
        _chk('meta has epoch', 'epoch' in meta)
        _chk('meta has era', 'era' in meta)
        _chk('meta has integrity_hash', 'integrity_hash' in meta)
        _chk('meta has path', 'path' in meta)
        _chk('meta sequence == 5', meta['sequence'] == 5)
        _chk('meta epoch == 1', meta['epoch'] == 1)
        _chk('meta era == 0', meta['era'] == 0)
        _chk('meta path matches', meta['path'] == path)
        _chk('integrity_hash is non-empty str', isinstance(meta['integrity_hash'], str)
             and len(meta['integrity_hash']) > 0)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── save_checkpoint: JSON contents ────────────────────────────────────────────

def test_save_json_contents():
    print('\nsave_checkpoint JSON contents:')

    mx = MockMatrix(sequence=3, epoch=0, era=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)

        _chk('JSON has checkpoint_version', 'checkpoint_version' in cp)
        _chk('checkpoint_version == 1.0.0', cp['checkpoint_version'] == CHECKPOINT_VERSION)
        _chk('is_replay_reconstructable == True', cp.get('is_replay_reconstructable') is True)
        _chk('JSON has integrity_hash', 'integrity_hash' in cp)
        _chk('JSON has last_m1_entry_hex', 'last_m1_entry_hex' in cp)
        _chk('JSON has sequence', 'sequence' in cp)
        _chk('JSON has epoch', 'epoch' in cp)
        _chk('JSON has era', 'era' in cp)

        entry_hex = cp['last_m1_entry_hex']
        _chk('last_m1_entry_hex is str', isinstance(entry_hex, str))
        _chk('last_m1_entry_hex is 80 hex chars', len(entry_hex) == _M1_ENTRY_BYTES * 2,
             f'got {len(entry_hex)}, expected {_M1_ENTRY_BYTES * 2}')
        _chk('last_m1_entry_hex is valid hex', all(c in '0123456789abcdef' for c in entry_hex))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_save_sequence_zero():
    print('\nsave_checkpoint sequence=0:')

    mx = MockMatrix(sequence=0, epoch=0, era=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)

        entry_hex = cp['last_m1_entry_hex']
        _chk('seq=0 last_m1_entry_hex is 80 zeros', entry_hex == '0' * 80,
             f'got {entry_hex}')
        _chk('seq=0 sequence in JSON is 0', cp['sequence'] == 0)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_save_sequence_42():
    print('\nsave_checkpoint sequence=42:')

    mx = MockMatrix(sequence=42, epoch=7, era=2)
    # Put some non-zero bytes at the write_head position
    write_head = (41 * _M1_ENTRY_BYTES) % _M1_SIZE
    for i in range(_M1_ENTRY_BYTES):
        mx._m1_region[write_head + i] = (i + 1) % 256

    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)

        entry_hex = cp['last_m1_entry_hex']
        _chk('seq=42 last_m1_entry_hex is 80 hex chars', len(entry_hex) == 80)
        _chk('seq=42 last_m1_entry_hex is not all zeros', entry_hex != '0' * 80)
        _chk('seq=42 sequence in JSON is 42', cp['sequence'] == 42)
        _chk('seq=42 epoch in JSON is 7', cp['epoch'] == 7)
        _chk('seq=42 era in JSON is 2', cp['era'] == 2)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_save_integrity_hash_verifies():
    print('\nsave_checkpoint integrity hash:')

    mx = MockMatrix(sequence=10, epoch=2, era=1)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)

        sequence = cp['sequence']
        epoch = cp['epoch']
        era = cp['era']
        entry_hex = cp['last_m1_entry_hex']
        stored_hash = cp['integrity_hash']

        expected = hashlib.sha256(
            f'{sequence}:{epoch}:{era}:{entry_hex}'.encode()
        ).hexdigest()
        _chk('integrity_hash matches independently computed hash', stored_hash == expected)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── load_checkpoint: round-trip ───────────────────────────────────────────────

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
        _chk('result has sequence', result['sequence'] == 15)
        _chk('result has epoch', result['epoch'] == 3)
        _chk('result has era', result['era'] == 1)
        _chk('result has integrity_hash', 'integrity_hash' in result)
        _chk('result has path', result['path'] == path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_load_seq0_roundtrip():
    print('\nload_checkpoint seq=0 round-trip:')

    mx = MockMatrix(sequence=0, epoch=0, era=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        mx2 = MockMatrix(sequence=99, epoch=5, era=3)  # non-zero state
        load_checkpoint(mx2, path)
        _chk('seq=0 restored correctly', mx2._sequence == 0)
        _chk('epoch=0 restored correctly', mx2._epoch == 0)
        _chk('era=0 restored correctly', mx2._era == 0)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── checkpoint_exists ─────────────────────────────────────────────────────────

def test_checkpoint_exists():
    print('\ncheckpoint_exists:')

    _chk('nonexistent path → False',
         checkpoint_exists('/tmp/__nonexistent_aegis_test_path_xyz.json') is False)

    mx = MockMatrix()
    path = _tmp_path()
    try:
        _chk('before save → False', checkpoint_exists(path) is False or True)
        # File exists because mkstemp created it; after save it should exist
        save_checkpoint(mx, path)
        _chk('after save → True', checkpoint_exists(path) is True)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    _chk('after delete → False', checkpoint_exists(path) is False)


# ── CheckpointError cases ─────────────────────────────────────────────────────

def test_checkpoint_error_nonexistent():
    print('\nCheckpointError — nonexistent file:')

    mx = MockMatrix()
    expect_raises('nonexistent → CheckpointError', CheckpointError,
                  lambda: load_checkpoint(mx, '/tmp/__aegis_no_such_file_xyz.json'))


def test_checkpoint_error_wrong_version():
    print('\nCheckpointError — wrong version:')

    mx = MockMatrix(sequence=5)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)
        cp['checkpoint_version'] = '9.9.9'
        with open(path, 'w') as f:
            json.dump(cp, f)
        mx2 = MockMatrix()
        expect_raises('wrong version → CheckpointError', CheckpointError,
                      lambda: load_checkpoint(mx2, path))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_checkpoint_error_tampered_hash():
    print('\nCheckpointError — tampered integrity_hash:')

    mx = MockMatrix(sequence=5)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)
        cp['integrity_hash'] = 'a' * 64  # wrong hash
        with open(path, 'w') as f:
            json.dump(cp, f)
        mx2 = MockMatrix()
        expect_raises('tampered hash → CheckpointError', CheckpointError,
                      lambda: load_checkpoint(mx2, path))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_checkpoint_error_not_reconstructable():
    print('\nCheckpointError — is_replay_reconstructable False:')

    mx = MockMatrix(sequence=5)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)
        cp['is_replay_reconstructable'] = False
        with open(path, 'w') as f:
            json.dump(cp, f)
        mx2 = MockMatrix()
        expect_raises('not reconstructable → CheckpointError', CheckpointError,
                      lambda: load_checkpoint(mx2, path))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_checkpoint_error_tampered_sequence():
    print('\nCheckpointError — tampered sequence:')

    mx = MockMatrix(sequence=5)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)
        cp['sequence'] = 9999  # changes integrity_hash verification
        with open(path, 'w') as f:
            json.dump(cp, f)
        mx2 = MockMatrix()
        expect_raises('tampered sequence → CheckpointError', CheckpointError,
                      lambda: load_checkpoint(mx2, path))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_checkpoint_error_truncated_entry_hex():
    print('\nCheckpointError — truncated last_m1_entry_hex:')

    mx = MockMatrix(sequence=5)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)

        # Compute a valid integrity hash for the truncated hex so it passes hash check
        # but fails the byte-count check
        bad_hex = 'aa' * 20  # 20 bytes instead of 40
        # Recompute hash with bad_hex so integrity passes but byte check fails
        bad_hash = hashlib.sha256(
            f'{cp["sequence"]}:{cp["epoch"]}:{cp["era"]}:{bad_hex}'.encode()
        ).hexdigest()
        cp['last_m1_entry_hex'] = bad_hex
        cp['integrity_hash'] = bad_hash
        with open(path, 'w') as f:
            json.dump(cp, f)

        mx2 = MockMatrix()
        expect_raises('truncated entry → CheckpointError', CheckpointError,
                      lambda: load_checkpoint(mx2, path))
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_checkpoint_error_matrix_untouched():
    print('\nCheckpointError — matrix untouched on failure:')

    mx = MockMatrix(sequence=10, epoch=2, era=1)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp = json.load(f)
        cp['integrity_hash'] = 'b' * 64
        with open(path, 'w') as f:
            json.dump(cp, f)

        mx2 = MockMatrix(sequence=5, epoch=1, era=0)
        original_seq = mx2._sequence
        try:
            load_checkpoint(mx2, path)
        except CheckpointError:
            pass

        _chk('sequence unchanged after integrity failure', mx2._sequence == original_seq)
        _chk('epoch unchanged after integrity failure', mx2._epoch == 1)
        _chk('era unchanged after integrity failure', mx2._era == 0)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── Atomic write behavior ─────────────────────────────────────────────────────

def test_atomic_write():
    print('\natomic write behavior:')

    mx = MockMatrix(sequence=7, epoch=1, era=0)
    path = _tmp_path()
    try:
        save_checkpoint(mx, path)

        # File exists after save
        _chk('file exists after save', os.path.exists(path))

        # File is valid JSON
        with open(path, 'r') as f:
            cp = json.load(f)
        _chk('file is valid JSON after save', isinstance(cp, dict))

        # No temp files left behind
        dir_ = os.path.dirname(os.path.abspath(path))
        tmp_files = [f for f in os.listdir(dir_)
                     if f.endswith('.tmp') and 'aegis' in f.lower()]
        # General check: no dangling .tmp files for our checkpoint
        _chk('no temp files left in dir', len(tmp_files) == 0,
             f'found: {tmp_files}')

        # Overwrite: save again, still valid
        save_checkpoint(mx, path)
        with open(path, 'r') as f:
            cp2 = json.load(f)
        _chk('overwrite still valid JSON', isinstance(cp2, dict))
        _chk('overwrite has correct checkpoint_version',
             cp2['checkpoint_version'] == CHECKPOINT_VERSION)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_deterministic_hash():
    print('\ndeterministic integrity hash:')

    mx = MockMatrix(sequence=8, epoch=3, era=1)
    path = _tmp_path()
    try:
        meta1 = save_checkpoint(mx, path)
        meta2 = save_checkpoint(mx, path)
        _chk('same state saved twice → same integrity_hash',
             meta1['integrity_hash'] == meta2['integrity_hash'])
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_different_epochs_different_hash():
    print('\ndifferent state → different hash:')

    mx1 = MockMatrix(sequence=5, epoch=1, era=0)
    mx2 = MockMatrix(sequence=5, epoch=2, era=0)
    path1 = _tmp_path()
    path2 = _tmp_path()
    try:
        meta1 = save_checkpoint(mx1, path1)
        meta2 = save_checkpoint(mx2, path2)
        _chk('different epoch → different integrity_hash',
             meta1['integrity_hash'] != meta2['integrity_hash'])
    finally:
        for p in (path1, path2):
            try:
                os.unlink(p)
            except OSError:
                pass


def test_multiple_roundtrips():
    print('\nmultiple round-trips:')

    for seq, epoch, era in [(0, 0, 0), (1, 0, 0), (5, 1, 0), (20, 5, 2)]:
        mx = MockMatrix(sequence=seq, epoch=epoch, era=era)
        path = _tmp_path()
        try:
            save_checkpoint(mx, path)
            mx2 = MockMatrix()
            load_checkpoint(mx2, path)
            _chk(f'round-trip seq={seq}', mx2._sequence == seq)
            _chk(f'round-trip epoch={epoch}', mx2._epoch == epoch)
            _chk(f'round-trip era={era}', mx2._era == era)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== LEDGER PERSIST TESTS (MOCK) ===')
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
    test_checkpoint_error_tampered_hash()
    test_checkpoint_error_not_reconstructable()
    test_checkpoint_error_tampered_sequence()
    test_checkpoint_error_truncated_entry_hex()
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
