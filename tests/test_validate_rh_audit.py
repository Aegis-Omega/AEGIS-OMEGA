import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_rh_audit", ROOT / "scripts/validate-rh-audit.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AstraReceiptTests(unittest.TestCase):
    def test_repository_audit_is_structurally_valid(self):
        self.assertEqual(MODULE.validate_dag(), 6)
        self.assertEqual(MODULE.validate_receipt(None), [])

    def test_missing_bundle_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            failures = MODULE.validate_receipt(Path(directory))
        self.assertTrue(failures)
        self.assertTrue(all(item.startswith("missing: ") for item in failures))

    def test_digest_mismatch_fails_closed(self):
        receipt = json.loads(MODULE.RECEIPT.read_text())
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            for name in receipt["files"]:
                (bundle / name).write_bytes(b"not the declared artifact")
            failures = MODULE.validate_receipt(bundle)
        self.assertEqual(len(failures), len(receipt["files"]))
        self.assertTrue(all(item.startswith("digest mismatch: ") for item in failures))

    def test_hashing_is_byte_exact(self):
        payload = b"normalization\r\nfreeze\x00"
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "ceab4957e017560ae05fcf4335adf18e0a3aeeeff2e5910c23ea6b19b54a7539",
        )


if __name__ == "__main__":
    unittest.main()
