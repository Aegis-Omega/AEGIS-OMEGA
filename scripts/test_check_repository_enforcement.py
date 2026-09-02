#!/usr/bin/env python3
from __future__ import annotations

import unittest
from unittest.mock import patch

import check_repository_enforcement as enforcement


class RepositoryEnforcementTests(unittest.TestCase):
    def test_unprotected_branch_denies_without_privileged_lookup(self) -> None:
        calls: list[str] = []

        def fake_get(path: str, token: str | None):
            calls.append(path)
            if path == "/repos/Aegis-Omega/AEGIS-OMEGA/branches/main":
                return 200, {"name": "main", "protected": False}
            self.fail(f"unexpected privileged lookup: {path}")

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify("Aegis-Omega/AEGIS-OMEGA", "main", "token")

        self.assertFalse(result.ok)
        self.assertEqual(result.source, "branch_endpoint:protected=false")
        self.assertEqual(calls, ["/repos/Aegis-Omega/AEGIS-OMEGA/branches/main"])
        self.assertEqual(result.as_dict()["production_admission"], "FORBIDDEN")

    def test_protected_branch_requires_detailed_policy_evidence(self) -> None:
        responses = {
            "/repos/Aegis-Omega/AEGIS-OMEGA/branches/main": (200, {"protected": True}),
            "/repos/Aegis-Omega/AEGIS-OMEGA/branches/main/protection": (
                200,
                {
                    "required_pull_request_reviews": {"required_approving_review_count": 1},
                    "required_status_checks": {"contexts": ["Repository Enforcement"]},
                    "enforce_admins": {"enabled": True},
                    "required_signatures": {"enabled": True},
                    "required_conversation_resolution": {"enabled": True},
                    "allow_force_pushes": {"enabled": False},
                    "allow_deletions": {"enabled": False},
                },
            ),
            "/repos/Aegis-Omega/AEGIS-OMEGA/rules/branches/main": (404, {"message": "Not Found"}),
        }

        def fake_get(path: str, token: str | None):
            return responses[path]

        with patch.object(enforcement, "_get", side_effect=fake_get):
            result = enforcement.verify("Aegis-Omega/AEGIS-OMEGA", "main", "token")

        self.assertTrue(result.ok)
        self.assertEqual(result.source, "classic_branch_protection")


if __name__ == "__main__":
    unittest.main()
