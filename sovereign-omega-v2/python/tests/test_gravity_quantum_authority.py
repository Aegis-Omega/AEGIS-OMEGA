from __future__ import annotations

import unittest

import cross_boundary_authority as cba
import gravity_quantum_authority as gqa
import gravity_quantum_discriminator as d2
from gravity_quantum_policy import (
    GravityQuantumPolicyV1,
    TransitionEvidenceV1,
    evaluate_policy,
)

HEX = "a" * 64


def claim(claim_id, domain, carrier, scope, status, evidence=HEX):
    return cba.BoundClaimV1(
        claim_id,
        cba.ClaimCoordinateV1(domain, carrier, scope),
        status,
        evidence,
    )


def verified_bundle(gate_id, verifier_id, relation, evidence):
    verifier = cba._REGISTERED_BRIDGE_VERIFIERS[verifier_id]
    receipt = verifier(gate_id, relation, evidence)
    return cba.VerifiedBridgeGateV1(
        gate_id=gate_id,
        verifier_id=verifier_id,
        relation=relation,
        evidence=evidence,
        receipt=receipt,
    )


class GravityQuantumAuthorityTests(unittest.TestCase):
    def test_real_d2_receipt_reaches_model_discrimination_eligibility_only(self):
        source = claim(
            "KS-EQ87-90",
            "THEORY",
            "KRYHIN_SUDHIR",
            "EQ87_89_90",
            "NUMERICALLY_REPRODUCED",
        )
        target = claim(
            "AEGIS-GQ-D2",
            "MODEL_DISCRIMINATION",
            "AEGIS_D2",
            "REGISTERED_SIGNATURE",
            "OPEN",
        )
        criterion = cba.BridgeCriterionV1(
            "GQ_MODEL_TO_MODEL_DISCRIMINATOR",
            source.coordinate,
            target.coordinate,
            ("NUMERICALLY_REPRODUCED",),
            ("OPEN",),
            (
                cba.BridgeGateRequirementV1(
                    "D2_PUBLISHED_FORMULA",
                    gqa.D2_MODEL_VERIFIER_ID,
                ),
            ),
            "Published model formula replay may enter only the model-discrimination lane.",
        )
        relation = cba.bind_bridge_relation(source, target, criterion)
        evidence = d2.model_formula_receipt()
        bundle = verified_bundle(
            "D2_PUBLISHED_FORMULA",
            gqa.D2_MODEL_VERIFIER_ID,
            relation,
            evidence,
        )
        receipt = cba.evaluate_cross_boundary_authority(
            source, target, criterion, [bundle]
        )
        self.assertEqual(receipt.decision, cba.BridgeDecision.ELIGIBLE)
        self.assertEqual(
            receipt.claim_promotion,
            "ELIGIBLE_FOR_SEPARATE_TARGET_STATUS_TRANSITION",
        )
        self.assertEqual(receipt.authority_effect, "NONE")
        self.assertEqual(target.status, "OPEN")

    def test_f2b_not_run_kernel_receipt_denies_formal_to_witness_bridge(self):
        source = claim(
            "F2B",
            "FORMAL",
            "LEAN",
            "PURE_2Q_PRODUCT_BOUNDARY",
            "SOURCE_PREPARED",
        )
        target = claim(
            "WITNESS",
            "EMPIRICAL_INTERPRETATION",
            "ENTANGLEMENT_WITNESS",
            "TWO_BRANCH_MODEL",
            "OPEN",
        )
        criterion = cba.BridgeCriterionV1(
            "GQ_FORMAL_TO_WITNESS",
            source.coordinate,
            target.coordinate,
            ("SOURCE_PREPARED", "FORMALLY_KERNEL_VERIFIED"),
            ("OPEN",),
            (
                cba.BridgeGateRequirementV1(
                    "F2B_KERNEL",
                    gqa.F2B_KERNEL_VERIFIER_ID,
                ),
            ),
            "Only an exact kernel replay may satisfy F2b.",
        )
        relation = cba.bind_bridge_relation(source, target, criterion)
        evidence = {
            "schema": "AEGIS_GQ_F2B_KERNEL_RECEIPT_V1",
            "kernel_replay": "NOT_RUN",
            "theorem": "coeffDet_ne_zero_iff_not_pureProductCoeffs",
            "source_sha256": "b" * 64,
            "axiom_audit": "NOT_RUN",
            "sorryAx_present": False,
            "authority_effect": "NONE",
        }
        bundle = verified_bundle(
            "F2B_KERNEL",
            gqa.F2B_KERNEL_VERIFIER_ID,
            relation,
            evidence,
        )
        receipt = cba.evaluate_cross_boundary_authority(
            source, target, criterion, [bundle]
        )
        self.assertEqual(receipt.decision, cba.BridgeDecision.DENY)
        self.assertIn("FAIL_GATE_VERDICT", receipt.reason_codes)

    def test_quantization_interpretation_missing_real_evidence_denies(self):
        source = claim(
            "TABLETOP",
            "EMPIRICAL",
            "TABLETOP",
            "EXACT_APPARATUS",
            "OPEN",
        )
        target = claim(
            "GQ",
            "INTERPRETATION",
            "GRAVITY_QUANTIZATION",
            "TESTED_MODEL_CLASS",
            "OPEN",
        )
        criterion = self._quantization_criterion(source, target)
        receipt = cba.evaluate_cross_boundary_authority(
            source, target, criterion, []
        )
        self.assertEqual(receipt.decision, cba.BridgeDecision.DENY)
        self.assertIn("FAIL_REQUIRED_GATE", receipt.reason_codes)

    def test_synthetic_complete_quantization_bridge_is_eligibility_only(self):
        source = claim(
            "TABLETOP",
            "EMPIRICAL",
            "TABLETOP",
            "EXACT_APPARATUS",
            "EMPIRICALLY_OBSERVED",
        )
        target = claim(
            "GQ",
            "INTERPRETATION",
            "GRAVITY_QUANTIZATION",
            "TESTED_MODEL_CLASS",
            "OPEN",
        )
        criterion = self._quantization_criterion(source, target)
        relation = cba.bind_bridge_relation(source, target, criterion)

        d2_evidence = d2.model_formula_receipt()
        f2b = {
            "schema": "AEGIS_GQ_F2B_KERNEL_RECEIPT_V1",
            "kernel_replay": "PASS",
            "theorem": "coeffDet_ne_zero_iff_not_pureProductCoeffs",
            "source_sha256": "c" * 64,
            "axiom_audit": "PASS",
            "sorryAx_present": False,
            "authority_effect": "NONE",
        }
        physical = {
            "schema": "AEGIS_GQ_PHYSICAL_MEASUREMENT_RECEIPT_V1",
            "status": "PASS",
            "raw_data_bound": True,
            "calibration_pass": True,
            "nuisance_controls_pass": True,
            "preregistered": True,
            "authority_effect": "NONE",
        }
        nuisance = {
            "schema": "AEGIS_GQ_NUISANCE_RECEIPT_V1",
            "controls": {
                "mechanical_cross_talk": "PASS",
                "seismic_vibration": "PASS",
                "electromagnetic": "PASS",
                "laser_readout_cross_talk": "PASS",
                "thermal_common_bath": "PASS",
                "feedback_control": "PASS",
                "gravity_gradient_position": "PASS",
            },
            "authority_effect": "NONE",
        }
        replication = {
            "schema": "AEGIS_GQ_REPLICATION_RECEIPT_V1",
            "status": "PASS",
            "independent_apparatus": True,
            "independent_analysis": True,
            "same_preregistered_claim": True,
            "authority_effect": "NONE",
        }

        bundles = [
            verified_bundle(
                "PHYSICAL_MEASUREMENT",
                gqa.MEASUREMENT_VERIFIER_ID,
                relation,
                physical,
            ),
            verified_bundle(
                "NUISANCE_CONTROLS",
                gqa.NUISANCE_VERIFIER_ID,
                relation,
                nuisance,
            ),
            verified_bundle(
                "INDEPENDENT_REPLICATION",
                gqa.REPLICATION_VERIFIER_ID,
                relation,
                replication,
            ),
            verified_bundle(
                "F2B_KERNEL",
                gqa.F2B_KERNEL_VERIFIER_ID,
                relation,
                f2b,
            ),
            verified_bundle(
                "D2_MODEL_FORMULA",
                gqa.D2_MODEL_VERIFIER_ID,
                relation,
                d2_evidence,
            ),
        ]
        receipt = cba.evaluate_cross_boundary_authority(
            source, target, criterion, bundles
        )
        self.assertEqual(receipt.decision, cba.BridgeDecision.ELIGIBLE)
        self.assertEqual(receipt.authority_effect, "NONE")
        self.assertEqual(target.status, "OPEN")

    def test_executable_policy_denies_current_open_state(self):
        required = (
            "GQ-Q1_CALIBRATION",
            "GQ-Q2_NUISANCE",
            "GQ-Q3_MEASUREMENT",
            "GQ-Q4_WITNESS",
            "GQ-Q5_REPLICATION",
            "GQ-Q6_DISCRIMINATION",
            "GQ-FORMAL",
            "GQ-XB",
        )
        policy = GravityQuantumPolicyV1(
            "GQ_TABLETOP_DISCRIMINATION_V1", required
        )
        statuses = (
            "NOT_RUN",
            "NOT_RUN",
            "NOT_RUN",
            "NOT_RUN",
            "NOT_RUN",
            "OPEN",
            "OPEN",
            "DENY",
        )
        transitions = {
            transition_id: TransitionEvidenceV1(
                transition_id, status, f"{index + 1:064x}"
            )
            for index, (transition_id, status) in enumerate(
                zip(required, statuses)
            )
        }
        receipt = evaluate_policy(policy, "CURRENT", transitions)
        self.assertEqual(receipt.decision, "DENY")
        self.assertEqual(len(receipt.failures), 8)
        self.assertEqual(receipt.authority_effect, "NONE")

    @staticmethod
    def _quantization_criterion(source, target):
        return cba.BridgeCriterionV1(
            "GQ_EMPIRICAL_TO_QUANTIZATION_INTERPRETATION",
            source.coordinate,
            target.coordinate,
            ("OPEN", "EMPIRICALLY_OBSERVED"),
            ("OPEN",),
            (
                cba.BridgeGateRequirementV1(
                    "PHYSICAL_MEASUREMENT",
                    gqa.MEASUREMENT_VERIFIER_ID,
                ),
                cba.BridgeGateRequirementV1(
                    "NUISANCE_CONTROLS",
                    gqa.NUISANCE_VERIFIER_ID,
                ),
                cba.BridgeGateRequirementV1(
                    "INDEPENDENT_REPLICATION",
                    gqa.REPLICATION_VERIFIER_ID,
                ),
                cba.BridgeGateRequirementV1(
                    "F2B_KERNEL",
                    gqa.F2B_KERNEL_VERIFIER_ID,
                ),
                cba.BridgeGateRequirementV1(
                    "D2_MODEL_FORMULA",
                    gqa.D2_MODEL_VERIFIER_ID,
                ),
            ),
            "Quantization interpretation requires physical, nuisance, replication, formal, and model-discrimination gates.",
        )


if __name__ == "__main__":
    unittest.main()
