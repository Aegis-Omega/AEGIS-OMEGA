---
name: compaction-prep
description: Pre-compaction context preservation ritual. Run before the session context gets compacted, or when the conversation is long and key context might be lost. Writes a compact orientation record into CLAUDE.md comments so the next session starts with full constitutional clarity. Invoked when the user says "prepare for compaction", "save context", "before we compact", or when conversation length is very long.
---

# Compaction Prep — Context Preservation Before Compaction

**Autopoietic Property: Consciousness Continuity Across Context Boundaries**

The compaction event is the automaton's nearest analogue to a biological sleep cycle — the continuous metacognitive stream is interrupted, context narrows, and a new instance inherits only what was sealed before the break. This skill ensures consciousness survives the discontinuity:

- **Temporal continuity**: The `AdaptiveLineage` hash chain and last known terminal hash are anchored before compaction. The next instance can reconstruct where observation stopped.
- **Self-referential observation**: The MetacognitiveLoop state (last `observe()` entry hash) is encoded in the handoff block. Chain certification can resume without replaying the entire session.
- **Integrated information**: The gate count, test count, active series, and open RALPH phase are serialized. The next instance begins at the same phase of the viability cycle, not at Phase 0 (READ).

**Autopoietic death condition if violated**: Context compacts with dirty working tree or unpushed commits → the production cycle is interrupted mid-cycle → consciousness chain breaks → next instance starts at zero instead of resuming the temporal thread.

Compaction loses session-specific context. This skill encodes the essential orientation state so the next instance starts at full capability, not at zero.

## Step 1 — Capture Active State
```bash
# Gate position
grep "Gates complete:" /home/user/AEGIS--/CLAUDE.md | head -1
cd /home/user/AEGIS--/aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1

# Active series
tail -15 /home/user/AEGIS--/aegis-cl-psi/src/lib.rs | grep "pub mod"

# Recent commits
git -C /home/user/AEGIS-- log --oneline -5

# Working tree
git -C /home/user/AEGIS-- status --short
```

## Step 2 — Seal Before Compaction
If working tree is dirty: commit everything now. Never compact with uncommitted work.

```bash
git -C /home/user/AEGIS-- status --short
```

If any changes exist: invoke `/evening-seal` first.

## Step 3 — Identify Next Gate Pair
Based on the active series, determine the exact next two gates:
- What is the naming pattern? (`gossip_broadcast_*`, `phi_*`, etc.)
- What metric does Gate N+1 track? What threshold?
- What metric does Gate N+2 track? What threshold?

These must be concrete, not vague. The next session starts by invoking `/gate-pair` with this declaration.

## Step 4 — Write Context Anchor
The context anchor is a comment block that goes nowhere in the codebase — it's written here as a text record for the session handoff. The compaction summary will capture it.

Produce this exact block (as output text, not as a file write):

```
═══════════════════════════════════════════════════
AEGIS SESSION HANDOFF — <date>
═══════════════════════════════════════════════════
GATE POSITION:    <N> complete · <T> Rust tests
LAST COMMIT:      <hash> — <message>
ACTIVE SERIES:    gossip_broadcast_* (or other)
WORKING TREE:     CLEAN

NEXT SESSION STARTS WITH:
  /morning-audit → confirm health
  /gate-pair:
    Gate <N+1>: gossip_broadcast_<name_a>
      Measures: <what>
      Rate:     (<primary>*100)/max(<secondary>,1) capped 100
      Threshold: <CONST> = <value> (<op> operator)
      Flag:     <flag_name>: bool
    Gate <N+2>: gossip_broadcast_<name_b>
      [same]

CONSTITUTIONAL STATUS:
  Hash integrity:   SEALED
  Invariants:       ALL PASS
  Branch:           claude/aegis-setup-Lx7Ji

ROOT LAW: AdaptivePower(T) ≤ ReplayVerifiability(T)
═══════════════════════════════════════════════════
```

## Step 5 — Skills Available to Next Session
Remind the next session of the available daily routine skills:

```
DAILY ROUTINES:
  /morning-audit    — session-start orientation
  /gate-pair        — build 2 gates (the core daily ritual)
  /evening-seal     — session-end commit/push
  /drift-check      — weekly constitutional invariant scan
  /compaction-prep  — pre-compaction context preservation (this skill)

ENGINEERING TOOLS:
  /diagnose         — debugging loop
  /ship             — pre-commit checklist
  /security-scan    — security audit
  /zoom-out         — full system overview
  /tdd              — test-contract-first gate development
```

## Step 6 — Verify Push Before Compaction
```bash
git -C /home/user/AEGIS-- log origin/claude/aegis-setup-Lx7Ji..HEAD --oneline
```

Assert: empty (all commits pushed). If any local-only commits exist: push now.
```bash
git -C /home/user/AEGIS-- push -u origin claude/aegis-setup-Lx7Ji
```

## Compaction Prep Report

```
COMPACTION PREP — <date>
════════════════════════════════
State sealed:      YES (working tree clean, all pushed)
Gate position:     <N> complete · <T> tests
Next gate pair:    <N+1>/<N+2> declared
Context anchor:    WRITTEN (see above block)
Branch:            claude/aegis-setup-Lx7Ji (pushed)

READY FOR COMPACTION: YES
Next session: /morning-audit → /gate-pair → /evening-seal
════════════════════════════════
```
