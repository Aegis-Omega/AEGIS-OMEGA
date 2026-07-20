from __future__ import annotations

from hashlib import sha256
import unittest

from platform.sol.adapters.ogemma import (
    OgemmaEvidenceError,
    normalize_verdict,
    to_authority_evidence,
)


ZERO = sha256(b"").hexdigest()


class OgemmaAdapterTests(unittest.TestCase):
    def valid(self, **overrides):
        payload = {
            "holon_id": "gemma-4e4b-iphone",
            "gate": "PRE_ORCHESTRATE",
            "verdict": "APPROVED",
            "confidence": 0.94,
            "reason_code": "NOMINAL",
            "task": "inspect current execution",
            "plan_digest": ZERO,
            "prompt_digest": ZERO,
            "model_identity": "google/gemma-3n-E4B-it@pinned-revision",
            "bio_state": {
                "stress": 0.42,
                "attention": 0.82,
                "rir": 0.95,
                "atp": 2100,
            },
        }
        payload.update(overrides)
        return normalize_verdict(**payload)

    def test_valid_evidence_is_advisory(self):
        evidence = self.valid()
        wrapped = to_authority_evidence(evidence)
        self.assertEqual(wrapped["evidence_tier"], "T2")
        self.assertFalse(wrapped["grants_authority"])
        self.assertEqual(len(evidence.evidence_digest), 64)

    def test_unknown_gate_is_denied(self):
        with self.assertRaises(OgemmaEvidenceError):
            self.valid(gate="UNKNOWN_GATE")

    def test_unknown_verdict_is_denied(self):
        with self.assertRaises(OgemmaEvidenceError):
            self.valid(verdict="PENDING")

    def test_out_of_range_bio_state_is_denied(self):
        with self.assertRaises(OgemmaEvidenceError):
            self.valid(
                bio_state={
                    "stress": 1.1,
                    "attention": 0.82,
                    "rir": 0.95,
                    "atp": 2100,
                }
            )

    def test_missing_bio_field_is_denied(self):
        with self.assertRaises(OgemmaEvidenceError):
            self.valid(
                bio_state={
                    "stress": 0.4,
                    "attention": 0.8,
                    "atp": 2100,
                }
            )

    def test_invalid_digest_is_denied(self):
        with self.assertRaises(OgemmaEvidenceError):
            self.valid(plan_digest="not-a-digest")

    def test_evidence_digest_is_deterministic(self):
        self.assertEqual(self.valid().evidence_digest, self.valid().evidence_digest)

    def test_task_changes_evidence_digest(self):
        self.assertNotEqual(
            self.valid(task="inspect current execution").evidence_digest,
            self.valid(task="inspect another execution").evidence_digest,
        )

    def test_bio_state_changes_evidence_digest(self):
        changed = {
            "stress": 0.43,
            "attention": 0.82,
            "rir": 0.95,
            "atp": 2100,
        }
        self.assertNotEqual(
            self.valid().evidence_digest,
            self.valid(bio_state=changed).evidence_digest,
        )


if __name__ == "__main__":
    unittest.main()
