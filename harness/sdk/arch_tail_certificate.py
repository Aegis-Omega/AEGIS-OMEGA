"""Rigorous scalar Archimedean-tail budget arithmetic for AEGIS Ω.

The released arXiv:2607.02828v3 reproducibility package evaluates an upper
budget for the finite-band Archimedean tail using Arb interval arithmetic,
dyadic pieces, and a logarithmic final-tail envelope.  This module replays the
bounded scalar computation independently inside AEGIS.

Crucial epistemic boundary: recomputing the scalar budget is not a machine
proof of the operator-order theorem

    0 <= Q_infty - Q_T <= B_T I.

Accordingly ``tail_order_theorem_verified`` remains false in v1.  The receipt
proves only that the stated bounded arithmetic and threshold predicates were
recomputed rigorously by the fixed kernel.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Any

from flint import acb, arb, ctx

from harness.sdk.sovereign_execution import canonical_hash

SPEC_KIND = "AEGIS_ARCH_TAIL_SPEC_V1"
RECEIPT_KIND = "AEGIS_ARCH_TAIL_BUDGET_RECEIPT_V1"
PROOF_SEMANTICS = "RIGOROUS_SCALAR_TAIL_BUDGET_ARITHMETIC_NOT_OPERATOR_ORDER_PROOF"
FORMULA_PROVENANCE = {
    "paper": "arXiv:2607.02828v3",
    "reference_tail_budget_script_blob": "7927ed7644c84a9324b95d338ef6f2b73c3c8c1e",
    "python_flint_expected": "0.8.0",
}

MIN_PREC_BITS = 128
MAX_PREC_BITS = 32768
MAX_CUTOFF_C = 100000
MAX_BAND = 10000
MAX_T = 10**12
MAX_DYADIC_COUNT = 256

FORMAL_BRIDGE_RECEIPT_KIND = "AEGIS_WEIL_FORMAL_BRIDGE_RECEIPT_V1"
FORMAL_BRIDGE_VERIFICATION_KIND = "AEGIS_WEIL_FORMAL_BRIDGE_VERIFICATION_V1"
FORMAL_TAIL_BINDING_RECEIPT_KIND = "AEGIS_ARCH_TAIL_FORMAL_BINDING_RECEIPT_V1"
FORMAL_BRIDGE_AUTHORITY = "FORMAL_MATH_EVIDENCE_ONLY"
FORMAL_SOURCE_RELATIVE_PATH = "sovereign-omega-v2/formal/theories/Weil/FiniteBridge.v"
FORMAL_THEOREMS = (
    "divided_difference_offdiag_symmetric",
    "pole_kernel_symmetric",
    "offdiag_entry_symmetric",
    "bounded_positive_tail_preserves_nonnegative",
    "bounded_positive_tail_certifies_negative",
    "gray_zone_can_change_sign",
)
FORMAL_RECEIPT_REQUIRED_FIELDS = frozenset(
    {
        "receipt_kind",
        "authority",
        "source_commit",
        "source_sha256",
        "coq_version_sha256",
        "compile_log_sha256",
        "theorem_assumption_log_sha256",
        "theorem_count",
        "declared_assumptions",
        "global_weil_positivity_proven",
        "rh_proven",
        "analytic_tail_order_theorem_proven",
        "formula_to_weil_operator_identity_proven",
        "receipt_sha256",
    }
)


class ArchTailError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class FormalBridgeError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ArchTailSpecV1:
    c: int
    N: int
    T: int
    prec_bits: int
    dyadic_count: int
    spec_kind: str = SPEC_KIND

    def __post_init__(self) -> None:
        if self.spec_kind != SPEC_KIND:
            raise ArchTailError("SPEC_KIND_MISMATCH")
        if isinstance(self.c, bool) or not isinstance(self.c, int) or not (2 <= self.c <= MAX_CUTOFF_C):
            raise ArchTailError("CUTOFF_INVALID")
        if isinstance(self.N, bool) or not isinstance(self.N, int) or not (0 <= self.N <= MAX_BAND):
            raise ArchTailError("BAND_INVALID")
        if isinstance(self.T, bool) or not isinstance(self.T, int) or not (1 <= self.T <= MAX_T):
            raise ArchTailError("TAIL_CUTOFF_INVALID")
        if isinstance(self.prec_bits, bool) or not isinstance(self.prec_bits, int):
            raise ArchTailError("PRECISION_INVALID")
        if self.prec_bits < MIN_PREC_BITS:
            raise ArchTailError("PRECISION_TOO_LOW")
        if self.prec_bits > MAX_PREC_BITS:
            raise ArchTailError("PRECISION_TOO_HIGH")
        if (
            isinstance(self.dyadic_count, bool)
            or not isinstance(self.dyadic_count, int)
            or not (1 <= self.dyadic_count <= MAX_DYADIC_COUNT)
        ):
            raise ArchTailError("DYADIC_COUNT_INVALID")

    @property
    def root(self) -> str:
        return canonical_hash("AEGIS_ARCH_TAIL_SPEC_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class ArchTailBudgetVerificationV1:
    receipt_kind: str
    proof_semantics: str
    subject_root: str
    formula_provenance_root: str
    c: int
    N: int
    T: int
    dimension: int
    prec_bits: int
    dyadic_count: int
    valid: bool
    status: str
    threshold_verified: bool
    final_envelope_domain_verified: bool
    scalar_budget_arithmetic_verified: bool
    trace_budget_strictly_positive: bool
    entry_budget_strictly_positive: bool
    trace_budget_ball: dict[str, str]
    entry_budget_ball: dict[str, str]
    global_log_trace_ball: dict[str, str]
    global_log_entry_ball: dict[str, str]
    h_plus_7_ball: dict[str, str]
    h_plus_7_positive_verified: bool
    terminal_tail_cutoff: str
    budget_root: str
    tail_order_theorem_verified: bool
    galerkin_semantics_verified: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_ARCH_TAIL_BUDGET_RECEIPT_ROOT_V1", asdict(self))

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["receipt_root"] = self.receipt_root
        return payload


@dataclass(frozen=True)
class WeilFormalBridgeVerificationV1:
    receipt_kind: str
    subject_receipt_sha256: str
    source_sha256: str
    source_digest_verified: bool
    theorem_set_verified: bool
    declared_assumptions_verified_zero: bool
    finite_tail_decision_algebra_formally_verified: bool
    valid: bool
    tail_order_theorem_verified: bool
    formula_to_weil_operator_identity_proven: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_WEIL_FORMAL_BRIDGE_VERIFICATION_ROOT_V1", asdict(self))


@dataclass(frozen=True)
class ArchTailFormalBindingVerificationV1:
    receipt_kind: str
    budget_receipt_root: str
    formal_verification_root: str
    valid: bool
    scalar_budget_arithmetic_verified: bool
    finite_tail_decision_algebra_formally_verified: bool
    tail_order_theorem_verified: bool
    formula_to_weil_operator_identity_proven: bool
    global_weil_positivity_proven: bool
    rh_proven: bool
    errors: tuple[str, ...]
    open_obligations: tuple[str, ...]

    @property
    def receipt_root(self) -> str:
        return canonical_hash("AEGIS_ARCH_TAIL_FORMAL_BINDING_ROOT_V1", asdict(self))


def _ball_repr(value: arb, prec_bits: int) -> dict[str, str]:
    digits = max(40, int(math.ceil(prec_bits * math.log10(2))) + 8)
    return {
        "mid": value.mid().str(digits, radius=False),
        "rad": value.rad().str(digits, radius=False),
    }


def _h_plus(tau: arb) -> arb:
    z = acb(arb("0.25"), tau / 2)
    return z.digamma().real - arb.pi().log()


def _j_log_tail(a0: arb, n: int, rho: arb) -> arb:
    nn = arb(n)
    if n == 0:
        return ((rho * a0).log() + 1) / a0
    return (rho * a0).log() / (a0 - nn) + (a0 / (a0 - nn)).log() / nn


def _trace_norm_integral(a0: arb, a1: arb, nmax: int) -> arb:
    total = arb(0)
    for n in range(-nmax, nmax + 1):
        nn = arb(n)
        total += 1 / (a0 - nn) - 1 / (a1 - nn)
        total += 1 / (a0 + nn) - 1 / (a1 + nn)
    return total


def _trace_log_tail(a0: arb, nmax: int, rho: arb) -> arb:
    total = arb(0)
    for n in range(-nmax, nmax + 1):
        total += _j_log_tail(a0, n, rho)
        total += _j_log_tail(a0, -n, rho)
    return total


def _entry_max_integral(a0: arb, a1: arb, nmax: int) -> arb:
    return 2 * (1 / (a0 - nmax) - 1 / (a1 - nmax))


def _entry_log_tail(a0: arb, nmax: int, rho: arb) -> arb:
    return 2 * _j_log_tail(a0, nmax, rho)


def verify_arch_tail_budget(spec: ArchTailSpecV1) -> ArchTailBudgetVerificationV1:
    ctx.prec = spec.prec_bits
    pi = arb.pi()
    L = arb(spec.c).log()
    rho = 2 * pi / L
    T = arb(spec.T)

    # The published scalar bound is used only beyond the finite Galerkin band
    # and the h_+ positivity edge.  This is a checked domain predicate, not a
    # proof of the theorem that makes the tail operator positive.
    threshold_verified = bool(T > rho * spec.N and T > arb(7))
    errors: list[str] = []
    if not threshold_verified:
        errors.append("TAIL_CUTOFF_BELOW_PROVEN_BAND_THRESHOLD")

    trace_sum = arb(0)
    entry_sum = arb(0)
    transcript: list[dict[str, object]] = []
    A = T

    # These divisions require a0 > N.  The threshold check above guarantees it
    # for accepted results; for a rejected spec we avoid unsafe evaluation and
    # emit zero-valued budget placeholders.
    arithmetic_verified = False
    if threshold_verified:
        for k in range(spec.dyadic_count):
            B = 2 * A
            a0 = A / rho
            a1 = B / rho
            hB = _h_plus(B).upper()
            trace_piece = hB / (pi * pi) * _trace_norm_integral(a0, a1, spec.N)
            entry_piece = hB / (pi * pi) * _entry_max_integral(a0, a1, spec.N)
            trace_sum += trace_piece
            entry_sum += entry_piece
            transcript.append(
                {
                    "k": k,
                    "A": _ball_repr(A, spec.prec_bits),
                    "B": _ball_repr(B, spec.prec_bits),
                    "h_plus_B_upper": _ball_repr(hB, spec.prec_bits),
                    "trace_piece": _ball_repr(trace_piece, spec.prec_bits),
                    "entry_piece": _ball_repr(entry_piece, spec.prec_bits),
                }
            )
            A = B

        R = A
        aR = R / rho
        final_envelope_domain_verified = bool(R > arb(7))
        if not final_envelope_domain_verified:
            errors.append("FINAL_LOG_ENVELOPE_DOMAIN_NOT_REACHED")
            trace_tail = arb(0)
            entry_tail = arb(0)
        else:
            trace_tail = _trace_log_tail(aR, spec.N, rho) / (pi * pi)
            entry_tail = _entry_log_tail(aR, spec.N, rho) / (pi * pi)

        trace_total = trace_sum + trace_tail
        entry_total = entry_sum + entry_tail
        a_start = T / rho
        global_log_trace = _trace_log_tail(a_start, spec.N, rho) / (pi * pi)
        global_log_entry = _entry_log_tail(a_start, spec.N, rho) / (pi * pi)
        arithmetic_verified = final_envelope_domain_verified
    else:
        R = T
        final_envelope_domain_verified = False
        trace_total = arb(0)
        entry_total = arb(0)
        global_log_trace = arb(0)
        global_log_entry = arb(0)

    h7 = _h_plus(arb(7))
    h7_positive = bool(h7 > 0)
    if threshold_verified and not h7_positive:
        errors.append("H_PLUS_7_POSITIVITY_NOT_CERTIFIED")
        arithmetic_verified = False

    trace_positive = bool(trace_total > 0) if arithmetic_verified else False
    entry_positive = bool(entry_total > 0) if arithmetic_verified else False
    if arithmetic_verified and not trace_positive:
        errors.append("TRACE_BUDGET_NOT_STRICTLY_POSITIVE")
    if arithmetic_verified and not entry_positive:
        errors.append("ENTRY_BUDGET_NOT_STRICTLY_POSITIVE")

    budget_root = canonical_hash(
        "AEGIS_ARCH_TAIL_BUDGET_ROOT_V1",
        {
            "spec_root": spec.root,
            "trace_budget_ball": _ball_repr(trace_total, spec.prec_bits),
            "entry_budget_ball": _ball_repr(entry_total, spec.prec_bits),
            "global_log_trace_ball": _ball_repr(global_log_trace, spec.prec_bits),
            "global_log_entry_ball": _ball_repr(global_log_entry, spec.prec_bits),
            "terminal_tail_cutoff": _ball_repr(R, spec.prec_bits),
            "dyadic_transcript": transcript,
        },
    )

    valid = (
        threshold_verified
        and arithmetic_verified
        and h7_positive
        and trace_positive
        and entry_positive
        and not errors
    )
    provenance_root = canonical_hash("AEGIS_ARCH_TAIL_FORMULA_PROVENANCE_V1", FORMULA_PROVENANCE)

    return ArchTailBudgetVerificationV1(
        receipt_kind=RECEIPT_KIND,
        proof_semantics=PROOF_SEMANTICS,
        subject_root=spec.root,
        formula_provenance_root=provenance_root,
        c=spec.c,
        N=spec.N,
        T=spec.T,
        dimension=2 * spec.N + 1,
        prec_bits=spec.prec_bits,
        dyadic_count=spec.dyadic_count,
        valid=valid,
        status="SCALAR_TAIL_BUDGET_ARITHMETIC_VERIFIED" if valid else "REJECTED",
        threshold_verified=threshold_verified,
        final_envelope_domain_verified=final_envelope_domain_verified,
        scalar_budget_arithmetic_verified=arithmetic_verified,
        trace_budget_strictly_positive=trace_positive,
        entry_budget_strictly_positive=entry_positive,
        trace_budget_ball=_ball_repr(trace_total, spec.prec_bits),
        entry_budget_ball=_ball_repr(entry_total, spec.prec_bits),
        global_log_trace_ball=_ball_repr(global_log_trace, spec.prec_bits),
        global_log_entry_ball=_ball_repr(global_log_entry, spec.prec_bits),
        h_plus_7_ball=_ball_repr(h7, spec.prec_bits),
        h_plus_7_positive_verified=h7_positive,
        terminal_tail_cutoff=_ball_repr(R, spec.prec_bits)["mid"],
        budget_root=budget_root,
        tail_order_theorem_verified=False,
        galerkin_semantics_verified=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        errors=tuple(sorted(set(errors))),
        open_obligations=(
            "H_PLUS_LOG_ENVELOPE_THEOREM_NOT_MACHINE_FORMALIZED",
            "ARCHIMEDEAN_TAIL_OPERATOR_ORDER_THEOREM_NOT_MACHINE_FORMALIZED",
            "FORMULA_TO_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_FORMALIZED",
            "FINITE_BAND_DOES_NOT_ESTABLISH_GLOBAL_WEIL_POSITIVITY",
        ),
    )


def _is_hex(value: object, length: int) -> bool:
    if not isinstance(value, str) or len(value) != length:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _formal_receipt_digest(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def verify_weil_formal_bridge_receipt(payload: object) -> WeilFormalBridgeVerificationV1:
    if not isinstance(payload, dict):
        raise FormalBridgeError("FORMAL_RECEIPT_OBJECT_REQUIRED")
    if set(payload) != FORMAL_RECEIPT_REQUIRED_FIELDS:
        raise FormalBridgeError("FORMAL_RECEIPT_FIELDS_INVALID")

    supplied_digest = payload["receipt_sha256"]
    if not _is_hex(supplied_digest, 64):
        raise FormalBridgeError("FORMAL_RECEIPT_DIGEST_INVALID")
    expected_digest = _formal_receipt_digest(payload)
    if not hmac.compare_digest(supplied_digest, expected_digest):
        raise FormalBridgeError("FORMAL_RECEIPT_DIGEST_MISMATCH")

    if payload["receipt_kind"] != FORMAL_BRIDGE_RECEIPT_KIND:
        raise FormalBridgeError("FORMAL_RECEIPT_KIND_MISMATCH")
    if payload["authority"] != FORMAL_BRIDGE_AUTHORITY:
        raise FormalBridgeError("FORMAL_RECEIPT_AUTHORITY_INVALID")
    if not _is_hex(payload["source_commit"], 40):
        raise FormalBridgeError("FORMAL_SOURCE_COMMIT_INVALID")
    for field in ("source_sha256", "coq_version_sha256", "compile_log_sha256"):
        if not _is_hex(payload[field], 64):
            raise FormalBridgeError("FORMAL_RECEIPT_HASH_INVALID")

    theorem_logs = payload["theorem_assumption_log_sha256"]
    if not isinstance(theorem_logs, dict) or set(theorem_logs) != set(FORMAL_THEOREMS):
        raise FormalBridgeError("FORMAL_THEOREM_SET_MISMATCH")
    if any(not _is_hex(value, 64) for value in theorem_logs.values()):
        raise FormalBridgeError("FORMAL_THEOREM_LOG_HASH_INVALID")
    if isinstance(payload["theorem_count"], bool) or payload["theorem_count"] != len(FORMAL_THEOREMS):
        raise FormalBridgeError("FORMAL_THEOREM_COUNT_MISMATCH")
    if isinstance(payload["declared_assumptions"], bool) or payload["declared_assumptions"] != 0:
        raise FormalBridgeError("FORMAL_DECLARED_ASSUMPTIONS_PRESENT")

    overclaim_fields = (
        "global_weil_positivity_proven",
        "rh_proven",
        "analytic_tail_order_theorem_proven",
        "formula_to_weil_operator_identity_proven",
    )
    if any(payload[field] is not False for field in overclaim_fields):
        raise FormalBridgeError("FORMAL_RECEIPT_OVERCLAIM_REJECTED")

    source_path = _repo_root() / FORMAL_SOURCE_RELATIVE_PATH
    if not source_path.is_file():
        raise FormalBridgeError("FORMAL_SOURCE_NOT_FOUND")
    local_source_sha256 = hashlib.sha256(source_path.read_bytes()).hexdigest()
    if not hmac.compare_digest(payload["source_sha256"], local_source_sha256):
        raise FormalBridgeError("FORMAL_SOURCE_DIGEST_MISMATCH")

    return WeilFormalBridgeVerificationV1(
        receipt_kind=FORMAL_BRIDGE_VERIFICATION_KIND,
        subject_receipt_sha256=supplied_digest,
        source_sha256=local_source_sha256,
        source_digest_verified=True,
        theorem_set_verified=True,
        declared_assumptions_verified_zero=True,
        finite_tail_decision_algebra_formally_verified=True,
        valid=True,
        tail_order_theorem_verified=False,
        formula_to_weil_operator_identity_proven=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        open_obligations=(
            "ARCHIMEDEAN_TAIL_OPERATOR_ORDER_THEOREM_NOT_MACHINE_FORMALIZED",
            "FORMULA_TO_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_FORMALIZED",
            "FINITE_BAND_DOES_NOT_ESTABLISH_GLOBAL_WEIL_POSITIVITY",
        ),
    )


def bind_formal_bridge_to_tail_budget(
    budget: ArchTailBudgetVerificationV1,
    formal_receipt: object,
) -> ArchTailFormalBindingVerificationV1:
    if not isinstance(budget, ArchTailBudgetVerificationV1):
        raise FormalBridgeError("TAIL_BUDGET_RECEIPT_TYPE_INVALID")
    formal = verify_weil_formal_bridge_receipt(formal_receipt)
    errors: list[str] = []
    if not budget.valid or not budget.scalar_budget_arithmetic_verified:
        errors.append("SCALAR_TAIL_BUDGET_NOT_VERIFIED")

    valid = not errors and formal.valid
    return ArchTailFormalBindingVerificationV1(
        receipt_kind=FORMAL_TAIL_BINDING_RECEIPT_KIND,
        budget_receipt_root=budget.receipt_root,
        formal_verification_root=formal.receipt_root,
        valid=valid,
        scalar_budget_arithmetic_verified=budget.scalar_budget_arithmetic_verified and budget.valid,
        finite_tail_decision_algebra_formally_verified=formal.finite_tail_decision_algebra_formally_verified,
        tail_order_theorem_verified=False,
        formula_to_weil_operator_identity_proven=False,
        global_weil_positivity_proven=False,
        rh_proven=False,
        errors=tuple(errors),
        open_obligations=(
            "ARCHIMEDEAN_TAIL_OPERATOR_ORDER_THEOREM_NOT_MACHINE_FORMALIZED",
            "FORMULA_TO_WEIL_OPERATOR_IDENTITY_NOT_MACHINE_FORMALIZED",
            "FINITE_BAND_DOES_NOT_ESTABLISH_GLOBAL_WEIL_POSITIVITY",
        ),
    )
