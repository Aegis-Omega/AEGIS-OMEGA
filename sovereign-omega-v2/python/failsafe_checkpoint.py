"""Strict, source-bound epoch-failsafe continuation for CoreMatrix checkpoints.

Reuses EpochFailsafeController.export_checkpoint/import_checkpoint, but validates
the entire untrusted snapshot in an isolated controller before installation.
Snapshot hashes are integrity checks, not authentication or signed provenance.
"""
import hashlib
import os
import string

from epoch_failsafe import EpochFailsafeController, EpochState

FAILSAFE_CONTRACT = 'epoch-failsafe-continuation-v1'
MAX_SNAPSHOT_BYTES = int(os.environ.get('AEGIS_FAILSAFE_MAX_SNAPSHOT_BYTES', str(64 * 1024 * 1024)))
MAX_LOG_EVENTS = int(os.environ.get('AEGIS_FAILSAFE_MAX_LOG_EVENTS', '1000000'))
if MAX_SNAPSHOT_BYTES <= 0 or MAX_LOG_EVENTS <= 0:
    raise ValueError('Failsafe resource limits must be positive')


class FailsafeCheckpointError(ValueError):
    """Unsafe, incomplete, or incompatible failsafe state."""


def _check(value, message):
    if not value:
        raise FailsafeCheckpointError(message)


def _uint(value):
    return type(value) is int and value >= 0


def _snapshot(row, label):
    if row is None:
        return
    _check(type(row) is dict, f'{label} must be an object')
    _check(set(row) == {
        'epoch_id', 'snapshot_hash', 'event_count', 'last_event_sequence',
        'timestamp_sequence', 'state_bytes_hex',
    }, f'{label} schema mismatch')
    _check(all(_uint(row[k]) for k in (
        'epoch_id', 'event_count', 'last_event_sequence', 'timestamp_sequence'
    )) and row['epoch_id'] < (1 << 64) and
           row['last_event_sequence'] < (1 << 64),
           f'{label} counters invalid or exceed u64')
    h, payload = row['snapshot_hash'], row['state_bytes_hex']
    _check(type(h) is str and len(h) == 64 and
           all(c in '0123456789abcdef' for c in h),
           f'{label} digest format invalid')
    _check(type(payload) is str and
           len(payload) <= MAX_SNAPSHOT_BYTES * 2 and
           len(payload) % 2 == 0 and
           all(c in string.hexdigits for c in payload),
           f'{label} payload invalid or exceeds configured size')
    state = bytes.fromhex(payload)
    actual = hashlib.sha256(
        state + row['epoch_id'].to_bytes(8, 'little')
        + row['last_event_sequence'].to_bytes(8, 'little')
    ).hexdigest()
    _check(h == actual, f'{label} SHA256 integrity violation')


def prepare_failsafe_restore(controller, data):
    """Fully validate and decode into an isolated controller, never mutating target."""
    _check(isinstance(controller, EpochFailsafeController),
           'Real EpochFailsafeController required')
    _check(type(data) is dict, 'Failsafe record must be an object')
    required = {
        'state', 'corruption_count', 'consecutive_failures', 'failure_threshold',
        'epoch_n', 'epoch_n1', 'failsafe_log',
    }
    _check(set(data) == required, 'Failsafe record schema mismatch')
    _check(type(data['state']) is str and
           data['state'] in {state.value for state in EpochState},
           'Failsafe state missing or invalid; never default to ACTIVE')
    _check(all(_uint(data[k]) for k in ('corruption_count', 'consecutive_failures')),
           'Failsafe counters invalid')
    _check(type(data['failure_threshold']) is int and
           data['failure_threshold'] == controller._failure_threshold and
           data['failure_threshold'] >= 1,
           'Failsafe threshold incompatible with source controller')
    _check(data['consecutive_failures'] <= data['failure_threshold'],
           'Failsafe failure count exceeds threshold')
    if data['state'] == EpochState.FROZEN.value:
        _check(data['corruption_count'] > 0, 'Frozen state missing corruption evidence')

    _snapshot(data['epoch_n'], 'epoch_n')
    _snapshot(data['epoch_n1'], 'epoch_n1')

    log = data['failsafe_log']
    _check(type(log) is list and len(log) <= MAX_LOG_EVENTS,
           'Failsafe log invalid or exceeds configured size')
    expected_fields = {
        'epoch_id', 'trigger_reason', 'buffer_id', 'snapshot_hash_before',
        'snapshot_hash_after', 'recovery_successful', 'consensus_rounds',
        'timestamp_sequence',
    }
    for event in log:
        _check(type(event) is dict and set(event) == expected_fields,
               'Failsafe log record schema mismatch')
        _check(type(event['epoch_id']) is int and event['epoch_id'] >= -1 and
               _uint(event['consensus_rounds']) and
               event['consensus_rounds'] <= controller.QUICK_CONSENSUS_ROUNDS and
               _uint(event['timestamp_sequence']) and
               type(event['recovery_successful']) is bool,
               'Failsafe log record counters invalid')
        _check(all(type(event[k]) is str and len(event[k]) <= 4096 for k in (
            'trigger_reason', 'buffer_id', 'snapshot_hash_before',
            'snapshot_hash_after',
        )), 'Failsafe log text invalid')
        _check(event['buffer_id'] in ('En', 'En+1'),
               'Failsafe buffer identifier invalid')

    # The original import verifies both SHA-256 snapshots; isolation prevents
    # any malformed event record from mutating the actual CoreMatrix controller.
    isolated = EpochFailsafeController()
    try:
        imported = isolated.import_checkpoint(data)
    except (TypeError, ValueError, KeyError, OverflowError) as err:
        raise FailsafeCheckpointError('Failsafe decode rejected input') from err
    _check(imported is True, 'Failsafe snapshot integrity failed')
    _check(isolated.export_checkpoint() == data,
           'Failsafe decoded state differs from checkpoint')
    return isolated


def snapshot_failsafe(controller):
    """Capture the installed failsafe state including quarantine, history, and buffers."""
    _check(isinstance(controller, EpochFailsafeController),
           'Real failsafe controller required')
    data = controller.export_checkpoint()
    prepare_failsafe_restore(controller, data)
    return data


def require_fresh_failsafe(target):
    """Validate the real destination before any M1 or calibration mutation."""
    _check(isinstance(target, EpochFailsafeController),
           'Failsafe restore target type mismatch')
    with target._lock:
        _check(target._state == EpochState.ACTIVE and
               target._epoch_n is None and target._epoch_n1 is None and
               target._consecutive_failures == 0 and
               target._corruption_count == 0 and
               not target._failsafe_log,
               'Failsafe restore target is not fresh')


def install_failsafe(target, prepared):
    """Install validated state into an unused controller, preserving callbacks."""
    _check(isinstance(prepared, EpochFailsafeController),
           'Prepared failsafe controller type mismatch')
    with target._lock:
        require_fresh_failsafe(target)
        target._epoch_n = prepared._epoch_n
        target._epoch_n1 = prepared._epoch_n1
        target._state = prepared._state
        target._corruption_count = prepared._corruption_count
        target._consecutive_failures = prepared._consecutive_failures
        target._failure_threshold = prepared._failure_threshold
        target._failsafe_log = list(prepared._failsafe_log)
