"""Execute the existing AEGIS GitHub dispatch classifier as real Bash.

No network, no secrets, no external effects. A failing case must prevent dispatch.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/agent-dispatch.yml"
HEAD_SHA = "a" * 40


def classifier_script():
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index("      - name: Determine event type and validate actor")
    code_start = lines.index("        run: |", start) + 1
    code_end = next((n for n in range(code_start, len(lines))
                     if lines[n].startswith("      - name: ")), len(lines))
    fragment = lines[code_start:code_end]
    if not fragment or any(line.strip() and not line.startswith("          ") for line in fragment):
        raise ValueError("unexpected Bash YAML indentation")
    return "\n".join(line[10:] if line.startswith("          ") else ""
                     for line in fragment) + "\n"


def run_case(**overrides):
    values = {
        "EVENT_NAME": "pull_request", "ACTOR": "maintainer",
        "ACTOR_TYPE": "MEMBER", "SENDER_LOGIN": "maintainer",
        "CONTENT_AUTHOR_LOGIN": "maintainer",
        "TARGET_REPOSITORY": "Aegis-Omega/AEGIS-OMEGA",
        "PR_TITLE": "Working title", "PR_NUMBER": "732",
        "PR_URL": "https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/732",
        "ISSUE_TITLE": "Sample task", "ISSUE_NUMBER": "734",
        "ISSUE_BODY": "Expected body",
        "COMMENT_BODY": "@aegis-agent fix bounded task",
        "COMMENT_ISSUE_NUMBER": "734",
        "WF_NAME": "⊕ AEGIS-Ω Constitutional Automaton",
        "WF_EVENT": "pull_request",
        "WF_REPOSITORY": "Aegis-Omega/AEGIS-OMEGA",
        "WF_SHA": HEAD_SHA, "WF_RUN_ID": "4195",
        "WF_BRANCH": "candidate-branch", "WF_CONCLUSION": "success",
    }
    values.update(overrides)
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "github-output"
        env = os.environ.copy()
        env.update(values)
        env["GITHUB_OUTPUT"] = str(output)
        completed = subprocess.run(
            ["bash", "-c", classifier_script()],
            cwd=tmp, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        data = {}
        if output.exists():
            for line in output.read_text(encoding="utf-8").splitlines():
                if "=" not in line:
                    raise AssertionError("Malformed multiline GitHub output")
                k, v = line.split("=", 1)
                if k in data:
                    raise AssertionError("Repeated GitHub output field")
                data[k] = v
        return completed, data


class AgentDispatchHolonTests(unittest.TestCase):
    def assert_denied(self, **changes):
        result, values = run_case(**changes)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DENIED", result.stderr)
        self.assertNotIn("github_pr_opened", values.get("event_type", ""))

    def test_01_trusted_pull_request(self):
        r, v = run_case()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v["event_type"], "github_pr_opened")
        self.assertEqual(json.loads(v["payload"])["number"], "732")

    def test_02_untrusted_contributor(self):
        self.assert_denied(ACTOR_TYPE="CONTRIBUTOR")

    def test_03_actor_sender_mismatch(self):
        self.assert_denied(SENDER_LOGIN="forged-actor")

    def test_04_actor_content_author_mismatch(self):
        self.assert_denied(CONTENT_AUTHOR_LOGIN="forged-author")

    def test_05_missing_actor(self):
        self.assert_denied(ACTOR="")

    def test_06_issue_body_multiline_roundtrip(self):
        text = "first line\nsecond line\n$(touch DONT_EXECUTE)"
        r, v = run_case(EVENT_NAME="issues", ISSUE_BODY=text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v["event_type"], "github_issue_opened")
        self.assertEqual(json.loads(v["payload"])["body"], text)
        self.assertEqual(len(v["payload"].splitlines()), 1)

    def test_07_comment_multiline_roundtrip(self):
        text = "hello\n@aegis-agent bounded task\n{ 'ignore': 'none' }"
        r, v = run_case(EVENT_NAME="issue_comment", COMMENT_BODY=text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v["event_type"], "github_pr_comment")
        self.assertEqual(json.loads(v["payload"])["body"], text)
        self.assertEqual(len(v["payload"].splitlines()), 1)

    def test_08_no_comment_invocation(self):
        r, v = run_case(EVENT_NAME="issue_comment", COMMENT_BODY="normal note")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v["event_type"], "")

    def test_09_trusted_collaborator(self):
        r, v = run_case(ACTOR_TYPE="COLLABORATOR")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_10_workflow_success_exact_sha(self):
        r, v = run_case(EVENT_NAME="workflow_run")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v["event_type"], "github_ci_success")
        self.assertEqual(json.loads(v["payload"])["head_sha"], HEAD_SHA)

    def test_11_workflow_failure_exact_sha(self):
        r, v = run_case(EVENT_NAME="workflow_run", WF_CONCLUSION="failure")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(v["event_type"], "github_ci_failure")
        self.assertEqual(json.loads(v["payload"])["head_sha"], HEAD_SHA)

    def test_12_workflow_origin_fork_rejected(self):
        self.assert_denied(EVENT_NAME="workflow_run", WF_REPOSITORY="random/fork")

    def test_13_workflow_name_wrong_rejected(self):
        self.assert_denied(EVENT_NAME="workflow_run", WF_NAME="forged automaton")

    def test_14_workflow_event_wrong_rejected(self):
        self.assert_denied(EVENT_NAME="workflow_run", WF_EVENT="workflow_dispatch")

    def test_15_workflow_sha_malformed_rejected(self):
        self.assert_denied(EVENT_NAME="workflow_run", WF_SHA="invalid")

    def test_16_secret_not_saved_as_step_output(self):
        w = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("steps.platform_key.outputs.key", w)
        self.assertNotIn('echo "key=$PLATFORM_KEY"', w)
        self.assertIn('PLATFORM_KEY="$(gcloud secrets versions access', w)
        self.assertNotIn("output: (.output |", w)
        self.assertIn("if: vars.PROXY_URL != ''", w)


if __name__ == "__main__":
    unittest.main()
