# AEGIS Worker (Claude Managed Agents)

One session delivers one GitHub issue as one reviewed pull request. Anthropic hosts the agent
loop and a per-session sandbox; this directory holds only the definitions and a runner.

| File | What it is |
|---|---|
| `agent.md` | Worker agent (`claude-opus-5-5`): sandbox tools, GitHub MCP, roster with the reviewer, dynamic workflows on |
| `../aegis-reviewer/agent.md` | Reviewer agent (`claude-sonnet-5-5`): reads and runs tests, cannot edit |
| `environment.yaml` | Cloud sandbox, `limited` networking (package managers + MCP servers only) |
| `vault.yaml` | Vault container for the GitHub MCP credential (credentials are never in files) |
| `run.py` | Starts a session for an issue, grades it against a rubric built from the issue's "Done when" |

## Setup (once)

Needs `ant` >= 1.40 and Anthropic credentials (`ant auth login`, or `ANTHROPIC_API_KEY`).

```sh
ant apply --dry-run -v agents/aegis-worker/agent.md agents/aegis-reviewer/agent.md \
    agents/aegis-worker/environment.yaml agents/aegis-worker/vault.yaml
ant apply agents/aegis-worker/agent.md agents/aegis-reviewer/agent.md \
    agents/aegis-worker/environment.yaml agents/aegis-worker/vault.yaml
```

Commit the `claude-lock.json` this writes at the repo root. Then store the GitHub token for the
MCP server in the vault (the vault ID is in `claude-lock.json`):

```sh
VAULT_ID=$(jq -r '.resources["./agents/aegis-worker/vault.yaml"].id' claude-lock.json)
ant beta:vaults:credentials create --vault-id "$VAULT_ID" <<YAML
display_name: GitHub MCP
auth: {type: mcp_oauth, mcp_server_url: "https://api.githubcopilot.com/mcp/", access_token: "$GITHUB_TOKEN"}
YAML
```

`GITHUB_TOKEN` is a fine-grained PAT on `Aegis-Omega/AEGIS-OMEGA` with Contents, Pull requests
and Issues set to read and write. It is also used, through Anthropic's git proxy, to clone and
push; it never enters the sandbox.

## Run

```sh
python agents/aegis-worker/run.py 749 --probe   # check access first: a real session, capped at $0.50
python agents/aegis-worker/run.py 749           # deliver issue #749; default spend cap $10
```

Exit 0 means the grader marked the rubric satisfied. GitHub calls pause for a decision and
`run.py` answers them: reads, `create_pull_request` and `add_issue_comment` are allowed; merges,
deletes and everything else are denied. Built-in sandbox calls the server cannot judge are
denied when unattended.

Dynamic workflows are on, so a large issue can fan out to many agents in parallel. Every agent
in a run uses tokens; the session budget (`--budget-usd`) caps the total. To turn workflows off,
set `workflows: {type: disabled}` in `agent.md` and run `ant apply` again.
