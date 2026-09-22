"""AEGIS Ω — D1 source-bound Gravity/Quantum scaling discriminator V1.

This module replays scaling exponents implied by formulas in Aziz & Howl,
Nature 646, 813–817 (2025), DOI 10.1038/s41586-025-09595-7.

The Aziz–Howl entanglement interpretation is disputed in subsequent preprints.
Accordingly this module verifies formula-level scaling only and grants no
physical-interpretation authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

SCALING_SIGNATURES = {
    "PERTURBATIVE_QG_NEWTONIAN_SMALL_DX": {
        "M": 2.0,
        "t": 1.0,
        "Delta_x": 2.0,
        "d": -3.0,
        "R": 0.0,
    },
    "AZIZ_HOWL_2025_EQ10_SMALL_DX": {
        "M": 6.0,
        "t": 2.0,
        "Delta_x": 2.0,
        "d": -4.0,
        "R": 2.0,
    },
}


@dataclass(frozen=True)
class ScalingPoint:
    M: float
    t: float
    Delta_x: float
    d: float
    R: float

    def __post_init__(self) -> None:
        if not all(
            math.isfinite(value) and value > 0.0
            for value in (self.M, self.t, self.Delta_x, self.d, self.R)
        ):
            raise ValueError("scaling coordinates must be finite and positive")


def perturbative_qg_proxy(point: ScalingPoint) -> float:
    return (
        point.M**2
        * point.t
        * point.Delta_x**2
        / point.d**3
    )


def aziz_howl_eq10_proxy(point: ScalingPoint) -> float:
    return (
        point.M**6
        * point.R**2
        * point.t**2
        * point.Delta_x**2
        / point.d**4
    )


def log_slope(
    fn: Callable[[ScalingPoint], float],
    point: ScalingPoint,
    axis: str,
    ratio: float = 2.0,
) -> float:
    if axis not in {"M", "t", "Delta_x", "d", "R"}:
        raise ValueError("unknown scaling axis")
    if not math.isfinite(ratio) or ratio <= 0.0 or ratio == 1.0:
        raise ValueError("invalid ratio")
    values = {
        "M": point.M,
        "t": point.t,
        "Delta_x": point.Delta_x,
        "d": point.d,
        "R": point.R,
    }
    values[axis] *= ratio
    shifted = ScalingPoint(**values)
    a = fn(point)
    b = fn(shifted)
    if a <= 0.0 or b <= 0.0:
        raise ValueError("proxy must remain positive")
    return math.log(b / a) / math.log(ratio)


def measured_signature(
    fn: Callable[[ScalingPoint], float],
    point: ScalingPoint,
) -> dict[str, float]:
    return {
        axis: log_slope(fn, point, axis)
        for axis in ("M", "t", "Delta_x", "d", "R")
    }


def classify_scaling(signature: dict[str, float]) -> dict[str, object]:
    required = {"M", "t", "Delta_x", "d", "R"}
    if set(signature) != required:
        raise ValueError("signature axes mismatch")
    distances = {
        model_id: sum(
            (signature[axis] - expected[axis]) ** 2
            for axis in required
        )
        for model_id, expected in SCALING_SIGNATURES.items()
    }
    best = min(distances, key=distances.get)
    return {
        "best_matching_registered_formula_signature": best,
        "distances": distances,
        "claim_scope": "FORMULA_SCALING_COMPARISON_ONLY",
        "aziz_howl_interpretation": "CONTESTED",
        "authority_effect": "NONE",
    }
