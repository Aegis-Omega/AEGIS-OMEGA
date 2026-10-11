"""Offline adversarial tests of HMAC-attested inert dendrite transport."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents.dendrite_system import from_source_record
from agents.dendrite_mailbox import publish_local
from agents.dendrite_attestation import publish_attested, read_attested, _read_secret

KEY = b"test-HMAC-relay-key-only-not-production-000000000"
OTHER = b"a-different-trusted-relay-secret-00000000000"
HEAD = "a" * 40
RECORD = "b" * 64


def receipt(channel="CANDIDATE", text="Claim under evaluation"):
    return from_source_record({
        "source": "formal", "source_head": HEAD, "source_record": RECORD,
        "sequence": 0, "text": text, "channel": channel})


class RelayAttestationTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.work = Path(d.name)
        self.root = self.work / "spool"
        self.keyfile = self.work / "relay_secret"
        self.keyfile.write_bytes(KEY)
        self.keyfile.chmod(0o600)

    def test_one_verified_recipient(self):
        result = publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        self.assertGreater(result["attestations_written"], 4)
        msgs = read_attested(self.root, "engineering", {"formal_relay": KEY})
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0]["transport_authentication"], "HMAC_VERIFIED_LOCAL_RELAY")
        self.assertEqual(msgs[0]["source_authenticity"], "NOT_VERIFIED")
        self.assertEqual(msgs[0]["authority_effect"], "NONE")
        self.assertEqual(msgs[0]["packet"]["envelope"]["text"], "Claim under evaluation")

    def test_key_mismatch_fails_closed(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        with self.assertRaisesRegex(ValueError, "RELAY_SIGNATURE_MISMATCH"):
            read_attested(self.root, "engineering", {"formal_relay": OTHER})

    def test_unknown_relay_id_fails_closed(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        with self.assertRaisesRegex(ValueError, "RELAY_KEY_NOT_TRUSTED"):
            read_attested(self.root, "engineering", {"other_relay": KEY})

    def test_unsigned_inbox_denied(self):
        publish_local(receipt(), self.root)
        with self.assertRaisesRegex(ValueError, "RELAY_ATTESTATION_MISSING"):
            read_attested(self.root, "engineering", {"formal_relay": KEY})

    def test_idempotent_replay(self):
        first = publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        second = publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        self.assertEqual(first["attestations_written"], second["attestation_duplicates"])
        self.assertEqual(second["attestations_written"], 0)

    def test_conflicting_rotation_rejected(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        with self.assertRaisesRegex(ValueError, "RELAY_ATTESTATION_CONFLICT"):
            publish_attested(receipt(), self.root, key_id="formal_relay", key=OTHER)

    def test_missing_one_attestation_repaired_by_retry(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        next((self.root / "engineering").glob("*.attest")).unlink()
        with self.assertRaisesRegex(ValueError, "RELAY_ATTESTATION_MISSING"):
            read_attested(self.root, "engineering", {"formal_relay": KEY})
        repair = publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        self.assertEqual(repair["attestations_written"], 1)
        self.assertEqual(len(read_attested(self.root, "engineering", {"formal_relay": KEY})), 1)

    def test_tamper_relay_key_id_rejected(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        p = next((self.root / "engineering").glob("*.attest"))
        obj = json.loads(p.read_text())
        obj["key_id"] = "other_relay"
        p.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            read_attested(self.root, "engineering", {"other_relay": KEY})

    def test_tamper_packet_source_rejected_even_with_signature(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        p = next((self.root / "engineering").glob("*.json"))
        obj = json.loads(p.read_text())
        obj["envelope"]["source_head"] = "c" * 40
        p.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            read_attested(self.root, "engineering", {"formal_relay": KEY})

    def test_tampered_auth_attestation_rejected(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        p = next((self.root / "engineering").glob("*.attest"))
        obj = json.loads(p.read_text())
        obj["hmac_sha256"] = "0" * 64
        p.write_text(json.dumps(obj))
        with self.assertRaisesRegex(ValueError, "RELAY_SIGNATURE_MISMATCH"):
            read_attested(self.root, "engineering", {"formal_relay": KEY})

    def test_symlink_auth_attestation_denied(self):
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        p = next((self.root / "engineering").glob("*.attest"))
        back = p.with_name("original")
        p.rename(back)
        p.symlink_to(back)
        with self.assertRaisesRegex(ValueError, "RELAY_ATTESTATION_SYMLINK"):
            read_attested(self.root, "engineering", {"formal_relay": KEY})

    def test_restricted_quarantine(self):
        publish_attested(receipt(channel="QUARANTINE"), self.root,
                         key_id="formal_relay", key=KEY)
        self.assertFalse((self.root / "engineering").exists())
        self.assertEqual(len(read_attested(self.root, "ai_safety", {"formal_relay": KEY})), 1)

    def test_reject_short_keys_and_empty_trust_store(self):
        with self.assertRaisesRegex(ValueError, "RELAY_KEY_INVALID"):
            publish_attested(receipt(), self.root, key_id="formal_relay", key=b"short")
        publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        with self.assertRaisesRegex(ValueError, "RELAY_TRUST_STORE_REQUIRED"):
            read_attested(self.root, "engineering", {})

    def test_secret_must_not_be_group_readable(self):
        self.keyfile.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "RELAY_KEY_FILE_UNSAFE"):
            _read_secret(self.keyfile)

    def test_secret_must_not_be_symlink(self):
        target = self.work / "actual_secret"
        self.keyfile.rename(target)
        self.keyfile.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "RELAY_KEY_PATH_UNSAFE"):
            _read_secret(self.keyfile)

    def test_independent_cli_processes(self):
        path = self.work / "source.json"
        path.write_text(json.dumps({
            "source": "formal", "source_head": HEAD, "source_record": RECORD,
            "sequence": 0, "text": "separate-process-claim", "channel": "CANDIDATE",
        }))
        pub = subprocess.run([
            sys.executable, "-m", "agents.dendrite_attestation", "publish", str(path),
            "--root", str(self.root), "--key-file", str(self.keyfile),
            "--key-id", "formal_relay"], capture_output=True, text=True, timeout=15)
        self.assertEqual(pub.returncode, 0, pub.stderr)
        read = subprocess.run([
            sys.executable, "-m", "agents.dendrite_attestation", "read", "engineering",
            "--root", str(self.root), "--key-file", str(self.keyfile),
            "--key-id", "formal_relay"], capture_output=True, text=True, timeout=15)
        self.assertEqual(read.returncode, 0, read.stderr)
        self.assertEqual(json.loads(read.stdout)[0]["packet"]["envelope"]["text"],
                         "separate-process-claim")

    def test_no_key_value_in_receipt(self):
        result = publish_attested(receipt(), self.root, key_id="formal_relay", key=KEY)
        self.assertNotIn(KEY.hex(), json.dumps(result))
        self.assertEqual(result["source_authenticity"], "NOT_VERIFIED")
        self.assertEqual(result["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
