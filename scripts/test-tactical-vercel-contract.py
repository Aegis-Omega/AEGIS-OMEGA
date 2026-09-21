#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERCEL = ROOT / "tactical" / "vercel.json"
BUILD = ROOT / "tactical" / "scripts" / "vercel-build.mjs"
ENV_EXAMPLE = ROOT / "tactical" / ".env.example"


class TacticalVercelContract(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(VERCEL.read_text(encoding="utf-8"))
        self.build = BUILD.read_text(encoding="utf-8")
        self.env_example = ENV_EXAMPLE.read_text(encoding="utf-8")

    def test_vercel_uses_existing_vite_build(self) -> None:
        self.assertEqual(self.config["framework"], "vite")
        self.assertEqual(self.config["installCommand"], "npm ci")
        self.assertEqual(self.config["buildCommand"], "node scripts/vercel-build.mjs")
        self.assertEqual(self.config["outputDirectory"], "dist")
        self.assertEqual(
            self.config["rewrites"],
            [{"source": "/(.*)", "destination": "/index.html"}],
        )

    def test_build_fails_closed_without_public_bridge(self) -> None:
        for token in (
            "VITE_BRIDGE_URL is required on Vercel",
            "VITE_BRIDGE_URL must be an absolute URL",
            "VITE_BRIDGE_URL must use HTTPS on Vercel",
            "VITE_BRIDGE_URL must not contain credentials",
            "TACTICAL_VERCEL_PREFLIGHT=PASS",
        ):
            self.assertIn(token, self.build)

    def test_deploy_contract_contains_no_api_key(self) -> None:
        combined = VERCEL.read_text(encoding="utf-8") + self.build
        self.assertNotIn("VITE_AEGIS_API_KEY=", combined)
        self.assertNotIn("aegis_your_key_here", combined)
        self.assertNotIn("ANTHROPIC_API_KEY", combined)

    def test_documented_bridge_is_https(self) -> None:
        self.assertIn(
            "VITE_BRIDGE_URL=https://aegis-vertex.aegisomega.com",
            self.env_example,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
