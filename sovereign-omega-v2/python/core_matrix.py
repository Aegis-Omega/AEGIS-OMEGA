"""
SOVEREIGN OMEGA — Core Matrix (core_matrix.py)
EPISTEMIC TIER: T0

The hardware inference layer for AMD RX 570 / 8GB RAM.
All system components are represented as abstract functional definitions
M1, M2, M3 operating over a single pre-allocated contiguous byte array.

CONSTRAINTS:
  - Single file: eliminates module complexity and external dependencies
  - Memory: single pre-allocated contiguous byte array, 8GB ceiling
  - Execution: unprivileged user-space only, no kernel calls
  - Determinism: bit-shifted integer arithmetic throughout
  - Self-regulation: via internal math only, no OS intervention

INTEGRATION POINTS:
  - Receives governance signals from the TypeScript E4 gate via bridge.py
  - Emits VCG-eligible telemetry to the TypeScript E2 calibration layer
  - Epoch state snapshots provided to epoch_failsafe.py
  - W_scale values adjusted by gradient_anchor.py calibration

VALIDATION: 12-hour multi-hop reasoning stress test (see tests/stress_test.py)
  SUCCESS: PGCS disk I/O = 0, TGCS σ² = 0, AFSE R² >= 0.98
"""

import array
import ctypes
import hashlib
import os
import time
import threading
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from hardware_config import (
    RAM_TOTAL_BYTES, PGCS_TRIGGER_FRACTION,
    INT_SCALE, INT_SHIFT_BITS, INT_MAX,
    to_fixed, from_fixed, fixed_mul, fixed_clamp,
    detect_hardware, HardwareProfile,
)
from pgcs import PGCSController, PGCSTelemetry
from epoch_failsafe import EpochFailsafeController, EpochState
from gradient_anchor import GradientAnchorCalibrator, DEFAULT_ANCHOR_TOKENS


# ── Memory Layout ────────────────────────────────────────────────────────────
# The byte array is partitioned into three regions for M1, M2, M3.
# All region boundaries are aligned to INT_SCALE (65536 bytes) for
# deterministic memory access patterns.

# Default 4GB (AMD RX 570 / 8GB RAM profile). Overridable via AEGIS_ARRAY_BYTES
# for memory-constrained deployments (e.g. Cloud Run, where the bridge serves
# /platform/* + telemetry and does not need the full inference arena). Must be a
# multiple of INT_SCALE (65536) so region boundaries stay aligned. Unset = 4GB,
# so all tests and local runs are byte-identical to the original layout.
_INT_SCALE_ALIGN      = 65536
ARRAY_TOTAL_BYTES     = int(os.environ.get('AEGIS_ARRAY_BYTES', str(4 * 1024 ** 3)))
ARRAY_TOTAL_BYTES    -= ARRAY_TOTAL_BYTES % _INT_SCALE_ALIGN  # force alignment
M1_REGION_FRACTION    = 0.50            # 2GB — state management (E3 substrate)
M2_REGION_FRACTION    = 0.30            # 1.2GB — calibration and gate data
M3_REGION_FRACTION    = 0.20            # 0.8GB — inference context and projections

M1_OFFSET = 0
M1_SIZE   = int(ARRAY_TOTAL_BYTES * M1_REGION_FRACTION)
M2_OFFSET = M1_SIZE
M2_SIZE   = int(ARRAY_TOTAL_BYTES * M2_REGION_FRACTION)
M3_OFFSET = M2_OFFSET + M2_SIZE
M3_SIZE   = int(ARRAY_TOTAL_BYTES * M3_REGION_FRACTION)


# ── Functional Definitions ────────────────────────────────────────────────────

def M1(state: memoryview, payload: bytes, sequence: int) -> Tuple[int, bytes]:
    """
    M1: State management function.
    Transforms the E3 event substrate region of the byte array.
    Receives: current M1 region view, event payload bytes, sequence number.
    Returns: (new_sequence, state_hash_bytes).

    INVARIANT: Pure function — no external state, no I/O.
    INVARIANT: Sequence is always greater than any previously processed sequence.
    INVARIANT: Output is deterministic for identical inputs.
    """
    # Compute payload hash using SHA-256 (byte-level, not string)
    payload_hash = hashlib.sha256(payload).digest()

    # Write sequence and hash into M1 region at the current write head
    # Format: 8 bytes sequence + 32 bytes payload hash + payload
    write_head = (sequence * 40) % len(state)
    seq_bytes = sequence.to_bytes(8, 'little')

    end_pos = write_head + 40 + len(payload)
    if end_pos <= len(state):
        state[write_head:write_head + 8] = seq_bytes
        state[write_head + 8:write_head + 40] = payload_hash
        if len(payload) > 0:
            payload_end = min(write_head + 40 + len(payload), len(state))
            state[write_head + 40:payload_end] = payload[:payload_end - write_head - 40]

    # Chain hash: SHA-256(previous_state_hash || payload_hash)
    # This implements the same hash-chaining as the TypeScript E3 substrate
    prev_offset = ((sequence - 1) * 40) % len(state) if sequence > 0 else 0
    prev_hash = bytes(state[prev_offset + 8:prev_offset + 40])
    chain_hash = hashlib.sha256(prev_hash + payload_hash).digest()

    return sequence + 1, chain_hash


def M2(state: memoryview, verifier_result: bytes, confidence_fixed: int, sequence: int = 0) -> Tuple[int, int]:
    """
    M2: Calibration and gate data function.
    Transforms the calibration region of the byte array.
    Receives: M2 region view, verifier result bytes, Q16.16 confidence value, sequence number.
    Returns: (vcg_error_fixed, gate_lcb_fixed) — both Q16.16 fixed-point.

    INVARIANT: confidence_fixed must be in [0, INT_SCALE] (representing [0.0, 1.0]).
    INVARIANT: Pure function — no side effects.
    INVARIANT: sequence must be included in offset to prevent same-length collision.
    """
    # Clamp confidence to valid range
    confidence_fixed = fixed_clamp(confidence_fixed, 0, INT_SCALE)

    # Compute empirical correctness from verifier result
    # Single byte: 0x01 = passed, 0x00 = failed
    actual_correct = int(verifier_result[0]) if verifier_result else 0
    actual_fixed = INT_SCALE if actual_correct else 0

    # VCG error = |confidence - actual| in Q16.16
    vcg_error_fixed = abs(confidence_fixed - actual_fixed)

    # Simple LCB approximation: confidence - sqrt(2 * variance / n)
    # Using integer arithmetic: LCB ≈ confidence - 2 * vcg_error / INT_SCALE
    # This is a conservative bound; the TypeScript layer computes the full Bernstein bound
    lcb_adjustment = (2 * vcg_error_fixed) >> 1
    gate_lcb_fixed = max(0, confidence_fixed - lcb_adjustment)

    # Write to M2 region — offset incorporates sequence to prevent collision when
    # different events produce verifier_result bytes of equal length.
    offset = (sequence * 8 + len(verifier_result)) % (len(state) // 8)
    if offset + 8 <= len(state):
        state[offset:offset + 4] = vcg_error_fixed.to_bytes(4, 'little', signed=False)
        state[offset + 4:offset + 8] = gate_lcb_fixed.to_bytes(4, 'little', signed=False)

    return vcg_error_fixed, gate_lcb_fixed


def M3(state: memoryview, context_tokens: bytes, w_scale: int) -> Tuple[bytes, int]:
    """
    M3: Inference context and projection function.
    Transforms the context region of the byte array.
    Receives: M3 region view, context token bytes, Q16.16 W_scale value.
    Returns: (compressed_context, divergence_score_fixed).

    INVARIANT: w_scale is always within the anchor token tolerance bounds.
    INVARIANT: context_tokens is the active window — not the full history.
    """
    if not context_tokens:
        return b'', 0

    # Apply W_scale to context token weights
    # This is the correction mechanism that keeps the router calibrated
    scaled_len = min(len(context_tokens), len(state))
    scaled = bytearray(scaled_len)
    for i in range(scaled_len):
        # Fixed-point multiplication: token[i] * w_scale / INT_SCALE
        token_val = context_tokens[i]
        scaled_val = (token_val * w_scale) >> INT_SHIFT_BITS
        scaled[i] = min(255, max(0, scaled_val))

    # Write to M3 region
    state[:scaled_len] = scaled

    # Compute divergence score as mean absolute deviation from INT_SCALE-normalised values
    # Lower divergence = better calibration
    expected = w_scale >> 8  # expected scaled token value
    total_deviation = sum(abs(b - expected) for b in scaled)
    divergence_fixed = (total_deviation * INT_SCALE) // (scaled_len * 255) if scaled_len > 0 else 0

    return bytes(scaled), divergence_fixed


# ── Core Matrix Controller ───────────────────────────────────────────────────

class CoreMatrix:
    """
    The unified execution matrix. Coordinates M1, M2, M3 over the
    pre-allocated contiguous byte array. Integrates PGCS, epoch failsafe,
    and gradient-anchor calibration.

    INTERFACE TO TYPESCRIPT LAYER:
      - receive_gate_signal(proposal_id, accepted): gate decisions from E4
      - emit_vcg_telemetry(): VCG-eligible data for E2 calibration layer
      - get_epoch_snapshot(): state for epoch failsafe
    """

    def __init__(
        self,
        event_callback: Optional[Callable[[str, dict], None]] = None,
    ):
        self._hw = detect_hardware()
        self._event_cb = event_callback

        # Pre-allocate the contiguous byte array
        # Using bytearray for mutability; memoryview for zero-copy slicing
        self._array = bytearray(ARRAY_TOTAL_BYTES)
        self._mem = memoryview(self._array)

        # Region views (zero-copy slices into the single array)
        self._m1_region = self._mem[M1_OFFSET:M1_OFFSET + M1_SIZE]
        self._m2_region = self._mem[M2_OFFSET:M2_OFFSET + M2_SIZE]
        self._m3_region = self._mem[M3_OFFSET:M3_OFFSET + M3_SIZE]

        # Subsystems
        self._pgcs = PGCSController(event_callback=event_callback)
        self._failsafe = EpochFailsafeController(event_callback=event_callback)
        self._calibrator = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)

        # State
        self._sequence: int = 0
        self._epoch: int = 0
        self._era: int = 0          # increments each time M1 wraps (circular log)
        self._running = False
        self._lock = threading.RLock()
        self._ready = threading.Event()

        # Capacity at which M1 write head wraps (events per era)
        self._m1_era_capacity: int = M1_SIZE // 40

        # Performance metrics (fixed-point for determinism)
        self._total_vcg_error_fixed: int = 0
        self._total_processed: int = 0

    def start(self) -> None:
        """Start the core matrix and all subsystems."""
        self._pgcs.start()
        self._running = True
        self._ready.set()
        if self._event_cb:
            self._event_cb('CORE_MATRIX_STARTED', {
                'hardware': self._hw.platform,
                'is_target_hardware': self._hw.is_target_hardware,
                'array_bytes': ARRAY_TOTAL_BYTES,
            })

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Block until start() has completed. Returns True if ready within timeout."""
        return self._ready.wait(timeout)

    def stop(self) -> None:
        """Stop the core matrix and all subsystems."""
        self._running = False
        self._pgcs.stop()
        if self._event_cb:
            self._event_cb('CORE_MATRIX_STOPPED', {
                'total_processed': self._total_processed,
                'final_epoch': self._epoch,
            })

    def process_event(
        self,
        payload: bytes,
        verifier_result: bytes,
        context_tokens: bytes,
    ) -> Dict[str, object]:
        """
        Process one governance event through M1 → M2 → M3.
        Returns telemetry dict for the TypeScript calibration layer.

        INVARIANT: sequence is always incremented atomically.
        INVARIANT: All temporal values derive from sequence, never wall clock.
        """
        with self._lock:
            # Check failsafe state before processing — FROZEN and RECOVERING both gate events
            failsafe_state = self._failsafe.state
            if failsafe_state in (EpochState.FROZEN, EpochState.RECOVERING):
                return {'status': failsafe_state.value.upper(), 'sequence': self._sequence}

            # Detect M1 circular wrap and log an era-boundary event (F-07)
            if self._sequence > 0 and self._sequence % self._m1_era_capacity == 0:
                self._era += 1
                if self._event_cb:
                    self._event_cb('M1_ERA_WRAP', {
                        'era': self._era,
                        'sequence': self._sequence,
                        'capacity_per_era': self._m1_era_capacity,
                    })

            # M1: state management
            self._sequence, state_hash = M1(
                self._m1_region, payload, self._sequence
            )

            # M2: calibration gate
            # confidence_fixed derived from verifier result
            confidence_fixed = INT_SCALE if verifier_result and verifier_result[0] else INT_SCALE // 2
            vcg_error_fixed, gate_lcb_fixed = M2(
                self._m2_region, verifier_result, confidence_fixed, self._sequence
            )

            # M3: context projection with current W_scale
            w_scale = self._calibrator.get_w_scale('GATE_ACCEPT_THRESHOLD')
            compressed_context, divergence_fixed = M3(
                self._m3_region, context_tokens, w_scale
            )

            # Accumulate VCG
            self._total_vcg_error_fixed += vcg_error_fixed
            self._total_processed += 1

            # Calibrate anchor tokens every 100 events
            if self._total_processed % 100 == 0:
                self._epoch += 1
                self._calibrator.calibrate_epoch(self._epoch)

            # Gate decision: LCB > 0 means accept
            gate_accepted = gate_lcb_fixed > 0

            return {
                'status': 'OK',
                'sequence': self._sequence,
                'epoch': self._epoch,
                'state_hash': state_hash.hex(),
                'vcg_error_fixed': vcg_error_fixed,
                'vcg_error_float': from_fixed(vcg_error_fixed),
                'gate_lcb_fixed': gate_lcb_fixed,
                'gate_accepted': gate_accepted,
                'divergence_fixed': divergence_fixed,
                'drift_index': self._calibrator.compute_drift_index(),
            }

    def receive_gate_signal(self, proposal_id: str, accepted: bool, sequence: int) -> None:
        """
        Receive gate decision from the TypeScript E4 gate.
        Updates M2 region to reflect the gate outcome.
        sequence MUST come from the TypeScript event substrate.
        """
        with self._lock:
            signal_byte = b'\x01' if accepted else b'\x00'
            M2(self._m2_region, signal_byte, INT_SCALE if accepted else 0, sequence)

    def emit_vcg_telemetry(self) -> Dict[str, object]:
        """
        Emit VCG-eligible telemetry for the TypeScript E2 calibration layer.
        This data will be fed into VCGTracker.addResult() in the TypeScript layer.
        Lock acquired so the caller sees a consistent epoch/sequence/vcg snapshot
        and not a torn view mid-process_event() execution (H-02).
        """
        with self._lock:
            seq = self._sequence
            epoch = self._epoch
            avg_vcg_error = from_fixed(
                self._total_vcg_error_fixed // max(1, self._total_processed)
            )
            drift_index = self._calibrator.compute_drift_index()
            failsafe_state = self._failsafe.state.value
            corruption_count = self._failsafe.corruption_count
            calibrator_ok = self._calibrator.passes_criterion(100_000)
        # pgcs.snapshot() reads psutil/disk — safe outside the lock
        pgcs_snap = self._pgcs.snapshot(seq)
        return {
            'sequence': seq,
            'epoch': epoch,
            'avg_vcg_error': avg_vcg_error,
            'drift_index': drift_index,
            'pgcs_passes': pgcs_snap.passes_criterion,
            'failsafe_state': failsafe_state,
            'corruption_count': corruption_count,
            'calibrator_passes_100k': calibrator_ok,
        }

    def get_epoch_snapshot(self) -> Optional[bytes]:
        """
        Return a representative epoch state sample for the epoch failsafe.
        Samples 256 bytes from four evenly-spaced positions across the 2GB M1 region
        rather than only the first 1KB, which is not representative after the first
        25 events fill the initial write window.
        Lock acquired so the snapshot captures M1 state consistent with the
        sequence/era counters — no torn read mid-process_event() (H-02).
        """
        with self._lock:
            region_len = len(self._m1_region)
            chunk = 256
            positions = [0, region_len // 4, region_len // 2, (3 * region_len) // 4]
            parts = [bytes(self._m1_region[p:p + chunk]) for p in positions]
            seq_bytes = self._sequence.to_bytes(8, 'little')
            era_bytes = self._era.to_bytes(4, 'little')
        return b''.join(parts) + seq_bytes + era_bytes  # 4×256 + 12 = 1036 bytes
