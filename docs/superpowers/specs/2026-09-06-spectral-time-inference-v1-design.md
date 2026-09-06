# Spectral Time Inference V1 Design

## Status

APPROVED_DESIGN / IMPLEMENTATION_PENDING

Base authority: `main@6eb2ac201bbe60ebaa9cebad714b8696683772e8`.

This design introduces a new evidence-bounded temporal estimator. It does not infer absolute time, causal direction, physical clock calibration, theorem truth, or admission authority.

## Goal

Given a uniformly sampled one-dimensional real signal, deterministically estimate its dominant recurring temporal scale and a bounded integration horizon using a joint spectral and autocorrelation witness.

## Interface

`infer_spectral_time(samples, sample_period)` returns an immutable `SpectralTimeInferenceReceiptV1` containing:

- `schema_version`
- `method`
- `sample_count`
- `sample_period`
- `dominant_frequency`
- `dominant_period`
- `integration_horizon`
- `spectral_bin`
- `lag_samples`
- `spectral_concentration`
- `autocorrelation_support`
- `authority_effect`

`authority_effect` is the constant string `NONE`.

## Algorithm

1. Validate a finite positive `sample_period` and at least 8 finite real samples.
2. Mean-center the signal. Reject zero-variance / DC-only input.
3. Compute an exact deterministic discrete Fourier power scan over positive bins `k=2..floor(n/2)`. Excluding `k=1` prevents claiming a robust recurring scale from only one cycle across the full observation window.
4. Choose the maximum-power bin. Exact ties choose the smallest bin index, producing a deterministic longest-period tie-break among equally powered admissible bins.
5. Convert the selected bin to `dominant_frequency = k / (n * sample_period)` and `dominant_period = 1 / dominant_frequency`.
6. Convert the spectral period to the nearest integer lag and compute normalized overlapping autocorrelation at that lag.
7. Require `autocorrelation_support >= 0.5`. Otherwise fail closed with `NO_CONSISTENT_TEMPORAL_WITNESS`.
8. Define `integration_horizon = dominant_period`. This is a measured recurring timescale, not a generic context-length preference.
9. Define `spectral_concentration` as selected-bin power divided by total scanned positive-bin power.

## Fail-closed conditions

Raise `SpectralTimeInferenceError` for:

- fewer than 8 samples;
- non-real samples or booleans;
- NaN or infinity in samples;
- non-finite or non-positive sample period;
- zero-variance / DC-only signals;
- absence of positive spectral energy;
- autocorrelation witness below 0.5.

## Required falsification tests

The implementation is not GREEN until all of the following pass:

1. integer-period sinusoid recovery;
2. sample-period scaling;
3. constant/DC-only rejection;
4. NaN/Inf rejection;
5. deterministic spectral tie-break;
6. spectral/autocorrelation consistency;
7. context-length anti-baseline: repeating the same periodic record must not double the inferred horizon;
8. `authority_effect == "NONE"`.

## Epistemic boundary

A passing test suite establishes only deterministic behavior of this software estimator for the tested contract. It does not establish a physical law, clock calibration, causality, biological mechanism, RH-related result, or AEGIS Claims Ledger admission. Promotion requires a separate evidence/admission transition.
