"""Adversarial offline receipt/actor/token lifecycle tests, no network or state writes."""
import copy
import unittest

from agents.evolution_token_lifecycle import (
    EVENT_SCHEMA, SCHEMA, TOKEN_SCHEMA, SPINE_SCHEMA, digest,
    evaluate_lifecycle, sign_local_event,
)

SHA = "a" * 40
S1, S2, S3 = b"p" * 32, b"v" * 32, b"o" * 32
KEYS = {
    "builder": {"actor": "agent_a", "role": "proposer", "secret": S1},
    "checker": {"actor": "agent_b", "role": "verifier", "secret": S2},
    "operator": {"actor": "operator", "role": "operator", "secret": S3},
}
ISSUE = "Aegis-Omega/AEGIS-OMEGA#758"


def fixture():
    fields = {
        "schema": TOKEN_SCHEMA, "issue": ISSUE,
        "source_head": SHA,
        "graph_receipt_hash": "b" * 64, "evolution_round_hash": "c" * 64,
        "workplane_receipt": None, "self_promotion": "DENIED",
        "claims_verified": False, "authority_effect": "NONE", "execution_effect": "NONE",
        "operator_required": False,
    }
    token = {**fields, "token_id": digest(fields)}
    spine_fields = {
        "schema": SPINE_SCHEMA, "source_head": SHA,
        "issue_graph_root": "b" * 64, "evolution_round_root": "c" * 64,
        "workplane_receipt": None,
        "token_meaning": "CONTENT_ADDRESS_ONLY_NOT_A_CAPABILITY",
        "improvement_admission": "DENIED", "skill_tier_effect": "NONE",
        "authority_effect": "NONE", "execution_effect": "NONE",
        "issue_count": 1, "issue_contract_tokens": [token],
    }
    return {**spine_fields, "receipt_hash": digest(spine_fields)}


def event(spine, action, key, *, seq=0, prev=None, nonce=1, now=100):
    p = KEYS[key]
    body = {
        "schema": EVENT_SCHEMA, "token_id": spine["issue_contract_tokens"][0]["token_id"],
        "issue": ISSUE, "source_head": SHA,
        "sequence": seq, "prev_event_hash": prev or "0" * 64,
        "nonce": format(nonce, "064x"), "action": action,
        "actor": p["actor"], "key_id": key,
        "evidence_sha256": "d" * 64, "issued_at": now - 10,
        "expires_at": now + 10, "authority_effect": "NONE",
        "execution_effect": "NONE",
    }
    return sign_local_event(body, secret=p["secret"])


class TokenLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.spine = fixture()
        self.root = self.spine["receipt_hash"]

    def replay(self, events, *, keys=None, now=100, spine=None, root=None):
        return evaluate_lifecycle(spine or self.spine, events,
                                  trusted_spine_hash=root or self.root,
                                  trusted_keys=KEYS if keys is None else keys,
                                  now=now)

    def request(self):
        return event(self.spine, "REQUEST_REVIEW", "builder", nonce=1)

    def attest(self, req=None):
        req = req or self.request()
        return event(self.spine, "ATTEST_LOCAL_REVIEW", "checker", seq=1,
                     prev=digest(req), nonce=2)

    def test_empty_spine_is_inert(self):
        x = self.replay([])
        self.assertEqual(x["tokens"][0]["status"], "OBSERVED_UNVERIFIED")
        self.assertFalse(x["promotion_applied"])
        self.assertFalse(x["capability_granted"])

    def test_request_then_separate_reviewer(self):
        req = self.request()
        x = self.replay([req, self.attest(req)])
        self.assertEqual(x["tokens"][0]["status"],
                         "LOCAL_REVIEW_ATTESTED_EXTERNAL_ADMISSION_REQUIRED")
        self.assertEqual(x["admission"], "DENIED")
        self.assertFalse(x["publisher_authenticated"])

    def test_deterministic_independent_replay(self):
        req = self.request()
        events = [req, self.attest(req)]
        self.assertEqual(self.replay(events), self.replay(copy.deepcopy(events)))

    def test_tamper_mac_denied(self):
        req = self.request()
        req["evidence_sha256"] = "e" * 64
        with self.assertRaisesRegex(ValueError, "EVENT_HMAC_INVALID"):
            self.replay([req])

    def test_other_secret_cannot_sign_as_verifier(self):
        req = self.request()
        forged = self.attest(req)
        forged["signature"] = sign_local_event(
            {k: v for k, v in forged.items() if k != "signature"}, secret=S1)["signature"]
        with self.assertRaisesRegex(ValueError, "EVENT_HMAC_INVALID"):
            self.replay([req, forged])

    def test_proposer_cannot_attest(self):
        req = self.request()
        forged = event(self.spine, "ATTEST_LOCAL_REVIEW", "builder", seq=1,
                       prev=digest(req), nonce=2)
        with self.assertRaisesRegex(ValueError, "EVENT_ROLE_BINDING_INVALID"):
            self.replay([req, forged])

    def test_actor_alias_same_key_not_a_separate_reviewer(self):
        req = self.request()
        forged = self.attest(req)
        forged["actor"] = "agent_a"
        forged = sign_local_event({k: v for k, v in forged.items() if k != "signature"},
                                  secret=S2)
        with self.assertRaisesRegex(ValueError, "EVENT_ROLE_BINDING_INVALID"):
            self.replay([req, forged])

    def test_replay_duplicate_nonce_denied(self):
        req = self.request()
        next_ev = event(self.spine, "REVOKE", "operator", seq=1,
                        prev=digest(req), nonce=1)
        with self.assertRaisesRegex(ValueError, "EVENT_NONCE_REPLAY"):
            self.replay([req, next_ev])

    def test_chain_fork_denied(self):
        req = self.request()
        bad = event(self.spine, "ATTEST_LOCAL_REVIEW", "checker", seq=1, nonce=2)
        with self.assertRaisesRegex(ValueError, "EVENT_CHAIN_REPLAY_OR_FORK"):
            self.replay([req, bad])

    def test_sequence_skip_denied(self):
        bad = event(self.spine, "REQUEST_REVIEW", "builder", seq=2)
        with self.assertRaisesRegex(ValueError, "EVENT_CHAIN_REPLAY_OR_FORK"):
            self.replay([bad])

    def test_revoke_is_irreversible(self):
        req = self.request()
        revoked = event(self.spine, "REVOKE", "operator", seq=1,
                        prev=digest(req), nonce=2)
        x = self.replay([req, revoked])
        self.assertEqual(x["tokens"][0]["status"], "REVOKED_NOT_ADMITTED")
        retry = event(self.spine, "ATTEST_LOCAL_REVIEW", "checker", seq=2,
                      prev=digest(revoked), nonce=3)
        with self.assertRaisesRegex(ValueError, "TOKEN_REVOKED_IRREVERSIBLY"):
            self.replay([req, revoked, retry])

    def test_nonoperator_cannot_revoke(self):
        forged = event(self.spine, "REVOKE", "builder")
        with self.assertRaisesRegex(ValueError, "EVENT_ROLE_BINDING_INVALID"):
            self.replay([forged])

    def test_expired_review_event_denied(self):
        req = self.request()
        with self.assertRaisesRegex(ValueError, "EVENT_EXPIRED"):
            self.replay([req], now=111)

    def test_future_clock_denied(self):
        req = self.request()
        with self.assertRaisesRegex(ValueError, "EVENT_CLOCK_INVALID"):
            self.replay([req], now=89)

    def test_forged_spine_content_rehashed_cannot_replace_trusted_root(self):
        x = copy.deepcopy(self.spine)
        x["issue_contract_tokens"][0]["claims_verified"] = True
        t = x["issue_contract_tokens"][0]
        t["token_id"] = digest({k: v for k, v in t.items() if k != "token_id"})
        x["receipt_hash"] = digest({k: v for k, v in x.items() if k != "receipt_hash"})
        with self.assertRaisesRegex(ValueError, "SPINE_HASH_MISMATCH"):
            self.replay([], spine=x)

    def test_self_promotion_with_new_spine_root_still_denied(self):
        x = copy.deepcopy(self.spine)
        t = x["issue_contract_tokens"][0]
        t["self_promotion"] = "APPROVED"
        t["token_id"] = digest({k: v for k, v in t.items() if k != "token_id"})
        x["receipt_hash"] = digest({k: v for k, v in x.items() if k != "receipt_hash"})
        with self.assertRaisesRegex(ValueError, "TOKEN_CONTENT_BINDING_INVALID"):
            self.replay([], spine=x, root=x["receipt_hash"])

    def test_forged_token_id_denied(self):
        x = copy.deepcopy(self.spine)
        x["issue_contract_tokens"][0]["token_id"] = "f" * 64
        x["receipt_hash"] = digest({k: v for k, v in x.items() if k != "receipt_hash"})
        with self.assertRaisesRegex(ValueError, "TOKEN_CONTENT_BINDING_INVALID"):
            self.replay([], spine=x, root=x["receipt_hash"])

    def test_unknown_issue_binding_denied(self):
        req = self.request()
        req["issue"] = "Aegis-Omega/AEGIS-OMEGA#999"
        req = sign_local_event({k: v for k, v in req.items() if k != "signature"},
                               secret=S1)
        with self.assertRaisesRegex(ValueError, "EVENT_TOKEN_BINDING_INVALID"):
            self.replay([req])

    def test_unknown_token_denied(self):
        req = self.request()
        req["token_id"] = "f" * 64
        req = sign_local_event({k: v for k, v in req.items() if k != "signature"},
                               secret=S1)
        with self.assertRaisesRegex(ValueError, "EVENT_UNKNOWN_TOKEN"):
            self.replay([req])

    def test_attempt_to_promote_action_denied(self):
        req = self.request()
        req["action"] = "PROMOTE_TIER"
        req = sign_local_event({k: v for k, v in req.items() if k != "signature"},
                               secret=S1)
        with self.assertRaisesRegex(ValueError, "EVENT_ACTION_FORBIDDEN"):
            self.replay([req])

    def test_extra_capability_field_denied(self):
        req = self.request()
        req["capability"] = "D4"
        with self.assertRaisesRegex(ValueError, "EVENT_SCHEMA_INVALID"):
            self.replay([req])

    def test_missing_signing_key_denied(self):
        with self.assertRaisesRegex(ValueError, "EVENT_UNKNOWN_KEY"):
            self.replay([self.request()], keys={})

    def test_weak_key_denied(self):
        keys = copy.deepcopy(KEYS)
        keys["builder"]["secret"] = b"no"
        with self.assertRaisesRegex(ValueError, "INVALID_LOCAL_SECRET"):
            self.replay([self.request()], keys=keys)

    def test_tamper_signature_denied(self):
        req = self.request()
        req["signature"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "EVENT_HMAC_INVALID"):
            self.replay([req])

    def test_no_mutation_of_spine_or_events(self):
        req = self.request()
        before_s = copy.deepcopy(self.spine)
        before_r = copy.deepcopy(req)
        self.replay([req])
        self.assertEqual(self.spine, before_s)
        self.assertEqual(req, before_r)

    def test_events_not_valid_nonlist(self):
        with self.assertRaisesRegex(ValueError, "LIFECYCLE_INPUT_INVALID"):
            self.replay("not-events")

    def test_journal_checkpoint_matches(self):
        req = self.request()
        out = evaluate_lifecycle(self.spine, [req], trusted_spine_hash=self.root,
                                 trusted_keys=KEYS, now=100,
                                 trusted_journal_digest=digest([req]))
        self.assertEqual(out["journal_checkpoint"], "EXTERNAL_DIGEST_MATCHED")

    def test_journal_checkpoint_detects_revocation_history_truncation(self):
        req = self.request()
        revoked = event(self.spine, "REVOKE", "operator", seq=1,
                        prev=digest(req), nonce=2)
        pinned = digest([req, revoked])
        with self.assertRaisesRegex(ValueError, "TOKEN_JOURNAL_ROLLBACK_OR_TAMPER"):
            evaluate_lifecycle(self.spine, [req], trusted_spine_hash=self.root,
                               trusted_keys=KEYS, now=100,
                               trusted_journal_digest=pinned)

    def test_unanchored_replay_does_not_claim_rollback_resistance(self):
        req = self.request()
        out = self.replay([req])
        self.assertEqual(out["journal_checkpoint"],
                         "UNANCHORED_NO_ROLLBACK_PROTECTION")

    def test_revoke_only_as_first_event(self):
        revoked = event(self.spine, "REVOKE", "operator", nonce=6)
        self.assertEqual(self.replay([revoked])["tokens"][0]["status"],
                         "REVOKED_NOT_ADMITTED")


if __name__ == "__main__":
    unittest.main()
