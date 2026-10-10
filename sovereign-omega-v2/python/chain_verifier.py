"""Bounded integrity check for the *process-local* AEGIS metacognitive chain.

This checks SHA-256 preimages, genesis linkage and sequence continuity. It is
NOT a durable ledger, signed attestation, constitutional admission, or an
independent external witness; a process that rewrites all entries can recompute
its hashes. Consumers must preserve this limited scope.
"""
from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence

GENESIS_HASH = "0" * 64
MAX_VERIFY_ENTRIES = 10_000


def verify_metacognitive_chain(entries: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return tri-state validity and a recomputed terminal hash; never default PASS."""
    count = len(entries)
    def result(valid: bool | None, reason: str, terminal: str | None = None) -> dict[str, object]:
        return {"valid": valid, "reason": reason, "terminal_hash": terminal, "entry_count": count,
                "scope": "in_process_sha256_linkage_only"}

    if not count:
        return result(None, "NO_CHAIN_ENTRIES")
    if count > MAX_VERIFY_ENTRIES:
        return result(None, "CHAIN_EXCEEDS_VERIFICATION_BUDGET")

    previous = GENESIS_HASH
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, Mapping):
            return result(False, f"ENTRY_SHAPE_INVALID:{index}")
        if type(entry.get("sequence")) is not int or entry["sequence"] != index:
            return result(False, f"SEQUENCE_INVALID:{index}")
        layer, signal, tier = (entry.get(k) for k in ("layer", "signal", "tier"))
        if not all(isinstance(v, str) and v for v in (layer, signal, tier)):
            return result(False, f"ENTRY_FIELDS_INVALID:{index}")
        if entry.get("prev_hash") != previous:
            return result(False, f"PREVIOUS_HASH_MISMATCH:{index}")
        received = entry.get("entry_hash")
        if not isinstance(received, str) or len(received) != 64 or any(c not in "0123456789abcdef" for c in received):
            return result(False, f"HASH_FORMAT_INVALID:{index}")
        preimage = f"{previous}|{layer}|{signal}|{tier}".encode("utf-8")
        expected = hashlib.sha256(preimage).hexdigest()
        if not hmac.compare_digest(received, expected):
            return result(False, f"ENTRY_HASH_MISMATCH:{index}")
        previous = expected
    return result(True, "CHAIN_RECOMPUTED_IN_PROCESS", previous)
