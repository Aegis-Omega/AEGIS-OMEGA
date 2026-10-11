"""Adversarial exact-head checkout boundary for formal dendrite packets."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agents.dendrite_formal_gate import (
    verify_formal_source, publish_formal_verified, read_formal_verified,
)

KEY = b"ephemeral-dendrite-formal-test-secret-0123456789"
PATH = "FormalConjectures/Millennium/RiemannHypothesis.lean"


class FormalSourceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "formal"
        self.repo.mkdir()
        self.spool = self.root / "spool"
        self.keyfile = self.root / "relay.key"
        self.keyfile.write_bytes(KEY)
        self.keyfile.chmod(0o600)
        self.source = self.repo / PATH
        self.source.parent.mkdir(parents=True)
        self.code = "theorem synthetic : True := by\n  trivial\n"
        self.source.write_text(self.code)
        self.git("init", "-q")
        self.git("remote", "add", "origin", "https://github.com/tarikskalic33/formal-conjectures.git")
        self.git("add", ".")
        self.git("-c", "user.name=AEGIS Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "fixture")
        self.head = self.git("rev-parse", "HEAD").strip()
        raw_hash = hashlib.sha256(self.code.encode()).hexdigest()
        prefix = (f"LEAN SOURCE ONLY — PROOF NOT VERIFIED; path={PATH}; "
                  f"source_bytes_sha256={raw_hash}; excerpt:\n")
        self.record = {"source": "formal", "source_head": self.head,
                       "source_record": raw_hash, "sequence": 0,
                       "text": prefix + self.code, "channel": "CANDIDATE"}

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True,
                           text=True, check=True)
        return p.stdout

    def test_verified_source_exact_head(self):
        result = verify_formal_source(self.record, repo=self.repo)
        self.assertEqual(result["status"], "LOCAL_GIT_HEAD_SOURCE_BYTES_MATCHED")
        self.assertFalse(result["github_author_verified"])
        self.assertFalse(result["mathematical_proof_verified"])

    def test_changed_worktree_does_not_change_head_snapshot(self):
        self.source.write_text("theorem tampered : False := by sorry\n")
        self.assertEqual(verify_formal_source(self.record, repo=self.repo)["source_head"], self.head)

    def test_wrong_checkout_head_denied(self):
        self.source.write_text("theorem changed : False := by sorry\n")
        self.git("add", ".")
        self.git("-c", "user.name=AEGIS Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "different head")
        with self.assertRaisesRegex(ValueError, "FORMAL_HEAD_MISMATCH"):
            verify_formal_source(self.record, repo=self.repo)

    def test_wrong_source_hash_denied(self):
        with self.assertRaisesRegex(ValueError, "FORMAL_SOURCE_DIGEST_MISMATCH"):
            verify_formal_source(dict(self.record, source_record="0" * 64), repo=self.repo)

    def test_wrong_excerpt_denied(self):
        bad = dict(self.record, text=self.record["text"].replace("trivial", "sorry"))
        with self.assertRaisesRegex(ValueError, "FORMAL_SOURCE_EXCERPT_MISMATCH"):
            verify_formal_source(bad, repo=self.repo)

    def test_prefix_path_spoof_denied(self):
        with self.assertRaisesRegex(ValueError, "FORMAL_SOURCE_NOT_REGULAR_BLOB"):
            verify_formal_source(self.record, repo=self.repo,
                                 path="FormalConjecturesForMathlib/Other.lean")

    def test_wrong_remote_denied(self):
        self.git("remote", "set-url", "origin", "https://github.com/evil/fake.git")
        with self.assertRaisesRegex(ValueError, "FORMAL_REMOTE_CONFIG_MISMATCH"):
            verify_formal_source(self.record, repo=self.repo)

    def test_extra_instruction_field_denied(self):
        bad = dict(self.record, command="deploy")
        with self.assertRaisesRegex(ValueError, "FORMAL_RECORD_SCHEMA_INVALID"):
            verify_formal_source(bad, repo=self.repo)

    def test_no_publish_before_source_verification(self):
        bad = dict(self.record, text="fake")
        with self.assertRaises(ValueError):
            publish_formal_verified(bad, self.spool, repo=self.repo,
                                    key_id="test_relay", key=KEY)
        self.assertFalse(self.spool.exists())

    def test_authenticated_roundtrip(self):
        result = publish_formal_verified(self.record, self.spool, repo=self.repo,
                                         key_id="test_relay", key=KEY)
        self.assertEqual(result["source_check"]["authority_effect"], "NONE")
        messages = read_formal_verified(self.spool, "engineering", {"test_relay": KEY},
                                        repo=self.repo)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["relay"]["transport_authentication"],
                         "HMAC_VERIFIED_LOCAL_RELAY")
        self.assertEqual(messages[0]["source_check"]["source_authenticity"],
                         "LOCAL_CHECKOUT_ONLY")

    def test_wrong_key_read_denied(self):
        publish_formal_verified(self.record, self.spool, repo=self.repo, key_id="test_relay", key=KEY)
        with self.assertRaisesRegex(ValueError, "RELAY_SIGNATURE_MISMATCH"):
            read_formal_verified(self.spool, "engineering", {"test_relay": b"x" * 32}, repo=self.repo)

    def test_second_process_verifies_source_and_relay(self):
        publish_formal_verified(self.record, self.spool, repo=self.repo, key_id="test_relay", key=KEY)
        cmd = [sys.executable, "-m", "agents.dendrite_formal_gate", "read",
               "--repo", str(self.repo), "--root", str(self.spool),
               "--key-file", str(self.keyfile), "--key-id", "test_relay", "engineering"]
        run = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)[0]["source_check"]["status"],
                         "LOCAL_GIT_HEAD_SOURCE_BYTES_MATCHED")

    def test_quarantine_does_not_persist_in_engineering(self):
        quarantined = dict(self.record, channel="QUARANTINE")
        publish_formal_verified(quarantined, self.spool, repo=self.repo,
                                key_id="test_relay", key=KEY)
        self.assertFalse((self.spool / "engineering").exists())
        self.assertEqual(len(read_formal_verified(self.spool, "cybersecurity",
                         {"test_relay": KEY}, repo=self.repo)), 1)

    def test_path_traversal_denied(self):
        with self.assertRaisesRegex(ValueError, "FORMAL_PATH_INVALID"):
            verify_formal_source(self.record, repo=self.repo, path="../secret.lean")


if __name__ == "__main__":
    unittest.main()
