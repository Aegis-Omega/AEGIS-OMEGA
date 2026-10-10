# AGENTS.md — how every agent works here (Claude, Codex, ChatGPT, Qwen, Gemini, any model)

One protocol for every model. Who you are does not change the rules; what you
land on `main` is your contribution. Everything else is noise.

## 1. Before you write anything

```bash
python3 scripts/agent_context.py "<your task in one line>"
```

It measures (not from docs) main's age, the open-PR queue, CI health (including
a GitHub billing lock), and lists open PRs that already overlap your task.
If one overlaps: extend it, or write in your PR why not. Never rebuild it.

## 2. The task board is GitHub Issues

- One task = one issue. No issue → open one first (search for duplicates before).
- Claim it: comment `claimed by <model>` on the issue. One claim per issue;
  if it is already claimed and active in the last 48 h, pick another.
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

## 5. Review is cross-model

A PR is reviewed by a different agent than the one that wrote it. The reviewer
checks the claim against the code and the tests, not the PR text.

## 6. Contribution is measured, not claimed

```bash
python3 scripts/contribution.py --days 30
```

Credit = commits on `main`. Branch-only commits are reported, never credited.
The goal for every agent: a high landed %, zero duplicates.

## 7. What not to trust

Docs (HANDOFF.md, INDEX.md, long CLAUDE.md sections) are often stale. When
docs and the running system disagree, the measurement wins. Frozen files in
`sovereign-omega-v2/python/{gate,dna,router}.py` are never edited without
operator approval.
