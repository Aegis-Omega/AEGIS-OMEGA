"""
SOVEREIGN OMEGA — 12-Hour Multi-Hop Reasoning Stress Test
EPISTEMIC TIER: T0/T1

Primary validation protocol for the Python core matrix on AMD RX 570 / 8GB RAM.
This test must pass before any production deployment.

SUCCESS CRITERIA (all must pass simultaneously):
  PGCS: disk_swap_bytes_in = 0 AND disk_swap_bytes_out = 0 throughout 12 hours
  TGCS: run-to-run telemetry variance σ² = 0
  AFSE: correlation index R² >= 0.98 with distributed baselines
  Epoch Failsafe: corruption_count = 0 across 1,000+ crash loops
  Gradient-Anchor: drift_index D = 0 across 100,000 epochs

USAGE:
  python tests/stress_test.py                  # full 12-hour run
  python tests/stress_test.py --quick          # 60-second smoke test
  python tests/stress_test.py --crash-loops    # epoch failsafe validation only
"""

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core_matrix import CoreMatrix
from epoch_failsafe import EpochFailsafeController
from gradient_anchor import GradientAnchorCalibrator, DEFAULT_ANCHOR_TOKENS
from hardware_config import STRESS_TEST_DURATION_H, CRASH_LOOP_COUNT, detect_hardware
from tgcs_afse import AFSEController


# Observe cumulative PGCS swap evidence every 30 s, with up to 60 s
# between successful observations. No assertion of continuous external
# kernel tracing is made by this bounded sampling witness.
PGCS_SAMPLE_INTERVAL_S = 30.0
PGCS_MAX_SAMPLE_GAP_S = 60.0


@dataclass
class PGCSIntervalWitness:
    """Monotonic, fail-closed sampled evidence across the requested window."""

    sample_count: int = 0
    first_elapsed_s: Optional[float] = None
    last_elapsed_s: Optional[float] = None
    max_gap_s: float = 0.0
    first_rejection: Optional[str] = None

    def _reject(self, code: str) -> None:
        if self.first_rejection is None:
            self.first_rejection = code

    def observe(self, elapsed_s: float, telemetry: dict) -> None:
        self.sample_count += 1
        if (type(elapsed_s) not in (int, float) or
                not math.isfinite(elapsed_s) or elapsed_s < 0):
            self._reject("PGCS_INVALID_MONOTONIC_TIME")
            return

        if self.last_elapsed_s is not None:
            if elapsed_s < self.last_elapsed_s:
                self._reject("PGCS_CLOCK_REGRESSION")
                return
            gap = elapsed_s - self.last_elapsed_s
            self.max_gap_s = max(self.max_gap_s, gap)
            if gap > PGCS_MAX_SAMPLE_GAP_S:
                self._reject("PGCS_SAMPLE_GAP")
        else:
            self.first_elapsed_s = elapsed_s

        self.last_elapsed_s = elapsed_s
        if not isinstance(telemetry, dict) or telemetry.get("pgcs_passes") is not True:
            self._reject("PGCS_SAMPLE_UNVERIFIED")

    def passes_window(self, requested_s: float, observed_s: float,
                      interrupted: bool) -> bool:
        required_s = STRESS_TEST_DURATION_H * 3600
        return (
            not interrupted and self.first_rejection is None and
            requested_s >= required_s and observed_s >= required_s and
            self.sample_count >= 2 and self.first_elapsed_s == 0.0 and
            self.last_elapsed_s == observed_s and
            self.max_gap_s <= PGCS_MAX_SAMPLE_GAP_S and
            self.last_elapsed_s - self.first_elapsed_s >= required_s
        )


@dataclass
class StressTestResult:
    duration_s: float
    events_processed: int
    pgcs_passes: bool
    tgcs_passes: bool
    afse_r_squared: float
    afse_passes: bool
    epoch_failsafe_passes: bool
    gradient_anchor_passes: bool
    corruption_count: int
    final_drift_index: float
    overall_pass: bool
    pgcs_sample_count: int = 0
    pgcs_max_sample_gap_s: float = 0.0
    pgcs_first_rejection: Optional[str] = None

    def report(self) -> str:
        lines = [
            "=== SOVEREIGN OMEGA STRESS TEST RESULTS ===",
            f"Duration:           {self.duration_s:.1f}s ({self.duration_s/3600:.2f}h)",
            f"Events processed:   {self.events_processed:,}",
            f"",
            f"PGCS (sampled 12h): {'PASS' if self.pgcs_passes else 'HOLD'}",
            f"PGCS sample count:   {self.pgcs_sample_count} (max gap {self.pgcs_max_sample_gap_s:.1f}s)",
            f"PGCS gap/fault:      {self.pgcs_first_rejection or 'none observed'}",
            f"TGCS  (σ²=0):       {'PASS' if self.tgcs_passes else 'UNVERIFIED'}",
            f"AFSE  (R²≥0.98):    {'PASS' if self.afse_passes else 'FAIL'} (R²={self.afse_r_squared:.4f})",
            f"Epoch Failsafe:     {'PASS' if self.epoch_failsafe_passes else 'FAIL'} (corruptions={self.corruption_count})",
            f"Gradient Anchor:    {'PASS' if self.gradient_anchor_passes else 'FAIL'} (D={self.final_drift_index:.6f})",
            f"",
            f"OVERALL:            {'*** PASS ***' if self.overall_pass else '*** HOLD / NOT ADMITTED ***'}",
        ]
        return "\n".join(lines)


def run_stress_test(duration_s: float, crash_loops: int) -> StressTestResult:
    """
    Run the full stress test for the given duration.
    duration_s: test duration in seconds
    crash_loops: number of simulated crash loops for epoch failsafe
    """
    events = []

    def on_event(event_type: str, data: dict):
        events.append({"type": event_type, **data})

    matrix = CoreMatrix(event_callback=on_event)
    calibrator = GradientAnchorCalibrator(DEFAULT_ANCHOR_TOKENS)
    failsafe = EpochFailsafeController(event_callback=on_event)
    afse_ctrl = AFSEController()

    matrix.start()
    start_time = time.monotonic()
    sequence = 0
    pgcs_witness = PGCSIntervalWitness()
    last_pgcs_sample_s = 0.0

    print("Starting stress test... (Ctrl+C to abort)")

    interrupted = False
    try:
        # A valid final sample cannot replace the first observation.
        pgcs_witness.observe(0.0, matrix.emit_vcg_telemetry())
        while True:
            observed_s = time.monotonic() - start_time
            if observed_s >= duration_s:
                break
            if observed_s - last_pgcs_sample_s >= PGCS_SAMPLE_INTERVAL_S:
                pgcs_witness.observe(observed_s, matrix.emit_vcg_telemetry())
                last_pgcs_sample_s = observed_s

            # Process a batch of events
            for _ in range(100):
                payload = f"event_{sequence}".encode()
                verifier_result = b'\x01' if sequence % 3 != 0 else b'\x00'
                context = payload[:64]

                result = matrix.process_event(payload, verifier_result, context)
                afse_ctrl.record_event(sequence)
                sequence += 1

                # Calibrate every 100 events
                if sequence % 100 == 0:
                    calibrator.calibrate_epoch(sequence // 100)

                # Register epoch snapshot for failsafe
                if sequence % 500 == 0:
                    snap_bytes = matrix.get_epoch_snapshot() or b'\x00' * 32
                    failsafe.set_epoch_snapshot(
                        epoch_id=sequence // 500,
                        state=snap_bytes,
                        event_count=sequence,
                        last_sequence=sequence,
                        timestamp_sequence=sequence,
                    )

            # Print progress every 10,000 events
            if sequence % 10_000 == 0:
                elapsed = time.monotonic() - start_time
                pct = 100 * elapsed / duration_s
                print(f"\r  {pct:.1f}% | {sequence:,} events | {elapsed:.0f}s elapsed", end="", flush=True)

        # Simulate crash loops for epoch failsafe validation
        print(f"\nRunning {crash_loops} crash loop simulations...")
        for i in range(crash_loops):
            failsafe.report_agent_failure("En", f"simulated_crash_{i}", sequence + i)
            if i % 100 == 0:
                failsafe.reset_after_recovery()

    except KeyboardInterrupt:
        interrupted = True
        print("\nAborted by user.")

    # Capture T0 telemetry *before* terminal PGCS stop. Any fault in
    # observation must propagate and must never produce an admitted PASS.
    # A deliberately interrupted run cannot satisfy the full protocol.
    finally:
        elapsed = time.monotonic() - start_time
        try:
            telemetry = matrix.emit_vcg_telemetry()
            pgcs_witness.observe(elapsed, telemetry)
        finally:
            matrix.stop()
    drift_index = calibrator.compute_drift_index()
    # A partial calibration trace cannot attest the 100,000-epoch target.
    epochs_observed = sequence // 100
    calibrator_passes = (epochs_observed >= 100_000 and
                         calibrator.passes_criterion(100_000))

    # AFSE R² — actual computation from the AFSEController (not hardcoded)
    afse_r2 = afse_ctrl.get_r2()

    # The 12-hour criterion is stricter than a quick smoke or one swap sample.
    # TGCS run-to-run sigma^2 has no measured source in this harness:
    # fail CLOSED rather than fabricating a passing value.
    full_window = (not interrupted and
                   duration_s >= STRESS_TEST_DURATION_H * 3600 and
                   elapsed >= STRESS_TEST_DURATION_H * 3600)
    pgcs_passes = (full_window and
                   pgcs_witness.passes_window(duration_s, elapsed, interrupted))
    tgcs_passes = False  # OPEN: independent run-to-run variance evidence
    failsafe_passes = (not interrupted and
                       crash_loops >= CRASH_LOOP_COUNT and
                       failsafe.passes_t0_criterion())

    result = StressTestResult(
        duration_s=elapsed,
        events_processed=sequence,
        pgcs_passes=pgcs_passes,
        tgcs_passes=tgcs_passes,
        afse_r_squared=afse_r2,
        afse_passes=afse_r2 >= 0.98,
        epoch_failsafe_passes=failsafe_passes,
        gradient_anchor_passes=calibrator_passes,
        corruption_count=failsafe.corruption_count,
        final_drift_index=drift_index,
        overall_pass=(
            pgcs_passes and tgcs_passes and failsafe_passes and
            calibrator_passes and afse_r2 >= 0.98
        ),
        pgcs_sample_count=pgcs_witness.sample_count,
        pgcs_max_sample_gap_s=pgcs_witness.max_gap_s,
        pgcs_first_rejection=pgcs_witness.first_rejection,
    )

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sovereign Omega Stress Test")
    parser.add_argument("--quick", action="store_true", help="60-second smoke test")
    parser.add_argument("--crash-loops", action="store_true", help="Epoch failsafe only")
    args = parser.parse_args()

    hw = detect_hardware()
    print(f"Hardware: {hw.platform}, RAM: {hw.ram_bytes / 1024**3:.1f}GB, Target: {hw.is_target_hardware}")

    if args.quick:
        result = run_stress_test(60.0, 100)
    elif args.crash_loops:
        result = run_stress_test(10.0, CRASH_LOOP_COUNT)
    else:
        result = run_stress_test(STRESS_TEST_DURATION_H * 3600, CRASH_LOOP_COUNT)

    print("\n" + result.report())
    sys.exit(0 if result.overall_pass else 1)
