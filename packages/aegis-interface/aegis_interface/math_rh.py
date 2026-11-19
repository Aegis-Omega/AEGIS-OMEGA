"""AEGIS MIRA RH proof IR v1: exact local algebra and fail-closed RH scopes.

Drop-in sibling module for the existing packages/aegis-interface package.
No imported project internals or unsafe evaluation. Python >= 3.10, stdlib.
No Lean result or global RH conclusion is claimed.
"""
from __future__ import annotations

import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA = "aegis-mira-rh-proof-ir/v1"
ALLOWED = {"reflection_polynomial", "finite_gram_sos", "support_prime_cutoff"}
MAX_INPUT_BYTES = 1_000_000
MAX_DEGREE = 64
MAX_DIMENSION = 64
MAX_INTEGER_DIGITS = 120
_NUM = re.compile(r"(?:0|-?[1-9][0-9]*)(?:/[1-9][0-9]*)?\Z")

class ProofHold(ValueError):
    """Unsupported, invalid, unproven, or unsafe claim; no certificate issued."""


def rational(value: object) -> F:
    if not isinstance(value, str) or not _NUM.fullmatch(value) or value == "-0":
        raise ProofHold("HOLD_RATIONAL_TOKEN: rationals must be canonical exact strings")
    parts = value.replace("-", "").split("/")
    if any(len(p) > MAX_INTEGER_DIGITS for p in parts):
        raise ProofHold("HOLD_RATIONAL_SIZE")
    try:
        parsed = F(value)
    except (ZeroDivisionError, ValueError) as err:
        raise ProofHold("HOLD_BAD_RATIONAL") from err
    if value != fmt(parsed):
        raise ProofHold("HOLD_NONCANONICAL_RATIONAL")
    return parsed


def fmt(q: F) -> str:
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def canonical(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict:
    output: dict = {}
    for k, v in pairs:
        if k in output:
            raise ProofHold("HOLD_DUPLICATE_JSON_KEY")
        output[k] = v
    return output


def load_json(path: str) -> dict:
    src = Path(path).read_bytes()
    if len(src) > MAX_INPUT_BYTES:
        raise ProofHold("HOLD_INPUT_TOO_LARGE")
    try:
        obj = json.loads(src.decode("utf-8"), object_pairs_hook=_no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(ProofHold("HOLD_NONFINITE_NUMBER")))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise ProofHold("HOLD_INVALID_JSON") from err
    if not isinstance(obj, dict):
        raise ProofHold("HOLD_OBJECT_EXPECTED")
    return obj


def _keys(obj: object, expected: set[str]) -> None:
    if not isinstance(obj, dict) or set(obj) != expected:
        raise ProofHold(f"HOLD_TYPED_SCHEMA: expected keys {sorted(expected)}")


def poly(coeffs: object) -> tuple[F, ...]:
    if not isinstance(coeffs, list) or not coeffs or len(coeffs) > MAX_DEGREE + 1:
        raise ProofHold("HOLD_POLYNOMIAL_DEGREE")
    return trim(tuple(rational(q) for q in coeffs))


def trim(v: tuple[F, ...] | list[F]) -> tuple[F, ...]:
    v = list(v)
    while len(v) > 1 and v[-1] == 0:
        v.pop()
    return tuple(v) if v else (F(0),)


def add(a: tuple[F, ...], b: tuple[F, ...]) -> tuple[F, ...]:
    return trim([((a[i] if i < len(a) else F(0)) +
                  (b[i] if i < len(b) else F(0))) for i in range(max(len(a), len(b)))])


def mul(a: tuple[F, ...], b: tuple[F, ...]) -> tuple[F, ...]:
    v = [F(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            v[i + j] += x * y
    return trim(v)


def compose(a: tuple[F, ...], b: tuple[F, ...]) -> tuple[F, ...]:
    """Polynomial a(b(x)); Horner's rule over exact rationals."""
    out = (F(0),)
    for c in reversed(a):
        out = add(mul(out, b), (c,))
    return out


def ev(a: tuple[F, ...], x: F) -> F:
    acc = F(0)
    for c in reversed(a):
        acc = acc * x + c
    return acc


def divide(a: tuple[F, ...], b: tuple[F, ...]) -> tuple[tuple[F, ...], tuple[F, ...]]:
    if b == (F(0),):
        raise ProofHold("HOLD_DIVIDE_BY_ZERO_POLYNOMIAL")
    rem = list(a)
    quo = [F(0)] * max(1, len(a) - len(b) + 1)
    while len(rem) >= len(b) and any(rem):
        d = len(rem) - len(b)
        q = rem[-1] / b[-1]
        quo[d] += q
        for j, c in enumerate(b):
            rem[d + j] -= q * c
        rem = list(trim(rem))
    return trim(quo), trim(rem)


def forward_normal_form(R: tuple[F, ...]) -> tuple[F, ...]:
    """P(s)=(s-1/2)((s-1/2)^2-1/4) R((s-1/2)^2)."""
    t = (F(-1, 2), F(1))
    u = mul(t, t)
    base = mul(t, add(u, (F(-1, 4),)))
    return mul(base, compose(R, u))


def inverse_normal_form(P: tuple[F, ...]) -> tuple[F, ...]:
    """Unique R in Q[u], iff P(0)=P(1)=0 and P(1-s)=-P(s)."""
    if P == (F(0),):
        raise ProofHold("HOLD_ZERO_WITNESS: trivial P is not a spectral witness")
    if ev(P, F(0)) != 0 or ev(P, F(1)) != 0:
        raise ProofHold("HOLD_MELLIN_MOMENTS_NOT_ZERO")
    reflected = compose(P, (F(1), F(-1)))
    if add(P, reflected) != (F(0),):
        raise ProofHold("HOLD_REFLECTION_ANTISYMMETRY_FAILED")
    in_t = compose(P, (F(1, 2), F(1)))
    quotient, remainder = divide(in_t, (F(0), F(-1, 4), F(0), F(1)))
    if remainder != (F(0),):
        raise ProofHold("HOLD_REFLECTION_FACTORIZATION_FAILED")
    if any(quotient[i] != 0 for i in range(1, len(quotient), 2)):
        raise ProofHold("HOLD_EVEN_QUOTIENT_FAILED")
    R = trim(list(quotient[::2]))
    if forward_normal_form(R) != P:
        raise ProofHold("HOLD_REPLAY_MISMATCH")
    return R


def _fraction_vector(xs: object, max_len: int) -> tuple[F, ...]:
    if not isinstance(xs, list) or not xs or len(xs) > max_len:
        raise ProofHold("HOLD_VECTOR_DIMENSIONS")
    return tuple(rational(x) for x in xs)


def check_reflection(statement: dict) -> dict:
    _keys(statement, {"coefficients_s_ascending"})
    P = poly(statement["coefficients_s_ascending"])
    R = inverse_normal_form(P)
    return {
        "claim": "P(0)=P(1)=0 and P(1-s)=-P(s) as Q[s] identities",
        "checked_scope": "ALL_COMPLEX_S_BY_POLYNOMIAL_IDENTITY",
        "degree": len(P) - 1,
        "P_s_ascending": [fmt(v) for v in P],
        "R_u_ascending": [fmt(v) for v in R],
        "proof_rule": "P(s)=(s-1/2)((s-1/2)^2-1/4)R((s-1/2)^2)",
        "source_theorem": "exact symbolic normal form, replayed from input coefficients",
        "analytic_claims": [
            "G(s)=P(s)Phi(s) requires Mellin integration-by-parts hypotheses",
            "Phi(1-s)=Phi(s) requires real-even bump hypotheses",
            "full explicit formula, universal Weil positivity, and RH are OPEN",
        ],
    }


def check_gram(statement: dict) -> dict:
    _keys(statement, {"matrix", "vectors", "weights"})
    A_raw, V_raw, W_raw = statement["matrix"], statement["vectors"], statement["weights"]
    if not isinstance(A_raw, list) or not (1 <= len(A_raw) <= MAX_DIMENSION):
        raise ProofHold("HOLD_GRAM_DIMENSIONS")
    n = len(A_raw)
    A = [_fraction_vector(row, MAX_DIMENSION) for row in A_raw]
    if any(len(row) != n for row in A):
        raise ProofHold("HOLD_GRAM_NOT_SQUARE")
    if any(A[i][j] != A[j][i] for i in range(n) for j in range(n)):
        raise ProofHold("HOLD_GRAM_NOT_SYMMETRIC")
    if (not isinstance(V_raw, list) or not isinstance(W_raw, list) or
            not V_raw or len(V_raw) != len(W_raw) or len(V_raw) > MAX_DIMENSION):
        raise ProofHold("HOLD_GRAM_DECOMPOSITION_LENGTH")
    V = [_fraction_vector(row, MAX_DIMENSION) for row in V_raw]
    if any(len(v) != n for v in V):
        raise ProofHold("HOLD_GRAM_VECTOR_WIDTH")
    W = [rational(w) for w in W_raw]
    if any(w < 0 for w in W):
        raise ProofHold("HOLD_NEGATIVE_SOS_WEIGHT")
    B = [tuple(sum((w * v[i] * v[j] for w, v in zip(W, V)), F(0))
               for j in range(n)) for i in range(n)]
    if A != B:
        raise ProofHold("HOLD_SOS_MATRIX_EQUALITY_FAILED")
    return {
        "claim": "forall x in R^n, x^T A x = sum_i w_i (v_i^T x)^2 >= 0",
        "checked_scope": "ALL_REAL_VECTORS_IN_DECLARED_FINITE_DIMENSION",
        "matrix": [[fmt(q) for q in row] for row in A],
        "vectors": [[fmt(q) for q in row] for row in V],
        "weights": [fmt(q) for q in W],
        "dimension": n,
        "proof_rule": "exact rational matrix coefficient comparison + nonnegative weights",
        "analytic_claims": ["No identification with the full Weil form Q(g) has been established"],
    }


def check_cutoff(statement: dict) -> dict:
    _keys(statement, {"delta"})
    d = rational(statement["delta"])
    if not (0 < 2 * d < 1):
        raise ProofHold("HOLD_SUPPORT_DELTA_RANGE")
    upper = 1 / (1 - 2 * d)
    if not upper < 2:
        raise ProofHold("HOLD_NO_PRIME_CUTOFF")
    return {
        "claim": "IF supp(g)⊆[exp(-d),exp(d)], THEN A_g(n)=A_g(1/n)=0 for every integer n>=2",
        "checked_scope": "CONDITIONAL_SUPPORT_TO_ALL_PRIME_POWERS",
        "delta": fmt(d),
        "exp_2delta_strict_upper_bound": fmt(upper),
        "proof_rule": "0<x<1 -> exp(x)<=1/(1-x); monotonicity; ratio support of autocorrelation",
        "analytic_claims": [
            "Support premise, regularity and normalization dy must be discharged against actual Lean definitions",
            "Prime cutoff eliminates no zero-side spectral terms and does not imply RH",
        ],
    }


def compile_statement(request: dict) -> dict:
    _keys(request, {"schema", "kind", "statement"})
    if request["schema"] != SCHEMA or not isinstance(request["kind"], str) or request["kind"] not in ALLOWED:
        raise ProofHold("HOLD_UNKNOWN_CLAIM_OR_RH_QUANTIFIER")
    kind = request["kind"]
    if kind == "reflection_polynomial":
        checked = check_reflection(request["statement"])
    elif kind == "finite_gram_sos":
        checked = check_gram(request["statement"])
    else:
        checked = check_cutoff(request["statement"])
    result = {
        "schema": SCHEMA,
        "kind": kind,
        "statement": request["statement"],
        "checked": checked,
        "authority_class": "NONE",
        "local_exact_arithmetic_checked": True,
        "lean_kernel_checked": False,
        "riemann_hypothesis_proven": False,
        "rh_obligations": [
            "exact-source full Weil explicit-formula identity",
            "universal Weil positivity for all admissible g",
            "proof term for the unmodified Mathlib RiemannHypothesis",
        ],
    }
    result["receipt_sha256"] = hashlib.sha256(canonical(result)).hexdigest()
    return result


def verify_receipt(receipt: dict) -> bool:
    if not isinstance(receipt, dict) or set(receipt) != {
        "schema", "kind", "statement", "checked", "authority_class",
        "local_exact_arithmetic_checked", "lean_kernel_checked",
        "riemann_hypothesis_proven", "rh_obligations", "receipt_sha256",
    }:
        raise ProofHold("HOLD_RECEIPT_SCHEMA")
    root = {k: receipt[k] for k in ("schema", "kind", "statement")}
    replay = compile_statement(root)
    if canonical(replay) != canonical(receipt):
        raise ProofHold("HOLD_RECEIPT_REPLAY_MISMATCH")
    return True



def project_wit_receipt(receipt: dict) -> dict:
    """Project a REPLAYED arithmetic receipt onto the RFC-0001 WIT record.

    The native WIT compiler checks structure, not mathematical correctness.
    We therefore replay the exact arithmetic before creating a typed projection.
    ``statement_sha256`` binds the original typed request, not just the result.
    False Lean/RH fields are hard-coded; neither a caller nor a parser can
    promote a local calculation to a kernel proof or global conjecture.
    """
    verify_receipt(receipt)
    request = {k: receipt[k] for k in ("schema", "kind", "statement")}
    return {
        "kind": receipt["kind"],
        "state": ("conditional_support" if receipt["kind"] == "support_prime_cutoff"
                  else "local_exact"),
        "statement_sha256": hashlib.sha256(canonical(request)).hexdigest(),
        "receipt_sha256": receipt["receipt_sha256"],
        "scope": receipt["checked"]["checked_scope"],
        "authority_class": "NONE",
        "lean_kernel_checked": False,
        "riemann_hypothesis_proven": False,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aegis-mira-rh", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compile", help="compile a typed exact proof obligation")
    c.add_argument("input")
    c.add_argument("--out")
    v = sub.add_parser("verify", help="independently replay issued receipt")
    v.add_argument("receipt")
    t = sub.add_parser("project", help="replay then export exact WIT-contract JSON")
    t.add_argument("receipt")
    args = ap.parse_args(argv)
    try:
        if args.command == "compile":
            result = compile_statement(load_json(args.input))
            txt = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
            if args.out:
                Path(args.out).write_text(txt, encoding="utf-8")
            else:
                print(txt, end="")
        elif args.command == "verify":
            verify_receipt(load_json(args.receipt))
            print("VERIFIED_LOCAL_EXACT_RECEIPT (NOT_LEAN, RH_OPEN)")
        else:
            typed = project_wit_receipt(load_json(args.receipt))
            print(json.dumps(typed, indent=2, sort_keys=True))
        return 0
    except (ProofHold, OSError) as err:
        print(f"HOLD: {err}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
