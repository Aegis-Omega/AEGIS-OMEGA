"""No AEGIS skill may self-certify its growth from mutable counters.

These tests validate that fabricated success events, inflated run histories
and eligibility claims cannot cross the operational authority boundary.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from agents.evolution import AdaptiveLineage, EvolutionEngine
from harness.sdk.skill_routing import (
    decide_skill_routing, propose_skill_observation, record_skill_observation,
)
from harness.sdk.skill_authority import (
    compute_registry_root, evaluate_registry, sanitize_legacy_tree,
)


def tree() -> dict:
    legacy = {
        "phase": 1, "doc_count": 1,
        "skills": [{
            "skill_id": "build_software",
            "label": "System builder", "tier": "T2",
            "confidence": 0.99, "validated_runs": 0,
            "recency_score": 1.0, "failure_rate": 0.0,
            "evidence_refs": ["README.md"],
        }],
    }
    return sanitize_legacy_tree(legacy, source_commit="a" * 40)


class AutonomousCapabilityGrowthTests(unittest.TestCase):
    def test_1000_forged_success_events_cannot_increment_runs(self):
        original = tree()
        snap = json.dumps(original, sort_keys=True)
        for i in range(1000):
            with self.assertRaisesRegex(ValueError, "ATTESTATION_REQUIRED"):
                record_skill_observation(
                    original, skill_id="build_software",
                    success=True, observed_at=f"2026-10-10T00:{i:04d}:00Z",
                    repo_root=".",
                )
        self.assertEqual(json.dumps(original, sort_keys=True), snap)
        self.assertEqual(original["skills"][0]["validated_runs"], 0)
        self.assertEqual(evaluate_registry(original).outcome, "ADMITTED")

    def test_attempt_telemetry_does_not_grant_authority(self):
        proposal = propose_skill_observation(
            skill_id="build_software", success=True,
            observed_at="2026-10-10T06:00:00Z", source_commit="a"*40,
        )
        self.assertFalse(proposal["authority_granted"])
        self.assertEqual(proposal["validated_run_increment"], 0)
        self.assertEqual(proposal["verification"], "PENDING_EXTERNAL_ATTESTATION")
        self.assertEqual(proposal, propose_skill_observation(
            skill_id="build_software", success=True,
            observed_at="2026-10-10T06:00:00Z", source_commit="a"*40,
        ))
        with self.assertRaises(ValueError):
            propose_skill_observation(
                skill_id="build_software", success="True",
                observed_at="2026-10-10", source_commit="a"*40,
            )

    def test_reported_counter_above_threshold_is_not_tier_promotion(self):
        engine = EvolutionEngine(lineage=AdaptiveLineage())
        v = engine.evaluate_skill({
            "skill_id": "build_software", "tier": "T2",
            "validated_runs": 100, "failure_rate": 0.0,
            "confidence": 1.0,
        })
        self.assertFalse(v.promoted)
        self.assertTrue(v.requires_guardian)
        self.assertEqual(v.eligible_tier, "T1")

    def test_unobserved_skill_remains_unroutable(self):
        registry = tree()
        outcome = decide_skill_routing(
            capability="build software", skill_id="build_software",
            skill=registry["skills"][0], registry=registry, repo_root=".",
        )
        self.assertEqual(outcome.outcome, "DENIED")
        self.assertEqual(outcome.authority_score, 0.0)
        self.assertIn("UNOBSERVED", outcome.reason_codes)


if __name__ == "__main__":
    unittest.main()
