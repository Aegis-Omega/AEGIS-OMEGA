from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

import research_invariants as ri
from cross_boundary_authority import (
    BoundClaimV1,
    BridgeCriterionV1,
    BridgeDecision,
    ClaimCoordinateV1,
    bind_bridge_relation,
    evaluate_cross_boundary_authority,
    verify_cross_boundary_authority_receipt,
)

HEX = "a" * 64


def claim(claim_id, domain, carrier, scope, status, evidence=HEX):
    return BoundClaimV1(
        claim_id,
        ClaimCoordinateV1(domain, carrier, scope),
        status,
        evidence,
    )


def criterion(
    source,
    target,
    source_status=("VERIFIED",),
    target_status=("OPEN",),
    gates=("g1", "g2"),
):
    return BridgeCriterionV1(
        "B",
        source.coordinate,
        target.coordinate,
        source_status,
        target_status,
        gates,
        "frozen bridge criterion",
    )


class CrossBoundaryAuthorityTests(unittest.TestCase):
    def test_positive_synthetic_requires_all_relation_bound_passes(self):
        source = claim("s", "d1", "formal", "finite", "VERIFIED")
        target = claim("t", "d2", "empirical", "local", "OPEN")
        bridge = criterion(source, target)
        relation = bind_bridge_relation(source, target, bridge)
        receipts = [
            ri.relation_gate_receipt(
                gate_id=gate_id,
                relation=relation,
                verdict=ri.GateVerdict.PASS,
                observation={"ok": True},
            )
            for gate_id in bridge.required_gate_ids
        ]

        result = evaluate_cross_boundary_authority(
            source, target, bridge, receipts
        )
        self.assertIs(result.decision, BridgeDecision.ELIGIBLE)
        self.assertEqual(result.changed_axes, ("DOMAIN", "CARRIER", "SCOPE"))
        self.assertEqual(result.authority_effect, "NONE")
        self.assertTrue(
            verify_cross_boundary_authority_receipt(
                result, source, target, bridge, receipts
            )
        )

    def test_missing_gate_fails_closed(self):
        source = claim("s", "d1", "formal", "finite", "VERIFIED")
        target = claim("t", "d2", "empirical", "local", "OPEN")
        bridge = criterion(source, target)
        relation = bind_bridge_relation(source, target, bridge)
        receipt = ri.relation_gate_receipt(
            gate_id="g1",
            relation=relation,
            verdict=ri.GateVerdict.PASS,
            observation={},
        )

        result = evaluate_cross_boundary_authority(
            source, target, bridge, [receipt]
        )
        self.assertIs(result.decision, BridgeDecision.DENY)
        self.assertEqual(result.missing_gate_ids, ("g2",))

    def test_spliced_relation_receipt_fails(self):
        source = claim("s", "d1", "formal", "finite", "VERIFIED")
        target = claim("t", "d2", "empirical", "local", "OPEN")
        other = claim("u", "d2", "empirical", "local", "OPEN")
        bridge = criterion(source, target)
        other_bridge = BridgeCriterionV1(
            "B",
            source.coordinate,
            other.coordinate,
            ("VERIFIED",),
            ("OPEN",),
            ("g1", "g2"),
            "frozen bridge criterion",
        )
        wrong_relation = bind_bridge_relation(source, other, other_bridge)
        receipts = [
            ri.relation_gate_receipt(
                gate_id=gate_id,
                relation=wrong_relation,
                verdict=ri.GateVerdict.PASS,
                observation={},
            )
            for gate_id in ("g1", "g2")
        ]

        result = evaluate_cross_boundary_authority(
            source, target, bridge, receipts
        )
        self.assertIn("FAIL_GATE_RECEIPT_BINDING", result.reason_codes)

    def test_tampered_witness_fails(self):
        source = claim("s", "d1", "formal", "finite", "VERIFIED")
        target = claim("t", "d2", "empirical", "local", "OPEN")
        bridge = criterion(source, target)
        relation = bind_bridge_relation(source, target, bridge)
        receipts = [
            ri.relation_gate_receipt(
                gate_id=gate_id,
                relation=relation,
                verdict=ri.GateVerdict.PASS,
                observation={},
            )
            for gate_id in bridge.required_gate_ids
        ]
        receipts[0] = replace(receipts[0], witness_sha256="0" * 64)

        result = evaluate_cross_boundary_authority(
            source, target, bridge, receipts
        )
        self.assertIn("FAIL_GATE_RECEIPT_BINDING", result.reason_codes)

    def test_no_boundary_and_bad_status_fail(self):
        source = claim("s", "d", "formal", "finite", "OPEN")
        target = claim("t", "d", "formal", "finite", "OPEN")
        bridge = criterion(source, target)

        result = evaluate_cross_boundary_authority(
            source, target, bridge, []
        )
        self.assertIn("FAIL_NO_BOUNDARY_CHANGE", result.reason_codes)
        self.assertIn("FAIL_SOURCE_STATUS", result.reason_codes)

    def test_qbp_and_repo_boundary_fixture_stays_denied(self):
        fixture_path = (
            Path(__file__).resolve().parents[3]
            / ".aegis"
            / "cross-domain"
            / "fixtures"
            / "qbp-cross-boundary-v1.json"
        )
        fixture = json.loads(fixture_path.read_text())
        self.assertEqual(fixture["authority_effect"], "NONE")

        drift = fixture["source_bindings"]["qbp_package"][
            "stale_documentation_observation"
        ]
        self.assertEqual(
            (
                drift["documented_expected_pytest_cases"],
                drift["fresh_replay_pytest_cases"],
            ),
            (35, 45),
        )

        for case in fixture["cases"]:
            source_coordinate = case["source"]["coordinate"]
            target_coordinate = case["target"]["coordinate"]
            source = BoundClaimV1(
                case["source"]["claim_id"],
                ClaimCoordinateV1(**source_coordinate),
                case["source"]["status"],
                case["source"]["evidence_sha256"],
            )
            target = BoundClaimV1(
                case["target"]["claim_id"],
                ClaimCoordinateV1(**target_coordinate),
                case["target"]["status"],
                case["target"]["evidence_sha256"],
            )
            raw = case["criterion"]
            bridge = BridgeCriterionV1(
                raw["bridge_id"],
                source.coordinate,
                target.coordinate,
                tuple(raw["allowed_source_statuses"]),
                tuple(raw["allowed_target_statuses"]),
                tuple(raw["required_gate_ids"]),
                raw["criterion_text"],
            )
            result = evaluate_cross_boundary_authority(
                source, target, bridge, []
            )

            self.assertEqual(
                result.decision.value,
                case["expected_decision"],
                case["id"],
            )
            for reason in case["expected_reason_codes"]:
                self.assertIn(reason, result.reason_codes, case["id"])
            self.assertEqual(result.authority_effect, "NONE", case["id"])


if __name__ == "__main__":
    unittest.main()
