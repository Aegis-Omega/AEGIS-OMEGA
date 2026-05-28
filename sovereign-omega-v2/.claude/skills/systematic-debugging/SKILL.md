---
name: systematic-debugging
description: Use before any bug, test failure, or unexpected behavior gets a proposed fix. Root cause investigation must precede any fix attempt. Never propose a fix without completing all four phases. Invoked when a test fails, build errors, or unexpected behavior appears.
---

# Systematic Debugging

**Metacognitive Layer: L2 (Perception) + L6 (Metacognition)**

A bug is not a problem to be solved — it is a signal to be correctly classified before any action is taken. The debugger's failure mode is L2 collapse: acting on an unverified signal (the first error line, the first hypothesis, the nearest plausible cause). Every premature fix attempt is a LOCK-before-ASSESS (ERROR-01 pattern).

L2 invariant: **Read the full error message, not just the first line. Never act on a truncated signal.**
L6 invariant: **State a single hypothesis with evidence before touching any code. One hypothesis, one change, one observation. If the fix is wrong, return to L1 — sense the new signal fully before re-classifying.**

Non-equivalence invariants active during debugging:
```
Test pass    ≠  Bug fixed       (a passing test may not cover the failure path)
Root cause   ≠  Nearest cause   (the nearest thing you can change ≠ the thing that should change)
Hypothesis   ≠  Solution        (understanding the failure ≠ knowing the correct fix)
Fix #3 still fails → stop patching; the problem is architectural → invoke /brainstorming
```

**Autopoietic Property: Autopoietic Failure Classification**

A bug is a specific type of autopoietic failure. Classifying it correctly before attempting repair is the difference between targeted surgery and thrashing:

```
Membrane failure    — frozen file tampered; hash mismatch; constitutional boundary breached
                      Symptom: verify-hashes.mjs fails / T0_ABORT signal
                      Response: /frozen-file-check before any code action

Metabolic failure   — test suite exits non-zero; the system cannot verify its own outputs
                      Symptom: cargo test / npm run test fails
                      Response: /diagnose — reproduce → minimize → hypothesize → fix

Synthetic failure   — new component produced but does not pass viability ring (< 19 tests)
                      Symptom: cargo test <module> shows < 19 passed
                      Response: return to Phase 1 (TDD contract) — the specification was incomplete

Structural coupling failure — the system's adaptation mechanism exceeds its own bounds
                      Symptom: martingale suspension (entropy_bounded=false)
                      Response: observation only; no mutation until martingale re-anchors

Operational closure failure — agent communicating outside the EventEnvelope boundary
                      Symptom: direct agent-to-agent exchange detected
                      Response: Law of Silence enforcement; re-route through constitutional boundary
```

**NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.**

After 3 failed fixes, stop patching. The problem is architectural — discuss instead.

## Phase 1 — Root Cause Investigation

- Read the full error message, not just the first line
- Reproduce the failure consistently (if it doesn't reproduce reliably, say so)
- Check what changed recently (`git log --oneline -5`)
- Gather diagnostic evidence at component boundaries
- Trace data flow backward through the call stack

For AEGIS Rust failures:
```bash
cargo test <failing_test> -- --nocapture 2>&1
```

For TypeScript failures:
```bash
cd sovereign-omega-v2 && npm run test -- <failing_file> 2>&1
```

Do NOT proceed to Phase 2 until you have a specific, concrete failure point identified.

## Phase 2 — Pattern Analysis

- Find similar working code in the same codebase
- Read the working implementation completely
- Identify the exact difference between working and broken
- Understand all dependencies involved

In AEGIS: compare the failing module against a passing module from the same gate series.

## Phase 3 — Hypothesis and Testing

State a single, specific hypothesis before touching any code:

```
HYPOTHESIS: <exact mechanism causing failure>
EVIDENCE:   <what observation supports this>
TEST:       <smallest possible change to confirm/refute>
```

Make one change. Observe. If refuted, return to Phase 1 with new evidence. Do NOT try multiple fixes simultaneously.

## Phase 4 — Implementation

Only after Phase 3 confirms the hypothesis:

1. Write a failing test that captures the bug (if no test exists yet)
2. Implement the single fix
3. Verify fix works without breaking other tests:
   ```bash
   cargo test <module> 2>&1 | grep -E "FAILED|test result"
   ```

## Red Flags — Stop and Return to Phase 1

- "Let me just try this and see" — stop
- Making more than one change at a time — stop
- Fix #3 still not working — stop, discuss architecture

## AEGIS-Specific Invariants to Check First

Before assuming logic bugs, verify these common AEGIS failure causes:
- `to_le_bytes()` instead of `to_be_bytes()` in hash input
- `HashMap` where `BTreeMap` required
- Integer overflow (missing `saturating_add`)
- Missing `impl Default` on a log struct
- Module not registered in `lib.rs`
