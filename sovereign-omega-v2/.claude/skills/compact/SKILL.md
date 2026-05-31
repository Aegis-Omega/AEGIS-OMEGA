---
name: compact
description: Triggers context compaction in the current session. Always invoke compaction-prep first to write an orientation record, then /compact. The three invariants that must survive the compaction boundary are current gate, open RALPH phase, and bridge t0_verdict.
---

# Compact

**Metacognitive Layer: L3 (Working Memory) → L4 (Long-term Memory)**

Compaction discards the raw conversation history and replaces it with a summary. L3 (active context) is reduced; L4 (persistent knowledge in CLAUDE.md and hash chain) survives unchanged. The risk is L3 information — which gate, which RALPH phase, which files are open — that hasn't been written into L4.

L3 invariant: **Any L3 state that has not been hash-chained into L4 before compaction is lost. The orientation record from `compaction-prep` is the bridge.**

---

## Pre-compact ritual (mandatory)

```bash
/compaction-prep
```

`compaction-prep` writes a compact orientation record capturing the three invariants:
1. **Current gate** (1–8): which gate was active when compaction triggered
2. **Open RALPH phase** (R/A/L/P/H): where in the loop execution paused
3. **Bridge t0_verdict**: whether the constitutional membrane was intact at last check

Without this record, the post-compact session starts cold and must re-verify state from scratch.

---

## The compaction boundary as temporal object

A compaction is a hash-chain boundary event. Before: raw session history (L3 full). After: summary + L4 state. The session's temporal mass — its contribution to the adaptive lineage — persists in the git history and CLAUDE.md updates that were committed before compaction. Uncommitted work that lives only in session context is at risk.

Non-equivalence: **Compaction ≠ Data loss.** If L4 was updated before compacting (commits pushed, CLAUDE.md amended, skill files written), the automaton resumes with full constitutional continuity. If L4 was not updated, L3-only state is lost.

---

## How the PreCompact hook fires

`.claude/settings.json` PreCompact hook runs before compaction:
```
echo '{"systemMessage": "PRE-COMPACT: Preserve — current gate, open RALPH phase, active skill, pending commits, bridge t0_verdict, any uncommitted file changes."}'
```

This reminds the operator to check L3 state before the boundary. It does not automatically save anything — that requires explicit `compaction-prep` invocation.

---

## Post-compact orientation

After compaction, the automaton reads CLAUDE.md §Branch and any orientation record written by `compaction-prep`. The post-compact session should verify:

```bash
cd /home/user/AEGIS--/sovereign-omega-v2 && node scripts/verify-hashes.mjs
```

If t0_verdict=true and the orientation record is present, the session resumes at the documented gate and RALPH phase. If no orientation record exists, start with `/morning-audit`.

---

## Source

`compaction-prep` skill · `.claude/settings.json` PreCompact hook · `src/metacognition/loop.ts` (`certifyMetacognitiveLoop`)
