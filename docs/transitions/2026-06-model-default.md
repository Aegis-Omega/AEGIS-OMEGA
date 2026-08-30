# Transition record: swarm default model — Fable 5 era (2026-06-10 → 2026-06-23)

All facts below were verified by git archaeology (`git log --all -S"claude-fable-5"`,
`git show 4747755`, `git show 8305ec6`) on branch `claude/slack-session-yyw7h6`.

## Record 1 — swarm code default (`AEGIS_SWARM_MODEL` fallback)

Three code sites: `sovereign-omega-v2/python/platform_helpers.py` `SWARM_MODEL`
(env fallback) and `sovereign-omega-v2/python/bridge.py` `/claude` + `/claude/stream`
request-body `model` defaults.

| Field | Value |
|-------|-------|
| Old value | `claude-sonnet-4-6` |
| Introducing commit | `4747755` (PR #148, 2026-06-10 13:09 +0200) — flipped all three code sites to `claude-fable-5`; also added a Fable-specific refusal fallback |
| Refs containing | Carried (not introduced) by PR #150 merge `a98ad63`: its tree contained fable-5 but its diff did not touch it; the squash title credited #148's work |
| Replacement value | `claude-opus-4-8` |
| Replacing commit | `8305ec6` (PR #172, 2026-06-23 23:35 +0200) — all three code sites + CLAUDE.md; commit message called fable-5 "the source of the recurring 'Fable 5 unavailable' errors"; 557/557 platform tests |
| Current canonical | `claude-opus-4-8` at HEAD and origin/main (`31bcb7e`) — `platform_helpers.py:20`, `bridge.py:538,617` |

## Record 2 — CLAUDE.md doc line (`AEGIS_SWARM_MODEL` default)

| Field | Value |
|-------|-------|
| Old value | `claude-sonnet-4-6` documented as swarm default |
| Introducing commit | `4747755` (PR #148) — flipped CLAUDE.md doc lines to `claude-fable-5` |
| Refs containing | `e22087b` (PR #153, 2026-06-17) rewrote CLAUDE.md, dropping the `VITE_CLAUDE_MODEL` line but re-adding `AEGIS_SWARM_MODEL` default `claude-fable-5` |
| Replacement value | `claude-opus-4-8` |
| Replacing commit | `8305ec6` (PR #172) |
| Current canonical | `claude-opus-4-8` in CLAUDE.md at HEAD |

## Interim events

- `dd2cc790` (2026-06-14) pinned `.claude/settings.json` to `claude-opus-4-8` because
  sessions defaulted to the unavailable Fable 5.
- `e22087b` (PR #153, 2026-06-17) — see Record 2.

## Nuance: frontend was never Fable 5 in code

The frontend CODE default was never `claude-fable-5`: pickaxe over `packages/`,
`hub/`, `cockpit/` returns empty. `packages/shared/lib/inference-router.ts` default
was and is `claude-haiku-4-5-20251001`; `cockpit` `agent.ts` uses `claude-sonnet-4-6`.
The #148-era CLAUDE.md claim "hub router default: claude-fable-5" was doc-only and
never true in code.

## Caveat

This clone is shallow/grafted (grafts `2d60f69`, `3dd4be2`); findings hold within
reachable history.
