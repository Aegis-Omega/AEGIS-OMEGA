---
name: reload-skills
description: Reloads the skill catalog from disk into the current session without restarting. Invoke after creating or modifying a SKILL.md file mid-session so the updated skill is immediately available. Also invoke when the run-skill-generator has just produced new skill files.
---

# Reload Skills

**Metacognitive Layer: L3 (Working Memory)**

The skill catalog is L3 state — the set of skills the automaton knows about in this session. When a new SKILL.md is written or an existing one is modified, L3 is stale until reloaded. `/reload-skills` updates L3 to match the on-disk state.

L3 invariant: **Act on current skill state, not session-start state. If a skill was modified this session and not reloaded, any invocation of that skill runs the old version.**

---

## What it does

Scans `.claude/skills/` directories for SKILL.md files and makes them available for invocation by name in the current session. No restart required. Does not affect:
- L4 (long-term memory — AdaptiveLineage, git history)
- L7 (self-model — frozen file hashes, t0_verdict)
- Active hooks (require restart to take effect)

---

## When to invoke

```
skill SKILL.md written or modified
         │
         ▼
/reload-skills
         │
         ▼
invoke the new/updated skill by name
```

Mandatory after:
- `run-skill-generator` produces new SKILL.md files
- Any direct edit to a SKILL.md within this session
- Adding a new skill directory under `.claude/skills/`

Not needed for:
- Changes to hook commands (restart required)
- Changes to settings.json permissions (restart required)
- Rust or TypeScript source changes (unrelated to skill catalog)

---

## Relationship to run-skill-generator

`run-skill-generator` creates or regenerates SKILL.md content from a specification. After it runs, the files exist on disk but the session's L3 catalog is stale. The sequence is:

```
/run-skill-generator   →   new SKILL.md on disk   →   /reload-skills   →   /new-skill-name
```

Skipping `/reload-skills` between generation and invocation causes the automaton to say "skill not found" even though the file exists.

---

## Source

`.claude/skills/` directories in both repo root and `sovereign-omega-v2/`. Skill files follow `SKILL.md` naming convention with YAML frontmatter (name, description) required for catalog registration.
