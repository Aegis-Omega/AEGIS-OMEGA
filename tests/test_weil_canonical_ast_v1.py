"""Fail-closed canonical AST contract for FINITE_GUINAND_WEIL_SPEC_V1.

The digest commits only to the mathematical semantic AST. Proof status,
repository admission, CI state, and authority state are deliberately outside
the preimage so digest identity cannot be promoted to theorem truth.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "sovereign-omega-v2" / "formal" / "specs" / "FINITE_GUINAND_WEIL_SPEC_V1.json"

EXPECTED_SCHEMA = "FINITE_GUINAND_WEIL_SPEC_V1"
EXPECTED_PROFILE = "WEIL_CANONICAL_AST_V1"
EXPECTED_DIGEST = "b9f7a8d7b37799fd6e493c1d764ceba549d294fdf8200bdbcff593484dc826b2"
EXPECTED_SURFACES = {
    "index",
    "von_mangoldt",
    "prime_term",
    "pole_term",
    "archimedean_normalization",
    "cutoff",
    "measure",
    "autocorrelation",
    "fourier_mellin_normalization",
    "complex_real_projection",
    "sign_orientation",
}
FORBIDDEN_STATE_KEYS = {
    "same_spec_digest",
    "semantic_equivalence_proven",
    "matrix_entries_binding",
    "quadratic_form_matrix_binding",
    "finite_psd",
    "finite_lower_bound",
    "pointwise_convergence",
    "vanishing_error",
    "global_weil_positivity",
    "rh",
    "authority_effect",
    "accepted",
    "pass",
}


def _reject_duplicate_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AssertionError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _walk(value):
    yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _canonical_semantic_bytes(data: dict) -> bytes:
    preimage = {
        "schema": data["spec_schema"],
        "semantic_ast": data["semantic_ast"],
    }
    return (
        b"WEIL_CANONICAL_AST_V1\0"
        + json.dumps(
            preimage,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


class FiniteGuinandWeilCanonicalAstV1(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SPEC.is_file(), f"missing canonical semantic AST: {SPEC}")
        self.data = json.loads(
            SPEC.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )

    def test_top_level_is_semantics_only(self) -> None:
        self.assertEqual(
            {"spec_schema", "digest_profile", "canonical_spec_digest", "semantic_ast"},
            set(self.data),
        )
        self.assertEqual(EXPECTED_SCHEMA, self.data["spec_schema"])
        self.assertEqual(EXPECTED_PROFILE, self.data["digest_profile"])

    def test_exact_eleven_surfaces(self) -> None:
        self.assertEqual(EXPECTED_SURFACES, set(self.data["semantic_ast"]))

    def test_digest_commits_only_to_schema_and_semantic_ast(self) -> None:
        digest = hashlib.sha256(_canonical_semantic_bytes(self.data)).hexdigest()
        self.assertEqual(EXPECTED_DIGEST, digest)
        self.assertEqual(EXPECTED_DIGEST, self.data["canonical_spec_digest"])

    def test_profile_has_no_float_or_mutable_proof_state(self) -> None:
        for value in _walk(self.data["semantic_ast"]):
            self.assertFalse(
                isinstance(value, float),
                f"float forbidden in canonical AST: {value!r}",
            )
        keys = set()

        def collect(value):
            if isinstance(value, dict):
                keys.update(value)
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(self.data["semantic_ast"])
        self.assertTrue(FORBIDDEN_STATE_KEYS.isdisjoint(keys))

    def test_prime_term_is_functional_not_basis_or_matrix(self) -> None:
        ast = self.data["semantic_ast"]
        self.assertEqual(0, ast["index"]["leading_m1"]["von_mangoldt_value"])
        self.assertEqual("SEMANTICALLY_INERT", ast["index"]["leading_m1"]["role"])
        constraints = ast["von_mangoldt"]["prime_power_case"]["constraints"]
        self.assertEqual("prime", constraints[0]["op"])
        self.assertEqual("eq", constraints[2]["op"])
        formula = ast["prime_term"]["formula"]
        self.assertEqual("mul", formula["op"])
        self.assertEqual("von_mangoldt", formula["args"][0]["op"])
        self.assertNotIn("matrix", json.dumps(formula).lower())
        self.assertNotIn("sine", json.dumps(formula).lower())
        self.assertNotIn("cos", json.dumps(formula).lower())

    def test_cutoff_is_index_semantics_not_positivity(self) -> None:
        cutoff = self.data["semantic_ast"]["cutoff"]
        self.assertEqual("LEADING_TERM_ZERO", cutoff["equivalence_obligation"]["kind"])
        self.assertEqual(0, cutoff["equivalence_obligation"]["required_value"])
        self.assertEqual("FORBIDDEN", cutoff["positivity_implication"])

    def test_measure_projection_and_sign_guards(self) -> None:
        ast = self.data["semantic_ast"]
        self.assertEqual("LEBESGUE_DY", ast["measure"]["autocorrelation_measure"])
        self.assertEqual("DY_OVER_Y", ast["measure"]["excluded_measure"])
        projection = ast["complex_real_projection"]
        self.assertIs(False, projection["pointwise_reality_of_autocorrelation"])
        self.assertEqual("eq", projection["reciprocal_involution"]["op"])
        self.assertEqual("FORBIDDEN", projection["silent_replace_Ag_by_ReAg"])
        self.assertEqual(
            "NOT_IMPLIED",
            ast["sign_orientation"]["sign_inequality_from_identity"],
        )

    def test_load_bearing_formulas_are_ast_nodes_not_formula_strings(self) -> None:
        ast = self.data["semantic_ast"]
        nodes = (
            ast["prime_term"]["formula"],
            ast["pole_term"]["formula"],
            ast["archimedean_normalization"]["constant_term"],
            ast["archimedean_normalization"]["integral"],
            ast["autocorrelation"]["formula"],
            ast["fourier_mellin_normalization"]["fourier_forward"],
            ast["fourier_mellin_normalization"]["fourier_inverse"],
            ast["fourier_mellin_normalization"]["mellin"],
            ast["complex_real_projection"]["reciprocal_involution"],
            ast["sign_orientation"]["explicit_identity"],
            ast["sign_orientation"]["moment_zero_autocorrelation_identity"],
        )
        for node in nodes:
            self.assertIsInstance(node, dict)
            self.assertIn("op", node)


if __name__ == "__main__":
    unittest.main()
