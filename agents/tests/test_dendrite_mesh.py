"""Pure stdlib adversarial tests for read-only AEGIS dendritic propagation."""
import dataclasses
import unittest
from types import SimpleNamespace

from agents.dendrite_mesh import (
    DendriteEvent, DendriteMesh, DendriteNode, default_mesh, propagate_pipeline,
    digest,
)

HEAD = "a" * 40
RECORD = "b" * 64


def event(channel="CANDIDATE", **overrides):
    d = dict(origin="corpus_ingestor", topic="research", channel=channel,
             source_head=HEAD, source_record=RECORD, sequence=1, text="Test claim")
    d.update(overrides)
    return DendriteEvent.create(**d)


class DendriteTests(unittest.TestCase):
    def test_hops_and_branches(self):
        receipt = default_mesh().propagate(event(), ttl=2)
        self.assertEqual(receipt["delivered_roles"], [
            "corpus_ingestor", "applied_science", "batch_processor",
            "cybersecurity", "ai_research", "chronologist", "product_management"])

    def test_joins_and_cycles_deduplicate(self):
        r = default_mesh().propagate(event(), ttl=8)
        self.assertEqual(len(set(r["delivered_roles"])), len(r["delivered_roles"]))
        self.assertEqual(len(r["delivered_roles"]), 9)
        self.assertIn("DUPLICATE", [x["result"] for x in r["routes"]])

    def test_information_is_in_recipient_inbox(self):
        r = default_mesh().propagate(event(), ttl=4)
        recipient = r["inboxes"]["product_management"]
        self.assertEqual(recipient["text"], "Test claim")
        self.assertEqual(recipient["recipient"], "product_management")
        self.assertEqual(recipient["event_hash"], r["event_hash"])

    def test_ttl_zero(self):
        self.assertEqual(default_mesh().propagate(event(), ttl=0)["delivered_roles"], ["corpus_ingestor"])

    def test_quarantine_never_reaches_normal_business_or_research(self):
        r = default_mesh().propagate(event("QUARANTINE"), ttl=8)
        self.assertEqual(r["delivered_roles"], ["corpus_ingestor", "cybersecurity", "chronologist"])

    def test_unsubscribed_node_does_not_forward(self):
        r = default_mesh().propagate(event("QUARANTINE"), ttl=8)
        self.assertTrue(any(x["result"] == "NOT_SUBSCRIBED" for x in r["routes"]))

    def test_receipt_deterministic(self):
        a = default_mesh().propagate(event(), ttl=8)
        b = default_mesh().propagate(event(), ttl=8)
        self.assertEqual(a, b)
        self.assertEqual(a["receipt_hash"], digest({k: v for k, v in a.items() if k != "receipt_hash"}))

    def test_no_execution_authority(self):
        r = default_mesh().propagate(event())
        self.assertEqual((r["authority_effect"], r["execution_effect"]), ("NONE", "NONE"))
        self.assertEqual(r["epistemic_status"], "UNVERIFIED_SOURCE_CLAIM")

    def test_content_tampering_denied(self):
        with self.assertRaisesRegex(ValueError, "EVENT_DIGEST_MISMATCH"):
            default_mesh().propagate(dataclasses.replace(event(), text="new truth"))

    def test_source_head_tampering_denied(self):
        with self.assertRaisesRegex(ValueError, "EVENT_DIGEST_MISMATCH"):
            default_mesh().propagate(dataclasses.replace(event(), source_head="c" * 40))

    def test_source_record_tampering_denied(self):
        with self.assertRaisesRegex(ValueError, "EVENT_DIGEST_MISMATCH"):
            default_mesh().propagate(dataclasses.replace(event(), source_record="c" * 64))

    def test_invalid_head_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_HEAD"):
            event(source_head="not-a-git-head")

    def test_bad_record_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SOURCE_RECORD"):
            event(source_record="0" * 40)

    def test_invalid_channel_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_TOPIC_OR_CHANNEL"):
            event(channel="ADMIN")

    def test_oversized_claim_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_TEXT_SIZE"):
            event(text="x" * 4097)

    def test_negative_sequence_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SEQUENCE"):
            event(sequence=-1)

    def test_bool_sequence_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SEQUENCE"):
            event(sequence=True)

    def test_ttl_too_large_denied(self):
        with self.assertRaisesRegex(ValueError, "INVALID_TTL"):
            default_mesh().propagate(event(), ttl=9)

    def test_no_unknown_nodes(self):
        with self.assertRaisesRegex(ValueError, "UNKNOWN_TARGET_NODE"):
            DendriteMesh({"a": DendriteNode("a", frozenset({"research"}), frozenset({"CANDIDATE"}))}, {"a": ("b",)})

    def test_fanout_limit(self):
        names = [f"n{i}" for i in range(10)]
        nodes = {n: DendriteNode(n, frozenset({"research"}), frozenset({"CANDIDATE"})) for n in names}
        with self.assertRaisesRegex(ValueError, "INVALID_FANOUT"):
            DendriteMesh(nodes, {"n0": tuple(names[1:])})

    def test_non_subscribed_origin_denied(self):
        with self.assertRaisesRegex(ValueError, "ORIGIN_NOT_SUBSCRIBED"):
            default_mesh().propagate(event(origin="finance", channel="QUARANTINE"))

    def test_wrong_topic_denied(self):
        with self.assertRaisesRegex(ValueError, "ORIGIN_NOT_SUBSCRIBED"):
            default_mesh().propagate(event(topic="commerce"))

    def test_pipeline_integration(self):
        claims = [dict(admitted=True, record_hash="1"*64, sequence=0, claim="Candidate claim"),
                  dict(admitted=False, record_hash="2"*64, sequence=1, claim="Unknown claim")]
        pipeline = SimpleNamespace(chain_valid=True, kan_terminal_hash="3"*64, arbitration=claims)
        result = propagate_pipeline(pipeline, source_head=HEAD, ttl=8)
        self.assertEqual(len(result["events"]), 2)
        self.assertIn("finance", result["events"][0]["delivered_roles"])
        self.assertNotIn("finance", result["events"][1]["delivered_roles"])
        self.assertEqual(result["authority_effect"], "NONE")

    def test_pipeline_invalid_chain_denied(self):
        with self.assertRaisesRegex(ValueError, "PIPELINE_CHAIN_INVALID"):
            propagate_pipeline(SimpleNamespace(chain_valid=False), source_head=HEAD)

    def test_pipeline_bad_root_denied(self):
        with self.assertRaisesRegex(ValueError, "PIPELINE_ROOT_INVALID"):
            propagate_pipeline(SimpleNamespace(chain_valid=True, kan_terminal_hash="?"), source_head=HEAD)

    def test_pipeline_too_many_events_denied(self):
        p = SimpleNamespace(chain_valid=True, kan_terminal_hash="3"*64,
                            arbitration=[{}]*65)
        with self.assertRaisesRegex(ValueError, "TOO_MANY_EVENTS"):
            propagate_pipeline(p, source_head=HEAD)

    def test_pipeline_invalid_record_denied(self):
        p = SimpleNamespace(chain_valid=True, kan_terminal_hash="3"*64,
                            arbitration=[dict(admitted=True, record_hash="x", sequence=0, claim="X")])
        with self.assertRaisesRegex(ValueError, "INVALID_RECORD_HASH"):
            propagate_pipeline(p, source_head=HEAD)

    def test_real_offline_cognitive_pipeline_bridge(self):
        import asyncio
        from agents.cognitive_pipeline import run_pipeline
        p = asyncio.run(run_pipeline("Dendrite routing offline fixture"))
        self.assertTrue(p.chain_valid)
        routed = propagate_pipeline(p, source_head=HEAD, ttl=4)
        self.assertEqual(len(routed["events"]), len(p.arbitration))
        self.assertEqual(routed["pipeline_root"], p.kan_terminal_hash)
        self.assertTrue(all(e["authority_effect"] == "NONE" for e in routed["events"]))

    def test_no_live_side_effects(self):
        r = default_mesh().propagate(event())
        self.assertNotIn("authorized", str(r).lower())
        self.assertNotIn("executed", str(r).lower())


if __name__ == "__main__":
    unittest.main()
