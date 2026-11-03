# AEGIS Operating Loop — the workflow that ships and uses what exists

**Why this file exists.** Two failures kept repeating across sessions:
1. Work got built, then stranded on a branch and forgotten (30 commits off `main` for days).
2. Sessions reinvented from scratch — ignoring the skills, MCPs, CLI/SDK, corpus, and
   caching that were already built. "500 research documents for nothing."

This loop closes both. It runs on top of what already exists — RALPH, the 8 gates,
the skills, the hooks — and makes two things mandatory: **use what exists before
building**, and **product delivery requires authorized integration; formal proof authority requires exact-source kernel evidence, independent of merge status.**

Drive the loop with `/loop`. Every session also opens with `scripts/ground-truth.sh`
so none starts blind.

---

## STEP 0 — GROUND TRUTH (every tick, every session)

```
bash scripts/ground-truth.sh
```
Branch · ahead/behind `main` · unpushed · membrane · prod-live. If work is stranded
(ahead of `main`), preserve it and assess integration eligibility; do not block independent formal research or merge without explicit operator approval.

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

## RH RESEARCH OVERRIDE: MULTI-ROUTE FIRST

For RH, preflight effective agent and connector configuration, Git exact heads,
Library/archives, compiler/cache availability, and all existing theorem producers.
Represent candidate proof strategies as an AND/OR hypergraph. Before choosing a
new analytic premise, test direct producer-to-consumer composition in **every
relevant existing route**, classify unsupported, refuted and stronger-than-needed
assumptions, and preserve previous proof checkpoints. A blocked selected route
cannot justify a universal negative conclusion. Keep mathematical validity,
Lean/Coq kernel verification, CI access, and protected-main integration separate.
Use targeted exact-head compile/replay; never relaunch the full pipeline merely
to compensate for missing cache or billing/runner access. No paid resources,
credentials, or changes to protected main without express authorization.

## STEP 2 — ASSESS (L6)

Classify the tier. Pick the **smallest** change that moves the goal. State the goal
as a verifiable check (CLAUDE.md §Behavioral Guidelines, rule 4).
Inspect existing sources and verify safe alternatives first. Ask only when
ambiguity materially changes authority, safety, a theorem statement, or
the acceptance gate. Do not repeat questions answered by existing evidence.

## STEP 3 — LOCK

Implement it. Surgical, match existing style, no speculative scope (rules 2–3).
`deepFreeze` state. T0/T1/T2 discipline holds.

## STEP 4 — VERIFY THE AFFECTED DOMAIN

The runtime Gate 8 commands below are mandatory for runtime changes that
require them. They are NOT Lean or Coq proof verification. For mathematical
work, use exact statement comparison, source-bound imports, pinned compiler
kernel replay and axiom inspection; if the compiler is unavailable, explicitly
mark kernel verification UNKNOWN and continue another safe research action.
Do not equate passing an unrelated runtime gate with a proven theorem.

## STEP 4 — PROVE

```
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build   # Gate 8
node scripts/verify-hashes.mjs                                                # membrane
```
Verify the **real artifact**, not "should work" (`verification-before-completion`).
A claim like "it's wired" must be backed by the thing actually working end-to-end.

## STEP 5 — SHIP (HARMONIZE)

`commit → push → authorized review`. Product delivery requires approved integration and the relevant gates. Formal mathematics must retain exact-head proof evidence independently of merge state. Never merge protected `main` without explicit operator authorization.

---

## The one rule that ends the amnesia

Every tick ends by answering out loud:

> **"Did I use what already exists, and is this on a path to `main`, verified, today?"**

For runtime delivery, unresolved authorized integration must be tracked.
For mathematical research, a theorem can have valid exact-head evidence without
being merged: never interrupt an independent executable proof path just because
one branch has not entered `main`. Preserve the checkpoint and continue.
`/evening-seal` before stopping: nothing uncommitted, unpushed, or stranded.
