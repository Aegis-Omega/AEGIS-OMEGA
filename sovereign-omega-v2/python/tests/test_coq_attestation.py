import json
import tempfile
import unittest
from pathlib import Path

from coq_attestation import (
    build_receipt,
    inspect_coq_source,
    parse_print_assumptions,
)


ROOT = Path(__file__).resolve().parents[2]
FORMAL = ROOT / "formal" / "theories"


class CoqSourceInventoryTests(unittest.TestCase):
    def test_current_formal_inventory_matches_repo_evidence(self) -> None:
        expected = {
            "Core/LatticeConvergence.v": (9, 0, 0, 0),
            "Core/LockIrreversibility.v": (8, 0, 0, 0),
            "Bisimulation/ThreeWay.v": (0, 1, 2, 0),
            "Core/Hash.v": (0, 0, 1, 0),
            "Core/Reducer.v": (1, 0, 0, 0),
            "Core/Event.v": (0, 0, 0, 0),
        }
        for relative, counts in expected.items():
            manifest = inspect_coq_source(FORMAL / relative)
            actual = (
                manifest["qed_count"],
                manifest["axiom_statement_count"],
                manifest["parameter_statement_count"],
                manifest["admitted_count"],
            )
            self.assertEqual(actual, counts, relative)

    def test_comment_tokens_do_not_contaminate_source_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CommentOnly.v"
            path.write_text(
                "(* Axiom fake : False. Parameter fake2 : nat. Admitted. *)\n"
                "Theorem real : True. Proof. exact I. Qed.\n",
                encoding="utf-8",
            )
            manifest = inspect_coq_source(path)
            self.assertEqual(manifest["qed_count"], 1)
            self.assertEqual(manifest["axiom_statement_count"], 0)
            self.assertEqual(manifest["parameter_statement_count"], 0)
            self.assertEqual(manifest["admitted_count"], 0)
            self.assertEqual(manifest["theorem_names"], ["real"])


class PrintAssumptionsParserTests(unittest.TestCase):
    def test_closed_theorem_is_axiom_free(self) -> None:
        parsed = parse_print_assumptions("Closed under the global context\n")
        self.assertTrue(parsed["closed_under_global_context"])
        self.assertEqual(parsed["assumption_lines"], [])

    def test_axiom_bearing_theorem_is_not_closed(self) -> None:
        parsed = parse_print_assumptions(
            "Axioms:\nsha256 : list Byte.byte -> list Byte.byte\n"
        )
        self.assertFalse(parsed["closed_under_global_context"])
        self.assertEqual(
            parsed["assumption_lines"],
            ["sha256 : list Byte.byte -> list Byte.byte"],
        )

    def test_unrecognized_output_fails_closed(self) -> None:
        parsed = parse_print_assumptions("unexpected prover output\n")
        self.assertFalse(parsed["closed_under_global_context"])
        self.assertEqual(parsed["parse_status"], "UNRECOGNIZED")


class CoqReceiptTests(unittest.TestCase):
    def test_receipt_separates_compile_status_from_axiom_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            sources = tmp_path / "formal"
            assumptions = tmp_path / "assumptions"
            assumptions.mkdir(parents=True)
            sources.mkdir(parents=True)

            clean = sources / "Clean.v"
            clean.write_text("Theorem clean : True. Proof. exact I. Qed.\n", encoding="utf-8")
            assumed = sources / "Assumed.v"
            assumed.write_text(
                "Parameter p : Prop.\nTheorem assumed : p -> p. Proof. auto. Qed.\n",
                encoding="utf-8",
            )
            broken = sources / "Broken.v"
            broken.write_text("Theorem broken : True. Proof.\n", encoding="utf-8")

            (assumptions / "Clean__clean.txt").write_text(
                "Closed under the global context\n", encoding="utf-8"
            )
            (assumptions / "Assumed__assumed.txt").write_text(
                "Axioms:\np : Prop\n", encoding="utf-8"
            )
            compile_status = tmp_path / "compile-status.json"
            compile_status.write_text(
                json.dumps(
                    {
                        "Clean.v": {"status": "COMPILED", "log_sha256": "a" * 64},
                        "Assumed.v": {"status": "COMPILED", "log_sha256": "b" * 64},
                        "Broken.v": {"status": "COMPILE_FAILED", "log_sha256": "c" * 64},
                    }
                ),
                encoding="utf-8",
            )

            receipt = build_receipt(
                formal_root=sources,
                compile_status_path=compile_status,
                assumptions_root=assumptions,
                source_commit="d" * 40,
                coq_version="8.20.1",
            )
            by_path = {entry["path"]: entry for entry in receipt["files"]}
            self.assertEqual(by_path["Clean.v"]["attestation"], "AXIOM_FREE")
            self.assertEqual(by_path["Assumed.v"]["attestation"], "ASSUMPTION_BEARING")
            self.assertEqual(by_path["Broken.v"]["attestation"], "COMPILE_FAILED")
            self.assertEqual(receipt["summary"]["compile_failures"], 1)
            self.assertEqual(receipt["summary"]["axiom_free_theorems"], 1)
            self.assertEqual(receipt["summary"]["assumption_bearing_theorems"], 1)
            self.assertEqual(receipt["authority"], "FORMAL_MATH_EVIDENCE_ONLY")
            self.assertRegex(receipt["receipt_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
