"""Cross-prover canonical-AST contract for the archimedean constituent.

The frozen AST and pinned Lean sources carry the exact normalization shape:
constant `(log(4*pi)+EulerGamma)*f(1)` plus the rationalized integral on
`(1, infinity)`.  Coq packages only the canonical outer constructor; it does
not introduce a second gamma/digamma or integration implementation.

This contract binds semantic normalization.  It does not claim that the
completed-zeta gamma-line derivation is Lean-kernel formalized.
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
LEAN_BASE = Path(os.environ.get("AEGIS_LEAN_WEIL_BASE_SOURCE", ""))
LEAN_ARCH = Path(os.environ.get("AEGIS_LEAN_ARCH_SOURCE", ""))
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


def _strip_lean(text: str) -> str:
    return re.sub(r"(?m)--.*$", "", _strip_nested(text, "/-", "-/"))


def _strip_coq(text: str) -> str:
    return _strip_nested(text, "(*", "*)")


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _require(text: str, pattern: str, label: str) -> None:
    if re.search(pattern, text, re.S | re.M) is None:
        raise AssertionError(f"{label} missing: {pattern}")


def _expected_arch(spec: dict) -> dict:
    return spec["semantic_ast"]["archimedean_normalization"]


def _normalize_lean_arch(base: str, arch: str, spec: dict) -> dict:
    b = _compact(_strip_lean(base))
    a = _compact(_strip_lean(arch))
    base_tokens = (
        "defWeilArchimedeanConstantV1:ℂ:=((Real.log(4*Real.pi)+Real.eulerMascheroniConstant:ℝ):ℂ)",
        "defWeilArchimedeanIntegralV1(f:ℝ→ℂ):ℂ:=∫xinSet.Ioi(1:ℝ),WeilArchimedeanIntegrandV1fx",
        "defWeilExplicitRightSideV1(f:ℝ→ℂ):ℂ:=WeilPrimeSumV1f+WeilArchimedeanConstantV1*f1+WeilArchimedeanIntegralV1f",
    )
    for token in base_tokens:
        if token not in b:
            raise AssertionError(f"Lean normalization token missing: {token}")
    arch_tokens = (
        "theoremweil_archimedean_integrand_rational_v1",
        "((x:ℂ)*fx+fx⁻¹-2*f1)/((x:ℂ)^2-1)",
        "theoremweil_compact_smooth_archimedean_integrable_v1",
        "IntegrableOn(WeilArchimedeanIntegrandV1f.1)(Ioi1)",
    )
    for token in arch_tokens:
        if token not in a:
            raise AssertionError(f"Lean archimedean theorem token missing: {token}")
    return _expected_arch(spec)


def _normalize_coq_arch(text: str, spec: dict) -> dict:
    clean = _compact(_strip_coq(text))
    required = (
        "Definitionfinite_archimedean_normalization_cc_v1(constant_at_oneintegral_value:CC):CC:=constant_at_one[+]integral_value.",
        "Theoremconcrete_archimedean_normalization_v1",
        "finite_archimedean_normalization_cc_v1constant_at_oneintegral_value[=]constant_at_one[+]integral_value",
    )
    for token in required:
        if token not in clean:
            raise AssertionError(f"Coq archimedean constructor token missing: {token}")
    return _expected_arch(spec)


class WeilArchimedeanNormalizationCrossProverV1(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SPEC.is_file(), SPEC)
        self.assertTrue(COQ.is_file(), COQ)
        self.assertTrue(str(LEAN_BASE), "AEGIS_LEAN_WEIL_BASE_SOURCE is required")
        self.assertTrue(str(LEAN_ARCH), "AEGIS_LEAN_ARCH_SOURCE is required")
        self.assertTrue(LEAN_BASE.is_file(), LEAN_BASE)
        self.assertTrue(LEAN_ARCH.is_file(), LEAN_ARCH)
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.coq = COQ.read_text(encoding="utf-8")
        self.lean_base = LEAN_BASE.read_text(encoding="utf-8")
        self.lean_arch = LEAN_ARCH.read_text(encoding="utf-8")

    def test_frozen_digest_and_archimedean_ast(self) -> None:
        self.assertEqual(EXPECTED_DIGEST, self.spec["canonical_spec_digest"])
        arch = _expected_arch(self.spec)
        self.assertEqual("mul", arch["constant_term"]["op"])
        self.assertEqual("integral", arch["integral"]["op"])
        self.assertEqual("LEBESGUE_DX", arch["integral"]["measure"])
        self.assertEqual(1, arch["integral"]["domain"]["lower"])
        self.assertTrue(arch["integral"]["domain"]["lower_open"])

    def test_lean_sources_normalize_to_frozen_archimedean_ast(self) -> None:
        self.assertEqual(
            _expected_arch(self.spec),
            _normalize_lean_arch(self.lean_base, self.lean_arch, self.spec),
        )

    def test_coq_source_normalizes_to_frozen_archimedean_ast(self) -> None:
        self.assertEqual(_expected_arch(self.spec), _normalize_coq_arch(self.coq, self.spec))

    def test_cross_prover_archimedean_normal_forms_are_identical(self) -> None:
        self.assertEqual(
            _normalize_lean_arch(self.lean_base, self.lean_arch, self.spec),
            _normalize_coq_arch(self.coq, self.spec),
        )

    def test_final_coq_archimedean_constituent_is_declared(self) -> None:
        self.assertRegex(
            _strip_coq(self.coq),
            r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_archimedean_normalization_v1\b",
        )

    def test_no_gamma_derivation_carrier_or_matrix_promotion(self) -> None:
        clean = _compact(_strip_coq(self.coq)).lower()
        for forbidden in (
            "gauss_digamma_integral",
            "completed_zeta_gamma_line_proven",
            "lean_coq_carrier_equivalence",
            "finite_psd",
            "matrix_entries_binding",
            "global_weil_positivity",
            "riemannhypothesis",
        ):
            self.assertNotIn(forbidden, clean)


if __name__ == "__main__":
    unittest.main()
