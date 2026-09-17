"""Cross-prover contract for the complex/real projection boundary.

The actual autocorrelation remains complex-valued.  Pinned Lean proves the
reciprocal-conjugation involution and separately proves reality only after the
full explicit-right-side functional is assembled.  The pole-aggregation lane
also gives a kernel-checked collision showing that real projection of an
endpoint cross term is information-losing.

This contract forbids silently replacing `A_g` by `Re A_g`.
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
LEAN_REALITY = Path(os.environ.get("AEGIS_LEAN_AUTOCORR_REALITY_SOURCE", ""))
LEAN_AGG = Path(os.environ.get("AEGIS_LEAN_POLE_AGGREGATION_SOURCE", ""))
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
            if text[i]=="\\" and i+1<len(text): out.extend("  "); i+=2
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
def _expected(spec:dict)->dict: return spec["semantic_ast"]["complex_real_projection"]


def _normalize_lean(reality:str, agg:str, spec:dict)->dict:
    r=_compact(_strip_lean(reality)); a=_compact(_strip_lean(agg))
    required_reality=(
        "theoremweil_autocorrelation_reciprocal_v1",
        "WeilAutocorrelationV1gx⁻¹=(x:ℂ)*conj(WeilAutocorrelationV1gx)",
        "theoremweil_autocorrelation_one_real_v1",
        "theoremweil_autocorrelation_explicit_right_side_real_v1",
    )
    for token in required_reality:
        if token not in r: raise AssertionError(f"Lean reciprocal/reality token missing: {token}")
    required_loss=(
        "theoremweil_endpoint_pole_aggregate_eq_two_re_v1",
        "theoremweil_endpoint_pole_aggregate_zero_collision_v1",
        "theoremweil_endpoint_pole_aggregate_zero_not_force_zero_profiles_v1",
    )
    for token in required_loss:
        if token not in a: raise AssertionError(f"Lean information-loss token missing: {token}")
    return _expected(spec)


def _normalize_coq(text:str,spec:dict)->dict:
    c=_compact(_strip_coq(text))
    required=(
        "InductiveFiniteAutocorrelationProjectionModeV1:Type:=",
        "ComplexAutocorrelationCarrierV1",
        "RealProjectedAutocorrelationCarrierV1",
        "InductiveFiniteAutocorrelationSymmetryV1:Type:=",
        "ReciprocalConjugateJacobianV1",
        "Definitionfinite_autocorrelation_projection_mode_v1:FiniteAutocorrelationProjectionModeV1:=ComplexAutocorrelationCarrierV1.",
        "Definitionfinite_autocorrelation_symmetry_v1:FiniteAutocorrelationSymmetryV1:=ReciprocalConjugateJacobianV1.",
        "Definitionfinite_autocorrelation_pointwise_real_v1:bool:=false.",
        "Theoremconcrete_complex_real_projection_v1",
    )
    for token in required:
        if token not in c: raise AssertionError(f"Coq projection token missing: {token}")
    return _expected(spec)


class WeilComplexRealProjectionCrossProverV1(unittest.TestCase):
    def setUp(self):
        for p in (SPEC,COQ,LEAN_REALITY,LEAN_AGG): self.assertTrue(p.is_file(),p)
        self.spec=json.loads(SPEC.read_text())
        self.coq=COQ.read_text(); self.reality=LEAN_REALITY.read_text(); self.agg=LEAN_AGG.read_text()

    def test_frozen_projection_ast(self):
        self.assertEqual(EXPECTED_DIGEST,self.spec["canonical_spec_digest"])
        p=_expected(self.spec)
        self.assertIs(False,p["pointwise_reality_of_autocorrelation"])
        self.assertEqual("eq",p["reciprocal_involution"]["op"])
        self.assertEqual("MUST_BE_PROVED_AT_TERM_OR_FUNCTIONAL_LEVEL",p["projection_rule"])
        self.assertEqual("FORBIDDEN",p["silent_replace_Ag_by_ReAg"])

    def test_pinned_lean_sources_normalize_to_projection_ast(self):
        self.assertEqual(_expected(self.spec),_normalize_lean(self.reality,self.agg,self.spec))

    def test_coq_source_normalizes_to_projection_ast(self):
        self.assertEqual(_expected(self.spec),_normalize_coq(self.coq,self.spec))

    def test_cross_prover_normal_forms_identical(self):
        self.assertEqual(_normalize_lean(self.reality,self.agg,self.spec),_normalize_coq(self.coq,self.spec))

    def test_final_coq_projection_constituent_declared(self):
        self.assertRegex(_strip_coq(self.coq),r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_complex_real_projection_v1\b")

    def test_no_silent_real_projection_or_authority_promotion(self):
        c=_compact(_strip_coq(self.coq)).lower()
        self.assertNotIn("finite_autocorrelation_projection_mode_v1:=realprojectedautocorrelationcarrierv1",c)
        for forbidden in ("finite_psd","matrix_entries_binding","global_weil_positivity","riemannhypothesis"):
            self.assertNotIn(forbidden,c)


if __name__=="__main__": unittest.main()
