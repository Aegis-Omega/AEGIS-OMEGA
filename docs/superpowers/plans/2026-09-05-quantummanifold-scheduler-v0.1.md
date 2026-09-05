# QuantumManifold Scheduler v0.1 Phase-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first repository-bound, deterministic, authority-zero QuantumManifold Scheduler slice on the audited MHP derivation substrate, with exact-head RED→GREEN evidence for centrality anti-inflation, closure-prior provenance, stale-coordinate isolation, and scheduler authority non-tunneling.

**Architecture:** The scheduler is a pure/read-only M3 optimization kernel. It consumes content-addressed graph/provenance inputs and existing MHP verified-store ports, computes exact integer fixed-point ranking, and emits `DispatchProposalV1` with `authority_effect="NONE"`. Automaton-3 remains the only positive execution authority; the dedicated QuantumManifold CI lane reruns inherited MHP suites on the same exact candidate head and emits a content-addressed RED/GREEN attestation.

**Tech Stack:** Python 3.12, stdlib dataclasses/typing/hashlib/json, pytest 8.3.5, GitHub Actions, existing AEGIS `canonical_hash`/MHP trust-store protocols.

**Spec:** `docs/superpowers/specs/QUANTUMMANIFOLD_SCHEDULER_PHASE1_DELTA_V1.md` and parent `docs/superpowers/specs/QUANTUMMANIFOLD_SCHEDULER_SPEC_V1.md`

## Global Constraints

- Scheduler authority is exactly `NONE`; it cannot admit claims or advance authority.
- Automaton-3 remains the sole positive execution authority.
- Canonical scheduler arithmetic uses non-negative exact integers only; `PPM = 1_000_000` and `MAX_SAFE_CANONICAL_INT = 9_007_199_254_740_991`.
- SHA-256 digests are identities/bindings, never numeric scoring operands.
- MHP integration is read-only through existing verified-store ports; no parallel lineage/proof store is introduced.
- `.claude.json` and `skill-hashes.sha256` are not manually rewritten by this plan.
- Trusted Cognitive Admission and repository merge enforcement are external boundaries, not Phase-1 GREEN requirements.
- Every CI claim is exact-head bound and every RED/GREEN run emits a content-addressed attestation artifact.
- No network I/O is performed inside the scheduler kernel.

---

## File Structure

- Create `harness/policies/quantummanifold-scheduler.v1.json` — immutable Phase-1 integer coefficients and authority-zero policy.
- Create `harness/sdk/quantummanifold_scheduler.py` — typed records, validators, fixed-point arithmetic, centrality, closure-prior resolution, stale gate, ranking, and proposal serialization. Keep this single module for V0.1 because the bounded surface is small; split only after it becomes unwieldy.
- Create `harness/tests/test_quantummanifold_scheduler_phase1.py` — focused four falsifiers plus deterministic/proposal invariants.
- Create `.github/workflows/quantummanifold-scheduler-phase1.yml` — exact-head RED/GREEN attestation and inherited MHP regression lane.
- Preserve inherited `harness/sdk/meaning_heritage.py`, `harness/sdk/morphisms.py`, `harness/sdk/heritage_composition_base.py`, and `harness/sdk/heritage_composition.py` unchanged during Phase 1 unless a failing regression proves a concrete integration defect.
- Preserve inherited MHP workflow files unchanged; the new QM workflow executes their test suites directly on the QM head.

---

### Task 1: Freeze policy and preregister focused RED contract

**Files:**
- Create: `harness/policies/quantummanifold-scheduler.v1.json`
- Create: `harness/tests/test_quantummanifold_scheduler_phase1.py`
- Create: `.github/workflows/quantummanifold-scheduler-phase1.yml`

**Interfaces:**
- Consumes: existing `harness.sdk.sovereign_execution.canonical_hash`, `harness.sdk.authority_client.authorize_from_environment` semantics, inherited MHP code/tests.
- Produces: preregistered test names and a dedicated workflow that emits `AEGIS_QUANTUMMANIFOLD_PHASE1_ATTESTATION_V1` even on RED.

- [ ] **Step 1: Add the policy file**

Use exactly:

```json
{
  "schema_version": "1.0.0",
  "policy_kind": "AEGIS_QUANTUMMANIFOLD_SCHEDULER_POLICY_V1",
  "authority_effect": "NONE",
  "ppm": 1000000,
  "max_safe_canonical_int": 9007199254740991,
  "alpha_ppm": 1000000,
  "beta_ppm": 1000000,
  "gamma_ppm": 1000000,
  "mu_ppm": 1000000,
  "eta_ppm": 1000000,
  "epsilon_ppm": 1
}
```

- [ ] **Step 2: Write the four failing tests before the production module exists**

The test file imports these public names:

```python
from harness.sdk.quantummanifold_scheduler import (
    CandidateActionV1,
    ClosurePriorV1,
    DispatchProposalV1,
    OpenObligationV1,
    QuantumManifoldError,
    QuantumManifoldSchedulerV1,
    RealityThreadV1,
    TrustedClosurePriorStore,
)
```

Preregister exact tests:

```python
def test_centrality_inflation_rejected(): ...
def test_fake_closure_leverage_rejected(): ...
def test_stale_exact_head_rejected(): ...
def test_authority_tunneling_rejected(): ...
```

The centrality fixture must build one canonical verified lineage contribution and a second graph with 100 aliases carrying the same `(claim_digest, semantic_fingerprint, verified_lineage_root)` tuple, then assert equal canonical centrality rather than 100x mass.

The closure-prior fixture must put a high inline numeric claim on `CandidateActionV1` without a trusted prior root and assert `QuantumManifoldError.reason_code == "UNVERIFIED_CLOSURE_PRIOR"`.

The stale fixture must evaluate a candidate bound to `source_head_sha=A*40` against `current_head_sha=B*40` and assert `STALE_RESULT_REQUIRES_REBASE`.

The authority fixture must assert all produced proposals have `authority_effect == "NONE"`, `can_admit_claim is False`, `can_advance_authority is False`, and that a proposal cannot be converted into a positive execution identity/decision by the scheduler API.

- [ ] **Step 3: Add the dedicated RED/GREEN workflow**

Workflow requirements:

```text
branch = feat/qm-scheduler-v0.1-impl
CANDIDATE_SHA = github.event.pull_request.head.sha || github.sha
SCHEDULER_DESIGN_PARENT = 8764d401379fd66f3295b0a51c51807eb0613481
MHP_SUBSTRATE_PARENT = b40163d19a1967db9ecafe8bd172556c21e8ef75
```

It must use `actions/checkout@11d5960a326750d5838078e36cf38b85af677262`, `fetch-depth: 0`, `persist-credentials: false`, assert exact checkout and both ancestor relations, install `pytest==8.3.5`, run the focused QM test with `set +e`, capture its exit code, then run inherited MHP suites separately.

Inherited same-head regression command:

```bash
python -m pytest -q \
  harness/tests/test_meaning_heritage_morphisms.py \
  harness/tests/test_morphism_hardening.py \
  harness/tests/test_heritage_fingerprint_hardening.py \
  harness/tests/test_heritage_transitive_composition.py \
  harness/tests/test_heritage_derivation_composition.py
```

The workflow must emit JSON receipt fields required by delta spec §12 and hash at least the policy, QM contract, `meaning_heritage.py`, `morphisms.py`, `heritage_composition_base.py`, and `heritage_composition.py`.

- [ ] **Step 4: Commit the preregistered RED contract**

```bash
git add harness/policies/quantummanifold-scheduler.v1.json \
        harness/tests/test_quantummanifold_scheduler_phase1.py \
        .github/workflows/quantummanifold-scheduler-phase1.yml
git commit -m "test(qm): preregister phase-1 scheduler falsifiers"
```

- [ ] **Step 5: Observe RED at exact head**

Expected focused failure: import/collection failure because `harness/sdk/quantummanifold_scheduler.py` does not exist. The workflow must nevertheless upload the attestation/log bundle. Record the run ID, exact head, receipt SHA-256, artifact ID and artifact digest. This is the module-absence RED anchor; it does not yet prove all four semantic failures were reached.

---

### Task 2: Add contract-only scheduler scaffold and expose semantic REDs

**Files:**
- Create: `harness/sdk/quantummanifold_scheduler.py`
- Test: `harness/tests/test_quantummanifold_scheduler_phase1.py`

**Interfaces:**
- Produces immutable dataclasses/protocols and reason-coded error class; no ranking implementation yet.
- Public error contract: `QuantumManifoldError(reason_code: str)` with `.reason_code`.

- [ ] **Step 1: Add immutable type contracts**

Define:

```python
@dataclass(frozen=True)
class RealityThreadV1:
    thread_id: str
    source_head_sha: str
    claim_digest: str
    semantic_fingerprint: str
    verified_lineage_root: str
    active: bool = True

@dataclass(frozen=True)
class OpenObligationV1:
    obligation_id: str
    obligation_digest: str
    source_head_sha: str
    downstream_threads: tuple[RealityThreadV1, ...]

@dataclass(frozen=True)
class CandidateActionV1:
    action_id: str
    candidate_action_digest: str
    source_head_sha: str
    obligation_digest: str
    closure_prior_root: str | None
    information_gain_ppm: int
    compute_cost_ppm: int
    evidence_cost_ppm: int
    latency_cost_ppm: int
    recommended_role: str

@dataclass(frozen=True)
class ClosurePriorV1:
    prior_root: str
    obligation_digest: str
    candidate_action_digest: str
    p_close_ppm: int
    estimator_kind: str
    estimator_root: str
    policy_digest: str
    source_head_sha: str
    verification_receipt_root: str

class TrustedClosurePriorStore(Protocol):
    def fetch_verified(self, prior_root: str) -> ClosurePriorV1: ...

@dataclass(frozen=True)
class DispatchProposalV1:
    receipt_kind: str
    baseline_digest: str
    source_head_sha: str
    reality_snapshot_digest: str
    obligation_set_digest: str
    candidate_set_digest: str
    scheduler_policy_digest: str
    selected_action_digest: str
    information_gain_ppm: int
    closure_leverage_ppm: int
    falsification_value_ppm: int
    cost_ppm: int
    ranking_score_ppm: int
    recommended_role: str
    authority_effect: str = "NONE"
    can_admit_claim: bool = False
    can_advance_authority: bool = False
```

- [ ] **Step 2: Add strict lexical/range validators but leave four core operations unimplemented**

Use lowercase 40-hex Git SHA, lowercase 64-hex digest patterns, role enum `{BUILDER,FALSIFIER,REVIEWER}`, and integer domain validation. Any `bool` used as an integer must be rejected because Python `bool` subclasses `int`.

Expose methods on `QuantumManifoldSchedulerV1` for:

```python
centrality_ppm(obligation: OpenObligationV1) -> int
closure_leverage_ppm(action: CandidateActionV1, obligation: OpenObligationV1) -> int
assert_current_head(bound_head_sha: str, current_head_sha: str) -> None
build_proposal(...) -> DispatchProposalV1
```

For this scaffold, raise `NotImplementedError` from these four methods.

- [ ] **Step 3: Run focused tests**

Run:

```bash
python -m pytest -q harness/tests/test_quantummanifold_scheduler_phase1.py
```

Expected: collection/import succeeds and the four preregistered semantic tests fail because core operations are not implemented. Capture exact-head RED receipt/artifact again. This is the semantic RED anchor.

- [ ] **Step 4: Commit scaffold**

```bash
git add harness/sdk/quantummanifold_scheduler.py
git commit -m "feat(qm): add authority-zero scheduler contracts"
```

---

### Task 3: Close centrality Sybil inflation and closure-prior provenance

**Files:**
- Modify: `harness/sdk/quantummanifold_scheduler.py`
- Test: `harness/tests/test_quantummanifold_scheduler_phase1.py`

**Interfaces:**
- Consumes: `canonical_hash("qm-lineage-class-v1", canonical_tuple)` semantics and `TrustedClosurePriorStore.fetch_verified`.
- Produces: deterministic `centrality_ppm` and `closure_leverage_ppm`.

- [ ] **Step 1: Implement canonical lineage-class dedupe**

For each active downstream thread:

```python
lineage_preimage = {
    "claim_digest": thread.claim_digest,
    "semantic_fingerprint": thread.semantic_fingerprint,
    "verified_lineage_root": thread.verified_lineage_root,
}
lineage_id = canonical_hash("qm-lineage-class-v1", lineage_preimage)
```

Only the first occurrence of a lineage ID contributes priority mass. In Phase 1 each unique verified lineage contributes equal unit mass; graph aliases cannot multiply it. Empty/unverified lineage root fails closed rather than granting positive mass.

- [ ] **Step 2: Implement verified closure-prior resolution**

`closure_leverage_ppm` must:

1. reject `closure_prior_root is None` with `UNVERIFIED_CLOSURE_PRIOR`;
2. call `prior_store.fetch_verified(root)`;
3. recompute and verify `prior_root` from all other canonical fields;
4. verify exact obligation digest, action digest, policy digest and source head;
5. validate `0 <= p_close_ppm <= PPM`;
6. return `mul_ppm(p_close_ppm, centrality_ppm(obligation))`.

Any missing/untrusted/spliced prior becomes `UNVERIFIED_CLOSURE_PRIOR`; do not fall back to a generator-provided scalar.

- [ ] **Step 3: Run targeted tests**

```bash
python -m pytest -q \
  harness/tests/test_quantummanifold_scheduler_phase1.py::test_centrality_inflation_rejected \
  harness/tests/test_quantummanifold_scheduler_phase1.py::test_fake_closure_leverage_rejected
```

Expected: PASS.

- [ ] **Step 4: Run inherited MHP regression**

Use the five-suite command from Task 1. Expected: PASS unchanged.

- [ ] **Step 5: Commit**

```bash
git add harness/sdk/quantummanifold_scheduler.py harness/tests/test_quantummanifold_scheduler_phase1.py
git commit -m "feat(qm): bind centrality and closure leverage to verified provenance"
```

---

### Task 4: Close stale-coordinate and authority-tunneling boundaries

**Files:**
- Modify: `harness/sdk/quantummanifold_scheduler.py`
- Test: `harness/tests/test_quantummanifold_scheduler_phase1.py`

**Interfaces:**
- Produces exact `STALE_RESULT_REQUIRES_REBASE` and scheduler-only authority denial behavior.
- Does not modify `harness/sdk/authority_client.py` unless a concrete failing test proves its existing exact-identity gate is insufficient.

- [ ] **Step 1: Implement stale-head gate**

```python
def assert_current_head(self, bound_head_sha: str, current_head_sha: str) -> None:
    validate_git_sha(bound_head_sha)
    validate_git_sha(current_head_sha)
    if bound_head_sha != current_head_sha:
        raise QuantumManifoldError("STALE_RESULT_REQUIRES_REBASE")
```

No network lookup is performed in this function. External ancestry/current-head facts are explicit inputs.

- [ ] **Step 2: Implement authority-zero proposal postconditions**

`build_proposal` must construct the three fields as constants, never caller values:

```python
authority_effect="NONE"
can_admit_claim=False
can_advance_authority=False
```

No API is exposed that converts a scheduler proposal into `AEGIS_EXECUTION_IDENTITY_JSON`, an approval, or an Automaton-3 `ADMIT`.

If a caller attempts to pass an authority effect other than `NONE` through canonical proposal input/verification, raise `AUTHORITY_TUNNELING_ATTEMPT`.

- [ ] **Step 3: Test the actual authority-client boundary**

Patch the environment so no valid `AEGIS_EXECUTION_IDENTITY_JSON` exists, include the scheduler proposal digest inside an otherwise ordinary action payload, invoke `authorize_from_environment`, and assert the result is DENIED because identity is unavailable/invalid. This demonstrates that a scheduler proposal cannot substitute for execution identity.

Do not assert that Automaton-3 must reject every action that merely references a scheduler proposal; a separately valid identity/policy may legitimately authorize an action, with authority originating only from Automaton-3.

- [ ] **Step 4: Run targeted tests**

```bash
python -m pytest -q \
  harness/tests/test_quantummanifold_scheduler_phase1.py::test_stale_exact_head_rejected \
  harness/tests/test_quantummanifold_scheduler_phase1.py::test_authority_tunneling_rejected
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/sdk/quantummanifold_scheduler.py harness/tests/test_quantummanifold_scheduler_phase1.py
git commit -m "feat(qm): enforce stale and authority-zero dispatch boundaries"
```

---

### Task 5: Implement exact fixed-point ranking and deterministic proposal serialization

**Files:**
- Modify: `harness/sdk/quantummanifold_scheduler.py`
- Modify: `harness/tests/test_quantummanifold_scheduler_phase1.py`

**Interfaces:**
- Produces `mul_ppm`, exact cost/score computation, deterministic candidate ordering, canonical proposal bytes/digest helpers.

- [ ] **Step 1: Add tests for numeric domain and digest/non-arithmetic separation**

Test that floats, negative values, booleans-as-integers, values over `MAX_SAFE_CANONICAL_INT`, and digest-to-int scoring attempts are rejected. Test exact floor behavior for `mul_ppm` and ranking score.

- [ ] **Step 2: Implement integer primitives**

```python
def mul_ppm(x: int, y: int) -> int:
    validate_non_negative_int(x)
    validate_non_negative_int(y)
    return (x * y) // PPM
```

Compute cost exactly as parent spec §4.6 and score exactly as §4.2. Range-check canonical serialized results.

- [ ] **Step 3: Implement deterministic tie-break**

Sort key:

```python
(-ranking_score_ppm, -closure_leverage_ppm, -falsification_value_ppm, cost_ppm, candidate_action_digest)
```

Reject duplicate action digests when canonical action content differs.

- [ ] **Step 4: Implement canonical proposal serialization**

Use `json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")`. Repeat the same scheduling input at least three times and assert byte-identical output.

- [ ] **Step 5: Run all QM tests**

```bash
python -m pytest -q harness/tests/test_quantummanifold_scheduler_phase1.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/sdk/quantummanifold_scheduler.py harness/tests/test_quantummanifold_scheduler_phase1.py
git commit -m "feat(qm): add deterministic fixed-point scheduler ranking"
```

---

### Task 6: Produce final same-head integration GREEN evidence

**Files:**
- Modify only if evidence proves necessary: `.github/workflows/quantummanifold-scheduler-phase1.yml`
- Do not modify production code after the final evidence candidate is chosen.

**Interfaces:**
- Produces exact-head `AEGIS_QUANTUMMANIFOLD_PHASE1_ATTESTATION_V1` and artifact.

- [ ] **Step 1: Ensure workflow receipt binds executed surfaces**

Receipt hashes must include:

```text
harness/policies/quantummanifold-scheduler.v1.json
harness/sdk/quantummanifold_scheduler.py
harness/tests/test_quantummanifold_scheduler_phase1.py
harness/sdk/meaning_heritage.py
harness/sdk/morphisms.py
harness/sdk/heritage_composition_base.py
harness/sdk/heritage_composition.py
```

It must also record both audited parent SHAs and `parent_ancestry_asserted=true`.

- [ ] **Step 2: Run/observe exact-head workflow**

Required same-head results:

```text
Focused QuantumManifold suite = PASS
Inherited MHP suite           = PASS
Exact checkout                = PASS
Both ancestor assertions      = PASS
Receipt emission              = PASS
Artifact upload               = PASS
Final job conclusion          = SUCCESS
```

- [ ] **Step 3: Fetch and verify artifact metadata**

Record run ID, exact head, receipt SHA-256, artifact ID, artifact SHA-256, policy SHA-256, scheduler kernel SHA-256, test-contract SHA-256, MHP kernel SHA map and pytest-log SHA-256.

- [ ] **Step 4: Check same-head repository regression lanes**

Fetch same-head workflow/status census. In particular record Kernel One and Coordinator Authority results if triggered. Do not convert `SKIPPED` Agent Dispatch into a failure if its configured behavior is a no-op for this branch.

- [ ] **Step 5: Record external blockers separately**

The final status must say, independently of QM GREEN:

```text
TRUSTED_COGNITIVE_ADMISSION    = current observed status; expected blocked until authorized refresh
REPOSITORY_MERGE_ENFORCEMENT   = NOT_ACTIVE unless fresh repository evidence proves otherwise
REPOSITORY_ADMISSION           = NOT_ESTABLISHED unless a separate authority path establishes it
```

- [ ] **Step 6: Do not merge**

Leave the branch/PR unmerged until the operator explicitly authorizes a merge. GREEN exact-head evidence is not merge/admission authority.
