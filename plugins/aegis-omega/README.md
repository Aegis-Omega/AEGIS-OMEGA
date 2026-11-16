# AEGIS Ω Mission Control

A Claude Code mod for everyone who works on AEGIS-OMEGA and the RH lab.

- **Operating facts from the first turn.** Every session gets the AEGIS facts in its system prompt: where the RH lab and its HANDOFF.md are, how pushes work here, which paths differ between Claude Code and Codex, and which actions only the GitHub web UI can do.
- **Shield for the plan limit.** Subagents, workflows, scheduled wake-ups and new sessions are refused unless the user's latest message asks for them (agent, workflow, delegiraj, zakaži, sesija, ...). The model is told to do the work in the session instead.
- **Push ledger.** Every push through the GitHub MCP is recorded, with a reminder to verify the blob SHAs.
- **`/omega` pane.** The RH frontier, this session's prompts, tool calls, pushes and shield blocks, and the ledger. The status line shows the same counters.

## Install

At the prompt of a Claude Code session (after this marketplace is on the default branch):

```
/plugin install aegis-omega --marketplace Aegis-Omega/AEGIS-OMEGA
```

From a shell:

```
claude plugin install aegis-omega --marketplace Aegis-Omega/AEGIS-OMEGA
```
