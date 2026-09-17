"""
SOVEREIGN OMEGA — Ledger Persistence
EPISTEMIC TIER: T1
Gate 170: Crash-safe checkpoint for CoreMatrix state.

Persistence strategy: the full CoreMatrix array need not be saved for M1
forward continuation. M1 uses fixed 40-byte circular slots containing the
sequence counter plus SHA-256(payload). The most recent slot is sufficient to
reproduce the next M1 returned digest because that digest depends on the
previous slot's stored payload hash and the next payload hash.

This is narrower than historical event replay or a recursively persisted hash
chain. The v1 checkpoint schema retains `is_replay_reconstructable` for
compatibility; this module does not widen that legacy field into a stronger
claim.

Checkpoint is written atomically: temp file → fsync → rename. A torn
write therefore leaves the previous checkpoint intact.
"""

import hashlib
import json
import os
import tempfile

CHECKPOINT_VERSION = '1.0.0'
DEFAULT_CHECKPOINT_PATH = os.environ.get(
    'AEGIS_CHECKPOINT_PATH',
    os.path.join(os.path.dirname(__file__), 'aegis_checkpoint.json'),
)

# M1 layout constants. Runtime addressing derives from len(matrix._m1_region)
# so reduced-memory deployments use the same slot geometry as core_matrix.py.
_M1_ENTRY_BYTES = 40   # 8 seq (little-endian) + 32 SHA-256(payload)

# Legacy/default-profile constants retained for compatibility with existing
# diagnostics and tests. Persistence addressing no longer uses _M1_SIZE.
_M1_REGION_FRACTION = 0.50
_ARRAY_TOTAL_BYTES = 4 * 1024 ** 3
_M1_SIZE = int(_ARRAY_TOTAL_BYTES * _M1_REGION_FRACTION)


class CheckpointError(Exception):
    pass


def _m1_write_head(matrix, sequence: int) -> int:
    """Return the fixed-slot byte offset for sequence in this runtime M1 region."""
    region_len = len(matrix._m1_region)
    slot_count = region_len // _M1_ENTRY_BYTES
    if slot_count <= 0:
        raise CheckpointError(
            f'M1 region must contain at least one {_M1_ENTRY_BYTES}-byte slot, '
            f'got {region_len} bytes'
        )
    return _M1_ENTRY_BYTES * (sequence % slot_count)


def _last_m1_entry(matrix) -> bytes:
    """Extract the most recent 40-byte M1 fixed slot."""
    seq = matrix._sequence
    if seq == 0:
        return b'\x00' * _M1_ENTRY_BYTES

    write_head = _m1_write_head(matrix, seq - 1)
    entry = bytes(matrix._m1_region[write_head: write_head + _M1_ENTRY_BYTES])
    if len(entry) != _M1_ENTRY_BYTES:
        raise CheckpointError(
            f'M1 entry must be {_M1_ENTRY_BYTES} bytes, got {len(entry)}'
        )
    return entry


def save_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """
    Serialize minimal CoreMatrix state to a JSON checkpoint file.
    Atomic write: temp file → fsync → rename. Never corrupts existing checkpoint.
    Returns checkpoint metadata.
    """
    with matrix._lock:
        sequence = matrix._sequence
        epoch = matrix._epoch
        era = matrix._era
        entry_bytes = _last_m1_entry(matrix)

    entry_hex = entry_bytes.hex()
    integrity_hash = hashlib.sha256(
        f'{sequence}:{epoch}:{era}:{entry_hex}'.encode()
    ).hexdigest()

    checkpoint = {
        'checkpoint_version': CHECKPOINT_VERSION,
        'sequence': sequence,
        'epoch': epoch,
        'era': era,
        'last_m1_entry_hex': entry_hex,
        'integrity_hash': integrity_hash,
        # Legacy v1 schema field. Kept byte-for-byte for compatibility; see
        # module header for the narrower continuation guarantee implemented here.
        'is_replay_reconstructable': True,
    }

    dir_ = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(checkpoint, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return {
        'sequence': sequence,
        'epoch': epoch,
        'era': era,
        'integrity_hash': integrity_hash,
        'path': path,
    }


def load_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """
    Restore CoreMatrix counters and the most recent M1 fixed slot.
    Verifies integrity hash and target slot geometry before applying any state.
    Raises CheckpointError on validation failure — matrix is left untouched.
    Returns restored metadata.
    """
    if not os.path.exists(path):
        raise CheckpointError(f'Checkpoint not found: {path}')

    with open(path, 'r') as f:
        cp = json.load(f)

    if cp.get('checkpoint_version') != CHECKPOINT_VERSION:
        raise CheckpointError(
            f'Version mismatch: expected {CHECKPOINT_VERSION}, '
            f'got {cp.get("checkpoint_version")}'
        )
    if cp.get('is_replay_reconstructable') is not True:
        raise CheckpointError('is_replay_reconstructable must be true')

    sequence = int(cp['sequence'])
    epoch = int(cp['epoch'])
    era = int(cp['era'])
    entry_hex = str(cp['last_m1_entry_hex'])

    # Integrity check
    expected = hashlib.sha256(
        f'{sequence}:{epoch}:{era}:{entry_hex}'.encode()
    ).hexdigest()
    if expected != cp.get('integrity_hash'):
        raise CheckpointError(
            'Integrity violation: checkpoint may be tampered'
        )

    entry_bytes = bytes.fromhex(entry_hex)
    if len(entry_bytes) != _M1_ENTRY_BYTES:
        raise CheckpointError(
            f'last_m1_entry_hex must decode to {_M1_ENTRY_BYTES} bytes, '
            f'got {len(entry_bytes)}'
        )

    # Validate runtime geometry before mutating the target matrix. This keeps
    # load fail-closed if the active M1 region cannot hold a complete slot.
    write_head = _m1_write_head(matrix, sequence - 1) if sequence > 0 else None

    with matrix._lock:
        if write_head is not None:
            matrix._m1_region[
                write_head: write_head + _M1_ENTRY_BYTES
            ] = entry_bytes
        matrix._sequence = sequence
        matrix._epoch = epoch
        matrix._era = era

    return {
        'sequence': sequence,
        'epoch': epoch,
        'era': era,
        'integrity_hash': cp['integrity_hash'],
        'path': path,
    }


def checkpoint_exists(path: str = DEFAULT_CHECKPOINT_PATH) -> bool:
    return os.path.exists(path)
