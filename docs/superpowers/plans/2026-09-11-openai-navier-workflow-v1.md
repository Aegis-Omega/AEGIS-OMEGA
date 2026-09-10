# AEGIS Ω OpenAI Navier–Stokes Research Workflow V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the smallest governed orchestration primitive for Navier–Stokes research: deterministic evidence receipts, bounded portfolio routing, provenance-preserving cross-pollination, and a read-only OpenAI/Codex candidate-generation workflow.

**Architecture:** The implementation is split into three deterministic Python units plus one GitHub Actions entry point. Model output is always candidate-only; epistemic status is carried only by explicit receipt transitions whose authority is capped by the weakest verified transition. The workflow is manual/read-only and cannot push, merge, deploy, mutate issues/PRs, or modify constitutional state.

**Tech Stack:** Python 3.12 standard library, pytest, SHA-256 canonical JSON compatible with AEGIS repository conventions, GitHub Actions, OpenAI Codex Action/Responses API boundary.

**Spec:** `docs/superpowers/specs/2026-09-11-openai-navier-workflow-design.md`

## Global Constraints

- `admitted_authority <= weakest_verified_transition`.
- Surrogate results never promote the target Navier–Stokes claim.
- Numerical/symbolic evidence never closes a theorem.
- Caller-authored `VERIFIED` strings have no authority.
- Cross-pollination must preserve source artifact digests, assumptions, conflicts, and open obligations.
- Exact-head mismatch blocks admission.
- OpenAI/Codex output is `CANDIDATE_ONLY` until downstream checks pass.
- The hosted OpenAI lane starts as `workflow_dispatch` only and uses least-privilege read permissions.
- No push, merge, release, deployment, PR/issue mutation, `.claude.json` mutation, or `INTEGRATION_LEDGER.md` mutation.
- Authority-bearing numeric policy fields use integers; canonical serialization rejects floats.

---

### Task 1: Deterministic Candidate and Receipt Schema

**Files:**
- Create: `navier_workflow/__init__.py`
- Create: `navier_workflow/schema_v1.py`
- Create: `navier_workflow/test_schema_v1.py`

**Interfaces:**
- Produces: `canonical_json(value: object) -> bytes`
- Produces: `sha256_digest(value: object) -> str`
- Produces: `validate_candidate(candidate: dict) -> dict`
- Produces: `validate_receipt(receipt: dict) -> dict`
- Produces: `transition_allowed(from_state: str, to_state: str) -> bool`

- [ ] **Step 1: Write failing schema tests**

```python
from navier_workflow.schema_v1 import (
    canonical_json,
    sha256_digest,
    validate_candidate,
    validate_receipt,
    transition_allowed,
)


def base_candidate():
    return {
        "candidate_id": "cand-1",
        "lane_id": "target-positive",
        "claim": "conditional estimate",
        "claim_scope": "SURROGATE_ONLY",
        "assumptions": ["smooth compactly supported seed"],
        "source_coordinates": ["paper:1#lemma-2"],
        "dependencies": ["dep-a"],
        "open_obligations": ["dep-a"],
        "known_failure_modes": [],
        "falsification_attempts": [],
        "artifact_digest": "a" * 64,
    }


def test_canonical_json_rejects_float():
    import pytest
    with pytest.raises(ValueError, match="floats are forbidden"):
        canonical_json({"score": 0.5})


def test_canonical_digest_is_order_independent():
    assert sha256_digest({"b": 2, "a": 1}) == sha256_digest({"a": 1, "b": 2})


def test_open_dependency_blocks_target_theorem_closed():
    receipt = {
        "schema": "AEGIS_NAVIER_RECEIPT_V1",
        "transition_id": "t1",
        "candidate_id": "cand-1",
        "from_state": "FORMALIZATION",
        "to_state": "TARGET_THEOREM_CLOSED",
        "exact_head_sha": "b" * 40,
        "input_artifact_digests": ["a" * 64],
        "output_artifact_digest": "c" * 64,
        "assumptions": [],
        "open_obligations": ["unclosed-lemma"],
        "checks": ["lean_kernel_pass"],
        "verifier_identity": "verifier-B",
        "producer_identity": "worker-A",
        "verifier_independence_class": "INDEPENDENT",
        "decision": "ALLOW",
        "claim_promotion": "TARGET",
        "authority_effect": "TARGET",
        "previous_receipt_digest": "d" * 64,
    }
    import pytest
    with pytest.raises(ValueError, match="open obligations"):
        validate_receipt(receipt)


def test_self_verification_is_rejected():
    receipt = {
        "schema": "AEGIS_NAVIER_RECEIPT_V1",
        "transition_id": "t1",
        "candidate_id": "cand-1",
        "from_state": "ADVERSARIAL_REVIEW",
        "to_state": "FORMALIZATION",
        "exact_head_sha": "b" * 40,
        "input_artifact_digests": ["a" * 64],
        "output_artifact_digest": "c" * 64,
        "assumptions": [],
        "open_obligations": [],
        "checks": [],
        "verifier_identity": "worker-A",
        "producer_identity": "worker-A",
        "verifier_independence_class": "INDEPENDENT",
        "decision": "ALLOW",
        "claim_promotion": "NONE",
        "authority_effect": "NONE",
        "previous_receipt_digest": "d" * 64,
    }
    import pytest
    with pytest.raises(ValueError, match="independently verify its own artifact"):
        validate_receipt(receipt)


def test_invalid_transition_is_rejected():
    assert transition_allowed("PROPOSED", "TARGET_THEOREM_CLOSED") is False
```

- [ ] **Step 2: Run schema tests and verify RED**

Run: `python -m pytest navier_workflow/test_schema_v1.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'navier_workflow.schema_v1'`.

- [ ] **Step 3: Implement minimal deterministic schema**

```python
# navier_workflow/schema_v1.py
import hashlib
import json
import unicodedata

ALLOWED_TRANSITIONS = {
    "PROPOSED": {"TRIAGED", "FALSIFIED"},
    "TRIAGED": {"ACTIVE_RESEARCH", "FALSIFIED", "STALE"},
    "ACTIVE_RESEARCH": {"CANDIDATE_RESULT", "FALSIFIED", "DEPENDENCY_OPEN"},
    "CANDIDATE_RESULT": {"ADVERSARIAL_REVIEW", "FALSIFIED", "DEPENDENCY_OPEN"},
    "ADVERSARIAL_REVIEW": {"FORMALIZATION", "FALSIFIED", "DEPENDENCY_OPEN"},
    "FORMALIZATION": {"INDEPENDENT_REPLAY", "FORMALIZATION_FAILED", "DEPENDENCY_OPEN"},
    "INDEPENDENT_REPLAY": {"ADMISSION_REVIEW", "REPLAY_FAILED", "DEPENDENCY_OPEN"},
    "ADMISSION_REVIEW": {"TARGET_THEOREM_CLOSED", "DEPENDENCY_OPEN", "FALSIFIED"},
}


def _reject_floats(value):
    if isinstance(value, float):
        raise ValueError("floats are forbidden in canonical authority-bearing structures")
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_floats(key)
            _reject_floats(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_floats(item)


def canonical_json(value: object) -> bytes:
    _reject_floats(value)
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return unicodedata.normalize("NFC", text).encode("utf-8")


def sha256_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def transition_allowed(from_state: str, to_state: str) -> bool:
    return to_state in ALLOWED_TRANSITIONS.get(from_state, set())


def validate_candidate(candidate: dict) -> dict:
    required = {
        "candidate_id", "lane_id", "claim", "claim_scope", "assumptions",
        "source_coordinates", "dependencies", "open_obligations",
        "known_failure_modes", "falsification_attempts", "artifact_digest",
    }
    missing = sorted(required - candidate.keys())
    if missing:
        raise ValueError(f"missing candidate fields: {missing}")
    canonical_json(candidate)
    return dict(candidate)


def validate_receipt(receipt: dict) -> dict:
    required = {
        "schema", "transition_id", "candidate_id", "from_state", "to_state",
        "exact_head_sha", "input_artifact_digests", "output_artifact_digest",
        "assumptions", "open_obligations", "checks", "verifier_identity",
        "producer_identity", "verifier_independence_class", "decision",
        "claim_promotion", "authority_effect", "previous_receipt_digest",
    }
    missing = sorted(required - receipt.keys())
    if missing:
        raise ValueError(f"missing receipt fields: {missing}")
    if not transition_allowed(receipt["from_state"], receipt["to_state"]):
        raise ValueError("invalid state transition")
    if receipt["verifier_identity"] == receipt["producer_identity"] and receipt["verifier_independence_class"] == "INDEPENDENT":
        raise ValueError("a verifier cannot independently verify its own artifact")
    if receipt["to_state"] == "TARGET_THEOREM_CLOSED" and receipt["open_obligations"]:
        raise ValueError("open obligations block target closure")
    canonical_json(receipt)
    return dict(receipt)
```

- [ ] **Step 4: Run schema tests and verify GREEN**

Run: `python -m pytest navier_workflow/test_schema_v1.py -q`
Expected: all tests PASS.

- [ ] **Step 5: Commit schema slice**

Commit message: `feat(navier): add deterministic candidate and receipt schema`

---

### Task 2: Bounded Portfolio Controller

**Files:**
- Create: `navier_workflow/portfolio_v1.py`
- Create: `navier_workflow/test_portfolio_v1.py`

**Interfaces:**
- Consumes: canonical integer-only structures from Task 1.
- Produces: `Lane` dataclass.
- Produces: `priority_score(lane: Lane) -> int`.
- Produces: `allocate_budget(lanes: list[Lane], total_budget: int, diversity_floor: int) -> dict[str, int]`.

- [ ] **Step 1: Write failing portfolio tests**

```python
from navier_workflow.portfolio_v1 import Lane, allocate_budget, priority_score


def test_priority_does_not_mutate_epistemic_status():
    lane = Lane("a", "TARGET", 9, 8, 7, 2, 1, "OPEN")
    before = lane.status
    assert priority_score(lane) == 21
    assert lane.status == before


def test_allocator_preserves_diversity_floor():
    lanes = [
        Lane("a", "TARGET", 10, 10, 10, 0, 0, "OPEN"),
        Lane("b", "ATTACK", 0, 0, 0, 9, 9, "OPEN"),
        Lane("c", "SURROGATE", 1, 1, 1, 4, 4, "OPEN"),
    ]
    result = allocate_budget(lanes, total_budget=30, diversity_floor=3)
    assert sum(result.values()) == 30
    assert all(value >= 3 for value in result.values())


def test_falsified_lane_gets_no_exploration_budget():
    lanes = [
        Lane("a", "TARGET", 1, 1, 1, 0, 0, "OPEN"),
        Lane("dead", "SURROGATE", 99, 99, 99, 0, 0, "FALSIFIED"),
    ]
    result = allocate_budget(lanes, total_budget=10, diversity_floor=2)
    assert result["dead"] == 0
    assert result["a"] == 10
```

- [ ] **Step 2: Run portfolio tests and verify RED**

Run: `python -m pytest navier_workflow/test_portfolio_v1.py -q`
Expected: FAIL because `portfolio_v1` does not exist.

- [ ] **Step 3: Implement deterministic integer allocator**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Lane:
    lane_id: str
    problem_class: str
    progress_signal: int
    transfer_utility: int
    verification_density: int
    open_obligation_penalty: int
    correlated_failure_penalty: int
    status: str


def priority_score(lane: Lane) -> int:
    return max(0, lane.progress_signal + lane.transfer_utility + lane.verification_density - lane.open_obligation_penalty - lane.correlated_failure_penalty)


def allocate_budget(lanes, total_budget: int, diversity_floor: int):
    active = [lane for lane in lanes if lane.status != "FALSIFIED"]
    if total_budget < diversity_floor * len(active):
        raise ValueError("budget below diversity floor")
    result = {lane.lane_id: 0 for lane in lanes}
    for lane in active:
        result[lane.lane_id] = diversity_floor
    remaining = total_budget - diversity_floor * len(active)
    ranked = sorted(active, key=lambda lane: (-priority_score(lane), lane.lane_id))
    if ranked:
        for index in range(remaining):
            result[ranked[index % len(ranked)].lane_id] += 1
    return result
```

- [ ] **Step 4: Run portfolio tests and verify GREEN**

Run: `python -m pytest navier_workflow/test_portfolio_v1.py -q`
Expected: all tests PASS.

- [ ] **Step 5: Commit portfolio slice**

Commit message: `feat(navier): add bounded deterministic portfolio allocator`

---

### Task 3: Provenance-Preserving Cross-Pollination

**Files:**
- Create: `navier_workflow/crosspollination_v1.py`
- Create: `navier_workflow/test_crosspollination_v1.py`

**Interfaces:**
- Consumes: validated candidate artifacts.
- Produces: `synthesize_shared_state(candidates: list[dict]) -> dict`.
- Output keeps assumptions/conflicts/provenance grouped by artifact digest rather than flattening them.

- [ ] **Step 1: Write failing cross-pollination tests**

```python
from navier_workflow.crosspollination_v1 import synthesize_shared_state


def candidate(cid, digest, assumptions, obligations):
    return {
        "candidate_id": cid,
        "lane_id": cid,
        "claim": f"claim-{cid}",
        "claim_scope": "SURROGATE_ONLY",
        "assumptions": assumptions,
        "source_coordinates": [f"source:{cid}"],
        "dependencies": [],
        "open_obligations": obligations,
        "known_failure_modes": [],
        "falsification_attempts": [],
        "artifact_digest": digest,
    }


def test_synthesis_preserves_assumptions_and_provenance():
    a = candidate("a", "a" * 64, ["periodic"], ["lemma-A"])
    b = candidate("b", "b" * 64, ["whole-space"], [])
    shared = synthesize_shared_state([a, b])
    assert shared["imports"][0]["artifact_digest"] == "a" * 64
    assert shared["imports"][0]["assumptions"] == ["periodic"]
    assert shared["imports"][1]["assumptions"] == ["whole-space"]


def test_conflicting_assumptions_are_not_flattened():
    a = candidate("a", "a" * 64, ["periodic"], [])
    b = candidate("b", "b" * 64, ["whole-space"], [])
    shared = synthesize_shared_state([a, b])
    assert shared["assumption_sets"] == {
        "a" * 64: ["periodic"],
        "b" * 64: ["whole-space"],
    }


def test_surrogate_import_cannot_promote_target():
    a = candidate("a", "a" * 64, [], [])
    shared = synthesize_shared_state([a])
    assert shared["claim_promotion"] == "BLOCKED"
    assert shared["authority_effect"] == "NONE"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest navier_workflow/test_crosspollination_v1.py -q`
Expected: FAIL because `crosspollination_v1` does not exist.

- [ ] **Step 3: Implement minimal provenance-preserving synthesis**

```python
from navier_workflow.schema_v1 import sha256_digest, validate_candidate


def synthesize_shared_state(candidates: list[dict]) -> dict:
    validated = [validate_candidate(candidate) for candidate in candidates]
    ordered = sorted(validated, key=lambda item: item["artifact_digest"])
    imports = [
        {
            "candidate_id": item["candidate_id"],
            "artifact_digest": item["artifact_digest"],
            "claim": item["claim"],
            "claim_scope": item["claim_scope"],
            "assumptions": list(item["assumptions"]),
            "source_coordinates": list(item["source_coordinates"]),
            "open_obligations": list(item["open_obligations"]),
        }
        for item in ordered
    ]
    state = {
        "schema": "AEGIS_NAVIER_SHARED_STATE_V1",
        "imports": imports,
        "assumption_sets": {item["artifact_digest"]: list(item["assumptions"]) for item in ordered},
        "claim_promotion": "BLOCKED",
        "authority_effect": "NONE",
    }
    state["state_digest"] = sha256_digest(state)
    return state
```

- [ ] **Step 4: Run cross-pollination tests and verify GREEN**

Run: `python -m pytest navier_workflow/test_crosspollination_v1.py -q`
Expected: all tests PASS.

- [ ] **Step 5: Commit cross-pollination slice**

Commit message: `feat(navier): preserve provenance across research synthesis`

---

### Task 4: Admission Falsification Matrix

**Files:**
- Create: `navier_workflow/test_admission_v1.py`

**Interfaces:**
- Consumes Task 1 state/receipt validation.
- Establishes negative guarantees for theorem closure.

- [ ] **Step 1: Add adversarial tests for authority leakage**

```python
import pytest
from navier_workflow.schema_v1 import validate_receipt


def receipt(**overrides):
    value = {
        "schema": "AEGIS_NAVIER_RECEIPT_V1",
        "transition_id": "t",
        "candidate_id": "c",
        "from_state": "ADMISSION_REVIEW",
        "to_state": "TARGET_THEOREM_CLOSED",
        "exact_head_sha": "e" * 40,
        "input_artifact_digests": ["a" * 64],
        "output_artifact_digest": "b" * 64,
        "assumptions": [],
        "open_obligations": [],
        "checks": ["formal_kernel_pass", "independent_replay_pass", "exact_head_fresh"],
        "verifier_identity": "verifier-B",
        "producer_identity": "worker-A",
        "verifier_independence_class": "INDEPENDENT",
        "decision": "ALLOW",
        "claim_promotion": "TARGET",
        "authority_effect": "ELIGIBLE_FOR_ADMISSION_REVIEW_ONLY",
        "previous_receipt_digest": "c" * 64,
    }
    value.update(overrides)
    return value


def test_caller_verified_string_does_not_replace_required_checks():
    with pytest.raises(ValueError, match="required target-closure checks"):
        validate_receipt(receipt(checks=["VERIFIED"]))


def test_stale_head_blocks_target_closure():
    with pytest.raises(ValueError, match="exact-head freshness"):
        validate_receipt(receipt(checks=["formal_kernel_pass", "independent_replay_pass"]))


def test_numerical_evidence_cannot_close_target():
    with pytest.raises(ValueError, match="formal kernel"):
        validate_receipt(receipt(checks=["numerical_simulation_pass", "independent_replay_pass", "exact_head_fresh"]))
```

- [ ] **Step 2: Run admission tests and verify RED**

Run: `python -m pytest navier_workflow/test_admission_v1.py -q`
Expected: FAIL because Task 1 validator does not yet enforce all target-closure check requirements.

- [ ] **Step 3: Extend only the target-closure validation path**

Add to `validate_receipt`:

```python
if receipt["to_state"] == "TARGET_THEOREM_CLOSED":
    checks = set(receipt["checks"])
    required = {"formal_kernel_pass", "independent_replay_pass", "exact_head_fresh"}
    missing = required - checks
    if "formal_kernel_pass" in missing:
        raise ValueError("formal kernel evidence is required for target closure")
    if "exact_head_fresh" in missing:
        raise ValueError("exact-head freshness is required for target closure")
    if missing:
        raise ValueError(f"required target-closure checks missing: {sorted(missing)}")
```

- [ ] **Step 4: Run the full Python lane**

Run: `python -m pytest navier_workflow -q`
Expected: all tests PASS.

- [ ] **Step 5: Commit admission hardening**

Commit message: `test(navier): enforce fail-closed theorem admission matrix`

---

### Task 5: Read-Only Hosted OpenAI/Codex Candidate Workflow

**Files:**
- Create: `.github/workflows/navier-openai-research.yml`
- Create: `navier_workflow/openai_candidate_schema.json`
- Create: `navier_workflow/test_workflow_v1.py`

**Interfaces:**
- GitHub Actions trigger: `workflow_dispatch` only.
- Repository permissions: `contents: read`.
- OpenAI model output: JSON candidate artifact only.
- No mutation permissions or mutation steps.

- [ ] **Step 1: Add static workflow security tests before workflow exists**

```python
from pathlib import Path


def test_workflow_is_manual_and_read_only():
    text = Path(".github/workflows/navier-openai-research.yml").read_text()
    assert "workflow_dispatch:" in text
    assert "pull_request:" not in text
    assert "issues:" not in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "pull-requests: write" not in text
    assert "issues: write" not in text


def test_workflow_cannot_push_or_merge():
    text = Path(".github/workflows/navier-openai-research.yml").read_text()
    forbidden = ["git push", "gh pr merge", "git merge", "gh release", "vercel"]
    assert all(token not in text.lower() for token in forbidden)


def test_workflow_marks_model_output_candidate_only():
    text = Path(".github/workflows/navier-openai-research.yml").read_text()
    assert "CANDIDATE_ONLY" in text
    assert "authority_effect=NONE" in text
```

- [ ] **Step 2: Run workflow tests and verify RED**

Run: `python -m pytest navier_workflow/test_workflow_v1.py -q`
Expected: FAIL because `.github/workflows/navier-openai-research.yml` does not exist.

- [ ] **Step 3: Create output schema and manual read-only workflow**

The JSON schema must require:

```json
{
  "candidate_id": "string",
  "lane_id": "string",
  "claim": "string",
  "claim_scope": "TARGET|SURROGATE|ATTACK|COUNTEREXAMPLE",
  "assumptions": ["string"],
  "source_coordinates": ["string"],
  "dependencies": ["string"],
  "open_obligations": ["string"],
  "known_failure_modes": ["string"],
  "falsification_attempts": ["string"],
  "status": "CANDIDATE_ONLY",
  "authority_effect": "NONE"
}
```

Workflow constraints:

```yaml
name: AEGIS Navier OpenAI Research

on:
  workflow_dispatch:
    inputs:
      research_lane:
        description: "Bounded research lane identifier"
        required: true
        type: choice
        options:
          - target-positive
          - counterexample-attack
          - surrogate-euler
          - apriori-estimates

permissions:
  contents: read

jobs:
  candidate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Run deterministic repository tests first
        run: python -m pytest navier_workflow -q
      - name: OpenAI candidate generation
        uses: openai/codex-action@main
        with:
          openai-api-key: ${{ secrets.OPENAI_API_KEY }}
          permission-profile: :read-only
          prompt: |
            Produce one bounded Navier–Stokes research candidate for lane ${{ inputs.research_lane }}.
            Treat all model output as CANDIDATE_ONLY.
            Do not claim theorem closure. Preserve assumptions, dependencies,
            falsification attempts, and source coordinates. authority_effect=NONE.
```

No write token is granted. A future production revision should pin the Codex Action to an audited immutable commit SHA before admission.

- [ ] **Step 4: Run static workflow tests and the full lane**

Run: `python -m pytest navier_workflow -q`
Expected: all tests PASS.

- [ ] **Step 5: Commit hosted workflow slice**

Commit message: `ci(navier): add manual read-only OpenAI research lane`

---

### Task 6: Exact-Head Verification and Bounded Disposition

**Files:**
- No new production files unless a test reveals a defect.

**Interfaces:**
- Consumes exact branch HEAD and hosted GitHub Actions run.
- Produces a bounded verification disposition only.

- [ ] **Step 1: Trigger/observe hosted tests at the exact candidate HEAD**

Expected hosted gates:

```text
schema_tests = PASS
portfolio_tests = PASS
crosspollination_tests = PASS
admission_falsification_tests = PASS
workflow_security_tests = PASS
```

- [ ] **Step 2: Verify branch ancestry and changed-file boundary**

Expected:

```text
base = main exact head used when branch was created
behind = 0 unless main advanced after branch creation
changed files limited to navier_workflow/, workflow, spec, plan
```

- [ ] **Step 3: Inspect commit signature and repository-wide checks**

Do not infer merge authority from dedicated-lane success. Record signature and unrelated repository blockers separately.

- [ ] **Step 4: Emit final bounded disposition**

```text
decision = HOLD_RESEARCH_ONLY
portfolio_orchestration = IMPLEMENTED_AND_TESTED
cross_pollination = PROVENANCE_PRESERVING_IN_TESTED_SCOPE
receipt_chain = DETERMINISTIC_AND_TAMPER_EVIDENT
openai_worker = READ_ONLY_CANDIDATE_PRODUCER
formal_proof_claim = NOT_MADE
navier_stokes_status = OPEN_UNLESS_TARGET_CLOSURE_EVIDENCE_EXISTS
claim_promotion = BLOCKED
authority_effect = NONE
merge = NOT_PERFORMED
```

- [ ] **Step 5: Do not open or merge a PR**

The output of V1 is the exact-head research branch plus verification evidence. PR/merge is a separate operator-authorized transition.
