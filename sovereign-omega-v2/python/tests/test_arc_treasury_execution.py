#!/usr/bin/env python3
"""Tests for governed non-broadcast Arc Testnet transfer planning."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_treasury_execution import (  # noqa: E402
    ARC_TESTNET_NETWORK,
    ARC_USDC_INTERFACE,
    plan_arc_testnet_transfer,
)
from harness.sdk.arc_treasury_witness import (  # noqa: E402
    ARC_MAINNET_CHAIN_ID,
    ARC_TESTNET_CHAIN_ID,
    ArcTreasuryIntent,
)
from harness.sdk.sovereign_execution import (  # noqa: E402
    ADMITTED,
    DENIED,
    D2,
    D3,
    D4,
    PolicyDecision,
    SCHEMA_VERSION,
    SovereignExecutionError,
)

HASH_A = "1" * 64
HASH_B = "2" * 64
HASH_C = "3" * 64
SENDER = "0x" + "11" * 20
DEST = "0x" + "22" * 20


class ArcTreasuryExecutionTests(TestCase):
    def decision(self, **changes) -> PolicyDecision:
        values = dict(
            schema_version=SCHEMA_VERSION,
            outcome=ADMITTED,
            authority_score="0.900000",
            action_class=D3,
            authority_domain="arc:treasury",
            requested_capability="treasury.settle",
            tool="arc-testnet",
            target_digest=HASH_B,
            identity_root=HASH_B,
            workspace_binding=HASH_B,
            registry_root=HASH_B,
            policy_root=HASH_B,
            denial_codes=(),
            decision_root=HASH_A,
        )
        values.update(changes)
        return PolicyDecision(**values)

    def intent(self, **changes) -> ArcTreasuryIntent:
        values = dict(
            schema_version=SCHEMA_VERSION,
            chain_id=ARC_TESTNET_CHAIN_ID,
            asset="USDC",
            amount_microunits=1_000_000,
            destination=DEST,
            purpose="tameion-first-settlement",
            authority_decision_root=HASH_A,
            mutation_receipt_root=HASH_C,
            idempotency_key="tameion-settlement-001",
        )
        values.update(changes)
        return ArcTreasuryIntent(**values)

    def test_d3_admitted_decision_builds_nonbroadcast_plan(self) -> None:
        plan = plan_arc_testnet_transfer(intent=self.intent(), decision=self.decision(), sender=SENDER)
        self.assertEqual(plan.network, ARC_TESTNET_NETWORK)
        self.assertEqual(plan.token_interface, ARC_USDC_INTERFACE)
        self.assertFalse(plan.broadcast_allowed)
        self.assertFalse(plan.real_value_allowed)
        self.assertEqual(plan.authority_effect, "NONE")
        self.assertEqual(len(plan.root), 64)

    def test_d4_is_also_accepted(self) -> None:
        plan = plan_arc_testnet_transfer(
            intent=self.intent(),
            decision=self.decision(action_class=D4),
            sender=SENDER,
        )
        self.assertEqual(plan.amount_microunits, 1_000_000)

    def test_d2_is_denied(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_REQUIRES_D3_OR_D4"):
            plan_arc_testnet_transfer(
                intent=self.intent(),
                decision=self.decision(action_class=D2),
                sender=SENDER,
            )

    def test_denied_policy_decision_is_denied(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_REQUIRES_ADMITTED_DECISION"):
            plan_arc_testnet_transfer(
                intent=self.intent(),
                decision=self.decision(outcome=DENIED),
                sender=SENDER,
            )

    def test_authority_root_must_match(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_AUTHORITY_ROOT_MISMATCH"):
            plan_arc_testnet_transfer(
                intent=self.intent(authority_decision_root=HASH_C),
                decision=self.decision(),
                sender=SENDER,
            )

    def test_mainnet_intent_is_refused(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_TESTNET_ONLY"):
            plan_arc_testnet_transfer(
                intent=self.intent(chain_id=ARC_MAINNET_CHAIN_ID),
                decision=self.decision(),
                sender=SENDER,
            )

    def test_sender_is_canonicalized(self) -> None:
        sender = "0x" + "Aa" * 20
        plan = plan_arc_testnet_transfer(intent=self.intent(), decision=self.decision(), sender=sender)
        self.assertEqual(plan.sender, sender.lower())

    def test_bad_sender_is_refused(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_ADDRESS_INVALID"):
            plan_arc_testnet_transfer(
                intent=self.intent(),
                decision=self.decision(),
                sender="not-an-address",
            )

    def test_plan_cannot_be_mutated_into_broadcast_authority(self) -> None:
        plan = plan_arc_testnet_transfer(intent=self.intent(), decision=self.decision(), sender=SENDER)
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_BROADCAST_AUTHORITY_FORBIDDEN"):
            replace(plan, broadcast_allowed=True).validate()

    def test_plan_cannot_be_mutated_into_real_value_authority(self) -> None:
        plan = plan_arc_testnet_transfer(intent=self.intent(), decision=self.decision(), sender=SENDER)
        with self.assertRaisesRegex(SovereignExecutionError, "ARC_EXECUTION_REAL_VALUE_FORBIDDEN"):
            replace(plan, real_value_allowed=True).validate()


if __name__ == "__main__":
    main()
