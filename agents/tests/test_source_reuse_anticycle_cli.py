"""Executable CLI tests for the independent no-duplicate source contract."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents.source_reuse_preflight import canonical
from agents.tests.test_source_reuse_anticycle import (
    DETECTOR, PINS, asset, manifest,
)


class TestAnticycleCLI(unittest.TestCase):
    def run_cli(self, m, pins=None, *, digest=None, pin_arg=True, symlink=False):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            mp = root / "manifest.json"
            mp.write_text(json.dumps(m), encoding="utf-8")
            args = [sys.executable, "-m", "agents.source_reuse_preflight", str(mp)]
            if pins is not None:
                pp = root / "pins.json"
                pp.write_text(json.dumps(pins), encoding="utf-8")
                if symlink:
                    link = root / "alias.json"
                    link.symlink_to(pp)
                    pp = link
                if pin_arg:
                    args.extend(("--required-asset-pins", str(pp)))
                if digest is not False:
                    args.extend(("--required-asset-pins-sha256",
                                 hashlib.sha256(canonical(pins)).hexdigest() if digest is None else digest))
            p = subprocess.run(args, capture_output=True, text=True, timeout=10)
            return p.returncode, json.loads(p.stdout)

    def test_original_cli_remains_backward_compatible_without_extra_contract(self):
        code, receipt = self.run_cli(manifest())
        self.assertEqual(code, 0)
        self.assertEqual(receipt["outcome"], "READY_FOR_AUTHORITY_REVIEW")
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_pinned_cli_denies_missing_previous_math(self):
        code, receipt = self.run_cli(manifest(), PINS)
        self.assertEqual(code, 2)
        self.assertEqual(receipt["outcome"], "HOLD")
        self.assertIn("REQUIRED_PRIOR_ART_MISSING:" + DETECTOR, receipt["blockers"])

    def test_pinned_cli_allows_explicit_reuse_but_no_authority(self):
        m = manifest()
        m["intent"] = "USE_EXISTING"
        m["assets"] = [asset(DETECTOR, PINS[DETECTOR], disposition="REUSE")]
        code, receipt = self.run_cli(m, {DETECTOR: PINS[DETECTOR]})
        self.assertEqual(code, 0)
        self.assertEqual(receipt["outcome"], "READY_FOR_AUTHORITY_REVIEW")
        self.assertEqual(receipt["authority_effect"], "NONE")

    def test_mismatch_contract_digest_blocks_execution(self):
        code, receipt = self.run_cli(manifest(), PINS, digest="a"*64)
        self.assertEqual(code, 2)
        self.assertEqual(receipt["reason"], "PIN_CONTRACT_HASH_MISMATCH")

    def test_missing_contract_hash_fails_closed(self):
        code, receipt = self.run_cli(manifest(), PINS, digest=False)
        self.assertEqual(code, 2)
        self.assertEqual(receipt["reason"], "PIN_CONTRACT_ARGUMENTS_INCOMPLETE")

    def test_symlink_contract_fails_closed(self):
        code, receipt = self.run_cli(manifest(), PINS, symlink=True)
        self.assertEqual(code, 2)
        self.assertEqual(receipt["reason"], "UNTRUSTED_PIN_CONTRACT_PATH")


if __name__ == "__main__":
    unittest.main()
