"""
SOVEREIGN OMEGA — Ledger Persistence
EPISTEMIC TIER: T1
Gate 170: Crash-safe checkpoint for CoreMatrix state.

Persistence strategy: the full CoreMatrix array need not be saved.
M1 is a fixed-width hash-chain log — only the most recent 40-byte entry
(sequence counter + chain hash) is required to resume the chain correctly
after restart. M2/M3 regions are calibration state that re-warms within one
epoch (100 events).

Checkpoint v2 binds the M1 record contract and the active M1 region geometry.
Legacy v1 checkpoints are intentionally rejected because their 32-byte M1
field was produced by the pre-v2 payload-hash semantics and cannot safely be
promoted to a v2 chain hash.

Checkpoint is written atomically: temp file → fsync → rename. A torn
write therefore leaves the previous checkpoint intact.

is_replay_reconstructable: True — sequence is deterministic, chain hash
resumes the hash chain from the exact commit boundary.
"""

import hashlib
import json
import os
import tempfile

CHECKPOINT_VERSION = '2.0.0'
M1_RECORD_CONTRACT = 'M1_FIXED_CHAIN_V2'
_MODULE_DIR = os.path.dirname(__file__)


def _resolve_checkpoint_paths(configured_path: str | None) -> tuple[str, str]:
    """
    Resolve active-v2 and legacy-v1 checkpoint namespaces.

    Existing deployment manifests still set AEGIS_CHECKPOINT_PATH to the
    historical basename `aegis_checkpoint.json`. Treat that exact basename as
    the legacy namespace and derive `aegis_checkpoint_v2.json` beside it so an
    existing v1 file can never be silently interpreted as v2 state.

    Any other explicit path is treated as the active v2 path; its legacy
    sibling remains `aegis_checkpoint.json` in the same directory.
    """
    if configured_path:
        directory = os.path.dirname(configured_path)
        basename = os.path.basename(configured_path)
        if basename == 'aegis_checkpoint.json':
            return (
                os.path.join(directory, 'aegis_checkpoint_v2.json'),
                configured_path,
            )
        return (
            configured_path,
            os.path.join(directory, 'aegis_checkpoint.json'),
        )

    return (
        os.path.join(_MODULE_DIR, 'aegis_checkpoint_v2.json'),
        os.path.join(_MODULE_DIR, 'aegis_checkpoint.json'),
    )


DEFAULT_CHECKPOINT_PATH, LEGACY_CHECKPOINT_PATH = _resolve_checkpoint_paths(
    os.environ.get('AEGIS_CHECKPOINT_PATH')
)

# M1 layout constants (mirror core_matrix.py — not imported to avoid circular deps)
_M1_ENTRY_BYTES = 40   # 8 seq (little-endian) + 32 chain_hash
_M1_HASH_BYTES = 32

# Legacy exported constant retained only for old tooling imports. Runtime slot
# geometry MUST derive from len(matrix._m1_region), never from this value.
_M1_REGION_FRACTION = 0.50
_ARRAY_TOTAL_BYTES = 4 * 1024 ** 3
_M1_SIZE = int(_ARRAY_TOTAL_BYTES * _M1_REGION_FRACTION)


class CheckpointError(Exception):
    pass


def _m1_geometry(matrix) -> tuple[int, int]:
    region_bytes = len(matrix._m1_region)
    slot_capacity = region_bytes // _M1_ENTRY_BYTES
    if slot_capacity <= 0:
        raise CheckpointError(
            f'M1 region must hold at least one {_M1_ENTRY_BYTES}-byte record; '
            f'got {region_bytes} bytes'
        )
    return region_bytes, slot_capacity


def _slot_offset(sequence: int, slot_capacity: int) -> int:
    return _M1_ENTRY_BYTES * (sequence % slot_capacity)


def _integrity_hash(
    checkpoint_version: str,
    record_contract: str,
    m1_region_bytes: int,
    sequence: int,
    epoch: int,
    era: int,
    entry_hex: str,
) -> str:
    material = (
        f'{checkpoint_version}:{record_contract}:{m1_region_bytes}:'
        f'{sequence}:{epoch}:{era}:{entry_hex}'
    ).encode()
    return hashlib.sha256(material).hexdigest()


def _last_m1_entry(matrix) -> bytes:
    """Extract the 40-byte M1 entry for the most recent sequence."""
    seq = matrix._sequence
    _, slot_capacity = _m1_geometry(matrix)
    if seq == 0:
        return b'\x00' * _M1_ENTRY_BYTES
    prev_seq = seq - 1
    write_head = _slot_offset(prev_seq, slot_capacity)
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
        m1_region_bytes, _ = _m1_geometry(matrix)
        entry_bytes = _last_m1_entry(matrix)

    entry_hex = entry_bytes.hex()
    integrity_hash = _integrity_hash(
        CHECKPOINT_VERSION,
        M1_RECORD_CONTRACT,
        m1_region_bytes,
        sequence,
        epoch,
        era,
        entry_hex,
    )

    checkpoint = {
        'checkpoint_version': CHECKPOINT_VERSION,
        'm1_record_contract': M1_RECORD_CONTRACT,
        'm1_region_bytes': m1_region_bytes,
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
        'checkpoint_version': CHECKPOINT_VERSION,
        'm1_record_contract': M1_RECORD_CONTRACT,
        'm1_region_bytes': m1_region_bytes,
        'sequence': sequence,
        'epoch': epoch,
        'era': era,
        'integrity_hash': integrity_hash,
        'path': path,
    }


def load_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """
    Restore CoreMatrix counters and last M1 entry from a v2 checkpoint file.
    Verifies contract, geometry and integrity before applying any state.
    Raises CheckpointError on validation failure — matrix is left untouched.
    Returns restored metadata.
    """
    if not os.path.exists(path):
        raise CheckpointError(f'Checkpoint not found: {path}')

    try:
        with open(path, 'r') as f:
            cp = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f'Checkpoint unreadable: {exc}') from exc

    if cp.get('checkpoint_version') != CHECKPOINT_VERSION:
        raise CheckpointError(
            f'Version mismatch: expected {CHECKPOINT_VERSION}, '
            f'got {cp.get("checkpoint_version")}'
        )
    if cp.get('m1_record_contract') != M1_RECORD_CONTRACT:
        raise CheckpointError(
            f'M1 record contract mismatch: expected {M1_RECORD_CONTRACT}, '
            f'got {cp.get("m1_record_contract")}'
        )
    if cp.get('is_replay_reconstructable') is not True:
        raise CheckpointError('is_replay_reconstructable must be true')

    active_region_bytes, slot_capacity = _m1_geometry(matrix)

    try:
        checkpoint_region_bytes = int(cp['m1_region_bytes'])
        sequence = int(cp['sequence'])
        epoch = int(cp['epoch'])
        era = int(cp['era'])
        entry_hex = str(cp['last_m1_entry_hex'])
    except (KeyError, TypeError, ValueError) as exc:
        raise CheckpointError(f'Malformed checkpoint fields: {exc}') from exc

    if checkpoint_region_bytes != active_region_bytes:
        raise CheckpointError(
            f'M1 region geometry mismatch: checkpoint={checkpoint_region_bytes}, '
            f'active={active_region_bytes}'
        )
    if sequence < 0 or epoch < 0 or era < 0:
        raise CheckpointError('sequence, epoch and era must be non-negative')

    expected = _integrity_hash(
        CHECKPOINT_VERSION,
        M1_RECORD_CONTRACT,
        checkpoint_region_bytes,
        sequence,
        epoch,
        era,
        entry_hex,
    )
    if expected != cp.get('integrity_hash'):
        raise CheckpointError('Integrity violation: checkpoint may be tampered')

    try:
        entry_bytes = bytes.fromhex(entry_hex)
    except ValueError as exc:
        raise CheckpointError('last_m1_entry_hex is not valid hex') from exc
    if len(entry_bytes) != _M1_ENTRY_BYTES:
        raise CheckpointError(
            f'last_m1_entry_hex must decode to {_M1_ENTRY_BYTES} bytes, '
            f'got {len(entry_bytes)}'
        )

    if sequence == 0:
        if entry_bytes != b'\x00' * _M1_ENTRY_BYTES:
            raise CheckpointError('sequence=0 checkpoint must carry a zero M1 entry')
    else:
        embedded_sequence = int.from_bytes(entry_bytes[:8], 'little')
        if embedded_sequence != sequence - 1:
            raise CheckpointError(
                f'M1 entry sequence mismatch: expected {sequence - 1}, '
                f'got {embedded_sequence}'
            )

    # All validation is complete before the first mutation.
    with matrix._lock:
        if sequence > 0:
            prev_seq = sequence - 1
            write_head = _slot_offset(prev_seq, slot_capacity)
            matrix._m1_region[write_head: write_head + _M1_ENTRY_BYTES] = entry_bytes
        matrix._sequence = sequence
        matrix._epoch = epoch
        matrix._era = era

    return {
        'checkpoint_version': CHECKPOINT_VERSION,
        'm1_record_contract': M1_RECORD_CONTRACT,
        'm1_region_bytes': active_region_bytes,
        'sequence': sequence,
        'epoch': epoch,
        'era': era,
        'integrity_hash': cp['integrity_hash'],
        'path': path,
    }


def checkpoint_exists(path: str | None = None) -> bool:
    """
    Return whether the requested checkpoint exists.

    On the active default namespace, a legacy v1 checkpoint with no v2
    successor is a migration boundary, not an empty state. Raise
    CheckpointError so bridge startup stops before BRIDGE_READY instead of
    silently starting a new chain. Explicit caller-supplied paths retain
    ordinary existence semantics.
    """
    use_default = path is None
    if path is None:
        path = DEFAULT_CHECKPOINT_PATH

    if (
        use_default
        and not os.path.exists(path)
        and os.path.exists(LEGACY_CHECKPOINT_PATH)
    ):
        raise CheckpointError(
            f'Legacy M1 checkpoint detected at {LEGACY_CHECKPOINT_PATH}; '
            'v1 cannot be promoted to M1_FIXED_CHAIN_V2 automatically'
        )
    return os.path.exists(path)
