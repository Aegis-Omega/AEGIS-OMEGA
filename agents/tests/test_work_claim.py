from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from agents.organism import OrganismStore, OrganizationOrganism, WorkStatus

FRONTIER_DIR = Path(__file__).resolve().parents[2] / "platform" / "sol" / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))
from stream_lease import open_stream_lease  # noqa: E402


class DurableWorkClaimTests(unittest.TestCase):
    def make_org(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "organism.json"
        return OrganizationOrganism(OrganismStore(path)), path

    def require_api(self, org: OrganizationOrganism):
        for name in ("prepare_claim", "claim_work", "release_claim", "record_claimed_contribution"):
            if not callable(getattr(org, name, None)):
                self.fail(f"WORK_CLAIM_API_MISSING:{name}")

    def test_claim_uses_existing_frontier_fence_semantics(self):
        org, _ = self.make_org()
        self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        prepared = org.prepare_claim("w1")
        claim = org.claim_work(
            "w1", owner_identity="provider:openai:session:s1", expected_state_root=prepared["state_root"],
            lease_ms=10_000, now_ms=1_000,
        )
        expected = open_stream_lease("w1", "provider:openai:session:s1", generation=1)
        self.assertEqual(claim["generation"], 1)
        self.assertEqual(claim["fencing_token"], expected.fencing_token)
        self.assertEqual(claim["owner_identity"], "provider:openai:session:s1")
        self.assertEqual(claim["expires_ms"], 11_000)
        self.assertEqual(org.get("w1").status, WorkStatus.QUEUED)

    def test_second_provider_cannot_take_active_claim(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p = org.prepare_claim("w1")
        org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=10_000, now_ms=1_000)
        p2 = org.prepare_claim("w1")
        with self.assertRaisesRegex(ValueError, "WORK_CLAIM_ACTIVE"):
            org.claim_work("w1", owner_identity="provider:google:session:s2", expected_state_root=p2["state_root"], lease_ms=10_000, now_ms=2_000)

    def test_claim_is_prestate_fenced(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        stale = org.prepare_claim("w1")
        org.submit("w2", "research_request", {}, consequence_class="D1")
        with self.assertRaisesRegex(ValueError, "WORK_CLAIM_PRESTATE_STALE"):
            org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=stale["state_root"], lease_ms=10_000, now_ms=1_000)

    def test_expired_claim_can_be_reclaimed_with_higher_generation(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p1 = org.prepare_claim("w1")
        first = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p1["state_root"], lease_ms=1_000, now_ms=1_000)
        p2 = org.prepare_claim("w1")
        second = org.claim_work("w1", owner_identity="provider:google:session:s2", expected_state_root=p2["state_root"], lease_ms=1_000, now_ms=2_001)
        self.assertEqual(first["generation"], 1)
        self.assertEqual(second["generation"], 2)
        self.assertNotEqual(first["fencing_token"], second["fencing_token"])

    def test_same_owner_active_claim_is_idempotent(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p1 = org.prepare_claim("w1")
        first = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p1["state_root"], lease_ms=10_000, now_ms=1_000)
        p2 = org.prepare_claim("w1")
        second = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p2["state_root"], lease_ms=10_000, now_ms=2_000)
        self.assertEqual(first, second)
        self.assertEqual(len([e for e in org.store.journal() if e["event_type"] == "WORK_CLAIMED"]), 1)

    def test_matching_claim_can_record_contribution_and_consumes_claim(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p = org.prepare_claim("w1")
        claim = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=10_000, now_ms=1_000)
        digest = hashlib.sha256(b"bounded-result").hexdigest()
        ref = org.record_claimed_contribution(
            "w1", owner_identity=claim["owner_identity"], claim_generation=claim["generation"],
            claim_fencing_token=claim["fencing_token"], provider="openai", model="gpt-5.6-sol",
            artifact_digest=digest, source_ref="mcp:openai", now_ms=2_000,
        )
        order = org.get("w1")
        self.assertIn(ref, order.contribution_refs)
        self.assertIsNone(order.claim_owner_identity)
        self.assertIsNone(order.claim_fencing_token)
        self.assertIsNone(order.claim_expires_ms)
        self.assertEqual(order.claim_generation, 1)

    def test_stale_generation_or_fence_cannot_contribute(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p1 = org.prepare_claim("w1")
        first = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p1["state_root"], lease_ms=1_000, now_ms=1_000)
        p2 = org.prepare_claim("w1")
        org.claim_work("w1", owner_identity="provider:google:session:s2", expected_state_root=p2["state_root"], lease_ms=10_000, now_ms=2_001)
        with self.assertRaisesRegex(ValueError, "WORK_CLAIM_(OWNER|GENERATION|FENCE)_MISMATCH"):
            org.record_claimed_contribution(
                "w1", owner_identity=first["owner_identity"], claim_generation=first["generation"],
                claim_fencing_token=first["fencing_token"], provider="openai", model="gpt-5.6-sol",
                artifact_digest=hashlib.sha256(b"stale-result").hexdigest(), source_ref="mcp:openai", now_ms=2_100,
            )

    def test_expired_claim_cannot_contribute(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p = org.prepare_claim("w1")
        claim = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=1_000, now_ms=1_000)
        with self.assertRaisesRegex(ValueError, "WORK_CLAIM_EXPIRED"):
            org.record_claimed_contribution(
                "w1", owner_identity=claim["owner_identity"], claim_generation=claim["generation"],
                claim_fencing_token=claim["fencing_token"], provider="openai", model="gpt-5.6-sol",
                artifact_digest=hashlib.sha256(b"late").hexdigest(), source_ref="mcp:openai", now_ms=2_001,
            )

    def test_release_requires_exact_owner_generation_and_fence(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p = org.prepare_claim("w1")
        claim = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=10_000, now_ms=1_000)
        with self.assertRaisesRegex(ValueError, "WORK_CLAIM_FENCE_MISMATCH"):
            org.release_claim("w1", owner_identity=claim["owner_identity"], claim_generation=1, claim_fencing_token="0" * 64, now_ms=2_000)
        self.assertTrue(org.release_claim(
            "w1", owner_identity=claim["owner_identity"], claim_generation=claim["generation"],
            claim_fencing_token=claim["fencing_token"], now_ms=2_000,
        ))
        self.assertIsNone(org.get("w1").claim_owner_identity)

    def test_claim_survives_restart(self):
        org, path = self.make_org(); self.require_api(org)
        org.submit("w1", "research_request", {}, consequence_class="D1")
        p = org.prepare_claim("w1")
        claim = org.claim_work("w1", owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=10_000, now_ms=1_000)
        restored = OrganizationOrganism(OrganismStore(path)); self.require_api(restored)
        order = restored.get("w1")
        self.assertEqual(order.claim_generation, claim["generation"])
        self.assertEqual(order.claim_fencing_token, claim["fencing_token"])
        self.assertEqual(order.claim_owner_identity, claim["owner_identity"])

    def test_next_work_excludes_active_claim_and_contributed_work(self):
        org, _ = self.make_org(); self.require_api(org)
        org.submit("claimed", "research_request", {}, consequence_class="D1")
        org.submit("free", "research_request", {}, consequence_class="D1")
        p = org.prepare_claim("claimed")
        org.claim_work("claimed", owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=10_000, now_ms=1_000)
        self.assertEqual([w.work_id for w in org.next_work(now_ms=2_000)], ["free"])

    def test_d3_and_d4_never_become_claimable_without_authority_transition(self):
        org, _ = self.make_org(); self.require_api(org)
        d3 = org.submit("d3", "deployment_event", {}, consequence_class="D3")
        d4 = org.submit("d4", "forbidden", {}, consequence_class="D4")
        self.assertEqual(d3.status, WorkStatus.WAITING_OPERATOR)
        self.assertEqual(d4.status, WorkStatus.DENIED)
        for work_id in ("d3", "d4"):
            p = org.prepare_claim(work_id)
            with self.assertRaisesRegex(ValueError, "WORK_NOT_CLAIMABLE"):
                org.claim_work(work_id, owner_identity="provider:openai:session:s1", expected_state_root=p["state_root"], lease_ms=10_000, now_ms=1_000)


if __name__ == "__main__":
    unittest.main()
