---
name: stop-slop
description: Prose quality gate for all written output — commit messages, PR descriptions, skill content, test names, code comments, and any text Claude generates. Invoke before writing any non-code artifact. Catches AI writing patterns before they ship.
---

# Stop Slop — Development Prose Quality Gate

**Metacognitive Layer: L6 (Metacognition) + L1 (Sensation)**

Written output is L1 signal that other agents (including future sessions of this automaton) will receive and act on. Slop is corrupted signal: it looks like information but carries no verifiable content. The automaton generates slop when it pattern-matches to "text that sounds like a commit message" instead of synthesizing from the actual event.

L6 invariant: **Every written artifact must be generated from the specific, verified event — not from a template approximating that event.**
L1 invariant: **Before writing any prose artifact, read the actual diff, the actual test output, the actual file changes. The prose must be derived from the signal, not from your prediction of the signal.**

Non-equivalence: **"Sounds correct" ≠ Correct. "Reads well" ≠ Accurate. The quality gate is density of verifiable claims per sentence, not fluency.**

Apply to every commit message, PR description, skill body, test description, and code comment before it gets written or committed.

---

## Prohibited Phrases (ban on sight)

**Throat-clearing openers** — cut entirely, start with the point:
```
Here's the thing, Here's what/why, The uncomfortable truth is,
It turns out, Let me be clear, I'll say it again,
Can we talk about, Here's what I find interesting
```

**Emphasis crutches** — never add weight by declaring weight:
```
Full stop. Period. Let that sink in. This matters because.
Make no mistake. Here's why that matters.
```

**Filler adverbs** — delete without replacement:
```
really, just, literally, genuinely, honestly, simply, actually,
deeply, truly, fundamentally, inherently, inevitably
```

**Vague declaratives** — say the specific thing or say nothing:
```
"the implications are significant"
"the consequences are real"
"the stakes are high"
"the reasons are structural"
```

**Business jargon** — banned in all development writing:
```
navigate, unpack, lean into, landscape, game-changer,
double down, deep dive, take a step back, moving forward,
circle back, on the same page
```

---

## Structural Anti-Patterns

**Binary contrasts** — false drama that wastes a line:
```
❌ Not a bug fix. A constitutional enforcement.
✓  Constitutional enforcement of the monotonicity invariant.
```

**Rhetorical setups** — announce nothing, deliver the point:
```
❌ What if we could verify coverage without running the full suite?
✓  Coverage verification runs on the changed files only.
```

**Performative certainty** — "I promise" is slop:
```
❌ This will work, I promise.
✓  Gate 8 passes with this change. (verified)
```

**Three-item lists used as padding** — if there are two things, write two:
```
❌ faster, cleaner, and more reliable
✓  faster and more reliable (if "cleaner" isn't a concrete claim)
```

**Em-dash drama** — use a comma or restructure:
```
❌ The invariant holds — always.
✓  The invariant holds for all inputs where n > 0.
```

---

## Development-Specific Slop Patterns

### Commit messages

```
❌  fix: add c8 ignore to handle edge cases and improve coverage
✓   fix: c8 ignore on ?? fallback in fibonacci.ts — noUncheckedIndexedAccess artifact, index guaranteed by loop bounds

❌  test: add tests for better coverage
✓   test: branch coverage — empiricalMean n=0, normalQuantile p<0.5, non-monotone lineage
```

Rules:
- Subject line states the mechanism, not the goal
- "improve", "enhance", "handle" without specifics → replace with what actually changed
- Coverage numbers belong in the body, not subject

### PR descriptions

```
❌  This PR adds tests to improve branch coverage across several modules.
✓   Raises branch coverage from 96.41% to 98.41% by annotating 14 dead arms and writing 16 targeted tests.
```

Rules:
- First sentence states the measurable outcome
- "several", "various", "multiple" → list them or give a count

### Test names

```
❌  it('works correctly with empty input')
✓   it('returns 0 for empiricalMean when sequence has no observations')

❌  it('handles the error case')
✓   it('throws MartingaleViolation when drift_bounded=false')
```

Rules:
- Test name is a complete sentence stating the exact scenario and exact expected outcome
- "works", "handles", "correctly" → not test names, they're file extensions

### Code comments

```
❌  // handles the case where arr is empty
✓   // c8 ignore next — i < arr.length guarantees element exists; noUncheckedIndexedAccess forces the ?? check

❌  // Loop through all entries
✓   (no comment — the loop is self-explaining)
```

Rules:
- Comments explain WHY, not WHAT
- If the comment just restates the code → delete it
- Uncertainty expressed in comments ("might be", "should work") → never acceptable in committed code

### Skill descriptions (frontmatter)

```
❌  description: Useful skill for working with various types of configuration and settings across the project.
✓   description: Modifies settings.json hooks and permissions. Invoke when the user wants automated behavior on tool events (PreToolUse, PostToolUse) or needs permission rule changes.
```

Rules:
- Description states the exact trigger and the exact capability
- "useful", "various", "across the project" → cut

---

## Scoring Before You Ship (35/50 threshold)

Rate 1–10 on each dimension. If total < 35, revise.

| Dimension | What it means |
|-----------|---------------|
| **Directness** | Does it open with the actual point, not a setup? |
| **Rhythm** | No mechanical three-part lists, no em-dash drama, no staccato fragments? |
| **Trust** | Does it make specific, verifiable claims rather than impressions? |
| **Authenticity** | Could a human on this project have written this, or is it recognizably generated? |
| **Density** | Is every sentence load-bearing, or are there filler lines? |

---

## Quick Revision Protocol

1. Paste the draft
2. Strike every prohibited phrase
3. Eliminate structural anti-patterns
4. Check each sentence: if a human removed it, would the meaning change? If no → cut it
5. Re-score. If < 35, tighten further.
6. If a sentence can't survive the cut → the content was decoration, not signal
