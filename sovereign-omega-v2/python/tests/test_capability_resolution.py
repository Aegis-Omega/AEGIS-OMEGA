#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from capability_resolution import law_terms, resolve  # noqa: E402

REGISTRY = ROOT / "security" / "capability-resolution-policy.v1.json"
EXPECTED_TERMS = (
    "configured_allowlist",
    "callable_execution_surface",
    "authenticating_principal_permission",
    "principal_is_workload_bound",
    "authority_guard_allows",
    "repository_policy_allows",
)


class ProviderNeutralCapabilityResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_resolution_law_is_exact_and_provider_neutral(self) -> None:
        self.assertEqual(tuple(law_terms(self.registry)), EXPECTED_TERMS)
        self.assertEqual(
            self.registry["resolution_law"],
            "effective_capability = " + " AND ".join(EXPECTED_TERMS),
        )
        serialized = json.dumps(self.registry, sort_keys=True).lower()
        for forbidden in ("claude", "vercel", "anthropic", "openai", "gemini", "qwen"):
            self.assertNotIn(forbidden, serialized)

    def test_borrowed_privileged_principal_fails_only_workload_binding(self) -> None:
        scenario = {term: True for term in EXPECTED_TERMS}
        scenario["principal_is_workload_bound"] = False
        permitted, unmet = resolve(scenario, self.registry)
        self.assertFalse(permitted)
        self.assertEqual(unmet, ["principal_is_workload_bound"])

    def test_own_workload_without_required_permission_is_denied(self) -> None:
        scenario = {term: True for term in EXPECTED_TERMS}
        scenario["authenticating_principal_permission"] = False
        permitted, unmet = resolve(scenario, self.registry)
        self.assertFalse(permitted)
        self.assertEqual(unmet, ["authenticating_principal_permission"])

    def test_silence_is_not_permission(self) -> None:
        permitted, unmet = resolve({}, self.registry)
        self.assertFalse(permitted)
        self.assertEqual(tuple(unmet), EXPECTED_TERMS)

    def test_positive_control_requires_every_term(self) -> None:
        permitted, unmet = resolve({term: True for term in EXPECTED_TERMS}, self.registry)
        self.assertTrue(permitted)
        self.assertEqual(unmet, [])

    def test_invariants_reject_capability_laundering(self) -> None:
        invariants = set(self.registry["invariants"])
        self.assertIn("INSTALLED_OR_CALLABLE_PRINCIPAL_IS_NOT_A_GRANTED_PRINCIPAL", invariants)
        self.assertIn("BORROWED_PRINCIPAL_PERMISSION_IS_NOT_WORKLOAD_AUTHORITY", invariants)
        self.assertIn("CONTENT_WRITE_DOES_NOT_IMPLY_REPOSITORY_ADMINISTRATION", invariants)
        self.assertIn("MISSING_RESOLUTION_TERM_DENIES", invariants)
        self.assertEqual(self.registry["authority_effect"], "NONE")

    def test_salvaged_lineage_invariants_remain_provider_neutral(self) -> None:
        invariants = set(self.registry["invariants"])
        for invariant in (
            "PR_TITLE_DOES_NOT_DEFINE_CAPABILITY",
            "CONFIGURED_ALLOWLIST_DOES_NOT_IMPLY_EXECUTION_CALLABILITY",
            "EXECUTION_CALLABILITY_DOES_NOT_IMPLY_AUTHENTICATING_PRINCIPAL_PERMISSION",
            "AUTHORITY_GUARDS_CAN_NARROW_AN_OTHERWISE_ALLOWED_TOOL",
            "CAPABILITY_CLAIMS_REQUIRE_EXACT_SOURCE_LINEAGE_AND_LIVE_PRINCIPAL_EVIDENCE",
        ):
            self.assertIn(invariant, invariants)


if __name__ == "__main__":
    unittest.main()
