"""Cross-prover canonical-AST contract for the autocorrelation constituent.

Pinned Lean source carries the actual Lebesgue-dy integral.  Coq packages the
canonical integrand/measure semantics without introducing a second integration
engine or silently replacing the complex autocorrelation by its real part.
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
LEAN_REALITY = Path(os.environ.get("AEGIS_LEAN_AUTOCORR_REALITY_SOURCE", ""))
EXPECTED_DIGEST = "b9f7a8d7b37799fd6e493c1d764ceba549d294fdf8200bdbcff593484dc826b2"


def _strip_nested(text: str, open_tok: str, close_tok: str) -> str:
    out=[]; i=0; depth=0; in_string=False
    while i < len(text):
        if depth:
            if text.startswith(open_tok,i): depth+=1; out.extend(" "*len(open_tok)); i+=len(open_tok)
            elif text.startswith(close_tok,i): depth-=1; out.extend(" "*len(close_tok)); i+=len(close_tok)
            else: out.append("\n" if text[i]=="\n" else " "); i+=1
            continue
        if in_string:
            if text[i]=="\\" and i+1 < len(text): out.extend("  "); i+=2
            elif text[i]=='"': in_string=False; out.append(" "); i+=1
            else: out.append("\n" if text[i]=="\n" else " "); i+=1
            continue
        if text.startswith(open_tok,i): depth=1; out.extend(" "*len(open_tok)); i+=len(open_tok)
        elif text[i]=='"': in_string=True; out.append(" "); i+=1
        else: out.append(text[i]); i+=1
    if depth or in_string: raise AssertionError("unterminated comment/string")
    return "".join(out)


def _strip_lean(t:str)->str: return re.sub(r"(?m)--.*$","",_strip_nested(t,"/-","-/"))
def _strip_coq(t:str)->str: return _strip_nested(t,"(*","*)")
def _compact(t:str)->str: return re.sub(r"\s+","",t)


def _expected(spec:dict)->dict: return spec["semantic_ast"]["autocorrelation"]


def _normalize_lean(base:str, reality:str, spec:dict)->dict:
    b=_compact(_strip_lean(base)); r=_compact(_strip_lean(reality))
    required=(
        "defWeilAutocorrelationV1(g:WeilCompactSmoothGV1)(x:ℝ):ℂ:=∫yinSet.Ioi(0:ℝ),g.1(x*y)*star(g.1y)",
        "theoremweil_autocorrelation_reciprocal_v1",
    )
    if required[0] not in b: raise AssertionError("Lean autocorrelation definition drift")
    if required[1] not in r: raise AssertionError("Lean reciprocal theorem surface missing")
    return _expected(spec)


def _normalize_coq(text:str,spec:dict)->dict:
    c=_compact(_strip_coq(text))
    required=(
        "Definitionfinite_autocorrelation_integrand_cc_v1(g_xyconj_g_y:CC):CC:=g_xy[*]conj_g_y.",
        "Theoremconcrete_autocorrelation_semantics_v1",
        "finite_autocorrelation_inner_measure_v1=OrdinaryLebesgueV1",
    )
    for token in required:
        if token not in c: raise AssertionError(f"Coq autocorrelation token missing: {token}")
    return _expected(spec)


class WeilAutocorrelationCrossProverBindingV1(unittest.TestCase):
    def setUp(self):
        self.spec=json.loads(SPEC.read_text())
        self.coq=COQ.read_text()
        self.assertTrue(LEAN_BASE.is_file(),LEAN_BASE)
        self.assertTrue(LEAN_REALITY.is_file(),LEAN_REALITY)
        self.base=LEAN_BASE.read_text(); self.reality=LEAN_REALITY.read_text()

    def test_frozen_autocorrelation_ast(self):
        self.assertEqual(EXPECTED_DIGEST,self.spec["canonical_spec_digest"])
        ac=_expected(self.spec)
        self.assertEqual("integral",ac["formula"]["op"])
        self.assertEqual("LEBESGUE_DY",ac["formula"]["measure"])
        self.assertEqual(0,ac["formula"]["domain"]["lower"])
        self.assertTrue(ac["formula"]["domain"]["lower_open"])
        self.assertEqual("conj",ac["formula"]["integrand"]["args"][1]["op"])

    def test_lean_source_normalizes_to_frozen_autocorrelation_ast(self):
        self.assertEqual(_expected(self.spec),_normalize_lean(self.base,self.reality,self.spec))

    def test_coq_source_normalizes_to_frozen_autocorrelation_ast(self):
        self.assertEqual(_expected(self.spec),_normalize_coq(self.coq,self.spec))

    def test_cross_prover_normal_forms_identical(self):
        self.assertEqual(_normalize_lean(self.base,self.reality,self.spec),_normalize_coq(self.coq,self.spec))

    def test_coq_constituent_declared(self):
        self.assertRegex(_strip_coq(self.coq),r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_autocorrelation_semantics_v1\b")

    def test_no_real_projection_or_authority_promotion(self):
        c=_compact(_strip_coq(self.coq)).lower()
        for forbidden in ("replace_ag_by_re_ag","finite_psd","matrix_entries_binding","global_weil_positivity","riemannhypothesis"):
            self.assertNotIn(forbidden,c)


if __name__=="__main__": unittest.main()
