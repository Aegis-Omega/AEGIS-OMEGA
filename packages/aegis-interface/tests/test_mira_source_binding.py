"""Source pin and fail-closed integration boundary, no fake compiler tests."""
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'packages' / 'aegis-interface'))
from aegis_interface.mira_bridge import (
    SOURCE_PINS, git_blob_sha, verify_lean_sources, verify_wit_contract,
)
from aegis_interface.math_rh import ProofHold


class BindingTests(unittest.TestCase):
    def test_git_blob_sha_matches_real_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'tiny.lean'
            p.write_bytes(b'example : True := by trivial\n')
            result=subprocess.run(['git','hash-object',str(p)],check=True,capture_output=True,text=True)
            self.assertEqual(git_blob_sha(p.read_bytes()),result.stdout.strip())

    def test_missing_lean_source_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ProofHold,'HOLD_LEAN_SOURCE_MISSING'):
                verify_lean_sources(Path(tmp))

    def test_wrong_lean_source_hash_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in SOURCE_PINS:
                (Path(tmp)/name).write_text('theorem fabricated : True := by trivial\n')
            with self.assertRaisesRegex(ProofHold,'HOLD_LEAN_SOURCE_BLOB_MISMATCH'):
                verify_lean_sources(Path(tmp))

    def test_real_compiler_unavailable_fails_closed_locally(self):
        wit=ROOT/'packages'/'aegis-interface'/'wit'/'mira_rh_proof.wit'
        try:
            importlib.import_module('aegis_interface.compiler')
        except ImportError:
            with self.assertRaisesRegex(ProofHold,'HOLD_REAL_AEGIS_COMPILER_UNAVAILABLE'):
                verify_wit_contract(wit)
        else:
            self.assertEqual(verify_wit_contract(wit)['equivalence'],'PASS_ORIGINAL_COMPILER')

    def test_malformed_wit_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'missing.wit'
            with self.assertRaisesRegex(ProofHold,'HOLD_WIT_SOURCE_UNAVAILABLE'):
                verify_wit_contract(p)

if __name__ == '__main__': unittest.main()
