#!/usr/bin/env python3
"""Tests for OpenMeter usage -> Arc Testnet intent binding."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_treasury_witness import ARC_TESTNET_CHAIN_ID  # noqa: E402
from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError  # noqa: E402
from harness.sdk.tameion_openmeter_bridge import (  # noqa: E402
    MAX_DEMO_SETTLEMENT_MICROUNITS,
    OpenMeterSettlementPolicy,
    OpenMeterUsageObservation,
    build_openmeter_arc_intent,
    build_openmeter_payment_obligation,
)

H1 = "1" * 64
H2 = "2" * 64
DEST = "0x" + "22" * 20


class OpenMeterArcBridgeTests(TestCase):
    def usage(self, **changes) -> OpenMeterUsageObservation:
        values = dict(
            schema_version=SCHEMA_VERSION,
            meter_slug="api_requests_total",
            event_id="quickstart-python-1",
            subject="quickstart-python",
            usage_units=1,
        )
        values.update(changes)
        return OpenMeterUsageObservation(**values)

    def policy(self, **changes) -> OpenMeterSettlementPolicy:
        values = dict(
            schema_version=SCHEMA_VERSION,
            meter_slug="api_requests_total",
            unit_price_microunits=100,
            destination=DEST,
            max_amount_microunits=10_000,
        )
        values.update(changes)
        return OpenMeterSettlementPolicy(**values)

    def test_one_metered_event_builds_deterministic_testnet_obligation(self) -> None:
        obligation = build_openmeter_payment_obligation(
            usage=self.usage(),
            policy=self.policy(),
        )
        self.assertEqual(obligation.amount_microunits, 100)
        self.assertEqual(obligation.chain_id, ARC_TESTNET_CHAIN_ID)
        self.assertEqual(obligation.idempotency_key, "openmeter:quickstart-python-1")
        self.assertEqual(obligation.authority_effect, "NONE")
        self.assertEqual(len(obligation.root), 64)

    def test_obligation_builds_arc_intent_and_source_binding(self) -> None:
        obligation = build_openmeter_payment_obligation(
            usage=self.usage(),
            policy=self.policy(),
        )
        intent, binding = build_openmeter_arc_intent(
            obligation=obligation,
            authority_decision_root=H1,
            mutation_receipt_root=H2,
        )
        self.assertEqual(intent.amount_microunits, 100)
        self.assertEqual(intent.destination, DEST)
        self.assertEqual(intent.idempotency_key, "openmeter:quickstart-python-1")
        self.assertEqual(binding.obligation_root, obligation.root)
        self.assertEqual(binding.treasury_intent_root, intent.root)
        self.assertEqual(binding.authority_effect, "NONE")

    def test_meter_policy_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_METER_POLICY_MISMATCH"):
            build_openmeter_payment_obligation(
                usage=self.usage(meter_slug="other_meter"),
                policy=self.policy(),
            )

    def test_cap_prevents_silent_large_obligation(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_SETTLEMENT_CAP_EXCEEDED"):
            build_openmeter_payment_obligation(
                usage=self.usage(usage_units=101),
                policy=self.policy(unit_price_microunits=100, max_amount_microunits=10_000),
            )

    def test_non_metered_input_is_rejected(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_USAGE_NOT_METERED"):
            build_openmeter_payment_obligation(
                usage=self.usage(status="PENDING"),
                policy=self.policy(),
            )

    def test_mainnet_policy_is_forbidden(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_SETTLEMENT_TESTNET_ONLY"):
            self.policy(chain_id="5042").validate()

    def test_policy_cannot_enable_broadcast_or_real_value(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_BROADCAST_AUTHORITY_FORBIDDEN"):
            self.policy(broadcast_allowed=True).validate()
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_REAL_VALUE_FORBIDDEN"):
            self.policy(real_value_allowed=True).validate()

    def test_demo_cap_itself_is_bounded(self) -> None:
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_MAX_AMOUNT_INVALID"):
            self.policy(max_amount_microunits=MAX_DEMO_SETTLEMENT_MICROUNITS + 1).validate()

    def test_derived_amount_cannot_be_tampered_with(self) -> None:
        obligation = build_openmeter_payment_obligation(
            usage=self.usage(),
            policy=self.policy(),
        )
        with self.assertRaisesRegex(SovereignExecutionError, "OPENMETER_OBLIGATION_AMOUNT_MISMATCH"):
            replace(obligation, amount_microunits=999).validate()


if __name__ == "__main__":
    main()
