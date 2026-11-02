# AGENTS.md

The one page every agent reads first (Codex, Claude Code, any other host). It wins over
older docs; when a doc disagrees with the code, the code wins.

## The operator

- Tarik writes Bosnian (BHS). Answer in BHS, briefly.
- An imperative is a command: do the work yourself, do not hand steps back. A question
  is written as a question.
- No progress reports. Speak up only for a large result, a real blocker, or a decision
  that is his.
- Decide what is needed yourself and aim for the best possible result, without inflating
  claims: evidence kinds are never promoted.

## Where the work is

- **AEGIS-OMEGA** (this repo): product and runtime. Layout and commands in `CLAUDE.md`,
  what is wired or dead in `REPO_MAP.md`.
- **RH lab**: Aegis-Omega/formal-conjectures, PR #92 (draft, never merge), branch
  `fix/rh-live-evidence-provenance-20261024`. Read `research/rh/aegis_math/HANDOFF.md`
  first and update its section 5 when you stop. Never declare RH proved.

## Environment

- Checkouts live at `/home/user/<repo>` (Claude Code cloud) or `/workspace/<repo>`
  (Codex). Never hard-code either.
- Setup script of every environment, one line:

```sh
for d in "${CLAUDE_PROJECT_DIR:-}" "$PWD" /home/user/AEGIS-OMEGA /workspace/AEGIS-OMEGA "$HOME/AEGIS-OMEGA"; do [ -f "$d/scripts/agent-env-setup.sh" ] && exec bash "$d/scripts/agent-env-setup.sh" "$d"; done; echo "agent-env-setup: repository not found, skipping"; exit 0
```

- Claude Code sessions: install the mod with
  `/plugin install aegis-omega --marketplace Aegis-Omega/AEGIS-OMEGA`.

## Changing code

- Never write to `main`, never merge, never force-push, never rewrite history. Work on an
  explicit branch; check its head before every push and verify the blob SHAs after.
- In Claude Code the authority guard (`scripts/claude-authority-guard.py`) blocks pushes
  from the shell; push through the GitHub MCP (`push_files`) to a non-main branch.
- Frozen: `sovereign-omega-v2/python/gate.py`, `dna.py`, `router.py`. Never commit `.env`
  files or secrets.
- Gate before a commit that touches TypeScript:
  `cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build`.

## CI and limits

- GitHub Actions on Aegis-Omega are locked by billing (#735): jobs do not start, so
  nothing can be verified or merged until the operator lifts it. Do not poll CI.
- The weekly plan limit is the binding constraint: no subagents, workflows, scheduled
  wake-ups or new sessions unless the operator asks; no full-file rewrites when a small
  change will do.

## Only the operator can (web UI)

Lifting the billing lock, enabling Pages, installing the Claude GitHub App, approving
bot workflow runs, deleting branches, editing an environment's setup script. Say so once,
with the exact place, and continue with everything else.

## Open priorities

#735 billing lock (operator) · #737 PR queue 392 to under 30 (classify now, execute after
#735) · #741 this page and a short CLAUDE.md · #742 move proof/ and research/ lanes to
their own repository · RH lab queue in HANDOFF.md.
