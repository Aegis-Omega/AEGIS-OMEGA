# Cross-Domain Collision V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an integer-first, offline-replayable cross-domain collision engine with immutable live-source snapshots, anti-double-counting rules, deterministic null-model evaluation, and append-only epistemic status transitions.

**Architecture:** External sources are ingestion-only evidence producers. They emit hash-bound `RegistrySnapshotV1` artifacts; the authoritative verifier consumes only immutable snapshots and deterministic local derivation receipts. Collision scoring is criterion-epoch-bound. The `65010` fixture is permanently retrospective, so it can establish exact mapping/collision semantics but cannot become prospective statistical evidence.

**Tech Stack:** Python 3.11 standard library, `dataclasses`, `enum`, `json`, `random.Random`, `urllib.request` only in the non-authoritative ingestion module, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-cross-domain-collision-v1-design.md`

## Global Constraints

- Execute after `docs/superpowers/plans/2026-08-25-relational-status-foundation-v1.md` is complete and green.
- Authoritative CI is fully offline; mutable Unicode/NCBI network state never gates admission.
- Live lookup produces snapshots only; it has no admission authority.
- `65010` is permanently `RETROSPECTIVE` in V1.
- `CROSS_REGISTRY_COLLISION` requires at least two unique admissible external/standard domains. Local arithmetic derivations cannot satisfy that threshold.
- Same-domain observations cannot be double-counted through formatting or alternate transforms.
- Unknown transforms, stale evidence bindings, provenance splicing, and non-replayable null criteria fail closed.
- `STRUCTURAL_RELATION` cannot be minted from collision significance or a p-value.
- No merge, deployment, runtime mutation authority, RH claim, biological mechanism claim, or metaphysical claim is added.

---

### Task 1: Canonical integer, transform, snapshot, and derivation types

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_collision.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: `research_invariants.sha256_hex`, `research_invariants.literal_sha256`, `research_invariants._check_digest`.
- Produces: `IntegerSubjectV1`, `TransformSpecV1`, `RegistrySnapshotV1`, `DerivationReceiptV1`, `EvidenceClass`, `SelectionProvenance`.

- [ ] **Step 1: Write RED subject/transform tests**

```python
import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc


class CrossDomainCollisionTests(unittest.TestCase):
    def test_integer_subject_is_representation_independent(self):
        a = cdc.IntegerSubjectV1(65010)
        b = cdc.IntegerSubjectV1(int("FDF2", 16))
        self.assertEqual(a.subject_sha256, b.subject_sha256)
        self.assertEqual(a.hex_upper, "FDF2")
        self.assertEqual(a.unicode_codepoint_label, "U+FDF2")

    def test_unicode_label_rejects_out_of_range_integer(self):
        with self.assertRaises(ValueError):
            _ = cdc.IntegerSubjectV1(0x110000).unicode_codepoint_label

    def test_transform_epoch_changes_on_literal_edit(self):
        a = cdc.TransformSpecV1("INTEGER_TO_HEX_V1", "1", "IntegerSubjectV1", "HexString", "uppercase hexadecimal")
        b = cdc.TransformSpecV1("INTEGER_TO_HEX_V1", "1", "IntegerSubjectV1", "HexString", "uppercase  hexadecimal")
        self.assertNotEqual(a.criterion_sha256, b.criterion_sha256)
```

- [ ] **Step 2: Run and verify RED**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
```

Expected: import failure because `cross_domain_collision.py` does not exist.

- [ ] **Step 3: Implement enums, subject, and transform types**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

import research_invariants as ri


class EvidenceClass(str, Enum):
    EXTERNAL_IDENTIFIER_MATCH = "EXTERNAL_IDENTIFIER_MATCH"
    STANDARD_CODEPOINT_MAPPING = "STANDARD_CODEPOINT_MAPPING"
    DERIVED_PROPERTY = "DERIVED_PROPERTY"


class SelectionProvenance(str, Enum):
    RETROSPECTIVE = "RETROSPECTIVE"
    PROSPECTIVE = "PROSPECTIVE"


@dataclass(frozen=True)
class IntegerSubjectV1:
    value: int
    subject_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError("IntegerSubjectV1 requires a Python int")
        object.__setattr__(self, "subject_sha256", ri.sha256_hex({
            "schema": "AEGIS_INTEGER_SUBJECT_V1",
            "value": self.value,
        }))

    @property
    def hex_upper(self) -> str:
        return ("-" + format(-self.value, "X")) if self.value < 0 else format(self.value, "X")

    @property
    def unicode_codepoint_label(self) -> str:
        if not 0 <= self.value <= 0x10FFFF:
            raise ValueError("integer is outside Unicode code-point range")
        width = 4 if self.value <= 0xFFFF else 6
        return f"U+{self.value:0{width}X}"


@dataclass(frozen=True)
class TransformSpecV1:
    transform_id: str
    transform_version: str
    input_type: str
    output_type: str
    criterion_text: str
    criterion_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not all((self.transform_id, self.transform_version, self.input_type, self.output_type, self.criterion_text)):
            raise ValueError("transform fields must be non-empty")
        object.__setattr__(self, "criterion_sha256", ri.literal_sha256(self.criterion_text))
```

- [ ] **Step 4: Implement exact snapshot and derivation contracts**

Add:

```python
@dataclass(frozen=True)
class RegistrySnapshotV1:
    registry_id: str
    registry_version_or_release: str
    query_key: str
    query_key_type: str
    result_kind: str
    canonical_result: Any
    source_locator: str
    source_observed_at: str
    ingestion_producer_id: str
    content_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if not all((self.registry_id, self.registry_version_or_release, self.query_key,
                    self.query_key_type, self.result_kind, self.source_locator,
                    self.source_observed_at, self.ingestion_producer_id)):
            raise ValueError("snapshot metadata fields must be non-empty")
        material = {
            "schema": "AEGIS_REGISTRY_SNAPSHOT_V1",
            "registry_id": self.registry_id,
            "registry_version_or_release": self.registry_version_or_release,
            "query_key": self.query_key,
            "query_key_type": self.query_key_type,
            "result_kind": self.result_kind,
            "canonical_result": self.canonical_result,
            "source_locator": self.source_locator,
            "source_observed_at": self.source_observed_at,
            "ingestion_producer_id": self.ingestion_producer_id,
        }
        object.__setattr__(self, "content_sha256", ri.sha256_hex(material))


@dataclass(frozen=True)
class DerivationReceiptV1:
    subject_sha256: str
    derivation_id: str
    derivation_version: str
    criterion_sha256: str
    canonical_result: Any
    receipt_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        ri._check_digest(self.subject_sha256, "subject_sha256")
        ri._check_digest(self.criterion_sha256, "criterion_sha256")
        if not self.derivation_id or not self.derivation_version:
            raise ValueError("derivation id/version must be non-empty")
        material = {
            "schema": "AEGIS_DERIVATION_RECEIPT_V1",
            "subject_sha256": self.subject_sha256,
            "derivation_id": self.derivation_id,
            "derivation_version": self.derivation_version,
            "criterion_sha256": self.criterion_sha256,
            "canonical_result": self.canonical_result,
        }
        object.__setattr__(self, "receipt_sha256", ri.sha256_hex(material))
```

- [ ] **Step 5: Add tamper/digest tests**

Construct two snapshots differing only in `canonical_result`; assert different `content_sha256`. Construct two derivation receipts differing only in a factorization value; assert different `receipt_sha256`.

- [ ] **Step 6: Verify GREEN and commit**

```bash
python -m py_compile sovereign-omega-v2/python/cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git add sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "feat(research): add canonical collision evidence types"
```

---

### Task 2: Domain observations and anti-double-counting collision receipts

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: Task 1 types.
- Produces: `DomainObservationV1`, `CollisionCriterionV1`, `CollisionReceiptV1`, `evaluate_collision(...)`.

- [ ] **Step 1: Implement reusable test helpers before RED tests**

In the test module add:

```python
def make_transform(transform_id: str = "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"):
    return cdc.TransformSpecV1(transform_id, "1", "IntegerSubjectV1", "RegistryKey", transform_id)


def make_criterion(**overrides):
    values = dict(
        universe_min=0,
        universe_max=100000,
        registry_set=("unicode", "ncbi-gene"),
        transform_set=("INTEGER_TO_UNICODE_CODEPOINT_V1", "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1", "INTEGER_TO_NUMBER_THEORY_PROPERTIES_V1"),
        independence_rule_id="UNIQUE_EXTERNAL_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=16,
        promotion_threshold=None,
        criterion_text="cdc-v1-test-criterion",
    )
    values.update(overrides)
    return cdc.CollisionCriterionV1(**values)


def make_observation(subject, domain_id, evidence_class, claim_suffix):
    transform_id = (
        "INTEGER_TO_NUMBER_THEORY_PROPERTIES_V1"
        if evidence_class is cdc.EvidenceClass.DERIVED_PROPERTY
        else "INTEGER_TO_UNICODE_CODEPOINT_V1" if domain_id == "unicode"
        else "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"
    )
    transform = make_transform(transform_id)
    artifact_sha = ri.sha256_hex({"fixture": claim_suffix})
    return cdc.DomainObservationV1.create(
        subject_sha256=subject.subject_sha256,
        domain_id=domain_id,
        evidence_class=evidence_class,
        transform_id=transform.transform_id,
        transform_criterion_sha256=transform.criterion_sha256,
        evidence_artifact_sha256=artifact_sha,
        normalized_claim=claim_suffix,
    )
```

Import `research_invariants as ri` in the test module.

- [ ] **Step 2: Write RED independence tests**

```python
def test_same_domain_cannot_inflate_independent_domain_count(self):
    subject = cdc.IntegerSubjectV1(65010)
    a = make_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "unicode-a")
    b = make_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "unicode-b")
    receipt = cdc.evaluate_collision(subject, cdc.SelectionProvenance.RETROSPECTIVE, [a, b], make_criterion())
    self.assertEqual(receipt.independent_external_domain_count, 1)
    self.assertFalse(receipt.cross_registry_collision)


def test_local_derivation_does_not_satisfy_external_collision_threshold(self):
    subject = cdc.IntegerSubjectV1(65010)
    unicode_obs = make_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "unicode")
    arithmetic = make_observation(subject, "number-theory", cdc.EvidenceClass.DERIVED_PROPERTY, "factorization")
    receipt = cdc.evaluate_collision(subject, cdc.SelectionProvenance.RETROSPECTIVE, [unicode_obs, arithmetic], make_criterion())
    self.assertEqual(receipt.independent_external_domain_count, 1)
    self.assertFalse(receipt.cross_registry_collision)
```

- [ ] **Step 3: Implement observation/criterion types**

`DomainObservationV1.create(...)` validates every digest and hashes:

```python
{
  "schema": "AEGIS_DOMAIN_OBSERVATION_V1",
  "subject_sha256": subject_sha256,
  "domain_id": domain_id,
  "evidence_class": evidence_class.value,
  "transform_id": transform_id,
  "transform_criterion_sha256": transform_criterion_sha256,
  "evidence_artifact_sha256": evidence_artifact_sha256,
  "normalized_claim": normalized_claim
}
```

`CollisionCriterionV1` fields are exactly:

```python
universe_min: int
universe_max: int
registry_set: tuple[str, ...]
transform_set: tuple[str, ...]
independence_rule_id: str
score_function_id: str
control_generator_id: str
control_seed: int
control_count: int
promotion_threshold: float | None
criterion_text: str
criterion_sha256: str = field(init=False)
```

Reject invalid bounds, non-positive control count, duplicate registry/transform IDs, unknown empty rule IDs, and thresholds outside `[0,1]`. Hash `criterion_text` literally.

- [ ] **Step 4: Implement `CollisionReceiptV1` and evaluator**

Evaluator rules:

```python
external_classes = {
    EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
    EvidenceClass.STANDARD_CODEPOINT_MAPPING,
}
```

Verify every observation subject digest matches the subject, every transform appears in `criterion.transform_set`, and every external observation domain appears in `criterion.registry_set`. For `score_function_id != "UNIQUE_EXTERNAL_DOMAINS_V1"`, raise `ValueError`.

Compute:

```python
external_domains = tuple(sorted({
    obs.domain_id for obs in observations if obs.evidence_class in external_classes
}))
score = len(external_domains)
cross_registry_collision = score >= 2
```

Sort observation digests before hashing the receipt so input list order does not alter semantics.

- [ ] **Step 5: Add anti-splicing/order tests**

Create subject A and B, then pass an A observation into B evaluation and assert `ValueError`. Evaluate the same observations in reverse order and assert identical `receipt_sha256`.

- [ ] **Step 6: Verify and commit**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
git add sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "feat(research): add collision independence verifier"
```

---

### Task 3: Deterministic null-model replay and provenance gate

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: `CollisionCriterionV1`, `CollisionReceiptV1`.
- Produces: `NullModelReceiptV1`, `generate_controls(...)`, `evaluate_null_model(...)`.

- [ ] **Step 1: Write RED replay tests**

```python
def test_control_generation_is_exactly_replayable(self):
    criterion = make_criterion(control_seed=1234, control_count=16)
    self.assertEqual(cdc.generate_controls(criterion), cdc.generate_controls(criterion))


def test_different_seed_changes_control_sequence(self):
    self.assertNotEqual(
        cdc.generate_controls(make_criterion(control_seed=1234)),
        cdc.generate_controls(make_criterion(control_seed=1235)),
    )
```

- [ ] **Step 2: Implement control generation**

Accept only `control_generator_id == "PY_RANDOM_UNIFORM_INT_V1"`. Use local state only:

```python
rng = random.Random(criterion.control_seed)
return tuple(rng.randint(criterion.universe_min, criterion.universe_max) for _ in range(criterion.control_count))
```

- [ ] **Step 3: Add a concrete prospective/retrospective collision helper in tests**

```python
def make_two_domain_collision(provenance):
    subject = cdc.IntegerSubjectV1(42)
    a = make_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "u")
    b = make_observation(subject, "ncbi-gene", cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH, "n")
    return cdc.evaluate_collision(subject, provenance, [a, b], make_criterion())
```

- [ ] **Step 4: Write RED provenance test**

```python
def test_retrospective_collision_is_not_promotion_eligible(self):
    with self.assertRaises(PermissionError):
        cdc.evaluate_null_model(
            observed=make_two_domain_collision(cdc.SelectionProvenance.RETROSPECTIVE),
            criterion=make_criterion(control_count=4, promotion_threshold=0.05),
            control_scores=[0, 0, 1, 1],
        )
```

- [ ] **Step 5: Implement empirical p-value receipt**

For `len(control_scores) != criterion.control_count` or criterion digest mismatch, raise `ValueError`. Compute:

```python
extreme = sum(1 for score in control_scores if score >= observed.score)
p_emp = (1 + extreme) / (1 + len(control_scores))
```

`NullModelReceiptV1` binds observed collision digest, criterion digest, control-score sequence digest, `p_emp`, `promotion_eligible`, and `null_survived`.

Default retrospective behavior raises `PermissionError`. With `allow_retrospective_descriptive=True`, emit a receipt with `promotion_eligible=False` and `null_survived=False` regardless of descriptive `p_emp`.

For prospective evidence, `promotion_eligible=True`; if `promotion_threshold is None`, set `null_survived=False` and record `threshold_applied=None`. Otherwise `null_survived = p_emp <= promotion_threshold`.

- [ ] **Step 6: Verify and commit**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git add sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "feat(research): add deterministic collision null model"
```

---

### Task 4: Live-ingestion boundary with zero admission authority

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_ingest.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_ingest.py`

**Interfaces:**
- Consumes: `RegistrySnapshotV1`.
- Produces: `IngestionOutcomeV1`, `fetch_json_snapshot(...)`.

- [ ] **Step 1: Write RED failure test**

```python
class FailingTransport:
    def __call__(self, url: str, timeout: float) -> bytes:
        raise TimeoutError("network unavailable")


def test_live_failure_yields_not_established_and_no_snapshot(self):
    outcome = ingest.fetch_json_snapshot(
        registry_id="ncbi-gene",
        registry_version_or_release="observed-live",
        query_key="65010",
        query_key_type="gene-id",
        result_kind="gene-record",
        source_locator="https://example.invalid/65010",
        source_observed_at="2026-08-25T00:00:00Z",
        producer_id="test",
        transport=FailingTransport(),
    )
    self.assertEqual(outcome.status, "NOT_ESTABLISHED")
    self.assertIsNone(outcome.snapshot)
```

- [ ] **Step 2: Implement injected transport and outcome**

```python
@dataclass(frozen=True)
class IngestionOutcomeV1:
    status: str
    snapshot: RegistrySnapshotV1 | None
    error_class: str | None
    error_message: str | None
```

`fetch_json_snapshot` accepts all fields shown in the test plus `timeout: float = 10.0`. The default transport is:

```python
def _default_transport(url: str, timeout: float) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()
```

Parse UTF-8 JSON. On success, pass the parsed object as `canonical_result` into `RegistrySnapshotV1` and return `IngestionOutcomeV1("ESTABLISHED", snapshot, None, None)`. Catch network/HTTP/Unicode/JSON/validation exceptions and return `NOT_ESTABLISHED` with no snapshot.

- [ ] **Step 3: Add deterministic success test**

Injected transport A returns `b'{"gene_id":65010,"symbol":"SLC26A6"}'`; transport B returns `b'{"gene_id":65010,"symbol":"DIFFERENT"}'`. Assert both are `ESTABLISHED` and snapshot digests differ.

- [ ] **Step 4: Verify and commit**

```bash
python -m py_compile sovereign-omega-v2/python/cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
git add sovereign-omega-v2/python/cross_domain_ingest.py sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
git commit -m "feat(research): add non-authoritative live snapshot ingestion"
```

---

### Task 5: Frozen 65010 retrospective fixture, replay, and status ceiling

**Files:**
- Create: `.aegis/cross-domain/fixtures/65010-v1.json`
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: Tasks 1-4 and `research_invariants.StatusJournalV1`.
- Produces: `load_fixture_bundle(path)`, `replay_fixture_bundle(path)`, `advance_collision_status(...)`.

- [ ] **Step 1: Capture authoritative Unicode and NCBI source records**

Use authoritative sources only. Record the exact source locator, observation time, and release/version if the source exposes one. The semantic payload frozen into the fixture must establish at minimum:

```json
{"codepoint":"U+FDF2","name":"ARABIC LIGATURE ALLAH ISOLATED FORM"}
```

and:

```json
{"gene_id":65010,"symbol":"SLC26A6"}
```

If either authoritative capture cannot be established, stop fixture promotion at `NOT_ESTABLISHED`; do not substitute an aggregator.

- [ ] **Step 2: Write the fixture bundle**

Use schema `AEGIS_CROSS_DOMAIN_FIXTURE_V1` with subject `65010`, provenance `RETROSPECTIVE`, expected representations `FDF2`/`U+FDF2`, both complete external snapshot objects, and a local derivation object whose exact factorization is `[2,3,5,11,197]` with `square_free=true`.

- [ ] **Step 3: Implement fixture loader/replay**

`load_fixture_bundle(path)` uses `json.load`, rejects any schema other than `AEGIS_CROSS_DOMAIN_FIXTURE_V1`, and returns the parsed mapping.

`replay_fixture_bundle(path)` must:

1. construct `IntegerSubjectV1` from fixture subject;
2. assert computed `hex_upper`/`unicode_codepoint_label` equal fixture expected representations;
3. reconstruct each `RegistrySnapshotV1` and local `DerivationReceiptV1` from frozen fields;
4. create one Unicode and one NCBI `DomainObservationV1` plus the local arithmetic observation;
5. evaluate under a frozen `CollisionCriterionV1` that includes exactly `unicode` and `ncbi-gene` as external registries;
6. return a frozen replay result containing subject, evidence artifacts, observations, criterion, and collision receipt.

- [ ] **Step 4: Implement collision status policy helper**

Define collision states as strings/constants:

```python
OBSERVED = "OBSERVED"
EXACT_MAPPING = "EXACT_MAPPING"
CROSS_REGISTRY_COLLISION = "CROSS_REGISTRY_COLLISION"
NULL_SURVIVED = "NULL_SURVIVED"
REPLICATED = "REPLICATED"
STRUCTURAL_RELATION = "STRUCTURAL_RELATION"
```

`advance_collision_status(journal, next_status, evidence_receipt_digests, criterion_sha256, reason, null_receipt=None)` applies these rules before calling `journal.append`:

- `NULL_SURVIVED` requires a non-null `NullModelReceiptV1` with `promotion_eligible=True` and `null_survived=True`.
- `STRUCTURAL_RELATION` always raises `PermissionError` in V1 because no structural-proof authority exists in this subsystem.
- Other states may be appended when caller supplies bound evidence digests; demotions remain allowed.

- [ ] **Step 5: Add exact 65010 replay tests**

```python
def test_65010_fixture_replays_to_retrospective_collision(self):
    replay = cdc.replay_fixture_bundle(FIXTURE_PATH)
    self.assertEqual(replay.subject.hex_upper, "FDF2")
    self.assertEqual(replay.subject.unicode_codepoint_label, "U+FDF2")
    self.assertEqual(replay.collision.independent_external_domain_count, 2)
    self.assertTrue(replay.collision.cross_registry_collision)
    self.assertEqual(replay.collision.provenance, cdc.SelectionProvenance.RETROSPECTIVE)


def test_65010_fixture_cannot_reach_null_survived_without_prospective_receipt(self):
    replay = cdc.replay_fixture_bundle(FIXTURE_PATH)
    journal = ri.StatusJournalV1("cdc-65010-v1")
    cdc.advance_collision_status(journal, cdc.OBSERVED, [replay.collision.receipt_sha256], replay.criterion.criterion_sha256, "observed")
    cdc.advance_collision_status(journal, cdc.EXACT_MAPPING, [replay.collision.receipt_sha256], replay.criterion.criterion_sha256, "exact mappings")
    cdc.advance_collision_status(journal, cdc.CROSS_REGISTRY_COLLISION, [replay.collision.receipt_sha256], replay.criterion.criterion_sha256, "two external domains")
    with self.assertRaises(PermissionError):
        cdc.advance_collision_status(journal, cdc.NULL_SURVIVED, [replay.collision.receipt_sha256], replay.criterion.criterion_sha256, "not allowed")
```

- [ ] **Step 6: Add exact replay determinism test**

Replay twice and assert equality of subject digest, each external snapshot digest, each observation digest, collision receipt digest, and the transition digests produced by identical status sequences.

- [ ] **Step 7: Verify and commit**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
git add .aegis/cross-domain/fixtures/65010-v1.json sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "test(research): freeze 65010 collision replay fixture"
```

---

### Task 6: Offline CI, research boundary document, cognition refresh, exact-head evidence

**Files:**
- Create: `.github/workflows/cross-domain-collision.yml`
- Create: `docs/research/cross-domain-collision-v1.md`
- Modify generated cognition files only through the repository's canonical refresh path.

**Interfaces:**
- Consumes: all completed V1 code/tests/fixture.
- Produces: exact-head hosted verification with no live-source dependency.

- [ ] **Step 1: Create deterministic workflow**

```yaml
name: AEGIS Cross-Domain Collision V1

on:
  pull_request:
    paths:
      - "sovereign-omega-v2/python/research_invariants.py"
      - "sovereign-omega-v2/python/cross_domain_collision.py"
      - "sovereign-omega-v2/python/cross_domain_ingest.py"
      - "sovereign-omega-v2/python/tests/test_research_invariants.py"
      - "sovereign-omega-v2/python/tests/test_cross_domain_collision.py"
      - "sovereign-omega-v2/python/tests/test_cross_domain_ingest.py"
      - ".aegis/cross-domain/fixtures/**"
      - "docs/research/cross-domain-collision-v1.md"
      - ".github/workflows/cross-domain-collision.yml"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  offline-collision-verification:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Compile
        run: |
          python -m py_compile \
            sovereign-omega-v2/python/research_invariants.py \
            sovereign-omega-v2/python/cross_domain_collision.py \
            sovereign-omega-v2/python/cross_domain_ingest.py
      - name: Run inherited research-gate regressions
        run: python sovereign-omega-v2/python/tests/test_research_invariants.py
      - name: Run collision regressions
        run: python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
      - name: Run ingestion-boundary regressions
        run: python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
```

No `curl`, `wget`, registry API, or live lookup is allowed in the admission workflow.

- [ ] **Step 2: Write the research boundary document**

State exactly:

- `65010 -> FDF2 -> U+FDF2` representation/code-point-label transform = deterministic fact;
- Unicode and NCBI claims = frozen external snapshot evidence;
- V1 collision = exact observed cross-registry collision under the frozen criterion;
- prospective statistical significance for the known seed = `NOT_ESTABLISHED`;
- cross-domain structural/causal mechanism = `NOT_ESTABLISHED`;
- live connectors = evidence producers only.

- [ ] **Step 3: Run full local offline verification**

```bash
python -m py_compile \
  sovereign-omega-v2/python/research_invariants.py \
  sovereign-omega-v2/python/cross_domain_collision.py \
  sovereign-omega-v2/python/cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
```

- [ ] **Step 4: Refresh repository cognition canonically**

Inspect the exact implementation head for the repository's existing cognition refresh command/workflow. Run that path; never hand-edit generated cognition hashes. Commit only generated output emitted by that path.

- [ ] **Step 5: Exact-head hosted verification**

Resolve the final SHA after cognition refresh. Inspect workflows on that exact SHA: `AEGIS Cross-Domain Collision V1`, inherited `AEGIS Zero-Discretion Type Gates`, `Kernel One`, and every repository-native check that actually triggers. Report SUCCESS/SKIPPED/FAILURE separately. Ancestor GREEN does not count.

- [ ] **Step 6: Completion claim boundary**

Only if exact-head offline verification passes, report `CrossDomainCollisionV1 offline vertical slice = ESTABLISHED`. Continue to report `non-random cross-domain mechanism = NOT_ESTABLISHED` until separate prospective evidence exists.
