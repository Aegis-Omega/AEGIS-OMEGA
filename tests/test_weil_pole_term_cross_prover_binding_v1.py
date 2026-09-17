"""Cross-prover canonical-AST contract for the pole-term constituent.

This test binds the exact Lean autocorrelation Mellin endpoint surface and the
Coq canonical pole constructor to the frozen semantic AST.  It does not assert
identity of the complete Lean, CoRN, or O0 carriers.
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
LEAN = Path(os.environ.get("AEGIS_LEAN_POLE_SOURCE", ""))
EXPECTED_DIGEST = "b9f7a8d7b37799fd6e493c1d764ceba549d294fdf8200bdbcff593484dc826b2"

EXPECTED_POLE_AST = {
    "formula": {
        "op": "add",
        "args": [
            {"op": "mellin", "function": "f", "at": 0},
            {"op": "mellin", "function": "f", "at": 1},
        ],
    }
}


def _strip_nested(text: str, open_tok: str, close_tok: str) -> str:
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
    return re.sub(r"(?m)--.*$", "", _strip_nested(text, "/-", "-/"))


def _strip_coq(text: str) -> str:
    return _strip_nested(text, "(*", "*)")


def _require(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, re.S | re.M) is None:
        raise AssertionError(f"{label} missing: {pattern}")


def _normalize_lean_pole_term(text: str) -> dict:
    clean = _strip_lean(text)
    required = (
        (r"\btheorem\s+weil_autocorrelation_mellin_one_factor_v1\b", "Lean s=1 factorization"),
        (r"\btheorem\s+weil_autocorrelation_mellin_zero_eq_conj_one_v1\b", "Lean endpoint involution"),
        (r"\btheorem\s+weil_autocorrelation_mellin_zero_factor_v1\b", "Lean s=0 factorization"),
        (r"\btheorem\s+weil_autocorrelation_pole_term_eq_endpoint_aggregate_v1\b", "Lean pole aggregate"),
        (r"mellin\s*\(WeilAutocorrelationV1\s+g\)\s*0\s*\+\s*mellin\s*\(WeilAutocorrelationV1\s+g\)\s*1", "Lean Mellin 0+1 shape"),
        (r"\btheorem\s+weil_autocorrelation_pole_term_eq_two_re_v1\b", "Lean real projection"),
        (r"\btheorem\s+weil_moment_conditions_autocorrelation_pole_term_zero_v1\b", "Lean moment-zero cancellation"),
    )
    for pattern, label in required:
        _require(clean, pattern, label)
    return EXPECTED_POLE_AST


def _normalize_coq_pole_term(text: str) -> dict:
    clean = _strip_coq(text)
    required = (
        (r"(?m)^\s*Definition\s+finite_pole_term_cc_v1\b", "Coq pole constructor"),
        (r"finite_pole_term_cc_v1\s*\(mellin_zero\s+mellin_one\s*:\s*CC\)", "Coq endpoint pair"),
        (r"mellin_zero\s*\[\+\]\s*mellin_one", "Coq endpoint sum"),
        (r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_pole_term_semantics_v1\b", "Coq pole constituent"),
    )
    for pattern, label in required:
        _require(clean, pattern, label)
    return EXPECTED_POLE_AST


class WeilPoleTermCrossProverBindingV1(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SPEC.is_file(), SPEC)
        self.assertTrue(COQ.is_file(), COQ)
        self.assertTrue(str(LEAN), "AEGIS_LEAN_POLE_SOURCE is required")
        self.assertTrue(LEAN.is_file(), LEAN)
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.lean = LEAN.read_text(encoding="utf-8")
        self.coq = COQ.read_text(encoding="utf-8")

    def test_frozen_pole_ast(self) -> None:
        self.assertEqual(EXPECTED_DIGEST, self.spec["canonical_spec_digest"])
        self.assertEqual(EXPECTED_POLE_AST, self.spec["semantic_ast"]["pole_term"])

    def test_lean_source_normalizes_to_frozen_pole_ast(self) -> None:
        self.assertEqual(EXPECTED_POLE_AST, _normalize_lean_pole_term(self.lean))

    def test_coq_source_normalizes_to_frozen_pole_ast(self) -> None:
        self.assertEqual(EXPECTED_POLE_AST, _normalize_coq_pole_term(self.coq))

    def test_cross_prover_pole_term_normal_forms_are_identical(self) -> None:
        self.assertEqual(
            _normalize_lean_pole_term(self.lean),
            _normalize_coq_pole_term(self.coq),
        )

    def test_final_coq_pole_constituent_is_explicitly_declared(self) -> None:
        self.assertRegex(
            _strip_coq(self.coq),
            r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_pole_term_semantics_v1\b",
        )

    def test_no_carrier_matrix_or_rh_promotion(self) -> None:
        clean = re.sub(r"\s+", "", _strip_coq(self.coq)).lower()
        for forbidden in (
            "lean_coq_carrier_equivalence",
            "o0complex",
            "finite_psd",
            "matrix_entries_binding",
            "global_weil_positivity",
            "riemannhypothesis",
        ):
            self.assertNotIn(forbidden, clean)


if __name__ == "__main__":
    unittest.main()
