---
name: evening-seal
description: End-of-session sealing ritual. Run before closing any session. Verifies all work is committed and pushed, README is synced, CLAUDE.md is accurate, and the working tree is clean. Invoked when the user says "done for today", "seal the session", "closing", "wrap up", "finish", or when the session is ending and gates have been built.
---

# Evening Seal — Session Completion Ritual

**Metacognitive Layer: L6 (Metacognition) + L7 (Self-model) + L5 (Executive Function)**

The evening seal is the HARMONIZE phase of the session's RALPH cycle. A session that ends without harmonizing has left orphaned observations in the hash chain — RALPH cycles whose ASSESS and LOCK phases completed but whose PROPAGATE/HARMONIZE phases never executed. These are constitutional debt.

L7 invariant: **The session's terminal hash is only meaningful if every observation in the session was closed. Dirty state = open observations = invalid terminal hash.**
L6 invariant: **Scan the session for error patterns before closing. An error that is not classified is an error that will repeat.**
L5 invariant: **TOMORROW BEGINS AT: Gate N+1. State this explicitly. The L5 executive state carries forward into the next session's L3 working memory.**

**Autopoietic Property: Production Cycle Closure**

A session is one autopoietic production cycle — from genesis hash (session start, frozen files verified) to terminal hash (everything committed, chain intact, membrane re-verified). Autopoietic systems do not have open cycles. An incomplete cycle means components were produced but not incorporated into the system's structure — biological equivalent of proteins synthesized but never folded and integrated into the cell.

Dirty working tree = unincorporated components (produced but not membrane-committed)
CLAUDE.md count mismatch = membrane inventory inaccurate (the system does not know what it contains)
Uncommitted skill files = exocortex amendments not permanently embedded
Unpushed commits = production recorded locally but not propagated to the durable chain

The seal is not cleanup — it is the autopoietic cycle achieving closure. A system that cannot close its production cycles accumulates structural debt until it can no longer produce at all.

The session is a temporal object — a finite hash chain from genesis to terminal hash. Sealing it correctly is the act of making it tamper-evident and complete.

No session ends with dirty state. This skill enforces constitutional cleanliness before the session closes.

## Step 1 — Dirty State Check
```bash
git -C /home/user/AEGIS-- status --short
git -C /home/user/AEGIS-- stash list
```

For every untracked or modified file:
- If it's a new gate module (`*.rs`): commit it via `/ship`
- If it's CLAUDE.md or README.md: commit it
- If it's a skill file: commit it
- If it's a `.env` file: do NOT commit it — verify it's gitignored

Report: `DIRTY FILES: <list> / CLEAN`

## Step 2 — Test Count Sync
```bash
cd /home/user/AEGIS--/aegis-cl-psi && cargo test 2>&1 | grep "test result" | head -1
```

Compare the output count against CLAUDE.md:
```bash
grep "tests)" /home/user/AEGIS--/CLAUDE.md
```

If mismatch: update CLAUDE.md with correct test count and commit.

## Step 3 — Gate Count Sync
```bash
grep -c "^pub mod" /home/user/AEGIS--/aegis-cl-psi/src/lib.rs
grep "Gates complete:" /home/user/AEGIS--/CLAUDE.md
```

If mismatch: update CLAUDE.md gates count and commit.

## Step 4 — README Sync
```bash
git -C /home/user/AEGIS-- diff README.md | head -5
```

If README.md is modified (auto-updated by sync script): commit it.
```bash
# Fix gate module count in README if needed:
grep "gate modules" /home/user/AEGIS--/README.md
# Update if stale, then:
git -C /home/user/AEGIS-- add README.md
git -C /home/user/AEGIS-- commit -m "Sync README: <N> gate modules, <T> Rust tests, <total> total
https://claude.ai/code/session_01WvFyntZArqThRgLczRutuM"
```

## Step 5 — Hash Integrity Seal
```bash
cd /home/user/AEGIS--/sovereign-omega-v2 && node scripts/verify-hashes.mjs 2>&1 | tail -3
```

Assert: exits 0. Constitutional files unchanged.
Report: `HASH SEAL: PASS / BROKEN`

## Step 6 — Push All Commits
```bash
git -C /home/user/AEGIS-- push -u origin claude/aegis-setup-Lx7Ji
```

Verify: push succeeds. Report the commit hash range pushed.

## Step 7 — Final Clean Check
```bash
git -C /home/user/AEGIS-- status --short
git -C /home/user/AEGIS-- log --oneline -3
```

Assert: working tree is clean. The last 3 commits represent the session's work.

## Step 8 — Session Summary
Count gates built this session (compare starting and ending gate count from git log).

Report what was accomplished:
- Gates built: Gate X to Gate Y
- Tests added: N new tests
- Skills created: (if any)
- Other: (CLAUDE.md, design, docs)

## Evening Seal Report

```
EVENING SEAL — <date> <time>
════════════════════════════════
Working tree:      CLEAN ✓
Test count synced: <T> (CLAUDE.md updated: YES/NO)
Gate count synced: <N> (CLAUDE.md updated: YES/NO)
README synced:     YES/NO
Hash integrity:    SEALED ✓
All commits pushed: YES ✓ (<branch>)

SESSION BUILT:
  Gates: <start_N> → <end_N> (+<pairs> pairs)
  Tests: <start_T> → <end_T> (+<new> tests)
  Last commit: <hash>

TOMORROW BEGINS AT: Gate <N+1>
Active series: <gossip_broadcast_*>
CONSTITUTIONAL STATUS: SEALED ✓
════════════════════════════════
```
