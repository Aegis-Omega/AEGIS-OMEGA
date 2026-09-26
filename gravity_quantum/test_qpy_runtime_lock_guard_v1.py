from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gravity_quantum.qpy_runtime_lock_guard_v1 import LockError, verify_lock


def good_lock() -> str:
    return """\
cudaq==0.15.1 \\
  --hash=sha256:%s
pennylane==0.45.1 \\
  --hash=sha256:%s
qiskit==2.5.2 \\
  --hash=sha256:%s
numpy==2.1.3 \\
  --hash=sha256:%s
""" % (("a"*64), ("b"*64), ("c"*64), ("d"*64))


class Tests(unittest.TestCase):
    def verify_text(self, text: str):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "lock.txt"
            path.write_text(text, encoding="utf-8")
            return verify_lock(path)

    def test_hash_bound_exact_lock_passes(self):
        r = self.verify_text(good_lock())
        self.assertTrue(r["all_requirements_hash_bound"])
        self.assertEqual(r["requirement_count"], 4)

    def test_missing_hash_fails(self):
        with self.assertRaisesRegex(LockError, "REQUIREMENT_HASH_MISSING:qiskit"):
            self.verify_text(good_lock().replace("qiskit==2.5.2 \\\n  --hash=sha256:" + "c"*64, "qiskit==2.5.2"))

    def test_unpinned_requirement_fails(self):
        with self.assertRaisesRegex(LockError, "REQUIREMENT_NOT_EXACTLY_PINNED"):
            self.verify_text(good_lock() + "scipy>=1.0 --hash=sha256:" + "e"*64 + "\n")

    def test_wrong_top_level_version_fails(self):
        with self.assertRaisesRegex(LockError, "TOP_LEVEL_VERSION_MISMATCH"):
            self.verify_text(good_lock().replace("qiskit==2.5.2", "qiskit==2.5.1"))

    def test_editable_or_url_requirement_fails(self):
        with self.assertRaisesRegex(LockError, "UNSUPPORTED_NON_INDEX_REQUIREMENT"):
            self.verify_text(good_lock() + "-e git+https://example.test/repo\n")

    def test_receipt_is_deterministic_for_same_bytes(self):
        a = self.verify_text(good_lock())
        b = self.verify_text(good_lock())
        self.assertEqual(a["lock_sha256"], b["lock_sha256"])
        self.assertEqual(a["receipt_sha256"], b["receipt_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)