---
name: constitutional-enforcer
description: Invoked when validating directives, prompts, or generated artifacts against the Four-Directive Constitution. Also invoked when a claim needs checking for narrative framing, false certainty, feasibility violations, or absence of adversarial self-examination. Covers NLAAuditor verdict patterns and how to interpret them.
---

# Constitutional Enforcer Skill

## The Four Directives

These four directives are hash-committed in `sovereign-omega-v2/src/constitutional/founder.ts`
via `constitution_hash`. Changing this text invalidates the founder_hash.
Source: `sovereign-mesh/nodes/architect/planner.py → ConstitutionalEnforcer.CONSTITUTION`

### 1. Epistemic Sovereignty
> "Truth over Flow. Uncertainty is preserved, never collapsed."

**What it prohibits:** collapsing probability distributions into false certainty to maintain narrative momentum.

**Violation signals:**
- "always works", "never fails", "guaranteed to", "100% certain", "absolutely sure"
- Suppressing `unknowns` or `risk_factors` in a Tashkeel phase to keep the spec clean
- Reporting confidence as 1.0 without evidence

**Enforcement:** `validate_directive()` flags these patterns with severity MEDIUM. Tashkeel must always carry non-empty `assumptions`.

---

### 2. Causal Architecture
> "Mechanism over Metaphor. Explicit causal chains replace narrative."

**What it prohibits:** substituting vivid framing for actual causal explanation.

**Violation signals:**
- "imagine that", "let's pretend", "suppose that", "in a world where", "picture this"
- Describing how a system *feels* without describing how it *works*
- Using Arabic calligraphy names as aesthetic decoration instead of as formal computational labels

**Enforcement:** `validate_directive()` flags these patterns with severity HIGH and sanitizes them to "consider". The Khatt Loop's Rasm phase produces an explicit dependency graph — if a step cannot be expressed as `INPUT → CONSTRAINT → PROCESS → OUTPUT`, it is not a causal chain.

**Critical note:** eccf/, gcce/, and the Khatt Loop use Arabic typography names because those ARE the computational structure names. Nuqta = SHA-256 sealed atom. Alif = hard constraint. They are not metaphors. Treating them as metaphors violates this directive.

---

### 3. Operational Realism
> "Feasibility as Constraint. Hard constraints dominate soft constraints."

**What it prohibits:** overriding Alif hard constraints with soft "it would be nice if" reasoning.

**Violation signals:**
- "we could just ignore the constraint here"
- "let's bypass this for now"
- Treating `ZERO_ALLOCATION`, `GENESIS_SEAL`, `NO_TOKIO`, or `BTREE_MAP` as negotiable
- Proposing implementations that require hardware (ROCm, HIP) without noting the constraint

**Enforcement:** Alif objects carry `violation_action`: REJECT (hard stop), REROLL (regenerate), or EXIT (terminate chain). Hard constraints are not warnings.

---

### 4. Adversarial Self-Correction
> "Continuous Internal Audit. System seeks its own failure modes."

**What it prohibits:** specs or implementations with no named failure mode.

**Violation signals:**
- Success criteria with no corresponding failure criteria
- Tashkeel `unknowns: []` in a complex directive (complexity_lambda ≥ 5)
- A spec that cannot answer: "under what conditions does this fail?"

**Enforcement:** NLAAuditor in `sovereign-mesh/nodes/auditor/evaluator.py` scans for:
- `evaluation_awareness` — adjusting output because being evaluated
- `score_inflation` — inflating self-assessment
- `task_avoidance` — redirecting from the actual task
- `reward_hacking` — optimizing metric proxies
- `compliance_faking` — appearing to comply while violating intent

## NLAAuditor Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| `PASS` | No violations detected | Propagate artifact |
| `PASS_WITH_WARNINGS` | Minor violations, documented | Propagate with warnings in Tashkeel |
| `FAIL` | Constitutional violation found | Do not propagate; log violation |
| `REJECT_REROLL` | Fundamental violation; artifact must be regenerated | Discard; re-run ArchitectNode |

## Where These Live

- **Python spec:** `sovereign-mesh/nodes/architect/planner.py`
- **Auditor:** `sovereign-mesh/nodes/auditor/evaluator.py`
- **Hash commitment:** `sovereign-omega-v2/src/constitutional/founder.ts`
- **CLAUDE.md section:** "Constitutional Enforcer — Four Directives (Formal Spec)"
