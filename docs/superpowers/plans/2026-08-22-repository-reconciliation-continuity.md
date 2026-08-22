# Repository Reconciliation and Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing repository-universe audit into a fail-closed continuity system that classifies every reachable work lineage, prevents duplicate branch creation, reconciles the active UCI/Company Brain spine, preserves side capabilities, and only then enables proven cleanup plus cross-provider connector access.

**Architecture:** Reuse `scripts/repo-universe.sh`, the existing UCI work/lease primitives, and the current provider-neutral MCP instead of creating parallel systems. Add a deterministic reconciliation layer above them: repository census -> WorkID lineage graph -> classification/decision ledger -> provider continuation envelope. Canonical `main` remains admitted runtime state; all refs/PRs/session artifacts are knowledge evidence only until explicitly reconciled.

**Tech Stack:** Python 3.12 stdlib, Bash, Git, GitHub Actions, existing AEGIS Python/TypeScript governance surfaces, JSON/JSONL, existing provider MCP.

**Spec:** `docs/superpowers/specs/2026-08-21-repository-reconciliation-continuity-design.md`

## Global Constraints

- No new feature branch when a compatible active/recoverable lineage exists.
- Do not merge merely because GitHub reports `mergeable=true`.
- Do not delete any ref without mechanical containment proof and recorded tip SHA.
- `main` is admitted state, not the complete knowledge universe.
- `UNKNOWN_FAIL_CLOSED` may never authorize merge, deletion, or absence claims.
- Provider/model output remains evidence only, never authority.
- Preserve DecisionReceipt / ExecutionReceipt / EffectReceipt / Admission separation.
- D3 remains operator-approval-bound; D4 remains denied absent admitted policy.
- Reuse existing repository and UCI primitives before adding new ones.
- Every canonical/destructive mutation must have a replayable reconciliation decision record.

---

### Task 1: Complete repository + PR census

**Files:**
- Reuse: `scripts/repo-universe.sh`
- Create: `scripts/reconcile-repository-universe.py`
- Create: `scripts/tests/test-reconcile-repository-universe.py`
- Modify: `.github/workflows/repo-universe-audit.yml`
- Runtime output: `.aegis/runtime/repository-universe.v1.json`

**Interfaces:**
- Consumes: `AEGIS_REPO_UNIVERSE_V1` JSON from `scripts/repo-universe.sh` plus a JSON array of GitHub PR metadata.
- Produces: `AEGIS_RECONCILIATION_UNIVERSE_V1` with exact main SHA, complete-history flag, branch entries, PR entries, source completeness flags, and deterministic digest.

- [ ] **Step 1: Write failing reconciliation tests**

Create fixtures that require: canonical main distinct from knowledge universe; open/closed PR base/head preservation; incomplete PR input marks `discovery_complete=false`; duplicate branch/PR refs are coalesced but not erased; output order and digest are deterministic.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q scripts/tests/test-reconcile-repository-universe.py`
Expected: FAIL because `scripts/reconcile-repository-universe.py` is absent.

- [ ] **Step 3: Implement minimal reconciler**

Implement pure functions `load_universe()`, `normalize_prs()`, `build_reconciliation_universe()`, `validate_document()`, and CLI `--repo-universe --prs --out` using stdlib only. The reconciler must never infer PR completeness unless the input explicitly says it was complete.

- [ ] **Step 4: Run GREEN + inherited census fixture**

Run:
`python -m pytest -q scripts/tests/test-reconcile-repository-universe.py`
`bash scripts/tests/test-repo-universe.sh`
Expected: PASS.

- [ ] **Step 5: Extend hosted audit**

In `repo-universe-audit.yml`, fetch complete history, export all PR metadata via authenticated GitHub API/`gh`, run the reconciler, print summary only, upload both raw census and reconciliation-universe JSON as evidence artifacts.

- [ ] **Step 6: Commit**

Commit message: `feat(reconciliation): build complete repository and PR census`

---

### Task 2: Build stable WorkID lineage graph

**Files:**
- Create: `scripts/build-work-lineage.py`
- Create: `scripts/tests/test-build-work-lineage.py`
- Create: `.aegis/reconciliation/spines.v1.json`
- Runtime output: `.aegis/runtime/work-lineage.v1.json`

**Interfaces:**
- Consumes: `AEGIS_RECONCILIATION_UNIVERSE_V1`.
- Produces: `AEGIS_WORK_LINEAGE_V1` entries containing `work_id`, `current_ref`, `current_head`, `pr_number`, `parent_work_ids`, `lineage_root`, `objective_digest`, `verification_state`, `admission_state`, `classification`, and provenance.

- [ ] **Step 1: Write failing lineage tests**

Tests must prove: WorkID is independent of mutable branch name; PR base/head relations become parent edges; the operator-approved spine `275 -> 276 -> 277 -> 278 -> 279 -> 280 -> 282 -> 283 -> 284 -> 285 -> 290 -> 291` is represented explicitly; #268/#270/#272/#273 are side history already reconciled by #276 rather than a competing active spine; unknown nodes default to `UNKNOWN_FAIL_CLOSED`.

- [ ] **Step 2: Run RED**

Run: `python -m pytest -q scripts/tests/test-build-work-lineage.py`
Expected: missing module failure.

- [ ] **Step 3: Implement lineage builder**

Use stable IDs `pr:<number>` for PR-backed work and domain-separated SHA-256 IDs for non-PR refs. `objective_digest` is a deterministic evidence digest of normalized title + explicit metadata; it is not semantic authority. Explicit spine/supersession declarations come only from `.aegis/reconciliation/spines.v1.json`.

- [ ] **Step 4: Run GREEN**

Run lineage tests twice and byte-compare output fixtures.

- [ ] **Step 5: Commit**

Commit message: `feat(reconciliation): add stable work lineage graph`

---

### Task 3: Fail-closed lineage resolver and branch-creation gate

**Files:**
- Create: `scripts/resolve-work-lineage.py`
- Create: `scripts/tests/test-resolve-work-lineage.py`
- Modify: `.claude/hooks/user-prompt-intake.sh`
- Modify: `.claude/hooks/session-start.sh`
- Later mirror the same contract into Codex/Gemini hooks without changing semantics.

**Interfaces:**
- Consumes a requested work envelope `{objective_digest, capability_set, paths, explicit_parent_work_ids, referenced_artifacts}` plus `AEGIS_WORK_LINEAGE_V1`.
- Produces one of `CONTINUE_EXISTING | STACK_ON_EXISTING | RESUME_ABANDONED | CREATE_NEW | AMBIGUOUS_HALT` and a continuation envelope.

- [ ] **Step 1: Write failing resolver tests**

Required falsifiers:
1. exact objective match on active work -> `CONTINUE_EXISTING`;
2. explicit parent dependency -> `STACK_ON_EXISTING`;
3. compatible abandoned work -> `RESUME_ABANDONED`;
4. no compatible evidence -> `CREATE_NEW`;
5. multiple equally compatible lineages -> `AMBIGUOUS_HALT`;
6. incomplete discovery -> never `CREATE_NEW` when compatibility cannot be ruled out;
7. a branch-name match alone is insufficient compatibility evidence;
8. `CREATE_NEW` is denied whenever a compatible lineage exists.

- [ ] **Step 2: Run RED**

Expected missing resolver failure.

- [ ] **Step 3: Implement deterministic resolver**

Compatibility v1 uses only explicit/evidence-bound signals: exact objective digest, explicit parent IDs, declared capability/path intersection, exact artifact references, and current work state. No embedding/model similarity may authorize branch creation.

- [ ] **Step 4: Wire provider startup**

Session startup must print `WORK_CONTINUITY_ACTIVE` with WorkID/ref/head when resolved, and `WORK_CONTINUITY_AMBIGUOUS_HALT` when not. User-prompt intake must inject `BRANCH_CREATION_GATE: CreateBranch requires ResolveLineage=CREATE_NEW`.

- [ ] **Step 5: Run GREEN and hook syntax checks**

Run Python tests plus `bash -n` on modified hooks.

- [ ] **Step 6: Commit**

Commit message: `feat(reconciliation): gate new work on lineage resolution`

---

### Task 4: Classification + replayable reconciliation decisions

**Files:**
- Create: `scripts/classify-reconciliation.py`
- Create: `scripts/tests/test-classify-reconciliation.py`
- Create: `.aegis/reconciliation/reconciliation-decisions.v1.jsonl`
- Runtime output: `.aegis/runtime/reconciliation-classification.v1.json`

**Interfaces:**
- Produces exactly one classification per reachable branch/PR: `ACTIVE_SPINE`, `READY_TO_ADMIT`, `NEEDS_REVERIFY`, `BLOCKED`, `UNIQUE_SIDE_CAPABILITY`, `SUPERSEDED_BY`, `REDUNDANT_PROVEN`, `HISTORICAL_EVIDENCE_ONLY`, `RECOVERY_REQUIRED`, or `UNKNOWN_FAIL_CLOSED`.

- [ ] **Step 1: Write falsifiers**

Unknown/incomplete evidence must classify `UNKNOWN_FAIL_CLOSED`; mechanical ancestry is required for `REDUNDANT_PROVEN`; downstream exact-parent PRs become `NEEDS_REVERIFY` after parent movement; mergeable alone cannot yield `READY_TO_ADMIT`; each decision line must bind subject ref/head, evidence roots, action, and predecessor decision digest.

- [ ] **Step 2: RED**

Run focused tests; expect missing implementation.

- [ ] **Step 3: Implement classifier + append-only decision hash chain**

No destructive action is performed by this script; it only emits evidence-bound dispositions.

- [ ] **Step 4: GREEN**

Run tests twice, byte-compare classification output, verify decision-chain tamper detection.

- [ ] **Step 5: Commit**

Commit message: `feat(reconciliation): classify work and record replayable decisions`

---

### Task 5: Reconcile active integration spine bottom-up

**Files:**
- Update generated/decision artifacts only; do not introduce another integration branch.

**Process:**

For each node in order `#275, #276, #277, #278, #279, #280, #282, #283, #284, #285, #290, #291`:

- [ ] resolve current base/head from GitHub;
- [ ] compare unique files/commits against its intended parent;
- [ ] read exact-head CI/workflow state;
- [ ] preserve witness/artifact roots from PR evidence;
- [ ] classify `READY_TO_ADMIT | NEEDS_REVERIFY | BLOCKED`;
- [ ] if parent movement invalidates frozen-parent checks, restack/reverify before promotion;
- [ ] merge only one eligible parent at a time with `expected_head_sha`;
- [ ] re-read `main` and all downstream bases after each canonical mutation;
- [ ] append a reconciliation decision before and after each merge attempt.

Acceptance: one explicit convergence path exists from #275-derived work to canonical main without silently invalidating exact-parent evidence.

---

### Task 6: Salvage every side lineage before cleanup

**Scope includes at minimum:** `#286 -> #289 -> #292`, #281, #274, #267, #268/#270/#272/#273 historical proofline, #240, #242, #239, #238/#243, #193-#200 and other reachable open/closed PRs/branches from the census.

For each item:

- [ ] compare unique diff against reconciled spine;
- [ ] classify unique capability vs superseded vs historical evidence;
- [ ] if still desired, transplant/restack the smallest unique slice with source SHA preserved in the decision record;
- [ ] if obsolete but unique, archive as `HISTORICAL_EVIDENCE_ONLY` rather than deleting history;
- [ ] if artifact/session recovery is required (ProofPrism class), run structural fingerprint recovery before disposition.

No side lineage is skipped because it looks old or has a misleading branch name.

---

### Task 7: Proven cleanup only after full classification

**Files:**
- Reuse/modify PR #287 branch-cleanup workflow only after lineage manifest exists.
- Add tests proving `UNKNOWN_FAIL_CLOSED`, `UNIQUE_SIDE_CAPABILITY`, `RECOVERY_REQUIRED`, and uncontained refs cannot be deleted.

- [ ] run cleanup workflow in dry-run mode;
- [ ] compare every candidate against the current reconciliation manifest;
- [ ] record candidate tip SHA + container ref + containment proof;
- [ ] delete only `REDUNDANT_PROVEN` refs;
- [ ] re-read refs after every deletion/batch;
- [ ] never delete a branch merely because its name appears obsolete.

---

### Task 8: Cross-provider continuity + connector capability plane

**Files:**
- Reuse: existing provider-neutral AEGIS MCP and provider session identity machinery.
- Create only the minimum connector registry/broker files after Tasks 1-7 establish WorkID continuity.

- [ ] mirror the same continuation envelope into Claude, Codex/OpenAI, Gemini and future provider sessions;
- [ ] enforce one WorkID/lease/fence across providers; secondary providers become verifier/reviewer/helper unless assigned a distinct node;
- [ ] register connectors as `AEGIS_NATIVE | REMOTE_MCP | HOST_BOUND` with read/write/consequence metadata;
- [ ] expose provider-neutral list/describe/call operations through AEGIS MCP;
- [ ] keep connector output evidence-only and route mutations through existing authorization/effect verification;
- [ ] add GitHub, Drive, SciSpace, Hugging Face and Airtable first, then Gmail/Calendar/Slack/Notion/Supabase/Vercel/others;
- [ ] test that provider identity does not change connector authority semantics.

---

## Self-review

Spec coverage: all seven design phases plus cross-provider connector plane are mapped to Tasks 1-8. Destructive cleanup is intentionally after census, lineage, classification, active-spine reconciliation and side salvage. Existing `repo-universe.sh`, UCI work/lease contracts and provider MCP are reused rather than duplicated.

Placeholder scan: no implementation step depends on undefined `TBD`/`TODO` behavior. Every generated classification has a closed enum and unknown evidence fails closed.

Type consistency: the flow is `AEGIS_REPO_UNIVERSE_V1 -> AEGIS_RECONCILIATION_UNIVERSE_V1 -> AEGIS_WORK_LINEAGE_V1 -> ResolveLineage result -> reconciliation classification/decisions -> provider continuation envelope`.

## Execution mode

Execute inline on the existing `fix/claude-artifact-discovery-v1` reconciliation lineage. Do not create another branch for this program. Establish RED before each new implementation surface, then GREEN, then proceed to the next task.