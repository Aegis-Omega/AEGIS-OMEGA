"""Fail-closed, proposal-bound mutation admission for the Python HTTP bridge.

This module does not replace the frozen constitutional gate.py.  It adds a
server-to-server authentication boundary and a single-use grant bound to
the exact event bytes.  The TypeScript E4 source of `lcb` is separately
trusted; statistical correctness is not established by this module.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import re
import threading

_EVENT_DOMAIN = b"AEGIS_MUTATION_EVENT_V1\x00"
_PROPOSAL_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def control_authenticated(provided: str | None, configured: str | None) -> bool:
    """Require a configured server-only secret; no development bypass."""
    if not isinstance(provided, str) or not isinstance(configured, str):
        return False
    actual = configured.encode("utf-8")
    candidate = provided.encode("utf-8")
    if len(actual) < 32 or not candidate:
        return False
    return hmac.compare_digest(candidate, actual)


def control_secrets_distinct(gate_secret: str | None, event_secret: str | None) -> bool:
    """Prevent a single caller credential from both issuing and using grants."""
    if not isinstance(gate_secret, str) or not isinstance(event_secret, str):
        return False
    gate = gate_secret.encode("utf-8")
    event = event_secret.encode("utf-8")
    if len(gate) < 32 or len(event) < 32:
        return False
    return not hmac.compare_digest(gate, event)


def event_digest(payload: bytes, verifier: bytes, context: bytes) -> str:
    """Versioned, length-framed SHA-256 binding to the exact routed event."""
    digest = hashlib.sha256(_EVENT_DOMAIN)
    for field in (payload, verifier, context):
        if not isinstance(field, bytes):
            raise TypeError("event fields must be bytes")
        digest.update(len(field).to_bytes(8, "big"))
        digest.update(field)
    return digest.hexdigest()


class MutationAdmissionLedger:
    """Bounded, thread-safe, single-use proposal grants.

    A signed server-side signal is necessary but not sufficient: the caller
    must also pass the separate constitutional gate verdict at consumption.
    The issuer may never promote a rejected or nonpositive-LCB signal by
    relying on a rolling global majority for unrelated proposals.
    """

    def __init__(self, max_pending: int = 4096) -> None:
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError("max_pending must be positive")
        self._pending: dict[str, str] = {}
        self._last_sequence = -1
        self._max_pending = max_pending
        self._lock = threading.Lock()

    def record(
        self,
        proposal_id: str,
        sequence: int,
        accepted: bool,
        lcb: float,
        expected_event_sha256: str,
        *,
        e_value: float,
        risk_spent: float,
        sample_size: int,
        e4_method: str,
    ) -> tuple[bool, str]:
        if not isinstance(proposal_id, str) or not _PROPOSAL_ID.fullmatch(proposal_id):
            return False, "INVALID_PROPOSAL"
        if type(sequence) is not int or not 0 <= sequence < 2**64:
            return False, "INVALID_SEQUENCE"
        if type(accepted) is not bool:
            return False, "INVALID_DECISION"
        if type(lcb) not in (float, int) or not math.isfinite(lcb):
            return False, "INVALID_LCB"
        # Enforce PR #817's E4 admission criterion at the Python boundary.
        # An issuer-authenticated positive LCB alone is NOT sequential evidence.
        # risk_spent is deltaAlpha for an accepted RiskBudgetManager decision.
        # These checks do not authenticate where the samples came from or prove
        # that an issuer maintains one global budget across restarts.
        if type(sample_size) is not int or sample_size < 0:
            return False, "INVALID_E4_SAMPLE_SIZE"
        if e4_method != "anytime_valid_bernstein":
            return False, "INVALID_E4_METHOD"
        if (type(e_value) not in (float, int)
                or not math.isfinite(e_value) or e_value < 0):
            return False, "INVALID_E_VALUE"
        if (type(risk_spent) not in (float, int)
                or not math.isfinite(risk_spent) or risk_spent < 0):
            return False, "INVALID_E4_ALPHA"
        if accepted:
            if lcb <= 0:
                return False, "DECISION_LCB_MISMATCH"
            if sample_size < 1:
                return False, "INVALID_E4_SAMPLE_SIZE"
            if not 0 < risk_spent < 1:
                return False, "INVALID_E4_ALPHA"
            # Reciprocal threshold mirrors RiskBudgetManager's one-round
            # e-process criterion; no bounded clipping of invalid evidence.
            if e_value < (1 / risk_spent):
                return False, "E_VALUE_FAIL"
        elif risk_spent != 0:
            return False, "REJECTED_WITH_RISK_SPEND"
        if (
            not isinstance(expected_event_sha256, str)
            or not _SHA256.fullmatch(expected_event_sha256)
        ):
            return False, "INVALID_EVENT_DIGEST"

        with self._lock:
            if sequence <= self._last_sequence:
                return False, "SEQUENCE_DESYNC"
            if accepted and proposal_id in self._pending:
                return False, "DUPLICATE_PENDING_PROPOSAL"
            if accepted and len(self._pending) >= self._max_pending:
                return False, "PENDING_CAPACITY"
            self._last_sequence = sequence
            if accepted:
                self._pending[proposal_id] = expected_event_sha256
            else:
                self._pending.pop(proposal_id, None)
            return True, "ACCEPTED"

    def revoke(self, proposal_id: str) -> None:
        with self._lock:
            self._pending.pop(proposal_id, None)

    def authorize_event(
        self,
        proposal_id: str,
        payload: bytes,
        verifier: bytes,
        context: bytes,
        constitutional_approved: bool,
    ) -> bool:
        if constitutional_approved is not True:
            return False
        if not isinstance(proposal_id, str) or not _PROPOSAL_ID.fullmatch(proposal_id):
            return False
        observed = event_digest(payload, verifier, context)
        with self._lock:
            if self._pending.get(proposal_id) != observed:
                return False
            self._pending.pop(proposal_id)
            return True

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)
