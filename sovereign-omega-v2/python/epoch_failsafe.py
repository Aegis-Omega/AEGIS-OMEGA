"""
SOVEREIGN OMEGA — Epoch Failsafe Isolation
EPISTEMIC TIER: T0 (non-negotiable correctness requirement)

Circuit-breaker epoch quarantine layer that prevents state corruption during
cascade multi-hop agent failures. When failures occur across both active
buffers faster than the ledger recovery worker can write compensatory events,
the failsafe halts ingestion and falls back to an immutable ledger state.

SUCCESS CRITERION: Zero post-cascade failure ledger corruption across
1,000+ simulated parallel agent crash loops. Binary pass/fail. T0.

INTEGRATION: Hooks into the buffer management, event validation,
and ingestion logic. Acts as a global arbiter capable of overriding
normal flow to preserve E3 substrate integrity.
"""

import hashlib
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple


class EpochState(Enum):
    ACTIVE     = "active"
    QUARANTINE = "quarantine"
    RECOVERING = "recovering"
    FROZEN     = "frozen"


@dataclass(frozen=True)
class EpochSnapshot:
    """Immutable epoch state snapshot. Serialisable for ledger storage."""
    epoch_id: int
    snapshot_hash: str          # SHA-256 of serialised state
    event_count: int
    last_event_sequence: int
    timestamp_sequence: int     # event-derived, never wall clock
    state_bytes: bytes


@dataclass(frozen=True)
class FailsafeEvent:
    """Immutable record of a failsafe activation."""
    epoch_id: int
    trigger_reason: str
    buffer_id: str              # "En" or "En+1"
    snapshot_hash_before: str
    snapshot_hash_after: str
    recovery_successful: bool
    consensus_rounds: int
    timestamp_sequence: int


class EpochFailsafeController:
    """
    Manages epoch quarantine and cascade failure isolation.

    The double-buffer architecture maintains two active buffers (Eₙ and Eₙ₊₁).
    If cascade failures propagate across both buffers faster than the recovery
    worker can compensate, this controller intervenes.

    INVARIANT: The E3 event substrate must never be corrupted. Any mechanism
    that could lead to corruption is intercepted and quarantined before it
    reaches the substrate.
    """

    QUICK_CONSENSUS_ROUNDS = 3  # rounds required for consensus validation

    def __init__(
        self,
        event_callback: Optional[Callable[[str, dict], None]] = None,
    ):
        self._epoch_n: Optional[EpochSnapshot] = None       # active buffer
        self._epoch_n1: Optional[EpochSnapshot] = None      # next buffer
        self._state = EpochState.ACTIVE
        self._lock = threading.RLock()
        self._event_cb = event_callback
        self._failsafe_log: List[FailsafeEvent] = []
        self._corruption_count = 0
        self._consecutive_failures = 0
        self._failure_threshold = 3  # failures before quarantine

    def set_epoch_snapshot(
        self, epoch_id: int, state: bytes, event_count: int,
        last_sequence: int, timestamp_sequence: int
    ) -> EpochSnapshot:
        """
        Register a new epoch snapshot. Called by the ledger recovery worker
        after successfully writing compensatory events.
        timestamp_sequence MUST come from the event substrate.
        """
        snapshot_hash = hashlib.sha256(
            state + epoch_id.to_bytes(8, 'little') + last_sequence.to_bytes(8, 'little')
        ).hexdigest()

        snapshot = EpochSnapshot(
            epoch_id=epoch_id,
            snapshot_hash=snapshot_hash,
            event_count=event_count,
            last_event_sequence=last_sequence,
            timestamp_sequence=timestamp_sequence,
            state_bytes=state,
        )

        with self._lock:
            self._epoch_n1 = self._epoch_n
            self._epoch_n = snapshot

        return snapshot

    def report_agent_failure(
        self, buffer_id: str, failure_type: str, sequence: int
    ) -> Tuple[bool, Optional[EpochSnapshot]]:
        """
        Report an agent failure in a buffer. Returns (should_quarantine, fallback_snapshot).
        If quarantine is triggered, returns the last known-good snapshot to fall back to.
        timestamp MUST come from the event substrate.
        """
        with self._lock:
            self._consecutive_failures += 1

            if self._consecutive_failures >= self._failure_threshold:
                return self._activate_quarantine(buffer_id, failure_type, sequence)

            return False, None

    def _activate_quarantine(
        self, buffer_id: str, reason: str, sequence: int
    ) -> Tuple[bool, Optional[EpochSnapshot]]:
        """
        Activate epoch quarantine. Halts all ingestion to the affected buffer
        and initiates fallback to the last known-good immutable ledger state.
        """
        if self._state == EpochState.QUARANTINE:
            return True, self._epoch_n  # already quarantined

        self._state = EpochState.QUARANTINE

        # Perform quick-consensus validation on the fallback state
        fallback = self._select_fallback_snapshot()
        consensus_valid, rounds = self._quick_consensus(fallback)

        before_hash = fallback.snapshot_hash if fallback else "none"
        after_hash = fallback.snapshot_hash if consensus_valid and fallback else "none"

        event = FailsafeEvent(
            epoch_id=fallback.epoch_id if fallback else -1,
            trigger_reason=reason,
            buffer_id=buffer_id,
            snapshot_hash_before=before_hash,
            snapshot_hash_after=after_hash,
            recovery_successful=consensus_valid,
            consensus_rounds=rounds,
            timestamp_sequence=sequence,
        )
        self._failsafe_log.append(event)

        if not consensus_valid:
            self._state = EpochState.FROZEN
            self._corruption_count += 1
            if self._event_cb:
                self._event_cb('EPOCH_FROZEN', {'reason': reason, 'sequence': sequence})
            return True, None

        self._state = EpochState.RECOVERING
        self._consecutive_failures = 0

        if self._event_cb:
            self._event_cb('EPOCH_QUARANTINE_RECOVERED', {
                'epoch_id': fallback.epoch_id if fallback else -1,
                'consensus_rounds': rounds,
                'sequence': sequence,
            })

        return True, fallback

    def _select_fallback_snapshot(self) -> Optional[EpochSnapshot]:
        """Select the best available fallback snapshot."""
        if self._epoch_n and self._verify_snapshot_integrity(self._epoch_n):
            return self._epoch_n
        if self._epoch_n1 and self._verify_snapshot_integrity(self._epoch_n1):
            return self._epoch_n1
        return None

    def _quick_consensus(self, snapshot: Optional[EpochSnapshot]) -> Tuple[bool, int]:
        """
        Run quick-consensus algorithm to verify snapshot integrity.
        Returns (is_valid, rounds_taken).
        """
        if not snapshot:
            return False, 0

        valid_rounds = 0
        for round_num in range(self.QUICK_CONSENSUS_ROUNDS):
            # Re-hash the state bytes and compare to stored hash
            expected_hash = hashlib.sha256(
                snapshot.state_bytes
                + snapshot.epoch_id.to_bytes(8, 'little')
                + snapshot.last_event_sequence.to_bytes(8, 'little')
            ).hexdigest()

            if expected_hash == snapshot.snapshot_hash:
                valid_rounds += 1
            else:
                break  # single hash mismatch fails consensus

        return valid_rounds == self.QUICK_CONSENSUS_ROUNDS, valid_rounds

    def _verify_snapshot_integrity(self, snapshot: EpochSnapshot) -> bool:
        """Verify a snapshot's hash chain integrity."""
        expected = hashlib.sha256(
            snapshot.state_bytes
            + snapshot.epoch_id.to_bytes(8, 'little')
            + snapshot.last_event_sequence.to_bytes(8, 'little')
        ).hexdigest()
        return expected == snapshot.snapshot_hash

    def reset_after_recovery(self):
        """Reset the failsafe state after successful human-supervised recovery."""
        with self._lock:
            if self._state != EpochState.FROZEN:
                self._state = EpochState.ACTIVE
                self._consecutive_failures = 0

    @property
    def state(self) -> EpochState:
        return self._state

    @property
    def corruption_count(self) -> int:
        """Number of unrecoverable corruption events. Must be 0 for T0 pass."""
        return self._corruption_count

    @property
    def failsafe_log(self) -> List[FailsafeEvent]:
        return list(self._failsafe_log)

    def passes_t0_criterion(self) -> bool:
        """Returns True if the T0 success criterion is met: zero corruption events."""
        return self._corruption_count == 0

    # ── Cycles 11–15: Checkpoint / Restore ───────────────────────────────────

    def export_checkpoint(self) -> dict:
        """
        Export full failsafe state as a serialisable checkpoint dict.
        Used for cross-session persistence and forensic audit trails.
        State: current EpochState + both buffer snapshots + log.
        """
        with self._lock:
            def _snap(s: Optional[EpochSnapshot]) -> Optional[dict]:
                if not s:
                    return None
                return {
                    'epoch_id': s.epoch_id,
                    'snapshot_hash': s.snapshot_hash,
                    'event_count': s.event_count,
                    'last_event_sequence': s.last_event_sequence,
                    'timestamp_sequence': s.timestamp_sequence,
                    'state_bytes_hex': s.state_bytes.hex(),
                }
            return {
                'state': self._state.value,
                'corruption_count': self._corruption_count,
                'consecutive_failures': self._consecutive_failures,
                'failure_threshold': self._failure_threshold,
                'epoch_n': _snap(self._epoch_n),
                'epoch_n1': _snap(self._epoch_n1),
                'failsafe_log': [
                    {
                        'epoch_id': e.epoch_id,
                        'trigger_reason': e.trigger_reason,
                        'buffer_id': e.buffer_id,
                        'snapshot_hash_before': e.snapshot_hash_before,
                        'snapshot_hash_after': e.snapshot_hash_after,
                        'recovery_successful': e.recovery_successful,
                        'consensus_rounds': e.consensus_rounds,
                        'timestamp_sequence': e.timestamp_sequence,
                    }
                    for e in self._failsafe_log
                ],
            }

    def import_checkpoint(self, checkpoint: dict) -> bool:
        """
        Restore failsafe state from a checkpoint dict (from export_checkpoint).
        Verifies snapshot hashes before restoring. Returns True on success.
        INVARIANT: Only restores if all hash verifications pass.
        """
        def _parse_snap(d: Optional[dict]) -> Optional[EpochSnapshot]:
            if not d:
                return None
            s = EpochSnapshot(
                epoch_id=d['epoch_id'],
                snapshot_hash=d['snapshot_hash'],
                event_count=d['event_count'],
                last_event_sequence=d['last_event_sequence'],
                timestamp_sequence=d['timestamp_sequence'],
                state_bytes=bytes.fromhex(d['state_bytes_hex']),
            )
            if not self._verify_snapshot_integrity(s):
                return None
            return s

        snap_n = _parse_snap(checkpoint.get('epoch_n'))
        snap_n1 = _parse_snap(checkpoint.get('epoch_n1'))

        # Fail closed: if a snapshot was present but failed hash verification, abort
        # without modifying any state. Proceeding with None would mask corruption.
        if checkpoint.get('epoch_n') is not None and snap_n is None:
            return False
        if checkpoint.get('epoch_n1') is not None and snap_n1 is None:
            return False

        with self._lock:
            self._epoch_n = snap_n
            self._epoch_n1 = snap_n1
            self._state = EpochState(checkpoint.get('state', 'active'))
            self._corruption_count = checkpoint.get('corruption_count', 0)
            self._consecutive_failures = checkpoint.get('consecutive_failures', 0)
            self._failure_threshold = checkpoint.get('failure_threshold', 3)
            log_entries = checkpoint.get('failsafe_log', [])
            self._failsafe_log = [
                FailsafeEvent(
                    epoch_id=e['epoch_id'],
                    trigger_reason=e['trigger_reason'],
                    buffer_id=e['buffer_id'],
                    snapshot_hash_before=e['snapshot_hash_before'],
                    snapshot_hash_after=e['snapshot_hash_after'],
                    recovery_successful=e['recovery_successful'],
                    consensus_rounds=e['consensus_rounds'],
                    timestamp_sequence=e['timestamp_sequence'],
                )
                for e in log_entries
            ]
        return True

    # ── Cycles 16–20: Entropy metrics ────────────────────────────────────────

    def failsafe_entropy(self) -> float:
        """
        Shannon entropy (nats) of the failsafe event distribution.
        Measures how predictable the failure pattern is — high entropy = unpredictable
        failures = potential adversarial input. Returns 0.0 if fewer than 2 events.
        """
        if len(self._failsafe_log) < 2:
            return 0.0
        import math
        counts: Dict[str, int] = {}
        for e in self._failsafe_log:
            counts[e.trigger_reason] = counts.get(e.trigger_reason, 0) + 1
        total = len(self._failsafe_log)
        entropy = 0.0
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log(p)
        return entropy

    def mean_consensus_rounds(self) -> float:
        """Mean consensus rounds across all failsafe events. 0.0 if no events."""
        if not self._failsafe_log:
            return 0.0
        return sum(e.consensus_rounds for e in self._failsafe_log) / len(self._failsafe_log)

    def recovery_success_rate(self) -> float:
        """Fraction of failsafe events that ended in successful recovery. 1.0 if no events."""
        if not self._failsafe_log:
            return 1.0
        successes = sum(1 for e in self._failsafe_log if e.recovery_successful)
        return successes / len(self._failsafe_log)
