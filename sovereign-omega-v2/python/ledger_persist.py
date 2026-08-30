"""
SOVEREIGN OMEGA — Ledger Persistence
EPISTEMIC TIER: T1
Gate 170: Crash-safe checkpoint for CoreMatrix state.

Persistence strategy: the full 4GB CoreMatrix array need not be saved.
M1 is a hash-chain log — only the most recent 40-byte entry (sequence
counter + chain hash) is required to resume the chain correctly after
restart. M2/M3 regions are calibration state that re-warms within one
epoch (100 events).

Checkpoint is written atomically: temp file → fsync → rename. A torn
write therefore leaves the previous checkpoint intact.

is_replay_reconstructable: True — sequence is deterministic, chain hash
resumes the hash chain from the exact commit boundary.
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

# M1 layout constants (mirror core_matrix.py — not imported to avoid circular deps)
_M1_ENTRY_BYTES = 40   # 8 seq (little-endian) + 32 chain_hash
_M1_REGION_FRACTION = 0.50
_ARRAY_TOTAL_BYTES = 4 * 1024 ** 3
_M1_SIZE = int(_ARRAY_TOTAL_BYTES * _M1_REGION_FRACTION)


class CheckpointError(Exception):
    pass


def _last_m1_entry(matrix) -> bytes:
    """Extract the 40-byte M1 entry for the most recent sequence."""
    seq = matrix._sequence
    if seq == 0:
        return b'\x00' * _M1_ENTRY_BYTES
    prev_seq = seq - 1
    write_head = (prev_seq * _M1_ENTRY_BYTES) % _M1_SIZE
    return bytes(matrix._m1_region[write_head: write_head + _M1_ENTRY_BYTES])


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
    Restore CoreMatrix counters and last M1 entry from a checkpoint file.
    Verifies integrity hash before applying any state.
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
            f'Integrity violation: checkpoint may be tampered'
        )

    entry_bytes = bytes.fromhex(entry_hex)
    if len(entry_bytes) != _M1_ENTRY_BYTES:
        raise CheckpointError(
            f'last_m1_entry_hex must decode to {_M1_ENTRY_BYTES} bytes, '
            f'got {len(entry_bytes)}'
        )

    # Restore: write last M1 entry back to correct position, set counters
    with matrix._lock:
        if sequence > 0:
            prev_seq = sequence - 1
            write_head = (prev_seq * _M1_ENTRY_BYTES) % _M1_SIZE
            matrix._m1_region[write_head: write_head + _M1_ENTRY_BYTES] = entry_bytes
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
