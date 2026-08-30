---
name: morning-audit
description: Session-start constitutional audit. Run at the beginning of every session before any code is written. Orients to the current gate series, verifies system health, and declares the 2-gate target for the session. Invoked when the user says "start", "begin", "where were we", "morning", or when the session starts with no clear prior context.
---

# Morning Audit — Session Orientation Ritual

**Autopoietic Property: Self-Production Viability Check**

Before an autopoietic system can begin a production cycle, it must verify that it can still produce. A biological cell does not begin mitosis without first confirming that its membrane is intact and its metabolic machinery is functional. This audit is that check.

`verify-hashes.mjs` = membrane integrity (the three frozen files ARE the autopoietic boundary — if they are altered, the system is no longer producing itself; it is being produced by something else)
`cargo test` = metabolic viability (the test suite is the system verifying that its own synthetic machinery — the 599 gate modules — still produces correct outputs)
`git status` = inventory check (uncommitted work = components produced but not yet incorporated into the membrane; they must be committed before the next cycle begins)

A session that starts without this check is a production cycle that begins without confirming the cell is alive. The autopoietic system does not trust continuity — it verifies it.

Run exactly once at the start of each session. Produces a signed orientation report before any gate work begins.

## Step 0 — Self-Model Check (L7 + L6)
```bash
cd /home/user/AEGIS--/sovereign-omega-v2 && node scripts/verify-hashes.mjs 2>&1 | tail -3
curl -s http://localhost:7890/node 2>/dev/null | jq '{t0: .t0_verdict, corruption: .corruption_count}' 2>/dev/null || echo "bridge offline (ok at session start)"
```

Mandatory gate before any code work:
- `verify-hashes.mjs` must exit 0 → frozen files intact (L7 self-model valid)
- If bridge is running: `t0_verdict=true`, `corruption_count=0` required
- Classify the session's planned work epistemically: T2 gate modules → proceed

Report: `L7 SELF-MODEL: VALID / BREACH` · `L6 TIER: T2 gate work`

If self-model BREACH: HALT — invoke `/frozen-file-check` before any other step.

## Step 1 — Gate Progress & Test Health  _(L2 Perception)_
```bash
grep "Gates complete:\|tests)" /home/user/AEGIS--/CLAUDE.md | head -3
cd /home/user/AEGIS--/aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1
```

Report: `GATES: <N> · RUST TESTS: <T> · STATUS: <ok/FAIL>`

If cargo test fails: HALT — invoke `/diagnose` before proceeding.

## Step 2 — Active Gate Series  _(L3 Working Memory)_
```bash
tail -25 /home/user/AEGIS--/aegis-cl-psi/src/lib.rs | grep "pub mod"
```

Identify the active naming series (e.g., `gossip_broadcast_*`, `compaction_*`, `phi_*`).
Report: `ACTIVE SERIES: <prefix>_*`
Identify the last gate number from lib.rs or CLAUDE.md.

## Step 3 — Uncommitted Work  _(L7 Self-model integrity)_
```bash
git -C /home/user/AEGIS-- status --short
```

If any files are unstaged: commit them before proceeding (do NOT carry forward dirty state).
```bash
git -C /home/user/AEGIS-- stash list
```

Report: `WORKING TREE: CLEAN / DIRTY: <files>`

## Step 4 — Hash Integrity  _(L7 T0_ABORT path — already run in Step 0, confirm once more)_
```bash
cd /home/user/AEGIS--/sovereign-omega-v2 && node scripts/verify-hashes.mjs 2>&1 | tail -3
```

If fails: HALT — invoke `/frozen-file-check`.
Report: `HASH INTEGRITY: PASS / FAIL`

## Step 5 — Recent Session History  _(L4 Long-term Memory)_
```bash
git -C /home/user/AEGIS-- log --oneline -6
```

Read the last 6 commits to orient to momentum. Note which gate pair was last completed.
Scan for error patterns: did the last session end with a fix commit? A deferred annotation? Apply the ERROR Pattern Recognition table from the Metacognitive Protocol.

## Step 6 — Declare Session Target  _(L5 Executive Function)_
Based on the last gate number (N), declare:

```
SESSION TARGET:
  Gate <N+1>: gossip_broadcast_<name_a> — <1-line description>
  Gate <N+2>: gossip_broadcast_<name_b> — <1-line description>
  Threshold A: <CONST_NAME> = <value> (<meaning>)
  Threshold B: <CONST_NAME> = <value> (<meaning>)
  Est. tests: ~19 per gate = 38 new tests
  Est. Rust total after: <T+38>
```

Choose the next two gate names by following the active series pattern. Do not invent a new series mid-session — complete the current one first.

## Morning Audit Report Format

```
MORNING AUDIT — <date> <time>
════════════════════════════════
L7 Self-model:     VALID / BREACH
L6 Tier:           T2 gate work
Gates complete:    <N>
Rust tests:        <T> (all passing)
TS tests:          <T> (Gate 8 status)
Active series:     <prefix>_*
Working tree:      CLEAN / DIRTY
Hash integrity:    PASS / FAIL
Last commit:       <hash> <message>
Error patterns:    NONE / <pattern from last session>

SESSION TARGET:
  Gate <N+1>: <name> — <description>
  Gate <N+2>: <name> — <description>

CONSTITUTIONAL STATUS: GO / HOLD
METACOGNITIVE STATUS:  NOMINAL / DEGRADED
════════════════════════════════
```

`GO` = all checks pass, ready to build gates.
`HOLD` = any check failed — fix before proceeding.
`NOMINAL` = L7 valid, L6 classified, L3 loaded, L5 sequenced — full cognitive stack active.
`DEGRADED` = any layer check failed — document which layer before proceeding.
