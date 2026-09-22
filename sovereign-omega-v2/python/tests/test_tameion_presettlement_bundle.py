#!/usr/bin/env python3
"""Tests for the Tameion OpenMeter pre-settlement evidence packet."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_erc20_call import build_unsigned_transfer_call  # noqa: E402
from harness.sdk.arc_treasury_execution import plan_arc_testnet_transfer  # noqa: E402
from harness.sdk.sovereign_execution import (  # noqa: E402
    ADMITTED,
    D3,
    SCHEMA_VERSION,
    PolicyDecision,
    SovereignExecutionError,
)
from harness.sdk.tameion_openmeter_bridge import (  # noqa: E402
    OpenMeterSettlementPolicy,
    OpenMeterUsageObservation,
    build_openmeter_arc_intent,
    build_openmeter_payment_obligation,
)
from harness.sdk.tameion_presettlement_bundle import (  # noqa: E402
    build_tameion_pre_settlement_bundle,
)

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
DEST = "0x" + "22" * 20
SENDER = "0x" + "11" * 20


class TameionPreSettlementBundleTests(TestCase):
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

    def admitted_decision(self, *, decision_root: str = H1) -> PolicyDecision:
        return PolicyDecision(
            schema_version=SCHEMA_VERSION,
            outcome=ADMITTED,
            authority_score="OBSERVED",
            action_class=D3,
            authority_domain="treasury.testnet",
            requested_capability="arc.testnet.transfer",
            tool="arc-plan",
            target_digest=H4,
            identity_root=H4,
            workspace_binding=H4,
            registry_root=H4,
            policy_root=H4,
            denial_codes=(),
            decision_root=decision_root,
        )

    def chain(self):
        obligation = build_openmeter_payment_obligation(
            usage=self.usage(),
            policy=self.policy(),
        )
        intent, binding = build_openmeter_arc_intent(
            obligation=obligation,
            authority_decision_root=H1,
            mutation_receipt_root=H2,
        )
        plan = plan_arc_testnet_transfer(
            intent=intent,
            decision=self.admitted_decision(),
            sender=SENDER,
        )
        call = build_unsigned_transfer_call(plan)
        return obligation, binding, plan, call

    def test_exact_source_to_unsigned_call_builds_bundle(self) -> None:
        obligation, binding, plan, call = self.chain()
        bundle = build_tameion_pre_settlement_bundle(
            obligation=obligation,
            source_binding=binding,
            plan=plan,
            unsigned_call=call,
        )
        self.assertEqual(bundle.obligation_root, obligation.root)
        self.assertEqual(bundle.source_binding_root, binding.root)
        self.assertEqual(bundle.transfer_plan_root, plan.root)
        self.assertEqual(bundle.unsigned_call_root, call.root)
        self.assertEqual(bundle.authority_effect, "NONE")
        self.assertEqual(len(bundle.root), 64)

    def test_different_metered_event_cannot_reuse_binding(self) -> None:
        obligation, binding, plan, call = self.chain()
        other = build_openmeter_payment_obligation(
            usage=self.usage(event_id="quickstart-python-2"),
            policy=self.policy(),
        )
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PRESETTLEMENT_OBLIGATION_MISMATCH"):
            build_tameion_pre_settlement_bundle(
                obligation=other,
                source_binding=binding,
                plan=plan,
                unsigned_call=call,
            )

    def test_binding_cannot_swap_intent(self) -> None:
        obligation, binding, plan, call = self.chain()
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PRESETTLEMENT_INTENT_MISMATCH"):
            build_tameion_pre_settlement_bundle(
                obligation=obligation,
                source_binding=replace(binding, treasury_intent_root=H3),
                plan=plan,
                unsigned_call=call,
            )

    def test_binding_cannot_swap_authority_decision(self) -> None:
        obligation, binding, plan, call = self.chain()
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PRESETTLEMENT_AUTHORITY_MISMATCH"):
            build_tameion_pre_settlement_bundle(
                obligation=obligation,
                source_binding=replace(binding, authority_decision_root=H3),
                plan=plan,
                unsigned_call=call,
            )

    def test_unsigned_call_must_bind_exact_plan(self) -> None:
        obligation, binding, plan, _ = self.chain()
        altered_plan = replace(plan, amount_microunits=200)
        altered_call = build_unsigned_transfer_call(altered_plan)
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PRESETTLEMENT_CALL_MISMATCH"):
            build_tameion_pre_settlement_bundle(
                obligation=obligation,
                source_binding=binding,
                plan=plan,
                unsigned_call=altered_call,
            )

    def test_plan_amount_cannot_diverge_from_metered_obligation(self) -> None:
        obligation, binding, plan, _ = self.chain()
        altered_plan = replace(plan, amount_microunits=200)
        altered_call = build_unsigned_transfer_call(altered_plan)
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PRESETTLEMENT_AMOUNT_MISMATCH"):
            build_tameion_pre_settlement_bundle(
                obligation=obligation,
                source_binding=binding,
                plan=altered_plan,
                unsigned_call=altered_call,
            )

    def test_bundle_cannot_gain_authority(self) -> None:
        obligation, binding, plan, call = self.chain()
        bundle = build_tameion_pre_settlement_bundle(
            obligation=obligation,
            source_binding=binding,
            plan=plan,
            unsigned_call=call,
        )
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_PRESETTLEMENT_AUTHORITY_EFFECT_INVALID"):
            replace(bundle, authority_effect="GRANT").validate()


if __name__ == "__main__":
    main()
