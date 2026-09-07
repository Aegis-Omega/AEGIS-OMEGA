"""Adversarial controls for semantic forgery despite recomputed chain hashes."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from genomics.quantum_dna import claims_gate as gate

PIN = "1" * 40  # Pure-function fixture only; CLI additionally checks real git objects.


class ClaimsGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = gate.build_ledger(PIN)
        cls.claims = gate.expected_claims(PIN)

    def test_valid_projection_and_immutable_source_bytes(self):
        self.assertEqual(gate.validate_ledger(self.ledger, self.claims), self.ledger["terminal_sha256"])
        self.assertEqual(len(self.claims), 16)
        self.assertFalse(self.ledger["header"]["authority_promotion"])

    def test_each_source_digest_is_required(self):
        for name in self.ledger["header"]["source_sha256"]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / "evidence"
                shutil.copytree(gate.HERE / "evidence", root)
                target = root / name
                target.write_bytes(target.read_bytes() + b"\n")
                with self.assertRaises(gate.GateError):
                    gate.validate_ledger(self.ledger, self.claims, root)

    @staticmethod
    def rehash(ledger):
        context = gate.digest(ledger["header"])
        previous = gate.GENESIS
        for entry in ledger["entries"]:
            entry["context_sha256"] = context
            entry["previous_entry_sha256"] = previous
            entry.pop("entry_sha256", None)
            previous = entry["entry_sha256"] = gate.digest(entry)
        ledger["terminal_sha256"] = previous

    def test_rehashed_authority_promotion_still_denied(self):
        for key, value in (("authority_promotion", True), ("control_plane_admission", "ADMITTED"),
                           ("mathematical_document", "VERIFIED"), ("source_run_commit", "2" * 40)):
            forged = copy.deepcopy(self.ledger)
            forged["header"][key] = value
            self.rehash(forged)
            with self.subTest(key=key), self.assertRaises(gate.GateError):
                gate.validate_ledger(forged, self.claims)

    def test_rehashed_claim_and_scope_forgery_denied(self):
        for key, value in (("authority", "MACHINE_ADMITTED"), ("limitations", []),
                           ("model_scope", "IN_CELL"), ("sequence", 10)):
            forged = copy.deepcopy(self.ledger)
            forged["entries"][0][key] = value
            self.rehash(forged)
            with self.subTest(key=key), self.assertRaises(gate.GateError):
                gate.validate_ledger(forged, self.claims)
        forged = copy.deepcopy(self.ledger)
        forged["entries"][3]["claim"]["tier"] = "Verified"
        self.rehash(forged)
        projected = [entry["claim"] for entry in forged["entries"]]
        with self.assertRaises(gate.GateError):
            gate.validate_ledger(forged, projected)

    def test_chain_break_reordering_truncation_and_unknown_keys_denied(self):
        variants = []
        broken = copy.deepcopy(self.ledger)
        broken["entries"][1]["previous_entry_sha256"] = gate.GENESIS
        variants.append(broken)
        reordered = copy.deepcopy(self.ledger)
        reordered["entries"].reverse()
        self.rehash(reordered)
        variants.append(reordered)
        truncated = copy.deepcopy(self.ledger)
        truncated["entries"].pop()
        self.rehash(truncated)
        variants.append(truncated)
        extra = copy.deepcopy(self.ledger)
        extra["admission_override"] = True
        variants.append(extra)
        for forged in variants:
            with self.assertRaises(gate.GateError):
                gate.validate_ledger(forged, self.claims)

    def test_central_projection_cannot_drop_duplicate_or_reword_claims(self):
        cases = [self.claims[:-1], self.claims + [self.claims[0]]]
        changed = copy.deepcopy(self.claims)
        changed[0]["claim"] = "Validated biological benefit"
        cases.append(changed)
        for claims in cases:
            with self.assertRaises(gate.GateError):
                gate.validate_ledger(self.ledger, claims)

    def test_hash_payload_has_no_floats_or_ambiguous_json(self):
        for value in (0.1, float("nan"), {1: "not a string"}):
            with self.assertRaises(gate.GateError):
                gate.canonical(value)
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "bad.json"
            for raw in ('{"authority":false,"authority":true}', '{"x":NaN}'):
                target.write_text(raw)
                with self.assertRaises(gate.GateError):
                    gate.read_json(target)

    def test_commit_pin_must_be_exact(self):
        for invalid in ("HEAD", "main", "1234567", None, "A" * 40):
            with self.assertRaises(gate.GateError):
                gate.build_ledger(invalid)

    def test_determinism_across_three_processes(self):
        command = [sys.executable, "-c", "from genomics.quantum_dna.claims_gate import build_ledger; "
                   f"print(build_ledger('{PIN}')['terminal_sha256'])"]
        results = [subprocess.check_output(command, cwd=gate.ROOT,
                   env={**os.environ, "PYTHONHASHSEED": str(seed)}, text=True).strip()
                   for seed in (1, 17, 909)]
        self.assertEqual(results, [self.ledger["terminal_sha256"]] * 3)


if __name__ == "__main__":
    unittest.main()
