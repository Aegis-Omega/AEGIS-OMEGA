"""Canonical lossless 64-bit integer wire transport for AEGIS contracts."""
import re

U64_MAX = (1 << 64) - 1
CANONICAL = re.compile(r"(?:0|[1-9][0-9]*)\Z", re.ASCII)


def decode_u64(wire: str) -> int:
    if not isinstance(wire, str) or len(wire) > 20 or CANONICAL.fullmatch(wire) is None:
        raise ValueError("U64_WIRE_FORMAT")
    value = int(wire)
    if value > U64_MAX:
        raise ValueError("U64_OUT_OF_RANGE")
    return value


def encode_u64(value: int) -> str:
    if type(value) is not int:
        raise TypeError("U64_NATIVE_TYPE")
    if value < 0 or value > U64_MAX:
        raise ValueError("U64_OUT_OF_RANGE")
    return str(value)


S64_MIN = -(1 << 63)
S64_MAX = (1 << 63) - 1
SIGNED_CANONICAL = re.compile(r"(?:0|-?[1-9][0-9]*)\Z", re.ASCII)


def decode_s64(wire: str) -> int:
    if not isinstance(wire, str) or len(wire) > 20 or SIGNED_CANONICAL.fullmatch(wire) is None:
        raise ValueError("S64_WIRE_FORMAT")
    value = int(wire)
    if not S64_MIN <= value <= S64_MAX:
        raise ValueError("S64_OUT_OF_RANGE")
    return value


def encode_s64(value: int) -> str:
    if type(value) is not int:
        raise TypeError("S64_NATIVE_TYPE")
    if not S64_MIN <= value <= S64_MAX:
        raise ValueError("S64_OUT_OF_RANGE")
    return str(value)
