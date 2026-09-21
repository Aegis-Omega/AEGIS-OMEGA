#!/usr/bin/env python3
"""Tests for evidence-only AEGIS Arc treasury settlement binding."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_treasury_witness import (  # noqa: E402
    ARC_MAINNET_CHAIN_ID,
    ARC_TESTNET_CHAIN_ID,
    ArcSettlementObservation,
    ArcTreasuryIntent,
    bind_arc_settlement,
)
from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError  # noqa: E402

HASH_A = "1" * 64
HASH_B = "2" * 64
ADDRESS = "0x" + "ab" * 20
TX_HASH = "0x" + "cd" * 32


class ArcTreasuryWitnessTests(TestCase):
    def intent(self, **changes) -> ArcTreasuryIntent:
        values = dict(
            schema_version=SCHEMA_VERSION,
            chain_id=ARC_TESTNET_CHAIN_ID,
            asset="USDC",
            amount_microunits=3_000_000,
            destination=ADDRESS,
            purpose="verified-milestone-payment",
            authority_decision_root=HASH_A,
            mutation_receipt_root=HASH_B,
            idempotency_key="tameion-demo-001",
        )
        values.update(changes)
        return ArcTreasuryIntent(**values)

    def observation(self, **changes) -> ArcSettlementObservation:
        values = dict(
            schema_version=SCHEMA_VERSION,
            chain_id=ARC_TESTNET_CHAIN_ID,
            tx_hash=TX_HASH,
            block_number=63_312_953,
            amount_microunits=3_000_000,
            destination=ADDRESS,
            status="CONFIRMED",
        )
        values.update(changes)
        return ArcSettlementObservation(**values)

    def test_intent_root_is_deterministic_and_address_case_canonical(self) -> None:
        a = self.intent()
        b = self.intent(destination=ADDRESS.upper().replace("0X", "0x"))
        self.assertEqual(a.root, b.root)

    def test_both_arc_chain_ids_are_admitted(self) -> None:
        self.assertEqual(self.intent(chain_id=ARC_MAINNET_CHAIN_ID).chain_id, ARC_MAINNET_CHAIN_ID)
        self.assertEqual(self.intent(chain_id=ARC_TESTNET_CHAIN_ID).chain_id, ARC_TESTNET_CHAIN_ID)
        self.intent(chain_id=ARC_MAINNET_CHAIN_ID).validate()
        self.intent(chain_id=ARC_TESTNET_CHAIN_ID).validate()

    def test_unknown_chain_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_CHAIN_UNSUPPORTED"):
            self.intent(chain_id="1").validate()

    def test_non_usdc_asset_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_ASSET_UNSUPPORTED"):
            self.intent(asset="ETH").validate()

    def test_nonpositive_amount_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_AMOUNT_INVALID"):
            self.intent(amount_microunits=0).validate()

    def test_invalid_authority_root_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "authority_decision_root:INVALID_SHA256"):
            self.intent(authority_decision_root="bad").validate()

    def test_invalid_destination_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "destination:INVALID_EVM_ADDRESS"):
            self.intent(destination="not-an-address").validate()

    def test_confirmed_observation_binds_to_intent(self) -> None:
        intent = self.intent()
        observation = self.observation()
        witness = bind_arc_settlement(intent, observation)
        self.assertEqual(witness.intent_root, intent.root)
        self.assertEqual(witness.settlement_root, observation.root)
        self.assertEqual(witness.authority_effect, "NONE")
        self.assertEqual(witness.scope, "EVIDENCE_ONLY")
        self.assertEqual(len(witness.root), 64)

    def test_amount_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_SETTLEMENT_AMOUNT_MISMATCH"):
            bind_arc_settlement(self.intent(), self.observation(amount_microunits=2_999_999))

    def test_destination_mismatch_fails_closed(self) -> None:
        other = "0x" + "ef" * 20
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_SETTLEMENT_DESTINATION_MISMATCH"):
            bind_arc_settlement(self.intent(), self.observation(destination=other))

    def test_chain_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_SETTLEMENT_CHAIN_MISMATCH"):
            bind_arc_settlement(self.intent(), self.observation(chain_id=ARC_MAINNET_CHAIN_ID))

    def test_reverted_transaction_never_binds(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_SETTLEMENT_NOT_CONFIRMED"):
            bind_arc_settlement(self.intent(), self.observation(status="REVERTED"))

    def test_invalid_tx_hash_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "tx_hash:INVALID_EVM_TX_HASH"):
            self.observation(tx_hash="0xdeadbeef").validate()


if __name__ == "__main__":
    main()
