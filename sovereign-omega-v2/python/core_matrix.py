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

_M1_ENTRY_BYTES = 40
_M1_GENESIS = bytes(32)
_M1_DOMAIN = b'AEGIS-M1-CHAIN-V2\x00'


def M1(state: memoryview, payload: bytes, sequence: int) -> Tuple[int, bytes]:
    """Advance an in-place SHA-256 chain over fixed 40-byte ring slots.

    Each slot contains u64le(sequence) || chain_digest. The digest binds
    the payload length and payload SHA-256; raw payload bytes are NOT stored
    in this ring. A separate authenticated event ledger is needed for replay.
    Requires exclusive write access; this is NOT a pure function.
    """
    if state.readonly or state.ndim != 1 or state.itemsize != 1 or not state.contiguous:
        raise ValueError('M1 requires a contiguous writable byte memoryview')
    slots = len(state) // _M1_ENTRY_BYTES
    if slots == 0:
        raise ValueError('M1 region must have at least 40 bytes')
    if not isinstance(sequence, int) or not 0 <= sequence < (1 << 64) - 1:
        raise ValueError('M1 sequence must fit u64 including successor')
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError('M1 payload must be bytes-like')

    snapshot = bytes(payload)
    if len(snapshot) >= 1 << 64:
        raise ValueError('M1 payload length must fit u64')
    seq_bytes = sequence.to_bytes(8, 'little')
    slot = (sequence % slots) * _M1_ENTRY_BYTES
    old = bytes(state[slot:slot + _M1_ENTRY_BYTES])
    if sequence == 0:
        if old != bytes(_M1_ENTRY_BYTES):
            raise ValueError('M1 genesis requires an empty first slot')
        prev_digest = _M1_GENESIS
    else:
        prev_slot = ((sequence - 1) % slots) * _M1_ENTRY_BYTES
        prev_record = bytes(state[prev_slot:prev_slot + _M1_ENTRY_BYTES])
        if (prev_record[:8] != (sequence - 1).to_bytes(8, 'little')
                or prev_record[8:] == bytes(32)):
            raise ValueError('M1 chain predecessor missing or mismatched')
        prev_digest = prev_record[8:]
        if old != bytes(_M1_ENTRY_BYTES) and old[:8] == seq_bytes:
            raise ValueError('M1 replay/rewrite of an existing sequence')
        if sequence < slots and old != bytes(_M1_ENTRY_BYTES):
            raise ValueError('M1 unexpected occupied slot before first wrap')

    digest = hashlib.sha256(
        _M1_DOMAIN + prev_digest + seq_bytes + len(snapshot).to_bytes(8, 'little')
        + hashlib.sha256(snapshot).digest()
    ).digest()
    state[slot:slot + _M1_ENTRY_BYTES] = seq_bytes + digest
    return sequence + 1, digest


def M2(state: memoryview, verifier_result: bytes, confidence_fixed: int,
       sequence: int = 0) -> Tuple[int, int]:
    """Record pointwise calibration error, not an unsupported statistical LCB.

    The 8-byte circular record is u32le(absolute_error_Q16) || u32le(0).
    The existing second return field is reserved for a separately validated
    multi-observation confidence bound, and fails closed (0) until then.
    The verifier byte must be an OUTCOME, never an EventClass discriminator.
    This function mutates state in place; it is NOT pure.
    """
    if state.readonly or state.ndim != 1 or state.itemsize != 1 or not state.contiguous:
        raise ValueError('M2 requires a contiguous writable byte memoryview')
    slots = len(state) // 8
    if slots == 0:
        raise ValueError('M2 region must have at least eight bytes')
    if not isinstance(sequence, int) or sequence < 0:
        raise ValueError('M2 sequence must be nonnegative')
    if verifier_result not in (b'\x00', b'\x01'):
        raise ValueError('M2 requires a single explicit binary verifier outcome')

    confidence_fixed = fixed_clamp(confidence_fixed, 0, INT_SCALE)
    actual_fixed = INT_SCALE if verifier_result == b'\x01' else 0
    vcg_error_fixed = abs(confidence_fixed - actual_fixed)
    gate_lcb_fixed = 0
    offset = (sequence % slots) * 8
    state[offset:offset + 8] = (vcg_error_fixed.to_bytes(4, 'little')
                               + gate_lcb_fixed.to_bytes(4, 'little'))
    return vcg_error_fixed, gate_lcb_fixed


def M3(state: memoryview, context_tokens: bytes, w_scale: int) -> Tuple[bytes, int]:
    """Project bytes and return Q16.16 mean absolute projection distortion.

    Only state[:len(context_tokens)] is active after the call. Trailing bytes
    remain unchanged; caller must track active length. Snapshot source first
    for deterministic operation when input aliases the destination.
    """
    if state.readonly or state.ndim != 1 or state.itemsize != 1 or not state.contiguous:
        raise ValueError('M3 requires a contiguous writable byte memoryview')
    if not isinstance(w_scale, int) or w_scale < 0:
        raise ValueError('M3 w_scale must be a nonnegative Q16.16 integer')
    if not isinstance(context_tokens, (bytes, bytearray, memoryview)):
        raise TypeError('M3 context_tokens must be bytes-like')
    original = bytes(context_tokens)
    n = len(original)
    if n > len(state):
        raise ValueError('M3 active window exceeds region capacity')
    if n == 0:
        return b'', 0

    scaled = bytearray(n)
    total_distortion = 0
    for i, token_val in enumerate(original):
        scaled_val = min(255, (token_val * w_scale) >> INT_SHIFT_BITS)
        scaled[i] = scaled_val
        total_distortion += abs(token_val - scaled_val)
    distortion_fixed = (total_distortion * INT_SCALE) // (n * 255)
    state[:n] = scaled
    return bytes(scaled), distortion_fixed


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
        self._total_verified: int = 0
        self._m3_active_length: int = 0
        self._last_gate_signal_sequence: int = -1
        self._last_gate_signal_accepted: Optional[bool] = None

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
        """Process one event. Unverified event-class bytes are not outcomes.

        Local pointwise calibration does NOT authorize an E4 action.
        The gate_accepted field is fail-closed until an authenticated,
        statistically validated E4 decision is integrated separately.
        """
        with self._lock:
            failsafe_state = self._failsafe.state
            if failsafe_state in (EpochState.FROZEN, EpochState.RECOVERING):
                return {'status': failsafe_state.value.upper(), 'sequence': self._sequence}

            # Validate all ordinary inputs before first region mutation.
            if verifier_result not in (b'', b'\x00', b'\x01'):
                raise ValueError('verifier outcome must be empty or a single binary byte')
            if not isinstance(context_tokens, (bytes, bytearray, memoryview)):
                raise TypeError('context must be bytes-like')
            if len(context_tokens) > len(self._m3_region):
                raise ValueError('context exceeds M3 region capacity')
            if len(self._m2_region) < 8 and verifier_result:
                raise ValueError('M2 region too short')
            w_scale = self._calibrator.get_w_scale('GATE_ACCEPT_THRESHOLD')
            if not isinstance(w_scale, int) or w_scale < 0:
                raise ValueError('invalid W_scale')

            old_sequence = self._sequence
            next_sequence, state_hash = M1(self._m1_region, payload, old_sequence)
            self._sequence = next_sequence
            if old_sequence > 0 and old_sequence % self._m1_era_capacity == 0:
                self._era += 1
                if self._event_cb:
                    self._event_cb('M1_ERA_WRAP', {
                        'era': self._era,
                        'sequence': old_sequence,
                        'capacity_per_era': self._m1_era_capacity,
                    })

            # b'' means no ground-truth outcome, not a failed verifier.
            # EventClass bytes are stripped by the bridge routing adapter.
            vcg_error_fixed, gate_lcb_fixed = 0, 0
            if verifier_result:
                confidence_fixed = INT_SCALE if verifier_result == b'\x01' else INT_SCALE // 2
                vcg_error_fixed, gate_lcb_fixed = M2(
                    self._m2_region, verifier_result, confidence_fixed, self._sequence
                )
                self._total_vcg_error_fixed += vcg_error_fixed
                self._total_verified += 1

            compressed_context, divergence_fixed = M3(
                self._m3_region, context_tokens, w_scale
            )
            self._m3_active_length = len(compressed_context)
            self._total_processed += 1
            if self._total_processed % 100 == 0:
                self._epoch += 1
                self._calibrator.calibrate_epoch(self._epoch)

            # No confidence-sequence history, n, alpha, or variance in M2.
            # Never elevate its Q16 point estimate to mutation authority.
            return {
                'status': 'OK',
                'sequence': self._sequence,
                'epoch': self._epoch,
                'state_hash': state_hash.hex(),
                'vcg_error_fixed': vcg_error_fixed,
                'vcg_error_float': from_fixed(vcg_error_fixed),
                'gate_lcb_fixed': gate_lcb_fixed,
                'gate_lcb_valid': False,
                'gate_accepted': False,
                'verified_outcome_available': bool(verifier_result),
                'divergence_fixed': divergence_fixed,
                'drift_index': self._calibrator.compute_drift_index(),
            }

    def receive_gate_signal(self, proposal_id: str, accepted: bool, sequence: int) -> None:
        """Track external E4 gate acknowledgements without falsifying VCG outcomes.

        A gate's accept/reject decision is NOT an observed correctness label;
        do not insert it into M2's pointwise calibration slots.
        Only the separate MutationGate maintains approval authority.
        """
        with self._lock:
            if not isinstance(sequence, int) or sequence < 0:
                raise ValueError('gate signal sequence must be nonnegative')
            if sequence <= self._last_gate_signal_sequence:
                return
            self._last_gate_signal_sequence = sequence
            self._last_gate_signal_accepted = bool(accepted)

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
                self._total_vcg_error_fixed // max(1, self._total_verified)
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
            'vcg_observations': self._total_verified,
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
