---
name: mythos-bootstrap
description: >
  Deterministic 6-stage execution pipeline with INDEX.md as ground truth and
  SYSTEM STATE VECTOR as required session state. Invoke when starting any
  non-trivial task, when the pipeline stage must be declared before acting,
  or when another agent invokes /mythos-bootstrap to enforce stage transitions.
  Also auto-activates on: "orchestrate", "planner stage", "validator gate",
  "system state vector", "INDEX citation", "reconciliation mode".
---

# MYTHOS BOOTSTRAP — Execution Pipeline

**Metacognitive Layer: L5 (Executive) + L6 (Metacognition) + L7 (Self-model)**
**Epistemic Tier: T1**

The MYTHOS BOOTSTRAP is a deterministic agent execution environment with enforced
state convergence, INDEX-anchored authority, and CI-gated stage transitions. It
extends (does not replace) the AEGIS constitutional framework.

Stage mapping to RALPH loop:
- ORCHESTRATE = READ (route only)
- PLAN = ASSESS (cite INDEX, define scope)
- VALIDATE = T0-check (CI gate)
- BUILD = LOCK (implement approved plan)
- REVIEW = PROPAGATE (Gate 8 + verdict)
- FINALIZE = HARMONIZE (commit state)

---

## SYSTEM STATE VECTOR (mandatory every cycle)

Emit this JSON at the start of every execution cycle:

```json
{
  "execution_phase": "ORCHESTRATE|PLAN|VALIDATE|BUILD|REVIEW|FINALIZE",
  "index_snapshot": "<sha256 of INDEX.md>",
  "active_files": ["path/relative/to/repo/root"],
  "forbidden_actions": ["list of prohibited ops for this cycle"],
  "validity": "UNVERIFIED|VERIFIED|REJECTED"
}
```

No work proceeds without this structure declared. If any field is missing → STOP,
emit the vector, then resume.

Compute `index_snapshot`:
```bash
node -e "const c=require('crypto'),f=require('fs'); console.log(c.createHash('sha256').update(f.readFileSync('INDEX.md')).digest('hex'))"
```

---

## Stage Definitions

### ORCHESTRATOR
- Routes task only
- States which stage will handle it and why
- No implementation reasoning
- No architecture decisions
- Output: `{ routed_to: Stage, task_summary: string }`

### PLANNER
- Reads INDEX.md (must read, not recall)
- Cites ≥1 INDEX path in output
- Defines exact files to be modified
- Defines plan steps in sequence
- No code generation
- Output: `{ index_citations: string[], files_affected: string[], plan_steps: string[] }`
- HARD GATE: any file in `files_affected` not in INDEX → RECONCILIATION MODE

### VALIDATOR (CI GATE)
- Checks: INDEX citation present, files in INDEX graph, no forbidden file in scope
- Checks: active stage transition is legal (see transition table)
- No modifications allowed
- Output: `{ valid: boolean, fail_reasons: string[] }`
- If `valid: false` → RECONCILIATION MODE immediately

### BUILDER
- Applies ONLY the PLANNER-approved plan
- No reinterpretation
- No scope expansion beyond `files_affected`
- No new abstractions not in plan
- Output: actual file changes

### REVIEWER
- Runs Gate 8: `npm run test && npm run typecheck && npm run build`
- Checks builder output covers all `plan_steps`
- Pass/fail only — cannot modify output
- Output: `{ verdict: 'PASS'|'FAIL', unmet_steps: string[] }`
- If `FAIL` → RECONCILIATION MODE

### FINALIZER
- Confirms `verdict: 'PASS'`
- Runs `node scripts/verify-hashes.mjs` — must exit 0
- Commits SYSTEM STATE VECTOR update
- Git push
- Emits final state snapshot

---

## Stage Transition Table (strict DAG)

```
ORCHESTRATE → PLAN
PLAN        → VALIDATE
VALIDATE    → BUILD     (only if valid: true)
BUILD       → REVIEW
REVIEW      → FINALIZE  (only if verdict: PASS)
```

Any other transition = HARD FAIL. Stop, report, wait for operator.

---

## RECONCILIATION MODE

Triggered by: VALIDATOR `valid: false`, REVIEWER `verdict: FAIL`, or detected
inconsistency between plan and INDEX.

Steps (in order, no deviation):
1. Compare all stage outputs — identify the discrepancy
2. Isolate INDEX-backed facts — discard inferred or assumed content
3. Remove files_affected entries not in INDEX
4. Regenerate SYSTEM STATE VECTOR with `validity: REJECTED`
5. Restart pipeline from PLAN stage (max 2 retries)
6. No code execution in RECONCILIATION MODE

If reconciliation fails after 2 retries → HALT, report to operator with diagnosis.

---

## Cross-Project Context

The SYSTEM STATE VECTOR is the AEGIS-layer analogue of state.json in Sovereign AGI OS.

| AEGIS | Sovereign AGI OS |
|-------|-----------------|
| `AdaptivePower(T) ≤ ReplayVerifiability(T)` | `HD = |claimed − actual|` |
| Hash chain integrity | Biological state coupling |
| corruption_count = 0 | stress in hormetic zone (0.3–0.6) |
| certifyMetacognitiveLoop() | Context_HD calibration |

Both measure divergence from ground truth. AEGIS does it cryptographically.
Sovereign AGI OS does it biologically. The MYTHOS BOOTSTRAP bridges both.

---

## Non-Negotiable Invariants

- No agent overlap: no stage performs another stage's function
- No implicit architecture: every decision cited in INDEX or rejected
- No execution without INDEX citation
- No state without SYSTEM STATE VECTOR
- No divergence from stage pipeline
- No assumptions outside indexed sources

---

## Usage

The MYTHOS pipeline can be run interactively (declare stage + SSV in conversation)
or programmatically via the Claude API pipeline:

```bash
cd sovereign-omega-v2
npx tsx scripts/mythos-pipeline.ts "task description"
```

Exits 0 = FINALIZED with valid SYSTEM STATE VECTOR.
Exits 1 = RECONCILIATION exhausted — review diagnosis output.
