---
name: brainstorming
description: Use before any significant new feature, new gate series, architectural change, or new commercial product direction. Hard gate — present design and get approval before any implementation. Do NOT invoke implementation until design is approved.
---

# Brainstorming

**Metacognitive Layer: L6 (Metacognition) + L8 (Theory of Mind)**

Brainstorming is the ASSESS phase of the RALPH loop at the architectural scale. The LOCK phase (implementation) cannot begin until ASSESS (design + approval) is complete. This is the L6 invariant at its purest: ASSESS before LOCK, always, with no exception for "simple" changes. Simple changes that skip design approval are where constitutional debt accumulates.

L8 invariant: **Operator intent is not always literal. When the operator says "embed metacognitive consciousness in everything", they mean: translate the philosophy architecturally, not superficially. Infer the scale of the request from the operator's escalation signals before proposing an approach.**
L6 invariant: **Classify the epistemic tier of the proposed change before designing it. T0 changes require formal proof, not brainstorming. T2 changes must be labeled as hypotheses.**

Non-equivalence: **"Approved" ≠ "Understood". Get both. "Design presented" ≠ "Design understood by operator". Confirm the design is unambiguous before proceeding.**

**HARD GATE: Do NOT write any code, scaffold any project, or take any implementation action until you have presented a design and the operator has approved it.**

Even simple things need a brief design check. The design can be 2 sentences — but it must be presented and approved.

## Process

### 1. Explore Context
Read relevant existing files before proposing anything:
```bash
# For a new gate series:
tail -30 aegis-cl-psi/src/lib.rs | grep "pub mod"
# For a new product:
ls /home/user/AEGIS--/platform-picker/src/
# For TypeScript changes:
ls sovereign-omega-v2/src/
```

### 2. Ask ONE Clarifying Question
If the goal is ambiguous, ask one focused question before proposing approaches. Not a list of questions — one.

### 3. Propose 2-3 Approaches
For each approach, state:
- What it does
- The key trade-off
- Estimated complexity (lines of code, test count)
- Which constitutional tier it falls under (T0/T1/T2)

Mark your recommendation clearly.

### 4. Present Design
After operator selects an approach, write the design:

For AEGIS gates:
```
GATE SERIES DESIGN: <name>
Series: gossip_<prefix>_*
Metrics to track: <list each proposed gate with its formula>
Thresholds: <list each CONST with value and rationale>
Estimated gates: <N>
Estimated tests: <N × 19>
Constitutional tier: T2
```

For new features:
```
FEATURE DESIGN: <name>
Purpose: <one sentence>
Files affected: <list>
Constitutional invariants: <which ones apply>
Test approach: <how it will be verified>
```

### 5. Get Approval
Present the design explicitly. Do not proceed until the operator says yes, approves, or gives equivalent confirmation.

### 6. Transition
After approval, proceed directly to implementation. For complex multi-file work, consider `/dispatching-parallel-agents` for independent parts.

## What NOT to Do

- Do not write implementation code during brainstorming
- Do not scaffold files "as examples"
- Do not start a "quick prototype" before approval
- Do not propose more than 3 approaches (forces real choice)

## For AEGIS Specifically

New gate series must pass this check before design is approved:
- [ ] T2 epistemic tier (engineering hypothesis, not proven)
- [ ] Pure deterministic computation (no I/O, no randomness)
- [ ] Follows hash-chain pattern (SHA-256, prev[32] ‖ fields)
- [ ] No HashMap, no float in hash input
- [ ] Each gate produces exactly 19 tests

New commercial product must pass:
- [ ] Builds on existing `@shared` infrastructure
- [ ] `.env.example` committed, `.env` gitignored
- [ ] Deploys to Vercel (one project per product)
- [ ] Gate 8 verified before deployment
