"""Rigorous finite cutoff-free Galerkin evaluator for AEGIS Ω.

This module evaluates the finite Connes–van Suijlekom / CCM cutoff-free
matrix formula with Arb ball arithmetic and certifies its finite inertia by
interval LDL^T.  It deliberately separates two claims:

1. the fixed formula was evaluated with rigorous interval enclosures; and
2. the formula is the Weil/Galerkin operator appearing in the mathematical
   theorem.

Only (1) is established by this software.  The theorem identity remains a
separate machine-proof obligation, so ``galerkin_semantics_verified`` stays
false in v1 even when every matrix entry and pivot is rigorously enclosed.

The finite formula follows the closed-form assembly documented in
arXiv:2607.02828v3 and its released Arb reproducibility package.  Citations and
source hashes are provenance only, never mathematical authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Optional

import flint
from flint import acb, arb, arb_mat, ctx

from harness.sdk.sovereign_execution import canonical_hash

SPEC_KIND = "AEGIS_ARB_GALERKIN_SPEC_V1"
RECEIPT_KIND = "AEGIS_ARB_GALERKIN_RECEIPT_V1"
PROOF_SEMANTICS = "RIGOROUS_FINITE_FORMULA_EVALUATION_NOT_GLOBAL_WEIL_PROOF"
FORMULA_ID = "GUINAND_WEIL_CUTOFF_FREE_GALERKIN_FORMULA_ARXIV_2607_02828_V3"
FORMULA_PROVENANCE = {
    "paper": "arXiv:2607.02828v3",
    "reference_arb_script_blob": "cec0ed724b00c7a4643bf86b66663b8b405a5585",
    "python_flint_expected": "0.8.0",
}

MIN_PREC_BITS = 128
MAX_PREC_BITS = 32768
MAX_BAND = 256
MAX_CUTOFF = 100000


class ArbGalerkinError(ValueError):
    """Fail-closed structural or arithmetic error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ArbGalerkinSpecV1:
    c: int
    N: int
    prec_bits: int
    spec_kind: str = SPEC_KIND
    formula_id: str = FORMULA_ID

    def __post_init__(self) -> None:
        if self.spec_kind != SPEC_KIND:
            raise ArbGalerkinError("SPEC_KIND_MISMATCH")
        if self.formula_id != FORMULA_ID:
            raise ArbGalerkinError("FORMULA_ID_MISMATCH")
        if isinstance(self.c, bool) or not isinstance(self.c, int) or not (2 <= self.c <= MAX_CUTOFF):
            raise ArbGalerkinError("CUTOFF_INVALID")
        if isinstance(self.N, bool) or not isinstance(self.N, int) or not (0 <= self.N <= MAX_BAND):
            raise ArbGalerkinError("BAND_INVALID")
        if isinstance(self.prec_bits, bool) or not isinstance(self.prec_bits, int):
            raise ArbGalerkinError("PRECISION_INVALID")
        if self.prec_bits < MIN_PREC_BITS:
            raise ArbGalerkinError("PRECISION_TOO_LOW")
        if self.prec_bits > MAX_PREC_BITS:
            raise ArbGalerkinError("PRECISION_TOO_HIGH")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_ARB_GALERKIN_SPEC_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class ArbGalerkinVerificationV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    formula_id: str
    formula_provenance_root: str
    backend: str
    c: int
    N: int
    dimension: int
    prec_bits: int
    valid: bool
    status: str
    cutoff_free_entry_enclosures_verified: bool
    interval_inertia_verified: bool
    n_positive: int
    n_negative: int
    undetermined_pivot: Optional[int]
    finite_matrix_positive_definite_verified: bool
    finite_matrix_psd_verified: bool
    matrix_root: str
    pivot_root: str
    galerkin_semantics_verified: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_ARB_GALERKIN_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def prime_powers_up_to(c: int) -> tuple[tuple[int, int], ...]:
    """Return all ``(q, p)`` with q=p^a <= c, using exact integer arithmetic."""
    if isinstance(c, bool) or not isinstance(c, int) or c < 2:
        raise ArbGalerkinError("CUTOFF_INVALID")
    sieve = [True] * (c + 1)
    sieve[0] = sieve[1] = False
    primes: list[int] = []
    for p in range(2, c + 1):
        if not sieve[p]:
            continue
        primes.append(p)
        if p * p <= c:
            for multiple in range(p * p, c + 1, p):
                sieve[multiple] = False
    powers: list[tuple[int, int]] = []
    for p in primes:
        q = p
        while q <= c:
            powers.append((q, p))
            if q > c // p:
                break
            q *= p
    return tuple(sorted(powers))


def _trigamma(z: acb) -> acb:
    return z.polygamma(acb(1))


def _geometric_remainders(n: int, L: arb, prec_bits: int) -> tuple[arb, arb, arb, arb]:
    """Rigorous auxiliary sums with a bounded, explicit geometric tail."""
    pi = arb.pi()
    omega = 2 * pi * n / L
    omega_sq = omega * omega
    sums = [arb(0), arb(0), arb(0), arb(0)]
    threshold = arb(2) ** (-(prec_bits + 24))
    max_terms = max(96, 2 * prec_bits + 64)
    stop_k: Optional[int] = None

    for k in range(max_terms):
        ck = arb(2 * k) + arb("0.5")
        exp_term = (-ck * L).exp()
        denom = ck * ck + omega_sq
        sums[0] += exp_term / denom
        if n != 0:
            sums[1] += exp_term * omega_sq / (ck * denom)
        sums[2] += exp_term * ck / denom
        sums[3] += exp_term * (ck * ck - omega_sq) / (denom * denom)
        if k > 2 and exp_term < threshold:
            stop_k = k
            break

    if stop_k is None:
        raise ArbGalerkinError("GEOMETRIC_SERIES_BOUND_EXCEEDED")

    next_ck = arb(2 * (stop_k + 1)) + arb("0.5")
    geometric_den = 1 - (-2 * L).exp()
    tail = (-next_ck * L).exp() / geometric_den
    radius = arb(4) * tail
    return tuple(value + arb(0, radius) for value in sums)  # type: ignore[return-value]


def _closed_form_sequences(spec: ArbGalerkinSpecV1) -> tuple[list[arb], list[arb], list[arb], arb]:
    ctx.prec = spec.prec_bits
    L = arb(spec.c).log()
    pi = arb.pi()
    quarter = arb("0.25")
    psi_quarter = quarter.digamma()
    S = [arb(0) for _ in range(spec.N + 1)]
    CC = [arb(0) for _ in range(spec.N + 1)]
    XC = [arb(0) for _ in range(spec.N + 1)]

    for n in range(spec.N + 1):
        omega = 2 * pi * n / L
        z = acb(quarter, pi * n / L)
        psi = z.digamma()
        psi1 = _trigamma(z)
        g_s, g_cc, g_x1, g_x2 = _geometric_remainders(n, L, spec.prec_bits)
        if n != 0:
            S[n] = arb("0.5") * psi.imag - omega * g_s
            CC[n] = -arb("0.5") * (psi.real - psi_quarter) + g_cc
        XC[n] = arb("0.25") * psi1.real - L * g_x1 - g_x2
    return S, CC, XC, L


def _J(L: arb) -> arb:
    u = (L / 2).exp()
    return -2 * (u + 1).log() + (u * u + 1).log() + 2 * u.atan() + arb(2).log() - arb.pi() / 2


def _kappa(L: arb) -> arb:
    e_l = L.exp()
    return (4 * arb.pi() * (e_l - 1) / (e_l + 1)).log() + arb.const_euler()


def _ball_repr(value: arb, prec_bits: int) -> dict[str, str]:
    digits = max(40, int(math.ceil(prec_bits * math.log10(2))) + 8)
    return {
        "mid": value.mid().str(digits, radius=False),
        "rad": value.rad().str(digits, radius=False),
    }


def _matrix_root(matrix: arb_mat, dim: int, spec: ArbGalerkinSpecV1) -> str:
    upper = []
    for i in range(dim):
        for j in range(i, dim):
            upper.append({"i": i, "j": j, "ball": _ball_repr(matrix[i, j], spec.prec_bits)})
    return canonical_hash(
        "AEGIS_ARB_GALERKIN_MATRIX_ROOT_V1",
        {
            "spec_root": spec.root,
            "backend": f"python-flint/{getattr(flint, '__version__', 'unknown')}",
            "upper_triangle": upper,
        },
    )


def _build_cutoff_free_matrix(spec: ArbGalerkinSpecV1) -> tuple[arb_mat, int, str]:
    """Evaluate the cutoff-free finite matrix formula as rigorous Arb balls."""
    ctx.prec = spec.prec_bits
    S, CC, XC, L = _closed_form_sequences(spec)
    pi = arb.pi()
    sixteen_pi_sq = 16 * pi * pi
    L_sq = L * L
    pole_prefactor = 32 * L * (L / 4).sinh() ** 2
    kappa = _kappa(L)
    j_const = _J(L)

    prime_data = prime_powers_up_to(spec.c)
    weights = [arb(p).log() * (arb(q) ** arb("-0.5")) for q, p in prime_data]
    positions = [arb(q).log() for q, _ in prime_data]

    def signed_s(index: int) -> arb:
        return S[index] if index >= 0 else -S[-index]

    dim = 2 * spec.N + 1
    matrix = arb_mat(dim, dim)
    for i in range(dim):
        n = i - spec.N
        for j in range(i, dim):
            m = j - spec.N

            numerator = L_sq - sixteen_pi_sq * m * n
            denominator = (L_sq + sixteen_pi_sq * m * m) * (L_sq + sixteen_pi_sq * n * n)
            w02 = pole_prefactor * numerator / denominator

            if n == m:
                w_real = kappa + 2 * CC[abs(n)] + j_const - (arb(2) / L) * XC[abs(n)]
            else:
                w_real = (signed_s(m) - signed_s(n)) / (pi * (n - m))

            w_prime = arb(0)
            for weight, y in zip(weights, positions):
                if n == m:
                    kernel = 2 * (1 - y / L) * (2 * pi * n * y / L).cos()
                else:
                    kernel = (
                        (2 * pi * m * y / L).sin() - (2 * pi * n * y / L).sin()
                    ) / (pi * (n - m))
                w_prime += weight * kernel

            value = w02 - w_real - w_prime
            matrix[i, j] = value
            matrix[j, i] = value

    return matrix, dim, _matrix_root(matrix, dim, spec)


def _certify_interval_inertia(matrix: arb_mat, dim: int, spec: ArbGalerkinSpecV1) -> tuple[int, int, Optional[int], str]:
    """Interval LDL^T; every strictly signed pivot is a proved inertia step."""
    diagonal: list[Optional[arb]] = [None] * dim
    lower = [[arb(0) for _ in range(dim)] for _ in range(dim)]
    transcript: list[dict[str, object]] = []
    n_positive = 0
    n_negative = 0
    undetermined: Optional[int] = None

    for i in range(dim):
        pivot = matrix[i, i]
        for k in range(i):
            assert diagonal[k] is not None
            pivot = pivot - lower[i][k] * lower[i][k] * diagonal[k]
        diagonal[i] = pivot

        if pivot > 0:
            sign = "+"
            n_positive += 1
        elif pivot < 0:
            sign = "-"
            n_negative += 1
        else:
            undetermined = i
            transcript.append({"index": i, "sign": "?", "ball": _ball_repr(pivot, spec.prec_bits)})
            break

        transcript.append({"index": i, "sign": sign, "ball": _ball_repr(pivot, spec.prec_bits)})
        for row in range(i + 1, dim):
            value = matrix[row, i]
            for k in range(i):
                assert diagonal[k] is not None
                value = value - lower[row][k] * lower[i][k] * diagonal[k]
            lower[row][i] = value / pivot

    pivot_root = canonical_hash(
        "AEGIS_ARB_GALERKIN_PIVOT_TRANSCRIPT_ROOT_V1",
        {"spec_root": spec.root, "transcript": transcript},
    )
    return n_positive, n_negative, undetermined, pivot_root


def verify_cutoff_free_galerkin(spec: ArbGalerkinSpecV1) -> ArbGalerkinVerificationV1:
    """Recompute the matrix and certify finite inertia; never promote to RH."""
    matrix, dim, matrix_root = _build_cutoff_free_matrix(spec)
    n_pos, n_neg, undetermined, pivot_root = _certify_interval_inertia(matrix, dim, spec)
    inertia_verified = undetermined is None and n_pos + n_neg == dim
    positive_definite = inertia_verified and n_neg == 0 and n_pos == dim
    errors: list[str] = []
    if not inertia_verified:
        errors.append("INTERVAL_PIVOT_UNDETERMINED")

    provenance_root = canonical_hash("AEGIS_GUINAND_WEIL_FORMULA_PROVENANCE_V1", FORMULA_PROVENANCE)
    valid = inertia_verified and not errors
    obligations = [
        "FORMULA_TO_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_FORMALIZED",
        "CUTOFF_FREE_ARCHIMEDEAN_CLOSED_FORM_DERIVATION_NOT_MACHINE_FORMALIZED",
        "FINITE_BAND_DOES_NOT_ESTABLISH_GLOBAL_WEIL_POSITIVITY",
        "N_TO_INFINITY_GLOBALIZATION_NOT_MACHINE_VERIFIED",
    ]
    if not inertia_verified:
        obligations.append("RAISE_ARB_PRECISION_OR_CHANGE_PIVOT_STRATEGY")

    return ArbGalerkinVerificationV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=spec.root,
        formula_id=FORMULA_ID,
        formula_provenance_root=provenance_root,
        backend=f"python-flint/{getattr(flint, '__version__', 'unknown')}",
        c=spec.c,
        N=spec.N,
        dimension=dim,
        prec_bits=spec.prec_bits,
        valid=valid,
        status="FINITE_INTERVAL_INERTIA_VERIFIED" if valid else "UNDETERMINED",
        cutoff_free_entry_enclosures_verified=True,
        interval_inertia_verified=inertia_verified,
        n_positive=n_pos,
        n_negative=n_neg,
        undetermined_pivot=undetermined,
        finite_matrix_positive_definite_verified=positive_definite,
        finite_matrix_psd_verified=positive_definite,
        matrix_root=matrix_root,
        pivot_root=pivot_root,
        galerkin_semantics_verified=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        errors=tuple(sorted(set(errors))),
        open_obligations=tuple(sorted(set(obligations))),
    )


@dataclass(frozen=True)
class ArbGalerkinTraceBindingV1:
    """A ProofTrace binding for one freshly replayed finite Galerkin verifier."""

    verification: ArbGalerkinVerificationV1
    span: "TraceSpanV1"

    @property
    def binding_root(self) -> str:
        return canonical_hash(
            "AEGIS_ARB_GALERKIN_TRACE_BINDING_ROOT_V1",
            {
                "verification_root": self.verification.receipt_root,
                "span_root": self.span.root,
            },
        )


def bind_cutoff_free_galerkin_verification(
    trace: "ProofTrace",
    spec: ArbGalerkinSpecV1,
    *,
    causal_parent_ids: tuple[str, ...] = (),
) -> ArbGalerkinTraceBindingV1:
    """Replay the verifier and bind it into ProofTrace as T2 evidence only.

    The binding never accepts a caller-supplied receipt and never changes the
    trace control-state root.  Matrix, pivot transcript, and verifier receipt
    are bound separately so later replay can detect semantic or arithmetic
    tampering without confusing integrity with theorem authority.
    """
    from harness.sdk.proof_trace import (
        DENIED,
        NO_AUTHORITY,
        OK,
        T2,
        VERIFIER,
        ProofTrace,
        TraceSpanV1,
        digest_payload,
    )

    if not isinstance(trace, ProofTrace):
        raise ArbGalerkinError("TRACE_TYPE_INVALID")

    verification = verify_cutoff_free_galerkin(spec)
    handle = trace.start_span(
        name="guinand-weil-arb-galerkin",
        span_kind=VERIFIER,
        causal_parent_ids=causal_parent_ids,
        start_context={
            "proof_semantics": PROOF_SEMANTICS,
            "formula_id": FORMULA_ID,
            "spec_root": spec.root,
        },
    )
    span: TraceSpanV1 = trace.finish_span(
        handle,
        status=OK if verification.valid else DENIED,
        authority_class=NO_AUTHORITY,
        epistemic_tier=T2,
        input_digest=digest_payload(asdict(spec)),
        output_digest=digest_payload(verification.to_dict()),
        evidence_roots=(
            verification.receipt_root,
            verification.matrix_root,
            verification.pivot_root,
        ),
        error_code=None if verification.valid else "GALERKIN_INTERVAL_UNDETERMINED",
    )
    return ArbGalerkinTraceBindingV1(verification=verification, span=span)
