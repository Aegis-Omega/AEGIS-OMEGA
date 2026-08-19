from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from agents.organism import MAX_TEXT_CONTRIBUTION_BYTES, OrganismStore, OrganizationOrganism, WorkStatus


class ProviderContributionTests(unittest.TestCase):
    def make_org(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        return OrganizationOrganism(OrganismStore(Path(td.name) / "organism.json"))

    def test_provider_can_record_digest_on_existing_work_without_authority_promotion(self):
        org = self.make_org()
        org.submit("w1", "research_request", {"topic": "effect verification"}, consequence_class="D1")
        digest = hashlib.sha256(b"provider-output").hexdigest()
        ref = org.record_contribution("w1", provider="openai", model="gpt-5.6-sol", artifact_digest=digest, source_ref="mcp:openai")
        order = org.get("w1")
        self.assertEqual(order.status, WorkStatus.QUEUED)
        self.assertEqual(order.contribution_refs, (ref,))
        self.assertIn(digest, ref)

    def test_same_contribution_is_idempotent(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        digest = hashlib.sha256(b"x").hexdigest()
        first = org.record_contribution("w1", provider="gemini", model="gemini-3", artifact_digest=digest, source_ref="mcp:gemini")
        second = org.record_contribution("w1", provider="gemini", model="gemini-3", artifact_digest=digest, source_ref="mcp:gemini")
        self.assertEqual(first, second)
        self.assertEqual(org.get("w1").contribution_refs, (first,))

    def test_unknown_work_fails_closed(self):
        org = self.make_org()
        digest = hashlib.sha256(b"x").hexdigest()
        with self.assertRaises(KeyError):
            org.record_contribution("missing", provider="claude", model="opus", artifact_digest=digest, source_ref="mcp:claude")

    def test_invalid_digest_is_rejected(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        with self.assertRaises(ValueError):
            org.record_contribution("w1", provider="deepseek", model="r1", artifact_digest="abc", source_ref="mcp:deepseek")

    def test_provider_identity_fields_are_bounded(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        digest = hashlib.sha256(b"x").hexdigest()
        with self.assertRaises(ValueError):
            org.record_contribution("w1", provider="bad provider\n", model="m", artifact_digest=digest, source_ref="mcp:x")

    def test_journal_contains_non_authoritative_contribution_event(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        digest = hashlib.sha256(b"x").hexdigest()
        org.record_contribution("w1", provider="local", model="llama", artifact_digest=digest, source_ref="mcp:local")
        contribution = [e for e in org.store.journal() if e["event_type"] == "PROVIDER_CONTRIBUTION_RECORDED"]
        self.assertEqual(len(contribution), 1)
        self.assertEqual(contribution[0]["body"]["authority"], "NON_AUTHORITATIVE_EVIDENCE")
        self.assertEqual(org.get("w1").status, WorkStatus.QUEUED)

    def test_text_contribution_is_content_addressed_and_persisted(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        result = org.contribute_text("w1", provider="openai", model="gpt-5.6-sol", text="# useful work\nproof body", source_ref="mcp:openai")
        digest = hashlib.sha256(b"# useful work\nproof body").hexdigest()
        self.assertEqual(result["artifact"]["sha256"], digest)
        self.assertEqual(result["artifact"]["authority"], "NON_AUTHORITATIVE_EVIDENCE")
        artifact_path = Path(result["artifact"]["artifact_path"])
        self.assertTrue(artifact_path.is_file())
        stored = json.loads(artifact_path.read_text())
        self.assertEqual(stored["content"], "# useful work\nproof body")
        self.assertEqual(org.get("w1").status, WorkStatus.QUEUED)

    def test_text_contribution_is_idempotent(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        first = org.contribute_text("w1", provider="gemini", model="gemini-3", text="same", source_ref="mcp:gemini")
        second = org.contribute_text("w1", provider="gemini", model="gemini-3", text="same", source_ref="mcp:gemini")
        self.assertEqual(first["contribution_ref"], second["contribution_ref"])
        self.assertEqual(org.get("w1").contribution_refs, (first["contribution_ref"],))

    def test_text_contribution_size_is_bounded(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        with self.assertRaisesRegex(ValueError, "CONTRIBUTION_TOO_LARGE"):
            org.contribute_text("w1", provider="claude", model="opus", text="x" * (MAX_TEXT_CONTRIBUTION_BYTES + 1), source_ref="mcp:claude")

    def test_artifact_tamper_is_detected(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        result = org.contribute_text("w1", provider="local", model="llama", text="original", source_ref="mcp:local")
        path = Path(result["artifact"]["artifact_path"])
        record = json.loads(path.read_text())
        record["content"] = "tampered"
        path.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "CONTRIBUTION_ARTIFACT_TAMPER_DETECTED"):
            org.contribution_store.get(result["artifact"]["sha256"])

    def test_next_work_exposes_only_queued_non_operator_items(self):
        org = self.make_org()
        org.submit("q1", "research_request", {"topic": "a"}, consequence_class="D1")
        org.submit("q2", "code_request", {"topic": "b"}, consequence_class="D2")
        org.submit("wait", "deployment_event", {}, consequence_class="D3")
        org.submit("deny", "forbidden", {}, consequence_class="D4")
        self.assertEqual([w.work_id for w in org.next_work()], ["q1", "q2"])

    def test_empty_text_contribution_is_rejected(self):
        org = self.make_org()
        org.submit("w1", "research_request", {}, consequence_class="D1")
        with self.assertRaisesRegex(ValueError, "CONTRIBUTION_EMPTY"):
            org.contribute_text("w1", provider="openai", model="gpt-5.6-sol", text="", source_ref="mcp:openai")


if __name__ == "__main__":
    unittest.main()
