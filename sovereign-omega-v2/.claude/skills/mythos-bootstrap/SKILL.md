---
name: mythos-bootstrap
description: >
  Deterministic 6-stage execution pipeline with complete repository cognition,
  INDEX.md authority context, and SYSTEM STATE VECTOR as required session state.
  Invoke when starting any non-trivial task, when the pipeline stage must be
  declared before acting, or when another agent invokes /mythos-bootstrap to
  enforce stage transitions. Also auto-activates on: "orchestrate", "planner
  stage", "validator gate", "system state vector", "INDEX citation",
  "repository cognition", "reconciliation mode".
---

# MYTHOS BOOTSTRAP — Execution Pipeline

**Metacognitive Layer: L5 (Executive) + L6 (Metacognition) + L7 (Self-model)**
**Epistemic Tier: T1**

The MYTHOS BOOTSTRAP is a deterministic agent execution environment with enforced
state convergence, content-addressed repository cognition, INDEX-anchored
authority context, and CI-gated stage transitions. It extends (does not replace)
the AEGIS constitutional framework.

Two surfaces are intentionally distinct:

- `.aegis/repo-cognition-v1.json` = complete content/existence census of the Git source corpus.
- `INDEX.md` = curated authority/policy subset; absence from INDEX does **not** prove a file is absent.

Stage mapping to RALPH loop:
- ORCHESTRATE = READ (route only)
- PLAN = ASSESS (read repository cognition + cite INDEX authority context)
- VALIDATE = T0/T1 deterministic scope check
- BUILD = LOCK (implement approved plan)
- REVIEW = PROPAGATE (Gate 8 + verdict)
- FINALIZE = HARMONIZE (commit state)

---

## REPOSITORY COGNITION GATE (mandatory before every cycle)

Run from repository root:

```bash
python3 scripts/repo_cognition.py --check --receipt
```

Required invariant:

```text
coverage = 1.0
indexed_file_count = eligible_file_count
recorded corpus_root = live Git HEAD source corpus root
```

If any condition fails, emit:

```text
REPOSITORY_KNOWLEDGE_INCOMPLETE
```

and halt before provider/model execution.

A hash/corpus receipt proves content identity and addressability only. It does
not prove proposition truth, semantic correctness, runtime wiring, or mutation
authority.

---

## SYSTEM STATE VECTOR (mandatory every cycle)

Emit this JSON at the start of every execution cycle:

```json
{
  "execution_phase": "ORCHESTRATE|PLAN|VALIDATE|BUILD|REVIEW|FINALIZE",
  "index_snapshot": "<sha256 of INDEX.md>",
  "repository_corpus_root": "<sha256>",
  "repository_coverage": 1.0,
  "active_files": ["path/relative/to/repo/root"],
  "forbidden_actions": ["list of prohibited ops for this cycle"],
  "validity": "UNVERIFIED|VERIFIED|REJECTED",
  "reconciliation_retries": 0
}
```

No work proceeds without a verified repository corpus and this structure.

Compute `index_snapshot`:

```bash
node -e "const c=require('crypto'),f=require('fs'); console.log(c.createHash('sha256').update(f.readFileSync('INDEX.md')).digest('hex'))"
```

---

## Stage Definitions

### ORCHESTRATOR
- Routes task only.
- States which stage will handle it and why.
- No implementation reasoning.
- No architecture decisions.
- Output: `{ routed_to: Stage, task_summary: string }`.

### PLANNER
- Reads the verified repository cognition catalog; do not recall file existence from memory.
- Reads INDEX.md as authority/policy context; do not treat it as a complete file list.
- Cites ≥1 relevant INDEX path in output.
- Every `files_affected` path must exist in the verified repository corpus.
- Defines plan steps in sequence.
- No code generation.
- Output: `{ index_citations: string[], files_affected: string[], plan_steps: string[] }`.
- HARD GATE: path absent from verified corpus → RECONCILIATION MODE.
- A path present in corpus but absent from INDEX is not automatically rejected; normal planner/authority rules apply.

### VALIDATOR (DETERMINISTIC CI GATE)
- Model/provider output does not decide whether a repository path exists.
- Checks repository coverage == 1.0.
- Checks all `files_affected` paths against the verified corpus.
- Checks INDEX citations are actually present in INDEX.md.
- Checks plan is non-empty and contains no duplicate affected paths.
- Checks active stage transition is legal.
- No modifications allowed.
- Output: `{ valid: boolean, fail_reasons: string[] }`.
- If `valid: false` → RECONCILIATION MODE immediately.

### BUILDER
- Applies ONLY the PLANNER-approved plan.
- No reinterpretation.
- No scope expansion beyond `files_affected`.
- No new abstractions not in plan.
- Output: actual file changes.

### REVIEWER
- Runs Gate 8: `npm run test && npm run typecheck && npm run build`.
- Checks builder output covers all `plan_steps`.
- Pass/fail only — cannot modify output.
- Output: `{ verdict: 'PASS'|'FAIL', unmet_steps: string[] }`.
- If `FAIL` → RECONCILIATION MODE.

### FINALIZER
- Confirms `verdict: 'PASS'`.
- Runs `node scripts/verify-hashes.mjs` — must exit 0.
- Re-verifies repository cognition.
- Repository corpus root, coverage, active file set, index snapshot, and reconciliation count come from deterministic runtime state, not model output.
- Commits SYSTEM STATE VECTOR update.
- Git push.
- Emits final state snapshot.

---

## Stage Transition Table (strict DAG)

```text
ORCHESTRATE → PLAN
PLAN        → VALIDATE
VALIDATE    → BUILD     (only if valid: true)
BUILD       → REVIEW
REVIEW      → FINALIZE  (only if verdict: PASS)
```

Any other transition = HARD FAIL.

---

## RECONCILIATION MODE

Triggered by: VALIDATOR `valid: false`, REVIEWER `verdict: FAIL`, repository
cognition mismatch, or detected inconsistency between plan and authority state.

Steps:
1. Re-run `scripts/repo_cognition.py --check --receipt`.
2. Compare all stage outputs and identify the discrepancy.
3. Preserve corpus-backed existence facts; discard inferred or assumed file existence.
4. Preserve INDEX-backed authority facts separately from corpus facts.
5. Remove `files_affected` paths absent from the verified corpus.
6. Regenerate SYSTEM STATE VECTOR with `validity: REJECTED`.
7. Restart pipeline from PLAN stage (max 2 retries).
8. No code execution in RECONCILIATION MODE.

If reconciliation fails after 2 retries → HALT with diagnosis.

---

## Non-Negotiable Invariants

- Repository cognition and mutation authority are separate evidence domains.
- No global repository claim when `repository_coverage < 1.0`.
- No claim that an unlisted INDEX path does not exist unless the verified corpus also lacks it.
- No agent overlap: no stage performs another stage's function.
- No execution without relevant authority context.
- No state without SYSTEM STATE VECTOR.
- No divergence from stage pipeline.
- No model/provider authority over deterministic repository identity fields.

---

## Usage

The pipeline can be run interactively or programmatically:

```bash
cd sovereign-omega-v2
npx tsx scripts/mythos-pipeline.ts "task description"
```

Exits 0 = FINALIZED with valid SYSTEM STATE VECTOR.
Exits 1 = repository cognition failure, reconciliation exhaustion, or another hard gate.
