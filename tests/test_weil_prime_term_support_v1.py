"""RED contract for the formula-level complex prime-term support layer.

This support layer is intentionally weaker than concrete_prime_term_semantics_v1.
It may prove the canonical complex scalar formula and the n+1 -> q=i+2 tail
reindexing, but it must not claim an O0/Lean carrier correspondence, matrix
semantics, PSD, or the final constituent theorem.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "sovereign-omega-v2"
    / "formal"
    / "theories"
    / "Weil"
    / "ConcreteFiniteGuinandWeilSemanticsV1.v"
)

REQUIRED_DECLARATIONS = (
    ("Definition", "finite_prime_positive_integer_ir_v1"),
    ("Definition", "finite_prime_reciprocal_ir_v1"),
    ("Definition", "finite_prime_scalar_term_cc_v1"),
    ("Definition", "canonical_q_reciprocal_ir_v1"),
    ("Definition", "canonical_q_prime_scalar_term_cc_v1"),
    ("Theorem", "finite_prime_scalar_term_leading_zero_v1"),
    ("Theorem", "finite_prime_scalar_term_tail_index_v1"),
)


def _strip_coq_comments_and_strings(text: str) -> str:
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
    if depth or in_string:
        raise AssertionError("unterminated Coq comment/string")
    return "".join(out)


class PrimeTermComplexSupportV1Contract(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(SOURCE.is_file())
        self.clean = _strip_coq_comments_and_strings(
            SOURCE.read_text(encoding="utf-8")
        )

    def test_constructive_complex_substrate_is_explicit(self) -> None:
        self.assertRegex(
            self.clean,
            r"(?m)^\s*Require\s+Import\s+CoRN\.complex\.CComplex\s*\.",
        )

    def test_required_support_declarations_exist(self) -> None:
        for kind, name in REQUIRED_DECLARATIONS:
            self.assertRegex(
                self.clean,
                rf"(?m)^\s*{kind}\s+{re.escape(name)}\b",
                name,
            )

    def test_scalar_term_uses_one_complex_function_and_canonical_lambda(self) -> None:
        match = re.search(
            r"(?ms)^\s*Definition\s+finite_prime_scalar_term_cc_v1\b(.*?)\.\s*$",
            self.clean,
        )
        self.assertIsNotNone(match)
        body = match.group(1)
        self.assertRegex(body, r"\bf\s*:\s*IR\s*->\s*CC\b")
        self.assertIn("von_mangoldt_v1", body)
        self.assertIn("cc_IR", body)
        self.assertIn("finite_prime_reciprocal_ir_v1", body)
        for forbidden in (
            "prime_source_term_v1",
            "FiniteBridge",
            "FiniteEntryDictionary",
            "matrix",
            "psd",
        ):
            self.assertNotIn(forbidden, body)

    def test_support_does_not_fake_final_carrier_binding(self) -> None:
        # The final constituent remains a separate theorem obligation. Merely
        # adding formula-level CC support must not auto-promote it.
        self.assertNotRegex(
            self.clean,
            r"(?m)^\s*(?:Theorem|Lemma)\s+concrete_prime_term_semantics_v1\b",
        )


if __name__ == "__main__":
    unittest.main()
