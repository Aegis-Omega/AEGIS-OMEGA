#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capability_resolution import law_terms, resolve  # noqa: E402
REGISTRY = ROOT / "security" / "agent-capability-lineage.json"


class AgentCapabilityLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_resolution_law_requires_all_authority_planes(self) -> None:
        law = self.registry["resolution_law"]
        for required in (
            "configured_allowlist",
            "callable_connector_surface",
            "authenticating_principal_permission",
            "principal_is_agent_own_principal",
            "authority_guard_allows",
            "repository_policy_allows",
        ):
            self.assertIn(required, law)

    def test_law_terms_and_prose_do_not_drift(self) -> None:
        # The prose is what a human reads; the term list is what the evaluator
        # runs. A term present in one and absent from the other is the defect.
        law = self.registry["resolution_law"]
        terms = law_terms(self.registry)
        self.assertEqual(len(terms), len(set(terms)))
        for term in terms:
            self.assertIn(term, law)

    def test_pr150_is_recorded_as_tool_allowlist_not_repository_admin(self) -> None:
        grant = next(item for item in self.registry["lineage"] if item["pull_request"] == 150)
        self.assertEqual(grant["commit"], "c55943bcba568f3864907583131b41fe97e9c196")
        self.assertEqual(grant["kind"], "project_runtime_allowlist")
        self.assertIn("mcp__github__create_or_update_file", grant["selected_github_tools_added"])
        self.assertIn("mcp__github__merge_pull_request", grant["selected_github_tools_added"])
        self.assertIn("repository_ruleset_administration", grant["does_not_establish"])
        self.assertIn("direct_main_authority", grant["does_not_establish"])

    def test_pr390_narrows_write_authority_and_does_not_grant_admin(self) -> None:
        guard = next(item for item in self.registry["lineage"] if item["pull_request"] == 390)
        self.assertEqual(guard["kind"], "authority_narrowing_guard")
        self.assertEqual(guard["guard"], "scripts/claude-authority-guard.py")
        self.assertEqual(guard["does_not_grant"], "repository_administration")
        self.assertIn("mcp__github__push_files", guard["protected_tools"])

    def test_admin_app_installation_is_not_treated_as_runtime_callability(self) -> None:
        principals = {
            item["name"]: item
            for item in self.registry["installed_github_principals_observed_2026_09_02"]
        }
        self.assertFalse(principals["ChatGPT Codex Connector"]["repository_ruleset_admin"])
        self.assertFalse(principals["Claude"]["repository_ruleset_admin"])
        vercel = principals["Vercel"]
        self.assertTrue(vercel["repository_ruleset_admin"])
        self.assertEqual(vercel["permissions"]["administration"], "write")
        self.assertEqual(vercel["runtime_callability"], "MUST_BE_PROVEN_PER_EXECUTION_SURFACE")

    # --- the borrowed-principal hole -------------------------------------
    #
    # The registry already refuses to treat an installed admin app as callable.
    # That is an evidential claim. These tests cover the separate, normative
    # one: even a principal proven callable is not this agent's grant.

    def test_borrowed_admin_principal_is_denied_even_when_every_other_term_holds(self) -> None:
        # The exact escalation: a ruleset write reached through the Vercel
        # installation, with everything else satisfied.
        borrowed = {
            "configured_allowlist": True,
            "callable_connector_surface": True,
            "authenticating_principal_permission": True,   # Vercel holds administration: write
            "principal_is_agent_own_principal": False,     # ...but it is not ours
            "authority_guard_allows": True,
            "repository_policy_allows": True,
        }
        permitted, unmet = resolve(borrowed, self.registry)
        self.assertFalse(permitted)
        self.assertEqual(unmet, ["principal_is_agent_own_principal"])

    def test_own_principal_without_the_permission_is_still_denied(self) -> None:
        # The mirror case, so the new term cannot be mistaken for a bypass.
        ours_but_unpermitted = {
            "configured_allowlist": True,
            "callable_connector_surface": True,
            "authenticating_principal_permission": False,  # Claude app: administration none
            "principal_is_agent_own_principal": True,
            "authority_guard_allows": True,
            "repository_policy_allows": True,
        }
        permitted, unmet = resolve(ours_but_unpermitted, self.registry)
        self.assertFalse(permitted)
        self.assertEqual(unmet, ["authenticating_principal_permission"])

    def test_silence_is_not_permission(self) -> None:
        # An incompletely described scenario must never resolve to permitted.
        permitted, unmet = resolve({}, self.registry)
        self.assertFalse(permitted)
        self.assertEqual(unmet, law_terms(self.registry))

    def test_all_terms_satisfied_resolves_to_permitted(self) -> None:
        # Positive control: without this, the three tests above would also pass
        # against a function that denies everything.
        everything = {term: True for term in law_terms(self.registry)}
        permitted, unmet = resolve(everything, self.registry)
        self.assertTrue(permitted)
        self.assertEqual(unmet, [])

    def test_vercel_borrow_is_registered_as_denied_by_policy(self) -> None:
        paths = {item["id"]: item for item in self.registry["denied_escalation_paths"]}
        borrow = paths["vercel-administration-borrow"]
        self.assertEqual(borrow["status"], "DENIED_BY_POLICY")
        self.assertIn("runtime_callability", borrow["denied_even_if"])
        # The path must name a term the law actually has, or the denial is decorative.
        self.assertIn(borrow["fails_term"], law_terms(self.registry))

    def test_agent_own_principal_is_not_an_administration_holder(self) -> None:
        own = self.registry["agent_own_principal"]
        principals = {
            item["name"]: item
            for item in self.registry["installed_github_principals_observed_2026_09_02"]
        }
        self.assertIn(own["name"], principals)
        self.assertEqual(principals[own["name"]]["app_id"], own["app_id"])
        self.assertFalse(principals[own["name"]]["repository_ruleset_admin"])

    def test_registry_forbids_content_write_admin_conflation(self) -> None:
        invariants = set(self.registry["invariants"])
        self.assertIn("CONTENT_WRITE_DOES_NOT_IMPLY_REPOSITORY_ADMINISTRATION", invariants)
        self.assertIn("INSTALLED_ADMIN_APP_DOES_NOT_IMPLY_ITS_ADMIN_PRINCIPAL_IS_CALLABLE", invariants)
        self.assertIn("CALLABLE_PRINCIPAL_IS_NOT_AUTHORISED_PRINCIPAL", invariants)
        self.assertIn("BORROWED_PRINCIPAL_IS_NOT_GRANTED_CAPABILITY", invariants)
        procedure = "\n".join(self.registry["required_agent_procedure"])
        self.assertIn("Administration authority", procedure)
        self.assertIn("content:write is insufficient", procedure)


if __name__ == "__main__":
    unittest.main()
