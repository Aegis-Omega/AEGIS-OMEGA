"""Exact-source provenance contract for the Weil sign orientation.

The frozen semantics fixes two orientations:
  Z(f) = Mellin(f,0) + Mellin(f,1) - WeilExplicitRightSideV1(f),
and, after the autocorrelation moment conditions remove the pole term,
  WeilExplicitRightSideV1(A_g) = - zero_sum(g).

The full normalized explicit identity is MATH_PROVED in the pinned #490 proof
note with explicitly listed external dependencies; this contract MUST NOT
promote it to a whole-identity Lean kernel theorem.  The pinned #507 Lean lane
provides kernel evidence for the autocorrelation pole cancellation used by the
moment-zero specialization.
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
PROOF_NOTE = Path(os.environ.get("AEGIS_WEIL_IDENTITY_PROOF_NOTE", ""))
LEAN_POLE = Path(os.environ.get("AEGIS_LEAN_POLE_AGGREGATION_SOURCE", ""))
EXPECTED_DIGEST = "b9f7a8d7b37799fd6e493c1d764ceba549d294fdf8200bdbcff593484dc826b2"


def _strip_nested(text: str, open_tok: str, close_tok: str) -> str:
    out: list[str] = []
    i = 0
    depth = 0
    in_string = False
    while i < len(text):
        if depth:
            if text.startswith(open_tok, i):
                depth += 1; out.extend(" " * len(open_tok)); i += len(open_tok)
            elif text.startswith(close_tok, i):
                depth -= 1; out.extend(" " * len(close_tok)); i += len(close_tok)
            else:
                out.append("\n" if text[i] == "\n" else " "); i += 1
            continue
        if in_string:
            if text[i] == "\\" and i + 1 < len(text):
                out.extend("  "); i += 2
            elif text[i] == '"':
                in_string = False; out.append(" "); i += 1
            else:
                out.append("\n" if text[i] == "\n" else " "); i += 1
            continue
        if text.startswith(open_tok, i):
            depth = 1; out.extend(" " * len(open_tok)); i += len(open_tok)
        elif text[i] == '"':
            in_string = True; out.append(" "); i += 1
        else:
            out.append(text[i]); i += 1
    if depth or in_string:
        raise AssertionError("unterminated comment/string")
    return "".join(out)


def _strip_coq(t: str) -> str:
    return _strip_nested(t, "(*", "*)")


def _strip_lean(t: str) -> str:
    return re.sub(r"(?m)--.*$", "", _strip_nested(t, "/-", "-/"))


def _compact(t: str) -> str:
    return re.sub(r"\s+", "", t)


def _expected(spec: dict) -> dict:
    return spec["semantic_ast"]["sign_orientation"]


def _normalize_math_and_lean(note: str, lean_pole: str, spec: dict) -> dict:
    n = _compact(note)
    l = _compact(_strip_lean(lean_pole))

    required_note = (
        "Status:**[MATH-PROVED]withtheexternaldependenciesexplicitlylistedbelow.**",
        "not a Lean certificate for the wholeidentity".replace(" ", ""),
        r"Z(f)=F(0)+F(1)-\operatorname{WeilExplicitRightSideV1}(f).",
        r"\operatorname{WeilExplicitRightSideV1}(f_g)=-\sum_\rhom_\rhoG(\rho)\overline{G(1-\overline\rho)}.",
        "Equation(Q)provesneithernonnegativityofthezeroexpressionnornonpositivityofthearithmeticexpression.",
    )
    for token in required_note:
        if token not in n:
            raise AssertionError(f"pinned mathematical sign-orientation token missing: {token}")

    required_lean = (
        "theoremweil_moment_conditions_autocorrelation_pole_term_zero_v1",
        "theoremweil_autocorrelation_pole_term_eq_endpoint_aggregate_v1",
        "theoremweil_autocorrelation_pole_term_eq_two_re_v1",
    )
    for token in required_lean:
        if token not in l:
            raise AssertionError(f"pinned Lean pole-cancellation token missing: {token}")

    return _expected(spec)


def _normalize_coq(text: str, spec: dict) -> dict:
    c = _compact(_strip_coq(text))
    required = (
        "InductiveFiniteExplicitIdentityOrientationV1:Type:=",
        "ZeroSideEqualsPoleMinusRhsV1",
        "InductiveFiniteMomentZeroOrientationV1:Type:=",
        "RhsEqualsNegativeZeroSumV1",
        "InductiveFiniteSignInferenceStatusV1:Type:=",
        "SignInequalityNotImpliedV1",
        "InductiveFiniteExplicitIdentityProofStatusV1:Type:=",
        "MathProvedExternalDependenciesV1",
        "WholeIdentityLeanKernelOpenV1",
        "Definitionfinite_explicit_identity_orientation_v1:FiniteExplicitIdentityOrientationV1:=ZeroSideEqualsPoleMinusRhsV1.",
        "Definitionfinite_moment_zero_orientation_v1:FiniteMomentZeroOrientationV1:=RhsEqualsNegativeZeroSumV1.",
        "Definitionfinite_sign_inference_status_v1:FiniteSignInferenceStatusV1:=SignInequalityNotImpliedV1.",
        "Definitionfinite_explicit_identity_proof_status_v1:FiniteExplicitIdentityProofStatusV1:=MathProvedExternalDependenciesV1.",
        "Definitionfinite_whole_identity_lean_status_v1:FiniteExplicitIdentityProofStatusV1:=WholeIdentityLeanKernelOpenV1.",
        "Theoremconcrete_sign_orientation_v1",
    )
    for token in required:
        if token not in c:
            raise AssertionError(f"Coq sign-orientation token missing: {token}")
    return _expected(spec)


class WeilSignOrientationProvenanceV1(unittest.TestCase):
    def setUp(self) -> None:
        for p in (SPEC, COQ, PROOF_NOTE, LEAN_POLE):
            self.assertTrue(p.is_file(), p)
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.coq = COQ.read_text(encoding="utf-8")
        self.note = PROOF_NOTE.read_text(encoding="utf-8")
        self.lean = LEAN_POLE.read_text(encoding="utf-8")

    def test_frozen_sign_ast(self) -> None:
        self.assertEqual(EXPECTED_DIGEST, self.spec["canonical_spec_digest"])
        s = _expected(self.spec)
        self.assertEqual("eq", s["explicit_identity"]["op"])
        self.assertEqual("sub", s["explicit_identity"]["args"][1]["op"])
        self.assertEqual("neg", s["moment_zero_autocorrelation_identity"]["args"][1]["op"])
        self.assertEqual("NOT_IMPLIED", s["sign_inequality_from_identity"])

    def test_pinned_math_and_kernel_inputs_match_sign_ast(self) -> None:
        self.assertEqual(_expected(self.spec), _normalize_math_and_lean(self.note, self.lean, self.spec))

    def test_coq_source_normalizes_to_sign_ast(self) -> None:
        self.assertEqual(_expected(self.spec), _normalize_coq(self.coq, self.spec))

    def test_provenance_and_coq_normal_forms_are_identical(self) -> None:
        self.assertEqual(
            _normalize_math_and_lean(self.note, self.lean, self.spec),
            _normalize_coq(self.coq, self.spec),
        )

    def test_final_coq_sign_constituent_declared(self) -> None:
        self.assertRegex(_strip_coq(self.coq), r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_sign_orientation_v1\b")

    def test_no_whole_identity_kernel_or_sign_promotion(self) -> None:
        c = _compact(_strip_coq(self.coq)).lower()
        self.assertNotIn("finite_sign_inference_status_v1:=signinequalityprovedv1", c)
        self.assertNotIn("finite_whole_identity_lean_status_v1:=wholeidentityleankernelprovedv1", c)
        for forbidden in ("global_weil_positivity", "riemannhypothesis", "rh_proven"):
            self.assertNotIn(forbidden, c)


if __name__ == "__main__":
    unittest.main()
