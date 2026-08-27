"""Proof-carrying Gaussian/prime-power probe for the AEGIS Ω Weil proofline.

This module turns the finite Gaussian Q-form calculations into a receipt whose
fields cannot silently acquire more authority than their verification route.
It is intentionally a *probe* around the existing rigorous Guinand-Weil Arb
kernel, not a replacement for it and not a proof of the formula-to-Weil
operator identity, global Weil positivity, the Weil criterion, or RH.

The local finite transcendental evaluations are enclosed with python-flint Arb
balls.  The prime-power census is recomputed through an integer-only route and
cross-checked against ``guinand_weil_arb.prime_powers_up_to``.  The Gaussian
envelope cutoff law is certified numerically as an implication of the stated
envelope; applying that envelope to the full arithmetic/operator tail remains a
separate theorem obligation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Optional

import flint
from flint import arb, ctx

from harness.sdk.guinand_weil_arb import prime_powers_up_to
from harness.sdk.sovereign_execution import canonical_hash

RECEIPT_KIND = "AEGIS_QFORM_RECEIPT_V1"
RECEIPT_VERSION = "QFormReceiptV1"
PROOF_SEMANTICS = "RIGOROUS_FINITE_GAUSSIAN_PROBE_NOT_GLOBAL_WEIL_PROOF"

EXACT = "EXACT"
CERTIFIED_INTERVAL = "CERTIFIED_INTERVAL"
NUMERICALLY_VERIFIED = "NUMERICALLY_VERIFIED"
EMPIRICAL_FIXTURE = "EMPIRICAL_FIXTURE"

AUTHORITY_RANK = {
    EMPIRICAL_FIXTURE: 0,
    NUMERICALLY_VERIFIED: 1,
    CERTIFIED_INTERVAL: 2,
    EXACT: 3,
}

MIN_PREC_BITS = 128
MAX_PREC_BITS = 32768
MAX_CUTOFF = 100000


class QFormReceiptError(ValueError):
    """Fail-closed input/provenance error with a stable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class QFormSpecV1:
    P_cutoff: int
    sigma: str
    du: str
    U_max: str
    prec_bits: int = 256

    def __post_init__(self) -> None:
        if isinstance(self.P_cutoff, bool) or not isinstance(self.P_cutoff, int):
            raise QFormReceiptError("P_CUTOFF_INVALID")
        if not (2 <= self.P_cutoff <= MAX_CUTOFF):
            raise QFormReceiptError("P_CUTOFF_OUT_OF_RANGE")
        if isinstance(self.prec_bits, bool) or not isinstance(self.prec_bits, int):
            raise QFormReceiptError("PRECISION_INVALID")
        if not (MIN_PREC_BITS <= self.prec_bits <= MAX_PREC_BITS):
            raise QFormReceiptError("PRECISION_OUT_OF_RANGE")
        for name, text in (("SIGMA", self.sigma), ("DU", self.du), ("U_MAX", self.U_max)):
            try:
                value = arb(text)
            except Exception as exc:  # pragma: no cover - backend-specific parse text
                raise QFormReceiptError(f"{name}_INVALID") from exc
            if not bool(value > 0):
                raise QFormReceiptError(f"{name}_NOT_STRICTLY_POSITIVE")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_QFORM_SPEC_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class QFormReceiptV1:
    receipt_kind: str
    receipt_version: str
    proof_semantics: str
    provenance: dict[str, object]
    parameters: dict[str, object]
    exact_census: dict[str, object]
    evaluations: dict[str, object]
    gaussian_cutoff: dict[str, object]
    error_budget: dict[str, object]
    finite_formula_authority: str
    overall_authority: str
    formula_to_weil_operator_identity_proven: bool
    tail_order_theorem_verified: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_QFORM_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


def _prime_sieve(limit: int) -> tuple[int, ...]:
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[0:2] = b"\x00\x00"
    bound = math.isqrt(limit)
    for p in range(2, bound + 1):
        if not sieve[p]:
            continue
        start = p * p
        count = ((limit - start) // p) + 1
        sieve[start : limit + 1 : p] = b"\x00" * count
    return tuple(i for i in range(2, limit + 1) if sieve[i])


def exact_prime_power_census(P_cutoff: int) -> tuple[tuple[int, int, int], ...]:
    """Return canonical ``(q, p, k)`` rows using integer arithmetic only."""
    if isinstance(P_cutoff, bool) or not isinstance(P_cutoff, int) or P_cutoff < 2:
        raise QFormReceiptError("P_CUTOFF_INVALID")
    rows: list[tuple[int, int, int]] = []
    for p in _prime_sieve(P_cutoff):
        q = p
        k = 1
        while q <= P_cutoff:
            rows.append((q, p, k))
            if q > P_cutoff // p:
                break
            q *= p
            k += 1
    return tuple(sorted(rows))


def _census_sha256(rows: tuple[tuple[int, int, int], ...]) -> str:
    material = "".join(f"{q},{p},{k}\n" for q, p, k in rows).encode("ascii")
    return hashlib.sha256(material).hexdigest()


def _ball_repr(value: arb, prec_bits: int) -> dict[str, str]:
    digits = max(40, int(math.ceil(prec_bits * math.log10(2))) + 8)
    return {
        "mid": value.mid().str(digits, radius=False),
        "rad": value.rad().str(digits, radius=False),
    }


def _certified_main_term(sigma: arb) -> arb:
    return 4 * arb.pi() * sigma * sigma * (sigma * sigma / 4).exp()


def _certified_prime_trace(rows: tuple[tuple[int, int, int], ...], sigma: arb) -> arb:
    total = arb(0)
    four_sigma_sq = 4 * sigma * sigma
    for q, p, _k in rows:
        log_p = arb(p).log()
        log_q = arb(q).log()
        weight = log_p / arb(q).sqrt()
        total += 2 * weight * (-(log_q * log_q) / four_sigma_sq).exp()
    return total


def _certified_symbol(
    rows: tuple[tuple[int, int, int], ...],
    gamma: arb,
    *,
    damping_sigma: Optional[arb] = None,
) -> arb:
    total = arb(0)
    for q, p, _k in rows:
        log_p = arb(p).log()
        log_q = arb(q).log()
        term = 2 * log_p / arb(q).sqrt() * (gamma * log_q).cos()
        if damping_sigma is not None:
            term *= (-(log_q * log_q) / (4 * damping_sigma * damping_sigma)).exp()
        total += term
    return total


def gaussian_cutoff_certificate(*, sigma: str, epsilon: str, P_cutoff: int, prec_bits: int) -> dict[str, object]:
    """Certify the scalar Gaussian-envelope inequality at a finite cutoff.

    From ``exp(-u^2/(4 sigma^2)) <= epsilon`` one obtains
    ``u >= C(epsilon) sigma`` with ``C(epsilon)=2 sqrt(log(1/epsilon))``.
    This function certifies those scalar relations with Arb; it does not assert
    that the same envelope already bounds the complete Weil operator tail.
    """
    ctx.prec = prec_bits
    s = arb(sigma)
    eps = arb(epsilon)
    if not bool(s > 0):
        raise QFormReceiptError("SIGMA_NOT_STRICTLY_POSITIVE")
    if not bool(eps > 0 and eps < 1):
        raise QFormReceiptError("EPSILON_OUT_OF_RANGE")
    u_cut = arb(P_cutoff).log()
    c_eps = 2 * ((1 / eps).log()).sqrt()
    envelope = (-(u_cut * u_cut) / (4 * s * s)).exp()
    threshold = c_eps * s
    cutoff_relation_verified = bool(u_cut >= threshold)
    envelope_below_epsilon_verified = bool(envelope <= eps)
    return {
        "status": CERTIFIED_INTERVAL,
        "epsilon": epsilon,
        "C_epsilon_ball": _ball_repr(c_eps, prec_bits),
        "u_cut_ball": _ball_repr(u_cut, prec_bits),
        "required_u_cut_ball": _ball_repr(threshold, prec_bits),
        "envelope_tail_ball": _ball_repr(envelope, prec_bits),
        "cutoff_relation_verified": cutoff_relation_verified,
        "envelope_below_epsilon_verified": envelope_below_epsilon_verified,
        "theorem_ref": "GAUSSIAN_ENVELOPE_ALGEBRA_V1",
        "scope": "SCALAR_GAUSSIAN_ENVELOPE_ONLY",
    }


def weakest_authority(*authorities: str) -> str:
    if not authorities:
        raise QFormReceiptError("AUTHORITY_SET_EMPTY")
    unknown = [value for value in authorities if value not in AUTHORITY_RANK]
    if unknown:
        raise QFormReceiptError("AUTHORITY_UNKNOWN")
    return min(authorities, key=lambda value: AUTHORITY_RANK[value])


def _git_text(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QFormReceiptError("GIT_PROVENANCE_UNAVAILABLE") from exc


def _resolve_provenance(
    *,
    source_commit: Optional[str],
    source_tree: Optional[str],
) -> tuple[str, str]:
    commit = source_commit or os.environ.get("EXPECTED_SHA") or _git_text("rev-parse", "HEAD")
    tree = source_tree or _git_text("rev-parse", f"{commit}^{{tree}}")
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise QFormReceiptError("SOURCE_COMMIT_INVALID")
    if len(tree) != 40 or any(ch not in "0123456789abcdef" for ch in tree):
        raise QFormReceiptError("SOURCE_TREE_INVALID")
    return commit, tree


def build_qform_receipt(
    spec: QFormSpecV1,
    *,
    gamma_fixture: str = "14.134725",
    epsilon: str = "1e-11",
    source_commit: Optional[str] = None,
    source_tree: Optional[str] = None,
) -> QFormReceiptV1:
    """Recompute a bounded Q-form receipt with explicit authority demotion."""
    ctx.prec = spec.prec_bits
    rows = exact_prime_power_census(spec.P_cutoff)
    independent_pairs = tuple((q, p) for q, p, _k in rows)
    parent_pairs = prime_powers_up_to(spec.P_cutoff)
    census_crosscheck = independent_pairs == parent_pairs
    if not census_crosscheck:
        raise QFormReceiptError("PRIME_POWER_CENSUS_CROSSCHECK_FAILED")

    sigma = arb(spec.sigma)
    gamma = arb(gamma_fixture)
    main_term = _certified_main_term(sigma)
    prime_trace = _certified_prime_trace(rows, sigma)
    undamped_symbol = _certified_symbol(rows, gamma)
    damped_symbol = _certified_symbol(rows, gamma, damping_sigma=sigma)
    cutoff = gaussian_cutoff_certificate(
        sigma=spec.sigma,
        epsilon=epsilon,
        P_cutoff=spec.P_cutoff,
        prec_bits=spec.prec_bits,
    )

    commit, tree = _resolve_provenance(source_commit=source_commit, source_tree=source_tree)
    implementation_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    parameter_sha256 = hashlib.sha256(
        json.dumps(asdict(spec), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    census = {
        "status": EXACT,
        "primes_count": len(_prime_sieve(spec.P_cutoff)),
        "prime_powers_count": len(rows),
        "census_sha256": _census_sha256(rows),
        "integer_crosscheck_verified": True,
        "crosscheck_route": "qform_receipt.exact_prime_power_census == guinand_weil_arb.prime_powers_up_to",
    }
    evaluations = {
        "main_term": {
            "status": CERTIFIED_INTERVAL,
            "formula": "4*pi*sigma^2*exp(sigma^2/4)",
            "arb_ball": _ball_repr(main_term, spec.prec_bits),
            "theorem_ref": "FINITE_GAUSSIAN_MAIN_TERM_FORMULA_INPUT",
        },
        "prime_trace_functional": {
            "status": CERTIFIED_INTERVAL,
            "formula": "2*sum(log(p)/sqrt(p^k)*exp(-(k*log(p))^2/(4*sigma^2)))",
            "arb_ball": _ball_repr(prime_trace, spec.prec_bits),
            "theorem_ref": "FINITE_PRIME_POWER_SUM_DEFINITION_V1",
        },
        "spectral_symbol_gamma_fixture": {
            "status": EMPIRICAL_FIXTURE,
            "gamma": gamma_fixture,
            "undamped_arb_ball": _ball_repr(undamped_symbol, spec.prec_bits),
            "gaussian_damped_arb_ball": _ball_repr(damped_symbol, spec.prec_bits),
            "method": "rigorous finite evaluation used only as a regression/falsification fixture",
        },
    }

    # The *finite formulas* are certified, but the full Q-form/operator bridge is
    # intentionally weaker until the semantic and operator-limit theorems close.
    finite_formula_authority = weakest_authority(EXACT, CERTIFIED_INTERVAL)
    error_budget = {
        "arithmetic_cutoff": {
            "status": CERTIFIED_INTERVAL,
            "description": "Scalar Gaussian envelope evaluated rigorously; extension to full arithmetic/operator tail is open.",
            "theorem_ref": "GAUSSIAN_ENVELOPE_ALGEBRA_V1",
        },
        "finite_domain_truncation": {
            "status": NUMERICALLY_VERIFIED,
            "description": "U_max remains a numerical truncation parameter; no rigorous operator norm bound is attached here.",
        },
        "discretization": {
            "status": NUMERICALLY_VERIFIED,
            "description": "Reported O(du^2) convergence remains numerical until a computable constant/enclosure theorem is bound.",
        },
        "transcendental_rounding": {
            "status": CERTIFIED_INTERVAL,
            "description": f"python-flint/{getattr(flint, '__version__', 'unknown')} Arb ball arithmetic at {spec.prec_bits} bits.",
        },
        "operator_projection": {
            "status": EMPIRICAL_FIXTURE,
            "description": "Finite dilation/Galerkin realization is not yet machine-identified with the global Weil operator.",
        },
    }
    overall_authority = weakest_authority(
        finite_formula_authority,
        *(term["status"] for term in error_budget.values()),
    )

    return QFormReceiptV1(
        receipt_kind=RECEIPT_KIND,
        receipt_version=RECEIPT_VERSION,
        proof_semantics=PROOF_SEMANTICS,
        provenance={
            "repository": "Aegis-Omega/AEGIS-OMEGA",
            "commit_sha": commit,
            "tree_sha": tree,
            "implementation_sha256": implementation_sha256,
            "parameter_sha256": parameter_sha256,
            "backend": f"python-flint/{getattr(flint, '__version__', 'unknown')}",
            "precision_bits": spec.prec_bits,
        },
        parameters=asdict(spec),
        exact_census=census,
        evaluations=evaluations,
        gaussian_cutoff=cutoff,
        error_budget=error_budget,
        finite_formula_authority=finite_formula_authority,
        overall_authority=overall_authority,
        formula_to_weil_operator_identity_proven=False,
        tail_order_theorem_verified=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=(
            "GAUSSIAN_ENVELOPE_TO_FULL_ARITHMETIC_TAIL_THEOREM_NOT_MACHINE_BOUND",
            "FINITE_DILATION_TO_GUINAND_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_BOUND",
            "FINITE_DOMAIN_TRUNCATION_OPERATOR_NORM_BOUND_NOT_MACHINE_BOUND",
            "DISCRETIZATION_CONSTANT_NOT_MACHINE_BOUND",
            "N_TO_INFINITY_GLOBALIZATION_REQUIRES_EXISTING_O0_HYPOTHESES",
            "WEIL_CRITERION_NOT_MACHINE_BOUND",
        ),
    )
