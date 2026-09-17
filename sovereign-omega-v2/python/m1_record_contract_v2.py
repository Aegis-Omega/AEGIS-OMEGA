"""
AEGIS M1 Record Contract V2 — inert reference model.

AUTHORITY_EFFECT: NONE
PRODUCTION_WIRING: NONE

Defines the smallest internally coherent M1 record semantics implied by the
existing ledger persistence contract:

    entry = sequence:u64le || chain_hash:sha256
    chain_0 = SHA256(ZERO32 || SHA256(payload_0))
    chain_n = SHA256(chain_(n-1) || SHA256(payload_n))
    byte_offset = 40 * (sequence mod slot_capacity)

Raw payload bytes are hashed but are not stored in the fixed-width M1 entry.
This module is a reference contract only; core_matrix.py does not import it.
"""

import hashlib
from typing import Tuple

M1_SEQUENCE_BYTES = 8
M1_HASH_BYTES = 32
M1_ENTRY_BYTES = M1_SEQUENCE_BYTES + M1_HASH_BYTES
M1_GENESIS_HASH = b'\x00' * M1_HASH_BYTES
_U64_MAX = (1 << 64) - 1


def _require_u64(sequence: int) -> None:
    if not isinstance(sequence, int):
        raise TypeError('sequence must be int')
    if sequence < 0 or sequence > _U64_MAX:
        raise ValueError('sequence must fit unsigned 64-bit range')


def _require_hash(chain_hash: bytes) -> None:
    if not isinstance(chain_hash, bytes):
        raise TypeError('chain_hash must be bytes')
    if len(chain_hash) != M1_HASH_BYTES:
        raise ValueError(f'chain_hash must be exactly {M1_HASH_BYTES} bytes')


def payload_hash(payload: bytes) -> bytes:
    """Return SHA-256(payload) as the only payload-derived M1 material."""
    if not isinstance(payload, bytes):
        raise TypeError('payload must be bytes')
    return hashlib.sha256(payload).digest()


def next_chain_hash(previous_chain_hash: bytes, payload: bytes) -> bytes:
    """Compute SHA256(previous_chain_hash || SHA256(payload))."""
    _require_hash(previous_chain_hash)
    return hashlib.sha256(previous_chain_hash + payload_hash(payload)).digest()


def encode_entry(sequence: int, chain_hash: bytes) -> bytes:
    """Encode one canonical fixed-width M1 entry."""
    _require_u64(sequence)
    _require_hash(chain_hash)
    entry = sequence.to_bytes(M1_SEQUENCE_BYTES, 'little') + chain_hash
    if len(entry) != M1_ENTRY_BYTES:
        raise AssertionError('internal M1 entry width violation')
    return entry


def decode_entry(entry: bytes) -> Tuple[int, bytes]:
    """Decode one canonical fixed-width M1 entry."""
    if not isinstance(entry, bytes):
        raise TypeError('entry must be bytes')
    if len(entry) != M1_ENTRY_BYTES:
        raise ValueError(f'entry must be exactly {M1_ENTRY_BYTES} bytes')
    sequence = int.from_bytes(entry[:M1_SEQUENCE_BYTES], 'little')
    chain_hash = entry[M1_SEQUENCE_BYTES:]
    _require_hash(chain_hash)
    return sequence, chain_hash


def slot_offset(sequence: int, slot_capacity: int) -> int:
    """Return the aligned byte offset for a logical M1 record slot."""
    _require_u64(sequence)
    if not isinstance(slot_capacity, int):
        raise TypeError('slot_capacity must be int')
    if slot_capacity <= 0:
        raise ValueError('slot_capacity must be positive')
    return M1_ENTRY_BYTES * (sequence % slot_capacity)
