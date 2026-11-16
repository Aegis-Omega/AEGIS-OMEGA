"""AEGIS M1 event history chaining, isolated from hardware dependencies.

The historical log needs a separate durable payload store for full replay.
This module never reads hardware, network or files. It mutates the supplied
bounded writable memory view and uses only standard-library SHA-256.
"""

import hashlib
from typing import Tuple


def M1(state: memoryview, payload: bytes, sequence: int) -> Tuple[int, bytes]:
    """Append an M1 digest to a circular array of complete 40-byte records.

    A record stores u64 little-endian sequence followed by SHA256 of
    (previous_chain_digest || SHA256(payload)); genesis digest is 32 zeros.
    This MUTATES state, it is not pure. Payloads are not retained in the
    record arena, so full historical replay needs a separate durable log.
    """
    if type(sequence) is not int or not 0 <= sequence < (1 << 64) - 1:
        raise ValueError('M1 requires a nonnegative u64 sequence with room to increment')
    capacity = len(state) // 40
    if capacity < 1 or getattr(state, 'readonly', False):
        raise ValueError('M1 requires at least one writable 40-byte slot')
    if sequence:
        prev_pos = ((sequence - 1) % capacity) * 40
        prev_record = bytes(state[prev_pos:prev_pos + 40])
        if int.from_bytes(prev_record[:8], 'little') != sequence - 1:
            raise ValueError('M1 previous record sequence mismatch')
        prev_digest = prev_record[8:40]
        if prev_digest == b'\x00' * 32:
            raise ValueError('M1 previous digest missing')
    else:
        prev_digest = b'\x00' * 32
    payload_digest = hashlib.sha256(payload).digest()
    chain_digest = hashlib.sha256(prev_digest + payload_digest).digest()
    head = (sequence % capacity) * 40
    state[head:head + 40] = sequence.to_bytes(8, 'little') + chain_digest
    return sequence + 1, chain_digest


