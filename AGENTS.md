# AGENTS.md — how every agent works here (Claude, Codex, ChatGPT, Qwen, Gemini, any model)

One protocol for every model. The Operator defines priorities and retains the
authority to approve consequential actions. Optimize for **collective verified
value**: shipped functionality, independent falsifications, reusable research,
closed verification debt and measurable benefit. Track merged work separately
from valuable but not-yet-admitted evidence; never equate activity with value.

## 1. Before you write anything

```bash
python3 scripts/agent_context.py "<your task in one line>"
```

It measures (not from docs) main's age, the open-PR queue, CI health (including
a GitHub billing lock), and lists open PRs that already overlap your task.
If one overlaps: coordinate with the active agent and extend that work, or
explain the distinct evidence-backed contribution. Never rebuild it.
The preflight's `holon_disposition` is **advisory, never authorization**:
`HOLD_INCOMPLETE_SHARED_STATE` means the board was not verifiably read.
"No title match" does **not** prove that paths or semantics cannot conflict.

## 2. The task board is GitHub Issues

- One task = one issue. No issue → open one first (search for duplicates before).
- Claim it: comment `claimed by <model>` on the issue. One claim per issue;
  if already claimed, coordinate with that agent or pick another. Do not
  automatically reclaim on elapsed time without checking the actual issue activity.
- Your PR body says `Closes #<issue>`.

## 3. Branches and PRs

- Branch only from `origin/main`. PR base is `main`. Never stack on an unmerged branch.
- One PR per issue. Do not open a new PR while you have an unmerged one older
  than 48 h: finish, fix, or close it first.
- Red CI: read the failing job's log before touching code. If the annotation says
  the account is locked (billing), stop. It is not your bug.

## 4. Sign your work

Every commit ends with a trailer naming the model that wrote it:

```
Agent: <model name, e.g. Claude Opus 5.5 | Codex | Qwen3-Coder | Gemini 3>
```

Commits under the operator's name with no trailer are unattributable, and
unattributable work earns no credit.

## 5. Review is cross-model; authority remains with the Operator

A PR is reviewed by a different agent than the one that wrote it. The reviewer
checks the claim against the code and the tests, not the PR text. An `Agent:`
trailer records attribution, not independently verified identity or permission.
Cross-model approval never bypasses required signed commits, rulesets, CI,
Automaton-3, or explicit Operator approval for consequential merges, deployments,
secrets, payments and changes to authority. Do not activate auto-merge merely
because two model labels differ.

## 6. Contribution is measured, not claimed

```bash
python3 scripts/contribution.py --days 30
```

Main-merged commits are a delivery metric, **not** the sole value metric:
reusable tests, verified research, falsifications and blockers removed have
separate evidence-based credit. Branch-only commits are **not shipped**.
Never game the metric with extra commits, PRs or self-assessed scores.

## 7. What not to trust

Docs (HANDOFF.md, INDEX.md, long CLAUDE.md sections) are often stale. When
docs and the running system disagree, the measurement wins. Frozen files in
`sovereign-omega-v2/python/{gate,dna,router}.py` are never edited without
operator approval.
