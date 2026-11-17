"""Optional, non-authoritative verifier transition analytics for CoreMatrix.

Observation never participates in gate decisions. State is process-local and
contains only 3-symbol transition counts, not payload or verifier history.
Disabled unless AEGIS_TRANSITION_OBSERVER=1 is explicitly set.
"""
from transition_info import TransitionStats, entropy_rate_q16, adjacent_mi_q16


class TransitionObserver:
    SCHEMA = "AEGIS_VERIFIER_TRANSITIONS_V14_1"
    ENCODING = "missing=0,first-byte-zero=1,first-byte-nonzero=2"

    def __init__(self):
        self._stats = TransitionStats.from_iterable((), 3)

    @staticmethod
    def symbol(verifier_result: bytes) -> int:
        if type(verifier_result) is not bytes:
            raise TypeError("VERIFIER_RESULT_NOT_BYTES")
        if not verifier_result:
            return 0
        return 2 if verifier_result[0] else 1

    def observe_verifier(self, verifier_result: bytes) -> None:
        token = self.symbol(verifier_result)
        # Atomic replace of a valid immutable summary. A failure leaves
        # the previous statistical state unmodified.
        updated = self._stats.concat(TransitionStats.from_iterable((token,), 3))
        self._stats = updated

    def snapshot(self) -> dict:
        s = self._stats
        return {
            "schema": self.SCHEMA,
            "status": "PROCESS_LOCAL_NONFORENSIC",
            "encoding": self.ENCODING,
            "sample_count": s.length,
            "transition_count": max(0, s.length - 1),
            "entropy_rate_q16": entropy_rate_q16(s),
            "adjacent_mi_q16": adjacent_mi_q16(s),
        }
