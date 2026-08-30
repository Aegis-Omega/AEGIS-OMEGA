"""Compatibility facade for the resident runtime with epistemic-actuation fields.

The implementation remains byte-identical in ``resident_runtime_impl``.  This
facade extends only the analysis packet contract first; runtime information-gain
binding is added in a separately falsified TDD step.  This keeps the refactor
reversible and prevents an unrelated rewrite of the large resident runtime.
"""
from __future__ import annotations

from dataclasses import dataclass

from harness.sdk import resident_runtime_impl as _impl
from harness.sdk.resident_runtime_impl import *  # noqa: F401,F403


@dataclass(frozen=True)
class AnalysisPacketV1(_impl.AnalysisPacketV1):
    """Resident analysis packet with explicit sensing/evidence bindings.

    Zero/None defaults mean that no action-conditioned information-gain receipt
    has yet been established.  A VERIFIED knowledge decision must not be
    interpreted as information gain merely because these fields exist.
    """

    observation_transform_root: str = _impl.ZERO_HASH
    observation_receipt_root: str = _impl.ZERO_HASH
    observed_information_gain_bps: int | None = None


# Methods defined in the implementation module resolve this global at call
# time.  Rebinding it makes packet construction use the extended contract while
# preserving every other resident-runtime implementation byte-for-byte.
_impl.AnalysisPacketV1 = AnalysisPacketV1
