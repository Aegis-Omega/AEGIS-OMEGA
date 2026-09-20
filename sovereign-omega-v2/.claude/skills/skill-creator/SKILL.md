---
name: skill-creator
description: Create new skills, modify and improve existing skills, and measure skill performance. Use when users want to create a skill from scratch, edit or optimize an existing skill, run evals to test a skill, benchmark skill performance with variance analysis, or optimize a skill's description for better triggering accuracy.
---

<!-- Source: anthropics/skills@skill-creator via claudemarketplaces.com -->

# Skill Creator

A structured workflow for creating new Claude Code skills and iteratively improving them.

## Workflow

### 1 — Capture Intent

Understand what the skill should do:
- When does it trigger?
- What is the expected output format?
- Are test cases needed?

### 2 — Interview & Research

Ask about:
- Edge cases and failure modes
- Input/output formats and examples
- Success criteria
- Dependencies (tools, packages, APIs)

### 3 — Write SKILL.md

Create the skill file with:
```yaml
---
name: <skill-name>
description: <one sentence — when does Claude auto-invoke this?>
---
```

Then: purpose section, core instructions, examples, edge cases.

### 4 — Create Test Cases

Draft 2–3 realistic test prompts and save to `evals/evals.json`:

```json
[
  {
    "prompt": "...",
    "assertions": ["output contains X", "output does not contain Y"]
  }
]
```

### 5 — Run Tests

Spawn parallel runs with and without the skill. Capture outputs and timing.

### 6 — Evaluate Results

Grade assertions, aggregate benchmarks, launch eval viewer for review.

### 7 — Iterate

Apply improvements based on feedback, rerun tests, repeat until satisfied.

### 8 — Optimize Description

Use trigger evaluation queries to optimize the skill `description` for better invocation accuracy. The description is the primary signal for auto-invocation — it must be specific and unambiguous.

### 9 — Package

Final skill structure:
```
skill-name/
├── SKILL.md             (required)
└── bundled/             (optional)
    ├── scripts/         — executable code
    ├── references/      — documentation
    └── assets/          — templates, fonts
```

## Key Principles

- **Progressive disclosure**: Metadata always in context; SKILL.md body under 500 lines; bundle heavy resources separately
- **No surprise**: No malware, exploits, or misleading content
- **Generalization**: Write for reuse across millions of prompts, not just your test case
- **Lean prompts**: Remove anything not pulling its weight
- **Explain the why**: Help the model understand reasoning, not just follow rote steps

## AEGIS Skill Harness Integration

All AEGIS skills live in `sovereign-omega-v2/.claude/skills/<skill-name>/SKILL.md`.

Frontmatter convention:
```yaml
---
name: <skill-name>
description: <one sentence — what triggers auto-invocation>
---
```

After writing a new skill: verify it appears in `ls sovereign-omega-v2/.claude/skills/` and commit it. No build step required — skills are static markdown.

Constitutional constraint: skills are **read-only instructions**, not executable code. They cannot modify `python/gate.py`, `python/dna.py`, or `python/router.py`.


## AEGIS Automatic Lifecycle

The operator does not perform skill-lifecycle chores.

For every new or modified AEGIS skill, the agent completing the work must carry the lifecycle through itself:

1. Write or update `SKILL.md`.
2. For a new skill, create `evals/evals.json` in the same package with realistic positive, negative-routing, and adversarial/edge-case prompts.
3. Run the bundled deterministic package validator before treating the skill package as structurally complete.
4. Never ask the operator to count skills, edit `.claude.json`, update `skill-hashes.sha256`, reload a manifest by hand, or manually start a ledger job.
5. On a repository PR, let `.github/workflows/skill-lifecycle.yml` dispatch the trusted cognitive-manifest writer when the tip commit changes a `SKILL.md`.
6. Verify the resulting exact-head cognitive manifest, skill hash ledger, Trusted Cognitive Admission, and Integration Ledger evidence before describing the skill as admitted.
7. Keep the change fail-closed and draft while required evidence is unavailable or stale. Infrastructure failure is not skill failure and must be reported as such.
8. Do not push operator work downstream as a workaround. Repair or retry the automated lane instead.

Operator approval remains required for consequential authority transitions such as merge, deploy, publication, external data movement, or any other action whose authority boundary requires explicit approval.

The lifecycle is complete only when the skill package and its evidence are bound to the same exact repository head.
