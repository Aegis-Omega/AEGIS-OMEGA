"""Run one AEGIS Worker session on one GitHub issue (Claude Managed Agents).

Setup once (IDs land in claude-lock.json):
    ant apply agents/aegis-worker/agent.md agents/aegis-reviewer/agent.md \
        agents/aegis-worker/environment.yaml agents/aegis-worker/vault.yaml
then add the GitHub MCP credential to the vault (see agents/aegis-worker/README.md).

Run:
    python agents/aegis-worker/run.py 749                # deliver issue #749 as a PR
    python agents/aegis-worker/run.py 749 --probe        # only check GitHub access, no work
Env: ANTHROPIC_API_KEY (or an `ant auth login` profile), GITHUB_TOKEN
     (fine-grained PAT, Contents + Pull requests + Issues read/write on the repo).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = "Aegis-Omega/AEGIS-OMEGA"
ROOT = Path(__file__).resolve().parents[2]
LOCK_KEYS = {
    "agent": "./agents/aegis-worker/agent.md",
    "environment": "./agents/aegis-worker/environment.yaml",
    "vault": "./agents/aegis-worker/vault.yaml",
}

# GitHub MCP calls pause for a decision (mcp_toolset defaults to always_ask). Unattended runs
# allow reads and the two writes a delivery needs; everything else (merge, delete, settings) is denied.
ALLOWED_GITHUB_PREFIXES = ("get_", "list_", "search_")
ALLOWED_GITHUB_TOOLS = {"issue_read", "pull_request_read", "create_pull_request", "add_issue_comment"}


def approve(event) -> bool:
    if event.type != "agent.mcp_tool_use":
        return False  # a built-in call the server could not judge: deny when nobody is watching
    name = getattr(event, "name", "") or ""
    return name in ALLOWED_GITHUB_TOOLS or name.startswith(ALLOWED_GITHUB_PREFIXES)


def done_when(issue_body: str) -> str:
    m = re.search(r"\*{0,2}Done when:?\*{0,2}:?\s*(.+)", issue_body or "", re.IGNORECASE)
    return m.group(1).strip() if m else ""


def build_rubric(number: int, issue_body: str) -> str:
    criterion = done_when(issue_body)
    first = (f'- The change satisfies the issue\'s "Done when": {criterion}' if criterion else
             "- The change satisfies every acceptance criterion stated in the issue body")
    return "\n".join([
        f"# Rubric for issue #{number} (starter - tune per issue)",
        first,
        "- Each acceptance criterion is covered by a test or a check whose real output is reported",
        "- The relevant gate passes in the sandbox (npm test+typecheck+build, cargo test, or pytest)",
        "- No change to sovereign-omega-v2/python/gate.py, dna.py or router.py; no secrets or .env files",
        "- The diff stays within the issue's scope: no unrelated refactors or reformatting",
        f"- One pull request against main from an agent/issue-{number}-* branch, body contains 'Closes #{number}'",
        "- Every commit message ends with an 'Agent: <model>' line",
        "- The AEGIS Reviewer agent reviewed the final diff and its findings are addressed",
        "- The PR body lists what was run with results; anything not run is marked NOT_RUN",
    ])


def fetch_issue(number: int, token: str) -> dict:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/issues/{number}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def resource_ids() -> dict[str, str]:
    env = {k: os.environ.get(f"AEGIS_WORKER_{k.upper()}_ID", "") for k in LOCK_KEYS}
    lock = ROOT / "claude-lock.json"
    if lock.exists():
        resources = json.loads(lock.read_text()).get("resources", {})
        for k, path in LOCK_KEYS.items():
            env[k] = env[k] or resources.get(path, {}).get("id", "")
    missing = [k for k, v in env.items() if not v]
    if missing:
        sys.exit(f"missing IDs for {missing}: run `ant apply` first or set AEGIS_WORKER_<KIND>_ID")
    return env


def run(number: int, budget_usd: float, probe: bool) -> int:
    import anthropic

    token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
    ids = resource_ids()
    issue = fetch_issue(number, token)
    client = anthropic.Anthropic()
    session = client.beta.sessions.create(
        agent=ids["agent"],
        environment_id=ids["environment"],
        vault_ids=[ids["vault"]],
        title=f"Issue #{number}: {issue['title']}"[:200],
        budget={"type": "limit", "max_list_cost": {"amount": str(round(budget_usd * 100)), "currency": "USD"}},
        resources=[{
            "type": "github_repository",
            "url": f"https://github.com/{REPO}",
            "authorization_token": token,
            "checkout": {"type": "branch", "name": "main"},
        }],
    )
    print(f"session {session.id}\nwatch: https://platform.claude.com/workspaces/default/sessions/{session.id}")

    if probe:
        events = [{"type": "user.message", "content": [{"type": "text", "text":
                   f"Confirm you can read issue #{number} with the GitHub tools and that "
                   "/workspace/AEGIS-OMEGA is a git checkout. Report both; do not start the task."}]}]
    else:
        events = [
            {"type": "user.message", "content": [{"type": "text", "text":
             f"Issue #{number}: {issue['title']}\n\n{issue.get('body') or ''}"}]},
            {"type": "user.define_outcome",
             "description": f"Deliver GitHub issue #{number} in {REPO} as one reviewed pull request.",
             "rubric": {"type": "text", "content": build_rubric(number, issue.get("body") or "")},
             "max_iterations": 5},
        ]

    result = "unknown"
    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        client.beta.sessions.events.send(session_id=session.id, events=events)
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, flush=True)
            elif event.type in ("agent.tool_use", "agent.mcp_tool_use") and event.evaluated_permission == "ask":
                ok = approve(event)
                print(f"[{'allow' if ok else 'deny'}] {getattr(event, 'name', event.type)}", flush=True)
                client.beta.sessions.events.send(session_id=session.id, events=[{
                    "type": "user.tool_confirmation", "tool_use_id": event.id,
                    "result": "allow" if ok else "deny"}])
            elif event.type == "span.outcome_evaluation_end":
                result = event.result
                print(f"[grader iteration {event.iteration}] {event.result}: {event.explanation}", flush=True)
            elif event.type == "session.status_idle":
                if event.stop_reason.type != "requires_action":
                    print(f"[idle] {event.stop_reason.type}")
                    break
            elif event.type == "session.status_terminated":
                print("[terminated]")
                break
    if probe:
        return 0
    print(f"outcome: {result}")
    return 0 if result == "satisfied" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("issue", type=int)
    ap.add_argument("--budget-usd", type=float, default=10.0, help="hard session spend cap (default 10)")
    ap.add_argument("--probe", action="store_true", help="only check GitHub access, do no work")
    a = ap.parse_args()
    return run(a.issue, a.budget_usd, a.probe)


if __name__ == "__main__":
    sys.exit(main())
