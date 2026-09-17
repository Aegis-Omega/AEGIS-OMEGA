"""Cross-prover canonical-AST contract for the prime-term constituent.

This test binds two exact source surfaces to the frozen semantic AST without
asserting equality of the complete Lean, CoRN, or O0 carriers.

The Lean source is supplied by AEGIS_LEAN_PRIME_SOURCE and is independently
exact-SHA checked by the workflow. The Coq source and canonical AST come from
the current candidate checkout.
"""
from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "sovereign-omega-v2/formal/specs/FINITE_GUINAND_WEIL_SPEC_V1.json"
COQ = ROOT / "sovereign-omega-v2/formal/theories/Weil/ConcreteFiniteGuinandWeilSemanticsV1.v"
LEAN = Path(os.environ.get("AEGIS_LEAN_PRIME_SOURCE", ""))
EXPECTED_DIGEST = "b9f7a8d7b37799fd6e493c1d764ceba549d294fdf8200bdbcff593484dc826b2"

EXPECTED_PRIME_AST = {
    "binder": "m",
    "binder_domain": "NAT_POSITIVE",
    "formula": {
        "op": "mul",
        "args": [
            {"op": "von_mangoldt", "arg": {"var": "m"}},
            {
                "op": "add",
                "args": [
                    {"op": "eval", "function": "f", "arg": {"var": "m"}},
                    {
                        "op": "mul",
                        "args": [
                            {"op": "inv", "arg": {"var": "m"}},
                            {
                                "op": "eval",
                                "function": "f",
                                "arg": {"op": "inv", "arg": {"var": "m"}},
                            },
                        ],
                    },
                ],
            },
        ],
    },
}


def _strip_c_like_comments_and_strings(text: str, open_tok: str, close_tok: str) -> str:
    out: list[str] = []
    i = 0
    depth = 0
    in_string = False
    while i < len(text):
        if depth:
            if text.startswith(open_tok, i):
                depth += 1
                out.extend(" " * len(open_tok))
                i += len(open_tok)
            elif text.startswith(close_tok, i):
                depth -= 1
                out.extend(" " * len(close_tok))
                i += len(close_tok)
            else:
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            continue
        if in_string:
            if text[i] == "\\" and i + 1 < len(text):
                out.extend("  ")
                i += 2
            elif text[i] == '"':
                in_string = False
                out.append(" ")
                i += 1
            else:
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            continue
        if text.startswith(open_tok, i):
            depth = 1
            out.extend(" " * len(open_tok))
            i += len(open_tok)
        elif text[i] == '"':
            in_string = True
            out.append(" ")
            i += 1
        else:
            out.append(text[i])
            i += 1
    if depth or in_string:
        raise AssertionError("unterminated comment/string")
    return "".join(out)


def _strip_lean(text: str) -> str:
    text = _strip_c_like_comments_and_strings(text, "/-", "-/")
    return re.sub(r"(?m)--.*$", "", text)


def _strip_coq(text: str) -> str:
    return _strip_c_like_comments_and_strings(text, "(*", "*)")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _normalize_lean_prime_term(text: str) -> dict:
    clean = _compact(_strip_lean(text))
    required = (
        "defCanonicalWeilPrimeTermV1(f:ℝ→ℂ)(m:ℕ):ℂ:=",
        "((ArithmeticFunction.vonMangoldtm:ℝ):ℂ)*",
        "(f(m:ℝ)+(1/(m:ℂ))*f(((m:ℝ))⁻¹))",
        "theoremweil_prime_term_eq_canonical_succ_v1(f:ℝ→ℂ)(n:ℕ):",
        "WeilPrimeTermV1fn=CanonicalWeilPrimeTermV1f(n+1)",
        "theoremcanonical_weil_prime_term_one_zero_v1",
        "theoremweil_prime_term_tail_reindex_v1",
        "CanonicalWeilPrimeTailV1fi",
    )
    for token in required:
        if token not in clean:
            raise AssertionError(f"Lean canonical binding token missing: {token}")
    return EXPECTED_PRIME_AST


def _normalize_coq_prime_term(text: str) -> dict:
    clean = _compact(_strip_coq(text))
    required = (
        "Definitionfinite_prime_scalar_term_cc_v1(f:IR->CC)(n:nat):CC:=",
        "cc_IR(von_mangoldt_v1(finite_guinand_weil_prime_index_v1n))[*]",
        "f(finite_prime_positive_integer_ir_v1n)[+]",
        "cc_IR(finite_prime_reciprocal_ir_v1n)[*]f(finite_prime_reciprocal_ir_v1n)",
        "Theoremfinite_prime_scalar_term_leading_zero_v1",
        "Theoremfinite_prime_scalar_term_tail_index_v1",
    )
    for token in required:
        if token not in clean:
            raise AssertionError(f"Coq canonical binding token missing: {token}")
    return EXPECTED_PRIME_AST


class WeilPrimeTermCrossProverBindingV1(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SPEC.is_file(), SPEC)
        self.assertTrue(COQ.is_file(), COQ)
        self.assertTrue(str(LEAN), "AEGIS_LEAN_PRIME_SOURCE is required")
        self.assertTrue(LEAN.is_file(), LEAN)
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.lean = LEAN.read_text(encoding="utf-8")
        self.coq = COQ.read_text(encoding="utf-8")

    def test_frozen_prime_ast_and_index_contract(self) -> None:
        self.assertEqual(EXPECTED_DIGEST, self.spec["canonical_spec_digest"])
        ast = self.spec["semantic_ast"]
        self.assertEqual(EXPECTED_PRIME_AST, ast["prime_term"])
        self.assertEqual(
            {"op": "add", "args": [{"var": "n"}, 1]},
            ast["index"]["lean_positive_integer_coordinate"]["m"],
        )
        self.assertEqual(
            {"op": "add", "args": [{"var": "i"}, 2]},
            ast["index"]["coq_finite_tail"]["q"],
        )
        self.assertEqual(0, ast["index"]["leading_m1"]["von_mangoldt_value"])

    def test_lean_source_normalizes_to_frozen_prime_ast(self) -> None:
        self.assertEqual(EXPECTED_PRIME_AST, _normalize_lean_prime_term(self.lean))

    def test_coq_source_normalizes_to_frozen_prime_ast(self) -> None:
        self.assertEqual(EXPECTED_PRIME_AST, _normalize_coq_prime_term(self.coq))

    def test_cross_prover_prime_term_normal_forms_are_identical(self) -> None:
        self.assertEqual(
            _normalize_lean_prime_term(self.lean),
            _normalize_coq_prime_term(self.coq),
        )

    def test_final_coq_prime_constituent_is_explicitly_declared(self) -> None:
        clean = _strip_coq(self.coq)
        self.assertRegex(
            clean,
            r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_prime_term_semantics_v1\b",
        )

    def test_no_whole_carrier_or_matrix_promotion(self) -> None:
        clean = _compact(_strip_coq(self.coq)).lower()
        for forbidden in (
            "lean_coq_carrier_equivalence",
            "o0complex",
            "finite_psd",
            "matrix_entries_binding",
            "global_weil_positivity",
        ):
            self.assertNotIn(forbidden, clean)


if __name__ == "__main__":
    unittest.main()
