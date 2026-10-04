#!/usr/bin/env python3
"""Regression matrix for Git preview deployment eligibility.

Separates the target OR policy from provider enforcement:
- target: deploy iff the deploy surface changed OR the branch is explicitly allowed;
- Vercel: repo-owned pre-allocation branch gate plus secondary ignored-build path guard;
- Cloudflare: provider-owned Build watch paths remain an external settings delta.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERCEL = {
    "hub": {
        "paths": ("hub/", "packages/shared/"),
        "branch_prefixes": ("preview/hub/", "deploy/hub/", "preview/all/", "deploy/all/"),
    },
    "platform-picker": {
        "paths": ("platform-picker/", "packages/shared/"),
        "branch_prefixes": (
            "preview/platform-picker/",
            "deploy/platform-picker/",
            "preview/all/",
            "deploy/all/",
        ),
    },
    "hook-generator": {
        "paths": ("hook-generator/", "packages/shared/"),
        "branch_prefixes": (
            "preview/hook-generator/",
            "deploy/hook-generator/",
            "preview/all/",
            "deploy/all/",
        ),
    },
}

CLOUDFLARE = {
    "aegisomega": {
        "paths": ("worker-src/", "aegisomega-webgpu/"),
        "exact_paths": ("wrangler.jsonc",),
        "branch_prefixes": (
            "preview/cloudflare/",
            "deploy/cloudflare/",
            "preview/all/",
            "deploy/all/",
        ),
    }
}


def branch_allowed(branch: str, prefixes: tuple[str, ...]) -> bool:
    return branch == "main" or any(branch.startswith(prefix) for prefix in prefixes)


def path_touches(
    changed_paths: tuple[str, ...] | list[str],
    prefixes: tuple[str, ...],
    exact_paths: tuple[str, ...] = (),
) -> bool:
    return any(
        path in exact_paths or any(path.startswith(prefix) for prefix in prefixes)
        for path in changed_paths
    )


def target_eligible(provider: str, surface: str, branch: str, changed_paths: list[str]) -> bool:
    policy = (VERCEL if provider == "vercel" else CLOUDFLARE)[surface]
    return branch_allowed(branch, policy["branch_prefixes"]) or path_touches(
        changed_paths,
        policy["paths"],
        policy.get("exact_paths", ()),
    )


TARGET_MATRIX = (
    ("vercel", "hub", "fix/repo-network-preflight-v1", ["scripts/repo_network_preflight.py"], False),
    ("vercel", "platform-picker", "fix/mcp-effect-unknown-v1", ["sovereign-omega-v2/mcp-server/src/server.ts"], False),
    ("vercel", "hook-generator", "fix/scale-os-signed-event-guard-v1", ["migrations/20261004.sql"], False),
    ("vercel", "hub", "feature/homepage-copy", ["hub/src/App.tsx"], True),
    ("vercel", "platform-picker", "feature/picker-ui", ["platform-picker/src/App.tsx"], True),
    ("vercel", "hook-generator", "feature/hook-ui", ["hook-generator/src/App.tsx"], True),
    ("vercel", "hub", "fix/shared-access", ["packages/shared/lib/access.ts"], True),
    ("vercel", "platform-picker", "fix/shared-access", ["packages/shared/lib/access.ts"], True),
    ("vercel", "hook-generator", "fix/shared-access", ["packages/shared/lib/access.ts"], True),
    ("vercel", "hub", "preview/hub/manual-qa", ["docs/note.md"], True),
    ("vercel", "platform-picker", "preview/all/release-candidate", ["docs/note.md"], True),
    ("vercel", "hook-generator", "deploy/all/release-candidate", ["docs/note.md"], True),
    ("vercel", "hub", "main", ["docs/note.md"], True),
    ("cloudflare", "aegisomega", "feature/edge-api", ["worker-src/index.ts"], True),
    ("cloudflare", "aegisomega", "feature/webgpu", ["aegisomega-webgpu/src/main.ts"], True),
    ("cloudflare", "aegisomega", "fix/wrangler", ["wrangler.jsonc"], True),
    ("cloudflare", "aegisomega", "preview/cloudflare/manual-qa", ["docs/note.md"], True),
    ("cloudflare", "aegisomega", "fix/repo-network-preflight-v1", ["scripts/repo_network_preflight.py"], False),
)


class DeployEligibilityMatrixTests(unittest.TestCase):
    def test_target_or_policy_matrix(self) -> None:
        for provider, surface, branch, paths, expected in TARGET_MATRIX:
            with self.subTest(provider=provider, surface=surface, branch=branch, paths=paths):
                self.assertEqual(target_eligible(provider, surface, branch, paths), expected)

    def test_vercel_pretrigger_is_deny_by_default(self) -> None:
        for surface, policy in VERCEL.items():
            config = json.loads((ROOT / surface / "vercel.json").read_text())
            rules = config["git"]["deploymentEnabled"]
            self.assertIs(rules["**"], False)
            self.assertIs(rules["main"], True)
            for prefix in policy["branch_prefixes"]:
                self.assertIs(rules[prefix + "**"], True)

    def test_vercel_pretrigger_rejects_infra_branch(self) -> None:
        branch = "fix/repo-network-preflight-v1"
        for policy in VERCEL.values():
            self.assertFalse(branch_allowed(branch, policy["branch_prefixes"]))

    def test_vercel_ignored_build_step_is_secondary_fail_closed_guard(self) -> None:
        for surface in VERCEL:
            command = json.loads((ROOT / surface / "vercel.json").read_text())["ignoreCommand"]
            self.assertIn("VERCEL_GIT_PREVIOUS_SHA", command)
            self.assertIn("VERCEL_GIT_COMMIT_SHA", command)
            self.assertIn(f":/{surface}", command)
            self.assertIn(":/packages/shared", command)
            self.assertNotIn(":/packages ", command)
            self.assertIn("exit 0", command)
            self.assertIn("exit 1", command)

    def test_probe_file_is_not_a_deploy_surface(self) -> None:
        probe = ["scripts/test_deploy_eligibility_gate.py"]
        for policy in VERCEL.values():
            self.assertFalse(path_touches(probe, policy["paths"]))
        policy = CLOUDFLARE["aegisomega"]
        self.assertFalse(path_touches(probe, policy["paths"], policy["exact_paths"]))

    def test_cloudflare_provider_watch_paths_are_not_faked_in_wrangler(self) -> None:
        wrangler = (ROOT / "wrangler.jsonc").read_text()
        for forbidden in ("path_includes", "path_excludes", "branch_includes", "branch_excludes"):
            self.assertNotIn(forbidden, wrangler)


if __name__ == "__main__":
    unittest.main(verbosity=2)
