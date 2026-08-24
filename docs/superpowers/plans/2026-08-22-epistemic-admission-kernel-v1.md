# Epistemic Admission Kernel v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed epistemic admission kernel that converts the Aug-02 debugging lexicon into executable claim-status, applicability, source-binding, retrieval, and bootstrap controls.

**Architecture:** A small pure-Python verifier in `harness/sdk` consumes typed dict/dataclass contracts and returns a deterministic `AdmissionDecisionV1`. A compact repo-local bootstrap is injected through Claude hooks, while a dedicated CI workflow runs the historical falsifiers against the exact candidate SHA. This layer constrains claim admission only; it does not grant external-effect or production authority.

**Tech Stack:** Python 3.12 stdlib (`dataclasses`, `enum`, `typing`), JSON Schema draft 2020-12, Bash/Claude hooks, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-22-epistemic-admission-kernel-v1-design.md`

## Global Constraints

- Canonical parent is `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`.
- Preserve CEL v1.1 research/epistemological scope; do not redefine Effect/Admission authority.
- Model output is evidence only, never authority.
- Historical validity and current applicability are separate fields.
- `search_miss != nonexistence`.
- `provenance_integrity != citation_entailment`.
- `chain_integrity != truth`, `chain_integrity != identity`, and `chain_integrity != consciousness`.
- All verifier outputs are deterministic over explicit inputs.
- No new mutable GitHub Action dependency may be introduced.

---

### Task 1: Claim/admission contracts and falsifiers

**Files:**
- Create: `harness/sdk/epistemic_admission.py`
- Create: `harness/tests/test_epistemic_admission.py`
- Create: `schemas/epistemic-admission-v1.schema.json`

**Interfaces:**
- Consumes: plain Python values supplied by callers; no network, git, clock, filesystem, or model calls.
- Produces: `ClaimStatus`, `FieldProvenance`, `Route`, `FailureLocus`, `SubjectBindingV1`, `LoadBearingFieldV1`, `SourceBindingV1`, `RetrievalObservationV1`, `EpistemicClaimV1`, `AdmissionDecisionV1`, and `evaluate_claim(claim, current_subject_sha=None) -> AdmissionDecisionV1`.

- [ ] **Step 1: Write failing falsifiers**

Create `harness/tests/test_epistemic_admission.py` with unittest cases asserting:

```python
from harness.sdk.epistemic_admission import (
    ClaimStatus, EpistemicClaimV1, FieldProvenance, LoadBearingFieldV1,
    RetrievalObservationV1, Route, SourceBindingV1, SubjectBindingV1,
    evaluate_claim,
)


def base_claim(**overrides):
    data = dict(
        claim_id="C-1",
        claim_text="candidate claim",
        status=ClaimStatus.VERIFIED,
        subject=SubjectBindingV1(subject_type="git_commit", subject_id="abc"),
        authority_scope="repo-state",
        evidence_window="run-1",
        load_bearing_fields=[],
        sources=[],
        retrieval_observations=[],
        verification_complete=True,
        historically_valid=True,
    )
    data.update(overrides)
    return EpistemicClaimV1(**data)


def test_declared_load_bearing_field_is_quarantined():
    claim = base_claim(load_bearing_fields=[
        LoadBearingFieldV1("current_head", "abc", True, FieldProvenance.DECLARED)
    ])
    assert evaluate_claim(claim, current_subject_sha="abc").route is Route.QUARANTINE


def test_historical_receipt_is_preserved_but_stale_head_is_quarantined():
    decision = evaluate_claim(base_claim(), current_subject_sha="def")
    assert decision.historically_valid is True
    assert decision.current_applicability is False
    assert decision.route is Route.QUARANTINE


def test_search_miss_cannot_establish_nonexistence():
    claim = base_claim(retrieval_observations=[
        RetrievalObservationV1(query="2607.24117", found=False, asserted_outcome="NONEXISTENT")
    ])
    assert evaluate_claim(claim, current_subject_sha="abc").route is Route.QUARANTINE


def test_provenance_pass_does_not_mask_entailment_fail():
    claim = base_claim(sources=[
        SourceBindingV1(source_id="S-1", provenance_integrity=True, entails_claim=False)
    ])
    d = evaluate_claim(claim, current_subject_sha="abc")
    assert d.route is Route.QUARANTINE
    assert "CITATION_ENTAILMENT_FAILURE" in {x.value for x in d.failure_loci}


def test_incomplete_verification_routes_review_not_serve():
    d = evaluate_claim(base_claim(verification_complete=False), current_subject_sha="abc")
    assert d.route is Route.REVIEW


def test_fully_bound_verified_claim_can_serve():
    d = evaluate_claim(base_claim(), current_subject_sha="abc")
    assert d.route is Route.SERVE
```

Add cases for incomplete enumeration and unresolved authorship when load-bearing.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python -m unittest harness.tests.test_epistemic_admission -v
```

Expected: import/module failure because `harness.sdk.epistemic_admission` does not exist.

- [ ] **Step 3: Implement minimal deterministic kernel**

Create enums/dataclasses and `evaluate_claim()` in `harness/sdk/epistemic_admission.py`. Rules must accumulate violations/failure loci deterministically, then choose route in precedence order `QUARANTINE > REVIEW > SERVE`.

Use no implicit environment state. `current_subject_sha` must be an explicit argument.

- [ ] **Step 4: Add JSON Schema mirror**

Create `schemas/epistemic-admission-v1.schema.json` with closed enums and required fields for serialized `EpistemicClaimV1` and `AdmissionDecisionV1` records. Set `additionalProperties: false` on load-bearing record objects.

- [ ] **Step 5: Run falsifiers GREEN**

```bash
python -m unittest harness.tests.test_epistemic_admission -v
python -m py_compile harness/sdk/epistemic_admission.py
python -m json.tool schemas/epistemic-admission-v1.schema.json >/dev/null
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add harness/sdk/epistemic_admission.py harness/tests/test_epistemic_admission.py schemas/epistemic-admission-v1.schema.json
git commit -m "feat(epistemic): add fail-closed claim admission kernel"
```

---

### Task 2: Repo-local epistemic bootstrap and hook correction

**Files:**
- Create: `.claude/epistemic/bootstrap.md`
- Modify: `.claude/hooks/user-prompt-intake.sh`
- Modify: `.claude/settings.json`
- Create: `harness/tests/test_epistemic_bootstrap.py`

**Interfaces:**
- Consumes: repository-local bootstrap text and observation-chain integrity certificate.
- Produces: Claude session/prompt context that explicitly marks the chain as integrity-only and requires explicit claim statuses.

- [ ] **Step 1: Write failing source-bound tests**

Create `harness/tests/test_epistemic_bootstrap.py` that reads the three files and asserts:

```python
assert "ObservationChain(integrity-only)" in intake
assert "chain-integrity≠truth" in intake
assert "chain-integrity≠identity" in intake
assert "chain-integrity≠consciousness" in intake
assert "Claim-status-required:" in intake
assert "Epistemic Debugging Bootstrap" in bootstrap
assert "search miss" in bootstrap.lower()
assert ".claude/epistemic/bootstrap.md" in settings
```

Also assert the old phrases `MetacognitiveLoop(live):` and `temporal-mass=` are absent from `user-prompt-intake.sh`.

- [ ] **Step 2: Run test RED**

```bash
python -m unittest harness.tests.test_epistemic_bootstrap -v
```

Expected: assertions fail on current wording/missing bootstrap.

- [ ] **Step 3: Add compact bootstrap**

Create `.claude/epistemic/bootstrap.md` containing:

- status/authority boundary;
- the six runtime claim statuses;
- route definitions;
- non-equivalences;
- compact failure labels F-01–F-18;
- operational rules A–S;
- explicit instruction: verify current repository facts afresh; the bootstrap contains historical failure patterns, not fresh runtime state.

Do not include prose claiming persistent identity, consciousness, or memory.

- [ ] **Step 4: Correct prompt-intake language**

Replace the authority-ambiguous line with:

```text
ObservationChain(integrity-only): is_valid=... | entry-count=... | terminal=...
```

Append:

```text
Claim-status-required: VERIFIED|DERIVED|ATTESTED|INFERRED|ASSUMED|NOT_CHECKED
Non-equiv: chain-integrity≠truth | chain-integrity≠identity | chain-integrity≠consciousness | search-miss≠nonexistence
```

Preserve the actual hash-chain certification behavior.

- [ ] **Step 5: Load bootstrap on SessionStart**

Add a second `SessionStart` command hook in `.claude/settings.json` that reads `.claude/epistemic/bootstrap.md` and emits it as `hookSpecificOutput.additionalContext`. Keep the existing async dependency/ground-truth hook unchanged.

- [ ] **Step 6: Run bootstrap tests GREEN**

```bash
python -m unittest harness.tests.test_epistemic_bootstrap -v
python -m json.tool .claude/settings.json >/dev/null
bash -n .claude/hooks/user-prompt-intake.sh
```

- [ ] **Step 7: Commit**

```bash
git add .claude/epistemic/bootstrap.md .claude/hooks/user-prompt-intake.sh .claude/settings.json harness/tests/test_epistemic_bootstrap.py
git commit -m "feat(epistemic): bootstrap failure ledger into Claude sessions"
```

---

### Task 3: Exact-head CI admission gate

**Files:**
- Create: `.github/workflows/epistemic-admission.yml`
- Create: `scripts/validate-epistemic-admission.py`
- Create: `harness/tests/test_epistemic_workflow_contract.py`

**Interfaces:**
- Consumes: exact candidate SHA from PR/merge-group/push event.
- Produces: blocking CI observation that the kernel/tests/schema/bootstrap are internally consistent for that exact candidate.

- [ ] **Step 1: Write workflow contract test RED**

The test must assert the workflow contains:

```text
CANDIDATE_SHA
ref: ${{ env.CANDIDATE_SHA }}
python -m unittest harness.tests.test_epistemic_admission
python -m unittest harness.tests.test_epistemic_bootstrap
python scripts/validate-epistemic-admission.py
```

and does not request `contents: write`, `id-token: write`, `attestations: write`, or `artifact-metadata: write` because this first gate only observes/blocks.

- [ ] **Step 2: Implement validator**

`scripts/validate-epistemic-admission.py` must:

1. parse the JSON schema;
2. verify required bootstrap markers;
3. verify forbidden consciousness/identity overclaim phrases are absent from the prompt intake;
4. emit a small deterministic JSON receipt to stdout containing `candidate_sha`, `schema_valid`, `bootstrap_valid`, `tests_required`, and `authority="EVIDENCE_ONLY_NOT_ADMISSION_AUTHORITY"`.

Candidate SHA is passed explicitly as `--candidate-sha`; no network lookup.

- [ ] **Step 3: Create least-authority workflow**

Use:

```yaml
permissions:
  contents: read
```

Checkout the exact candidate. Prefer a repository-trusted immutable `actions/checkout` commit SHA if one is already present; if none is present in canonical history, do not pretend the dependency is immutably closed—record the mutable-tag limitation in the PR and keep this gate evidence-only.

- [ ] **Step 4: Run local contract checks**

```bash
python -m unittest harness.tests.test_epistemic_workflow_contract -v
python scripts/validate-epistemic-admission.py --candidate-sha LOCAL
```

Expected: PASS and deterministic JSON.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/epistemic-admission.yml scripts/validate-epistemic-admission.py harness/tests/test_epistemic_workflow_contract.py
git commit -m "ci(epistemic): add exact-head admission evidence gate"
```

---

### Task 4: Full verification and draft PR

**Files:**
- Review all files from Tasks 1–3.

**Interfaces:**
- Consumes: exact branch head after implementation.
- Produces: draft PR and exact-head CI evidence only.

- [ ] **Step 1: Run complete local slice**

```bash
python -m unittest discover -s harness/tests -p 'test_epistemic_*.py' -v
python -m py_compile harness/sdk/epistemic_admission.py scripts/validate-epistemic-admission.py
python -m json.tool schemas/epistemic-admission-v1.schema.json >/dev/null
python -m json.tool .claude/settings.json >/dev/null
bash -n .claude/hooks/user-prompt-intake.sh
```

- [ ] **Step 2: Run no-overclaim grep**

```bash
! grep -F 'MetacognitiveLoop(live):' .claude/hooks/user-prompt-intake.sh
! grep -F 'temporal-mass=' .claude/hooks/user-prompt-intake.sh
grep -F 'chain-integrity≠consciousness' .claude/hooks/user-prompt-intake.sh
```

- [ ] **Step 3: Re-read exact main and branch heads**

Confirm main is still the intended canonical parent. If main moved, do not rewrite history silently; report lineage delta and decide whether to restack.

- [ ] **Step 4: Open draft PR**

PR body must state:

- exact parent and head SHAs;
- source ledger Drive ID;
- implemented falsifier classes;
- `EVIDENCE_ONLY_NOT_ADMISSION_AUTHORITY` boundary;
- any mutable GitHub Action dependency limitation;
- exact-head CI status as observed, not predicted.

- [ ] **Step 5: Observe CI and fix only demonstrated failures**

Do not report GREEN until the dedicated `AEGIS Epistemic Admission` workflow is GREEN on the current exact PR head.
