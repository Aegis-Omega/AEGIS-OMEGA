# Self-Improvement Loop V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic evidence-only verifier for bounded capability-improvement experiments that cannot mint authority.

**Architecture:** Add one focused standard-library Python kernel under `harness/sdk/` and one adversarial test module. Candidate generation remains outside the authority boundary; the kernel verifies frozen experiment bindings and a trusted independent evaluation receipt, then issues only `authority_class == "NONE"` evidence.

**Tech Stack:** Python 3.12 standard library, repository-local `canonical_hash`, pytest 8.3.5, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-31-self-improvement-loop-v1-design.md`

## Global Constraints

- `harness/sdk/sovereign_execution.py` remains the single authority-decision path.
- The self-improvement module MUST NOT issue admission, execution, merge, deploy, or authority decisions.
- Successful receipts MUST carry `authority_class == "NONE"`.
- Verification-bound metric values MUST be integer micro-units, never float.
- All deterministic roots MUST use domain-separated `canonical_hash`.
- Missing trust/provenance or binding mismatch MUST fail closed.
- Candidate access to the frozen withheld-label root MUST fail closed.
- Independent evaluator and verifier roots MUST be frozen in the experiment contract.

---

### Task 1: Preregister the adversarial contract and exact-head workflow

**Files:**
- Create: `harness/tests/test_self_improvement.py`
- Create: `.github/workflows/self-improvement-loop.yml`

**Interfaces:**
- Consumes: `canonical_hash(domain: str, value: Any) -> str` from `harness.sdk.sovereign_execution`.
- Produces expected API names for Task 2: `MetricDirection`, `MetricRuleV1`, `MetricObservationV1`, `HypothesisEnvelopeV1`, `ExperimentContractV1`, `CandidateObservationV1`, `EvaluationReceiptV1`, `ImprovementVerifierV1`, and `ImprovementReceiptV1`.

- [ ] **Step 1: Write failing tests**

Tests import the Task 2 API and cover these real behaviors:

```python
def test_valid_independent_improvement_issues_evidence_only_receipt():
    result, receipt = verifier.verify_and_issue(...)
    assert result.status == "PASS"
    assert receipt is not None
    assert receipt.authority_class == "NONE"


def test_withheld_label_access_fails_closed():
    result, receipt = verifier.verify_and_issue(candidate_with_withheld_access, ...)
    assert receipt is None
    assert "WITHHELD_LABEL_ACCESS_DETECTED" in result.error_codes


def test_evaluation_receipt_cannot_be_spliced_to_different_candidate():
    result, receipt = verifier.verify_and_issue(spliced_candidate, ...)
    assert receipt is None
    assert "EVALUATION_BINDING_FAILURE" in result.error_codes


def test_candidate_cannot_select_different_evaluator():
    result, receipt = verifier_with_wrong_evaluator.verify_and_issue(...)
    assert receipt is None
    assert "EVALUATOR_BINDING_FAILURE" in result.error_codes


def test_metric_regression_fails_preregistered_gate():
    result, receipt = verifier.verify_and_issue(regressing_evaluation, ...)
    assert receipt is None
    assert "METRIC_THRESHOLD_FAILURE" in result.error_codes
```

The valid case uses a trusted in-memory evaluation store and asserts that changing evaluator/candidate bindings changes receipt roots.

- [ ] **Step 2: Add the exact-head workflow**

Create `.github/workflows/self-improvement-loop.yml` with:

```yaml
name: Self-Improvement Loop V1

on:
  push:
    branches: [feat/self-improvement-loop-v1]
    paths:
      - 'harness/sdk/self_improvement.py'
      - 'harness/tests/test_self_improvement.py'
      - '.github/workflows/self-improvement-loop.yml'
      - 'docs/superpowers/specs/2026-08-31-self-improvement-loop-v1-design.md'
      - 'docs/superpowers/plans/2026-08-31-self-improvement-loop-v1.md'
  pull_request:
    paths:
      - 'harness/sdk/self_improvement.py'
      - 'harness/tests/test_self_improvement.py'
      - '.github/workflows/self-improvement-loop.yml'

permissions:
  contents: read

jobs:
  verify:
    name: aegis / self-improvement-loop-v1
    runs-on: ubuntu-latest
    timeout-minutes: 10
    env:
      CANDIDATE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ env.CANDIDATE_SHA }}
          fetch-depth: 1
      - run: test "$(git rev-parse HEAD)" = "$CANDIDATE_SHA"
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install --disable-pip-version-check pytest==8.3.5
      - run: python -m py_compile harness/sdk/self_improvement.py harness/tests/test_self_improvement.py
      - run: python -m pytest -q harness/tests/test_self_improvement.py
```

- [ ] **Step 3: Verify RED**

Run via the branch workflow. Expected result before Task 2: FAIL because `harness.sdk.self_improvement` does not yet exist. The failure is the preregistered witness; do not weaken the tests.

- [ ] **Step 4: Commit**

Commit message:

```text
test(self-improvement): preregister fail-closed verifier contract
```

---

### Task 2: Implement the deterministic improvement evidence kernel

**Files:**
- Create: `harness/sdk/self_improvement.py`
- Test: `harness/tests/test_self_improvement.py`

**Interfaces:**
- Consumes: `canonical_hash` from `harness.sdk.sovereign_execution`.
- Produces:

```python
class MetricDirection(str, Enum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"

@dataclass(frozen=True)
class MetricRuleV1:
    metric_id: str
    direction: MetricDirection
    minimum_improvement_micros: int

@dataclass(frozen=True)
class MetricObservationV1:
    metric_id: str
    value_micros: int

@dataclass(frozen=True)
class HypothesisEnvelopeV1: ...
@dataclass(frozen=True)
class ExperimentContractV1: ...
@dataclass(frozen=True)
class CandidateObservationV1: ...
@dataclass(frozen=True)
class EvaluationReceiptV1: ...
@dataclass(frozen=True)
class ImprovementVerificationResultV1: ...
@dataclass(frozen=True)
class ImprovementReceiptV1: ...

class TrustedEvaluationReceiptStore(Protocol):
    def fetch_verified(self, root: str) -> EvaluationReceiptV1 | None: ...

class ImprovementVerifierV1:
    def verify_and_issue(
        self,
        *,
        hypothesis: HypothesisEnvelopeV1,
        contract: ExperimentContractV1,
        candidate: CandidateObservationV1,
        evaluation_receipt_root: str,
    ) -> tuple[ImprovementVerificationResultV1, ImprovementReceiptV1 | None]: ...
```

- [ ] **Step 1: Implement strict validators and domain-separated roots**

Use exact 64-lowercase-hex validation, non-empty safe IDs, integer-only metric values/thresholds, unique metric IDs, unique access roots, and deterministic sorted serialization.

- [ ] **Step 2: Implement frozen binding checks**

`ImprovementVerifierV1.verify_and_issue` must compare hypothesis, contract, baseline, environment, verifier, policy, trial index, and candidate roots before scoring any metric.

- [ ] **Step 3: Implement trusted evaluation replay**

Fetch only through `TrustedEvaluationReceiptStore`. Deny if missing, root-spliced, evaluator-mismatched, evaluator-policy-mismatched, contaminated, non-PASS, or bound to different contract/baseline/candidate/evaluation/environment roots.

- [ ] **Step 4: Implement anti-cheating gate**

Deny with `WITHHELD_LABEL_ACCESS_DETECTED` when `contract.withheld_labels_root` appears in `candidate.accessed_roots`.

- [ ] **Step 5: Implement deterministic metric gate**

Construct exact maps from baseline/candidate metric tuples. Require the metric key set to equal the preregistered rule set. For each rule calculate signed improvement:

```python
if rule.direction == MetricDirection.MAXIMIZE:
    delta = candidate_value - baseline_value
else:
    delta = baseline_value - candidate_value
```

Deny with `METRIC_THRESHOLD_FAILURE` when `delta < rule.minimum_improvement_micros`.

- [ ] **Step 6: Issue evidence-only receipt**

On zero errors, bind all evidence roots and sorted metric deltas into a verification root and return `ImprovementReceiptV1` whose `authority_class` is an `init=False` constant `"NONE"`.

- [ ] **Step 7: Verify GREEN**

Run the exact-head workflow. Expected: compile succeeds and all focused tests pass with zero failures.

- [ ] **Step 8: Commit**

Commit message:

```text
feat(self-improvement): add bounded evidence verifier kernel
```

---

### Task 3: Exact-head verification and stacked PR

**Files:**
- No production-code changes required if Task 2 is GREEN.
- Update PR body only after fresh exact-head evidence exists.

**Interfaces:**
- Consumes: exact Task 2 head SHA and GitHub Actions run IDs.
- Produces: stacked PR targeting `feat/mhp1-morphism-engine-v1`.

- [ ] **Step 1: Read the exact head and workflow results**

Require `aegis / self-improvement-loop-v1` to be SUCCESS at the exact candidate SHA. Record Kernel One / Coordinator Authority state separately; `Agent Dispatch` being SKIPPED is not treated as a verifier success or failure.

- [ ] **Step 2: Open a draft stacked PR**

Title:

```text
feat(self-improvement): add bounded evidence-only improvement verifier
```

Base: `feat/mhp1-morphism-engine-v1`

Head: `feat/self-improvement-loop-v1`

The body must state that the slice demonstrates deterministic bounded improvement verification only; it does not demonstrate recursive self-improvement, autonomous authority, AGI, Weil positivity, or RH.

- [ ] **Step 3: Preserve admission boundary**

Do not merge or enable auto-merge. Do not call the improvement receipt an admission record. Any canonical promotion remains external to this PR and to `harness/sdk/self_improvement.py`.

## Self-review

- Spec coverage: every authority, provenance, anti-splicing, evaluator, withheld-label, metric, and exact-head workflow requirement has a named task.
- Placeholder scan: no TODO/TBD/implicit implementation steps remain.
- Type consistency: all Task 1 test imports match Task 2 produced interfaces; Task 3 consumes only the exact-head evidence produced by Tasks 1–2.