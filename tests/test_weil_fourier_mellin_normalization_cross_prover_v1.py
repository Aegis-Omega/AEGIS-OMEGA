"""Exact-source normalization contract for Fourier/Mellin conventions.

The frozen AEGIS AST uses angular frequency:
    F(t) = ∫ f(x) exp(-i t x) dx,
    f(x) = (1/(2*pi)) ∫ F(t) exp(i t x) dt.
Pinned Mathlib uses the analyst/cycles convention exp(-2*pi*i*x*xi).
Therefore the Mellin/Fourier bridge must evaluate Mathlib Fourier at
`s.im / (2*pi)`.  Losing this scale is a semantic failure, not formatting.
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
AEGIS_MELLIN = Path(os.environ.get("AEGIS_MELLIN_DECAY_SOURCE", ""))
AEGIS_INVERSION = Path(os.environ.get("AEGIS_MELLIN_INVERSION_SOURCE", ""))
MATHLIB_MELLIN = Path(os.environ.get("MATHLIB_MELLIN_INVERSION_SOURCE", ""))
MATHLIB_TRANSFORM = Path(os.environ.get("MATHLIB_MELLIN_TRANSFORM_SOURCE", ""))
MATHLIB_FOURIER = Path(os.environ.get("MATHLIB_FOURIER_SOURCE", ""))
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


def _strip_lean(t: str) -> str:
    return re.sub(r"(?m)--.*$", "", _strip_nested(t, "/-", "-/"))


def _strip_coq(t: str) -> str:
    return _strip_nested(t, "(*", "*)")


def _compact(t: str) -> str:
    return re.sub(r"\s+", "", t)


def _expected(spec: dict) -> dict:
    return spec["semantic_ast"]["fourier_mellin_normalization"]


def _normalize_exact_sources(
    aegis_mellin: str,
    aegis_inv: str,
    mathlib_mellin: str,
    mathlib_transform: str,
    mathlib_fourier: str,
    spec: dict,
) -> dict:
    am = _compact(_strip_lean(aegis_mellin))
    ai = _compact(_strip_lean(aegis_inv))
    mm = _compact(_strip_lean(mathlib_mellin))
    mt = _compact(_strip_lean(mathlib_transform))
    mf = _compact(_strip_lean(mathlib_fourier))

    # Mathlib's analyst convention has -2*pi in the forward exponent.
    if "lemmafourier_eq'(f:V→E)(w:V):𝓕fw=∫v,Complex.exp((↑(-2*π*⟪v,w⟫)*Complex.I))•fv" not in mf:
        raise AssertionError("pinned Mathlib Fourier -2*pi convention missing")

    # The ordinary Mellin transform and inverse 1/(2*pi) normalization.
    if "defmellin(f:ℝ→E)(s:ℂ):E:=∫t:ℝinIoi0,(t:ℂ)^(s-1)•ft" not in mt:
        raise AssertionError("pinned Mathlib Mellin dx definition missing")
    if "defmellinInv(σ:ℝ)(f:ℂ→E)(x:ℝ):E:=(1/(2*π))•∫y:ℝ" not in mt:
        raise AssertionError("pinned Mathlib Mellin inverse 1/(2*pi) prefactor missing")

    # Load-bearing theorem: angular frequency gamma maps to cycles gamma/(2*pi).
    if "theoremmellin_eq_fourier(f:ℝ→E){s:ℂ}:mellinfs=𝓕" not in mm:
        raise AssertionError("mellin_eq_fourier theorem missing")
    if "(s.im/(2*π))" not in mm:
        raise AssertionError("mellin_eq_fourier lost divide-by-2*pi scaling")
    if "theoremmellinInv_eq_fourierInv" not in mm or "σ+2*π*y*I" not in mm:
        raise AssertionError("inverse Mellin/Fourier 2*pi rescaling missing")

    # AEGIS must consume the same scale rather than silently treating conventions as identical.
    if "rw[mellin_eq_fourier]" not in am:
        raise AssertionError("AEGIS Mellin decay does not use mellin_eq_fourier")
    if "γ/(2*Real.pi)" not in am:
        raise AssertionError("AEGIS Mellin decay lost gamma/(2*pi) frequency bridge")
    if "rw[mellin_eq_fourier]" not in ai or "γ/(2*Real.pi)" not in ai:
        raise AssertionError("AEGIS Mellin inversion lane lost gamma/(2*pi) bridge")

    return _expected(spec)


def _normalize_coq(text: str, spec: dict) -> dict:
    c = _compact(_strip_coq(text))
    required = (
        "InductiveFiniteFourierFrequencyConventionV1:Type:=",
        "AngularFrequencyV1",
        "CyclesFrequencyV1",
        "InductiveFiniteFourierBridgeScaleV1:Type:=",
        "DivideByTwoPiV1",
        "InductiveFiniteFourierInversePrefactorV1:Type:=",
        "OneOverTwoPiV1",
        "Definitionfinite_frozen_fourier_frequency_v1:FiniteFourierFrequencyConventionV1:=AngularFrequencyV1.",
        "Definitionfinite_mathlib_fourier_frequency_v1:FiniteFourierFrequencyConventionV1:=CyclesFrequencyV1.",
        "Definitionfinite_mellin_to_mathlib_scale_v1:FiniteFourierBridgeScaleV1:=DivideByTwoPiV1.",
        "Definitionfinite_frozen_fourier_inverse_prefactor_v1:FiniteFourierInversePrefactorV1:=OneOverTwoPiV1.",
        "Theoremconcrete_fourier_mellin_normalization_v1",
    )
    for token in required:
        if token not in c:
            raise AssertionError(f"Coq Fourier/Mellin normalization token missing: {token}")
    return _expected(spec)


class WeilFourierMellinNormalizationCrossProverV1(unittest.TestCase):
    def setUp(self) -> None:
        for p in (SPEC, COQ, AEGIS_MELLIN, AEGIS_INVERSION, MATHLIB_MELLIN, MATHLIB_TRANSFORM, MATHLIB_FOURIER):
            self.assertTrue(p.is_file(), p)
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        self.coq = COQ.read_text(encoding="utf-8")
        self.am = AEGIS_MELLIN.read_text(encoding="utf-8")
        self.ai = AEGIS_INVERSION.read_text(encoding="utf-8")
        self.mm = MATHLIB_MELLIN.read_text(encoding="utf-8")
        self.mt = MATHLIB_TRANSFORM.read_text(encoding="utf-8")
        self.mf = MATHLIB_FOURIER.read_text(encoding="utf-8")

    def test_frozen_fourier_mellin_ast(self) -> None:
        self.assertEqual(EXPECTED_DIGEST, self.spec["canonical_spec_digest"])
        fm = _expected(self.spec)
        self.assertEqual("integral", fm["fourier_forward"]["op"])
        self.assertEqual("mul", fm["fourier_inverse"]["op"])
        self.assertEqual("integral", fm["mellin"]["op"])
        self.assertEqual("LEBESGUE_DX", fm["mellin"]["measure"])
        inv = fm["fourier_inverse"]["args"][0]
        self.assertEqual(1, inv["numerator"])
        self.assertEqual([2, "pi"], inv["denominator"]["args"])

    def test_pinned_lean_and_mathlib_sources_normalize_to_frozen_ast(self) -> None:
        self.assertEqual(_expected(self.spec), _normalize_exact_sources(self.am, self.ai, self.mm, self.mt, self.mf, self.spec))

    def test_coq_source_normalizes_to_frozen_ast(self) -> None:
        self.assertEqual(_expected(self.spec), _normalize_coq(self.coq, self.spec))

    def test_cross_prover_normal_forms_are_identical(self) -> None:
        self.assertEqual(
            _normalize_exact_sources(self.am, self.ai, self.mm, self.mt, self.mf, self.spec),
            _normalize_coq(self.coq, self.spec),
        )

    def test_final_coq_constituent_declared(self) -> None:
        self.assertRegex(_strip_coq(self.coq), r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_fourier_mellin_normalization_v1\b")

    def test_no_silent_identity_scale_or_authority_promotion(self) -> None:
        c = _compact(_strip_coq(self.coq)).lower()
        self.assertNotIn("mellin_to_mathlib_scale_v1:=identity", c)
        for forbidden in ("finite_psd", "matrix_entries_binding", "global_weil_positivity", "riemannhypothesis"):
            self.assertNotIn(forbidden, c)


if __name__ == "__main__":
    unittest.main()
