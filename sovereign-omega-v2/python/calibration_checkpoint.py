"""Lossless, versioned GradientAnchor calibration-state checkpoint codec.

No hardware/memory-size assumptions. Identical measurement batches are encoded
as runs, while decoding restores *every* DriftMeasurement and the Q16.16
momentum state. This is a continuation record, NOT an authenticated event log.
"""
import math
import os
from dataclasses import dataclass

from gradient_anchor import (
    DriftMeasurement, GradientAnchorCalibrator, GradientAnchorState,
    INT_SCALE, fixed_mul, from_fixed,
)

CALIBRATION_FORMAT = 'gradient-anchor-rle-v1'
# Exact restoration expands all measurements; cap the untrusted expansion.
# The limit is configurable for legitimately longer research runs.
MAX_RESTORE_MEASUREMENTS = int(os.environ.get(
    'AEGIS_CALIBRATION_MAX_RESTORE_MEASUREMENTS', '1000000'
))
if MAX_RESTORE_MEASUREMENTS < 1:
    raise ValueError('AEGIS_CALIBRATION_MAX_RESTORE_MEASUREMENTS must be positive')


class CalibrationCheckpointError(ValueError):
    """Calibration history cannot be safely serialized or restored."""


def _require(condition, detail):
    if not condition:
        raise CalibrationCheckpointError(detail)


def _anchors(calibrator):
    return [
        [token_id, anchor.token_hash, anchor.expected_w_scale,
         anchor.tolerance_fixed]
        for token_id, anchor in calibrator._anchors.items()
    ]


def _sample(measurement):
    return [
        measurement.anchor_token_id, measurement.measured_w_scale,
        measurement.expected_w_scale, measurement.drift_fixed,
        measurement.drift_index, measurement.adjustment_applied,
        measurement.passes_criterion,
    ]


@dataclass
class PreparedCalibration:
    state: GradientAnchorState
    velocities: dict


def snapshot_calibration(calibrator):
    """Serialize complete observable calibration state using repeat-run batches."""
    _require(isinstance(calibrator, GradientAnchorCalibrator),
             'checkpoint requires the real GradientAnchorCalibrator')
    state = calibrator._state
    ids = list(calibrator._anchors)
    n = len(ids)
    _require(n > 0 and type(state.epoch) is int and state.epoch >= 0,
             'invalid anchor count or calibration epoch')
    _require(state.epoch * n <= MAX_RESTORE_MEASUREMENTS,
             'calibration history exceeds configured restoration limit')
    _require(len(state.measurements) == state.epoch * n,
             'partial or missing calibration epoch measurements')
    runs = []
    for epoch in range(1, state.epoch + 1):
        batch = state.measurements[(epoch - 1) * n:epoch * n]
        _require(all(m.epoch == epoch and m.anchor_token_id == ids[i]
                     for i, m in enumerate(batch)),
                 'calibration measurements out of epoch/token order')
        samples = [_sample(m) for m in batch]
        if runs and runs[-1][2] == samples:
            runs[-1][1] += 1
        else:
            runs.append([epoch, 1, samples])
    result = {
        'format': CALIBRATION_FORMAT,
        'anchors': _anchors(calibrator),
        'epoch': state.epoch,
        'lr_fixed': calibrator._lr_fixed,
        'momentum_beta': calibrator._momentum_beta,
        'w_scales': dict(state.w_scales),
        'velocities': {key: calibrator._velocities.get(key, 0) for key in ids},
        'cumulative_drift': state.cumulative_drift,
        'total_adjustments': state.total_adjustments,
        'measurement_runs': runs,
    }
    # A save must also reject partially corrupt local calibration state.
    prepare_calibration_restore(calibrator, result, state.epoch)
    return result


def prepare_calibration_restore(calibrator, body, expected_epoch):
    """Validate and reconstruct without modifying the destination calibrator.

    Reject malformed schemas, mismatched anchor identity or hyperparameters,
    partial epochs, impossible drift records, and inconsistent Q16.16 momentum.
    """
    _require(isinstance(calibrator, GradientAnchorCalibrator),
             'restoration requires the real GradientAnchorCalibrator')
    _require(isinstance(body, dict), 'calibration snapshot must be an object')
    _require(body.get('format') == CALIBRATION_FORMAT,
             'unknown calibration snapshot format')
    _require(body.get('anchors') == _anchors(calibrator),
             'anchor identity, order, hash or tolerance mismatch')
    _require(type(expected_epoch) is int and expected_epoch >= 0,
             'invalid expected calibration epoch')
    _require(type(body.get('epoch')) is int and body['epoch'] == expected_epoch,
             'calibrator epoch differs from checkpoint epoch')
    _require(type(body.get('lr_fixed')) is int and
             body['lr_fixed'] == calibrator._lr_fixed and
             type(body.get('momentum_beta')) is int and
             body['momentum_beta'] == calibrator._momentum_beta,
             'calibrator dynamics differ from checkpoint')
    ids = list(calibrator._anchors)
    n = len(ids)
    _require(n > 0, 'empty anchor registry')
    _require(expected_epoch * n <= MAX_RESTORE_MEASUREMENTS,
             'calibration history exceeds configured restoration limit')
    scales = body.get('w_scales')
    velocities = body.get('velocities')
    _require(type(scales) is dict and type(velocities) is dict and
             set(scales) == set(ids) and set(velocities) == set(ids),
             'calibration scale/velocity keys mismatch')
    for key in ids:
        anchor = calibrator._anchors[key]
        _require(type(scales[key]) is int and type(velocities[key]) is int,
                 'Q16.16 calibration state must use integer values')
        _require(anchor.expected_w_scale - anchor.tolerance_fixed <= scales[key]
                 <= anchor.expected_w_scale + anchor.tolerance_fixed,
                 'calibrated weight outside permitted anchor bounds')
    cdrift = body.get('cumulative_drift')
    total_adjustments = body.get('total_adjustments')
    _require(type(cdrift) in (float, int) and math.isfinite(cdrift) and
             cdrift >= 0, 'invalid cumulative drift')
    _require(type(total_adjustments) is int and total_adjustments >= 0,
             'invalid total adjustment count')
    runs = body.get('measurement_runs')
    _require(type(runs) is list, 'invalid calibration measurement runs')

    # Prevalidate run extents before expanding any historical measurements.
    next_epoch = 1
    for run in runs:
        _require(type(run) is list and len(run) == 3 and
                 type(run[0]) is int and type(run[1]) is int and
                 run[0] == next_epoch and 1 <= run[1] <= expected_epoch,
                 'invalid or nonconsecutive measurement run')
        next_epoch += run[1]
        _require(next_epoch <= expected_epoch + 1,
                 'measurement run exceeds checkpoint epoch')
        _require(type(run[2]) is list and len(run[2]) == n,
                 'measurement batch does not match anchor count')
    _require(next_epoch == expected_epoch + 1,
             'missing calibration measurements')

    measurements = []
    reconstructed_velocities = {key: 0 for key in ids}
    recomputed_adjustments = 0
    recomputed_drift = 0.0
    # Reconstruct the exact previous corrected scale at each epoch boundary.
    # A checksum alone cannot establish that a recorded trajectory is possible.
    simulated_scales = {key: INT_SCALE for key in ids}
    for first, count, samples in runs:
        batch_drift = 0.0
        for i, row in enumerate(samples):
            _require(type(row) is list and len(row) == 7 and row[0] == ids[i],
                     'measurement token order mismatch')
            _, measured, expected, drift, index, adjustment, passed = row
            _require(all(type(v) is int for v in (measured, expected, drift, adjustment)) and
                     type(index) is float and math.isfinite(index) and
                     type(passed) is bool, 'measurement field type mismatch')
            anchor = calibrator._anchors[ids[i]]
            actual_drift = abs(measured - anchor.expected_w_scale)
            actual_index = (from_fixed(actual_drift) /
                            from_fixed(anchor.expected_w_scale)
                            if anchor.expected_w_scale != 0 else 0.0)
            _require(expected == anchor.expected_w_scale and
                     drift == actual_drift and index == actual_index and
                     passed == (index == 0.0),
                     'measurement does not satisfy mathematical drift identities')
            _require(anchor.tolerance_fixed > 0 or drift == 0,
                     'zero-tolerance anchor drift cannot be restored')
            batch_drift += index
        for epoch in range(first, first + count):
            for i, row in enumerate(samples):
                key, measured, expected, drift, index, adjustment, passed = row
                anchor = calibrator._anchors[key]
                _require(measured == simulated_scales[key],
                         'calibration epoch does not continue prior W_scale')
                grad = -fixed_mul(calibrator._lr_fixed, measured - expected)
                momentum = (fixed_mul(calibrator._momentum_beta,
                                      reconstructed_velocities[key]) +
                            fixed_mul(INT_SCALE - calibrator._momentum_beta, grad))
                lo = expected - anchor.tolerance_fixed
                hi = expected + anchor.tolerance_fixed
                corrected = max(lo, min(hi, measured + momentum))
                _require(corrected - measured == adjustment,
                         'measurement adjustment disagrees with Q16.16 dynamics')
                reconstructed_velocities[key] = momentum
                simulated_scales[key] = corrected
                measurements.append(DriftMeasurement(
                    epoch=epoch, anchor_token_id=key, measured_w_scale=measured,
                    expected_w_scale=expected, drift_fixed=drift,
                    drift_index=index, adjustment_applied=adjustment,
                    passes_criterion=passed,
                ))
                if adjustment:
                    recomputed_adjustments += 1
            recomputed_drift += batch_drift

    _require(recomputed_adjustments == total_adjustments and
             recomputed_drift == cdrift,
             'calibration aggregates disagree with recorded measurements')
    _require(reconstructed_velocities == velocities,
             'calibrator momentum not reproducible from measurements')
    _require(simulated_scales == scales,
             'final weight scales disagree with replayed calibration trajectory')
    result = GradientAnchorState(
        epoch=expected_epoch, w_scales=dict(scales),
        cumulative_drift=float(cdrift), measurements=measurements,
        total_adjustments=total_adjustments,
    )
    return PreparedCalibration(result, dict(velocities))


def require_fresh_calibrator(calibrator):
    """Prevent state recovery into a previously operated calibrator."""
    _require(isinstance(calibrator, GradientAnchorCalibrator),
             'destination has no recoverable calibration subsystem')
    state = calibrator._state
    _require(state.epoch == 0 and not state.measurements and
             state.total_adjustments == 0 and state.cumulative_drift == 0 and
             all(v == 0 for v in calibrator._velocities.values()) and
             all(v == INT_SCALE for v in state.w_scales.values()),
             'destination calibrator is not a fresh instance')


def install_calibration(calibrator, prepared):
    """Install a previously validated snapshot; call under CoreMatrix lock."""
    calibrator._state = prepared.state
    calibrator._velocities = prepared.velocities
