"""Focused negative controls for the bounded Lean axiom-log audit."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from verify_lean_axiom_surface import AuditError, audit_axiom_log


A = "AEGIS.WeilMixedLogKernelV27.mixedLogCorrelation_integrable_v27"
B = "AEGIS.WeilMixedLogKernelV27.mixedLogCorrelation_eq_mixed_v27"


def record(name=A, axioms="propext, Classical.choice, Quot.sound"):
    return f"'{name}' depends on axioms: [{axioms}]\n"


class AxiomAuditTests(unittest.TestCase):
    def test_exact_standard_closure(self):
        result = audit_axiom_log(record() + record(B, ""), [A, B])
        self.assertEqual(result[A], ["Classical.choice", "Quot.sound", "propext"])
        self.assertEqual(result[B], [])

    def test_multiline_official_output(self):
        log = f"'{A}' depends on axioms:\n[propext,\n Classical.choice,\n Quot.sound]\n"
        self.assertEqual(len(audit_axiom_log(log, [A])[A]), 3)

    def test_no_axioms_official_output(self):
        log = f"'{A}' does not depend on any axioms\n"
        self.assertEqual(audit_axiom_log(log, [A]), {A: []})

    def test_missing_record_and_empty_log(self):
        for log in ("", " \n", record()):
            with self.subTest(log=log), self.assertRaises(AuditError):
                audit_axiom_log(log, [A, B])

    def test_duplicate_records_and_contradictory_forms(self):
        none = f"'{A}' does not depend on any axioms\n"
        for log in (record() * 2, none * 2, record() + none, none + record()):
            with self.subTest(log=log), self.assertRaises(AuditError):
                audit_axiom_log(log, [A])

    def test_custom_sorry_and_native_trust_axioms(self):
        for axiom in ("sorryAx", "Aegis.hiddenAssumption", "Lean.ofReduceBool",
                      "Lean.trustCompiler", "Lean.ofReduceNat", "propextFake"):
            with self.subTest(axiom=axiom), self.assertRaises(AuditError):
                audit_axiom_log(record(axioms=f"propext, {axiom}"), [A])

    def test_extra_theorem_and_wrong_theorem(self):
        for log in (record(B), record() + record(B)):
            with self.subTest(log=log), self.assertRaises(AuditError):
                audit_axiom_log(log, [A])

    def test_malformed_and_embedded_output(self):
        for log in (record().replace("]", ""), record(axioms="propext,,Quot.sound"),
                    record(axioms="propext,"), record(axioms="propext propext"),
                    record(axioms="propext, propext"), record() + "warning: example\n",
                    "prefix " + record(), record().replace("]", "]junk"),
                    "\x1b[32m" + record(), record(axioms="propext\n'forged' []")):
            with self.subTest(log=log), self.assertRaises(AuditError):
                audit_axiom_log(log, [A])

    def test_requested_surface_must_be_nonempty_and_unique(self):
        for targets in ([], [A, A], [""], ["bad\nname"], ["bad'name"], [" name"]):
            with self.subTest(targets=targets), self.assertRaises(AuditError):
                audit_axiom_log(record(), targets)

    def test_cli_fail_closed_under_optimization(self):
        script = Path(__file__).with_name("verify_lean_axiom_surface.py")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "axioms.log"
            for optimized in (False, True):
                for log, expected in ((record(), 0), ("", 1),
                                      (record(axioms="sorryAx"), 1),
                                      (record(axioms="Lean.ofReduceBool"), 1),
                                      (record() * 2, 1)):
                    with self.subTest(optimized=optimized, log=log):
                        path.write_text(log, encoding="utf-8")
                        command = [sys.executable]
                        if optimized:
                            command.append("-O")
                        command += [str(script), "--log", str(path), "--theorem", A]
                        process = subprocess.run(command, text=True, capture_output=True)
                        self.assertEqual(process.returncode, expected, process.stderr)
                        self.assertIn("PASS" if expected == 0 else "FAIL",
                                      process.stdout if expected == 0 else process.stderr)


if __name__ == "__main__":
    unittest.main()
