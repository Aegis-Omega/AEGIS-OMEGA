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

    def test_no_unbounded_ask_first_loops(self):
        root = read("CLAUDE.md")
        flow = read("WORKFLOW.md")
        self.assertNotIn("If uncertain, ask.", root)
        self.assertNotIn("If something is unclear, stop. Name what's confusing. Ask.", root)
        self.assertIn("Ask only when unresolved ambiguity would change a consequential action", root)
        self.assertIn("Do not repeat questions answered by existing evidence.", flow)

    def test_frozen_guard_negative_and_positive_inputs(self):
        import importlib.util

        path = ROOT / "sovereign-omega-v2/.claude/hooks/frozen-write-guard.py"
        spec = importlib.util.spec_from_file_location("aegis_frozen_guard", path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        cases = (
            ("Write", "python/gate.py", "deny"),
            ("Edit", "python/dna.py", "deny"),
            ("Write", "sovereign-omega-v2/python/router.py", "deny"),
            ("Edit", "docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md", "deny"),
            ("Write", "ARTIFACT_REGISTRY.md", "deny"),
            ("Edit", "python/../python/gate.py", "deny"),
            ("Edit", str((ROOT / "sovereign-omega-v2/python/gate.py").resolve()), "deny"),
            ("Write", "../.claude.json", "deny"),
            ("Edit", "../skill-hashes.sha256", "deny"),
            ("Write", "src/event/allowed.ts", "allow"),
            ("Edit", "test/good.test.ts", "allow"),
        )
        for tool, file_path, decision in cases:
            with self.subTest(tool=tool, path=file_path):
                payload = {"tool_name": tool, "tool_input": {"file_path": file_path}}
                actual = module.evaluate(payload)["hookSpecificOutput"]["permissionDecision"]
                self.assertEqual(decision, actual)

        for payload in (None, {}, {"tool_name": "Edit", "tool_input": {}},
                        {"tool_name": "Write", "tool_input": {"file_path": 123}},
                        {"tool_name": "Bash", "tool_input": {"file_path": "python/gate.py"}}):
            with self.subTest(malformed=repr(payload)):
                self.assertEqual(
                    "deny", module.evaluate(payload)["hookSpecificOutput"]["permissionDecision"]
                )

    def test_both_hook_layers_enforce_write_and_edit(self):
        import json

        root = json.loads(read(".claude/settings.json"))
        nested = json.loads(read("sovereign-omega-v2/.claude/settings.json"))
        root_guards = root["hooks"]["PreToolUse"]
        nested_guards = nested["hooks"]["PreToolUse"]
        self.assertTrue(any("Write|Edit" in x["matcher"]
                            and "pre-write-tier.sh" in str(x["hooks"]) for x in root_guards))
        self.assertTrue(any(x["matcher"] == "Write|Edit"
                            and "frozen-write-guard.py" in str(x["hooks"]) for x in nested_guards))
        shell = read(".claude/hooks/pre-write-tier.sh")
        self.assertIn("FROZEN_GUARD", shell)
        self.assertIn("AEGIS frozen guard crashed; fail closed", shell)
        self.assertIn("permissionDecision", shell)
        legacy = read("sovereign-omega-v2/.claude/hooks/block-frozen-writes.sh")
        self.assertIn("frozen-write-guard.py", legacy)
        self.assertNotIn("CLAUDE_TOOL_INPUT_PATH", legacy)

    def test_preflight_hooks_have_no_implicit_mutations(self):
        import re

        session = read(".claude/hooks/session-start.sh")
        ground = read("scripts/ground-truth.sh")
        intake = read(".claude/hooks/user-prompt-intake.sh")
        for path, source in (("session", session), ("ground", ground), ("intake", intake)):
            with self.subTest(hook=path):
                self.assertIsNone(
                    re.search(r"(?m)^\\s*(?:npm\\s+install|pip3?\\s+install|"
                              r"git\\s+fetch|curl\\b|npx\\b|node\\s+[^\\n]*\\s+observe\\b)",
                              source),
                    "Unexpected default network/install/write command",
                )
        self.assertNotIn('node "$CHAIN_MJS" observe', intake)
        self.assertIn('node "$CHAIN_MJS" certify', intake)
        self.assertIn("No prompt-triggered observation was appended", intake)
        self.assertIn("NOT_CHECKED", ground)
        self.assertIn("UNKNOWN", intake)

if __name__ == "__main__":
    unittest.main()
