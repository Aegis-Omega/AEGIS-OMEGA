"""Preregistered RED contract for isolated finite Guinand-Weil semantics V1.

This test intentionally lands before the production Coq module.  The first
hosted run must therefore fail at the missing production source.  The contract
prevents PR #1 from silently importing finite-matrix/PSD/globalization evidence
or from replacing theorem closure with metadata.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIL = ROOT / "sovereign-omega-v2" / "formal" / "theories" / "Weil"
SOURCE = WEIL / "ConcreteFiniteGuinandWeilSemanticsV1.v"

CONSTITUENT_THEOREMS = (
    "concrete_index_semantics_v1",
    "concrete_von_mangoldt_semantics_v1",
    "concrete_prime_term_semantics_v1",
    "concrete_pole_term_semantics_v1",
    "concrete_archimedean_normalization_v1",
    "concrete_cutoff_semantics_v1",
    "concrete_measure_semantics_v1",
    "concrete_autocorrelation_semantics_v1",
    "concrete_fourier_mellin_normalization_v1",
    "concrete_complex_real_projection_v1",
    "concrete_sign_orientation_v1",
)
FINAL_THEOREM = "concrete_finite_guinand_weil_semantics_v1"

# PR #1 is semantics-only.  These modules belong to matrix/PSD/globalization
# layers or to the historical mixed semantics branch and are forbidden even
# through a local re-export.
FORBIDDEN_LOCAL_MODULES = {
    "FiniteBridge",
    "Globalization",
    "ConcreteFiniteWeil",
    "FiniteDictionary",
    "FiniteEntryDictionary",
    "ConcreteGlobalizationInstantiation",
}

FORBIDDEN_DOWNSTREAM_TOKENS = (
    "FiniteLowerBoundV1",
    "pointwise_converges_v1",
    "vanishing_nonnegative_error_v1",
    "GlobalizationReadyV1",
    "GlobalizationTargetV1",
    "GlobalWeilPositivityV1",
)


def _strip_coq_comments_and_strings(text: str) -> str:
    """Remove nested Coq comments and string payloads while preserving lines."""
    out: list[str] = []
    i = 0
    depth = 0
    in_string = False
    while i < len(text):
        if depth:
            if text.startswith("(*", i):
                depth += 1
                out.extend("  ")
                i += 2
            elif text.startswith("*)", i):
                depth -= 1
                out.extend("  ")
                i += 2
            else:
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            continue

        if in_string:
            if text[i] == '"':
                # Coq strings may escape a quote by doubling it.
                if i + 1 < len(text) and text[i + 1] == '"':
                    out.extend("  ")
                    i += 2
                else:
                    in_string = False
                    out.append(" ")
                    i += 1
            else:
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            continue

        if text.startswith("(*", i):
            depth = 1
            out.extend("  ")
            i += 2
        elif text[i] == '"':
            in_string = True
            out.append(" ")
            i += 1
        else:
            out.append(text[i])
            i += 1

    if depth:
        raise AssertionError("unterminated Coq comment")
    if in_string:
        raise AssertionError("unterminated Coq string")
    return "".join(out)


def _local_imports(path: Path) -> set[str]:
    clean = _strip_coq_comments_and_strings(path.read_text(encoding="utf-8"))
    imports: set[str] = set()

    # Require Import A B. / Require Export A B.
    for match in re.finditer(
        r"(?m)^\s*Require\s+(?:Import|Export)\s+([^.]*)\.", clean
    ):
        imports.update(match.group(1).split())

    # From Prefix Require Import A B.  Only resolve names that actually exist
    # as sibling modules; standard-library imports are ignored by closure walk.
    for match in re.finditer(
        r"(?m)^\s*From\s+\S+\s+Require\s+(?:Import|Export)\s+([^.]*)\.",
        clean,
    ):
        imports.update(match.group(1).split())
    return imports


def _transitive_local_dependencies(start: Path) -> set[str]:
    seen: set[str] = set()
    stack = list(_local_imports(start))
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        seen.add(module)
        local = WEIL / f"{module}.v"
        if local.is_file():
            stack.extend(_local_imports(local) - seen)
    return seen


class ConcreteFiniteGuinandWeilSemanticsV1Contract(unittest.TestCase):
    def setUp(self) -> None:
        # RED-1: production theorem source is intentionally absent in the
        # preregistration commit.  This is the first expected failure.
        self.assertTrue(
            SOURCE.is_file(),
            "RED_EXPECTED: ConcreteFiniteGuinandWeilSemanticsV1.v is absent",
        )
        self.raw = SOURCE.read_text(encoding="utf-8")
        self.clean = _strip_coq_comments_and_strings(self.raw)

    def test_all_constituent_and_final_theorems_are_declared(self) -> None:
        for theorem in (*CONSTITUENT_THEOREMS, FINAL_THEOREM):
            self.assertRegex(
                self.clean,
                rf"(?m)^\s*(?:Theorem|Lemma)\s+{re.escape(theorem)}\b",
                theorem,
            )

    def test_no_global_trust_shortcuts(self) -> None:
        forbidden_declarations = re.compile(
            r"(?m)^\s*(?:Axiom|Axioms|Parameter|Parameters|Conjecture)\b"
        )
        self.assertIsNone(forbidden_declarations.search(self.clean))
        self.assertIsNone(re.search(r"(?m)^\s*Admitted\s*\.", self.clean))
        self.assertIsNone(re.search(r"\badmit\b", self.clean))

    def test_forbidden_dependencies_are_absent_transitively(self) -> None:
        closure = _transitive_local_dependencies(SOURCE)
        leaked = sorted(closure & FORBIDDEN_LOCAL_MODULES)
        self.assertEqual([], leaked, f"forbidden transitive dependencies: {leaked}")

    def test_no_downstream_globalization_obligations_are_encoded(self) -> None:
        for token in FORBIDDEN_DOWNSTREAM_TOKENS:
            self.assertNotIn(token, self.clean, token)

    def test_semantics_surface_does_not_encode_matrix_or_psd_claims(self) -> None:
        # Matrix representation/PSD belongs to PR #2/#3.  Names are checked in
        # executable source, after comments/strings are removed.
        for token in (
            "concrete_finite_matrix_entries_v1",
            "concrete_finite_quadratic_form_binding_v1",
            "finite_psd",
            "exact_ldlt",
        ):
            self.assertNotIn(token, self.clean, token)


if __name__ == "__main__":
    unittest.main()
