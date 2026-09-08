from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.spectral_time_inference import (  # noqa: E402
    SpectralTimeInferenceError,
    infer_spectral_time,
)


def sine_samples(*, period_samples: int, cycles: int, amplitude: float = 1.0) -> list[float]:
    return [
        amplitude * math.sin(2.0 * math.pi * index / period_samples)
        for index in range(period_samples * cycles)
    ]


def test_recovers_integer_period_sinusoid() -> None:
    receipt = infer_spectral_time(sine_samples(period_samples=8, cycles=8), sample_period=1.0)
    assert receipt.dominant_period == pytest.approx(8.0, rel=1e-12, abs=1e-12)
    assert receipt.dominant_frequency == pytest.approx(0.125, rel=1e-12, abs=1e-12)
    assert receipt.integration_horizon == pytest.approx(8.0, rel=1e-12, abs=1e-12)
    assert receipt.lag_samples == 8


def test_sample_period_scales_frequency_period_and_horizon() -> None:
    samples = sine_samples(period_samples=8, cycles=8)
    unit = infer_spectral_time(samples, sample_period=1.0)
    scaled = infer_spectral_time(samples, sample_period=0.25)
    assert scaled.dominant_frequency == pytest.approx(unit.dominant_frequency * 4.0)
    assert scaled.dominant_period == pytest.approx(unit.dominant_period * 0.25)
    assert scaled.integration_horizon == pytest.approx(unit.integration_horizon * 0.25)
    assert scaled.spectral_bin == unit.spectral_bin
    assert scaled.lag_samples == unit.lag_samples


def test_constant_signal_is_rejected() -> None:
    with pytest.raises(SpectralTimeInferenceError, match="ZERO_VARIANCE_SIGNAL"):
        infer_spectral_time([3.5] * 32, sample_period=1.0)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nonfinite_sample_is_rejected(bad: float) -> None:
    samples = sine_samples(period_samples=8, cycles=4)
    samples[3] = bad
    with pytest.raises(SpectralTimeInferenceError, match="NONFINITE_SAMPLE"):
        infer_spectral_time(samples, sample_period=1.0)


def test_equal_power_tie_break_prefers_smallest_spectral_bin() -> None:
    samples = [
        math.sin(2.0 * math.pi * index / 16.0)
        + math.sin(2.0 * math.pi * index / 8.0)
        for index in range(64)
    ]
    receipt = infer_spectral_time(samples, sample_period=1.0)
    assert receipt.spectral_bin == 4
    assert receipt.dominant_period == pytest.approx(16.0)


def test_spectral_peak_has_matching_autocorrelation_witness() -> None:
    receipt = infer_spectral_time(sine_samples(period_samples=8, cycles=8), sample_period=1.0)
    assert receipt.spectral_concentration > 0.999999999
    assert receipt.autocorrelation_support > 0.999999999


def test_repeating_same_periodic_record_does_not_double_horizon() -> None:
    short = sine_samples(period_samples=8, cycles=4)
    long = short + short
    short_receipt = infer_spectral_time(short, sample_period=1.0)
    long_receipt = infer_spectral_time(long, sample_period=1.0)
    assert long_receipt.sample_count == 2 * short_receipt.sample_count
    assert long_receipt.integration_horizon == pytest.approx(short_receipt.integration_horizon)
    assert long_receipt.dominant_period == pytest.approx(short_receipt.dominant_period)


def test_receipt_has_zero_authority_effect() -> None:
    receipt = infer_spectral_time(sine_samples(period_samples=8, cycles=4), sample_period=1.0)
    assert receipt.authority_effect == "NONE"


def test_invalid_sample_period_fails_closed() -> None:
    samples = sine_samples(period_samples=8, cycles=4)
    for bad in (0.0, -1.0, math.nan, math.inf):
        with pytest.raises(SpectralTimeInferenceError, match="INVALID_SAMPLE_PERIOD"):
            infer_spectral_time(samples, sample_period=bad)


def test_too_few_samples_fails_closed() -> None:
    with pytest.raises(SpectralTimeInferenceError, match="INSUFFICIENT_SAMPLES"):
        infer_spectral_time([0.0, 1.0, 0.0, -1.0], sample_period=1.0)
