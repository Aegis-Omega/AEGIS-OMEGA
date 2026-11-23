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

- Never write to `main` directly, never force-push, never rewrite history. Work on an
  explicit branch; check its head before every push and verify the blob SHAs after.
  Land work on `main` only through a pull request, per "Merging and spend" below.
- In Claude Code the authority guard (`scripts/claude-authority-guard.py`) blocks pushes
  from the shell; push through the GitHub MCP (`push_files`) to a non-main branch.
- Frozen: `sovereign-omega-v2/python/gate.py`, `dna.py`, `router.py`. Never commit `.env`
  files or secrets.
- Gate before a commit that touches TypeScript:
  `cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build`.

## Merging and spend (operator directive, 2026-11-23)

Replaces the earlier "no merge without express operator instruction" rule.

- Agents merge pull requests into `main` themselves (`merge_pull_request` or auto-merge)
  when it makes sense: every required check is green on the exact head, a different model
  than the author has reviewed it, the PR is not a draft, and it has no conflicts. Prefer
  squash so one revert undoes it. If any of that is UNKNOWN, do not merge.
- Never merge: a PR with a failing or missing required check, one that disables or
  weakens a check or ruleset, one that touches the frozen files, secrets, permissions or
  billing, anything labelled `needs-operator`, or RH PR #92. The author never approves
  their own PR.
- Spend is allowed while it is covered by free credits assigned to the account. Confirm
  the credit source before spending; if it is unknown, stop. Never add a payment method,
  upgrade a plan, or run anything that bills beyond the credits.

## CI and limits

- GitHub Actions billing rejection is historical, not a blanket current lock (#735).
  Native runner execution succeeded on 2026-11-02 (runs 41403116306 and 41406485670).
  Current billing state and isolated startup failures remain UNKNOWN. Inspect each
  run's exact head, jobs and annotations before claiming any build is blocked or green.
  Do not poll CI.
- The weekly plan limit is the binding constraint: no subagents, workflows, scheduled
  wake-ups or new sessions unless the operator asks; no full-file rewrites when a small
  change will do.

## Only the operator can (web UI)

Checking or changing organization billing, enabling Pages, installing the Claude
GitHub App, approving bot workflow runs, deleting branches, editing an environment's
setup script. Say so once,
with the exact place, and continue with everything else.

## Open priorities

#735 verify residual billing status (not a universal CI blocker) · #737 PR triage
(use current issue and source, not historical queue counts) · #741 this page and
a short CLAUDE.md · #742 preserve and index proof/ and research/ lanes before
any move · RH lab queue in HANDOFF.md.
