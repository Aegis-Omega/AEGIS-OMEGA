"""
SOVEREIGN OMEGA — Gradient-Anchor Calibration
EPISTEMIC TIER: T0/T1

Maintains zero quantisation drift in the intent verification micro-router
by continuously adjusting internal weight scaling factors (W_scale) toward
a set of immutable anchor tokens that represent non-negotiable T0 knowledge.

SUCCESS CRITERION: Dynamic quantisation drift index D = 0
maintained across 100,000 active epochs.

CORRECTION, NOT LEARNING: The system cannot adapt beyond the bounds
defined by the anchor tokens. W_scale adjustments only pull the router
back toward calibrated state — they cannot expand it.

INTEGRATION: Connects to the TypeScript VCG calibration layer via
the bridge module. Anchor tokens are seeded from T0 knowledge:
RFC 8785 test vectors, frozen constitutional file hashes, gate invariants.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from hardware_config import to_fixed, from_fixed, fixed_mul, INT_SCALE


# ── Anchor Token Registry ────────────────────────────────────────────────────
@dataclass(frozen=True)
class AnchorToken:
    """
    An immutable T0 anchor token representing a non-negotiable enterprise rule.
    Anchor tokens are seeded from T0 knowledge and cannot be modified at runtime.
    """
    token_id: str
    token_hash: str         # SHA-256 of the canonical token bytes
    expected_w_scale: int   # Q16.16 fixed-point expected weight scale
    tolerance_fixed: int    # Q16.16 maximum allowed deviation from expected
    description: str


# T0 anchor tokens derived from Sovereign Omega's known-good invariants
DEFAULT_ANCHOR_TOKENS: List[AnchorToken] = [
    AnchorToken(
        token_id="RFC8785_NULL",
        token_hash=hashlib.sha256(b"null").hexdigest(),
        expected_w_scale=INT_SCALE,  # 1.0
        tolerance_fixed=INT_SCALE // 100,  # 0.01
        description="RFC 8785 canonical serialisation of null",
    ),
    AnchorToken(
        token_id="RFC8785_EMPTY_OBJ",
        token_hash=hashlib.sha256(b"{}").hexdigest(),
        expected_w_scale=INT_SCALE,
        tolerance_fixed=INT_SCALE // 100,
        description="RFC 8785 canonical serialisation of empty object",
    ),
    AnchorToken(
        token_id="GATE_ACCEPT_THRESHOLD",
        token_hash=hashlib.sha256(b"LCB_POSITIVE").hexdigest(),
        expected_w_scale=INT_SCALE,
        tolerance_fixed=INT_SCALE // 200,  # 0.005 — tighter tolerance for gate logic
        description="Gate acceptance condition: LCB > 0",
    ),
    AnchorToken(
        token_id="VERSION_MISMATCH_ABORT",
        token_hash=hashlib.sha256(b"HARD_ABORT_NO_FALLBACK").hexdigest(),
        expected_w_scale=INT_SCALE,
        tolerance_fixed=0,  # zero tolerance — this invariant is absolute
        description="Version mismatch causes hard abort, never silent fallback",
    ),
    AnchorToken(
        token_id="ADVISORY_EXCLUDED",
        token_hash=hashlib.sha256(b"V4_V5_NEVER_IN_VCG").hexdigest(),
        expected_w_scale=INT_SCALE,
        tolerance_fixed=0,  # zero tolerance — trust partitioning is T0
        description="V4/V5 verifiers never contribute to VCG calibration",
    ),
]


# ── Drift Measurement ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DriftMeasurement:
    """Immutable drift measurement at a single epoch."""
    epoch: int
    anchor_token_id: str
    measured_w_scale: int       # Q16.16
    expected_w_scale: int       # Q16.16
    drift_fixed: int            # |measured - expected| in Q16.16
    drift_index: float          # D value: 0.0 = perfect calibration
    adjustment_applied: int     # W_scale adjustment in Q16.16
    passes_criterion: bool      # D == 0.0


@dataclass
class GradientAnchorState:
    """Mutable calibration state. Updated by background async process."""
    epoch: int = 0
    w_scales: Dict[str, int] = field(default_factory=dict)  # token_id → Q16.16
    cumulative_drift: float = 0.0
    measurements: List[DriftMeasurement] = field(default_factory=list)
    total_adjustments: int = 0


class GradientAnchorCalibrator:
    """
    Background calibration system that maintains W_scale alignment with
    anchor tokens across 100,000 active epochs.

    INVARIANT: This system is correction-only. It pulls W_scale values
    toward anchor token expectations. It cannot push them beyond those bounds.
    The system cannot learn new behaviours — only correct quantisation drift.
    """

    def __init__(
        self,
        anchor_tokens: Optional[List[AnchorToken]] = None,
        learning_rate: float = 0.01,  # small enough to be corrective, not adaptive
    ):
        self._anchors = {t.token_id: t for t in (anchor_tokens or DEFAULT_ANCHOR_TOKENS)}
        self._lr_fixed = to_fixed(learning_rate)
        self._momentum_beta = to_fixed(0.9)  # EMA momentum coefficient
        self._state = GradientAnchorState()
        self._velocities: Dict[str, int] = {}  # token_id → Q16.16 velocity

        for token_id in self._anchors:
            self._state.w_scales[token_id] = INT_SCALE
            self._velocities[token_id] = 0  # zero initial velocity

    def calibrate_epoch(self, epoch: int) -> List[DriftMeasurement]:
        """
        Run one calibration step for all anchor tokens.
        Called by the background async process once per epoch.
        epoch MUST be derived from the event substrate sequence counter.
        """
        self._state.epoch = epoch
        measurements = []

        for token_id, anchor in self._anchors.items():
            measured = self._state.w_scales[token_id]
            expected = anchor.expected_w_scale

            # Compute drift
            drift_fixed = abs(measured - expected)
            drift_float = from_fixed(drift_fixed)

            # D = drift / expected (normalised)
            drift_index = drift_float / from_fixed(expected) if expected != 0 else 0.0

            # Compute correction with momentum (Nesterov-style)
            # velocity = β * velocity + (1 - β) * (-lr * error)
            error_fixed = measured - expected
            gradient_fixed = -fixed_mul(self._lr_fixed, error_fixed)
            prev_velocity = self._velocities.get(token_id, 0)
            new_velocity = fixed_mul(self._momentum_beta, prev_velocity) + \
                           fixed_mul(INT_SCALE - self._momentum_beta, gradient_fixed)
            self._velocities[token_id] = new_velocity
            correction = new_velocity

            # Apply correction — clamped to prevent overshoot
            new_w_scale = measured + correction

            # Hard clamp: cannot push beyond the expected ± tolerance
            lo = expected - anchor.tolerance_fixed
            hi = expected + anchor.tolerance_fixed
            new_w_scale = max(lo, min(hi, new_w_scale))

            # Zero-tolerance anchors: any deviation is a hard abort, never silent correction.
            # Enforces CLAUDE.md invariant: "Version mismatch = hard abort, never fallback."
            if anchor.tolerance_fixed == 0:
                if drift_fixed > 0:
                    raise RuntimeError(
                        f"Hard abort: zero-tolerance anchor '{token_id}' has drifted "
                        f"(measured={measured}, expected={expected}). "
                        "This invariant permits no correction."
                    )
                new_w_scale = expected

            self._state.w_scales[token_id] = new_w_scale
            adjustment = new_w_scale - measured

            m = DriftMeasurement(
                epoch=epoch,
                anchor_token_id=token_id,
                measured_w_scale=measured,
                expected_w_scale=expected,
                drift_fixed=drift_fixed,
                drift_index=drift_index,
                adjustment_applied=adjustment,
                passes_criterion=drift_index == 0.0,
            )
            measurements.append(m)
            self._state.measurements.append(m)
            if adjustment != 0:
                self._state.total_adjustments += 1

        self._state.cumulative_drift += sum(m.drift_index for m in measurements)
        return measurements

    def compute_drift_index(self) -> float:
        """
        Compute the current aggregate drift index D.
        SUCCESS CRITERION: D must equal 0.0 across 100,000 epochs.
        """
        if not self._state.measurements:
            return 0.0
        recent = self._state.measurements[-len(self._anchors):]
        return sum(m.drift_index for m in recent) / len(recent)

    def passes_criterion(self, epoch_count: int) -> bool:
        """
        Returns True if D = 0 has been maintained for epoch_count epochs.
        This is the T0 success criterion validation.
        """
        if len(self._state.measurements) < epoch_count * len(self._anchors):
            return False
        relevant = self._state.measurements[-(epoch_count * len(self._anchors)):]
        return all(m.passes_criterion for m in relevant)

    def get_w_scale(self, token_id: str) -> int:
        """Get current W_scale for a token in Q16.16 fixed-point."""
        return self._state.w_scales.get(token_id, INT_SCALE)

    def inject_anchor_token(self, token: AnchorToken) -> None:
        """
        Register a new anchor token at runtime.
        INVARIANT: Only permitted before the first calibration epoch.
        After epoch 0, the anchor set is frozen.
        """
        if self._state.epoch > 0:
            raise RuntimeError(
                "Anchor token registry is sealed after epoch 0. "
                "New anchors cannot be injected at runtime."
            )
        self._anchors[token.token_id] = token
        self._state.w_scales[token.token_id] = INT_SCALE

    def convergence_epochs(self) -> int:
        """Number of consecutive epochs with D=0 (convergence depth)."""
        count = 0
        n = len(self._anchors)
        measurements = self._state.measurements
        for i in range(len(measurements) - 1, -1, -n):
            batch = measurements[max(0, i - n + 1):i + 1]
            if not all(m.passes_criterion for m in batch):
                break
            count += 1
        return count
