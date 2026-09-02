# Cognitive Recovery Admission V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, offline, non-mutating recovery-admission validator that consumes an exact content-addressed request plus recovery evidence and emits a schema-valid `RECOVERY_ADMISSION_GRANTED` or `DENIED` receipt with `mutation_authority = NONE`.

**Architecture:** The first executable milestone is deliberately smaller than a hosted recovery signer. JSON schemas define the request and receipt contracts; a pure Python validator canonicalizes and hashes inputs, checks exact Git/receipt/blob/diff/authority/platform-observation bindings, and emits a deterministic receipt. A candidate-controlled CI lane may prove the validator implementation but has no signer or production authority. Hosted/base-owned signing and `ApplyCognitiveRecoveryV1` are explicitly outside this plan and require a separate specification after this validator is exact-head GREEN.

**Tech Stack:** Python 3.12, standard library (`argparse`, `hashlib`, `json`, `pathlib`, `subprocess`, `datetime`), `jsonschema==4.23.0`, Git CLI, GitHub Actions for non-authoritative CI only.

**Spec:** `docs/superpowers/specs/2026-09-02-cognitive-recovery-admission-v1-design.md`

## Global Constraints

- Normal Automaton-2/Automaton-3 admission semantics are not modified.
- Candidate-controlled code cannot grant itself production recovery authority.
- Every Git commit identity is a 40-lowercase-hex SHA-1 and every digest is a 64-lowercase-hex SHA-256.
- Request identity is SHA-256 over canonical JSON bytes with `request_id` omitted from the hashed body.
- Receipt identity is SHA-256 over canonical JSON bytes with `receipt_hash` omitted from the hashed body and domain-separated by `AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1`.
- `mutation_authority` is always `NONE` in this milestone, including successful admission decisions.
- `authority` on success is exactly `RECOVERY_ADMISSION_ONLY`; on denial it is exactly `NONE`.
- Allowed changed paths come only from the request; candidate prose cannot alter them at evaluation time.
- GCP/provider enablement, billing, deployment, network/secrets authority, repository-governance widening, and mathematical authority are forbidden in this recovery scope.
- Platform governance input is an externally supplied observation bound by digest. `ENFORCED` is required for a success decision; `DISABLED`, `UNKNOWN`, missing, expired, or digest-mismatched observations deny.
- Operator approval input is an externally supplied exact request/candidate approval record bound by digest. It is evidence to the offline validator, not a signer implementation.
- No workflow in this plan receives `contents: write`, `id-token: write`, `attestations: write`, `artifact-metadata: write`, merge authority, deployment credentials, cloud credentials, or GCP credentials.
- No code in this plan updates `main` or any Git ref.
- `RIEMANN_HYPOTHESIS = NOT_PROVEN` is invariant and outside the recovery authority domain.

---

## File Structure

### New files

- `schemas/cognitive-recovery-admission-request.v1.schema.json` — closed JSON Schema for exact recovery admission requests.
- `schemas/cognitive-recovery-admission-receipt.v1.schema.json` — closed JSON Schema for deterministic admission decisions.
- `scripts/validate-cognitive-recovery-admission.py` — pure/offline validator and CLI; no mutation functions.
- `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py` — unit, schema, Git-fixture, and adversarial falsifier corpus.
- `.github/workflows/cognitive-recovery-admission-validator.yml` — candidate-controlled `contents: read` verification lane; explicitly authority `NONE`.

### Existing files read but not modified

- `scripts/validate-cognitive-recovery.py` — canonical JSON/hash/Git helper semantics to mirror, not import across authority layers.
- `schemas/mutation-receipt.v1.schema.json` — schema style reference only.
- `.github/workflows/cognitive-anchor-recovery.yml` — recovery evidence producer; never promoted to admission signer.

---

### Task 1: Freeze request and receipt schemas through RED tests

**Files:**
- Create: `schemas/cognitive-recovery-admission-request.v1.schema.json`
- Create: `schemas/cognitive-recovery-admission-receipt.v1.schema.json`
- Create: `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py`

**Interfaces:**
- Consumes: JSON Schema draft 2020-12 via `jsonschema==4.23.0`.
- Produces: exact request/receipt field names consumed by all later tasks.

- [ ] **Step 1: Write the failing schema-existence and valid-fixture tests**

Create `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py` with these constants and first tests:

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest import TestCase, main

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUEST_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-request.v1.schema.json"
RECEIPT_SCHEMA_PATH = REPO_ROOT / "schemas" / "cognitive-recovery-admission-receipt.v1.schema.json"

SHA1_A = "a" * 40
SHA1_B = "b" * 40
SHA1_C = "c" * 40
SHA1_D = "d" * 40
SHA256_1 = "1" * 64
SHA256_2 = "2" * 64
SHA256_3 = "3" * 64
SHA256_4 = "4" * 64
SHA256_5 = "5" * 64
SHA256_6 = "6" * 64
SHA256_7 = "7" * 64
SHA256_8 = "8" * 64


def load_schema(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def valid_request() -> dict:
    return {
        "schema_version": "1.0.0",
        "request_id": SHA256_1,
        "repository_id": "Aegis-Omega/AEGIS-OMEGA",
        "trusted_control_plane_sha": SHA1_A,
        "recovery_parent_sha": SHA1_B,
        "denied_base_sha": SHA1_C,
        "candidate_sha": SHA1_D,
        "zero_parent_repair_sha": "e" * 40,
        "zero_parent_validator_blob": "f" * 40,
        "zero_parent_test_blob": "0" * 40,
        "writer_workflow_blob": "1" * 40,
        "recovery_receipt_hash": SHA256_2,
        "denied_receipt_hash": SHA256_3,
        "counterfactual_admission_receipt_hash": SHA256_4,
        "recovery_artifact_digest": SHA256_5,
        "expected_manifest_blob": "2" * 40,
        "expected_skill_hashes_blob": "3" * 40,
        "expected_recovery_state_hash": SHA256_6,
        "allowed_changed_paths": [".claude.json", "skill-hashes.sha256"],
        "requested_transition": "COGNITIVE_CANONICAL_RECOVERY",
        "requested_authority": "RESTORE_PREVIOUSLY_ADMITTED_COGNITIVE_CONTROL_SURFACE",
        "expires_at": "2026-09-03T00:00:00Z",
        "operator_approval_digest": SHA256_7,
        "platform_governance_observation_digest": SHA256_8,
    }


class RecoveryAdmissionSchemaTests(TestCase):
    def test_request_schema_accepts_closed_valid_fixture(self) -> None:
        schema = load_schema(REQUEST_SCHEMA_PATH)
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(valid_request())

    def test_request_schema_rejects_authority_widening_field(self) -> None:
        request = valid_request()
        request["gcp_enabled"] = True
        errors = list(Draft202012Validator(load_schema(REQUEST_SCHEMA_PATH)).iter_errors(request))
        self.assertTrue(errors)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
python sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
```

Expected: FAIL with `FileNotFoundError` for `cognitive-recovery-admission-request.v1.schema.json`.

- [ ] **Step 3: Add the closed request schema**

The schema must be draft 2020-12, `additionalProperties: false`, and require exactly the fields returned by `valid_request()`. Use these constraints:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aegisomega.com/schemas/cognitive-recovery-admission-request.v1.schema.json",
  "title": "AEGIS Cognitive Recovery Admission Request V1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version", "request_id", "repository_id",
    "trusted_control_plane_sha", "recovery_parent_sha", "denied_base_sha", "candidate_sha",
    "zero_parent_repair_sha", "zero_parent_validator_blob", "zero_parent_test_blob",
    "writer_workflow_blob", "recovery_receipt_hash", "denied_receipt_hash",
    "counterfactual_admission_receipt_hash", "recovery_artifact_digest",
    "expected_manifest_blob", "expected_skill_hashes_blob", "expected_recovery_state_hash",
    "allowed_changed_paths", "requested_transition", "requested_authority",
    "expires_at", "operator_approval_digest", "platform_governance_observation_digest"
  ],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "request_id": {"$ref": "#/$defs/sha256"},
    "repository_id": {"const": "Aegis-Omega/AEGIS-OMEGA"},
    "trusted_control_plane_sha": {"$ref": "#/$defs/sha1"},
    "recovery_parent_sha": {"$ref": "#/$defs/sha1"},
    "denied_base_sha": {"$ref": "#/$defs/sha1"},
    "candidate_sha": {"$ref": "#/$defs/sha1"},
    "zero_parent_repair_sha": {"$ref": "#/$defs/sha1"},
    "zero_parent_validator_blob": {"$ref": "#/$defs/sha1"},
    "zero_parent_test_blob": {"$ref": "#/$defs/sha1"},
    "writer_workflow_blob": {"$ref": "#/$defs/sha1"},
    "recovery_receipt_hash": {"$ref": "#/$defs/sha256"},
    "denied_receipt_hash": {"$ref": "#/$defs/sha256"},
    "counterfactual_admission_receipt_hash": {"$ref": "#/$defs/sha256"},
    "recovery_artifact_digest": {"$ref": "#/$defs/sha256"},
    "expected_manifest_blob": {"$ref": "#/$defs/sha1"},
    "expected_skill_hashes_blob": {"$ref": "#/$defs/sha1"},
    "expected_recovery_state_hash": {"$ref": "#/$defs/sha256"},
    "allowed_changed_paths": {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "string", "minLength": 1}},
    "requested_transition": {"const": "COGNITIVE_CANONICAL_RECOVERY"},
    "requested_authority": {"const": "RESTORE_PREVIOUSLY_ADMITTED_COGNITIVE_CONTROL_SURFACE"},
    "expires_at": {"type": "string", "format": "date-time"},
    "operator_approval_digest": {"$ref": "#/$defs/sha256"},
    "platform_governance_observation_digest": {"$ref": "#/$defs/sha256"}
  },
  "$defs": {
    "sha1": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
  }
}
```

- [ ] **Step 4: Add a receipt fixture test, then create the closed receipt schema**

Add `valid_receipt()` to the test file:

```python
def valid_receipt() -> dict:
    return {
        "receipt_kind": "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1",
        "schema_version": "1.0.0",
        "request_digest": SHA256_1,
        "repository_id": "Aegis-Omega/AEGIS-OMEGA",
        "candidate_sha": SHA1_D,
        "denied_base_sha": SHA1_C,
        "trusted_control_plane_sha": SHA1_A,
        "recovery_parent_sha": SHA1_B,
        "recovery_receipt_hash": SHA256_2,
        "writer_workflow_blob": "1" * 40,
        "platform_governance_observation_digest": SHA256_8,
        "platform_governance_state": "ENFORCED",
        "operator_approval_digest": SHA256_7,
        "verified_gates": ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7"],
        "violations": [],
        "outcome": "RECOVERY_ADMISSION_GRANTED",
        "scope": "ONE_EXACT_CANONICAL_RECOVERY_TRANSITION",
        "authority": "RECOVERY_ADMISSION_ONLY",
        "mutation_authority": "NONE",
        "verifier_identity": "offline:aegis-cognitive-recovery-admission-v1",
        "verifier_code_digest": SHA256_6,
        "receipt_hash": SHA256_5,
    }
```

The receipt schema must be closed and constrain:
- `receipt_kind` to `AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1`;
- `schema_version` to `1.0.0`;
- `outcome` to `RECOVERY_ADMISSION_GRANTED | DENIED`;
- `scope` to `ONE_EXACT_CANONICAL_RECOVERY_TRANSITION`;
- `mutation_authority` to `NONE`;
- `authority` to `RECOVERY_ADMISSION_ONLY | NONE`;
- `platform_governance_state` to `ENFORCED | DISABLED | UNKNOWN`;
- `verified_gates` unique values from `R0..R7`;
- `violations` as unique strings;
- all SHA fields with the same SHA-1/SHA-256 regexes as the request schema.

- [ ] **Step 5: Run schema tests GREEN and commit**

Run:

```bash
python sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
```

Expected: PASS for schema tests.

Commit:

```bash
git add schemas/cognitive-recovery-admission-request.v1.schema.json \
        schemas/cognitive-recovery-admission-receipt.v1.schema.json \
        sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
git commit -m "test(cognitive): freeze recovery admission contracts"
```

---

### Task 2: Build canonical request and deterministic receipt primitives

**Files:**
- Create: `scripts/validate-cognitive-recovery-admission.py`
- Modify: `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py`

**Interfaces:**
- Produces: `canonical_bytes(value: Any) -> bytes`, `sha256_hex(data: bytes) -> str`, `request_digest(request: dict[str, Any]) -> str`, `build_receipt(...) -> dict[str, Any]`.
- Consumes: schemas frozen in Task 1.

- [ ] **Step 1: Write RED tests for canonical request identity**

Add:

```python
import importlib.util

VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate-cognitive-recovery-admission.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecoveryAdmissionDigestTests(TestCase):
    def test_request_digest_ignores_only_request_id(self) -> None:
        validator = load_module("recovery_admission", VALIDATOR_PATH)
        left = valid_request()
        right = valid_request()
        right["request_id"] = "9" * 64
        self.assertEqual(validator.request_digest(left), validator.request_digest(right))
        right["candidate_sha"] = "8" * 40
        self.assertNotEqual(validator.request_digest(left), validator.request_digest(right))

    def test_canonical_json_rejects_nan(self) -> None:
        validator = load_module("recovery_admission_nan", VALIDATOR_PATH)
        with self.assertRaises(ValueError):
            validator.canonical_bytes({"x": float("nan")})
```

- [ ] **Step 2: Run and verify RED because validator file is absent**

Run the test file. Expected: `FileNotFoundError` for the validator.

- [ ] **Step 3: Implement canonical primitives**

Create the validator with:

```python
RECEIPT_KIND = "AEGIS_COGNITIVE_RECOVERY_ADMISSION_RECEIPT_V1"
SCHEMA_VERSION = "1.0.0"
VERIFIER_IDENTITY = "offline:aegis-cognitive-recovery-admission-v1"


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def request_digest(request: dict[str, Any]) -> str:
    body = {k: v for k, v in request.items() if k != "request_id"}
    return sha256_hex(canonical_bytes({"domain": "AEGIS_COGNITIVE_RECOVERY_ADMISSION_REQUEST_V1", "request": body}))
```

Implement `build_receipt()` so the `receipt_hash` is computed after all deterministic fields except `receipt_hash` are present. Do not include wall-clock time in this milestone; exact determinism is more important than an unauthenticated timestamp.

- [ ] **Step 4: Run digest tests GREEN and commit**

Commit:

```bash
git add scripts/validate-cognitive-recovery-admission.py \
        sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
git commit -m "feat(cognitive): add deterministic recovery admission primitives"
```

---

### Task 3: Implement R0–R5 exact Git/evidence/authority validation

**Files:**
- Modify: `scripts/validate-cognitive-recovery-admission.py`
- Modify: `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py`

**Interfaces:**
- Produces: `evaluate(*, repo: Path, request: dict[str, Any], recovery_evidence: dict[str, Any], platform_observation: dict[str, Any], operator_approval: dict[str, Any], verifier_code_digest: str) -> dict[str, Any]`.
- Internal helpers: `git_text`, `is_ancestor`, `changed_paths`, `blob_sha`, `load_json_file`, `schema_validate`.

- [ ] **Step 1: Build a temporary Git fixture in the test suite**

Use `TemporaryDirectory`, `git init`, and four commits:

1. trusted root with neutral control files;
2. recovery parent;
3. denied base changing only `.claude.json` and `skill-hashes.sha256`;
4. repair/candidate containing pinned validator/test/writer blobs and recovery files.

Store the exact commit/blob IDs from `git rev-parse` into a generated request fixture rather than hardcoding local Git hashes.

- [ ] **Step 2: Write RED test for exact repair ancestry/blob binding**

The passing fixture must become `RECOVERY_ADMISSION_GRANTED`; then mutate `zero_parent_validator_blob` in the request to another valid 40-hex value and assert `DENIED` with an R2 violation.

- [ ] **Step 3: Write RED test for bounded diff**

Create an extra `unrelated.txt` in the candidate, omit it from `allowed_changed_paths`, and assert `DENIED` with an R3 violation.

- [ ] **Step 4: Write RED test for recovery receipt/artifact binding**

Construct `recovery_evidence` as:

```python
{
    "receipt_kind": "AEGIS_COGNITIVE_RECOVERY_RECEIPT_V1",
    "outcome": "RECOVERY_VERIFIED",
    "production_admission": "NONE",
    "authority": "NONE",
    "candidate_sha": request["candidate_sha"],
    "denied_base_sha": request["denied_base_sha"],
    "recovery_parent_sha": request["recovery_parent_sha"],
    "receipt_hash": request["recovery_receipt_hash"],
    "denied_receipt_hash": request["denied_receipt_hash"],
    "recovery_validation_receipt_hash": request["counterfactual_admission_receipt_hash"],
    "artifact_digest": request["recovery_artifact_digest"],
}
```

Change each binding independently and assert R4 denial.

- [ ] **Step 5: Write RED authority-firewall tests**

The request schema is closed, but recovery files may still contain forbidden semantic changes. The validator must deny if the bounded diff includes any path matching these default forbidden prefixes/patterns unless it is the exact explicitly pinned recovery path:

```python
FORBIDDEN_RECOVERY_PATH_PREFIXES = (
    "infra/",
    "terraform/",
    "gcp/",
    "deploy/",
    ".github/workflows/deploy",
)
```

Also deny if candidate `.claude.json` or any request field attempts to encode GCP/billing/deployment enablement outside the admitted cognitive-control surface. The test uses `gcp/provider.json` in the candidate and demonstrates R5 denial even when a malicious request includes that path in `allowed_changed_paths`.

- [ ] **Step 6: Implement R0–R5 minimally**

Required behavior:

- R0: validate request schema and require `request["request_id"] == request_digest(request)`.
- R1: all named SHAs resolve; trusted root is ancestor of recovery parent; denied base is a direct child or explicitly declared incident descendant as encoded by this V1 fixture; repository ID exact.
- R2: zero-parent repair is ancestor of candidate; candidate blobs at validator/test/writer paths equal request values.
- R3: `changed_paths(denied_base, candidate)` is a subset of `allowed_changed_paths`; no open obligations concept exists in this first executable slice, so any unclassified path denies.
- R4: every recovery-evidence identity/digest equals the corresponding request field and recovery evidence itself says authority/production admission `NONE`.
- R5: forbidden authority-widening paths deny regardless of allowlist membership.

Every failed gate appends a deterministic string prefixed `R0:`, `R1:`, etc. Sort and deduplicate violations before hashing the receipt.

- [ ] **Step 7: Run all focused tests GREEN and commit**

Commit message:

```bash
git commit -m "feat(cognitive): verify recovery evidence and authority boundary"
```

---

### Task 4: Implement R6 platform observation and R7 operator approval binding

**Files:**
- Modify: `scripts/validate-cognitive-recovery-admission.py`
- Modify: `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py`

**Interfaces:**
- Platform observation input:

```python
{
    "schema_version": "1.0.0",
    "repository_id": "Aegis-Omega/AEGIS-OMEGA",
    "observed_for_candidate_sha": request["candidate_sha"],
    "state": "ENFORCED",  # ENFORCED | DISABLED | UNKNOWN
    "ruleset_ids": [123],
    "required_checks": ["aegis / automaton-2", "aegis / automaton-3", "Main branch enforcement"],
    "observation_digest": "...sha256 canonical body...",
}
```

- Operator approval input:

```python
{
    "schema_version": "1.0.0",
    "request_digest": request["request_id"],
    "candidate_sha": request["candidate_sha"],
    "decision": "APPROVE_RECOVERY_ADMISSION_EVALUATION",
    "approval_digest": request["operator_approval_digest"],
}
```

These are evidence inputs only; this task does not implement identity/signature issuance.

- [ ] **Step 1: Write RED tests for disabled/unknown governance**

Assert `DISABLED` and `UNKNOWN` always produce `DENIED` with `R6:` violations.

- [ ] **Step 2: Write RED anti-replay tests for governance observation**

Set `observed_for_candidate_sha` to another valid SHA and assert denial even if the observation state is `ENFORCED`.

- [ ] **Step 3: Write RED operator-binding tests**

Independently change approval request digest, candidate SHA, decision, and approval digest; every mutation must produce R7 denial.

- [ ] **Step 4: Implement canonical observation/approval digest helpers and R6/R7**

Use separate domain strings:

```text
AEGIS_PLATFORM_GOVERNANCE_OBSERVATION_V1
AEGIS_RECOVERY_OPERATOR_APPROVAL_V1
```

`platform_governance_observation_digest` in the request must equal the canonical observation digest. `operator_approval_digest` must equal the canonical approval body digest excluding its own `approval_digest` field.

A success requires all R0–R7 gates verified. Otherwise outcome is `DENIED`, authority `NONE`, mutation authority `NONE`.

- [ ] **Step 5: Run the full adversarial suite GREEN and commit**

Commit:

```bash
git commit -m "feat(cognitive): bind recovery admission to governance and approval"
```

---

### Task 5: Add CLI and schema-valid deterministic receipt emission

**Files:**
- Modify: `scripts/validate-cognitive-recovery-admission.py`
- Modify: `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py`

**Interfaces:**

CLI:

```text
python scripts/validate-cognitive-recovery-admission.py \
  --repo . \
  --request REQUEST.json \
  --recovery-evidence COGNITIVE_RECOVERY_RECEIPT.json \
  --platform-observation PLATFORM_GOVERNANCE_OBSERVATION.json \
  --operator-approval OPERATOR_APPROVAL.json \
  --verifier-code-digest <64hex> \
  --output COGNITIVE_RECOVERY_ADMISSION_RECEIPT.json
```

- [ ] **Step 1: Write RED subprocess tests**

One valid fixture must exit `0`, print `RECOVERY_ADMISSION_GRANTED <receipt_hash>`, and write a receipt validating against the receipt schema. A denied fixture must exit `1`, print `DENIED <receipt_hash>`, and still write a schema-valid receipt.

- [ ] **Step 2: Implement CLI file loading and output**

Never accept inline command-line overrides for request fields. All authority-relevant request values come from the exact request JSON file.

- [ ] **Step 3: Prove deterministic replay**

Run the exact same valid invocation twice and byte-compare output receipts:

```bash
cmp RECEIPT_1.json RECEIPT_2.json
```

Expected: exit 0 with no output.

- [ ] **Step 4: Run test suite and commit**

```bash
python sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
```

Expected: all tests PASS.

Commit:

```bash
git commit -m "feat(cognitive): emit deterministic recovery admission receipts"
```

---

### Task 6: Add non-authoritative exact-head CI verification lane

**Files:**
- Create: `.github/workflows/cognitive-recovery-admission-validator.yml`
- Modify: `sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py`

**Interfaces:**
- CI proves validator/test/schema implementation only.
- CI emits no admission receipt for the live incident and has no recovery signing authority.

- [ ] **Step 1: Add RED workflow-trust tests**

Read the workflow as text and require:

```python
self.assertIn("permissions:\n  contents: read", workflow)
for forbidden in (
    "contents: write",
    "id-token: write",
    "attestations: write",
    "artifact-metadata: write",
    "pull-requests: write",
    "google-github-actions/auth",
    "gcloud",
    "terraform apply",
    "git push",
):
    self.assertNotIn(forbidden, workflow)
```

Also require pinned `actions/checkout` and `actions/setup-python` commit SHAs, Python 3.12, `jsonschema==4.23.0`, and execution of the focused test file.

- [ ] **Step 2: Verify RED before workflow exists**

Run focused tests; expected failure because workflow file is missing.

- [ ] **Step 3: Create minimal read-only workflow**

Required structure:

```yaml
name: Cognitive Recovery Admission Validator

on:
  pull_request:

permissions:
  contents: read

jobs:
  validator:
    name: aegis / cognitive-recovery-admission-validator
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Checkout exact candidate
        uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065
        with:
          python-version: '3.12'
      - name: Install exact schema validator
        run: pip install jsonschema==4.23.0
      - name: Run recovery admission validator falsifier corpus
        run: python sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
```

Do not upload an artifact labeled as an admission receipt. The job is implementation evidence only.

- [ ] **Step 4: Run local workflow-contract tests GREEN and commit**

Commit:

```bash
git commit -m "ci(cognitive): verify offline recovery admission validator"
```

---

### Task 7: Exact-head verification and milestone closure

**Files:**
- No new production files unless a test reveals a defect.
- Update: PR description only after terminal evidence exists.

**Interfaces:**
- Produces milestone status `OFFLINE_VALIDATOR_VERIFIED_AT_EXACT_HEAD` or keeps `NOT_ESTABLISHED`.

- [ ] **Step 1: Fetch the current PR head after all commits**

Do not use a planned SHA. Resolve live head from GitHub.

- [ ] **Step 2: Fetch current-head workflow runs**

Require the dedicated `aegis / cognitive-recovery-admission-validator` job to be terminal `SUCCESS` on that exact head. Any new generated-state head invalidates the current-head claim until re-run.

- [ ] **Step 3: Inspect the dedicated job log**

Require focused tests to report PASS. Distinguish workflow authorization failures from validator failures.

- [ ] **Step 4: Re-fetch changed files**

The milestone PR may contain only:

```text
docs/superpowers/specs/2026-09-02-cognitive-recovery-admission-v1-design.md
docs/superpowers/plans/2026-09-02-cognitive-recovery-admission-v1.md
schemas/cognitive-recovery-admission-request.v1.schema.json
schemas/cognitive-recovery-admission-receipt.v1.schema.json
scripts/validate-cognitive-recovery-admission.py
sovereign-omega-v2/python/tests/test_cognitive_recovery_admission.py
.github/workflows/cognitive-recovery-admission-validator.yml
```

If generated state is added by a bot, classify it separately and re-establish exact-head evidence; do not silently broaden the milestone.

- [ ] **Step 5: Record the narrow status**

Only after terminal exact-head GREEN:

```text
RECOVERY_ADMISSION_DESIGN          = SPECIFIED
OFFLINE_ADMISSION_VALIDATOR        = VERIFIED_AT_EXACT_HEAD
HOSTED_BASE_OWNED_SIGNER           = NOT_ESTABLISHED
RECOVERY_MUTATION_AUTHORITY        = NONE
CANONICAL_MAIN_RECOVERY            = NOT_ADMITTED
PLATFORM_ENFORCEMENT               = NOT_ESTABLISHED unless freshly observed ENFORCED
GCP_DEPLOYMENT                     = DISABLED / NOT_AUTHORIZED
RIEMANN_HYPOTHESIS                 = NOT_PROVEN
```

- [ ] **Step 6: Stop this implementation milestone**

Do **not** add a signer, a `workflow_dispatch` recovery mutation, `git push main`, ruleset mutation, branch-protection mutation, cloud credentials, or GCP deployment under this plan. Those require separate approved specs because they change authority rather than merely validate evidence.

---

## Self-review

### Spec coverage

- Exact request identity: Tasks 1–2.
- Trusted root / ancestry / pinned repair and writer blobs: Task 3.
- Bounded diff: Task 3.
- Recovery evidence reproduction/binding: Task 3.
- Authority firewall: Task 3.
- Platform governance fail-closed: Task 4.
- Exact operator approval binding: Task 4.
- Deterministic admission receipt, mutation authority NONE: Tasks 2, 4, 5.
- Candidate cannot self-sign: Task 6 permissions and explicit milestone stop.
- Separate mutation gate: deliberately outside implementation milestone per spec; no mutation code is created.
- GCP isolation: Global Constraints, R5 falsifier, Task 6 permissions, Task 7 stop condition.
- RH authority isolation: Global Constraints and Task 7 status.

### Placeholder scan

The plan contains no `TODO`, `TBD`, generic “add validation”, or unspecified implementation step. Later hosted signing and canonical mutation are intentionally excluded rather than represented as placeholders.

### Type consistency

- Request schema field names match `valid_request()` and Task 4 bindings.
- Receipt field names match `valid_receipt()` and Task 5 CLI output.
- SHA-1 and SHA-256 types remain distinct throughout.
- `mutation_authority` is consistently `NONE`.
- `evaluate()` consumes the same four evidence objects used by CLI and tests.
