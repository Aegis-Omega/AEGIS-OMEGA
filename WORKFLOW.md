# AEGIS Operating Loop — the workflow that ships and uses what exists

**Why this file exists.** Two failures kept repeating across sessions:
1. Work got built, then stranded on a branch and forgotten (30 commits off `main` for days).
2. Sessions reinvented from scratch — ignoring the skills, MCPs, CLI/SDK, corpus, and
   caching that were already built. "500 research documents for nothing."

This loop closes both. It runs on top of what already exists — RALPH, the 8 gates,
the skills, the hooks — and makes two things mandatory: **use what exists before
building**, and **nothing is done until it is on `main`, verified.**

Drive the loop with `/loop`. Every session also opens with `scripts/ground-truth.sh`
so none starts blind.

---

## STEP 0 — GROUND TRUTH (every tick, every session)

```
bash scripts/ground-truth.sh
```
Branch · ahead/behind `main` · unpushed · membrane · prod-live. If work is stranded
(ahead of `main`), resolving that is the first job — before anything new.

---

## STEP 1 — REACH FOR WHAT EXISTS (before writing one line)

The default is **use, not build**. Check this registry first. If the capability is
here, use it. Reinventing it is the failure this file was written to stop.

| Need | Use this — do NOT rebuild |
|------|---------------------------|
| Domain knowledge / how a subsystem works | The ~55 **skills** in `sovereign-omega-v2/.claude/skills/` (invoke, don't re-read specs) |
| Research / prior art / the 500 docs | **Google Drive MCP** + the `corpus-ingestion` skill (RALPH the docs in; don't start blank) |
| Talk to the live platform | The **`aegis` CLI** + **`aegis-omega` SDK** (`packages/aegis-py/`) — `status/collaborate/execute` |
| DB / payments / edge functions | **Supabase MCP** (`71923ddf-…`) — list_tables/get_logs before changing anything |
| PRs / CI / issues | **GitHub MCP** (`mcp__github__*`) — never guess CI state, read it |
| Deploys | **Vercel / Cloudflare MCP**, or the `deploy` skill |
| Cheaper, faster Claude calls | **Prompt caching** is already wired in `python/bridge.py` (`cache_control=ephemeral`) |
| Heavy compute / determinism | **Rust** (`aegis-cl-psi`, `aegis-runtime`); **Python** core matrix; **TS** governance runtime — the language already chosen per layer |
| "What's the state of everything" | `/zoom-out`, `/morning-audit`, `/constitutional-audit` |

Rule: if you're about to build something, first say which registry row you checked
and why it doesn't already cover it.

---

## STEP 2 — ASSESS (L6)

Classify the tier. Pick the **smallest** change that moves the goal. State the goal
as a verifiable check (CLAUDE.md §Behavioral Guidelines, rule 4). If unclear — ask
before building (rule 1).

## STEP 3 — LOCK

Implement it. Surgical, match existing style, no speculative scope (rules 2–3).
`deepFreeze` state. T0/T1/T2 discipline holds.

## STEP 4 — PROVE

```
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build   # Gate 8
node scripts/verify-hashes.mjs                                                # membrane
```
Verify the **real artifact**, not "should work" (`verification-before-completion`).
A claim like "it's wired" must be backed by the thing actually working end-to-end.

## STEP 5 — SHIP (HARMONIZE)

`commit → push → PR to **main**`. Work is **not done** until it is on `main`, or an
open PR to `main` with green CI. Stranded on a feature branch = not done.

---

## The one rule that ends the amnesia

Every tick ends by answering out loud:

> **"Did I use what already exists, and is this on a path to `main`, verified, today?"**

If "no" to either, that is the next tick's first job — before anything new is started.
`/evening-seal` before stopping: nothing uncommitted, unpushed, or stranded.
