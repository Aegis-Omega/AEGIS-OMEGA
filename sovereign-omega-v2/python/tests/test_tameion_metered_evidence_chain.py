#!/usr/bin/env python3
"""Tests for the metered OpenMeter -> Arc settlement evidence chain."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_erc20_call import build_unsigned_transfer_call  # noqa: E402
from harness.sdk.arc_treasury_execution import plan_arc_testnet_transfer  # noqa: E402
from harness.sdk.arc_treasury_witness import ArcSettlementObservation, bind_arc_settlement  # noqa: E402
from harness.sdk.sovereign_execution import (  # noqa: E402
    ADMITTED,
    D3,
    SCHEMA_VERSION,
    PolicyDecision,
    SovereignExecutionError,
)
from harness.sdk.tameion_metered_evidence_chain import (  # noqa: E402
    build_tameion_metered_evidence_chain,
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
TX = "0x" + "33" * 32


class TameionMeteredEvidenceChainTests(TestCase):
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

    def source_chain(self, *, event_id: str = "quickstart-python-1", amount_units: int = 1):
        usage = OpenMeterUsageObservation(
            schema_version=SCHEMA_VERSION,
            meter_slug="api_requests_total",
            event_id=event_id,
            subject="quickstart-python",
            usage_units=amount_units,
        )
        policy = OpenMeterSettlementPolicy(
            schema_version=SCHEMA_VERSION,
            meter_slug="api_requests_total",
            unit_price_microunits=100,
            destination=DEST,
            max_amount_microunits=10_000,
        )
        obligation = build_openmeter_payment_obligation(usage=usage, policy=policy)
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
        pre = build_tameion_pre_settlement_bundle(
            obligation=obligation,
            source_binding=binding,
            plan=plan,
            unsigned_call=call,
        )
        return obligation, intent, plan, pre

    def settlement_witness(self, *, intent, plan, tx_hash: str = TX):
        observation = ArcSettlementObservation(
            schema_version=SCHEMA_VERSION,
            chain_id=plan.chain_id,
            tx_hash=tx_hash,
            block_number=123456,
            amount_microunits=plan.amount_microunits,
            destination=plan.destination,
            status="CONFIRMED",
        )
        return bind_arc_settlement(intent, observation)

    def test_metered_event_closes_into_replayable_settlement_chain(self) -> None:
        obligation, intent, plan, pre = self.source_chain()
        witness = self.settlement_witness(intent=intent, plan=plan)
        chain, calibration = build_tameion_metered_evidence_chain(
            pre_settlement=pre,
            plan=plan,
            witness=witness,
            claimed_correctness_micros=900_000,
        )
        self.assertEqual(chain.pre_settlement_bundle_root, pre.root)
        self.assertEqual(chain.settlement_witness_root, witness.root)
        self.assertEqual(calibration.hd_micros, 100_000)
        self.assertEqual(chain.authority_effect, "NONE")
        self.assertEqual(len(chain.root), 64)

    def test_different_pre_settlement_plan_cannot_close_same_witness(self) -> None:
        _, intent, plan, _ = self.source_chain()
        witness = self.settlement_witness(intent=intent, plan=plan)

        _, _, other_plan, other_pre = self.source_chain(event_id="quickstart-python-2")
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_METERED_CHAIN_PLAN_MISMATCH"):
            build_tameion_metered_evidence_chain(
                pre_settlement=other_pre,
                plan=plan,
                witness=witness,
                claimed_correctness_micros=900_000,
            )

    def test_settlement_witness_for_other_intent_is_rejected(self) -> None:
        _, _, plan, pre = self.source_chain()
        _, other_intent, other_plan, _ = self.source_chain(event_id="quickstart-python-2")
        other_witness = self.settlement_witness(intent=other_intent, plan=other_plan)

        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_METERED_CHAIN_INTENT_MISMATCH"):
            build_tameion_metered_evidence_chain(
                pre_settlement=pre,
                plan=plan,
                witness=other_witness,
                claimed_correctness_micros=900_000,
            )

    def test_metered_chain_cannot_gain_authority(self) -> None:
        _, intent, plan, pre = self.source_chain()
        witness = self.settlement_witness(intent=intent, plan=plan)
        chain, _ = build_tameion_metered_evidence_chain(
            pre_settlement=pre,
            plan=plan,
            witness=witness,
            claimed_correctness_micros=1_000_000,
        )
        with self.assertRaisesRegex(SovereignExecutionError, "TAMEION_METERED_CHAIN_AUTHORITY_EFFECT_INVALID"):
            replace(chain, authority_effect="GRANT").validate()


if __name__ == "__main__":
    main()
