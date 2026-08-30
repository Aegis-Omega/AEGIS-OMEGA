"""
SOVEREIGN OMEGA — Gate: Mutation Authority
EPISTEMIC TIER: T0 (constitutional — frozen after creation)

Controls whether proposed mutations are approved or rejected at the Python layer.
Acts as the Layer B counterpart to the TypeScript Bernstein confidence gate
(sovereign-omega-v2/src/gate/hoeffding.ts).

Role: mutation authority — every Python-layer state mutation must be approved
      by this gate before execution. Bridge.py receives /gate_signal from
      TypeScript and calls gate.record_signal(); core_matrix.py checks
      gate.is_approved() before committing any M2/M3 write.

Decision model: sliding window of the last WINDOW_SIZE gate signals from
TypeScript. Acceptance rate = (accepted signals / window size). When rate
>= MIN_ACCEPTANCE_RATE, the mutation is APPROVED. This mirrors the Bernstein
LCB > 0 criterion in TypeScript: both require statistical evidence of benefit.

Invariants enforced here:
  - Gate signals must be strictly monotonically increasing in sequence.
  - Out-of-order or duplicate signals are silently discarded (idempotent).
  - After seal(), no new signal processing is allowed (system is shutting down).
  - Verdict for unknown proposal_id is always PENDING (never assumed approved).
"""

import threading
from collections import deque
from typing import Dict, Optional

from dna import GateSignal, MutationVerdict


WINDOW_SIZE: int = 32          # rolling window of recent gate signals
MIN_ACCEPTANCE_RATE: float = 0.5  # majority-rule: >50% accepted → APPROVED


class MutationGate:
    """
    Tracks gate signals from the TypeScript Bernstein gate and issues
    mutation verdicts for the Python core matrix layer.

    Thread-safe. All methods may be called from any thread.
    """

    def __init__(
        self,
        window_size: int = WINDOW_SIZE,
        min_rate: float = MIN_ACCEPTANCE_RATE,
    ) -> None:
        self._lock = threading.Lock()
        self._window: deque = deque(maxlen=window_size)
        self._min_rate = min_rate
        self._proposals: Dict[str, MutationVerdict] = {}
        self._last_sequence: int = -1
        self._sealed: bool = False
        self._total_signals: int = 0

    def record_signal(self, signal: GateSignal) -> None:
        """
        Record a gate signal from the TypeScript layer.
        Sequence must be strictly monotonically increasing.
        Out-of-order or duplicate signals are discarded silently.
        """
        with self._lock:
            if self._sealed:
                return
            self._total_signals += 1  # count all received, including discarded
            if signal.sequence <= self._last_sequence:
                return  # out-of-order or duplicate — discard (idempotent)
            self._last_sequence = signal.sequence
            self._window.append(signal.accepted)

            if signal.proposal_id:
                rate = self._acceptance_rate()
                self._proposals[signal.proposal_id] = (
                    MutationVerdict.APPROVED
                    if rate >= self._min_rate
                    else MutationVerdict.REJECTED
                )

    def verdict(self, proposal_id: str) -> MutationVerdict:
        """Return the current verdict for a proposal. PENDING if unknown."""
        with self._lock:
            return self._proposals.get(proposal_id, MutationVerdict.PENDING)

    def is_approved(self, proposal_id: str) -> bool:
        """True only when proposal has APPROVED verdict."""
        return self.verdict(proposal_id) == MutationVerdict.APPROVED

    def acceptance_rate(self) -> float:
        """Current acceptance rate across the rolling window (0.0–1.0)."""
        with self._lock:
            return self._acceptance_rate()

    def last_sequence(self) -> int:
        """Sequence number of the most recent recorded signal."""
        with self._lock:
            return self._last_sequence

    def total_signals(self) -> int:
        """Total number of gate signals received (including discarded)."""
        with self._lock:
            return self._total_signals

    def seal(self) -> None:
        """
        Seal the gate. No further signals processed after this point.
        Called by bridge.py during graceful shutdown.
        """
        with self._lock:
            self._sealed = True

    @property
    def is_sealed(self) -> bool:
        with self._lock:
            return self._sealed

    def telemetry(self) -> dict:
        """Emit gate telemetry for inclusion in VCG telemetry payload."""
        with self._lock:
            return {
                'gate_acceptance_rate': self._acceptance_rate(),
                'gate_window_size': len(self._window),
                'gate_last_sequence': self._last_sequence,
                'gate_total_signals': self._total_signals,
                'gate_sealed': self._sealed,
            }

    # ── Private ──────────────────────────────────────────────────────────────

    def _acceptance_rate(self) -> float:
        if not self._window:
            return 0.0
        return sum(self._window) / len(self._window)


# Module-level singleton — imported by bridge.py and core_matrix.py
gate = MutationGate()
