#!/usr/bin/env python3
"""Tests for the offline Tameion evidence demo CLI."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import ADMITTED, DENIED, D3, SCHEMA_VERSION, SovereignExecutionError  # noqa: E402
from harness.sdk.tameion_demo_cli import build_demo_packet  # noqa: E402

H1 = "1" * 64
H2 = "2" * 64
H4 = "4" * 64
DEST = "0x" + "22" * 20
SENDER = "0x" + "11" * 20
TX = "0x" + "33" * 32


class TameionDemoCliTests(TestCase):
    def decision(self, *, outcome: str = ADMITTED):
        return {
            "schema_version": SCHEMA_VERSION,
            "outcome": outcome,
            "authority_score": "OBSERVED",
            "action_class": D3,
            "authority_domain": "treasury.testnet",
            "requested_capability": "arc.testnet.transfer",
            "tool": "arc-plan",
            "target_digest": H4,
            "identity_root": H4,
            "workspace_binding": H4,
            "registry_root": H4,
            "policy_root": H4,
            "denial_codes": [] if outcome == ADMITTED else ["TEST_DENIAL"],
            "decision_root": H1,
        }

    def payload(self):
        return {
            "usage": {
                "meter_slug": "api_requests_total",
                "event_id": "quickstart-python-1",
                "subject": "quickstart-python",
                "usage_units": 1,
            },
            "settlement_policy": {
                "meter_slug": "api_requests_total",
                "unit_price_microunits": 100,
                "destination": DEST,
                "max_amount_microunits": 10_000,
            },
            "policy_decision": self.decision(),
            "mutation_receipt_root": H2,
            "sender": SENDER,
        }

    def test_dry_run_emits_only_pre_settlement_packet(self) -> None:
        packet = build_demo_packet(self.payload())
        self.assertEqual(packet["status"], "PRE_SETTLEMENT_READY")
        self.assertEqual(packet["authority_effect"], "NONE")
        self.assertEqual(packet["network_effect"], "NONE")
        self.assertFalse(packet["unsigned_call"]["broadcast_allowed"])
        self.assertFalse(packet["unsigned_call"]["signer_attached"])
        self.assertNotIn("settlement_witness_root", packet)
        self.assertEqual(len(packet["pre_settlement_bundle_root"]), 64)

    def test_observed_settlement_closes_final_metered_chain(self) -> None:
        payload = self.payload()
        payload["claimed_correctness_micros"] = 900_000
        payload["settlement_observation"] = {
            "chain_id": "5042002",
            "tx_hash": TX,
            "block_number": 123456,
            "amount_microunits": 100,
            "destination": DEST,
            "status": "CONFIRMED",
        }
        packet = build_demo_packet(payload)
        self.assertEqual(packet["status"], "SETTLEMENT_RECONCILED")
        self.assertEqual(packet["hallucination_delta_micros"], 100_000)
        self.assertEqual(len(packet["settlement_witness_root"]), 64)
        self.assertEqual(len(packet["metered_evidence_chain_root"]), 64)

    def test_denied_policy_decision_cannot_produce_transfer_plan(self) -> None:
        payload = self.payload()
        payload["policy_decision"] = self.decision(outcome=DENIED)
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_REQUIRES_ADMITTED_DECISION"):
            build_demo_packet(payload)

    def test_settlement_mismatch_fails_closed(self) -> None:
        payload = self.payload()
        payload["settlement_observation"] = {
            "chain_id": "5042002",
            "tx_hash": TX,
            "block_number": 123456,
            "amount_microunits": 101,
            "destination": DEST,
            "status": "CONFIRMED",
        }
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_SETTLEMENT_AMOUNT_MISMATCH"):
            build_demo_packet(payload)


if __name__ == "__main__":
    main()
