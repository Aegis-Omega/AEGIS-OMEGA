---
name: branch-coverage
description: Systematic branch coverage analysis workflow. Invoke at the start of any coverage improvement session. Produces a prioritized action plan, classifies every uncovered arm, and enforces immediate action — never defer dead-code annotations or test writes to a later pass.
---

# Branch Coverage Analysis — Systematic Workflow

**Metacognitive Layer: L2 (Perception) + L5 (Executive Function)**

Coverage analysis is the L2 function at the code topology scale — perceiving which branches exist and which have been verified. The cardinal non-equivalence for this skill:

```
Coverage ≠ Correctness
100% branch coverage ≠ correct behavior in all branches
An annotated dead branch ≠ a tested live branch
```

L2 invariant: **Read the full coverage report. Don't act on coverage numbers alone — read the specific uncovered arms and classify each one (dead code, untested live code, structurally unreachable). A number is not a signal; the classified list is.**
L5 invariant: **Every uncovered arm is an open RALPH cycle — either close it (write the test or add the annotation) or explicitly defer it with a classified rationale. Leaving it open is constitutional debt that compounds.**

**INVOKE THIS FIRST.** Before any file is touched, complete Phase 1. No exceptions.

---

## Phase 1 — Baseline Snapshot (run before touching any file)

```bash
cd sovereign-omega-v2
npm run test -- --coverage 2>&1 | grep -E "Branches|All files"
```

Record: `BASELINE: XX.XX% (covered/total)`

Then get per-file branch data:
```bash
npm run test -- --coverage 2>&1 | grep -v "100 |" | grep -v "^$" | grep "|" | head -60
```

Sort by branch miss count descending. Identify top-10 files with most missed branches.

**Do not skip this step.** A coverage baseline without per-file data is useless for prioritization.

---

## Phase 2 — Classify Every Uncovered Branch Before Writing Anything

For each missed branch, apply the decision tree **immediately**. Do not collect a list and defer action — classify and act inline.

### Decision Tree

```
Uncovered branch at line L, arm A
         │
         ▼
Is it structurally impossible to reach?
(e.g., noUncheckedIndexedAccess ?? fallback, dead sort comparator arm,
 function only called with validated inputs, private guard on singleton,
 enum arm not reachable by any valid caller)
         │
    YES  │   NO
         │    │
         ▼    ▼
  → DEAD ARM  → TESTABLE ARM
    ACT NOW     ACT NOW
```

### DEAD ARM — Act Immediately

Add `/* c8 ignore next */` on the line BEFORE the dead arm. Do it NOW — do not note it in a list and continue.

**Pattern selection:**
- One-liner dead arm (`?? 0`, `?? ''`, dead else on one line): `/* c8 ignore next */` on the preceding line
- If statement with dead false arm spanning 2+ lines: `/* c8 ignore next */` before the `if` (suppresses both branches)
- Ternary with dead false arm on same line: `/* c8 ignore next */` on the line before the entire ternary

**Comment format** (mandatory — explains WHY, not WHAT):
```typescript
/* c8 ignore next -- <1-line explanation of WHY this arm cannot be reached> */
```

Do NOT write multi-line explanations. One clause is enough.

### TESTABLE ARM — Act Immediately

Write the test immediately. Do not defer. The test must:
1. Target the specific arm (arm 0 = true/first path, arm 1 = false/second path)
2. Assert the exact output of that arm, not just "it doesn't throw"
3. Go in the appropriate test file (misc-coverage-N.test.ts if no existing home)

**Before writing the test:**
- Read the source at the exact line number to understand what the arm does
- Check the public API surface — can the arm be reached from a public function?
- If only reachable via private internals, it may actually be dead (re-classify)

---

## Phase 3 — Batch Protocol

Group by module for efficiency. Do NOT mix action types within a batch:

**Batch A — c8 ignores only** (fast, no tests needed)
- All dead arms across all files
- Each file: read source, add ignores, move on
- No Gate 8 run between files — save it for end of batch

**Batch B — Tests only** (slower, needs verification)
- All testable arms, grouped by source module
- Write tests for one module → run that test file → confirm arm covered → move to next
- Only run full Gate 8 at end of batch

**Batch C — Combined** (when a source change is needed to expose testability)
- Source change + corresponding test, as a unit
- Run full Gate 8 before starting the next combined unit

---

## Phase 4 — Verification Gate (mandatory before every commit)

```bash
cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build
```

Gate 8 must exit 0. If tests fail: fix, re-run. Do not commit with a red gate.

After Gate 8, re-run coverage and compare:
```bash
npm run test -- --coverage 2>&1 | grep "Branches"
```

Report: `BEFORE: XX.XX% → AFTER: XX.XX% (+X.XX pp, -N misses)`

---

## Phase 5 — Commit Message Protocol

Format: `test: branch coverage batch N — <comma-separated module names>`

Body must list:
- Source files annotated with c8 ignore (and WHY for each)
- Test additions (describe test → what arm it hits)
- Before/after coverage numbers

---

## Common Dead Arm Patterns in This Codebase

| Pattern | Root Cause | Fix |
|---------|-----------|-----|
| `arr[i] ?? fallback` inside bounds loop | `noUncheckedIndexedAccess` TS strict mode | `/* c8 ignore next */` |
| `sort((a, b) => { ...; return 0 })` on unique-keyed collections | Keys are unique; equality impossible | Simplify sort to remove `return 0` OR ignore |
| `if (err instanceof SpecificError)` when only that type is thrown | Only one error class in throw path | `/* c8 ignore next */` before the if |
| `?? 0` on `.pop()` result after non-empty check | Non-empty guard ensures pop is defined | `/* c8 ignore next */` |
| Guard in private fn only called with validated args | Caller validates; guard is double-safety | `/* c8 ignore next */` |
| `if (typeof x === 'object')` after exhaustive non-object checks | All non-object types already handled above | `/* c8 ignore next */` |

---

## Anti-Patterns — Never Do These

- **Note dead code and continue** — acts immediately or not at all
- **Write "I'll add c8 ignore for the dead arms in a cleanup pass"** — no deferred passes; classify and act inline
- **Guess at whether an arm is dead** — read the source and the call sites; confirm before acting
- **Use `/* c8 ignore next */` without a comment** — always explain WHY
- **Run Gate 8 between every single file edit** — batch ignores in Batch A, run Gate 8 once at end
- **Add c8 ignore to lines that ARE testable** — only annotate truly unreachable arms

---

## Session Report Format

```
BRANCH COVERAGE SESSION REPORT
═══════════════════════════════
Baseline:   XX.XX% (covered/total)
Final:      XX.XX% (covered/total)
Delta:      +X.XX pp (-N branch misses)

Batch A (dead arms annotated):
  src/foo.ts L42: noUncheckedIndexedAccess ?? fallback
  src/bar.ts L88: sort equality arm (keys are unique UUIDs)
  ...

Batch B (tests written):
  test/unit/misc-coverage-N.test.ts:
    - assertFoo with invalid input → arm 1 (false branch) covered
    - ...

Gate 8: PASS (tests: N passed, typecheck: ok, build: ok)
```
