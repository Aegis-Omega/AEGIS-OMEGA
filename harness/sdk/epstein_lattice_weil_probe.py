"""Finite Epstein/Weil lattice controls for the AEGIS RH research lane.

This module is intentionally diagnostic. It compares two completed degree-two
objects with discriminant -20 and therefore the same conductor/gamma factor:

* the principal Epstein zeta of Q(x,y)=x^2+5y^2 (normalized by its two units),
  which is not an Euler product; and
* the Dedekind/class-sum control zeta(s)L(s,chi_-20), which is an Euler product.

The arithmetic diagnostic is the Dirichlet series of -F'/F. Euler products
have support only on prime powers. The principal D=-20 Epstein zeta has an
explicit composite leakage already at n=6.

The spectral probe uses the same moment-zero trigonometric/Galerkin family as
research/rh/krein_dual_beyond_log2.py and evaluates a finite generalized
eigenproblem. Floating point spectral output has no proof authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import scipy.linalg as la
import scipy.special as sp

AUTHORITY = "T1_NUMERICAL_DIAGNOSTIC"
DISCRIMINANT = -20


def chi_minus4(n: int) -> int:
    n = int(n)
    if n <= 0:
        raise ValueError("n must be positive")
    if n % 2 == 0:
        return 0
    return 1 if n % 4 == 1 else -1


def chi_5(n: int) -> int:
    n = int(n)
    if n <= 0:
        raise ValueError("n must be positive")
    residue = n % 5
    if residue == 0:
        return 0
    return 1 if residue in (1, 4) else -1


def chi_minus20(n: int) -> int:
    """Primitive quadratic character for fundamental discriminant -20."""
    return chi_minus4(n) * chi_5(n)


def _divisors(n: int) -> tuple[int, ...]:
    small: list[int] = []
    large: list[int] = []
    root = math.isqrt(n)
    for d in range(1, root + 1):
        if n % d == 0:
            small.append(d)
            if d * d != n:
                large.append(n // d)
    return tuple(small + large[::-1])


def d20_euler_coefficients(max_n: int) -> np.ndarray:
    """Coefficients of zeta(s)L(s,chi_-20), normalized with a(1)=1."""
    if max_n < 1:
        raise ValueError("max_n must be >= 1")
    out = np.zeros(max_n + 1, dtype=float)
    for n in range(1, max_n + 1):
        out[n] = float(sum(chi_minus20(d) for d in _divisors(n)))
    return out


def d20_principal_coefficients(max_n: int) -> np.ndarray:
    """Coefficients of E_{x^2+5y^2}(s)/2, normalized with a(1)=1."""
    if max_n < 1:
        raise ValueError("max_n must be >= 1")
    counts = np.zeros(max_n + 1, dtype=np.int64)
    x_bound = math.isqrt(max_n)
    y_bound = math.isqrt(max_n // 5) if max_n >= 5 else 0
    for x in range(-x_bound, x_bound + 1):
        x2 = x * x
        for y in range(-y_bound, y_bound + 1):
            value = x2 + 5 * y * y
            if 1 <= value <= max_n:
                counts[value] += 1
    return counts.astype(float) / 2.0


def d20_companion_coefficients(max_n: int) -> np.ndarray:
    """Coefficients of L(s,chi_-4)L(s,chi_5)."""
    if max_n < 1:
        raise ValueError("max_n must be >= 1")
    out = np.zeros(max_n + 1, dtype=float)
    for n in range(1, max_n + 1):
        out[n] = float(
            sum(chi_minus4(d) * chi_5(n // d) for d in _divisors(n))
        )
    return out


def generalized_log_derivative_coefficients(a: np.ndarray) -> np.ndarray:
    """Return Lambda_F for -F'/F = sum Lambda_F(n)n^{-s}.

    Input is a finite coefficient prefix of F(s)=sum a(n)n^{-s}, with a(1)=1.
    The Dirichlet-convolution recurrence is exact on the supplied prefix.
    """
    a = np.asarray(a, dtype=float)
    if a.ndim != 1 or a.size < 2 or not math.isclose(float(a[1]), 1.0):
        raise ValueError("a must be one-dimensional with a(1)=1")
    out = np.zeros_like(a)
    for n in range(2, a.size):
        value = float(a[n]) * math.log(n)
        for d in _divisors(n):
            if 1 < d < n:
                value -= float(out[d]) * float(a[n // d])
        out[n] = value
    return out


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def is_prime_power(n: int) -> bool:
    n = int(n)
    if n < 2:
        return False
    p = None
    for candidate in range(2, math.isqrt(n) + 1):
        if n % candidate == 0:
            p = candidate
            break
    if p is None:
        return True
    m = n
    while m % p == 0:
        m //= p
    return m == 1 and is_prime(p)


def arithmetic_support_certificate(
    a: np.ndarray, *, tolerance: float = 1e-12
) -> dict[str, object]:
    lam = generalized_log_derivative_coefficients(a)
    support = tuple(
        int(n) for n in range(2, lam.size) if abs(float(lam[n])) > tolerance
    )
    leakage = tuple(n for n in support if not is_prime_power(n))
    return {
        "support": support,
        "non_prime_power_support": leakage,
        "prime_power_only": not leakage,
        "lambda_values": {n: float(lam[n]) for n in support},
    }


@dataclass(frozen=True)
class EpsteinWeilProbeConfig:
    support_length: float = 3.5
    basis_dim: int = 24
    t_bound: float = 800.0
    dt: float = 0.04
    chunk_size: int = 4096

    def __post_init__(self) -> None:
        if not math.isfinite(self.support_length) or self.support_length <= 0:
            raise ValueError("support_length must be finite and positive")
        if self.basis_dim < 2:
            raise ValueError("basis_dim must be >= 2")
        if not math.isfinite(self.t_bound) or self.t_bound <= 0:
            raise ValueError("t_bound must be finite and positive")
        if not math.isfinite(self.dt) or self.dt <= 0:
            raise ValueError("dt must be finite and positive")
        if self.chunk_size < 32:
            raise ValueError("chunk_size must be >= 32")


def _mode_coefficients(L: float, k: int) -> dict[int, float]:
    alpha = math.pi / L
    m1, m2 = k - 1, k + 1
    return {
        m1: 0.5 * (0.25 + (m1 * alpha) ** 2),
        m2: -0.5 * (0.25 + (m2 * alpha) ** 2),
    }


def exact_gram_matrix(L: float, basis_dim: int) -> np.ndarray:
    """Exact-in-form Gram matrix for the trigonometric moment-zero basis."""
    modes = [_mode_coefficients(L, k) for k in range(1, basis_dim + 1)]
    G = np.zeros((basis_dim, basis_dim), dtype=float)
    for i, left in enumerate(modes):
        for j in range(i, basis_dim):
            right = modes[j]
            value = 0.0
            for m in set(left).intersection(right):
                cosine_norm = L if m == 0 else L / 2.0
                value += left[m] * right[m] * cosine_norm
            G[i, j] = value
            G[j, i] = value
    return G


def _integral_exp_minus(c: np.ndarray, L: float) -> np.ndarray:
    return L * np.exp(-0.5j * c * L) * np.sinc(c * L / (2.0 * math.pi))


def basis_fourier(t: np.ndarray, L: float, basis_dim: int) -> np.ndarray:
    t = np.asarray(t, dtype=float)
    F = np.empty((basis_dim, t.size), dtype=np.complex128)
    alpha = math.pi / L
    for row, k in enumerate(range(1, basis_dim + 1)):
        terms = _mode_coefficients(L, k)
        value = np.zeros(t.size, dtype=np.complex128)
        for mode, coefficient in terms.items():
            beta = mode * alpha
            cosine_transform = 0.5 * (
                _integral_exp_minus(t - beta, L)
                + _integral_exp_minus(t + beta, L)
            )
            value += coefficient * cosine_transform
        F[row] = value
    return F


def completed_epstein_symbol(
    t: np.ndarray,
    *,
    support_length: float,
    generalized_lambda: np.ndarray,
    discriminant: int = DISCRIMINANT,
) -> np.ndarray:
    """Critical-line log-derivative symbol for the completed degree-two object.

    Completion convention (constant multiples ignored):
      (sqrt(|D|)/(2*pi))^s Gamma(s) F(s).
    """
    t = np.asarray(t, dtype=float)
    conductor_scale = math.sqrt(abs(discriminant)) / (2.0 * math.pi)
    symbol = (
        2.0 * np.real(sp.digamma(0.5 + 1j * t))
        + 2.0 * math.log(conductor_scale)
    )
    cutoff = min(
        generalized_lambda.size - 1,
        int(math.ceil(math.exp(support_length))),
    )
    for n in range(2, cutoff + 1):
        lam = float(generalized_lambda[n])
        if lam == 0.0 or not math.log(n) < support_length:
            continue
        symbol -= 2.0 * lam / math.sqrt(n) * np.cos(t * math.log(n))
    return symbol


def assemble_quadratic_matrix(
    config: EpsteinWeilProbeConfig,
    generalized_lambda: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    L = config.support_length
    dim = config.basis_dim
    M = np.zeros((dim, dim), dtype=float)
    total = int(math.ceil(config.t_bound / config.dt))
    for start in range(0, total, config.chunk_size):
        stop = min(total, start + config.chunk_size)
        t = (np.arange(start, stop, dtype=float) + 0.5) * config.dt
        F = basis_fourier(t, L, dim)
        S = completed_epstein_symbol(
            t,
            support_length=L,
            generalized_lambda=generalized_lambda,
        )
        weighted = F * (S * config.dt / math.pi)
        M += (weighted @ F.conj().T).real
    M = 0.5 * (M + M.T)
    G = exact_gram_matrix(L, dim)
    return M, G


def solve_minimum(
    config: EpsteinWeilProbeConfig,
    generalized_lambda: np.ndarray,
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    M, G = assemble_quadratic_matrix(config, generalized_lambda)
    eigenvalues, eigenvectors = la.eigh(M, G, check_finite=True)
    vector = np.asarray(eigenvectors[:, 0], dtype=float)
    vector /= math.sqrt(float(vector @ G @ vector))
    return float(eigenvalues[0]), vector, M, G


def run_d20_same_discriminant_control(
    config: EpsteinWeilProbeConfig = EpsteinWeilProbeConfig(),
) -> dict[str, object]:
    max_n = max(64, int(math.ceil(math.exp(config.support_length))) + 2)
    principal_a = d20_principal_coefficients(max_n)
    euler_a = d20_euler_coefficients(max_n)
    principal_lambda = generalized_log_derivative_coefficients(principal_a)
    euler_lambda = generalized_log_derivative_coefficients(euler_a)

    p_min, witness, _, _ = solve_minimum(config, principal_lambda)
    e_min, _, e_M, _ = solve_minimum(config, euler_lambda)
    witness_on_euler = float(witness @ e_M @ witness)

    p_cert = arithmetic_support_certificate(principal_a)
    e_cert = arithmetic_support_certificate(euler_a)

    return {
        "schema_version": "1.0.0",
        "authority": AUTHORITY,
        "config": asdict(config),
        "discriminant": DISCRIMINANT,
        "principal_form": "x^2 + 5 y^2",
        "same_archimedean_factor": True,
        "same_conductor": True,
        "principal_lambda_min": p_min,
        "euler_classsum_lambda_min": e_min,
        "principal_minimizer_on_euler_classsum": witness_on_euler,
        "principal_arithmetic": p_cert,
        "euler_classsum_arithmetic": e_cert,
        "n6_leakage_value": float(principal_lambda[6]),
        "n6_expected_value": float(2.0 * math.log(6.0)),
        "principal_witness": tuple(float(x) for x in witness),
        "proof_authority": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "non_claims": (
            "FINITE_GALERKIN_NEGATIVITY_IS_NOT_A_GLOBAL_OPERATOR_THEOREM",
            "FLOAT64_POSITIVITY_OF_THE_CONTROL_IS_NOT_A_PROOF_OF_GLOBAL_POSITIVITY",
            "NO_RH_AUTHORITY",
        ),
    }


D20_FIXED_WITNESS_MODES = (4, 6, 8, 10, 12, 16, 18)
D20_FIXED_WITNESS_COEFFICIENTS = (22, 10, 6, 3, 2, -2, -1)


def evaluate_d20_fixed_integer_witness(
    config: EpsteinWeilProbeConfig = EpsteinWeilProbeConfig(),
) -> dict[str, object]:
    """Evaluate the committed optimizer-free D=-20 sign witness.

    The witness uses only seven even basis modes and integer coefficients:
      modes = (4, 6, 8, 10, 12, 16, 18)
      coeff = (22, 10, 6, 3, 2, -2, -1)

    Rayleigh quotients are scale invariant, so the integer vector is the
    canonical representation.  The calculation is still a finite floating-
    point Galerkin diagnostic; fixing the vector removes eigensolver dependence
    from the sign witness but does not supply interval/infinite-tail authority.
    """
    if config.basis_dim < max(D20_FIXED_WITNESS_MODES):
        raise ValueError("basis_dim must include all fixed witness modes")

    max_n = max(64, int(math.ceil(math.exp(config.support_length))) + 2)
    principal_lambda = generalized_log_derivative_coefficients(
        d20_principal_coefficients(max_n)
    )
    euler_lambda = generalized_log_derivative_coefficients(
        d20_euler_coefficients(max_n)
    )
    principal_M, G = assemble_quadratic_matrix(config, principal_lambda)
    euler_M, _ = assemble_quadratic_matrix(config, euler_lambda)

    indices = np.asarray([mode - 1 for mode in D20_FIXED_WITNESS_MODES], dtype=int)
    coeff = np.asarray(D20_FIXED_WITNESS_COEFFICIENTS, dtype=float)
    principal_block = principal_M[np.ix_(indices, indices)]
    euler_block = euler_M[np.ix_(indices, indices)]
    gram_block = G[np.ix_(indices, indices)]

    norm_sq = float(coeff @ gram_block @ coeff)
    if not math.isfinite(norm_sq) or norm_sq <= 0.0:
        raise RuntimeError("fixed witness Gram norm is not positive")

    principal_q = float(coeff @ principal_block @ coeff) / norm_sq
    euler_q = float(coeff @ euler_block @ coeff) / norm_sq
    return {
        "schema_version": "1.0.0",
        "authority": AUTHORITY,
        "discriminant": DISCRIMINANT,
        "modes": D20_FIXED_WITNESS_MODES,
        "integer_coefficients": D20_FIXED_WITNESS_COEFFICIENTS,
        "gram_norm_squared": norm_sq,
        "principal_rayleigh": principal_q,
        "euler_classsum_rayleigh": euler_q,
        "optimizer_used_for_evaluation": False,
        "principal_negative_observed": principal_q < 0.0,
        "same_witness_euler_positive_observed": euler_q > 0.0,
        "proof_authority": False,
        "global_weil_positivity_proven": False,
        "rh_proven": False,
        "open_obligations": (
            "INTERVAL_CERTIFY_FIXED_WITNESS_FINITE_INTEGRAL",
            "CERTIFY_ARCHIMEDEAN_TAIL_FOR_FIXED_WITNESS",
            "FORMULA_TO_TARGET_WEIL_FORM_IDENTITY_NOT_MACHINE_FORMALIZED",
        ),
    }
