"""SOVEREIGN OMEGA -- Ledger Persistence, chain-continuation checkpoint V2.

Each M1 ring slot is 8-byte sequence + 32-byte SHA-256 *chain* digest.
Only the chain tail is checkpointed; raw event bodies are NOT retained.
A checkpoint alone does not make the event history replay-reconstructable.
Legacy V1 stored a payload hash, not a chain hash, so V1 MUST NOT resume V2.
"""
import hashlib
import hmac
import json
import os
import tempfile

CHECKPOINT_VERSION = '2.0.0'
CHAIN_ALGORITHM = 'AEGIS-M1-CHAIN-V2'
DEFAULT_CHECKPOINT_PATH = os.environ.get(
    'AEGIS_CHECKPOINT_PATH',
    os.path.join(os.path.dirname(__file__), 'aegis_checkpoint.json'),
)
_M1_ENTRY_BYTES = 40
_M1_SIZE = 2 * 1024 ** 3  # Legacy constant; V2 indexes actual matrix region.


class CheckpointError(Exception):
    pass


def _capacity(matrix) -> int:
    slots = len(matrix._m1_region) // _M1_ENTRY_BYTES
    if slots < 1:
        raise CheckpointError('M1 region has no complete digest slots')
    return slots


def _last_m1_entry(matrix) -> bytes:
    """Read the last full u64 sequence + 32-byte chain digest slot."""
    seq = matrix._sequence
    slots = _capacity(matrix)
    if not isinstance(seq, int) or not 0 <= seq < (1 << 64):
        raise CheckpointError('checkpoint sequence out of u64 range')
    if seq == 0:
        return bytes(_M1_ENTRY_BYTES)
    prev_seq = seq - 1
    offset = (prev_seq % slots) * _M1_ENTRY_BYTES
    entry = bytes(matrix._m1_region[offset:offset + _M1_ENTRY_BYTES])
    if (len(entry) != _M1_ENTRY_BYTES
            or entry[:8] != prev_seq.to_bytes(8, 'little')
            or entry[8:] == bytes(32)):
        raise CheckpointError('last M1 chain digest missing or sequence mismatch')
    return entry


def _integrity_hash(checkpoint_fields: dict) -> str:
    """Unkeyed checksum, NOT an authenticity signature or MAC."""
    return hashlib.sha256(json.dumps(
        checkpoint_fields, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True,
    ).encode('utf-8')).hexdigest()


def save_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """Atomically replace a V2 chain-tail checkpoint under the matrix lock."""
    with matrix._lock:
        fields = {
            'checkpoint_version': CHECKPOINT_VERSION,
            'chain_algorithm': CHAIN_ALGORITHM,
            'm1_capacity_slots': _capacity(matrix),
            'sequence': matrix._sequence,
            'epoch': matrix._epoch,
            'era': matrix._era,
            'total_processed': getattr(matrix, '_total_processed', matrix._sequence),
            'total_verified': getattr(matrix, '_total_verified', 0),
            'total_vcg_error_fixed': getattr(matrix, '_total_vcg_error_fixed', 0),
            'last_m1_entry_hex': _last_m1_entry(matrix).hex(),
            'can_resume_chain': True,
            'is_replay_reconstructable': False,
        }
    counters = ('sequence', 'epoch', 'era', 'total_processed',
                'total_verified', 'total_vcg_error_fixed')
    if any(type(fields[k]) is not int or fields[k] < 0 for k in counters):
        raise CheckpointError('invalid checkpoint counters')
    if (fields['sequence'] != fields['total_processed'] or
            fields['total_verified'] > fields['total_processed'] or
            fields['total_vcg_error_fixed'] > fields['total_verified'] * 65536):
        raise CheckpointError('checkpoint counters do not satisfy invariants')
    checkpoint = {**fields, 'integrity_hash': _integrity_hash(fields)}
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(checkpoint, out, sort_keys=True)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {
        'sequence': fields['sequence'], 'epoch': fields['epoch'],
        'era': fields['era'], 'integrity_hash': checkpoint['integrity_hash'],
        'path': path, 'can_resume_chain': True,
        'is_replay_reconstructable': False,
    }


def load_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """Restore a V2 chain tail, rejecting V1 and any mismatched region.

    Validation completes before any destination mutation. An unkeyed checksum
    cannot detect intentional editing by an actor with checkpoint write access.
    """
    if not os.path.exists(path):
        raise CheckpointError(f'Checkpoint not found: {path}')
    try:
        with open(path, 'r', encoding='utf-8') as inp:
            cp = json.load(inp)
    except (OSError, ValueError, TypeError) as exc:
        raise CheckpointError(f'Invalid checkpoint JSON: {exc}') from exc
    if not isinstance(cp, dict):
        raise CheckpointError('checkpoint root must be an object')
    if cp.get('checkpoint_version') != CHECKPOINT_VERSION:
        raise CheckpointError(
            'Unsupported checkpoint version (V1 contained payload hashes, not '
            'chain digests); explicit migration with external event log required'
        )
    fields = {key: val for key, val in cp.items() if key != 'integrity_hash'}
    if not hmac.compare_digest(_integrity_hash(fields), str(cp.get('integrity_hash', ''))):
        raise CheckpointError('checkpoint checksum mismatch')
    if (cp.get('chain_algorithm') != CHAIN_ALGORITHM
            or cp.get('can_resume_chain') is not True
            or cp.get('is_replay_reconstructable') is not False):
        raise CheckpointError('checkpoint chain/replay contract mismatch')
    slots = _capacity(matrix)
    if type(cp.get('m1_capacity_slots')) is not int or cp['m1_capacity_slots'] != slots:
        raise CheckpointError('M1 region capacity differs from checkpoint')
    counters = ('sequence', 'epoch', 'era', 'total_processed',
                'total_verified', 'total_vcg_error_fixed')
    if any(type(cp.get(k)) is not int or cp[k] < 0 for k in counters):
        raise CheckpointError('invalid checkpoint counters')
    sequence = cp['sequence']
    if (sequence != cp['total_processed'] or
            cp['total_verified'] > cp['total_processed'] or
            cp['total_vcg_error_fixed'] > cp['total_verified'] * 65536):
        raise CheckpointError('checkpoint counters do not satisfy invariants')
    if sequence >= 1 << 64:
        raise CheckpointError('checkpoint sequence out of u64 range')
    if not isinstance(cp.get('last_m1_entry_hex'), str):
        raise CheckpointError('missing or non-string M1 entry hex')
    try:
        entry = bytes.fromhex(cp['last_m1_entry_hex'])
    except (TypeError, ValueError) as exc:
        raise CheckpointError('invalid M1 entry hex') from exc
    if len(entry) != _M1_ENTRY_BYTES or entry.hex() != cp['last_m1_entry_hex']:
        raise CheckpointError('invalid M1 entry format')
    if sequence == 0:
        if entry != bytes(_M1_ENTRY_BYTES):
            raise CheckpointError('genesis checkpoint entry must be zero')
    elif (entry[:8] != (sequence - 1).to_bytes(8, 'little')
            or entry[8:] == bytes(32)):
        raise CheckpointError('checkpoint M1 chain tail does not match sequence')

    with matrix._lock:
        if getattr(matrix, '_sequence', None) != 0 or getattr(matrix, '_total_processed', 0) != 0:
            raise CheckpointError('load requires a fresh, unprocessed matrix')
        if sequence > 0:
            offset = ((sequence - 1) % slots) * _M1_ENTRY_BYTES
            matrix._m1_region[offset:offset + _M1_ENTRY_BYTES] = entry
        else:
            matrix._m1_region[:_M1_ENTRY_BYTES] = bytes(_M1_ENTRY_BYTES)
        matrix._sequence = sequence
        matrix._epoch = cp['epoch']
        matrix._era = cp['era']
        matrix._total_processed = cp['total_processed']
        matrix._total_verified = cp['total_verified']
        matrix._total_vcg_error_fixed = cp['total_vcg_error_fixed']
        matrix._m3_active_length = 0  # M3 context bytes were not checkpointed
    return {
        'sequence': sequence, 'epoch': cp['epoch'], 'era': cp['era'],
        'integrity_hash': cp['integrity_hash'], 'path': path,
        'can_resume_chain': True, 'is_replay_reconstructable': False,
    }


def checkpoint_exists(path: str = DEFAULT_CHECKPOINT_PATH) -> bool:
    return os.path.exists(path)
