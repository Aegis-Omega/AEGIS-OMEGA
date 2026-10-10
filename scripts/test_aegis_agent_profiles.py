#!/usr/bin/env python3
"""Dependency-free structural contract for AEGIS Copilot agent profiles.

Run: python3 scripts/test_aegis_agent_profiles.py
This validates configuration; it does NOT execute hosted AI models or attest CI.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "aegis-operator": {"read", "search", "agent", "github/*"},
    "aegis-ci-investigator": {"read", "search", "github/*"},
    "aegis-implementation": {"read", "search", "edit", "execute"},
    "aegis-verifier": {"read", "search", "execute", "github/*"},
}


class AgentProfilesContract(unittest.TestCase):
    def test_profiles_have_explicit_bounded_tools(self):
        for agent, expected_tools in EXPECTED.items():
            with self.subTest(agent=agent):
                path = ROOT / ".github" / "agents" / (agent + ".agent.md")
                self.assertTrue(path.is_file())
                content = path.read_text(encoding="utf-8")
                self.assertLess(len(content), 30000)
                self.assertTrue(content.startswith("---\n"))
                header, body = content[4:].split("\n---\n", 1)
                fields = dict(line.split(": ", 1) for line in header.splitlines())
                self.assertEqual(fields.get("name"), agent)
                self.assertTrue(fields.get("description"))
                self.assertEqual(set(json.loads(fields["tools"])), expected_tools)
                self.assertNotIn("*", expected_tools)
                self.assertEqual(fields.get("user-invocable"), "true")
                self.assertIn("AEGIS", body)

    def test_single_writer_and_independent_verifier(self):
        folder = ROOT / ".github" / "agents"
        profiles = {p.stem.replace(".agent", ""): p.read_text(encoding="utf-8")
                    for p in folder.glob("*.agent.md")}
        self.assertEqual(set(profiles), set(EXPECTED))
        for role in ("aegis-operator", "aegis-ci-investigator", "aegis-verifier"):
            self.assertNotIn('"edit"', profiles[role].split("\n---\n", 1)[0])
        self.assertIn('"edit"', profiles["aegis-implementation"].split("\n---\n", 1)[0])
        self.assertIn("aegis-verifier", profiles["aegis-operator"])
        self.assertIn("SUBAGENT_DISPATCH_UNAVAILABLE", profiles["aegis-operator"])
        self.assertIn("NOT_ADMITTED", profiles["aegis-verifier"])


if __name__ == "__main__":
    unittest.main()
