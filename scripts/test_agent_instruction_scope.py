#!/usr/bin/env python3
"""Check AEGIS agent instruction consistency; not a substitute for runtime CI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

CASES = {
    "CLAUDE.md": (
        "MANDATORY CONFIGURATION AND WORKFLOW SELF-AUDIT",
        "AND/OR alternative proof routes",
        "Task continuity and bounded autonomy",
        "Never merge protected",
    ),
    "WORKFLOW.md": (
        "RH RESEARCH OVERRIDE: MULTI-ROUTE FIRST",
        "VERIFY THE AFFECTED DOMAIN",
        "They are NOT Lean or Coq proof verification",
        "never interrupt an independent executable proof path",
    ),
    "sovereign-omega-v2/AGENTS.md": (
        "Failure at any gate = HALT progression",
        "Never bypass the failed",
        "gate, label it PASS, weaken its assertions or deploy",
        "Gate 8: npm run test && npm run typecheck && npm run build",
        "unrelated formally authorized research may proceed",
        "Do not install dependencies or create",
        "Report and halt the **affected implementation or production transition**",
    ),
    "sovereign-omega-v2/CLAUDE.md": (
        "Research / runtime classification (mandatory)",
        "not a live",
        "Never skip, relabel or weaken a gate",
    ),
    "sovereign-omega-v2/.claude/agents/implementer.md": (
        "Effective preflight",
        "investigate and repair the failing gate",
        "Do not proceed to the **next dependent runtime gate**",
        "Never mark a failure PASS",
    ),
    "sovereign-omega-v2/.claude/agents/verifier.md": (
        "smallest source-bound repair candidate",
        "Hand this to the",
        "do not terminate the task with a status alone",
        "do not write implementation code or approve your own repair",
    ),
    "docs/rh/RH_ASSUMPTION_CENSUS_V1.md": (
        "Scope correction (2026-11-03)",
        "Historical, scope-limited evidence only",
        "It is **not** a statement about",
    ),
}

class TestInstructionConsistency(unittest.TestCase):
    def test_all_required_source_rules(self):
        for path, tokens in CASES.items():
            with self.subTest(file=path):
                body = read(path)
                for token in tokens:
                    with self.subTest(token=token):
                        self.assertIn(token, body)

    def test_verifier_no_longer_forbids_causal_fixes(self):
        self.assertNotIn(
            "You do not suggest fixes.",
            read("sovereign-omega-v2/.claude/agents/verifier.md"),
        )

    def test_all_four_rh_agents_keep_alternative_routes(self):
        base = "sovereign-omega-v2/.claude/agents/"
        for name in (
            "rh-dependency-cartographer.md",
            "rh-lean-closer.md",
            "rh-semantic-bridge-closer.md",
            "rh-proof-verifier.md",
        ):
            with self.subTest(agent=name):
                body = read(base + name).lower()
                self.assertTrue(
                    "alternative" in body
                    or "other route" in body
                    or "other proof" in body,
                    msg="No alternative-route instruction: " + name,
                )
        self.assertIn(
            "RiemannHypothesis", read(base + "rh-proof-verifier.md")
        )

    def test_no_automatic_production_or_permission_mutation(self):
        s = read("sovereign-omega-v2/AGENTS.md")
        self.assertIn("Runtime deployment, publishing, gateway changes", s)
        self.assertIn("FORBIDDEN without a fresh explicit operator authorization", s)
        self.assertIn("MANUAL-ONLY: explicit deployment approval", s)
        self.assertIn("Orchestration Setup (opt-in only)", s)
        self.assertIn("Do not install plugins, onboard external agents", s)

if __name__ == "__main__":
    unittest.main()
