"""Independent-route consistency check for the finite Galerkin formula.

This module intentionally does *not* provide theorem authority. It evaluates
the same bounded finite matrix through a second numerical route based on the
hypergeometric/digamma/Lerch closed forms used by the released three-route
verification script for arXiv:2607.02828v3, then checks that each point value
lands inside the corresponding rigorous Arb enclosure produced by
``guinand_weil_arb``.

The comparison is useful falsification evidence, but the routes share the same
mathematical derivation and upstream research target. Therefore this module
never claims statistical/epistemic independence and never sets
``galerkin_semantics_verified``, global Weil positivity, or RH to true.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import mpmath as mp

from harness.sdk.guinand_weil_arb import ArbGalerkinSpecV1, _build_cutoff_free_matrix
from harness.sdk.sovereign_execution import canonical_hash

RECEIPT_KIND = "AEGIS_GUINAND_WEIL_CROSSCHECK_RECEIPT_V1"
PROOF_SEMANTICS = "NONRIGOROUS_SECOND_ROUTE_CONSISTENCY_EVIDENCE_ONLY"
ROUTE_ID = "MPMATH_HYPERGEOMETRIC_DIGAMMA_LERCH_FULL_Q_V1"
ROUTE_PROVENANCE = {
    "paper": "arXiv:2607.02828v3",
    "reference_three_route_script_blob": "90576ea92835fff2f9dd2e3aa63ad99829bd17e5",
    "mpmath_expected": "1.3.0",
}
MIN_DECIMAL_DIGITS = 50
MAX_DECIMAL_DIGITS = 500


class GuinandWeilCrosscheckError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ClosedFormCrosscheckV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    arb_matrix_root: str
    route_id: str
    route_provenance_root: str
    decimal_digits: int
    mpmath_version: str
    entry_count: int
    mismatch_count: int
    all_entries_agree: bool
    valid: bool
    comparison_root: str
    route_independence_claimed: bool
    galerkin_semantics_verified: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_GUINAND_WEIL_CROSSCHECK_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def _prime_powers_point(c: int) -> tuple[tuple[int, int], ...]:
    """Independent exact enumeration route; intentionally does not reuse Arb helper."""
    primes: list[int] = []
    for x in range(2, c + 1):
        if all(x % p for p in primes if p * p <= x):
            primes.append(x)
    out: list[tuple[int, int]] = []
    for p in primes:
        q = p
        while q <= c:
            out.append((q, p))
            if q > c // p:
                break
            q *= p
    return tuple(sorted(out))


def _closed_form_full_matrix(spec: ArbGalerkinSpecV1, decimal_digits: int) -> list[list[mp.mpf]]:
    mp.mp.dps = decimal_digits
    L = mp.log(spec.c)
    z = mp.e ** (-2 * L)
    pi = mp.pi
    gamma = mp.euler
    pp = _prime_powers_point(spec.c)

    def a_n(n: int):
        return mp.mpf(1) / 4 + pi * 1j * n / L

    def F(n: int):
        a = a_n(n)
        return mp.hyp2f1(1, a, a + 1, z)

    def alpha_L(n: int):
        a = a_n(n)
        return (
            mp.e ** (-L / 2) * mp.im((2 * L / (L + 4 * pi * 1j * n)) * F(n))
            + mp.mpf(1) / 2 * mp.im(mp.digamma(a))
        ) / pi

    def beta_L(n: int):
        a = a_n(n)
        t1 = -L * mp.e ** (-L / 2) * mp.im((2 * L / (4 * pi * n - 1j * L)) * F(n))
        t2 = -(mp.e ** (-L / 2) / 4) * mp.re(mp.lerchphi(z, 2, a))
        t3 = mp.mpf(1) / 4 * mp.re(mp.polygamma(1, a))
        return (t1 + t2 + t3) / L

    def c_w():
        u = mp.e ** (L / 2)
        return (
            mp.mpf(1) / 2 * mp.log((u - 1) / (u + 1))
            + mp.atan(u)
            - pi / 4
            + gamma / 2
            + mp.mpf(1) / 2 * mp.log(8 * pi)
        )

    F0 = mp.hyp2f1(mp.mpf(1) / 4, 1, mp.mpf(5) / 4, z)
    psi_quarter = mp.digamma(mp.mpf(1) / 4)

    def gamma_L(n: int):
        a = a_n(n)
        return (
            -mp.e ** (-L / 2) * mp.re((2 * L / (L + 4 * pi * 1j * n)) * F(n))
            + 2 * mp.e ** (-L / 2) * F0
            - mp.mpf(1) / 2 * (mp.re(mp.digamma(a)) - psi_quarter)
            + c_w()
        )

    def psipr(m: int):
        return -(1 / pi) * mp.fsum(
            mp.log(p) / mp.sqrt(q) * mp.sin(2 * pi * m * (1 - mp.log(q) / L))
            for q, p in pp
        )

    def psiprd(m: int):
        return -2 * mp.fsum(
            mp.log(p) / mp.sqrt(q)
            * (1 - mp.log(q) / L)
            * mp.cos(2 * pi * m * (1 - mp.log(q) / L))
            for q, p in pp
        )

    indices = tuple(range(-spec.N, spec.N + 1))
    P0 = {m: alpha_L(m) + psipr(m) for m in indices}
    P0d = {m: -2 * (gamma_L(m) - beta_L(m)) + psiprd(m) for m in indices}

    def Cm(m: int):
        return mp.sinh(L / 4) / mp.sqrt(L) / (mp.mpf(1) / 4 + (2 * pi * m / L) ** 2)

    def Sm(m: int):
        return (
            4 * pi * mp.sinh(L / 4) / (L * mp.sqrt(L))
            * m
            / (mp.mpf(1) / 4 + (2 * pi * m / L) ** 2)
        )

    C = {m: Cm(m) for m in indices}
    S = {m: Sm(m) for m in indices}

    def Q(m: int, n: int):
        pole = 2 * (C[m] * C[n] - S[m] * S[n])
        if m == n:
            return mp.re(P0d[n] + pole)
        return mp.re((P0[m] - P0[n]) / (m - n) + pole)

    dim = len(indices)
    matrix = [[mp.mpf(0) for _ in range(dim)] for _ in range(dim)]
    for i, m in enumerate(indices):
        for j, n in enumerate(indices):
            matrix[i][j] = mp.mpf(Q(m, n))
    return matrix


def _arb_point_enclosure(ball, decimal_digits: int) -> tuple[mp.mpf, mp.mpf]:
    digits = max(decimal_digits + 20, 80)
    mid = mp.mpf(ball.mid().str(digits, radius=False))
    rad = mp.mpf(ball.rad().str(digits, radius=False))
    return mid, rad


def verify_closed_form_crosscheck(
    spec: ArbGalerkinSpecV1,
    *,
    decimal_digits: int = 70,
) -> ClosedFormCrosscheckV1:
    if isinstance(decimal_digits, bool) or not isinstance(decimal_digits, int):
        raise GuinandWeilCrosscheckError("DECIMAL_DIGITS_INVALID")
    if not (MIN_DECIMAL_DIGITS <= decimal_digits <= MAX_DECIMAL_DIGITS):
        raise GuinandWeilCrosscheckError("DECIMAL_DIGITS_OUT_OF_RANGE")

    arb_matrix, dim, arb_matrix_root = _build_cutoff_free_matrix(spec)
    point_matrix = _closed_form_full_matrix(spec, decimal_digits)
    slack = mp.power(10, -(decimal_digits - 12))
    transcript: list[dict[str, object]] = []
    mismatch_count = 0

    for i in range(dim):
        for j in range(i, dim):
            mid, rad = _arb_point_enclosure(arb_matrix[i, j], decimal_digits)
            value = point_matrix[i][j]
            difference = abs(value - mid)
            agrees = difference <= rad + slack
            if not agrees:
                mismatch_count += 1
            transcript.append(
                {
                    "i": i,
                    "j": j,
                    "point": mp.nstr(value, decimal_digits),
                    "arb_mid": mp.nstr(mid, decimal_digits),
                    "arb_rad": mp.nstr(rad, decimal_digits),
                    "abs_difference": mp.nstr(difference, decimal_digits),
                    "agrees": agrees,
                }
            )

    comparison_root = canonical_hash(
        "AEGIS_GUINAND_WEIL_CROSSCHECK_COMPARISON_ROOT_V1",
        {
            "spec_root": spec.root,
            "arb_matrix_root": arb_matrix_root,
            "route_id": ROUTE_ID,
            "decimal_digits": decimal_digits,
            "entries": transcript,
        },
    )
    entry_count = dim * (dim + 1) // 2
    all_entries_agree = mismatch_count == 0 and len(transcript) == entry_count
    provenance_root = canonical_hash("AEGIS_GUINAND_WEIL_CROSSCHECK_PROVENANCE_V1", ROUTE_PROVENANCE)

    return ClosedFormCrosscheckV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=spec.root,
        arb_matrix_root=arb_matrix_root,
        route_id=ROUTE_ID,
        route_provenance_root=provenance_root,
        decimal_digits=decimal_digits,
        mpmath_version=getattr(mp, "__version__", "unknown"),
        entry_count=entry_count,
        mismatch_count=mismatch_count,
        all_entries_agree=all_entries_agree,
        valid=all_entries_agree,
        comparison_root=comparison_root,
        route_independence_claimed=False,
        galerkin_semantics_verified=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=(
            "CROSSCHECK_IS_NOT_AN_INDEPENDENT_THEOREM_PROOF",
            "FORMULA_TO_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_FORMALIZED",
            "FINITE_BAND_DOES_NOT_ESTABLISH_GLOBAL_WEIL_POSITIVITY",
        ),
    )
