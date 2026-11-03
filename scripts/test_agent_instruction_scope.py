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

    def test_commit_gate_rejects_nonzero_tools_and_bad_hook_payloads(self):
        import json
        import os
        import subprocess
        import tempfile

        gate = ROOT / ".claude/hooks/pre-commit-gate.sh"
        settings = json.loads(read(".claude/settings.json"))
        hooks = settings["hooks"]["PreToolUse"]
        self.assertTrue(any(
            item["matcher"] == "Bash"
            and any("pre-commit-gate.sh" in hook["command"] for hook in item["hooks"])
            for item in hooks
        ), "Pre-commit gate exists but is not registered on actual Bash calls")

        def run_case(command, failed_stage=None, platform=True, malformed=False):
            with tempfile.TemporaryDirectory() as d:
                temp = Path(d)
                project = temp / "sovereign-omega-v2"
                project.mkdir()
                if platform:
                    test = project / "python/tests/test_platform.py"
                    test.parent.mkdir(parents=True)
                    test.write_text("print('PASS: 1  FAIL: 0')\n")
                bindir = temp / "bin"
                bindir.mkdir()
                npm = bindir / "npm"
                npm.write_text(
                    "#!/bin/sh\n"
                    + (f'if [ "$2" = "{failed_stage}" ]; then exit 17; fi\n'
                       if failed_stage else "")
                    + "exit 0\n"
                )
                npm.chmod(0o755)
                env = dict(os.environ,
                           CLAUDE_PROJECT_DIR=str(temp),
                           PATH=str(bindir) + os.pathsep + os.environ["PATH"])
                event = "{}" if malformed else json.dumps({
                    "tool_name": "Bash", "tool_input": {"command": command}
                })
                return subprocess.run(
                    ["bash", str(gate)], input=event, text=True,
                    capture_output=True, env=env, timeout=15
                )

        self.assertEqual(run_case("git status", failed_stage="test").returncode, 0)
        self.assertNotEqual(run_case("git commit -m x", malformed=True).returncode, 0)
        for invocation in ("git commit -m x", "git -C repo commit -m x"):
            for stage in ("test", "typecheck", "build"):
                with self.subTest(invocation=invocation, stage=stage):
                    result = run_case(invocation, failed_stage=stage)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(run_case("git commit -m x", platform=False).returncode, 2)
        good = run_case("git commit -m x")
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        self.assertIn("Gate 8 passed", good.stdout)

    def test_preflight_hooks_have_no_implicit_mutations(self):
        import re

        session = read(".claude/hooks/session-start.sh")
        ground = read("scripts/ground-truth.sh")
        intake = read(".claude/hooks/user-prompt-intake.sh")
        danger = re.compile(
            r"(?m)^[ \t]*(?:npm[ \t]+install|pip3?[ \t]+install|"
            r"git[ \t]+fetch|curl\b|npx\b|node[ \t]+[^\n]*[ \t]+observe\b)"
        )
        # Negative controls prove that the guard itself is not an inert string test.
        for sample in ("npm install dep", "pip install pkg", "git fetch origin main",
                       "curl https://example.com", "npx unsafe-cli",
                       'node "$CHAIN_MJS" observe SENSATION T1 prompt'):
            with self.subTest(hazard=sample):
                self.assertIsNotNone(danger.search(sample))
        for path, source in (("session", session), ("ground", ground), ("intake", intake)):
            with self.subTest(hook=path):
                self.assertIsNone(
                    danger.search(source),
                    "Unexpected default network/install/write command",
                )
        self.assertNotIn('node "$CHAIN_MJS" observe', intake)
        self.assertIn('node "$CHAIN_MJS" certify', intake)
        self.assertIn("No prompt-triggered observation was appended", intake)
        self.assertIn("NOT_CHECKED", ground)
        self.assertIn("UNKNOWN", intake)

    def test_consequential_operations_not_auto_approved(self):
        import json
        import re

        root_settings = json.loads(read(".claude/settings.json"))
        nested_settings = json.loads(read("sovereign-omega-v2/.claude/settings.json"))
        root_allow = set(root_settings["permissions"]["allow"])
        nested_allow = set(nested_settings["permissions"]["allow"])
        shell_auto = re.compile(
            r"^Bash\((?:npm install|npx |pip |pip3 |curl \*|gcloud |supabase |"
            r"git (?:push|merge|rebase|reset|cherry-pick|remote set-url|pull|stash|tag))"
        )
        privileged_connectors = re.compile(
            r"__(?:apply_migration|execute_sql|confirm_cost|create_project|"
            r"delete_branch|deploy_edge_function|merge_branch|pause_project|"
            r"restore_project|rebase_branch|reset_branch|create_repository|"
            r"delete_file|merge_pull_request|enable_pr_auto_merge|"
            r"disable_pr_auto_merge|update_pull_request_branch|deploy_to_vercel|"
            r"d1_database_create|d1_database_delete|d1_database_query|"
            r"hyperdrive_config_delete|r2_bucket_create|r2_bucket_delete)$"
        )
        for permission in root_allow:
            with self.subTest(level="root", permission=permission):
                self.assertIsNone(shell_auto.search(permission))
                self.assertIsNone(privileged_connectors.search(permission))
        for forbidden in (
            "Bash(npm:*)", "Bash(npx:*)", "Bash(git:*)",
            "Bash(pip:*)", "Bash(pip3:*)", "Bash(curl:*)",
            "mcp__71923ddf-e9ee-4959-b191-9ef0ac574e2a__apply_migration",
            "mcp__71923ddf-e9ee-4959-b191-9ef0ac574e2a__execute_sql",
        ):
            with self.subTest(level="nested", permission=forbidden):
                self.assertNotIn(forbidden, nested_allow)
        for safe in ("Bash(npm run test*)", "Bash(npm run typecheck*)",
                     "Bash(npm run build*)", "Bash(git status*)"):
            self.assertIn(safe, nested_allow)

    def test_hash_verifier_never_falsely_green(self):
        import importlib.util
        import json

        path = ROOT / "sovereign-omega-v2/.claude/hooks/session-hash-check.py"
        spec = importlib.util.spec_from_file_location("aegis_session_hash_guard", path)
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        receipt = "".join("  OK:   " + item + "\n" for item in module.REQUIRED)
        receipt += module.PASS_MARKER
        cases = (
            (0, receipt, "VERIFIED"),
            (1, "  FAIL: python/dna.py", "FAILED"),
            (2, "  WARN: python/dna.py", "INCOMPLETE"),
            (0, "  OK:   python/gate.py", "UNKNOWN"),
            (0, receipt.replace("router.py", "router.pyx"), "UNKNOWN"),
            (0, receipt + "\n  FAIL: python/dna.py", "UNKNOWN"),
            (3, receipt, "UNKNOWN"),
        )
        for rc, out, expected in cases:
            with self.subTest(rc=rc,expected=expected):
                self.assertEqual(module.classify(rc, out, "")["status"], expected)
        nested = json.loads(read("sovereign-omega-v2/.claude/settings.json"))
        hook = nested["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        self.assertIn("session-hash-check.py", hook)
        self.assertNotIn("grep -q", hook)

    def test_tier_checker_write_edit_json(self):
        import json
        import shutil
        import subprocess
        import tempfile

        source = ROOT / "sovereign-omega-v2/.claude/hooks/tier-check.sh"
        nested = json.loads(read("sovereign-omega-v2/.claude/settings.json"))
        configured = nested["hooks"]["PostToolUse"]
        self.assertTrue(any(
            x["matcher"] == "Write|Edit" and "tier-check.sh" in str(x["hooks"])
            for x in configured
        ))
        self.assertIn("ROOT", source.read_text(encoding="utf-8"))
        self.assertNotIn('FILEPATH="$1"', source.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "sovereign-omega-v2"
            hook = project / ".claude/hooks/tier-check.sh"
            hook.parent.mkdir(parents=True)
            shutil.copyfile(source, hook)
            source_file = project / "src/example.ts"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("// consciousness is a tier marker\\n", encoding="utf-8")
            target = project / "test/clean.test.ts"
            target.parent.mkdir()
            target.write_text("// clean\\n", encoding="utf-8")
            cases = (
                ("Write", "src/example.ts", "tier warning"),
                ("Edit", str(source_file), "tier warning"),
                ("Edit", "sovereign-omega-v2/src/example.ts", "tier warning"),
                ("Edit", "test/clean.test.ts", ""),
                ("Write", "../outside.ts", "UNKNOWN"),
                ("Edit", "src/missing.ts", "UNKNOWN"),
            )
            for tool, location, required in cases:
                with self.subTest(tool=tool, path=location):
                    event = json.dumps({"tool_name": tool, "tool_input": {"file_path": location}})
                    done = subprocess.run(["bash", str(hook)], input=event, text=True,
                                          capture_output=True, timeout=5)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertIn(required, done.stdout)
            invalid = subprocess.run(["bash", str(hook)], input="{}",
                                     text=True, capture_output=True, timeout=5)
            self.assertIn("UNKNOWN", invalid.stdout)

if __name__ == "__main__":
    unittest.main()
