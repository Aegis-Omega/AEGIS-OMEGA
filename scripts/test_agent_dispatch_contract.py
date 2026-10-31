#!/usr/bin/env python3
"""Replay the existing agent dispatch shell with a fake curl, no real calls."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / ".github/workflows/agent-dispatch.yml"
MARKER = "      - name: Dispatch to AEGIS constitutional proxy (fail-closed)"

FAKE_CURL = """#!/usr/bin/env python3
import os
import pathlib
import sys
args = sys.argv[1:]
required = ['--proto', '--max-redirs', '--connect-timeout', '--max-time',
            '--output', '--write-out', '--data-binary']
if any(k not in args for k in required):
    sys.exit(21)
if args[args.index('--proto')+1] != '=https':
    sys.exit(22)
if args[args.index('--max-redirs')+1] != '0':
    sys.exit(23)
pathlib.Path(os.environ['MOCK_CALLED']).write_text('called')
pathlib.Path(args[args.index('--output')+1]).write_text(os.environ['MOCK_BODY'])
sys.stdout.write(os.environ['MOCK_STATUS'])
"""


def dispatch_shell() -> str:
    source = YAML.read_text(encoding="utf8")
    if source.count(MARKER) != 1:
        raise AssertionError("dispatch step missing or duplicated")
    section = source.split(MARKER, 1)[1]
    if "        run: |" not in section:
        raise AssertionError("dispatch shell missing")
    tail = section.split("        run: |", 1)[1]
    lines = []
    for line in tail.splitlines()[1:]:
        if line and not line.startswith("          "):
            break
        lines.append(line)
    if not lines:
        raise AssertionError("empty dispatch shell")
    return textwrap.dedent("\n".join(lines))


class DispatchSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = dispatch_shell()

    def invoke(self, url="https://approved.example", status="200", body=None, payload='{"branch":"main"}'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            curl = root / "curl"
            curl.write_text(FAKE_CURL, encoding="utf8")
            curl.chmod(0o755)
            called = root / "called"
            if body is None:
                body = json.dumps({"results": [
                    {"role": "engineering", "is_valid": True, "output": "NEVER_LOG_THIS_OUTPUT"}
                ]})
            env = dict(os.environ,
                PATH=str(root) + os.pathsep + os.environ["PATH"],
                PROXY_URL=url,
                DISPATCH_EVENT_TYPE="github_ci_success",
                DISPATCH_PAYLOAD=payload,
                PLATFORM_KEY="SYNTHETIC_KEY_NEVER_LOG",
                MOCK_CALLED=str(called),
                MOCK_BODY=body,
                MOCK_STATUS=status)
            proc = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", self.shell],
                env=env, capture_output=True, text=True, timeout=15)
            return proc, called.exists()

    def test_compact_classification_and_hold(self):
        source = YAML.read_text(encoding="utf8")
        self.assertEqual(source.count("PAYLOAD=$(jq -cn"), 5)
        self.assertIn("if: vars.PROXY_URL != ''", source)
        self.assertIn("if: github.event_name == 'pull_request'", source)

    def test_success_never_logs_agent_output_or_key(self):
        result, called = self.invoke()
        self.assertTrue(called, result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"agent_result_count":1', result.stdout)
        self.assertNotIn("NEVER_LOG_THIS_OUTPUT", result.stdout+result.stderr)
        self.assertNotIn("SYNTHETIC_KEY_NEVER_LOG", result.stdout+result.stderr)

    def test_rejects_unsafe_proxy_before_curl(self):
        for url in [
            "http://approved.example", "https://user@approved.example",
            "https://approved.example/evil", "https://approved.example?x=1",
            "https://approved.example#fragment", "https://approved.example:444",
        ]:
            with self.subTest(url=url):
                result, called = self.invoke(url=url)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(called)

    def test_denies_non200_without_leaking_upstream_body(self):
        result, called = self.invoke(status="403", body="SENSITIVE_BODY_DO_NOT_LOG")
        self.assertTrue(called)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 403", result.stderr)
        self.assertNotIn("SENSITIVE_BODY_DO_NOT_LOG", result.stdout+result.stderr)

    def test_denies_invalid_or_unverified_results(self):
        for body in [
            "invalid JSON SECRET_DO_NOT_LOG",
            '{"results":[],"secret":"SECRET_DO_NOT_LOG"}',
            '{"results":[{"role":"agent","is_valid":false,"output":"SECRET_DO_NOT_LOG"}]}',
            '{"results":[{"role":5,"is_valid":true,"output":"SECRET_DO_NOT_LOG"}]}',
        ]:
            with self.subTest(sample=body[:20]):
                result, called = self.invoke(body=body)
                self.assertTrue(called)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("SECRET_DO_NOT_LOG", result.stdout+result.stderr)

    def test_bad_payload_does_not_call_curl(self):
        result, called = self.invoke(payload="not json")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()
