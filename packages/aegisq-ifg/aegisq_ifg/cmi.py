"""Restricted Gaussian conditional mutual information pilot.

The Fisher interval is an asymptotic interval under an *asserted* IID joint
Gaussian model and features fixed independently of the evaluated observations.
Its transformation is an approximate lower confidence bound on Gaussian CMI,
not a distribution-free bound, a causal test, or a diagnostic validation.

Reference for the partial-correlation Fisher standard error:
https://search.r-project.org/CRAN/refmans/pcalg/html/condIndFisherZ.html
"""

import math
from numbers import Integral, Real

import numpy as np
from scipy.stats import norm


SUPPORTED_ASSUMPTIONS = "iid_joint_gaussian_fixed_features"
MAX_DESIGN_CONDITION = 1e8
MIN_RESIDUAL_RMS = 1e-10
PERFECT_CORRELATION_TOLERANCE = 1e-12


class _InvalidInput(ValueError):
    pass


def _finite_real_scalar(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        return None
    try:
        converted = float(value)
    except (OverflowError, TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _real_array(value, name):
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise _InvalidInput(f"{name}_INVALID_ARRAY") from exc
    if np.iscomplexobj(array):
        raise _InvalidInput(f"{name}_COMPLEX_UNSUPPORTED")
    if array.dtype.kind not in "iuf":
        raise _InvalidInput(f"{name}_REAL_NUMERIC_REQUIRED")
    with np.errstate(over="ignore", invalid="ignore"):
        array = array.astype(np.float64)
    if not np.isfinite(array).all():
        raise _InvalidInput(f"{name}_NONFINITE")
    return array


def _standardize(array, name):
    """Scale before centering to tolerate very large or small measurement units."""
    magnitude = np.max(np.abs(array), axis=0)
    if np.any(magnitude == 0):
        raise _InvalidInput(f"{name}_CONSTANT_FEATURE")
    scaled = array / magnitude
    centered = scaled - np.mean(scaled, axis=0)
    rms = np.sqrt(np.mean(centered * centered, axis=0))
    if np.any(rms == 0) or not np.isfinite(rms).all():
        raise _InvalidInput(f"{name}_CONSTANT_FEATURE")
    return centered / rms


def gaussian_cmi_lcb(
    x,
    y,
    z,
    *,
    unit_ids,
    assumptions,
    alpha=0.05,
    gamma_nats=0.02,
    family_size=1,
):
    """Return a JSON-safe research gate decision for scalar Gaussian X and Y.

    ``x`` and ``y`` must be finite real one-dimensional arrays. ``z`` is an
    n-by-k array, a vector for one conditioning feature, or None for k=0.
    ``unit_ids`` must be unique nonempty strings, one per observation. Distinct
    identifiers do not establish independence: repeated measures, time series,
    learned/adaptively selected features and binary targets are outside scope.

    ``assumptions`` must equal SUPPORTED_ASSUMPTIONS. This is a caller assertion,
    never verification of Gaussianity, IID sampling or absence of confounding.
    ``family_size`` is the externally specified number of tests in the fixed
    family; the function cannot detect undeclared/adaptive multiple testing.

    The two-sided Fisher interval uses SE=1/sqrt(n-k-3), and a Bonferroni
    critical value qnorm(1-alpha/(2*family_size)). Its closest point to zero is
    transformed with -log(1-r^2)/2. Acceptance requires LCB >= gamma_nats > 0.
    All invalid or numerically degenerate inputs return DENY; missing required
    keyword arguments are rejected by Python's call signature.
    """
    result = {
        "status": "DENY",
        "reasons": [],
        "estimate_nats": None,
        "lcb_nats": None,
        "partial_r": None,
        "scope": "GAUSSIAN_SCALAR_CONTINUOUS_CMI_RESEARCH_ONLY",
        "uncertainty_method": "ASYMPTOTIC_FISHER_INTERVAL_BONFERRONI",
        "assumptions_verified": False,
        "causal_evidence": False,
        "clinical_validation": False,
        "limitations": [
            "Unique unit IDs do not establish IID sampling.",
            "The joint Gaussian model and fixed feature selection are asserted, not verified.",
            "Time series, clusters, binary labels and adaptive test families are unsupported.",
            "Conditional dependence does not establish causation or eliminate unmeasured confounding.",
        ],
    }

    def deny(reason):
        result["reasons"] = [reason]
        return result

    if not isinstance(assumptions, str) or assumptions != SUPPORTED_ASSUMPTIONS:
        return deny("UNSUPPORTED_OR_MISSING_ASSUMPTIONS")
    result["asserted_assumptions"] = assumptions
    alpha = _finite_real_scalar(alpha)
    if alpha is None or not 0 < alpha < 1:
        return deny("INVALID_ALPHA")
    gamma_nats = _finite_real_scalar(gamma_nats)
    if gamma_nats is None or gamma_nats <= 0:
        return deny("INVALID_GAMMA_NATS")
    if (
        isinstance(family_size, (bool, np.bool_))
        or not isinstance(family_size, Integral)
        or family_size < 1
    ):
        return deny("INVALID_FAMILY_SIZE")
    alpha, gamma_nats, family_size = float(alpha), float(gamma_nats), int(family_size)
    try:
        corrected_alpha = alpha / family_size
        # isf avoids subtractive cancellation in 1 - alpha/(2*family_size).
        critical_value = float(norm.isf(corrected_alpha / 2))
    except (OverflowError, ValueError):
        return deny("UNCERTAINTY_NUMERIC_FAILURE")
    if corrected_alpha <= 0 or not np.isfinite(critical_value):
        return deny("UNCERTAINTY_NUMERIC_FAILURE")
    result.update(
        alpha=alpha,
        gamma_nats=gamma_nats,
        family_size=family_size,
        corrected_alpha=corrected_alpha,
    )

    try:
        x = _real_array(x, "X")
        y = _real_array(y, "Y")
        if x.ndim != 1 or y.ndim != 1 or x.shape != y.shape:
            raise _InvalidInput("SCALAR_X_Y_MATCHING_VECTORS_REQUIRED")
        n = len(x)
        if z is None:
            z = np.empty((n, 0), dtype=float)
        else:
            z = _real_array(z, "Z")
            if z.ndim == 1:
                z = z[:, None]
            if z.ndim != 2 or z.shape[0] != n:
                raise _InvalidInput("Z_SHAPE_MISMATCH")
        k = z.shape[1]
        result.update(n=n, conditioning_dimension=k)
        if n < max(30, k + 5):
            raise _InvalidInput("INSUFFICIENT_INDEPENDENT_UNITS")

        if not isinstance(unit_ids, (list, tuple, np.ndarray)):
            raise _InvalidInput("UNIT_IDS_REQUIRED")
        if isinstance(unit_ids, np.ndarray) and unit_ids.ndim != 1:
            raise _InvalidInput("UNIT_IDS_INVALID")
        ids = list(unit_ids)
        if len(ids) != n or any(not isinstance(value, str) or not value.strip() for value in ids):
            raise _InvalidInput("UNIT_IDS_INVALID")
        if len(set(ids)) != n:
            raise _InvalidInput("DUPLICATE_UNIT_IDS_CLUSTERED_DATA_UNSUPPORTED")

        if np.unique(x).size <= 2 or np.unique(y).size <= 2:
            raise _InvalidInput("BINARY_OR_CONSTANT_X_Y_UNSUPPORTED")
        x_standard = _standardize(x, "X")
        y_standard = _standardize(y, "Y")
        if k:
            z_standard = _standardize(z, "Z")
            design = np.column_stack((np.ones(n), z_standard))
        else:
            design = np.ones((n, 1))
        singular_values = np.linalg.svd(design, compute_uv=False)
        if singular_values[-1] <= 0:
            raise _InvalidInput("Z_DESIGN_RANK_DEFICIENT_OR_ILL_CONDITIONED")
        condition_number = float(singular_values[0] / singular_values[-1])
        if not np.isfinite(condition_number) or condition_number > MAX_DESIGN_CONDITION:
            raise _InvalidInput("Z_DESIGN_RANK_DEFICIENT_OR_ILL_CONDITIONED")
        result["standardized_design_condition_number"] = condition_number
        responses = np.column_stack((x_standard, y_standard))
        coefficients, _, rank, _ = np.linalg.lstsq(design, responses, rcond=None)
        if rank != k + 1:
            raise _InvalidInput("Z_DESIGN_RANK_DEFICIENT_OR_ILL_CONDITIONED")
        residuals = responses - design @ coefficients
        residuals -= residuals.mean(axis=0)
        residual_rms = np.sqrt(np.mean(residuals * residuals, axis=0))
        if np.any(residual_rms <= MIN_RESIDUAL_RMS) or not np.isfinite(residual_rms).all():
            raise _InvalidInput("ZERO_OR_NEAR_ZERO_RESIDUAL_VARIANCE")
        residuals /= residual_rms
        partial_r = float(np.mean(residuals[:, 0] * residuals[:, 1]))
        if not np.isfinite(partial_r):
            raise _InvalidInput("NONFINITE_PARTIAL_CORRELATION")
        if abs(partial_r) >= 1 - PERFECT_CORRELATION_TOLERANCE:
            raise _InvalidInput("PERFECT_OR_NEAR_PERFECT_RESIDUAL_CORRELATION")

        standard_error = float(1 / np.sqrt(n - k - 3))
        fisher_r = float(np.arctanh(partial_r))
        interval = np.tanh(
            [fisher_r - critical_value * standard_error, fisher_r + critical_value * standard_error]
        )
        if interval[0] <= 0 <= interval[1]:
            closest_r = 0.0
        else:
            closest_r = float(min(abs(interval[0]), abs(interval[1])))
        estimate = float(-0.5 * np.log1p(-(partial_r * partial_r)))
        lower_bound = float(-0.5 * np.log1p(-(closest_r * closest_r)))
        if not np.isfinite([estimate, lower_bound, *interval]).all():
            raise _InvalidInput("UNCERTAINTY_NUMERIC_FAILURE")
        result.update(
            estimate_nats=estimate,
            lcb_nats=lower_bound,
            partial_r=partial_r,
            signed_r_interval=[float(value) for value in interval],
            fisher_standard_error=standard_error,
            fisher_critical_value=critical_value,
        )
        if lower_bound < gamma_nats:
            return deny("CMI_LCB_BELOW_THRESHOLD")
        result["status"] = "PASS_RESEARCH_ONLY"
        return result
    except _InvalidInput as exc:
        return deny(str(exc))
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError):
        return deny("NUMERICAL_RECONSTRUCTION_FAILURE")
