"""AEGIS M1 transitive SHA-256 digest ring, hardware-independent.

The wire-level digest rule inherited from PR #806 remains UNCHANGED:
    h[n] = SHA256(h[n-1] || SHA256(payload[n]))
The 40-byte in-memory slot is LE_u64(sequence) || h[n]. No payload history.
Requires caller-managed exclusive write lock. This is not a pure function.
"""
import hashlib
from typing import Tuple

_ENTRY_BYTES = 40
_GENESIS = bytes(32)


def M1(state: memoryview, payload: bytes, sequence: int) -> Tuple[int, bytes]:
    """Mutate one full slot; reject invalid sequence and unsafe replay.

    The digest is a transitive commitment only. External authenticated logging
    is required for durable replay, and a checkpoint is not such a log.
    """
    if type(sequence) is not int or not 0 <= sequence < (1 << 64) - 1:
        raise ValueError('M1 requires nonnegative u64 sequence with room to increment')
    if (not isinstance(state, memoryview) or state.readonly or state.ndim != 1
            or state.itemsize != 1 or not state.contiguous):
        raise ValueError('M1 requires a contiguous writable 1-D byte memoryview')
    slots = len(state) // _ENTRY_BYTES
    if not slots:
        raise ValueError('M1 requires a complete 40-byte slot')
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError('M1 payload must be bytes-like')

    # Snapshot potentially aliased input *before* mutating any slot.
    payload_bytes = bytes(payload)
    payload_digest = hashlib.sha256(payload_bytes).digest()
    head = (sequence % slots) * _ENTRY_BYTES
    old_slot = bytes(state[head:head + _ENTRY_BYTES])

    if sequence == 0:
        if old_slot != bytes(_ENTRY_BYTES):
            raise ValueError('M1 genesis requires an empty slot')
        prior = _GENESIS
    else:
        previous = ((sequence - 1) % slots) * _ENTRY_BYTES
        prev_record = bytes(state[previous:previous + _ENTRY_BYTES])
        if (len(prev_record) != _ENTRY_BYTES or
                prev_record[:8] != (sequence - 1).to_bytes(8, 'little') or
                prev_record[8:] == _GENESIS):
            raise ValueError('M1 predecessor missing or sequence mismatch')
        prior = prev_record[8:]
        if old_slot[:8] == sequence.to_bytes(8, 'little'):
            raise ValueError('M1 repeated sequence would replace existing record')
        if sequence < slots and old_slot != bytes(_ENTRY_BYTES):
            raise ValueError('M1 unexpected occupied slot before wrap')

    chained_digest = hashlib.sha256(prior + payload_digest).digest()
    state[head:head + _ENTRY_BYTES] = sequence.to_bytes(8, 'little') + chained_digest
    return sequence + 1, chained_digest
