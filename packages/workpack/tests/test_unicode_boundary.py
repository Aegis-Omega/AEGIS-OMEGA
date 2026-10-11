"""Regression cases for escaped lone-surrogate JSON from untrusted sources.

RFC 8259 section 8.2 warns that the ABNF admits unpaired UTF-16 code
units and that their software behavior is unpredictable. This verifier
rejects them with an explicit reason instead of crashing or rewriting.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aegis_workpack.protocol import Invalid, read_json, verify, _strict_json_loads


def contract(path, body):
    return {
        "schema": "aegis.workpack.v1", "task_id": "unicode-001",
        "domain": "data", "authority": "read_only",
        "objective": "Verify a safely decoded unicode JSON artifact",
        "producer": {"agent": "strict-json-test"},
        "artifacts": [{"path": path, "sha256": hashlib.sha256(body).hexdigest()}],
        "checks": [{"id": "A1", "kind": "json_keys", "artifact": path,
                    "keys": ["result"]}],
    }


class UnicodeBoundaryTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)

    def test_helper_unpaired_surrogate_value_has_controlled_error(self):
        p = self.root / "source.json"
        p.write_bytes(b'{"result":"\\ud800"}')
        with self.assertRaisesRegex(Invalid, "JSON_UNPAIRED_SURROGATE"):
            read_json(p)

    def test_helper_unpaired_surrogate_key_has_controlled_error(self):
        p = self.root / "source.json"
        p.write_bytes(b'{"\\udfff":"present"}')
        with self.assertRaisesRegex(Invalid, "JSON_UNPAIRED_SURROGATE"):
            read_json(p)

    def test_structural_json_check_rejects_escaped_surrogate(self):
        raw = b'{"result":"\\ud800"}'
        (self.root / "data.json").write_bytes(raw)
        report = verify(self.root, contract("data.json", raw))
        self.assertEqual(report["disposition"], "NOT_ADMITTED")
        self.assertEqual(report["artifact_integrity"], "PASS")
        self.assertEqual(report["checks"][0]["result"], "FAIL")
        self.assertEqual(report["checks"][0]["reason"], "JSON_UNPAIRED_SURROGATE")

    def test_cli_emits_json_receipt_without_traceback_for_surrogate(self):
        raw = b'{"result": "valid"}'
        (self.root / "data.json").write_bytes(raw)
        m = contract("data.json", raw)
        m["note"] = chr(0xD800)
        (self.root / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-S", "-m", "aegis_workpack.protocol", str(self.root)],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["disposition"], "NOT_ADMITTED")
        self.assertEqual(receipt["reason"], "JSON_UNPAIRED_SURROGATE")

    def test_direct_python_api_invalid_unicode_is_not_exception(self):
        raw = b'{"result": "valid"}'
        (self.root / "data.json").write_bytes(raw)
        m = contract("data.json", raw)
        m["note"] = chr(0xDFFF)
        receipt = verify(self.root, m)
        self.assertEqual(receipt["disposition"], "NOT_ADMITTED")
        self.assertEqual(receipt["contract"], "INVALID")
        self.assertEqual(receipt["reason"], "JSON_UNPAIRED_SURROGATE")

    def test_valid_surrogate_pair_is_accepted(self):
        p = self.root / "source.json"
        p.write_bytes(b'{"result":"\\ud83d\\ude00"}')
        self.assertEqual(read_json(p)["result"], "\N{GRINNING FACE}")
        self.assertEqual(_strict_json_loads('{"result":"\\ud83d\\ude00"}')["result"],
                         "\N{GRINNING FACE}")

    def test_valid_plain_utf8_is_accepted(self):
        p = self.root / "source.json"
        p.write_text('{"result":"Čisto · Ω"}', encoding="utf-8")
        self.assertEqual(read_json(p)["result"], "Čisto · Ω")


if __name__ == "__main__":
    unittest.main()
