"""Conditional analytic error budget for the finite QForm translation probe.

This module computes rigorous *constant arithmetic* with Arb for an explicit
finite-domain + composite-trapezoid error budget.  It deliberately does not
promote the resulting inequality to a theorem: the real-analysis lemmas from
which the formulas are derived (Gaussian tail inequality, composite trapezoid
remainder, and quotient-stability composition) must still be machine-bound in
the formal layer.

For g(u)=exp(-u^2/(2*sigma^2)) the full L2 norm is sqrt(pi)*sigma and the
full normalized overlap at shift tau is 2*exp(-tau^2/(4*sigma^2)).  The
finite-domain and discretization constants below are conservative and are
computed independently of the observed refinement ratio.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
from pathlib import Path

from flint import arb, ctx

from harness.sdk.qform_operator import QFormOperatorSpecV1
from harness.sdk.qform_receipt import CERTIFIED_INTERVAL, QFormReceiptError, exact_prime_power_census
from harness.sdk.sovereign_execution import canonical_hash

RECEIPT_KIND = "AEGIS_QFORM_ANALYTIC_ERROR_BUDGET_V1"
PROOF_SEMANTICS = "CONDITIONAL_ANALYTIC_ERROR_CONSTANTS_NOT_MACHINE_BOUND_THEOREM"


@dataclass(frozen=True)
class QFormAnalyticErrorBudgetV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    implementation_sha256: str
    parameters: dict[str, object]
    constant_arithmetic_status: str
    gaussian_full_norm_ball: dict[str, str]
    denominator_tail_bound_ball: dict[str, str]
    denominator_integral_lower_ball: dict[str, str]
    max_shift_ball: dict[str, str]
    minimum_shift_margin_ball: dict[str, str]
    finite_domain_tail_bound_ball: dict[str, str]
    K_disc_ball: dict[str, str]
    conditional_discretization_bound_ball: dict[str, str]
    conditional_absolute_error_bound_ball: dict[str, str]
    conditional_absolute_error_bound_upper: float
    gaussian_tail_inequality_machine_bound: bool
    composite_trapezoid_theorem_machine_bound: bool
    quotient_stability_machine_bound: bool
    analytic_error_bound_machine_bound: bool
    formula_to_weil_operator_identity_proven: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_QFORM_ANALYTIC_ERROR_BUDGET_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def _ball_repr(value: arb, prec_bits: int) -> dict[str, str]:
    digits = max(40, int(math.ceil(prec_bits * math.log10(2))) + 8)
    return {
        "mid": value.mid().str(digits, radius=False),
        "rad": value.rad().str(digits, radius=False),
    }


def _float_upper(value: arb) -> float:
    """Non-authoritative convenience upper estimate for regression comparisons.

    The Arb ball carried in the receipt is the certification object.  This
    binary-float projection is intentionally not used by any proof predicate.
    """
    return float(value.mid()) + abs(float(value.rad()))


def build_analytic_error_budget(spec: QFormOperatorSpecV1) -> QFormAnalyticErrorBudgetV1:
    """Compute conservative constants for ``domain_error + K_disc * du^2``.

    The formulas are conditional on three real-analysis lemmas that remain
    explicit open obligations.  Arb certifies only evaluation/composition of
    the stated formulas for the supplied finite specification.
    """
    ctx.prec = spec.prec_bits
    sigma = arb(spec.sigma)
    U = arb(spec.U_max)
    h_max = arb(spec.du)
    rows = exact_prime_power_census(spec.P_cutoff)
    if not rows:
        raise QFormReceiptError("PRIME_POWER_CENSUS_EMPTY")

    # ||g||_2^2 on R for g(u)=exp(-u^2/(2*sigma^2)).
    full_norm = arb.pi().sqrt() * sigma

    # Two-sided Gaussian tail:
    # int_{|u|>U} exp(-u^2/sigma^2) du
    #   <= sigma^2/U * exp(-U^2/sigma^2).
    denominator_tail = sigma * sigma / U * (-(U * U) / (sigma * sigma)).exp()
    denominator_lower = full_norm - denominator_tail
    if not bool(denominator_lower > 0):
        raise QFormReceiptError("DENOMINATOR_LOWER_NOT_POSITIVE")

    max_q = max(q for q, _p, _k in rows)
    max_shift = arb(max_q).log()
    min_margin = U - max_shift / 2
    if not bool(min_margin > 0):
        raise QFormReceiptError("DOMAIN_SHIFT_MARGIN_NONPOSITIVE")

    # Composite-trapezoid error for the denominator.  For
    # f(u)=exp(-u^2/sigma^2), sup_R |f''(u)| <= 2/sigma^2, hence
    # |T_h(f)-I(f)| <= U/(3*sigma^2) h^2 on [-U,U].
    c_den = U / (3 * sigma * sigma)
    trap_den_lower = denominator_lower - c_den * h_max * h_max
    if not bool(trap_den_lower > 0):
        raise QFormReceiptError("TRAPEZOID_DENOMINATOR_LOWER_NOT_POSITIVE")

    domain_total = arb(0)
    k_disc_total = arb(0)

    for q, p, _k in rows:
        tau = arb(q).log()
        log_p = arb(p).log()
        weight = log_p / arb(q).sqrt()
        envelope = (-(tau * tau) / (4 * sigma * sigma)).exp()
        margin = U - tau / 2
        if not bool(margin > 0):
            raise QFormReceiptError("DOMAIN_SHIFT_MARGIN_NONPOSITIVE")

        # The two translated Gaussian overlap tails are each controlled after
        # recentering by the same two-sided tail at U-|tau|/2.
        numerator_tail = (
            2
            * envelope
            * sigma
            * sigma
            / margin
            * (-(margin * margin) / (sigma * sigma)).exp()
        )

        # |A_U/N_U - A/N| <= (E_A + (A/N) E_N) / N_U,
        # with A/N = 2*envelope and N_U >= denominator_lower.
        domain_ratio_bound = (
            numerator_tail + 2 * envelope * denominator_tail
        ) / denominator_lower
        domain_total += weight * domain_ratio_bound

        # For each shifted overlap integrand the global second derivative is
        # bounded by 2/sigma^2 times its Gaussian envelope.  Two translated
        # terms therefore give sup |F_tau''| <= 4*envelope/sigma^2 and
        # c_num*h^2 with c_num=2U*envelope/(3*sigma^2).
        c_num = 2 * U * envelope / (3 * sigma * sigma)

        # A_U/N_U <= A_full/N_lower =
        # 2*full_norm*envelope/denominator_lower.
        finite_ratio_upper = 2 * full_norm * envelope / denominator_lower

        # Quotient perturbation at every h <= h_max:
        # |T_A/T_N - A_U/N_U|
        # <= [c_num + finite_ratio_upper*c_den] / T_N_lower * h^2.
        k_term = (c_num + finite_ratio_upper * c_den) / trap_den_lower
        k_disc_total += weight * k_term

    discretization_bound = k_disc_total * h_max * h_max
    total_bound = domain_total + discretization_bound

    return QFormAnalyticErrorBudgetV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=spec.root,
        implementation_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        parameters=asdict(spec),
        constant_arithmetic_status=CERTIFIED_INTERVAL,
        gaussian_full_norm_ball=_ball_repr(full_norm, spec.prec_bits),
        denominator_tail_bound_ball=_ball_repr(denominator_tail, spec.prec_bits),
        denominator_integral_lower_ball=_ball_repr(denominator_lower, spec.prec_bits),
        max_shift_ball=_ball_repr(max_shift, spec.prec_bits),
        minimum_shift_margin_ball=_ball_repr(min_margin, spec.prec_bits),
        finite_domain_tail_bound_ball=_ball_repr(domain_total, spec.prec_bits),
        K_disc_ball=_ball_repr(k_disc_total, spec.prec_bits),
        conditional_discretization_bound_ball=_ball_repr(discretization_bound, spec.prec_bits),
        conditional_absolute_error_bound_ball=_ball_repr(total_bound, spec.prec_bits),
        conditional_absolute_error_bound_upper=_float_upper(total_bound),
        gaussian_tail_inequality_machine_bound=False,
        composite_trapezoid_theorem_machine_bound=False,
        quotient_stability_machine_bound=False,
        analytic_error_bound_machine_bound=False,
        formula_to_weil_operator_identity_proven=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=(
            "GAUSSIAN_TWO_SIDED_TAIL_INEQUALITY_NOT_MACHINE_BOUND",
            "COMPOSITE_TRAPEZOID_REMAINDER_NOT_MACHINE_BOUND",
            "NORMALIZED_QUOTIENT_STABILITY_NOT_MACHINE_BOUND",
            "FINITE_TRANSLATION_TO_GUINAND_WEIL_IDENTITY_NOT_MACHINE_BOUND",
            "COMPACT_SUPPORT_BRIDGE_NOT_MACHINE_BOUND",
            "WEIL_CRITERION_NOT_MACHINE_BOUND",
        ),
    )
