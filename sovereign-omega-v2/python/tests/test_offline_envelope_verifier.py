#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFIER_PATH = REPO_ROOT / "scripts/aegis-envelope-verify.py"
SPEC = importlib.util.spec_from_file_location("aegis_offline_verify", VERIFIER_PATH)
assert SPEC and SPEC.loader
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)

PYTHON_DIR = REPO_ROOT / "sovereign-omega-v2/python"
sys.path.insert(0, str(PYTHON_DIR))
import canonical_envelope as runtime  # noqa: E402


def make_chain() -> list[dict]:
    chain = runtime.EnvelopeChain()
    return [
        chain.emit("a" * 64, "b" * 64, "model-a", "T1", "anthropic"),
        chain.emit("c" * 64, "d" * 64, "model-a", "T1", "anthropic"),
        chain.emit("e" * 64, "f" * 64, "model-b", "T2", "demo"),
    ]


class OfflineEnvelopeVerifierTests(unittest.TestCase):
    def test_independent_verifier_does_not_import_runtime_module(self):
        source = VERIFIER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("import canonical_envelope", source)
        self.assertNotIn("from canonical_envelope", source)

    def test_runtime_envelope_verifies_independently(self):
        envelope = make_chain()[0]
        result = verify.verify_envelope(envelope)
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["envelope_hash"], envelope["envelope_hash"])
        self.assertFalse(result["signature_verified"])

    def test_runtime_chain_verifies_and_terminal_matches(self):
        envelopes = make_chain()
        result = verify.verify_chain(envelopes)
        self.assertEqual(result["status"], "VALID")
        self.assertEqual(result["envelope_count"], 3)
        self.assertEqual(result["terminal_hash"], envelopes[-1]["envelope_hash"])

    def test_packaged_chain_expected_terminal_is_enforced(self):
        envelopes = make_chain()
        package = {
            "schema_version": "1.0.0",
            "kind": verify.CHAIN_KIND,
            "envelopes": envelopes,
            "expected_terminal_hash": envelopes[-1]["envelope_hash"],
        }
        self.assertEqual(
            verify.verify_chain(package)["terminal_hash"],
            envelopes[-1]["envelope_hash"],
        )
        package["expected_terminal_hash"] = "9" * 64
        with self.assertRaisesRegex(
            verify.VerificationError, "EXPECTED_TERMINAL_HASH_MISMATCH"
        ):
            verify.verify_chain(package)

    def test_body_tamper_is_rejected_even_if_claimed_hash_is_unchanged(self):
        envelope = make_chain()[0]
        envelope["provider"] = "other"
        with self.assertRaisesRegex(
            verify.VerificationError, "ENVELOPE_HASH_MISMATCH"
        ):
            verify.verify_envelope(envelope)

    def test_rehashed_middle_envelope_still_breaks_chain(self):
        envelopes = make_chain()
        envelopes[1]["provider"] = "other"
        body = {key: envelopes[1][key] for key in verify.BODY_FIELDS}
        envelopes[1]["envelope_hash"] = hashlib.sha256(
            verify.canon(body)
        ).hexdigest()
        with self.assertRaisesRegex(
            verify.VerificationError, "EXPECTED_PREV_HASH_MISMATCH"
        ):
            verify.verify_chain(envelopes)

    def test_sequence_break_is_rejected(self):
        envelopes = make_chain()
        envelopes[1]["seq"] = 7
        body = {key: envelopes[1][key] for key in verify.BODY_FIELDS}
        envelopes[1]["envelope_hash"] = hashlib.sha256(
            verify.canon(body)
        ).hexdigest()
        with self.assertRaisesRegex(
            verify.VerificationError, "EXPECTED_SEQUENCE_MISMATCH"
        ):
            verify.verify_chain(envelopes)

    def test_extra_and_missing_fields_are_rejected(self):
        envelope = make_chain()[0]
        extra = dict(envelope, unexpected=True)
        with self.assertRaisesRegex(
            verify.VerificationError, "ENVELOPE_FIELD_SET_MISMATCH"
        ):
            verify.verify_envelope(extra)
        missing = dict(envelope)
        missing.pop("provider")
        with self.assertRaisesRegex(
            verify.VerificationError, "ENVELOPE_FIELD_SET_MISMATCH"
        ):
            verify.verify_envelope(missing)

    def test_non_null_signature_is_fail_closed_until_kms_verifier_exists(self):
        envelope = make_chain()[0]
        envelope["signature"] = "deadbeef"
        with self.assertRaisesRegex(
            verify.VerificationError, "SIGNATURE_VERIFICATION_UNSUPPORTED"
        ):
            verify.verify_envelope(envelope)

    def test_float_and_nonfinite_numbers_are_rejected_at_input_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "bad.json"
            p.write_text('{"x":0.5}', encoding="utf-8")
            with self.assertRaisesRegex(
                verify.VerificationError, "FLOAT_IN_HASHED_STATE"
            ):
                verify.load_json(p)
            p.write_text('{"x":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(
                verify.VerificationError, "NON_FINITE_NUMBER"
            ):
                verify.load_json(p)

    def test_expected_single_envelope_anchors_are_enforced(self):
        envelope = make_chain()[0]
        result = verify.verify_envelope(
            envelope,
            expected_seq=0,
            expected_prev_hash=verify.GENESIS,
            expected_envelope_hash=envelope["envelope_hash"],
        )
        self.assertEqual(result["status"], "VALID")
        with self.assertRaisesRegex(
            verify.VerificationError, "EXPECTED_ENVELOPE_HASH_MISMATCH"
        ):
            verify.verify_envelope(
                envelope,
                expected_envelope_hash="9" * 64,
            )

    def test_cli_json_output_is_machine_readable_and_exit_codes_fail_closed(self):
        envelopes = make_chain()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chain.json"
            path.write_text(json.dumps(envelopes), encoding="utf-8")
            ok = subprocess.run(
                [
                    sys.executable,
                    str(VERIFIER_PATH),
                    "--json",
                    "chain",
                    str(path),
                    "--expected-terminal-hash",
                    envelopes[-1]["envelope_hash"],
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr)
            payload = json.loads(ok.stdout)
            self.assertEqual(payload["status"], "VALID")
            self.assertFalse(payload["signature_verified"])
            self.assertFalse(payload["transparency_log_verified"])

            bad = copy.deepcopy(envelopes)
            bad[2]["prev_hash"] = "9" * 64
            path.write_text(json.dumps(bad), encoding="utf-8")
            denied = subprocess.run(
                [sys.executable, str(VERIFIER_PATH), "--json", "chain", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(denied.returncode, 2)
            payload = json.loads(denied.stdout)
            self.assertEqual(payload["status"], "INVALID")


if __name__ == "__main__":
    unittest.main(verbosity=2)
