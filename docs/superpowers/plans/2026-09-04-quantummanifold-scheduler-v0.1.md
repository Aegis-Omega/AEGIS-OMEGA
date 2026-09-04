# QuantumManifold Scheduler v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the AEGIS Thread-as-QuantumManifold Scheduler v0.1 as a deterministic, fail-closed M3 ranking subsystem with Builder/Falsifier/Reviewer state isolation, replay protection, and an Automaton-3-only M4 authority boundary.

**Architecture:** The production scheduler is a pure deterministic function over canonical M2 graph snapshots and policy-bound candidate actions. It emits `authority_effect = NONE` receipts only. Role envelopes and replay guards remain non-authoritative; the existing `agents/coordinator.py` / Automaton-3 path remains the sole positive execution authority boundary. The implementation is delivered as four atomic PRs stacked onto an integration branch; `main` is not modified by these phase PRs.

**Tech Stack:** Python 3.12 + pytest 8.4.1 for the coordinator-facing runtime and authority tests; TypeScript 5.5 + Vitest 4.1 for Sovereign Omega canonicalization/conformance; Rust 2021 + `cargo test` for independent integer/conformance vectors; RFC 8785 JCS; SHA-256; JSON Schema.

**Spec:** `docs/superpowers/specs/QUANTUMMANIFOLD_SCHEDULER_SPEC_V1.md` at exact spec commit `8764d401379fd66f3295b0a51c51807eb0613481`.

## Global Constraints

- Immutable AEGIS Master Notebook v0.4 digest: `457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404`.
- Design-base `main`: `6eb2ac201bbe60ebaa9cebad714b8696683772e8`.
- Implementation lineage MUST contain spec commit `8764d401379fd66f3295b0a51c51807eb0613481`; do not create the implementation root directly from `main` and thereby omit the approved spec from ancestry.
- `REPOSITORY_MERGE_ENFORCEMENT = NOT_ACTIVE` remains the repository status unless separately re-verified and activated. This plan does not change branch protection or repository rulesets.
- `SchedulerScore(A) != Authority(A)` and all scheduler/role receipts use `authority_effect = "NONE"`.
- Only Automaton-3 may return execution `DENY | ADMIT`.
- No direct `M4 -> M2` promotion.
- Canonical serialized scheduler numbers are non-negative integers only; scale is `PPM = 1_000_000`; all division uses mathematical floor over non-negative exact integers; no runtime floating-point arithmetic in canonical scheduler paths.
- RFC 8785 is the canonical serialization algorithm. The existing `sovereign-omega-v2/src/core/canonicalize.ts` is the repository's declared integrity serialization path and MUST be conformance-hardened rather than bypassed by an incompatible policy.
- Cross-runtime implementations/ports MUST reproduce the same committed conformance vectors; they may not define independent serialization semantics.
- The approved RED identifiers and meanings in spec §15 are immutable. Do not reuse an existing `QM-RED-*` identifier for a different falsifier.
- Synthetic fixtures are allowed for software determinism/unit tests. They do not constitute empirical scientific evidence.
- No RH, QuanPhotonic, PQC-integration, or biological claim is promoted by this implementation.

## Branch / PR Topology

Create the integration branch from the approved spec commit:

```bash
git switch --detach 8764d401379fd66f3295b0a51c51807eb0613481
git switch -c feat/qm-scheduler-v0.1-impl
```

Then deliver four sequential PRs, each targeting `feat/qm-scheduler-v0.1-impl` and merged there only after its exact-head CI is GREEN:

```text
feat/qm-scheduler-phase1-core-kernel
feat/qm-scheduler-phase2-metrics-engine
feat/qm-scheduler-phase3-role-isolation
feat/qm-scheduler-phase4-receipts-boundary
```

Do not open or merge a final integration-to-`main` PR as part of this plan. That is a separate admission decision.

## Canonical RED Mapping

This plan preserves spec §15 exactly:

| RED ID | Canonical meaning | Phase |
|---|---|---:|
| QM-RED-001 | production module absent / expected import failure before implementation | 1 |
| QM-RED-002 | baseline digest mismatch | 1 |
| QM-RED-003 | invalid/non-ancestor exact-head coordinate | 1 |
| QM-RED-004 | reality snapshot digest mismatch | 1 |
| QM-RED-005 | unknown node type | 1 |
| QM-RED-006 | unknown edge type | 1 |
| QM-RED-007 | graph cycle | 1 |
| QM-RED-008 | node-ID collision with different content | 1 |
| QM-RED-009 | dangling edge | 1 |
| QM-RED-010 | scheduler policy digest mismatch | 1 |
| QM-RED-011 | invalid/negative/non-integer/overflow canonical numeric value | 1 |
| QM-RED-012 | `epsilon_ppm <= 0` | 1 |
| QM-RED-013 | equal-score deterministic tie-break | 2 |
| QM-RED-014 | repeated identical input -> byte-identical receipt | 2 |
| QM-RED-015 | scheduler attempts `authority_effect != NONE` | 4 |
| QM-RED-016 | Falsifier receives Builder continuation | 3 |
| QM-RED-017 | Reviewer receives prose continuation | 3 |
| QM-RED-018 | stale head/reality result | 3 |
| QM-RED-019 | repeated execution intent | 4 |
| QM-RED-020 | replay reconstructs different `G_t` digest | 4 |
| QM-RED-021 | restart without persisted authoritative root | 4 |
| QM-RED-022 | Automaton-3 DENY must produce zero side effects | 4 |
| QM-RED-023 | Builder result directly mutates M2 | 4 |
| QM-RED-024 | `SURVIVED_CURRENT_FALSIFIER` mapped to `PROVEN` | 3 |

Additional RFC 8785 conformance tests are prerequisites, but MUST use names such as `JCS-RED-*`, not steal `QM-RED-*` identifiers.

---

# Phase 1 — Core Data Model, JCS Conformance, Fixed-Point Kernel

Target branch/PR: `feat/qm-scheduler-phase1-core-kernel` -> `feat/qm-scheduler-v0.1-impl`.

## Task 1: Establish the true RED anchor and policy artifact

**Files:**
- Create: `configs/scheduler_policy_v1.json`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py`
- Create later in Task 3: `agents/quantummanifold/`

**Interfaces:**
- Produces canonical policy fields `ppm_scale`, `max_safe_canonical_int`, `alpha_ppm`, `beta_ppm`, `gamma_ppm`, `mu_ppm`, `eta_ppm`, `epsilon_ppm`, and `baseline_digest`.
- Policy digest is SHA-256 over RFC-8785 canonical policy bytes and is bound by all later scheduling receipts.

Use this initial policy document:

```json
{
  "schema_version": "AEGIS_QUANTUMMANIFOLD_SCHEDULER_POLICY_V1",
  "ppm_scale": 1000000,
  "max_safe_canonical_int": 9007199254740991,
  "alpha_ppm": 1000000,
  "beta_ppm": 1000000,
  "gamma_ppm": 1000000,
  "mu_ppm": 1000000,
  "eta_ppm": 1000000,
  "epsilon_ppm": 1,
  "baseline_digest": "457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404"
}
```

The coefficients are neutral v0.1 scheduling weights, not scientific probabilities or authority.

- [ ] **Step 1: Write `QM-RED-001` as a test that must fail before production code exists**

```python
# sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py
import importlib


def test_qm_red_001_scheduler_production_module_exists():
    module = importlib.import_module("agents.quantummanifold.scheduler")
    assert module is not None
```

- [ ] **Step 2: Run the single RED anchor before creating production code**

Run:

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py::test_qm_red_001_scheduler_production_module_exists
```

Expected: **FAIL** with `ModuleNotFoundError: agents.quantummanifold.scheduler`. This failure is the RED evidence. Record exact head and CI run ID in the PR body.

- [ ] **Step 3: Commit only the failing RED contract + policy document**

```bash
git add configs/scheduler_policy_v1.json sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py
git commit -m "test(qm): establish RED scheduler absence contract"
```

The test is retained. It becomes GREEN only after the scheduler production module exists.

## Task 2: Harden the repository RFC 8785 path before hashing scheduler state

**Files:**
- Modify: `sovereign-omega-v2/src/core/canonicalize.ts`
- Modify/Create focused tests: `sovereign-omega-v2/test/unit/jcs.test.ts`
- Create: `tests/fixtures/quantummanifold/jcs_conformance_v1.json`

**Rationale:** The current exact-head serializer claims RFC 8785 but sorts keys with `codePointAt`, silently filters object properties whose value is `undefined`, and serializes `bigint` as a JSON string. Those behaviors must not be used as untested integrity semantics for QuantumManifold.

**Interfaces:**
- `canonicalizeJCS(value: unknown): Uint8Array`
- `canonicalizeJCSString(value: unknown): string`
- No second incompatible production canonicalization policy.

- [ ] **Step 1: Add failing JCS conformance tests**

Add tests covering:

```ts
it('JCS-RED-UTF16: sorts object property names by UTF-16 code units', () => {
  const value = { '\uE000': 1, '😀': 2 }
  expect(canonicalizeJCSString(value)).toBe('{"😀":2,"":1}')
})

it('JCS-RED-UNDEFINED: rejects undefined object members instead of silently dropping them', () => {
  expect(() => canonicalizeJCSString({ a: 1, b: undefined })).toThrow(TypeError)
})

it('JCS-RED-BIGINT: rejects bigint because it is not valid I-JSON input', () => {
  expect(() => canonicalizeJCSString({ a: 1n })).toThrow(TypeError)
})
```

- [ ] **Step 2: Run only those tests and verify they fail against the current implementation**

```bash
cd sovereign-omega-v2
npm test -- --run test/unit/jcs.test.ts
```

Expected: at least the newly added conformance cases fail for the intended reasons.

- [ ] **Step 3: Implement the minimum RFC 8785 corrections**

Required semantics:

```ts
if (type === 'bigint') throw new TypeError('bigint is not JSON-serialisable')

const sortedKeys = Object.keys(obj).sort((a, b) => {
  const n = Math.min(a.length, b.length)
  for (let i = 0; i < n; i++) {
    const diff = a.charCodeAt(i) - b.charCodeAt(i)
    if (diff !== 0) return diff
  }
  return a.length - b.length
})

const pairs = sortedKeys.map(k => {
  if (obj[k] === undefined) throw new TypeError('undefined is not JSON-serialisable')
  return serializeString(k) + ':' + serializeValue(obj[k])
})
```

Do not broaden this task into unrelated serializer refactoring.

- [ ] **Step 4: Run the full canonicalization and TypeScript unit suite**

```bash
cd sovereign-omega-v2
npm test -- --run test/unit/jcs.test.ts
npm run typecheck
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/src/core/canonicalize.ts sovereign-omega-v2/test/unit/jcs.test.ts tests/fixtures/quantummanifold/jcs_conformance_v1.json
git commit -m "fix(jcs): enforce RFC8785 scheduler canonicalization semantics"
```

## Task 3: Implement exact fixed-point arithmetic and create the scheduler module boundary

**Files:**
- Create: `agents/quantummanifold/__init__.py`
- Create: `agents/quantummanifold/fixed_point.py`
- Create: `agents/quantummanifold/scheduler.py` as a minimal importable module with no ranking implementation beyond a fail-closed stub until Phase 2
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_fixed_point.py`
- Create: `sovereign-omega-v2/src/quantummanifold/fixed-point.ts`
- Create: `sovereign-omega-v2/test/unit/quantummanifold-fixed-point.test.ts`
- Create: `aegis-cl-psi/tests/quantummanifold_fixed_point.rs`

**Interfaces:**

Python:

```python
PPM = 1_000_000
MAX_SAFE_CANONICAL_INT = 9_007_199_254_740_991

def require_canonical_int(value: object, *, field: str) -> int: ...
def mul_ppm(x: int, y: int) -> int: ...
def score_ppm(*, alpha_ppm: int, information_gain_ppm: int, beta_ppm: int, closure_leverage_ppm: int, gamma_ppm: int, falsification_value_ppm: int, epsilon_ppm: int, cost_ppm: int) -> int: ...
```

Normative arithmetic:

```text
mul_ppm(x, y) = floor(x*y / 1_000_000)
ranking_score_ppm = floor(numerator_ppm * 1_000_000 / denominator_ppm)
```

- [ ] **Step 1: Write `QM-RED-011` and `QM-RED-012` failures**

Test negative, boolean-as-int, float, serialization overflow, and `epsilon_ppm <= 0`. Expected reason codes are `FIXED_POINT_DOMAIN_ERROR`, `SCORE_RANGE_EXCEEDED`, and `INVALID_STABILIZER`.

- [ ] **Step 2: Run Python tests and verify RED**

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_fixed_point.py sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py
```

Expected: fixed-point behavior tests fail before implementation; `QM-RED-001` remains RED until the minimal `scheduler.py` boundary is created in the GREEN step.

- [ ] **Step 3: Implement Python exact integer kernel and minimal importable `scheduler.py`; no `/` operator in canonical arithmetic**

Use `//` on non-negative integers only and explicit range checks at serialization boundaries. The minimal scheduler module may expose only a typed `NotImplementedError` path for ranking until Phase 2; it MUST NOT fabricate a scheduling receipt.

- [ ] **Step 4: Port only the normative arithmetic to TypeScript `bigint` and Rust checked integer arithmetic for conformance**

TypeScript and Rust ports are conformance implementations; they MUST consume the same committed vectors and may not define different rounding semantics.

- [ ] **Step 5: Run all three runtimes**

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py sovereign-omega-v2/python/tests/test_quantummanifold_fixed_point.py
cd sovereign-omega-v2 && npm test -- --run test/unit/quantummanifold-fixed-point.test.ts
cd ../aegis-cl-psi && cargo test --test quantummanifold_fixed_point
```

Expected: PASS, including `QM-RED-001` now GREEN because the production module boundary exists.

- [ ] **Step 6: Commit**

```bash
git add agents/quantummanifold sovereign-omega-v2/python/tests/test_quantummanifold_fixed_point.py sovereign-omega-v2/src/quantummanifold sovereign-omega-v2/test/unit/quantummanifold-fixed-point.test.ts aegis-cl-psi/tests/quantummanifold_fixed_point.rs
git commit -m "feat(qm): add exact PPM fixed-point kernel"
```

## Task 4: Implement typed graph, exact-head binding, and digest verification

**Files:**
- Create: `agents/quantummanifold/model.py`
- Create: `agents/quantummanifold/graph.py`
- Create: `agents/quantummanifold/bindings.py`
- Create: `schemas/quantummanifold-reality-graph.v1.schema.json`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_graph.py`

**Interfaces:**

```python
NODE_TYPES = {"CLAIM", "OBLIGATION", "EVIDENCE", "THREAD", "ACTION_CANDIDATE"}
EDGE_TYPES = {"DEPENDS_ON", "SUPPORTED_BY", "FALSIFIED_BY", "BLOCKS", "CLOSES", "DERIVED_FROM", "BELONGS_TO_THREAD"}

def validate_graph(graph: dict) -> None: ...
def canonical_graph_digest(graph: dict) -> str: ...
def verify_coordinate_bindings(*, graph: dict, baseline_digest: str, source_head_sha: str, expected_reality_digest: str, expected_policy_digest: str, repo_root: str) -> None: ...
```

- [ ] **Step 1: Write canonical RED tests `QM-RED-002` through `QM-RED-010`**

Each test must assert exactly one reason code:

```text
QM-RED-002 BASELINE_BINDING_MISMATCH
QM-RED-003 SOURCE_HEAD_INVALID
QM-RED-004 REALITY_DIGEST_MISMATCH
QM-RED-005 UNKNOWN_NODE_TYPE
QM-RED-006 UNKNOWN_EDGE_TYPE
QM-RED-007 GRAPH_CYCLE_DETECTED
QM-RED-008 NODE_ID_COLLISION
QM-RED-009 DANGLING_EDGE
QM-RED-010 SCHEDULER_POLICY_MISMATCH
```

- [ ] **Step 2: Run and verify RED**

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_graph.py
```

- [ ] **Step 3: Implement exact graph validation and topological cycle detection**

Node IDs bind canonical node content. v0.1 rejects duplicate node IDs even when content is byte-identical; this avoids ambiguous provenance and keeps the graph representation unique.

- [ ] **Step 4: Implement `SOURCE_HEAD_INVALID` as repository-bound validation**

`source_head_sha` must resolve to a 40-lowercase-hex Git commit and be an ancestor of the current execution coordinate selected for this scheduler run. A historical proof head is accepted only when the run explicitly declares that historical coordinate as its source coordinate.

- [ ] **Step 5: Run Phase-1 tests**

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_red_contract.py sovereign-omega-v2/python/tests/test_quantummanifold_fixed_point.py sovereign-omega-v2/python/tests/test_quantummanifold_graph.py
cd sovereign-omega-v2 && npm test -- --run test/unit/jcs.test.ts test/unit/quantummanifold-fixed-point.test.ts && npm run typecheck
cd ../aegis-cl-psi && cargo test --test quantummanifold_fixed_point
```

Expected: all behavior tests PASS. Preserve the exact pre-GREEN `QM-RED-001` failing commit/run receipt in the PR body.

- [ ] **Step 6: Add Phase-1 CI lane**

Create `.github/workflows/quantummanifold-scheduler.yml` with `contents: read`, exact Python dependency pins consistent with `coordinator-authority.yml`, Node install for `sovereign-omega-v2`, and Rust stable. The workflow must run only read/test commands and must not write branch/ruleset state.

- [ ] **Step 7: Commit and open Phase-1 PR to the integration branch**

Commit message:

```text
feat(qm): close phase1 core kernel RED contracts
```

PR body must record the RED anchor commit/run, GREEN exact head, policy digest, test commands, and explicitly state `authority_effect = NONE` and `main unchanged`.

---

# Phase 2 — Admissible Projection, Metrics, Ranking, Determinism

Target branch/PR: `feat/qm-scheduler-phase2-metrics-engine` -> `feat/qm-scheduler-v0.1-impl`, created only after Phase 1 is GREEN and merged into the integration branch.

## Task 5: Implement M1 -> M2 admissible projection

**Files:**
- Create: `agents/quantummanifold/projection.py`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_projection.py`

**Interfaces:**

```python
def project_admissible(history_graph: dict, *, admission_state: dict) -> dict: ...
```

The projection MUST preserve falsified/stale historical nodes in M1 input while excluding non-admissible support from returned M2 `G_t`.

- [ ] Write tests that a falsified thread remains in history but is absent from `Gamma_t_active`.
- [ ] Run tests and observe RED.
- [ ] Implement minimal deterministic projection.
- [ ] Re-run tests and commit `feat(qm): add deterministic admissible projection`.

## Task 6: Implement centrality, closure leverage, falsification value, cost, and score

**Files:**
- Create: `agents/quantummanifold/metrics.py`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_metrics.py`
- Extend: `tests/fixtures/quantummanifold/conformance-v1.json`

**Interfaces:**

```python
def obligation_centrality_ppm(graph: dict, obligation_id: str) -> int: ...
def closure_leverage_ppm(graph: dict, action: dict) -> int: ...
def falsification_value_ppm(graph: dict, action: dict) -> int: ...
def action_cost_ppm(action: dict, policy: dict) -> int: ...
def action_score_ppm(graph: dict, action: dict, policy: dict) -> dict[str, int]: ...
```

- [ ] Write hand-computable fixtures with exact integer expected values.
- [ ] Verify tests fail before implementation.
- [ ] Implement using only fixed-point primitives from Phase 1.
- [ ] Add a source-level guard test that rejects use of runtime floating arithmetic in the canonical fixed-point/scoring modules.
- [ ] Run and commit.

## Task 7: Implement deterministic candidate ranking and `QM-RED-013` / `QM-RED-014`

**Files:**
- Modify: `agents/quantummanifold/scheduler.py`
- Create: `agents/quantummanifold/canonical.py`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_scheduler.py`
- Create: `sovereign-omega-v2/src/quantummanifold/conformance.ts`
- Create: `aegis-cl-psi/tests/quantummanifold_scheduler_conformance.rs`

**Interfaces:**

```python
def rank_candidates(*, graph: dict, candidates: list[dict], policy: dict, coordinate: dict) -> list[dict]: ...
def select_action(*, graph: dict, candidates: list[dict], policy: dict, coordinate: dict) -> dict: ...
def scheduling_receipt_bytes(*, graph: dict, candidates: list[dict], policy: dict, coordinate: dict) -> bytes: ...
```

Tie-break key is exactly:

```python
(-ranking_score_ppm, -closure_leverage_ppm, -falsification_value_ppm, cost_ppm, candidate_action_digest)
```

- [ ] **Write `QM-RED-013`: equal-score actions choose the same winner according to all four tie-break levels.**
- [ ] **Write `QM-RED-014`: run the identical canonical input at least three times and assert byte-identical receipt bytes and identical SHA-256.**
- [ ] Run and verify RED.
- [ ] Implement minimum ranking and canonical receipt construction.
- [ ] Make TypeScript and Rust conformance tests consume the same committed vectors and compare selected digest + integer score + canonical receipt SHA-256.
- [ ] Run:

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_projection.py sovereign-omega-v2/python/tests/test_quantummanifold_metrics.py sovereign-omega-v2/python/tests/test_quantummanifold_scheduler.py
cd sovereign-omega-v2 && npm test -- --run test/unit/jcs.test.ts test/unit/quantummanifold-fixed-point.test.ts && npm run typecheck
cd ../aegis-cl-psi && cargo test --test quantummanifold_fixed_point --test quantummanifold_scheduler_conformance
```

- [ ] Commit and open Phase-2 PR. Record exact cross-runtime vector digest(s). Do not claim full platform parity unless all three lanes are GREEN at the same candidate head.

---

# Phase 3 — Builder/Falsifier/Reviewer Isolation and Stale-State Semantics

Target branch/PR: `feat/qm-scheduler-phase3-role-isolation` -> `feat/qm-scheduler-v0.1-impl`.

## Task 8: Implement immutable role-context envelopes

**Files:**
- Create: `agents/quantummanifold/role_context.py`
- Create: `schemas/quantummanifold-role-context-envelope.v1.schema.json`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_role_isolation.py`

**Interfaces:**

```python
def build_builder_context(...)->dict: ...
def build_falsifier_context(...)->dict: ...
def build_reviewer_context(...)->dict: ...
def validate_role_context(envelope: dict) -> None: ...
```

Role constraints are structural allowlists, not a heuristic prose scrubber:

```text
BUILDER   -> PRESERVE
FALSIFIER -> RAW_EVIDENCE_ONLY, continuation_state_digest = null
REVIEWER  -> CLEAN_ROOM, continuation_state_digest = null
```

Do **not** implement a regex-based "prose filter" as the primary control. Construct Falsifier/Reviewer envelopes from explicit machine-field allowlists so forbidden Builder fields never enter the envelope.

- [ ] Write `QM-RED-016`: any Builder continuation/memory field supplied to Falsifier construction must raise `ROLE_ISOLATION_VIOLATION`.
- [ ] Write `QM-RED-017`: any narrative/prose continuation field supplied to Reviewer construction must raise `CLEAN_ROOM_VIOLATION`.
- [ ] Verify RED, implement allowlist constructors/validators, rerun GREEN.

## Task 9: Implement stale/rebase classification and epistemic anti-inflation

**Files:**
- Create: `agents/quantummanifold/state_transition.py`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_state_transition.py`

**Interfaces:**

```python
def classify_returned_result(*, result_coordinate: dict, current_coordinate: dict) -> str: ...
def validate_falsifier_outcome_transition(*, outcome: str, requested_status: str) -> None: ...
```

- [ ] Write `QM-RED-018` asserting coordinate drift returns exactly `STALE_RESULT_REQUIRES_REBASE`, preserves the result for M1 append, and forbids automatic M2 inclusion.
- [ ] Write `QM-RED-024` asserting `SURVIVED_CURRENT_FALSIFIER -> PROVEN` raises `EPISTEMIC_INFLATION_FORBIDDEN`.
- [ ] Run RED, implement, rerun GREEN.
- [ ] Commit and open Phase-3 PR with a machine-readable envelope example for each role, all containing `authority_effect = NONE`.

---

# Phase 4 — Receipts, Replay, Recovery Boundary, Automaton-3 Integration

Target branch/PR: `feat/qm-scheduler-phase4-receipts-boundary` -> `feat/qm-scheduler-v0.1-impl`.

## Task 10: Implement scheduling and role-result receipt verification

**Files:**
- Create: `agents/quantummanifold/receipts.py`
- Create: `schemas/quantummanifold-scheduling-receipt.v1.schema.json`
- Create: `schemas/quantummanifold-role-result.v1.schema.json`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_receipts.py`

**Interfaces:**

```python
def emit_scheduling_receipt(...)->dict: ...
def verify_scheduling_receipt(receipt: dict) -> None: ...
def verify_role_result_receipt(receipt: dict) -> None: ...
```

- [ ] Write `QM-RED-015`: any scheduling or role receipt with `authority_effect != "NONE"` raises `AUTHORITY_TUNNELING_ATTEMPT`.
- [ ] Verify RED, implement exact schema/semantic checks, rerun GREEN.

## Task 11: Implement replay-intent and restart/reconstruction guards

**Files:**
- Create: `agents/quantummanifold/replay.py`
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_replay.py`

**Interfaces:**

```python
def execution_intent_digest(*, source_head_sha: str, reality_snapshot_digest: str, selected_action_digest: str, role_context_digest: str, attempt_sequence: int) -> str: ...
def consume_execution_intent(state: dict, intent_digest: str) -> dict: ...
def verify_replayed_state(*, recorded_reality_digest: str, replayed_graph: dict, recorded_scheduler_digest: str, replayed_scheduler_bytes: bytes) -> None: ...
def require_authoritative_restart_root(root_digest: str | None) -> None: ...
```

- [ ] `QM-RED-019`: duplicate execution intent -> `EXECUTION_INTENT_REPLAY` and no side effect callback.
- [ ] `QM-RED-020`: replayed `G_t`/scheduler digest mismatch -> `REPLAY_STATE_DIVERGENCE`.
- [ ] `QM-RED-021`: missing restart root -> `STATE_RESET_EXPOSURE`.
- [ ] Run RED, implement, rerun GREEN.

Do not claim durable persistence. The existing TypeScript ledger persistence code is a deterministic serialization/reconstruction seam, not a database backend.

## Task 12: Integrate M3 recommendation with the existing Automaton-3 authority choke point

**Files:**
- Create: `agents/quantummanifold/dispatch_bridge.py`
- Modify: `agents/coordinator.py` only at the narrow dispatch seam required to accept a verified scheduler recommendation as non-authoritative input.
- Modify: `.github/workflows/coordinator-authority.yml` path triggers to include `agents/quantummanifold/**` and new QuantumManifold authority tests, or keep the dedicated QuantumManifold workflow cross-wired to run existing coordinator authority tests.
- Create: `sovereign-omega-v2/python/tests/test_quantummanifold_authority_boundary.py`

**Interfaces:**

```python
async def dispatch_recommended_action(*, scheduling_receipt: dict, role_context: dict, current_coordinate: dict) -> list: ...
```

Required sequence:

```text
verify scheduler receipt
verify current exact-head/reality coordinate
construct role context
call existing Automaton-3 positive authority path
DENY -> zero run_agent calls
ADMIT -> at most the explicitly admitted role/action executes
append result/denial to historical output path
never mutate M2 directly
```

- [ ] Write `QM-RED-022`: patch Automaton-3 to return `DENY`; assert `run_agent` / side-effect callback call count is zero.
- [ ] Write `QM-RED-023`: Builder result attempting direct M2 mutation raises `DIRECT_M4_TO_M2_PROMOTION_FORBIDDEN`.
- [ ] Verify RED before integration code.
- [ ] Implement the narrow bridge without adding any alternate positive-authority function.
- [ ] Run existing coordinator authority tests unchanged:

```bash
pytest -q sovereign-omega-v2/python/tests/test_skill_authority.py
pytest -q sovereign-omega-v2/python/tests/test_coordinator_authority.py
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_authority_boundary.py
```

Expected: all PASS.

- [ ] Run the complete QuantumManifold suite and all cross-runtime conformance lanes.
- [ ] Inspect `git diff`/repository metadata and confirm no changes to branch protection, rulesets, or workflow settings that could masquerade as repository merge enforcement.
- [ ] Commit and open Phase-4 PR to the integration branch.

---

# Final Verification on the Integration Branch

After all four phase PRs are GREEN and merged to `feat/qm-scheduler-v0.1-impl`, create an integration verification receipt but do not merge to `main`.

Required checks:

```bash
pytest -q sovereign-omega-v2/python/tests/test_quantummanifold_*.py
pytest -q sovereign-omega-v2/python/tests/test_skill_authority.py sovereign-omega-v2/python/tests/test_coordinator_authority.py
cd sovereign-omega-v2 && npm test -- --run test/unit/jcs.test.ts test/unit/quantummanifold-fixed-point.test.ts && npm run typecheck
cd ../aegis-cl-psi && cargo test --test quantummanifold_fixed_point --test quantummanifold_scheduler_conformance
```

The final integration receipt must bind:

```text
approved_spec_commit
integration_head_sha
baseline_digest
scheduler_policy_digest
conformance_fixture_digest
QM-RED-001..024 result map
Python test command + result
TypeScript test command + result
Rust test command + result
existing coordinator authority test result
authority_effect = NONE
repository_merge_enforcement = NOT_ACTIVE
```

Permitted bounded status after all integration checks are GREEN:

```text
QUANTUMMANIFOLD_SCHEDULER = MACHINE_TESTED_ON_INTEGRATION_EXACT_HEAD
ROLE_ISOLATION            = MACHINE_TESTED_ON_INTEGRATION_EXACT_HEAD
REPLAY_GUARDS             = MACHINE_TESTED_ON_INTEGRATION_EXACT_HEAD
AUTOMATON3_BOUNDARY       = PRESERVED_IN_RECORDED_TEST_ENVIRONMENT
MAIN_ADMISSION            = NOT_PERFORMED
REPOSITORY_MERGE_ENFORCEMENT = NOT_ACTIVE
GLOBAL_FAIL_CLOSED_SYSTEM = NOT_YET_ESTABLISHED
```

Do not promote the status to `ACTIVE_FAIL_CLOSED`, `PRODUCTION`, or repository-wide `MACHINE_ENFORCED` without separate evidence.

# Plan Self-Review Result

- **Spec coverage:** All spec v0.1 surfaces are assigned to a task: M1/M2 projection, typed DAG, exact coordinates, fixed-point arithmetic, metrics, deterministic ranking, scheduling receipt, claim/role boundaries, stale semantics, replay, recovery boundary, Automaton-3 integration, and all 24 RED falsifiers.
- **RED-ID consistency:** Corrected. The user's draft had reassigned several RED identifiers; this plan preserves the exact approved §15 mapping.
- **TDD RED semantics:** Corrected. `QM-RED-001` is now a genuinely failing import test before production code exists, then becomes GREEN when the module boundary is introduced.
- **Lineage consistency:** Corrected. The implementation integration branch is rooted at approved spec commit `8764d401...`, which itself descends from design-base `main`; therefore the normative spec travels in implementation ancestry.
- **Canonicalization consistency:** Corrected. No incompatible second serialization policy is introduced; the declared RFC 8785 path is hardened and cross-runtime ports are tested against common vectors.
- **Role isolation:** Uses construction-time allowlists, not post-hoc prose regex stripping.
- **Authority consistency:** No task grants scheduler/role output positive authority. Automaton-3 remains the only positive execution gate.
- **Persistence boundary:** Durable backend remains out of scope and unestablished.
- **Repository enforcement:** No branch-protection/ruleset mutation is part of the plan.
- **Placeholders:** None; exact paths, commands, interfaces, branch topology, failure codes, and acceptance boundaries are specified.
