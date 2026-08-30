---
name: zoom-out
description: High-level AEGIS status overview. Invoked when the user asks "where are we", "what's left", "status", "overview", "how many gates", "what's the plan", or when context has become too narrow and a broader perspective is needed. Reports constitutional health, gate progress, and next steps.
---

# Zoom Out Skill

**Metacognitive Layer: L8 (Theory of Mind) + L4 (Long-term Memory)**

Zooming out is the L8 operation: stepping from the immediate task to the operator's full intent and the system's full trajectory. When context has become too narrow, the automaton has lost L8 — it knows what it is doing but has lost the structural frame of WHY it is doing it and WHERE it fits in the full adaptive lineage.

L8 invariant: **Operator messages have holonic scale. A request about a specific gate is always also a statement about the session's direction and the system's evolution. Zoom out resolves the context collapse.**
L4 invariant: **The git log IS the long-term memory. The last 8 commits are the recent session's shape. Read them before assessing where to go next.**

Non-equivalence: **"Current gate" ≠ "System state". "What I'm building now" ≠ "What the system needs next". The zoom-out perspective is the one that makes these distinct.**

Step back from the current detail. Get a structural view of the full system state.

## Overview Protocol

### 1. GATE COUNT & TEST STATUS
```bash
cd /home/user/AEGIS--
grep "Gates complete:" CLAUDE.md | head -1
grep "tests)" CLAUDE.md | head -1
cd aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1
```

Report: `GATES: <N> complete · <T> tests passing · <last gate pair>`

### 2. RECENT HISTORY (last 8 commits)
```bash
git log --oneline -8
```

Report the gate pairs recently committed. Identify the rhythm of recent gate building.

### 3. CONSTITUTIONAL HEALTH
```bash
cd /home/user/AEGIS--/sovereign-omega-v2 && node scripts/verify-hashes.mjs 2>&1 | tail -3
```
Report: `HASH INTEGRITY: PASS / FAIL`

Check for uncommitted work:
```bash
git status --short
```

### 4. GATE SERIES PATTERN
Examine the last 6 module names in lib.rs to identify which series is active:
```bash
tail -30 /home/user/AEGIS--/aegis-cl-psi/src/lib.rs | grep "pub mod"
```

Identify: "Currently in the `gossip_broadcast_*` series" or similar.

### 5. SOVEREIGN-OMEGA STATE
```bash
cd /home/user/AEGIS--/sovereign-omega-v2 && npm run test 2>&1 | grep "test result\|Tests " | tail -3
```
Report: `TS SUITE: <N> tests · <status>`

### 6. COMMERCIAL PRODUCTS STATUS
Check if commercial products build (quick check, don't rebuild):
```bash
ls /home/user/AEGIS--/platform-picker/dist /home/user/AEGIS--/hub/dist /home/user/AEGIS--/hook-generator/dist /home/user/AEGIS--/content-calendar/dist /home/user/AEGIS--/cockpit/dist 2>/dev/null | grep -c "index.html" || echo "0 built"
```

### 7. NEXT GATE IDENTIFICATION
Based on the active series, determine the logical next two gates. The gossip broadcast series follows:
- fanout → retry → drop → ack → timeout → sequence → **[next: batch efficiency? dedup? peer routing?]**

Propose the next gate pair with their `CONST_NAME: u32 = N` thresholds and formula.

## Reporting Format

```
AEGIS STATUS — <date>

GATE PROGRESS:
  Complete:      <N> gates
  Rust tests:    <T> passing
  TS tests:      <T> passing
  Active series: <name>

RECENT GATES:
  <last 4 gate pairs from git log>

CONSTITUTIONAL HEALTH:
  Hash integrity:   PASS / FAIL
  Uncommitted work: <list or NONE>

NEXT GATES:
  Gate <N+1>: <name> — <1-line description>
  Gate <N+2>: <name> — <1-line description>

BLOCKERS: <NONE / list any issues>

SYSTEM IS:  adaptive · recursive · bounded · replay-governed
SYSTEM NOT: sovereign consciousness · unrestricted AGI
```
