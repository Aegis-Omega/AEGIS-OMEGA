import hashlib
import itertools
import unittest

from coq_attestation import parse_print_assumptions


class PrintAssumptionsOutputIntegrityTests(unittest.TestCase):
    def assert_unrecognized(self, output: str) -> None:
        parsed = parse_print_assumptions(output)
        self.assertEqual(parsed["parse_status"], "UNRECOGNIZED")
        self.assertFalse(parsed["closed_under_global_context"])
        self.assertEqual(parsed["assumption_lines"], [])
        self.assertEqual(parsed["assumption_symbols"], [])
        self.assertEqual(
            parsed["raw_sha256"], hashlib.sha256(output.encode("utf-8")).hexdigest()
        )

    def test_multiple_result_headers_are_rejected(self) -> None:
        results = (
            "Closed under the global context\n",
            "Axioms:\nExternal.p : Prop\n",
            "Assumptions:\nExternal.q : Prop\n",
        )
        for first, second in itertools.product(results, repeat=2):
            with self.subTest(first=first, second=second):
                self.assert_unrecognized(first + second)

    def test_error_diagnostics_are_rejected_before_or_after_results(self) -> None:
        results = (
            "Closed under the global context\n",
            "Axioms:\nExternal.p : Prop\n",
            "Assumptions:\nExternal.p : Prop\n",
        )
        diagnostics = (
            "Error: The reference missing was not found.\n",
            "Anomaly: Uncaught exception.\n",
            "Fatal error: exception Failure\n",
            "Uncaught exception Failure\n",
        )
        for result, diagnostic in itertools.product(results, diagnostics):
            for output in (diagnostic + result, result + diagnostic):
                with self.subTest(output=output):
                    self.assert_unrecognized(output)

    def test_empty_or_unrecognized_assumptions_block_is_rejected(self) -> None:
        for header, body in itertools.product(
            ("Axioms:", "Assumptions:"),
            ("", "\n  \n", "unexpected prover output\n", "External.p :\n"),
        ):
            with self.subTest(header=header, body=body):
                self.assert_unrecognized(header + "\n" + body)

    def test_extra_output_around_closed_result_is_rejected(self) -> None:
        closed = "Closed under the global context\n"
        for output in ("unexpected output\n" + closed, closed + "unexpected output\n"):
            with self.subTest(output=output):
                self.assert_unrecognized(output)

    def test_extra_output_before_assumptions_is_rejected(self) -> None:
        self.assert_unrecognized("unexpected output\nAxioms:\nExternal.p : Prop\n")

    def test_closed_result_allows_surrounding_whitespace(self) -> None:
        output = "\n  Closed under the global context  \n\n"
        parsed = parse_print_assumptions(output)
        self.assertEqual(parsed["parse_status"], "CLOSED")
        self.assertTrue(parsed["closed_under_global_context"])
        self.assertEqual(
            parsed["raw_sha256"], hashlib.sha256(output.encode("utf-8")).hexdigest()
        )

    def test_multiline_assumption_types_preserve_symbols_and_evidence(self) -> None:
        for header in ("Axioms:", "Assumptions:"):
            with self.subTest(header=header):
                output = (
                    header + "\n"
                    "External.choice : forall (A : Type) (P : A -> Prop),\n"
                    "  (exists x, P x) ->\n"
                    "  {x : A | P x}\n"
                    "External.p : Prop\n"
                )
                parsed = parse_print_assumptions(output)
                self.assertEqual(parsed["parse_status"], "ASSUMPTIONS_PRESENT")
                self.assertFalse(parsed["closed_under_global_context"])
                self.assertEqual(
                    parsed["assumption_symbols"], ["External.choice", "External.p"]
                )
                self.assertEqual(
                    parsed["assumption_lines"],
                    [
                        "External.choice : forall (A : Type) (P : A -> Prop),",
                        "(exists x, P x) ->",
                        "{x : A | P x}",
                        "External.p : Prop",
                    ],
                )

    def test_wrapped_colon_preserves_name_and_raw_assumption_lines(self) -> None:
        parsed = parse_print_assumptions(
            "Axioms:\nExternal.long_assumption_name\n"
            "  : forall P : Prop,\n    P -> P\n"
        )
        self.assertEqual(parsed["parse_status"], "ASSUMPTIONS_PRESENT")
        self.assertEqual(parsed["assumption_symbols"], ["External.long_assumption_name"])
        self.assertEqual(
            parsed["assumption_lines"],
            ["External.long_assumption_name", ": forall P : Prop,", "P -> P"],
        )

    def test_error_named_namespace_is_not_a_diagnostic(self) -> None:
        parsed = parse_print_assumptions("Axioms:\nError.p : Prop\n")
        self.assertEqual(parsed["parse_status"], "ASSUMPTIONS_PRESENT")
        self.assertEqual(parsed["assumption_symbols"], ["Error.p"])

    def test_historical_coqtop_closed_result_with_preamble(self) -> None:
        # Captured Core__LockIrreversibility__aoie_not_pre_lock.txt, Coq 8.20.1.
        output = (
            "[WARNING] Running as root is not recommended\n"
            "Welcome to Coq 8.20.1\n\n"
            "Coq < \nCoq < \n"
            "Coq < Fetching opaque proofs from disk for LockIrreversibility\n"
            "Closed under the global context\n\nCoq < \n"
        )
        parsed = parse_print_assumptions(output)
        self.assertEqual(parsed["parse_status"], "CLOSED")
        self.assertTrue(parsed["closed_under_global_context"])
        self.assertEqual(
            parsed["raw_sha256"], hashlib.sha256(output.encode("utf-8")).hexdigest()
        )

    def test_historical_plugin_preamble_and_multiline_assumptions(self) -> None:
        # Informational forms and assumption body from the O0 trust-probe logs.
        parsed = parse_print_assumptions(
            "[WARNING] Running as root is not recommended\n"
            "Welcome to Coq 8.20.1\nCoq < \n"
            "Coq < [Loading ML file ring_plugin.cmxs (using legacy method) ... done]\n"
            "[Loading ML file zify_plugin.cmxs (using legacy method) ... done]\n"
            "Coq < Fetching opaque proofs from disk for O0TrustProbeCompact\n"
            "Fetching opaque proofs from disk for Coq.Init.Logic\n"
            "Axioms:\n"
            "ClassicalDedekindReals.sig_forall_dec :\n"
            "  forall P : nat -> Prop,\n"
            "  (forall n : nat, {P n} + {~ P n}) ->\n"
            "  {n : nat | ~ P n} + {forall n : nat, P n}\n"
            "FunctionalExtensionality.functional_extensionality_dep :\n"
            "  forall (A : Type) (B : A -> Type) (f g : forall x : A, B x),\n"
            "  (forall x : A, f x = g x) -> f = g\n\nCoq < \n"
        )
        self.assertEqual(parsed["parse_status"], "ASSUMPTIONS_PRESENT")
        self.assertEqual(
            parsed["assumption_symbols"],
            [
                "ClassicalDedekindReals.sig_forall_dec",
                "FunctionalExtensionality.functional_extensionality_dep",
            ],
        )
        self.assertEqual(len(parsed["assumption_lines"]), 7)

    def test_fetching_prefix_without_interactive_banner_is_supported(self) -> None:
        for result, status in (
            ("Closed under the global context\n", "CLOSED"),
            ("Axioms:\nHash.sha256 : Prop\n", "ASSUMPTIONS_PRESENT"),
        ):
            with self.subTest(result=result):
                parsed = parse_print_assumptions(
                    "Fetching opaque proofs from disk for Coq.Init.Logic\n" + result
                )
                self.assertEqual(parsed["parse_status"], status)

    def test_allowed_preamble_does_not_hide_errors_or_multiple_results(self) -> None:
        prefix = "Coq < Fetching opaque proofs from disk for Coq.Init.Logic\n"
        closed = "Coq < Closed under the global context\n"
        for tail in (
            "Coq < Error: missing theorem\n",
            "Coq < Anomaly: exception\n",
            "Coq < Axioms:\nExternal.p : Prop\n",
            "Coq < Closed under the global context\n",
        ):
            with self.subTest(tail=tail):
                self.assert_unrecognized(prefix + closed + tail)
                self.assert_unrecognized(prefix + tail + closed)

    def test_informational_prefix_allowlist_is_anchored(self) -> None:
        for prefix in (
            "Fetching opaque proofs from disk for Module Error: failure\n",
            "Fetching opaque proofs from disk for ../Module\n",
            "[Loading ML file ring_plugin.cmxs (using legacy method) ... failed]\n",
            "[WARNING] An unexpected prover warning\n",
            "Welcome to Coq 8.20.1 Error: failure\n",
        ):
            with self.subTest(prefix=prefix):
                self.assert_unrecognized(prefix + "Closed under the global context\n")

    def test_informational_messages_are_only_allowed_before_result(self) -> None:
        for result in (
            "Closed under the global context\n",
            "Axioms:\nExternal.p : Prop\n",
        ):
            with self.subTest(result=result):
                self.assert_unrecognized(
                    result + "Fetching opaque proofs from disk for Coq.Init.Logic\n"
                )


if __name__ == "__main__":
    unittest.main()
