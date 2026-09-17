"""
AEGIS M2 Slot Contract V1 — inert reference model.

AUTHORITY_EFFECT: NONE
PRODUCTION_WIRING: NONE

Defines the minimal fixed-width M2 storage contract implied by the current
8-byte record layout:

    entry_n  = vcg_error_fixed:u32le || gate_lcb_fixed:u32le
    capacity = floor(region_bytes / 8)
    offset_n = 8 * (sequence mod capacity)

Verifier bytes affect the values written, never the storage address. Tail bytes
that cannot hold a complete 8-byte entry are intentionally unused.
"""

from typing import Tuple

M2_FIELD_BYTES = 4
M2_ENTRY_BYTES = 8
_U32_MAX = (1 << 32) - 1
_U64_MAX = (1 << 64) - 1


def _require_u32(name: str, value: int) -> None:
    if not isinstance(value, int):
        raise TypeError(f'{name} must be int')
    if value < 0 or value > _U32_MAX:
        raise ValueError(f'{name} must fit unsigned 32-bit range')


def _require_sequence(sequence: int) -> None:
    if not isinstance(sequence, int):
        raise TypeError('sequence must be int')
    if sequence < 0 or sequence > _U64_MAX:
        raise ValueError('sequence must fit unsigned 64-bit range')


def slot_capacity(region_bytes: int) -> int:
    """Return the number of complete 8-byte M2 records in a region."""
    if not isinstance(region_bytes, int):
        raise TypeError('region_bytes must be int')
    if region_bytes < 0:
        raise ValueError('region_bytes must be non-negative')
    return region_bytes // M2_ENTRY_BYTES


def slot_offset(sequence: int, capacity: int) -> int:
    """Map one logical sequence to one aligned M2 record slot."""
    _require_sequence(sequence)
    if not isinstance(capacity, int):
        raise TypeError('capacity must be int')
    if capacity <= 0:
        raise ValueError('capacity must be positive')
    return M2_ENTRY_BYTES * (sequence % capacity)


def encode_entry(vcg_error_fixed: int, gate_lcb_fixed: int) -> bytes:
    """Encode one canonical M2 record."""
    _require_u32('vcg_error_fixed', vcg_error_fixed)
    _require_u32('gate_lcb_fixed', gate_lcb_fixed)
    entry = (
        vcg_error_fixed.to_bytes(M2_FIELD_BYTES, 'little', signed=False)
        + gate_lcb_fixed.to_bytes(M2_FIELD_BYTES, 'little', signed=False)
    )
    if len(entry) != M2_ENTRY_BYTES:
        raise AssertionError('internal M2 entry width violation')
    return entry


def decode_entry(entry: bytes) -> Tuple[int, int]:
    """Decode one canonical M2 record."""
    if not isinstance(entry, bytes):
        raise TypeError('entry must be bytes')
    if len(entry) != M2_ENTRY_BYTES:
        raise ValueError(f'entry must be exactly {M2_ENTRY_BYTES} bytes')
    return (
        int.from_bytes(entry[:M2_FIELD_BYTES], 'little', signed=False),
        int.from_bytes(entry[M2_FIELD_BYTES:], 'little', signed=False),
    )
