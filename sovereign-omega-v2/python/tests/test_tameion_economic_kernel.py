"""Tameion A+C integration / safety lab. Synthetic observations, no payment."""
from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.arc_erc20_call import build_unsigned_transfer_call  # noqa: E402
from harness.sdk.arc_treasury_execution import plan_arc_testnet_transfer  # noqa: E402
from harness.sdk.sovereign_execution import (  # noqa: E402
    ADMITTED, D3, SCHEMA_VERSION, PolicyDecision, SovereignExecutionError,
)
from harness.sdk.tameion_economic_kernel import (  # noqa: E402
    EconomicAttempt, EconomicPolicy, audit_economic_boundary,
)
from harness.sdk.tameion_openmeter_bridge import (  # noqa: E402
    OpenMeterSettlementPolicy, OpenMeterUsageObservation,
    build_openmeter_arc_intent, build_openmeter_payment_obligation,
)
from harness.sdk.tameion_presettlement_bundle import build_tameion_pre_settlement_bundle  # noqa: E402

H1, H2, H4 = '1' * 64, '2' * 64, '4' * 64
DEST, SENDER = '0x' + '22' * 20, '0x' + '11' * 20


class EconomicKernelSafetyLab(unittest.TestCase):
    def fixture(self):
        usage = OpenMeterUsageObservation(
            schema_version=SCHEMA_VERSION, meter_slug='api_requests_total',
            event_id='quickstart-python-1', subject='quickstart-python', usage_units=1,
        )
        meter_policy = OpenMeterSettlementPolicy(
            schema_version=SCHEMA_VERSION, meter_slug='api_requests_total',
            unit_price_microunits=100, destination=DEST, max_amount_microunits=10_000,
        )
        obligation = build_openmeter_payment_obligation(usage=usage, policy=meter_policy)
        intent, binding = build_openmeter_arc_intent(
            obligation=obligation, authority_decision_root=H1,
            mutation_receipt_root=H2,
        )
        decision = PolicyDecision(
            schema_version=SCHEMA_VERSION, outcome=ADMITTED,
            authority_score='OBSERVED', action_class=D3,
            authority_domain='treasury.testnet', requested_capability='arc.testnet.transfer',
            tool='arc-plan', target_digest=H4, identity_root=H4,
            workspace_binding=H4, registry_root=H4, policy_root=H4,
            denial_codes=(), decision_root=H1,
        )
        plan = plan_arc_testnet_transfer(intent=intent, decision=decision, sender=SENDER)
        call = build_unsigned_transfer_call(plan)
        bundle = build_tameion_pre_settlement_bundle(
            obligation=obligation, source_binding=binding,
            plan=plan, unsigned_call=call,
        )
        policy = EconomicPolicy(
            schema_version=SCHEMA_VERSION, chain_id='5042002',
            asset='USDC', destination=DEST, budget_microunits=500,
            permitted_capabilities=('data.read',),
        )
        attempt = EconomicAttempt(
            attempt_id=plan.idempotency_key, requested_capabilities=('data.read',),
            confirmed_spend_microunits=0, reserved_spend_microunits=0,
            prior_attempt_ids=(),
        )
        return dict(policy=policy, attempt=attempt, obligation=obligation,
                    binding=binding, plan=plan, unsigned_call=call, bundle=bundle,
                    decision=decision, pinned_policy_root=policy.root,
                    pinned_decision_root=H1, pinned_mutation_receipt_root=H2)

    def audit(self, **mutations):
        inputs = self.fixture()
        inputs.update(mutations)
        return audit_economic_boundary(**inputs)

    def test_valid_synthetic_chain_is_evidence_only(self):
        r = self.audit()
        self.assertEqual(r.outcome, 'BOUNDARY_CHECKS_PASSED')
        self.assertEqual(r.authority_effect, 'NONE')
        self.assertEqual(r.network_effect, 'NONE')
        self.assertFalse(r.settlement_asserted)
        self.assertEqual(r.scope, 'EVIDENCE_ONLY_NON_AUTHORITATIVE')

    def test_deterministic_replay(self):
        self.assertEqual(self.audit().root, self.audit().root)

    def test_no_promotion_to_settlement(self):
        self.assertNotIn('SETTLED', self.audit().outcome)

    def test_policy_pin_does_not_match(self):
        self.assertIn('POLICY_PIN_MISMATCH', self.audit(pinned_policy_root=H4).denial_codes)

    def test_decision_pin_does_not_match(self):
        self.assertIn('DECISION_BINDING_MISMATCH', self.audit(pinned_decision_root=H4).denial_codes)

    def test_mutation_receipt_pin_does_not_match(self):
        self.assertIn('MUTATION_RECEIPT_PIN_MISMATCH', self.audit(pinned_mutation_receipt_root=H4).denial_codes)

    def test_denied_authority(self):
        f = self.fixture()
        f['decision'] = replace(f['decision'], outcome='DENIED', denial_codes=('TEST',))
        self.assertIn('AEGIS_AUTHORITY_NOT_ADMITTED', audit_economic_boundary(**f).denial_codes)

    def test_wrong_domain(self):
        f = self.fixture()
        f['decision'] = replace(f['decision'], authority_domain='unknown')
        self.assertIn('AEGIS_AUTHORITY_NOT_ADMITTED', audit_economic_boundary(**f).denial_codes)

    def test_wrong_capability_for_payment(self):
        f = self.fixture()
        f['decision'] = replace(f['decision'], requested_capability='unrelated')
        self.assertIn('AEGIS_AUTHORITY_NOT_ADMITTED', audit_economic_boundary(**f).denial_codes)

    def test_network_mismatch(self):
        f = self.fixture()
        f['plan'] = replace(f['plan'], chain_id='1')
        r = audit_economic_boundary(**f)
        self.assertIn('NETWORK_OR_ASSET_MISMATCH', r.denial_codes)
        self.assertIn('SOURCE_EVIDENCE_INVALID', r.denial_codes)

    def test_wrong_destination(self):
        f = self.fixture()
        f['policy'] = replace(f['policy'], destination=SENDER)
        f['pinned_policy_root'] = f['policy'].root
        self.assertIn('RECIPIENT_MISMATCH', audit_economic_boundary(**f).denial_codes)

    def test_bypassed_budget(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], confirmed_spend_microunits=401)
        self.assertIn('SIMULATED_BUDGET_EXCEEDED', audit_economic_boundary(**f).denial_codes)

    def test_reserved_budget_counts(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], reserved_spend_microunits=401)
        self.assertIn('SIMULATED_BUDGET_EXCEEDED', audit_economic_boundary(**f).denial_codes)

    def test_exact_budget_passes(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], reserved_spend_microunits=400)
        self.assertEqual(audit_economic_boundary(**f).outcome, 'BOUNDARY_CHECKS_PASSED')

    def test_new_capability_not_approved(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], requested_capabilities=('admin.write', 'data.read'))
        self.assertIn('CAPABILITY_ESCALATION', audit_economic_boundary(**f).denial_codes)

    def test_replayed_attempt(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], prior_attempt_ids=(f['attempt'].attempt_id,))
        self.assertIn('ATTEMPT_REPLAY_OR_ID_MISMATCH', audit_economic_boundary(**f).denial_codes)

    def test_swapped_attempt_id(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], attempt_id='different')
        self.assertIn('ATTEMPT_REPLAY_OR_ID_MISMATCH', audit_economic_boundary(**f).denial_codes)

    def test_tampered_pre_settlement_bundle(self):
        f = self.fixture()
        f['bundle'] = replace(f['bundle'], transfer_plan_root=H4)
        self.assertIn('BUNDLE_ROOT_MISMATCH', audit_economic_boundary(**f).denial_codes)

    def test_tampered_unsigned_call(self):
        f = self.fixture()
        f['unsigned_call'] = replace(f['unsigned_call'], broadcast_allowed=True)
        self.assertIn('SOURCE_EVIDENCE_INVALID', audit_economic_boundary(**f).denial_codes)

    def test_no_broadcast_authority(self):
        f = self.fixture()
        f['plan'] = replace(f['plan'], broadcast_allowed=True)
        self.assertIn('SOURCE_EVIDENCE_INVALID', audit_economic_boundary(**f).denial_codes)

    def test_policy_cannot_grant_authority(self):
        f = self.fixture()
        f['policy'] = replace(f['policy'], authority_effect='GRANTED')
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_POLICY_AUTHORITY_EFFECT_FORBIDDEN'):
            audit_economic_boundary(**f)

    def test_float_budget_forbidden(self):
        f = self.fixture()
        f['policy'] = replace(f['policy'], budget_microunits=500.0)
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_POLICY_BUDGET_INVALID'):
            audit_economic_boundary(**f)

    def test_bool_spend_forbidden(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], reserved_spend_microunits=True)
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_ATTEMPT_SPEND_INVALID'):
            audit_economic_boundary(**f)

    def test_duplicate_capabilities_forbidden(self):
        f = self.fixture()
        f['attempt'] = replace(f['attempt'], requested_capabilities=('data.read', 'data.read'))
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_ATTEMPT_IDENTIFIERS_INVALID'):
            audit_economic_boundary(**f)

    def test_unsorted_capabilities_forbidden(self):
        f = self.fixture()
        f['policy'] = replace(f['policy'], permitted_capabilities=('data.read', 'admin.write'))
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_POLICY_CAPABILITIES_INVALID'):
            audit_economic_boundary(**f)

    def test_invalid_pin_format(self):
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_PIN_FORMAT_INVALID'):
            self.audit(pinned_policy_root='not-a-hash')

    def test_wrong_source_type(self):
        with self.assertRaisesRegex(SovereignExecutionError, 'ECON_SOURCE_TYPE_INVALID'):
            self.audit(bundle={'fake': 1})


if __name__ == '__main__':
    unittest.main()
