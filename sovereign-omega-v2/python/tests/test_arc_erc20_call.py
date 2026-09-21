#!/usr/bin/env python3
"""Tests for deterministic Arc USDC unsigned-call encoding."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_erc20_call import (  # noqa: E402
    ARC_USDC_INTERFACE,
    TRANSFER_SELECTOR,
    build_unsigned_transfer_call,
    encode_transfer_calldata,
)
from harness.sdk.arc_treasury_execution import ArcTransferPlan  # noqa: E402
from harness.sdk.arc_treasury_witness import ARC_TESTNET_CHAIN_ID  # noqa: E402
from harness.sdk.sovereign_execution import SovereignExecutionError  # noqa: E402

DEST = "0x" + "22" * 20
HASH = "1" * 64


class ArcErc20CallTests(TestCase):
    def plan(self, **changes) -> ArcTransferPlan:
        values = dict(
            schema_version="1.0.0",
            chain_id=ARC_TESTNET_CHAIN_ID,
            network="ARC-TESTNET",
            asset="USDC",
            token_interface=ARC_USDC_INTERFACE,
            sender="0x" + "11" * 20,
            destination=DEST,
            amount_microunits=1_000_000,
            idempotency_key="tameion-call-001",
            purpose="test-transfer",
            authority_decision_root=HASH,
            treasury_intent_root=HASH,
        )
        values.update(changes)
        return ArcTransferPlan(**values)

    def test_transfer_selector_and_length(self) -> None:
        data = encode_transfer_calldata(DEST, 1_000_000)
        self.assertTrue(data.startswith("0x" + TRANSFER_SELECTOR))
        self.assertEqual(len(data), 2 + 8 + 64 + 64)

    def test_destination_is_left_padded_to_word(self) -> None:
        data = encode_transfer_calldata(DEST, 1)
        address_word = data[10:74]
        self.assertEqual(address_word, ("0" * 24) + DEST[2:].lower())

    def test_amount_is_big_endian_uint256(self) -> None:
        data = encode_transfer_calldata(DEST, 1_000_000)
        self.assertEqual(int(data[-64:], 16), 1_000_000)

    def test_bad_destination_is_denied(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_CALL_ADDRESS_INVALID"):
            encode_transfer_calldata("bad", 1)

    def test_negative_amount_is_denied(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_CALL_UINT256_INVALID"):
            encode_transfer_calldata(DEST, -1)

    def test_plan_builds_unsigned_nonbroadcast_call(self) -> None:
        call = build_unsigned_transfer_call(self.plan())
        self.assertEqual(call.to, ARC_USDC_INTERFACE)
        self.assertEqual(call.value, 0)
        self.assertFalse(call.broadcast_allowed)
        self.assertFalse(call.signer_attached)
        self.assertEqual(call.authority_effect, "NONE")
        self.assertEqual(len(call.root), 64)

    def test_call_cannot_gain_broadcast_authority(self) -> None:
        call = build_unsigned_transfer_call(self.plan())
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_CALL_BROADCAST_AUTHORITY_FORBIDDEN"):
            replace(call, broadcast_allowed=True).validate()

    def test_call_cannot_gain_signer(self) -> None:
        call = build_unsigned_transfer_call(self.plan())
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_CALL_SIGNER_FORBIDDEN"):
            replace(call, signer_attached=True).validate()


if __name__ == "__main__":
    main()
