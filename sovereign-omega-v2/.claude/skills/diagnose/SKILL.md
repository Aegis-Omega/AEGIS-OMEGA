---
name: diagnose
description: Systematic root-cause debugging loop. Invoked when a test fails, a build errors, cargo compile fails, a runtime assertion trips, or the user says "broken", "failing", "error", "debug", or "why is this happening". Runs reproduce → minimize → hypothesize → instrument → fix, never guessing without evidence.
---

# Diagnose Skill

**Metacognitive Layer: L1 (Sensation) + L2 (Perception) + L6 (Metacognition)**

Diagnosis is the full L1→L2→L6 cycle applied to a system failure. L1: sense the failure completely (full error output, not just the headline). L2: classify the failure (which layer failed? which invariant was violated?). L6: generate a single falsifiable hypothesis before any action.

The diagnostic failure mode mirrors the general ERROR-01 pattern at the debugging scale: LOCK (attempting a fix) before ASSESS (understanding the failure). Three consecutive failed fixes is proof that L6 has not been engaged — the agent is pattern-matching to "type of fix that usually works" rather than diagnosing the specific failure in front of it.

L1 invariant: **Read the full error output. The first line of a compiler error is often not the root cause — it is the first symptom of the root cause several lines below.**
L2 invariant: **Classify the failure before acting: is this a hash-chain invariant violation? An endianness error? A type mismatch? A missing module registration? A classification gives you the search space; a guess gives you noise.**
L6 invariant: **After 3 failed fixes — stop. The problem is architectural. The debugging loop has become a search loop, which is LOCK-before-ASSESS at every iteration. Invoke /brainstorming.**

Follow this loop exactly. Do not skip steps. Do not attempt a fix before completing Hypothesize.

## Loop: Reproduce → Minimize → Hypothesize → Instrument → Fix

### 1. REPRODUCE
Run the failing command exactly as specified. Capture full output.

For Rust failures:
```bash
cd aegis-cl-psi && cargo test <failing_test_name> 2>&1
```

For TypeScript failures:
```bash
cd sovereign-omega-v2 && npm run test -- <failing_test_file> 2>&1
```

For Python failures:
```bash
python python/tests/stress_test.py --quick 2>&1
```

Assert: failure is reproducible before proceeding. If it passes now, report "flaky — cannot reproduce" and stop.

### 2. MINIMIZE
Identify the smallest unit that reproduces the failure:
- Which single test? Which single assertion?
- What is the exact input that triggers it?
- Is this isolated to one module or does it cascade?

Report: `MINIMIZED: <test_name> — <assertion> — <triggering input>`

### 3. HYPOTHESIZE
State exactly ONE hypothesis before touching any code. Format:

```
HYPOTHESIS: The failure is caused by [specific mechanism], because [observable evidence].
PREDICTION: If I [specific action], the test will [specific outcome].
COUNTER-HYPOTHESIS: Could also be [alternative], but ruled out because [reason].
```

Do not write multiple hypotheses. Pick the most evidence-supported one.

### 4. INSTRUMENT
Add minimal instrumentation to confirm or refute the hypothesis. For Rust:
- Add `dbg!(value)` to the specific line — remove after diagnosis.
- Run `cargo test <test> -- --nocapture` to see output.

For TypeScript:
- Add `console.log(JSON.stringify(value, null, 2))` at the suspect line — remove after.

Run and observe. Does the evidence confirm or refute the hypothesis?

If refuted: return to HYPOTHESIZE with the new evidence. Do NOT jump to trying fixes.

### 5. FIX
Apply the minimal fix consistent with the confirmed hypothesis.

**AEGIS invariants to check before any fix:**
- Rust: `to_be_bytes()` not `to_le_bytes()` in all hash inputs
- Rust: `BTreeMap` not `HashMap` (determinism requirement)
- Rust: `saturating_add`/`saturating_mul` — no silent overflow
- TypeScript: `canonicalizeJCS` not `JSON.stringify` for integrity
- TypeScript: `.js` suffix on all relative imports
- TypeScript: `deepFreeze` on all state objects

After fix, run the full module test suite (not just the minimized case):
```bash
cargo test <module_name>       # or
npm run test -- <test_file>
```

## Reporting Format

```
DIAGNOSE REPORT:
  Reproduced: YES / NO (if NO, stop)
  Minimized:  <test_name> — <assertion>
  Hypothesis: <confirmed mechanism>
  Fix:        <exact change made>
  Verified:   <test result after fix>
  Invariant check: PASS / VIOLATION (<which invariant>)
```
