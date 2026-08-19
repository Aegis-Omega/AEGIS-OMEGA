from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.organism import OrganismStore, OrganizationOrganism


class WorkClaimConcurrencyTests(unittest.TestCase):
    def test_two_store_instances_cannot_both_claim_same_work(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "organism.json"
            first = OrganizationOrganism(OrganismStore(path))
            first.submit("w1", "research_request", {}, consequence_class="D1")
            second = OrganizationOrganism(OrganismStore(path))
            for org in (first, second):
                if not callable(getattr(org, "prepare_claim", None)) or not callable(getattr(org, "claim_work", None)):
                    self.fail("WORK_CLAIM_API_MISSING:cross_instance")

            p1 = first.prepare_claim("w1")
            first.claim_work(
                "w1", owner_identity="provider:openai:session:s1",
                expected_state_root=p1["state_root"], lease_ms=10_000, now_ms=1_000,
            )
            p2 = second.prepare_claim("w1")
            with self.assertRaisesRegex(ValueError, "WORK_CLAIM_ACTIVE"):
                second.claim_work(
                    "w1", owner_identity="provider:google:session:s2",
                    expected_state_root=p2["state_root"], lease_ms=10_000, now_ms=2_000,
                )


if __name__ == "__main__":
    unittest.main()
