"""Automaton-2 adversarial EventEnvelope verifier.

EPISTEMIC TIER: T1

This module is intentionally sequence-clocked. Sovereign Omega's Python
invariants prohibit ``time.time()`` in determinism-critical paths, so pacing is
verified against envelope sequence continuity rather than wall-clock delay.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

PHI = 1.618033988749895
PHASE_SHIFT_DEGREES = 108.0
PHASE_SHIFT_RAD = (PHASE_SHIFT_DEGREES * 3.141592653589793) / 180.0
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True)
class VerificationFailure:
    """Structured verifier failure payload for callers that need details."""

    code: str
    message: str

    def format(self) -> str:
        return f"{self.code}: {self.message}"


class AutomatonTwoVerifier:
    """Parallel verifier for hash-chained EventEnvelope mutations.

    The verifier enforces four consume-side checks before advancing its local
    observer chain:
    1. parent hash continuity,
    2. HMAC-SHA256 signature match,
    3. deterministic sequence pacing,
    4. adversarial mutation filter rejection.
    """

    def __init__(self, signing_secret: bytes, genesis_hash: str, initial_sequence: int = 0):
        if not signing_secret:
            raise ValueError("signing_secret must not be empty")
        if not _is_sha256_hex(genesis_hash):
            raise ValueError("genesis_hash must be a 64-character SHA-256 hex string")
        if initial_sequence < 0:
            raise ValueError("initial_sequence must be non-negative")

        self.signing_secret = signing_secret
        self.last_verified_hash = genesis_hash
        self.sequence_cursor = initial_sequence

    def calculate_envelope_hash(self, envelope: Mapping[str, Any]) -> str:
        """Return the deterministic SHA-256 hash of an EventEnvelope.

        RFC-8785-compatible JSON constraints are approximated here with sorted
        keys and compact separators because the payload contract is plain JSON.
        Non-JSON values are rejected instead of coerced.
        """

        canonical = _canonical_envelope_bytes(envelope)
        return hashlib.sha256(canonical).hexdigest()

    def sign_envelope(self, envelope: Mapping[str, Any]) -> str:
        """Create the HMAC-SHA256 signature expected by verify_signature."""

        envelope_hash = self.calculate_envelope_hash(envelope)
        mac = hmac.new(
            self.signing_secret,
            msg=envelope_hash.encode("utf-8"),
            digestmod=hashlib.sha256,
        )
        return mac.hexdigest()

    def verify_signature(self, envelope: Mapping[str, Any], signature: str) -> bool:
        """Verify non-repudiation of the envelope hash via HMAC-SHA256."""

        if not isinstance(signature, str) or len(signature) != SHA256_HEX_LENGTH:
            return False
        expected_sig = self.sign_envelope(envelope)
        return hmac.compare_digest(expected_sig, signature.lower())

    def verify_phi_pacing(self, sequence: int) -> bool:
        """Verify deterministic φ pacing through monotonic sequence movement.

        Wall-clock pacing is deliberately not used: temporal semantics in this
        repository are event-sequence derived. The φ constant remains metadata
        for the adversarial boundary; the enforceable rule is exactly one next
        sequence per accepted mutation.
        """

        return sequence == self.sequence_cursor + 1

    def validate_mutation_rules(self, payload: Mapping[str, Any]) -> bool:
        """Reject obvious adversarial command-injection mutation vectors."""

        prohibited_commands = ("DROP", "DELETE", "FORCE_COMMIT", "BYPASS_CONSENSUS")
        for key, value in _walk_payload(payload):
            key_text = str(key).upper()
            value_text = str(value).upper()
            if any(command in key_text or command in value_text for command in prohibited_commands):
                return False
        return True

    def process_and_chain(self, envelope: Mapping[str, Any], signature: str) -> Tuple[bool, str]:
        """Validate an EventEnvelope and advance the observer hash chain."""

        validation_failure = self._validate_envelope_shape(envelope)
        if validation_failure is not None:
            return False, validation_failure.format()

        parent_hash = envelope["parent_hash"]
        sequence = envelope["sequence"]
        payload = envelope["payload"]

        if parent_hash != self.last_verified_hash:
            return False, "STATE_CORRUPT: Parent hash mismatch on active ledger."

        if not self.verify_signature(envelope, signature):
            return False, "SIGNATURE_INVALID: EventEnvelope failed signature verification."

        if not self.verify_phi_pacing(sequence):
            return False, "PACING_VIOLATION: Mutation sequence exceeds deterministic phi pacing limits."

        if not self.validate_mutation_rules(payload):
            return False, "CONSTITUTIONAL_VIOLATION: Gaslit vector detected. State rollback triggered."

        self.last_verified_hash = self.calculate_envelope_hash(envelope)
        self.sequence_cursor = sequence
        return True, self.last_verified_hash

    def _validate_envelope_shape(self, envelope: Mapping[str, Any]) -> VerificationFailure | None:
        if not isinstance(envelope, Mapping):
            return VerificationFailure("ENVELOPE_INVALID", "EventEnvelope must be a mapping.")
        if not isinstance(envelope.get("execution_id"), str) or not envelope.get("execution_id"):
            return VerificationFailure("ENVELOPE_INVALID", "execution_id must be a non-empty string.")
        if not isinstance(envelope.get("parent_hash"), str) or not _is_sha256_hex(envelope["parent_hash"]):
            return VerificationFailure("ENVELOPE_INVALID", "parent_hash must be SHA-256 hex.")
        if not isinstance(envelope.get("sequence"), int) or envelope["sequence"] < 0:
            return VerificationFailure("ENVELOPE_INVALID", "sequence must be a non-negative integer.")
        if not isinstance(envelope.get("timestamp"), str) or not envelope.get("timestamp"):
            return VerificationFailure("ENVELOPE_INVALID", "timestamp must be a non-empty string.")
        if not isinstance(envelope.get("payload"), Mapping):
            return VerificationFailure("ENVELOPE_INVALID", "payload must be a mapping.")
        return None


def _canonical_envelope_bytes(envelope: Mapping[str, Any]) -> bytes:
    canonical_envelope = {
        "execution_id": envelope.get("execution_id"),
        "parent_hash": envelope.get("parent_hash"),
        "payload": envelope.get("payload", {}),
        "sequence": envelope.get("sequence"),
        "timestamp": envelope.get("timestamp"),
    }
    return json.dumps(
        canonical_envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _is_sha256_hex(value: str) -> bool:
    if len(value) != SHA256_HEX_LENGTH:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _walk_payload(payload: Mapping[str, Any]):
    for key, value in payload.items():
        if isinstance(value, Mapping):
            yield key, ""
            yield from _walk_payload(value)
        elif isinstance(value, (list, tuple)):
            yield key, ""
            for index, item in enumerate(value):
                if isinstance(item, Mapping):
                    yield from _walk_payload(item)
                else:
                    yield f"{key}[{index}]", item
        else:
            yield key, value
