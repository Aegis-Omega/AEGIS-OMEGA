# PR-2 Independent Effect Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a provider-neutral effect-observation boundary and a filesystem reference adapter that can produce EffectWitness + adapter-bound EffectReceipt only from independent pre/post state reads, while leaving complete verification and authoritative admission unavailable.

**Architecture:** PR-2 is stacked on PR-1 exact head `6bf071d9c757d0f3514904f1efad3e3b14a60a09`. A new `effect_adapters.py` module owns independent observation and is the only canonical producer allowed to cross from post-effect observation into `EffectReceipt`; `transition_receipts.py` retains nominal receipt semantics and exposes no public generic effect-receipt factory. A filesystem reference adapter provides deterministic, dependency-free exact-head evidence without defining universal cloud/payment/actuator semantics.

**Tech Stack:** Python 3.12 stdlib (`dataclasses`, `hashlib`, `os`, `pathlib`), existing canonical hashing from `harness.sdk.sovereign_execution`, JSON Schema draft 2020-12, existing unittest-based Automaton-3 runner.

**Spec:** `docs/superpowers/specs/2026-08-19-pr2-independent-effect-observation-design.md`

## Global Constraints

- Exact stacked parent: `pr1-transition-receipt-separation@6bf071d9c757d0f3514904f1efad3e3b14a60a09`.
- Preserve `DECISION != EXECUTION != EFFECT`.
- Preserve `AuthorizationDerivedArtifacts ∩ AcceptableEvidence(V_effect) = ∅`.
- Caller-supplied `post_state_digest` never participates in canonical EffectWitness/EffectReceipt production.
- Direct `EffectReceipt(...)` construction remains forbidden.
- EffectReceipt may exist for a no-op observation; existence does not imply effect success, verification, or admission.
- No complete verifier registry, current-revocation gate, distributed CAS, AdmissionRecord, EffectBoundAdmission, or production claim in PR-2.
- Do not redefine TypeScript sovereignty `MutationReceiptV1`.
- No legacy fallback when effect evidence is missing.
- Target test count after the exact 17-test PR-2 falsification file is added: `75` Automaton-3 Python tests (`58 + 17`).

---

### Task 1: Add PR-2 falsification tests and serialized EffectWitness contract

**Files:**
- Create: `sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py`
- Create: `schemas/effect-witness.v1.schema.json`

**Interfaces:**
- Consumes existing `TransitionIdentity`, `DecisionReceipt`, `ExecutionReceipt`, `EffectReceipt`, `accept_effect_evidence` from `harness.sdk.transition_receipts`.
- Expects future `EffectAdapterError`, `EffectObservationHandle`, `EffectWitness`, `FilesystemEffectAdapter`, and `filesystem_state_commitment` from `harness.sdk.effect_adapters`.
- Produces exactly 17 new unittest cases.

- [ ] **Step 1: Write the failing 17-test PR-2 suite**

Implement these exact tests in one `unittest.TestCase` class:

```python
TEST_NAMES = (
    "test_authorization_artifact_still_not_effect_evidence",
    "test_legacy_succeeded_receipt_still_not_effect_evidence",
    "test_direct_effect_receipt_construction_still_forbidden",
    "test_caller_post_state_digest_has_no_effect_authority",
    "test_prepare_observation_rejects_pre_state_mismatch",
    "test_prepare_observation_rejects_target_escape",
    "test_prepare_observation_rejects_symlink_escape",
    "test_effect_observation_binds_transition_id",
    "test_effect_observation_binds_execution_instance_id",
    "test_cross_transition_execution_receipt_splicing_fails",
    "test_cross_target_observation_splicing_fails",
    "test_post_state_is_derived_from_fresh_filesystem_read",
    "test_no_effect_produces_evidence_with_effect_changed_false",
    "test_real_effect_produces_distinct_observed_post_state",
    "test_effect_receipt_is_adapter_bound",
    "test_effect_receipt_exists_does_not_imply_verified",
    "test_missing_effect_receipt_still_has_no_legacy_fallback",
)
```

Use `tempfile.TemporaryDirectory()` for every filesystem test. Build the transition pre-state commitment from the real target bytes via the future `filesystem_state_commitment()` helper. Instantiate `ExecutionReceipt` directly from the PR-1 type; test both `SUCCEEDED` and `FAILED` execution outcomes to prove observation does not infer effect from execution status.

- [ ] **Step 2: Write the EffectWitness JSON schema**

Create `schemas/effect-witness.v1.schema.json` with:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aegisomega.com/schemas/effect-witness.v1.schema.json",
  "title": "AEGIS Effect Witness V1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "witness_kind",
    "transition_id",
    "execution_instance_id",
    "target_identity",
    "observed_pre_state_commitment",
    "observed_post_state_commitment",
    "effect_changed",
    "pre_observation_provenance",
    "post_observation_provenance",
    "adapter_identity",
    "adapter_version"
  ],
  "properties": {
    "witness_kind": {"const": "EFFECT_WITNESS_V1"},
    "transition_id": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "execution_instance_id": {"type": "string", "minLength": 1},
    "target_identity": {"type": "string", "minLength": 1},
    "observed_pre_state_commitment": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "observed_post_state_commitment": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "effect_changed": {"type": "boolean"},
    "pre_observation_provenance": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "post_observation_provenance": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "adapter_identity": {"type": "string", "minLength": 1},
    "adapter_version": {"type": "string", "minLength": 1}
  }
}
```

- [ ] **Step 3: Run the new test file and prove RED**

Run:

```bash
python sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py
```

Expected: import/module failures because `harness.sdk.effect_adapters` does not exist yet. The existing 58 PR-1 tests must remain untouched and reproducible.

- [ ] **Step 4: Commit the RED contract**

```bash
git add sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py schemas/effect-witness.v1.schema.json
git commit -m "test(automaton3): define PR-2 effect observation falsifiers"
```

---

### Task 2: Implement independent filesystem pre-effect observation

**Files:**
- Create: `harness/sdk/effect_adapters.py`

**Interfaces:**
- Consumes: `TransitionIdentity`, `ExecutionReceipt`, `verify_transition_binding` from `harness.sdk.transition_receipts`; `canonical_hash`, `ZERO_HASH` from `harness.sdk.sovereign_execution`.
- Produces:

```python
class EffectAdapterError(ValueError): ...

@dataclass(frozen=True)
class EffectObservationHandle:
    transition_id: str
    target_identity: str
    observed_pre_state_commitment: str
    pre_observation_provenance: str
    adapter_identity: str
    adapter_version: str
    observation_id: str

@dataclass(frozen=True)
class EffectWitness:
    witness_kind: str
    transition_id: str
    execution_instance_id: str
    target_identity: str
    observed_pre_state_commitment: str
    observed_post_state_commitment: str
    effect_changed: bool
    pre_observation_provenance: str
    post_observation_provenance: str
    adapter_identity: str
    adapter_version: str

@dataclass(frozen=True)
class FilesystemStateObservation:
    target_identity: str
    exists: bool
    content_sha256: str
    size_bytes: int
    device: int
    inode: int
    mtime_ns: int


def filesystem_state_commitment(*, allowed_root: Path, target: Path) -> str: ...

class FilesystemEffectAdapter:
    identity = "aegis.filesystem-effect-adapter"
    version = "1.0.0"
    def __init__(self, *, allowed_root: Path): ...
    def prepare_observation(self, *, transition: TransitionIdentity, target: Path) -> EffectObservationHandle: ...
```

- [ ] **Step 1: Implement canonical contained target resolution**

Add `_resolve_target()` that resolves both `allowed_root` and the target using `Path.resolve(strict=False)` and fails with:

```python
raise EffectAdapterError("EFFECT_TARGET_OUTSIDE_ALLOWED_ROOT")
```

unless `resolved_target == allowed_root` or `allowed_root in resolved_target.parents`.

Use `relative_to(allowed_root).as_posix()` as `target_identity`; state commitments include this identity so identical bytes at different paths are not equivalent states.

- [ ] **Step 2: Implement an actual filesystem observation**

`_observe_state()` must read the file itself. For an existing regular file:

```python
content = target.read_bytes()
stat = target.stat()
content_sha256 = hashlib.sha256(content).hexdigest()
```

For a missing file use `exists=False`, `content_sha256=ZERO_HASH`, `size_bytes=0`, `device=0`, `inode=0`, `mtime_ns=0`.

Reject directories/non-regular existing targets with `EFFECT_TARGET_NOT_REGULAR_FILE`.

- [ ] **Step 3: Implement the state commitment**

Use exactly:

```python
canonical_hash(
    "AEGIS_FILESYSTEM_EFFECT_STATE_V1",
    {
        "target_identity": observation.target_identity,
        "exists": observation.exists,
        "content_sha256": observation.content_sha256,
        "size_bytes": observation.size_bytes,
    },
)
```

`filesystem_state_commitment()` performs a fresh observation and returns this root.

- [ ] **Step 4: Implement PRE observation provenance**

Use domain `AEGIS_EFFECT_OBSERVATION_PROVENANCE_V1` over:

```python
{
    "transition_id": transition.root,
    "phase": "PRE",
    "target_identity": obs.target_identity,
    "state_commitment": pre_commitment,
    "content_sha256": obs.content_sha256,
    "size_bytes": obs.size_bytes,
    "filesystem_device": obs.device,
    "filesystem_inode": obs.inode,
    "filesystem_mtime_ns": obs.mtime_ns,
    "adapter_identity": self.identity,
    "adapter_version": self.version,
    "observation_id": observation_id,
}
```

Compute `observation_id` deterministically with domain `AEGIS_EFFECT_OBSERVATION_HANDLE_V1` over transition ID, target identity, pre-state commitment, adapter identity/version.

- [ ] **Step 5: Fail closed on stale/wrong pre-state**

`prepare_observation()` MUST compare the freshly observed commitment to `transition.pre_state_commitment` and raise:

```python
EffectAdapterError("EFFECT_PRE_STATE_COMMITMENT_MISMATCH")
```

before returning a handle.

- [ ] **Step 6: Run only the PRE-observation tests to GREEN**

Run the mismatch, target escape, symlink escape, and cross-target tests from `test_effect_adapters_pr2.py`.

Expected: PASS. Tests that require post-effect production remain RED.

- [ ] **Step 7: Commit**

```bash
git add harness/sdk/effect_adapters.py sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py
git commit -m "feat(automaton3): add independent filesystem effect observation"
```

---

### Task 3: Enable adapter-bound EffectWitness and EffectReceipt production

**Files:**
- Modify: `harness/sdk/effect_adapters.py`
- Modify: `harness/sdk/transition_receipts.py`

**Interfaces:**
- `FilesystemEffectAdapter.observe_effect()` produces `(EffectWitness, EffectReceipt)`.
- `EffectReceipt` remains `init=False`.
- No public symbol named `make_effect_receipt` or generic `effect_receipt_from_post_state` is introduced.

- [ ] **Step 1: Add a module-private adapter producer capability to `transition_receipts.py`**

Define:

```python
_EFFECT_RECEIPT_PRODUCER_CAPABILITY = object()


def _issue_adapter_bound_effect_receipt(*, witness: Any, producer_capability: object) -> EffectReceipt:
    if producer_capability is not _EFFECT_RECEIPT_PRODUCER_CAPABILITY:
        raise TransitionReceiptError("EFFECT_RECEIPT_PRODUCER_UNAUTHORIZED")
    ...
```

Construct `EffectReceipt` using `object.__new__(EffectReceipt)` plus `object.__setattr__` for the frozen fields, then call `receipt.validate()` before returning it.

Set:

```python
receipt_kind = EFFECT_RECEIPT_KIND
transition_id = witness.transition_id
execution_instance_id = witness.execution_instance_id
effect_witness_digest = witness.root
pre_state_commitment = witness.observed_pre_state_commitment
post_state_commitment = witness.observed_post_state_commitment
observation_provenance = canonical_hash(
    "AEGIS_EFFECT_OBSERVATION_BUNDLE_V1",
    {
        "pre": witness.pre_observation_provenance,
        "post": witness.post_observation_provenance,
    },
)
adapter_identity = witness.adapter_identity
adapter_version = witness.adapter_version
```

Do not add the private producer symbols to any public `__all__` surface.

- [ ] **Step 2: Add `EffectWitness.root`**

Use:

```python
canonical_hash("AEGIS_EFFECT_WITNESS_V1", asdict(self))
```

after validating `witness_kind == "EFFECT_WITNESS_V1"`, all required SHA-256 roots, IDs, and adapter fields.

- [ ] **Step 3: Implement fresh POST observation**

Add:

```python
def observe_effect(
    self,
    *,
    transition: TransitionIdentity,
    handle: EffectObservationHandle,
    execution_receipt: ExecutionReceipt,
) -> tuple[EffectWitness, EffectReceipt]:
```

Fail closed unless:

```python
handle.transition_id == transition.root
execution_receipt.transition_id == transition.root
handle.adapter_identity == self.identity
handle.adapter_version == self.version
handle.observed_pre_state_commitment == transition.pre_state_commitment
```

Do **not** require `execution_receipt.outcome == SUCCEEDED`; failed/cancelled execution may still have observable partial effects.

Perform a new `_observe_state()` call after those binding checks. The method accepts no caller-supplied post-state commitment.

- [ ] **Step 4: Compute POST provenance and EffectWitness**

POST provenance uses the same observation domain as PRE with `phase="POST"`, and additionally records `execution_instance_id`.

Set:

```python
effect_changed = observed_post_state_commitment != handle.observed_pre_state_commitment
```

Create the witness, then call the private adapter producer to issue the EffectReceipt.

- [ ] **Step 5: Keep verification/admission unavailable**

Do not make `accept_effect_evidence()` a complete verifier. Preserve its rejection of legacy MutationReceipt, DecisionReceipt, ExecutionReceipt, and `None`.

Add a narrow helper in `effect_adapters.py`:

```python
def is_adapter_bound_effect_evidence(*, witness: EffectWitness, receipt: EffectReceipt) -> bool:
    ...
```

It may check witness/receipt structural binding and roots, but its docstring MUST state:

```text
Adapter-bound evidence candidate only; does not establish VerifyTransition or admission.
```

- [ ] **Step 6: Run all 17 PR-2 tests to GREEN**

Run:

```bash
python sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py
```

Expected: `Ran 17 tests` / `OK`.

- [ ] **Step 7: Run the existing 58 PR-1 tests unchanged**

Run:

```bash
python scripts/run-automaton3-tests.py --output /tmp/pr1-summary.json --log /tmp/pr1.log
```

Before Task 4 adds the PR-2 file to the runner, expected result remains the original PR-1 `58/58` contract.

- [ ] **Step 8: Commit**

```bash
git add harness/sdk/effect_adapters.py harness/sdk/transition_receipts.py sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py
git commit -m "feat(automaton3): issue adapter-bound effect evidence"
```

---

### Task 4: Bind PR-2 into exact-head Automaton-3 conformance evidence

**Files:**
- Modify: `scripts/run-automaton3-tests.py`
- Modify: `scripts/validate-automaton3.py`
- Modify: `.github/workflows/automaton-3.yml`

**Interfaces:**
- Existing runner includes `test_effect_adapters_pr2.py` and exact expected count becomes `75`.
- Canonical candidate manifest includes `effect_adapters.py`, the PR-2 test, and `effect-witness.v1.schema.json`.
- Validation metadata promotes only reference effect observation/adapter-bound production; complete verification/admission remain false.

- [ ] **Step 1: Add the PR-2 test file to the runner**

Change:

```python
TEST_FILES = (
    ...existing four files...,
    ROOT / "sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py",
)
EXPECTED_TEST_COUNT = 75
```

- [ ] **Step 2: Add PR-2 summary assertions**

When and only when all 75 tests pass, emit:

```python
"pr2_effect_adapter_protocol_asserted": passed,
"pr2_filesystem_effect_adapter_asserted": passed,
"pr2_independent_pre_post_observation_asserted": passed,
"pr2_adapter_bound_effect_receipt_production_asserted": passed,
"pr2_authorization_artifact_effect_evidence_forbidden_asserted": passed,
"pr2_caller_post_state_effect_authority_forbidden_asserted": passed,
"pr2_complete_verification_unavailable_asserted": passed,
"pr2_atomic_admission_unavailable_asserted": passed,
"pr2_effect_bound_admission_unavailable_asserted": passed,
```

- [ ] **Step 3: Expand the canonical manifest**

Add to `KEY_FILES`:

```text
harness/sdk/effect_adapters.py
sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py
schemas/effect-witness.v1.schema.json
```

Set validator `EXPECTED_TEST_COUNT = 75` and fail closed unless all nine PR-2 summary assertions are exactly `True`.

- [ ] **Step 4: Add integration expectation without claiming admission**

Require `harness/sdk/effect_adapters.py` to contain `FilesystemEffectAdapter` and `AEGIS_EFFECT_WITNESS_V1`.

Do not add any expectation for `AdmissionRecord`, `EffectBoundAdmission`, or generic effect-receipt production.

- [ ] **Step 5: Extend workflow schema/attestation subject list**

Add:

```text
schemas/effect-witness.v1.schema.json
```

to schema validation/attestation subjects. Add the effect adapter module/test to the deterministic candidate manifest through the validator, not by creating a separate authority path.

- [ ] **Step 6: Execute exact-head conformance**

Run:

```bash
python scripts/run-automaton3-tests.py \
  --output /tmp/AUTOMATON3_TEST_SUMMARY.json \
  --log /tmp/AUTOMATON3_TEST.log
```

Expected:

```text
actual_test_count = 75
test_count_matches_expected = true
return_code = 0
```

Run MCP integration and canonical validator using the same commands as `.github/workflows/automaton-3.yml`.

- [ ] **Step 7: Produce an external exact-head witness if AEGIS-hosted Actions remain blocked**

Use the already established `tarikskalic33/info` external witness pattern. The witness MUST checkout the final PR-2 head by exact SHA and label itself:

```text
AEGIS_PR2_EXTERNAL_EXACT_HEAD_WITNESS_V1
```

It must not label itself repo-native CI, complete verification, EffectBoundAdmission, or production proof.

- [ ] **Step 8: Commit**

```bash
git add scripts/run-automaton3-tests.py scripts/validate-automaton3.py .github/workflows/automaton-3.yml
git commit -m "test(automaton3): bind PR-2 effect observation to exact-head evidence"
```

## Required final ledger

Only after exact-head execution evidence:

```text
PR2
= OPEN / DRAFT / STACKED_ON_PR1

EFFECT_ADAPTER_PROTOCOL
= IMPLEMENTED_AND_TESTED_REFERENCE

FILESYSTEM_EFFECT_ADAPTER
= IMPLEMENTED_AND_TESTED_REFERENCE

INDEPENDENT_PRE_POST_EFFECT_OBSERVATION
= IMPLEMENTED_AND_TESTED_REFERENCE

VALID_EFFECT_RECEIPT_PRODUCTION
= ADAPTER_BOUND_ONLY / IMPLEMENTED_AND_TESTED_REFERENCE

AUTHORIZATION_DERIVED_ARTIFACT_ACCEPTED_AS_EFFECT_EVIDENCE
= NEVER

CALLER_SUPPLIED_POST_STATE_ACCEPTED_AS_EFFECT_EVIDENCE
= NEVER

EFFECT_RECEIPT_EXISTS_IMPLIES_VERIFIED
= FALSE

COMPLETE_VERIFICATION
= NOT_IMPLEMENTED

ATOMIC_ADMISSION
= NOT_IMPLEMENTED

EFFECT_BOUND_ADMISSION
= UNAVAILABLE

C_IMPLEMENTATION
= FALSE
```

Acceptance sentence: **Effect evidence can only be produced from an independent observation path bound to the exact transition and execution instance; its existence still does not mean the transition is verified or admitted.**
