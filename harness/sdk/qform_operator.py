"""Fail-closed finite translation-operator probe for the AEGIS Ω Weil proofline.

This module operationalizes the numerical L2 translation experiment without
promoting it to a theorem.  Exact integer prime-power structure is inherited
from :mod:`harness.sdk.qform_receipt`; logarithms, square roots, quadrature and
finite-domain effects are explicitly separated from that exact structure.

Authority boundary
------------------
* prime-power indices ``(p, k, p**k)`` are exact;
* the Fourier/Nyquist preflight inequality is enclosed with Arb balls;
* the finite translation quadrature is a numerical probe;
* observed second-order refinement is evidence, not an analytic O(h^2) bound;
* no result in this module establishes the Guinand-Weil operator identity,
  global Weil positivity, the Weil criterion, or RH.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path
from typing import Mapping, Optional

from flint import arb, ctx

from harness.sdk.qform_receipt import (
    CERTIFIED_INTERVAL,
    NUMERICALLY_VERIFIED,
    QFormReceiptError,
    exact_prime_power_census,
)
from harness.sdk.sovereign_execution import canonical_hash

PREFLIGHT_RECEIPT_KIND = "AEGIS_QFORM_PREFLIGHT_RECEIPT_V1"
OPERATOR_RECEIPT_KIND = "AEGIS_QFORM_OPERATOR_RECEIPT_V1"
PROOF_SEMANTICS = "NUMERICAL_TRANSLATION_OPERATOR_PROBE_NOT_WEIL_OPERATOR_PROOF"
MIN_PREC_BITS = 128
MAX_PREC_BITS = 32768
MAX_CUTOFF = 100000
MAX_GRID_POINTS = 2_000_001


@dataclass(frozen=True)
class PrimePowerIndexV1:
    """Exact structural identity for one prime-power contribution."""

    q: int
    p: int
    k: int

    @property
    def tau_formula(self) -> str:
        return f"{self.k}*log({self.p})"

    @property
    def weight_formula(self) -> str:
        return f"log({self.p})/sqrt({self.q})"


@dataclass(frozen=True)
class QFormOperatorSpecV1:
    P_cutoff: int
    sigma: str
    du: str
    U_max: str
    N_F: int
    h: str
    gamma_max: str
    prec_bits: int = 256

    def __post_init__(self) -> None:
        if isinstance(self.P_cutoff, bool) or not isinstance(self.P_cutoff, int):
            raise QFormReceiptError("P_CUTOFF_INVALID")
        if not (2 <= self.P_cutoff <= MAX_CUTOFF):
            raise QFormReceiptError("P_CUTOFF_OUT_OF_RANGE")
        if isinstance(self.N_F, bool) or not isinstance(self.N_F, int) or self.N_F <= 0:
            raise QFormReceiptError("N_F_INVALID")
        if isinstance(self.prec_bits, bool) or not isinstance(self.prec_bits, int):
            raise QFormReceiptError("PRECISION_INVALID")
        if not (MIN_PREC_BITS <= self.prec_bits <= MAX_PREC_BITS):
            raise QFormReceiptError("PRECISION_OUT_OF_RANGE")
        for name, text in (
            ("SIGMA", self.sigma),
            ("DU", self.du),
            ("U_MAX", self.U_max),
            ("H", self.h),
            ("GAMMA_MAX", self.gamma_max),
        ):
            try:
                value = arb(text)
            except Exception as exc:  # pragma: no cover - backend parse detail
                raise QFormReceiptError(f"{name}_INVALID") from exc
            if not bool(value > 0):
                raise QFormReceiptError(f"{name}_NOT_STRICTLY_POSITIVE")

        # Bound memory/time before a numerical experiment is admitted.
        du = float(self.du)
        u_max = float(self.U_max)
        points = math.ceil((2.0 * u_max) / du) + 1
        if points > MAX_GRID_POINTS:
            raise QFormReceiptError("GRID_POINT_BUDGET_EXCEEDED")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_QFORM_OPERATOR_SPEC_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class QFormPreflightReceiptV1:
    receipt_kind: str
    subject_root: str
    implementation_sha256: str
    status: str
    blocked: bool
    reason: str
    authority: str
    N_F: int
    h: str
    gamma_max: str
    frequency_capacity_ball: dict[str, str]
    inequality: str

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_QFORM_PREFLIGHT_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


@dataclass(frozen=True)
class QFormOperatorReceiptV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    preflight_receipt_root: str
    preflight_status: str
    prime_power_count: int
    parameters: dict[str, object]
    main_term_numeric: float
    closed_form_prime_trace_numeric: float
    discrete_prime_trace_numeric: float
    discrete_q_numeric: float
    refined_du: float
    refined_prime_trace_numeric: float
    observed_relative_error_to_closed_form: float
    observed_refinement_delta: float
    observed_refinement_ratio: Optional[float]
    discretization_status: str
    discretization_order_theorem_verified: bool
    finite_domain_error_theorem_verified: bool
    formula_to_weil_operator_identity_proven: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_QFORM_OPERATOR_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def _implementation_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _ball_repr(value: arb, prec_bits: int) -> dict[str, str]:
    digits = max(40, int(math.ceil(prec_bits * math.log10(2))) + 8)
    return {
        "mid": value.mid().str(digits, radius=False),
        "rad": value.rad().str(digits, radius=False),
    }


def exact_prime_power_indices(P_cutoff: int) -> tuple[PrimePowerIndexV1, ...]:
    """Expose only the exact combinatorial part of prime-power generation."""
    return tuple(PrimePowerIndexV1(q=q, p=p, k=k) for q, p, k in exact_prime_power_census(P_cutoff))


def build_preflight_receipt(spec: QFormOperatorSpecV1) -> QFormPreflightReceiptV1:
    """Apply the zero-discretion Fourier coverage gate with interval arithmetic.

    The requested rule is fail-closed: if ``N_F*pi/h < gamma_max`` is proved,
    execution is blocked.  If Arb cannot order the two balls, execution is also
    blocked rather than guessed through.
    """
    ctx.prec = spec.prec_bits
    capacity = arb(spec.N_F) * arb.pi() / arb(spec.h)
    gamma = arb(spec.gamma_max)

    if bool(capacity < gamma):
        blocked = True
        status = "BLOCKED"
        reason = "FOURIER_COVERAGE_INSUFFICIENT"
    elif bool(capacity >= gamma):
        blocked = False
        status = "PASS"
        reason = "FOURIER_COVERAGE_CERTIFIED"
    else:
        blocked = True
        status = "BLOCKED"
        reason = "FOURIER_COVERAGE_UNDECIDED"

    return QFormPreflightReceiptV1(
        receipt_kind=PREFLIGHT_RECEIPT_KIND,
        subject_root=spec.root,
        implementation_sha256=_implementation_sha256(),
        status=status,
        blocked=blocked,
        reason=reason,
        authority=CERTIFIED_INTERVAL,
        N_F=spec.N_F,
        h=spec.h,
        gamma_max=spec.gamma_max,
        frequency_capacity_ball=_ball_repr(capacity, spec.prec_bits),
        inequality="N_F*pi/h >= gamma_max",
    )


def verify_preflight_receipt(payload: Mapping[str, object], spec: QFormOperatorSpecV1) -> None:
    """Reject stale or tampered gate receipts instead of reusing them."""
    if payload.get("receipt_kind") != PREFLIGHT_RECEIPT_KIND:
        raise QFormReceiptError("PREFLIGHT_KIND_MISMATCH")
    if payload.get("subject_root") != spec.root:
        raise QFormReceiptError("PREFLIGHT_PARAMETER_ROOT_MISMATCH")
    if payload.get("implementation_sha256") != _implementation_sha256():
        raise QFormReceiptError("PREFLIGHT_IMPLEMENTATION_CHANGED")

    claimed_root = payload.get("receipt_root")
    body = dict(payload)
    body.pop("receipt_root", None)
    expected = canonical_hash("AEGIS_QFORM_PREFLIGHT_RECEIPT_ROOT_V1", body)
    if claimed_root != expected:
        raise QFormReceiptError("PREFLIGHT_RECEIPT_ROOT_MISMATCH")
    if payload.get("blocked") is True or payload.get("status") != "PASS":
        raise QFormReceiptError("PREFLIGHT_BLOCKED")


def _float_prime_rows(P_cutoff: int) -> tuple[tuple[float, float], ...]:
    rows = []
    for q, p, _k in exact_prime_power_census(P_cutoff):
        rows.append((math.log(q), math.log(p) / math.sqrt(q)))
    return tuple(rows)


def finite_prime_trace_closed_form_numeric(P_cutoff: int, sigma: float) -> float:
    """Finite double-precision formula used only as a numerical comparator."""
    denom = 4.0 * sigma * sigma
    return 2.0 * math.fsum(
        weight * math.exp(-(tau * tau) / denom)
        for tau, weight in _float_prime_rows(P_cutoff)
    )


def _translation_prime_trace_at_du(P_cutoff: int, sigma: float, U_max: float, du: float) -> tuple[float, float]:
    """Trapezoidal L2 expectation of the finite translation operator.

    ``g(u)=exp(-u^2/(2*sigma^2))`` and the result is normalized by the
    truncated numerical ``||g||_2^2``.  The routine deliberately evaluates
    translated functions instead of replacing the experiment by the known
    Gaussian overlap formula.
    """
    intervals = max(2, math.ceil((2.0 * U_max) / du))
    actual_du = (2.0 * U_max) / intervals
    grid = tuple(-U_max + i * actual_du for i in range(intervals + 1))
    gaussian = tuple(math.exp(-(u * u) / (2.0 * sigma * sigma)) for u in grid)
    trap = tuple(0.5 if i in (0, intervals) else 1.0 for i in range(intervals + 1))
    norm = actual_du * math.fsum(w * g * g for w, g in zip(trap, gaussian))
    if not math.isfinite(norm) or norm <= 0.0:
        raise QFormReceiptError("DISCRETE_NORM_INVALID")

    contributions = []
    inv_two_sigma_sq = 1.0 / (2.0 * sigma * sigma)
    for tau, weight in _float_prime_rows(P_cutoff):
        overlap_sum = math.fsum(
            w
            * g
            * (
                math.exp(-((u + tau) * (u + tau)) * inv_two_sigma_sq)
                + math.exp(-((u - tau) * (u - tau)) * inv_two_sigma_sq)
            )
            for w, g, u in zip(trap, gaussian, grid)
        )
        contributions.append(weight * actual_du * overlap_sum / norm)
    return math.fsum(contributions), actual_du


def build_operator_receipt(
    spec: QFormOperatorSpecV1,
    *,
    preflight_payload: Optional[Mapping[str, object]] = None,
) -> QFormOperatorReceiptV1:
    """Run the bounded translation experiment only after a valid preflight."""
    if preflight_payload is None:
        preflight = build_preflight_receipt(spec).to_dict()
    else:
        preflight = dict(preflight_payload)
    verify_preflight_receipt(preflight, spec)

    sigma = float(spec.sigma)
    U_max = float(spec.U_max)
    requested_du = float(spec.du)
    main_term = 4.0 * math.pi * sigma * sigma * math.exp((sigma * sigma) / 4.0)
    closed_prime = finite_prime_trace_closed_form_numeric(spec.P_cutoff, sigma)
    discrete_prime, actual_du = _translation_prime_trace_at_du(
        spec.P_cutoff, sigma, U_max, requested_du
    )
    refined_prime, refined_du = _translation_prime_trace_at_du(
        spec.P_cutoff, sigma, U_max, requested_du / 2.0
    )

    rel_error = abs(discrete_prime - closed_prime) / max(abs(closed_prime), 1e-300)
    refinement_delta = abs(discrete_prime - refined_prime) / max(abs(refined_prime), 1e-300)

    # A second refinement supplies a diagnostic ratio.  It does not certify an
    # asymptotic theorem because no uniform derivative/tail constant is bound.
    finer_prime, _ = _translation_prime_trace_at_du(
        spec.P_cutoff, sigma, U_max, requested_du / 4.0
    )
    finer_delta = abs(refined_prime - finer_prime) / max(abs(finer_prime), 1e-300)
    refinement_ratio = None if finer_delta == 0.0 else refinement_delta / finer_delta

    return QFormOperatorReceiptV1(
        receipt_kind=OPERATOR_RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=spec.root,
        preflight_receipt_root=str(preflight["receipt_root"]),
        preflight_status=str(preflight["status"]),
        prime_power_count=len(exact_prime_power_census(spec.P_cutoff)),
        parameters=asdict(spec),
        main_term_numeric=main_term,
        closed_form_prime_trace_numeric=closed_prime,
        discrete_prime_trace_numeric=discrete_prime,
        discrete_q_numeric=main_term - discrete_prime,
        refined_du=refined_du,
        refined_prime_trace_numeric=refined_prime,
        observed_relative_error_to_closed_form=rel_error,
        observed_refinement_delta=refinement_delta,
        observed_refinement_ratio=refinement_ratio,
        discretization_status=NUMERICALLY_VERIFIED,
        discretization_order_theorem_verified=False,
        finite_domain_error_theorem_verified=False,
        formula_to_weil_operator_identity_proven=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=(
            "DISCRETIZATION_O_DU2_CONSTANT_NOT_MACHINE_BOUND",
            "FINITE_DOMAIN_TAIL_BOUND_NOT_MACHINE_BOUND",
            "TRANSLATION_OPERATOR_TO_GUINAND_WEIL_IDENTITY_NOT_MACHINE_BOUND",
            "COMPACT_SUPPORT_BRIDGE_NOT_MACHINE_BOUND",
            "N_TO_INFINITY_GLOBALIZATION_REQUIRES_EXISTING_O0_HYPOTHESES",
            "WEIL_CRITERION_NOT_MACHINE_BOUND",
        ),
    )
