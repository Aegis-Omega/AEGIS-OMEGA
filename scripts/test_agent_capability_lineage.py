#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
            "authority_guard_allows",
            "repository_policy_allows",
        ):
            self.assertIn(required, law)

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

    def test_registry_forbids_content_write_admin_conflation(self) -> None:
        invariants = set(self.registry["invariants"])
        self.assertIn("CONTENT_WRITE_DOES_NOT_IMPLY_REPOSITORY_ADMINISTRATION", invariants)
        self.assertIn("INSTALLED_ADMIN_APP_DOES_NOT_IMPLY_ITS_ADMIN_PRINCIPAL_IS_CALLABLE", invariants)
        procedure = "\n".join(self.registry["required_agent_procedure"])
        self.assertIn("Administration authority", procedure)
        self.assertIn("content:write is insufficient", procedure)


if __name__ == "__main__":
    unittest.main()
