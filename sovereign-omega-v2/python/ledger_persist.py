"""AEGIS Omega / Gate 170: versioned M1 hash-chain continuation checkpoint.

The V2 40-byte event header stores sequence + a chain digest, not a payload.
The last header can restart the chain, but cannot replay historical payloads.
The unkeyed integrity hash detects corruption, NOT authenticated provenance.
Legacy V1 checkpoints stored payload hashes and MUST NOT be interpreted as V2.
"""
import hashlib
from contextlib import nullcontext
import json
import os
import tempfile

from calibration_checkpoint import (
    CalibrationCheckpointError, snapshot_calibration,
    prepare_calibration_restore, require_fresh_calibrator,
    install_calibration,
)
from failsafe_checkpoint import (
    FailsafeCheckpointError, snapshot_failsafe,
    prepare_failsafe_restore, require_fresh_failsafe,
    install_failsafe,
)

CHECKPOINT_VERSION = '2.3.0'  # Adds lossless failsafe quarantine continuation
CHAIN_MODE = 'sha256-prev-chain-plus-sha256-payload-v2'  # identical PR #806 M1 digest
STATE_CONTRACT = 'm123-calibration-and-failsafe-state-v3'
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
    """Snapshot M1 and calibration as one consistent continuation state."""
    calibrator = getattr(matrix, '_calibrator', None)
    # Lock order matches CoreMatrix.process_event(): matrix -> calibrator.
    # Chain-only fixtures have no calibrator and require no extra lock.
    calibration_lock = (calibrator._lock if calibrator is not None
                        else nullcontext())
    with matrix._lock, calibration_lock:
        if calibrator is not None:
            try:
                calibration = snapshot_calibration(calibrator)
                if calibration['epoch'] != matrix._epoch:
                    raise CalibrationCheckpointError('matrix and calibrator epochs disagree')
            except CalibrationCheckpointError as err:
                raise CheckpointError('Unsafe calibration checkpoint: ' + str(err)) from err
        else:
            # Chain-only mock/standalone use is explicit and NEVER claims
            # calibration continuation. A real CoreMatrix always has _calibrator.
            calibration = None
        failsafe = getattr(matrix, '_failsafe', None)
        if failsafe is not None:
            try:
                failsafe_state = snapshot_failsafe(failsafe)
            except FailsafeCheckpointError as err:
                raise CheckpointError('Unsafe failsafe checkpoint: ' + str(err)) from err
        else:
            failsafe_state = None
        body = {
            'checkpoint_version': CHECKPOINT_VERSION,
            'chain_mode': CHAIN_MODE,
            'sequence': matrix._sequence,
            'epoch': matrix._epoch,
            'era': matrix._era,
            'm1_capacity_slots': _m1_slots(matrix),
            'state_contract': STATE_CONTRACT,
            'calibration_snapshot': calibration,
            'is_calibration_continuation_supported': calibration is not None,
            'failsafe_snapshot': failsafe_state,
            'is_failsafe_continuation_supported': failsafe_state is not None,
            'total_processed': getattr(matrix, '_total_processed', matrix._sequence),
            'total_verified': getattr(matrix, '_total_verified', 0),
            'total_vcg_error_fixed': getattr(matrix, '_total_vcg_error_fixed', 0),
            'last_gate_signal_sequence': getattr(matrix, '_last_gate_signal_sequence', -1),
            'last_gate_signal_accepted': getattr(matrix, '_last_gate_signal_accepted', None),
            'last_m1_entry_hex': _last_m1_entry(matrix).hex(),
            'is_replay_reconstructable': False,
            'is_chain_continuation_supported': True,
        }
    counters = ('sequence', 'epoch', 'era', 'total_processed',
                'total_verified', 'total_vcg_error_fixed')
    if any(type(body[k]) is not int or body[k] < 0 for k in counters):
        raise CheckpointError('Invalid checkpoint counters')
    if (body['total_processed'] != body['sequence'] or
            body['total_verified'] > body['total_processed'] or
            body['total_vcg_error_fixed'] > body['total_verified'] * 65536):
        raise CheckpointError('Inconsistent calibration counters')
    if (type(body['last_gate_signal_sequence']) is not int or
            body['last_gate_signal_sequence'] < -1 or
            body['last_gate_signal_accepted'] is not None and
            type(body['last_gate_signal_accepted']) is not bool):
        raise CheckpointError('Invalid gate observation metadata')
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
        'checkpoint_version': CHECKPOINT_VERSION,
        'is_replay_reconstructable': False,
        'is_chain_continuation_supported': True,
        'is_calibration_continuation_supported': calibration is not None,
        'is_failsafe_continuation_supported': failsafe_state is not None,
    }


def load_checkpoint(matrix, path: str = DEFAULT_CHECKPOINT_PATH) -> dict:
    """Lock destination through full validation and atomic state installation.

    In particular, independent calibrate_epoch callers must not alter the
    destination between prepare_calibration_restore and install_calibration.
    Lock order is always CoreMatrix -> calibrator (both are RLocks).
    """
    calibrator = getattr(matrix, '_calibrator', None)
    calibration_lock = (calibrator._lock if calibrator is not None
                        else nullcontext())
    with matrix._lock, calibration_lock:
        return _load_checkpoint_locked(matrix, path)


def _load_checkpoint_locked(matrix, path: str) -> dict:
    """Validate all fields before modifying the destination matrix.

    Caller holds the matrix lock and the calibrator lock if attached.
    """
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
    if body.get('state_contract') != STATE_CONTRACT:
        raise CheckpointError('Unknown checkpoint calibration contract')
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
    calibration = body.get('calibration_snapshot')
    is_calibration = body.get('is_calibration_continuation_supported')
    if type(is_calibration) is not bool:
        raise CheckpointError('Missing calibration-continuation declaration')
    if is_calibration != (calibration is not None):
        raise CheckpointError('Calibration snapshot/declaration mismatch')
    calibrator = getattr(matrix, '_calibrator', None)
    if is_calibration:
        if calibrator is None:
            raise CheckpointError('Cannot restore calibration into chain-only matrix')
        # The exact epoch and token identities are validated below, before
        # any M1 state is modified.
    elif calibrator is not None:
        raise CheckpointError('Real CoreMatrix requires full calibration checkpoint')
    failsafe_data = body.get('failsafe_snapshot')
    is_failsafe = body.get('is_failsafe_continuation_supported')
    if type(is_failsafe) is not bool:
        raise CheckpointError('Missing failsafe-continuation declaration')
    if is_failsafe != (failsafe_data is not None):
        raise CheckpointError('Failsafe snapshot/declaration mismatch')
    failsafe = getattr(matrix, '_failsafe', None)
    if is_failsafe:
        if failsafe is None:
            raise CheckpointError('Cannot restore failsafe into chain-only matrix')
    elif failsafe is not None:
        raise CheckpointError('Real CoreMatrix requires full failsafe checkpoint')

    counter_keys = ('sequence', 'epoch', 'era', 'total_processed',
                    'total_verified', 'total_vcg_error_fixed')
    if any(type(body.get(k)) is not int or body[k] < 0 for k in counter_keys):
        raise CheckpointError('Malformed calibration counters')
    sequence = body['sequence']
    epoch, era = body['epoch'], body['era']
    if (sequence != body['total_processed'] or
            body['total_verified'] > body['total_processed'] or
            body['total_vcg_error_fixed'] > body['total_verified'] * 65536):
        raise CheckpointError('Inconsistent calibration counters')
    if (type(body.get('last_gate_signal_sequence')) is not int or
            body['last_gate_signal_sequence'] < -1 or
            body.get('last_gate_signal_accepted') is not None and
            type(body['last_gate_signal_accepted']) is not bool):
        raise CheckpointError('Invalid gate observation metadata')
    try:
        if type(body['m1_capacity_slots']) is not int:
            raise ValueError('capacity must be integer')
        capacity = body['m1_capacity_slots']
        if not isinstance(body['last_m1_entry_hex'], str):
            raise ValueError('entry must be hex string')
        record = bytes.fromhex(body['last_m1_entry_hex'])
    except (TypeError, ValueError, KeyError) as err:
        raise CheckpointError('Malformed checkpoint') from err
    if sequence >= (1 << 64): raise CheckpointError('Sequence outside u64 range')
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
    if is_calibration:
        try:
            prepared = prepare_calibration_restore(calibrator, calibration, epoch)
        except CalibrationCheckpointError as err:
            raise CheckpointError('Unsafe calibration restore: ' + str(err)) from err
    else:
        prepared = None
    if is_failsafe:
        try:
            prepared_failsafe = prepare_failsafe_restore(failsafe, failsafe_data)
        except FailsafeCheckpointError as err:
            raise CheckpointError('Unsafe failsafe restore: ' + str(err)) from err
    else:
        prepared_failsafe = None
    # Matrix and calibrator locks are already held by load_checkpoint().
    if getattr(matrix, '_sequence', -1) != 0 or getattr(matrix, '_total_processed', 0) != 0:
        raise CheckpointError('Resume requires an unprocessed matrix')
    if prepared is not None:
        try:
            require_fresh_calibrator(calibrator)
        except CalibrationCheckpointError as err:
            raise CheckpointError('Unsafe calibration target: ' + str(err)) from err
    if prepared_failsafe is not None:
        try:
            require_fresh_failsafe(failsafe)
        except FailsafeCheckpointError as err:
            raise CheckpointError('Unsafe failsafe target: ' + str(err)) from err
    if sequence:
        head = ((sequence - 1) % capacity) * _M1_ENTRY_BYTES
        matrix._m1_region[head:head + _M1_ENTRY_BYTES] = record
    matrix._sequence = sequence
    matrix._epoch = epoch
    matrix._era = era
    matrix._total_processed = body['total_processed']
    matrix._total_verified = body['total_verified']
    matrix._total_vcg_error_fixed = body['total_vcg_error_fixed']
    matrix._last_gate_signal_sequence = body['last_gate_signal_sequence']
    matrix._last_gate_signal_accepted = body['last_gate_signal_accepted']
    matrix._m3_active_length = 0  # context is ephemeral, not replayed
    if prepared is not None:
        install_calibration(calibrator, prepared)
    if prepared_failsafe is not None:
        install_failsafe(failsafe, prepared_failsafe)
    return {
        'sequence': sequence, 'epoch': epoch, 'era': era,
        'integrity_hash': actual_digest, 'path': path,
        'is_calibration_continuation_supported': is_calibration,
        'is_failsafe_continuation_supported': is_failsafe,
    }


def checkpoint_exists(path: str = DEFAULT_CHECKPOINT_PATH) -> bool:
    return os.path.exists(path)
