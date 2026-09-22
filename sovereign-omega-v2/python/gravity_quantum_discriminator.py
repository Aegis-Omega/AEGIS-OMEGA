"""Source-bound Kryhin–Sudhir D2 model-formula replay.

Implements the two-oscillator displacement cross-spectrum reported in
arXiv:2309.09105v2 Appendix E, Eq. (87), together with the high-Q
additional-zero approximation Eq. (89) and visibility condition Eq. (90).

This is model-formula replay only. No physical measurement is performed.
"""
from __future__ import annotations

import math

SOURCE_DOI = "10.1103/PhysRevLett.134.061501"
SOURCE_ARXIV = "2309.09105v2"


def denominator(Omega: float, omega: float, gamma: float) -> float:
    return (
        16.0 * (omega * omega - Omega * Omega) ** 2
        + 8.0 * gamma * gamma * (omega * omega + Omega * Omega)
        + gamma**4
    )


def sx1x2_eq87(
    Omega: float,
    *,
    omega: float,
    gamma: float,
    nbar: float,
    epsilon: float,
    mu: float = 1.0,
    d: float = 1.0,
) -> float:
    D = denominator(Omega, omega, gamma)
    classical = epsilon * omega / D
    thermal = (
        2.0
        * gamma
        * (2.0 * nbar + 1.0)
        * ((4.0 * omega * omega + gamma * gamma) ** 2 - 16.0 * Omega**4)
        / (D**2)
    )
    return 16.0 * mu * d * d * omega * (classical + thermal)


def eq89_zero_frequency(
    *, omega: float, gamma: float, nbar: float, epsilon: float
) -> float | None:
    if epsilon == 0.0:
        return None
    Q = omega / (2.0 * gamma)
    rad = (2.0 * nbar + 1.0) ** 2 - epsilon**2 / 4.0
    den = epsilon * Q - (2.0 * nbar + 1.0)
    if rad < 0.0 or den <= 0.0:
        return None
    ratio = (epsilon * Q + math.sqrt(rad)) / den
    return omega * math.sqrt(ratio) if ratio > 0.0 else None


def eq90_visible_zero_condition(
    *, omega: float, gamma: float, nbar: float, epsilon: float
) -> bool:
    Q = omega / (2.0 * gamma)
    return ((2.0 * nbar + 1.0) / Q) < epsilon < 2.0 * (2.0 * nbar + 1.0)


def bracket_zero(
    center: float,
    *,
    omega: float,
    gamma: float,
    nbar: float,
    epsilon: float,
    relative_window: float = 0.002,
    steps: int = 100_000,
) -> float | None:
    lo = center * (1.0 - relative_window)
    hi = center * (1.0 + relative_window)
    dx = (hi - lo) / steps
    x0 = lo
    f0 = sx1x2_eq87(
        x0, omega=omega, gamma=gamma, nbar=nbar, epsilon=epsilon
    )
    for index in range(1, steps + 1):
        x1 = lo + index * dx
        f1 = sx1x2_eq87(
            x1, omega=omega, gamma=gamma, nbar=nbar, epsilon=epsilon
        )
        if f0 == 0.0:
            return x0
        if f0 * f1 < 0.0:
            a, b, fa = x0, x1, f0
            for _ in range(100):
                mid = 0.5 * (a + b)
                fm = sx1x2_eq87(
                    mid,
                    omega=omega,
                    gamma=gamma,
                    nbar=nbar,
                    epsilon=epsilon,
                )
                if fa * fm <= 0.0:
                    b = mid
                else:
                    a, fa = mid, fm
            return 0.5 * (a + b)
        x0, f0 = x1, f1
    return None


def model_formula_receipt() -> dict[str, object]:
    omega = 2.0 * math.pi * 100.0
    gamma = 2.0 * math.pi * 0.001
    nbar = 0.0
    epsilon = 1.0

    approx = eq89_zero_frequency(
        omega=omega, gamma=gamma, nbar=nbar, epsilon=epsilon
    )
    if approx is None:
        raise RuntimeError("Eq.89 produced no additional zero")
    exact = bracket_zero(
        approx,
        omega=omega,
        gamma=gamma,
        nbar=nbar,
        epsilon=epsilon,
    )
    if exact is None:
        raise RuntimeError("Eq.87 additional zero was not bracketed")

    delta = max(0.05 * gamma, 1e-10 * omega)
    left = sx1x2_eq87(
        exact - delta,
        omega=omega,
        gamma=gamma,
        nbar=nbar,
        epsilon=epsilon,
    )
    right = sx1x2_eq87(
        exact + delta,
        omega=omega,
        gamma=gamma,
        nbar=nbar,
        epsilon=epsilon,
    )
    rel_error = abs(exact - approx) / exact
    phase_flip = left * right < 0.0

    return {
        "schema": "AEGIS_GQ_D2_MODEL_FORMULA_RECEIPT_V1",
        "source_doi": SOURCE_DOI,
        "source_arxiv": SOURCE_ARXIV,
        "equations": ("87", "89", "90"),
        "eq90_condition": eq90_visible_zero_condition(
            omega=omega, gamma=gamma, nbar=nbar, epsilon=epsilon
        ),
        "phase_flip": "PASS"
        if phase_flip and rel_error < 0.0001
        else "FAIL",
        "physical_measurement": "NOT_PERFORMED",
        "authority_effect": "NONE",
    }
