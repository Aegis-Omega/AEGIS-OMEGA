"""AEGIS Omega / Gate 170: versioned M1 hash-chain continuation checkpoint.

The V2 40-byte event header stores sequence + a chain digest, not a payload.
The last header can restart the chain, but cannot replay historical payloads.
The unkeyed integrity hash detects corruption, NOT authenticated provenance.
Legacy V1 checkpoints stored payload hashes and MUST NOT be interpreted as V2.
"""
import hashlib
import json
import os
import tempfile

CHECKPOINT_VERSION = '2.0.0'
CHAIN_MODE = 'sha256-prev-chain-plus-sha256-payload-v2'
DEFAULT_CHECKPOINT_PATH = os.environ.get(
    'AEGIS_CHECKPOINT_PATH',
    os.path.join(os.path.dirname(__file__), 'aegis_checkpoint.json'),
)
_M1_ENTRY_BYTES = 40
_M1_REGION_FRACTION = 0.50
_ARRAY_TOTAL_BYTES = 4 * 1024 ** 3
_M1_SIZE = int(_ARRAY_TOTAL_BYTES * _M1_REGION_FRACTION)  # nominal, for legacy test imports only


class CheckpointError(Exception):
    pass


def _m1_slots(matrix):
    slots = len(matrix._m1_region) // _M1_ENTRY_BYTES
    if slots < 1:
        raise CheckpointError('M1 region has no complete record')
    return slots


def _last_m1_entry(matrix):
    sequence = matrix._sequence
    if sequence == 0:
        return b'\x00' * _M1_ENTRY_BYTES
    if sequence < 0 or sequence >= (1 << 64):
        raise CheckpointError('M1 sequence outside u64 range')
    position = ((sequence - 1) % _m1_slots(matrix)) * _M1_ENTRY_BYTES
    record = bytes(matrix._m1_region[position:position + _M1_ENTRY_BYTES])
    if len(record) != _M1_ENTRY_BYTES:
        raise CheckpointError('M1 record truncated')
    if int.from_bytes(record[:8], 'little') != sequence - 1:
        raise CheckpointError('M1 record sequence mismatch')
    if record[8:] == b'\x00' * 32:
        raise CheckpointError('M1 record digest missing')
    return record


def _integrity_hash(obj):
    return hashlib.sha256(json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
        allow_nan=False,
    ).encode('utf-8')).hexdigest()


def save_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """Persist a chain-continuation anchor atomically; not the event history."""
    with matrix._lock:
        body = {
            'checkpoint_version': CHECKPOINT_VERSION,
            'chain_mode': CHAIN_MODE,
            'sequence': matrix._sequence,
            'epoch': matrix._epoch,
            'era': matrix._era,
            'm1_capacity_slots': _m1_slots(matrix),
            'last_m1_entry_hex': _last_m1_entry(matrix).hex(),
            'is_replay_reconstructable': False,
            'is_chain_continuation_supported': True,
        }
    body['integrity_hash'] = _integrity_hash(body)
    fd, temp_path = tempfile.mkstemp(
        dir=os.path.dirname(os.path.abspath(path)) or '.', suffix='.tmp',
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(body, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return {
        'sequence': body['sequence'], 'epoch': body['epoch'],
        'era': body['era'], 'integrity_hash': body['integrity_hash'], 'path': path,
    }


def load_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """Validate all fields before modifying the destination matrix."""
    if not os.path.exists(path):
        raise CheckpointError(f'Checkpoint not found: {path}')
    with open(path, encoding='utf-8') as handle:
        body = json.load(handle)
    if not isinstance(body, dict):
        raise CheckpointError('Checkpoint must be an object')
    if body.get('checkpoint_version') != CHECKPOINT_VERSION:
        raise CheckpointError(
            f'Version mismatch: expected {CHECKPOINT_VERSION}, '
            f'got {body.get("checkpoint_version")}'
        )
    if body.get('chain_mode') != CHAIN_MODE:
        raise CheckpointError('Unknown M1 chain mode')
    if body.get('is_replay_reconstructable') is not False:
        raise CheckpointError('Full historical replay cannot be claimed by V2')
    if body.get('is_chain_continuation_supported') is not True:
        raise CheckpointError('Missing chain continuation declaration')
    actual_digest = body.get('integrity_hash')
    expected_digest = _integrity_hash({
        k: v for k, v in body.items() if k != 'integrity_hash'
    })
    if actual_digest != expected_digest:
        raise CheckpointError('Integrity violation: checkpoint data changed')
    try:
        sequence = int(body['sequence'])
        epoch = int(body['epoch'])
        era = int(body['era'])
        capacity = int(body['m1_capacity_slots'])
        record = bytes.fromhex(body['last_m1_entry_hex'])
    except (TypeError, ValueError, KeyError) as err:
        raise CheckpointError('Malformed checkpoint') from err
    if not 0 <= sequence < (1 << 64) or epoch < 0 or era < 0:
        raise CheckpointError('Invalid counters')
    if capacity != _m1_slots(matrix):
        raise CheckpointError('M1 capacity mismatch; refusing relocation')
    if len(record) != _M1_ENTRY_BYTES:
        raise CheckpointError('M1 record must contain 40 bytes')
    if sequence:
        if int.from_bytes(record[:8], 'little') != sequence - 1:
            raise CheckpointError('M1 record sequence mismatch')
        if record[8:] == b'\x00' * 32:
            raise CheckpointError('M1 record digest missing')
    elif record != b'\x00' * _M1_ENTRY_BYTES:
        raise CheckpointError('Genesis record must be all zeroes')
    with matrix._lock:
        if sequence:
            head = ((sequence - 1) % capacity) * _M1_ENTRY_BYTES
            matrix._m1_region[head:head + _M1_ENTRY_BYTES] = record
        matrix._sequence = sequence
        matrix._epoch = epoch
        matrix._era = era
    return {
        'sequence': sequence, 'epoch': epoch, 'era': era,
        'integrity_hash': actual_digest, 'path': path,
    }


def checkpoint_exists(path: str = DEFAULT_CHECKPOINT_PATH) -> bool:
    return os.path.exists(path)
