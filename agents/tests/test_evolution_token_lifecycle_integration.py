"""Actual existing spine contract -> new token lifecycle; no mocked graph reducer."""
import unittest

from agents.issue_evolution import compile_graph
from agents.evolution_contract_spine import compose_spine
from agents.evolution_token_lifecycle import (
    EVENT_SCHEMA, digest, sign_local_event, evaluate_lifecycle,
)

S1 = b"a" * 32
S2 = b"b" * 32
S3 = b"c" * 32
TRUST = {
    "proposer": {"actor": "builder", "role": "proposer", "secret": S1},
    "verifier": {"actor": "reviewer", "role": "verifier", "secret": S2},
    "operator": {"actor": "owner", "role": "operator", "secret": S3},
}


def real_spine():
    snapshot = {"repository": "Aegis-Omega/AEGIS-OMEGA", "complete_pages": True,
                "acquisition": "EXPLICIT_OFFLINE_FIXTURE", "pages": 1,
                "issues": [
                    {"number": 734, "title": "Firm of agents", "body": "", "labels": []},
                    {"number": 758, "title": "Evolution test", "body": "Parent #734", "labels": []},
                ]}
    graph = compile_graph(snapshot)
    return compose_spine(graph=graph, trials=[], source_head="a" * 40)


def seal(spine, token, action, who, seq=0, prev=None, nonce=1):
    p = TRUST[who]
    fields = {"schema": EVENT_SCHEMA, "token_id": token["token_id"],
              "issue": token["issue"], "source_head": spine["source_head"],
              "sequence": seq, "prev_event_hash": prev or "0" * 64,
              "nonce": format(nonce, "064x"), "action": action,
              "actor": p["actor"], "key_id": who,
              "evidence_sha256": "e" * 64,
              "issued_at": 90, "expires_at": 110,
              "authority_effect": "NONE", "execution_effect": "NONE"}
    return sign_local_event(fields, secret=p["secret"])


class RealSpineTokenIntegration(unittest.TestCase):
    def test_two_actual_issue_contract_tokens(self):
        spine = real_spine()
        result = evaluate_lifecycle(spine, [], trusted_spine_hash=spine["receipt_hash"],
                                    trusted_keys=TRUST, now=100)
        self.assertEqual(result["token_count"], 2)
        self.assertTrue(all(t["status"] == "OBSERVED_UNVERIFIED" for t in result["tokens"]))
        self.assertFalse(result["promotion_applied"])

    def test_one_issue_review_cannot_promote_other_issue(self):
        spine = real_spine()
        target = next(t for t in spine["issue_contract_tokens"] if t["issue"].endswith("#758"))
        request = seal(spine, target, "REQUEST_REVIEW", "proposer")
        attested = seal(spine, target, "ATTEST_LOCAL_REVIEW", "verifier", 1, digest(request), 2)
        result = evaluate_lifecycle(spine, [request, attested],
                                    trusted_spine_hash=spine["receipt_hash"],
                                    trusted_keys=TRUST, now=100)
        index = {t["issue"]: t for t in result["tokens"]}
        self.assertEqual(index["Aegis-Omega/AEGIS-OMEGA#734"]["status"],
                         "OBSERVED_UNVERIFIED")
        self.assertEqual(index["Aegis-Omega/AEGIS-OMEGA#758"]["status"],
                         "LOCAL_REVIEW_ATTESTED_EXTERNAL_ADMISSION_REQUIRED")
        self.assertEqual(result["admission"], "DENIED")

    def test_revocation_does_not_spread_as_authority(self):
        spine = real_spine()
        target = spine["issue_contract_tokens"][0]
        rev = seal(spine, target, "REVOKE", "operator")
        out = evaluate_lifecycle(spine, [rev], trusted_spine_hash=spine["receipt_hash"],
                                 trusted_keys=TRUST, now=100)
        self.assertEqual(sum(t["revoked"] for t in out["tokens"]), 1)
        self.assertFalse(out["capability_granted"])


if __name__ == "__main__":
    unittest.main()
