"""Deterministic spectral/autocorrelation temporal-scale inference.

This module estimates a recurring timescale in a uniformly sampled real signal.
It has no authority effect and does not infer absolute time, causality, or clock
calibration.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Sequence

SCHEMA_VERSION = "1.0.0"
METHOD = "DFT_AUTOCORRELATION_V1"
AUTHORITY_EFFECT = "NONE"
MIN_SAMPLES = 8
MIN_AUTOCORRELATION_SUPPORT = 0.5


class SpectralTimeInferenceError(ValueError):
    """Raised when temporal-scale inference cannot be established safely."""


@dataclass(frozen=True)
class SpectralTimeInferenceReceiptV1:
    schema_version: str
    method: str
    sample_count: int
    sample_period: float
    dominant_frequency: float
    dominant_period: float
    integration_horizon: float
    spectral_bin: int
    lag_samples: int
    spectral_concentration: float
    autocorrelation_support: float
    authority_effect: str


def _validated_sample_period(sample_period: Real) -> float:
    if isinstance(sample_period, bool) or not isinstance(sample_period, Real):
        raise SpectralTimeInferenceError("INVALID_SAMPLE_PERIOD")
    value = float(sample_period)
    if not math.isfinite(value) or value <= 0.0:
        raise SpectralTimeInferenceError("INVALID_SAMPLE_PERIOD")
    return value


def _validated_samples(samples: Sequence[Real]) -> tuple[float, ...]:
    if len(samples) < MIN_SAMPLES:
        raise SpectralTimeInferenceError("INSUFFICIENT_SAMPLES")
    values: list[float] = []
    for sample in samples:
        if isinstance(sample, bool) or not isinstance(sample, Real):
            raise SpectralTimeInferenceError("NONREAL_SAMPLE")
        value = float(sample)
        if not math.isfinite(value):
            raise SpectralTimeInferenceError("NONFINITE_SAMPLE")
        values.append(value)
    return tuple(values)


def _positive_frequency_powers(centered: Sequence[float]) -> tuple[tuple[int, float], ...]:
    n = len(centered)
    powers: list[tuple[int, float]] = []
    for spectral_bin in range(2, n // 2 + 1):
        real = math.fsum(
            value * math.cos(2.0 * math.pi * spectral_bin * index / n)
            for index, value in enumerate(centered)
        )
        imag = -math.fsum(
            value * math.sin(2.0 * math.pi * spectral_bin * index / n)
            for index, value in enumerate(centered)
        )
        powers.append((spectral_bin, real * real + imag * imag))
    return tuple(powers)


def _normalized_autocorrelation(centered: Sequence[float], lag: int) -> float:
    left = centered[:-lag]
    right = centered[lag:]
    numerator = math.fsum(a * b for a, b in zip(left, right))
    left_energy = math.fsum(value * value for value in left)
    right_energy = math.fsum(value * value for value in right)
    denominator = math.sqrt(left_energy * right_energy)
    if denominator <= 0.0 or not math.isfinite(denominator):
        raise SpectralTimeInferenceError("NO_CONSISTENT_TEMPORAL_WITNESS")
    support = numerator / denominator
    return min(1.0, max(-1.0, support))


def infer_spectral_time(
    samples: Sequence[Real],
    sample_period: Real,
) -> SpectralTimeInferenceReceiptV1:
    """Infer a recurring temporal scale from a uniformly sampled real signal."""

    dt = _validated_sample_period(sample_period)
    values = _validated_samples(samples)
    n = len(values)

    mean = math.fsum(values) / n
    centered = tuple(value - mean for value in values)
    variance_energy = math.fsum(value * value for value in centered)
    if variance_energy <= 0.0 or not math.isfinite(variance_energy):
        raise SpectralTimeInferenceError("ZERO_VARIANCE_SIGNAL")

    powers = _positive_frequency_powers(centered)
    total_power = math.fsum(power for _, power in powers)
    if total_power <= 0.0 or not math.isfinite(total_power):
        raise SpectralTimeInferenceError("NO_POSITIVE_SPECTRAL_ENERGY")

    peak_power = max(power for _, power in powers)
    tie_abs_tol = max(1e-30, abs(peak_power) * 1e-15)
    spectral_bin = min(
        bin_index
        for bin_index, power in powers
        if math.isclose(power, peak_power, rel_tol=1e-12, abs_tol=tie_abs_tol)
    )

    dominant_frequency = spectral_bin / (n * dt)
    dominant_period = 1.0 / dominant_frequency
    lag_samples = int(round(dominant_period / dt))
    if lag_samples <= 0 or lag_samples >= n:
        raise SpectralTimeInferenceError("NO_CONSISTENT_TEMPORAL_WITNESS")

    autocorrelation_support = _normalized_autocorrelation(centered, lag_samples)
    if autocorrelation_support < MIN_AUTOCORRELATION_SUPPORT:
        raise SpectralTimeInferenceError("NO_CONSISTENT_TEMPORAL_WITNESS")

    return SpectralTimeInferenceReceiptV1(
        schema_version=SCHEMA_VERSION,
        method=METHOD,
        sample_count=n,
        sample_period=dt,
        dominant_frequency=dominant_frequency,
        dominant_period=dominant_period,
        integration_horizon=dominant_period,
        spectral_bin=spectral_bin,
        lag_samples=lag_samples,
        spectral_concentration=peak_power / total_power,
        autocorrelation_support=autocorrelation_support,
        authority_effect=AUTHORITY_EFFECT,
    )
