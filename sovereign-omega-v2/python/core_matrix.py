"""
SOVEREIGN OMEGA — Core Matrix (core_matrix.py)
EPISTEMIC TIER: T0

The hardware inference layer for AMD RX 570 / 8GB RAM.
All system components are represented as abstract functional definitions
M1, M2, M3 operating over a single pre-allocated contiguous byte array.

CONSTRAINTS:
  - Isolated M1 hash-chain primitive in m1_chain.py (stdlib only)
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
import mmap
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


# ── Adaptive Memory Layout (V18) ─────────────────────────────────────────────
# From exact V15 adaptive_memory.py; per-instance geometry and no 4 GiB default.
from adaptive_memory import (
    configured_arena_layout, effective_available_bytes, MemoryBudgetError,
)


# ── Functional Definitions ────────────────────────────────────────────────────

# M1 is re-exported here for existing consumers; implementation is hardware-free.
from m1_chain import M1

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

        # Adopt the exact V15 layout calculus, not its older M1 or checkpoint.
        self._layout = configured_arena_layout()
        try:
            self._array = mmap.mmap(-1, self._layout.total)
        except (MemoryError, OSError) as exc:
            raise MemoryBudgetError('ARENA_MMAP_ALLOCATION_FAILED') from exc
        try:
            self._mem = memoryview(self._array)
            self._m1_region = self._mem[:self._layout.m1_size]
            self._m2_region = self._mem[self._layout.m2_offset:self._layout.m3_offset]
            self._m3_region = self._mem[self._layout.m3_offset:self._layout.total]
            self._pgcs = PGCSController(event_callback=event_callback)
            self._failsafe = EpochFailsafeController(event_callback=event_callback)
            self._calibrator = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
        except BaseException:
            for name in ('_m3_region', '_m2_region', '_m1_region', '_mem'):
                view = getattr(self, name, None)
                if view is not None:
                    view.release()
            self._array.close()
            raise

        # State
        self._sequence: int = 0
        self._epoch: int = 0
        self._era: int = 0          # increments each time M1 wraps (circular log)
        self._running = False
        self._closed = False
        self._stopped = False
        self._views_released = False
        self._lock = threading.RLock()
        self._ready = threading.Event()

        # OPTIMUS V17: optional process-local transition statistics. Nothing
        # from this observer participates in E4, M1, public telemetry or replay.
        self._transition_observer = None
        self._transition_observer_errors = 0
        if os.environ.get('AEGIS_TRANSITION_OBSERVER') == '1':
            from transition_observer import TransitionObserver
            self._transition_observer = TransitionObserver()

        # Capacity at which M1 write head wraps (events per era)
        self._m1_era_capacity: int = len(self._m1_region) // 40

        # Performance metrics (fixed-point for determinism)
        self._total_vcg_error_fixed: int = 0
        self._total_processed: int = 0
        self._total_verified: int = 0
        self._m3_active_length: int = 0
        self._last_gate_signal_sequence: int = -1
        self._last_gate_signal_accepted: Optional[bool] = None

    def start(self) -> None:
        """Start before terminal stop; never restart closed PGCS."""
        with self._lock:
            if self._closed or self._stopped or self._views_released:
                raise RuntimeError('CORE_MATRIX_CLOSED')
            if self._running:
                return
            self._pgcs.start()
            self._running = True
            self._ready.set()
        if self._event_cb:
            self._event_cb('CORE_MATRIX_STARTED', {
                'hardware': self._hw.platform,
                'is_target_hardware': self._hw.is_target_hardware,
                'array_bytes': self._layout.total,
            })

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Block until start() has completed. Returns True if ready within timeout."""
        return self._ready.wait(timeout)

    def stop(self) -> None:
        """Idempotent terminal PGCS stop before optional arena release."""
        with self._lock:
            if self._closed or self._stopped:
                return
            self._running = False
            self._ready.clear()
            self._pgcs.stop()
            self._stopped = True
            if self._event_cb:
                self._event_cb('CORE_MATRIX_STOPPED', {
                    'total_processed': self._total_processed,
                    'final_epoch': self._epoch,
                })

    def close(self) -> None:
        """Release owned mmap views; exports can delay close, safely retryable."""
        with self._lock:
            if self._running:
                raise RuntimeError('CORE_MATRIX_STOP_REQUIRED')
            if self._closed:
                return
            if not self._stopped:
                self._pgcs.stop()
                self._stopped = True
                self._ready.clear()
            if not self._views_released:
                self._m1_region.release()
                self._m2_region.release()
                self._m3_region.release()
                self._mem.release()
                self._views_released = True
            try:
                self._array.close()
            except BufferError as exc:
                raise RuntimeError('CORE_MATRIX_EXPORTED_VIEW') from exc
            self._closed = True

    def process_event(
        self,
        payload: bytes,
        verifier_result: bytes,
        context_tokens: bytes,
    ) -> Dict[str, object]:
        """Commit a validated event with fail-closed E4 semantics.

        For a calibration boundary, plan the ENTIRE epoch before M1 mutation,
        so a zero-tolerance anchor violation cannot commit an event and leave
        partially advanced calibration. Caller-visible callback failure is a
        distinct COMMITTED status: irreversible M1 digests are never disguised
        as rolled-back events.
        """
        # Keep the calibration plan, M1 append and epoch commit in one
        # exclusion zone. Lock order: CoreMatrix, then calibrator. No reverse
        # acquisition is permitted in calibration methods.
        with self._lock, self._calibrator._lock:
            if (getattr(self, '_closed', False) or
                    getattr(self, '_stopped', False) or
                    getattr(self, '_views_released', False)):
                raise RuntimeError('CORE_MATRIX_CLOSED')
            failsafe_state = self._failsafe.state
            if failsafe_state in (EpochState.QUARANTINE, EpochState.FROZEN, EpochState.RECOVERING):
                return {'status': failsafe_state.value.upper(), 'sequence': self._sequence}

            if verifier_result not in (b'', b'\x00', b'\x01'):
                raise ValueError('verifier outcome must be empty or a single binary byte')
            if not isinstance(payload, (bytes, bytearray, memoryview)):
                raise TypeError('event payload must be bytes-like')
            if not isinstance(context_tokens, (bytes, bytearray, memoryview)):
                raise TypeError('context must be bytes-like')
            # Snapshot once before mutating any arena: caller may supply views
            # aliasing M1 or M3; memoryview byte lengths are not always len().
            safe_payload = bytes(payload)
            safe_context = bytes(context_tokens)
            if len(safe_context) > len(self._m3_region):
                raise ValueError('context exceeds M3 region capacity')
            if self._m1_era_capacity <= 0:
                raise ValueError('M1 ring contains no complete record')

            for name, view, needed in (
                ('M1', self._m1_region, 40),
                ('M3', self._m3_region, len(safe_context)),
            ):
                if (not isinstance(view, memoryview) or view.readonly or
                        view.ndim != 1 or view.itemsize != 1 or
                        not view.contiguous or len(view) < needed):
                    raise ValueError(f'{name} requires a writable byte region')
            if verifier_result:
                view = self._m2_region
                if (not isinstance(view, memoryview) or view.readonly or
                        view.ndim != 1 or view.itemsize != 1 or
                        not view.contiguous or len(view) < 8):
                    raise ValueError('M2 requires a writable eight-byte region')

            w_scale = self._calibrator.get_w_scale('GATE_ACCEPT_THRESHOLD')
            if type(w_scale) is not int or w_scale < 0:
                raise ValueError('invalid W_scale')

            old_sequence = self._sequence
            old_processed = self._total_processed
            era_wrap = (old_sequence > 0 and
                        old_sequence % self._m1_era_capacity == 0)
            next_epoch = self._epoch + 1
            planned_epoch = None
            if (old_processed + 1) % 100 == 0:
                # Plan may raise on invalid epoch or zero-tolerance drift.
                # No M1, M2, M3 or counter mutation has occurred yet.
                planned_epoch = self._calibrator.prepare_epoch(next_epoch)

            next_sequence, state_hash = M1(
                self._m1_region, safe_payload, old_sequence
            )
            self._sequence = next_sequence
            if era_wrap:
                self._era += 1

            vcg_error_fixed, gate_lcb_fixed = 0, 0
            if verifier_result:
                confidence_fixed = (INT_SCALE if verifier_result == b'\x01'
                                    else INT_SCALE // 2)
                vcg_error_fixed, gate_lcb_fixed = M2(
                    self._m2_region, verifier_result, confidence_fixed,
                    next_sequence,
                )

            compressed_context, divergence_fixed = M3(
                self._m3_region, safe_context, w_scale
            )
            self._m3_active_length = len(compressed_context)
            if verifier_result:
                self._total_vcg_error_fixed += vcg_error_fixed
                self._total_verified += 1
            self._total_processed = old_processed + 1
            if planned_epoch is not None:
                self._calibrator.commit_epoch(planned_epoch)
                self._epoch = next_epoch

            callback_error = None
            if era_wrap and self._event_cb:
                try:
                    self._event_cb('M1_ERA_WRAP', {
                        'era': self._era,
                        'sequence': old_sequence,
                        'capacity_per_era': self._m1_era_capacity,
                    })
                except Exception as exc:
                    # Do not raise as though the M1 append never committed.
                    callback_error = type(exc).__name__

            result = {
                'status': ('COMMITTED_CALLBACK_ERROR'
                           if callback_error else 'OK'),
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
            if callback_error:
                result['callback_delivery_error'] = callback_error
            # An observer failure cannot undo the committed M1 event or
            # alter the returned gate status. Fixtures predating V17 omit it.
            observer = getattr(self, '_transition_observer', None)
            if observer is not None:
                try:
                    observer.observe_verifier(verifier_result)
                except Exception:
                    self._transition_observer_errors = (
                        getattr(self, '_transition_observer_errors', 0) + 1
                    )
            return result

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

    def transition_analytics_snapshot(self) -> Optional[Dict[str, object]]:
        """Internal-only, explicitly authorized, process-local observation.

        Not part of emit_vcg_telemetry, /telemetry, SSE, checkpoint, or E4.
        The statistical summary is lossy and is not a replay or identity proof.
        """
        with self._lock:
            observer = getattr(self, '_transition_observer', None)
            if observer is None:
                return None
            try:
                snapshot = observer.snapshot()
                snapshot['observation_errors'] = getattr(
                    self, '_transition_observer_errors', 0
                )
                return snapshot
            except Exception:
                return {
                    'schema': 'AEGIS_VERIFIER_TRANSITIONS_V14_1',
                    'status': 'UNAVAILABLE',
                    'observation_errors': getattr(
                        self, '_transition_observer_errors', 0
                    ) + 1,
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
