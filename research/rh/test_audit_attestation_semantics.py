#!/usr/bin/env python3
"""Tests for the attestation-semantics auditor.

The point of the tool is that `Print Assumptions` closure and theorem content are
independent, so the tests pin both directions: a contentless theorem that IS
closed must be flagged, and a contentful theorem that is NOT closed must not be.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "audit_attestation_semantics.py")

CLOSED_RECEIPT = "Coq < Closed under the global context\n"
AXIOM_RECEIPT = (
    "Coq < Axioms:\n"
    "ClassicalDedekindReals.sig_not_dec : forall P : Prop, {~ ~ P} + {~ P}\n"
)

SOURCE = """
Definition Target (x : nat) : Prop := x = x.

Theorem tautology_thm :
  forall x : nat, Target x -> Target x.
Proof.
  intros x H. exact H.
Qed.

Theorem substantive_thm :
  forall x : nat, x + 0 = x.
Proof.
  intros x. induction x as [|k IH].
  - reflexivity.
  - simpl. rewrite IH. reflexivity.
Qed.
"""


class AuditTest(unittest.TestCase):
    def run_tool(self, receipts, strict=False, obligations=()):
        tmp = tempfile.mkdtemp()
        adir = os.path.join(tmp, "assumptions")
        sdir = os.path.join(tmp, "src")
        os.makedirs(adir)
        os.makedirs(sdir)
        with open(os.path.join(sdir, "Demo.v"), "w") as fh:
            fh.write(SOURCE)
        for name, body in receipts.items():
            with open(os.path.join(adir, name), "w") as fh:
                fh.write(body)
        out = os.path.join(tmp, "report.json")
        cmd = [sys.executable, TOOL, "--assumptions", adir,
               "--source-root", sdir, "--json", out]
        for ob in obligations:
            cmd += ["--obligation", ob]
        if strict:
            cmd.append("--strict")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        with open(out) as fh:
            return proc, json.load(fh)

    def test_closed_tautology_is_flagged_as_overstated(self):
        proc, rep = self.run_tool(
            {"Weil__Demo__tautology_thm.txt": CLOSED_RECEIPT}, strict=True)
        self.assertEqual(rep["closed"], 1)
        self.assertEqual(rep["tautologies"], 1)
        self.assertEqual(rep["overstated_closures"], ["Demo.tautology_thm"])
        self.assertEqual(proc.returncode, 1, "strict mode must fail the audit")

    def test_substantive_theorem_is_not_flagged(self):
        proc, rep = self.run_tool(
            {"Weil__Demo__substantive_thm.txt": CLOSED_RECEIPT}, strict=True)
        self.assertEqual(rep["substantive"], 1)
        self.assertEqual(rep["overstated_closures"], [])
        self.assertEqual(proc.returncode, 0)

    def test_axioms_are_reported_verbatim_and_do_not_overstate(self):
        # Not closed, but contentful: nothing is overstated, so strict passes.
        # The receipt uses the "Coq < Axioms:" prompt form that a coqtop session
        # emits; a bare "Axioms:" from coqc must parse identically.
        proc, rep = self.run_tool(
            {"Weil__Demo__substantive_thm.txt": AXIOM_RECEIPT}, strict=True)
        self.assertEqual(rep["closed"], 0)
        self.assertIn("sig_not_dec", rep["rows"][0]["axioms"])
        self.assertEqual(proc.returncode, 0)

    def test_missing_source_fails_strict(self):
        proc, rep = self.run_tool(
            {"Weil__Absent__ghost_thm.txt": CLOSED_RECEIPT}, strict=True)
        self.assertEqual(rep["unlocatable"], 1)
        self.assertEqual(proc.returncode, 1)

    def test_obligation_not_discharged_by_a_tautology(self):
        proc, _ = self.run_tool(
            {"Weil__Demo__tautology_thm.txt": CLOSED_RECEIPT},
            obligations=("Target",))
        self.assertIn("NOT DISCHARGED", proc.stdout)


if __name__ == "__main__":
    unittest.main()
