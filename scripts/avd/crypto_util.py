from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any


class CanonicalizationError(ValueError):
    pass


_MAX_SAFE_INTEGER = (1 << 53) - 1


def _utf16_sort_key(value: str) -> bytes:
    return value.encode("utf-16-be")


def _encode_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, int):
        if abs(value) > _MAX_SAFE_INTEGER:
            raise CanonicalizationError("INTEGER_OUTSIDE_IJSON_SAFE_RANGE")
        return str(value)
    if isinstance(value, float):
        raise CanonicalizationError("FLOAT_FORBIDDEN")
    if isinstance(value, str):
        if unicodedata.normalize("NFC", value) != value:
            raise CanonicalizationError("NON_NFC_STRING")
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    raise CanonicalizationError(f"UNSUPPORTED_CANONICAL_TYPE:{type(value).__name__}")


def _encode(value: Any) -> str:
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError("NON_STRING_OBJECT_KEY")
            if unicodedata.normalize("NFC", key) != key:
                raise CanonicalizationError("NON_NFC_OBJECT_KEY")
        parts = []
        for key in sorted(value.keys(), key=_utf16_sort_key):
            parts.append(f"{_encode_scalar(key)}:{_encode(value[key])}")
        return "{" + ",".join(parts) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode(item) for item in value) + "]"
    return _encode_scalar(value)


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON for the AVD receipt domain.

    AVD receipts intentionally forbid floating-point JSON values. For the
    remaining I-JSON-compatible types, this encoder follows RFC 8785 ordering
    and string emission rules relevant to the schema. It is deliberately a
    restricted JCS domain, not a general-purpose floating-point JCS library.
    """
    return _encode(obj).encode("utf-8")


def avd_digest(domain: str, payload: bytes) -> str:
    if not domain or not domain.isascii() or "\x00" in domain:
        raise ValueError("INVALID_DIGEST_DOMAIN")
    prefix = b"AEGIS-AVD-V1\x00" + domain.encode("ascii") + b"\x00"
    return hashlib.sha256(prefix + payload).hexdigest()


def compute_receipt_digest(receipt_without_digest: dict[str, Any]) -> str:
    if "receipt_digest" in receipt_without_digest:
        raise ValueError("RECEIPT_DIGEST_ALREADY_PRESENT")
    raw = canonical_json_bytes(receipt_without_digest)
    return hashlib.sha256(b"AEGIS-AVD-TRIAL-RECEIPT-V1\x00" + raw).hexdigest()
