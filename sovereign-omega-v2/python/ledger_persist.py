"""
SOVEREIGN OMEGA — Ledger Persistence
EPISTEMIC TIER: T1
Gate 170: Crash-safe checkpoint for CoreMatrix state.

Persistence strategy: the complete CoreMatrix memory mapping is not saved.
The checkpoint contains counters and the final 40-byte M1 slot, NOT the
full source history. Because M1's transitive chain semantics are separately
under audit, this is NOT proof of a complete event replay.

V15 binds new checkpoints to the *actual M1 region geometry*, avoiding the
old 4 GiB hardcoded modulo. Legacy checkpoints may load only when the last
record position cannot have wrapped in either layout.

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

# Preserve a backwards-compatible inspection constant, but never use
# process-global region size to locate per-instance checkpoint records.
from adaptive_memory import configured_arena_layout
_M1_ENTRY_BYTES = 40
_M1_SIZE = configured_arena_layout().m1_size


def _region_size(matrix) -> int:
    size = len(matrix._m1_region)
    if size < _M1_ENTRY_BYTES or size % _M1_ENTRY_BYTES:
        raise CheckpointError('M1_REGION_ALIGNMENT_INVALID')
    return size



class CheckpointError(Exception):
    pass


def _last_m1_entry(matrix) -> bytes:
    """Extract the 40-byte M1 entry for the most recent sequence."""
    seq = matrix._sequence
    if seq == 0:
        return b'\x00' * _M1_ENTRY_BYTES
    prev_seq = seq - 1
    write_head = (prev_seq * _M1_ENTRY_BYTES) % _region_size(matrix)
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
        region_bytes = _region_size(matrix)
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
        'is_replay_reconstructable': True,  # legacy flag; does not certify raw event history
        'm1_region_bytes': region_bytes,
        'layout_integrity_hash': hashlib.sha256(
            f'{integrity_hash}:{region_bytes}'.encode('ascii')
        ).hexdigest(),
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

    # Geometry validation precedes all state mutations. Existing legacy v1
    # snapshots have no length binding: only permit an initial non-wrap
    # region where offsets coincide across all compatible arena sizes.
    with matrix._lock:
        region_bytes = _region_size(matrix)
        stored_size = cp.get('m1_region_bytes')
        if stored_size is None:
            if sequence * _M1_ENTRY_BYTES > region_bytes:
                raise CheckpointError('LEGACY_CHECKPOINT_GEOMETRY_UNKNOWN')
        else:
            if type(stored_size) is not int or stored_size != region_bytes:
                raise CheckpointError('M1_REGION_SIZE_MISMATCH')
            layout_hash = hashlib.sha256(
                f'{expected}:{stored_size}'.encode('ascii')
            ).hexdigest()
            if cp.get('layout_integrity_hash') != layout_hash:
                raise CheckpointError('M1_LAYOUT_HASH_MISMATCH')
        if sequence > 0:
            prev_seq = sequence - 1
            write_head = (prev_seq * _M1_ENTRY_BYTES) % region_bytes
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
