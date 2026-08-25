# Cross-Domain Collision V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an integer-first, offline-replayable cross-domain collision engine with immutable live-source snapshots, anti-double-counting rules, deterministic null-model evaluation, and append-only epistemic status transitions.

**Architecture:** External sources are ingestion-only evidence producers. They emit hash-bound `RegistrySnapshotV1` artifacts; the authoritative verifier consumes only immutable snapshots and deterministic local derivation receipts. Collision scoring is criterion-epoch-bound, and the `65010` fixture is explicitly retrospective, so it can establish exact mappings/collision semantics but cannot become prospective statistical evidence.

**Tech Stack:** Python 3.11 standard library, `dataclasses`, `enum`, `hashlib`, `json`, `random.Random`, `urllib.request` only in the non-authoritative ingestion module, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-cross-domain-collision-v1-design.md`

## Global Constraints

- Execute after `docs/superpowers/plans/2026-08-25-relational-status-foundation-v1.md` is complete and green.
- The authoritative CI path is fully offline and MUST NOT depend on mutable Unicode/NCBI network state.
- Live lookup produces snapshots only; it has no admission authority.
- `65010` is permanently `RETROSPECTIVE` in the V1 fixture.
- `CROSS_REGISTRY_COLLISION` requires at least two unique admissible external/standard domains; local arithmetic derivations never satisfy that threshold by themselves.
- Same-domain observations cannot be counted twice through alternate formatting/transforms.
- Unknown transforms, stale snapshot bindings, retrospective/prospective provenance splicing, and non-replayable null criteria fail closed.
- `STRUCTURAL_RELATION` cannot be minted from collision significance or a p-value.
- No merge, deployment, runtime mutation authority, RH claim, biological mechanism claim, or metaphysical claim is added.

---

### Task 1: Create canonical integer, transform, snapshot, and derivation types

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_collision.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: `research_invariants.sha256_hex`, `research_invariants.literal_sha256`, `_check_digest`, `StatusJournalV1`.
- Produces: `IntegerSubjectV1`, `TransformSpecV1`, `RegistrySnapshotV1`, `DerivationReceiptV1`, `EvidenceClass`, `SelectionProvenance`.

- [ ] **Step 1: Write RED tests for subject and transform determinism**

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
        self.assertEqual(a.value, b.value)
        self.assertEqual(a.subject_sha256, b.subject_sha256)
        self.assertEqual(a.hex_upper, "FDF2")
        self.assertEqual(a.unicode_codepoint_label, "U+FDF2")

    def test_unicode_label_rejects_out_of_range_integer(self):
        subject = cdc.IntegerSubjectV1(0x110000)
        with self.assertRaises(ValueError):
            _ = subject.unicode_codepoint_label

    def test_transform_epoch_changes_on_literal_edit(self):
        a = cdc.TransformSpecV1(
            "INTEGER_TO_HEX_V1", "1", "IntegerSubjectV1", "HexString", "uppercase hexadecimal"
        )
        b = cdc.TransformSpecV1(
            "INTEGER_TO_HEX_V1", "1", "IntegerSubjectV1", "HexString", "uppercase  hexadecimal"
        )
        self.assertNotEqual(a.criterion_sha256, b.criterion_sha256)
```

- [ ] **Step 2: Run test and verify RED**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
```

Expected: import failure because `cross_domain_collision.py` does not exist.

- [ ] **Step 3: Implement subject, transforms, enums, and canonical snapshot types**

Implement these exact public shapes:

```python
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
        object.__setattr__(self, "subject_sha256", ri.sha256_hex({
            "schema": "AEGIS_INTEGER_SUBJECT_V1",
            "value": self.value,
        }))

    @property
    def hex_upper(self) -> str:
        if self.value < 0:
            return "-" + format(-self.value, "X")
        return format(self.value, "X")

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
        for value in (self.transform_id, self.transform_version, self.input_type, self.output_type):
            if not value:
                raise ValueError("transform fields must be non-empty")
        object.__setattr__(self, "criterion_sha256", ri.literal_sha256(self.criterion_text))
```

Add frozen `RegistrySnapshotV1` and `DerivationReceiptV1` whose `content_sha256` / `receipt_sha256` are recomputed from every canonical semantic field. Reject an explicitly supplied digest that does not match recomputation.

- [ ] **Step 4: Add snapshot/derivation tamper tests**

Test that changing one canonical result byte produces a different digest, that an invalid 64-hex digest is rejected, and that local derivation receipts are tagged `DERIVED_PROPERTY` rather than an external registry class.

- [ ] **Step 5: Run compile + tests**

```bash
python -m py_compile sovereign-omega-v2/python/cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "feat(research): add canonical collision evidence types"
```

---

### Task 2: Add domain observations and anti-double-counting collision receipts

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: Task 1 evidence artifacts and the foundational relation/status APIs.
- Produces: `DomainObservationV1`, `CollisionCriterionV1`, `CollisionReceiptV1`, `evaluate_collision(...)`.

- [ ] **Step 1: Write RED tests for external-domain independence**

```python
def test_same_domain_cannot_inflate_independent_domain_count(self):
    subject = cdc.IntegerSubjectV1(65010)
    unicode_a = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "unicode-a")
    unicode_b = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "unicode-b")
    receipt = cdc.evaluate_collision(
        subject=subject,
        provenance=cdc.SelectionProvenance.RETROSPECTIVE,
        observations=[unicode_a, unicode_b],
        criterion=fixture_criterion(),
    )
    self.assertEqual(receipt.independent_external_domain_count, 1)
    self.assertFalse(receipt.cross_registry_collision)


def test_local_derived_property_does_not_satisfy_external_collision_threshold(self):
    subject = cdc.IntegerSubjectV1(65010)
    unicode_obs = fixture_observation(subject, "unicode", cdc.EvidenceClass.STANDARD_CODEPOINT_MAPPING, "unicode")
    arithmetic_obs = fixture_observation(subject, "number-theory", cdc.EvidenceClass.DERIVED_PROPERTY, "factorization")
    receipt = cdc.evaluate_collision(subject, cdc.SelectionProvenance.RETROSPECTIVE, [unicode_obs, arithmetic_obs], fixture_criterion())
    self.assertEqual(receipt.independent_external_domain_count, 1)
    self.assertFalse(receipt.cross_registry_collision)
```

- [ ] **Step 2: Write RED anti-splicing tests**

Create subject A and subject B. Attempt to evaluate B using an observation whose `subject_sha256` belongs to A. Expected: `ValueError`/`PermissionError`; never a FAIL-as-data collision receipt.

- [ ] **Step 3: Implement observation and criterion contracts**

`DomainObservationV1` fields:

```python
subject_sha256: str
domain_id: str
evidence_class: EvidenceClass
transform_id: str
transform_criterion_sha256: str
evidence_artifact_sha256: str
normalized_claim: str
observation_sha256: str
```

`CollisionCriterionV1` fields:

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
criterion_sha256: str
```

Require `universe_min <= universe_max`, `control_count > 0`, unique registry/transform IDs, and literal criterion hashing.

- [ ] **Step 4: Implement collision evaluation**

`evaluate_collision` MUST:

1. verify all observation subject digests equal the subject digest;
2. reject observation transform IDs absent from the frozen criterion;
3. classify unique external domains from `EXTERNAL_IDENTIFIER_MATCH` + `STANDARD_CODEPOINT_MAPPING` only;
4. exclude `DERIVED_PROPERTY` from the external count;
5. compute a deterministic score using V1 `score_function_id == "UNIQUE_EXTERNAL_DOMAINS_V1"`, where `score = independent_external_domain_count`;
6. set `cross_registry_collision = independent_external_domain_count >= 2`;
7. bind subject, provenance, ordered observation digests, criterion digest, score, external-domain count, and verdict into `receipt_sha256`.

Unknown score-function IDs fail closed.

- [ ] **Step 5: Run test suite**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "feat(research): add collision independence verifier"
```

---

### Task 3: Add deterministic null-model replay and provenance gate

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: `CollisionCriterionV1`, `CollisionReceiptV1`.
- Produces: `NullModelReceiptV1`, `generate_controls(...)`, `evaluate_null_model(...)`.

- [ ] **Step 1: Write RED replay tests**

```python
def test_control_generation_is_exactly_replayable(self):
    criterion = fixture_criterion(control_seed=1234, control_count=16)
    self.assertEqual(cdc.generate_controls(criterion), cdc.generate_controls(criterion))


def test_different_seed_changes_control_sequence(self):
    a = fixture_criterion(control_seed=1234, control_count=16)
    b = fixture_criterion(control_seed=1235, control_count=16)
    self.assertNotEqual(cdc.generate_controls(a), cdc.generate_controls(b))
```

- [ ] **Step 2: Implement control generator**

For V1, accept only `control_generator_id == "PY_RANDOM_UNIFORM_INT_V1"` and use a local `random.Random(control_seed)` instance. Generate exactly `control_count` integers with inclusive bounds:

```python
rng = random.Random(criterion.control_seed)
return tuple(rng.randint(criterion.universe_min, criterion.universe_max) for _ in range(criterion.control_count))
```

The global PRNG state MUST NOT be used.

- [ ] **Step 3: Write RED retrospective/prospective test**

```python
def test_retrospective_fixture_cannot_be_promoted_by_null_model(self):
    collision = retrospective_65010_collision_receipt()
    with self.assertRaises(PermissionError):
        cdc.evaluate_null_model(
            observed=collision,
            criterion=fixture_criterion(promotion_threshold=0.05),
            control_scores=[0] * 100,
        )
```

- [ ] **Step 4: Implement empirical p-value exactly**

`evaluate_null_model` takes a collision receipt plus control scores generated/evaluated under the same criterion and computes:

```python
extreme = sum(1 for score in control_scores if score >= observed.score)
p_emp = (1 + extreme) / (1 + len(control_scores))
```

It MUST verify `len(control_scores) == criterion.control_count`, bind every control score or their deterministic sequence digest, and reject criterion-digest mismatch. If `observed.provenance is RETROSPECTIVE`, it may produce a descriptive null receipt only when explicitly called with `allow_retrospective_descriptive=True`; such a receipt MUST contain `promotion_eligible=False`. Default behavior is fail closed.

- [ ] **Step 5: Add promotion semantics test**

For a prospective synthetic observation with `promotion_threshold=0.05`, assert `null_survived` equals `p_emp <= 0.05`; for `promotion_threshold=None`, assert no promotion verdict is minted.

- [ ] **Step 6: Run suite + commit**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
```

Then:

```bash
git add sovereign-omega-v2/python/cross_domain_collision.py sovereign-omega-v2/python/tests/test_cross_domain_collision.py
git commit -m "feat(research): add deterministic collision null model"
```

---

### Task 4: Add live-ingestion boundary with zero admission authority

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_ingest.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_ingest.py`

**Interfaces:**
- Consumes: `RegistrySnapshotV1`.
- Produces: `canonicalize_external_result(...)`, `fetch_json_snapshot(...)`.

- [ ] **Step 1: Write RED test proving connector failure is not a negative result**

```python
class FailingTransport:
    def __call__(self, url: str, timeout: float) -> bytes:
        raise TimeoutError("network unavailable")


def test_live_failure_yields_not_established_and_no_snapshot(self):
    outcome = ingest.fetch_json_snapshot(
        registry_id="ncbi-gene",
        registry_version_or_release="observed-live",
        query_key="65010",
        query_key_type="integer-id",
        url="https://example.invalid/65010",
        producer_id="test",
        transport=FailingTransport(),
    )
    self.assertEqual(outcome.status, "NOT_ESTABLISHED")
    self.assertIsNone(outcome.snapshot)
```

- [ ] **Step 2: Implement dependency-injected transport**

Define:

```python
@dataclass(frozen=True)
class IngestionOutcomeV1:
    status: str
    snapshot: RegistrySnapshotV1 | None
    error_class: str | None
    error_message: str | None
```

`fetch_json_snapshot` accepts a `transport(url, timeout) -> bytes` callback. The default transport may wrap `urllib.request.urlopen`, but tests use injected transports. Parse JSON with `json.loads`, pass the parsed canonical result into `RegistrySnapshotV1`, and return `ESTABLISHED` only when a snapshot is actually constructed.

On timeout, HTTP error, malformed JSON, or validation failure return `NOT_ESTABLISHED` and no snapshot. Do not fabricate an empty/negative registry result.

- [ ] **Step 3: Prove live response mutation changes snapshot digest**

Two injected transports returning JSON payloads that differ by one semantic value MUST produce different snapshot digests.

- [ ] **Step 4: Keep live tests network-free**

```bash
python -m py_compile sovereign-omega-v2/python/cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
```

Expected: PASS without internet.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_ingest.py sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
git commit -m "feat(research): add non-authoritative live snapshot ingestion"
```

---

### Task 5: Add the frozen 65010 retrospective fixture and offline replay

**Files:**
- Create: `.aegis/cross-domain/fixtures/65010-v1.json`
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_collision.py`

**Interfaces:**
- Consumes: Tasks 1-4 models.
- Produces: `load_fixture_bundle(path)`, exact `65010` replay receipt and status history.

- [ ] **Step 1: Create frozen fixture content**

The JSON bundle MUST include:

```json
{
  "schema": "AEGIS_CROSS_DOMAIN_FIXTURE_V1",
  "subject": {"value": 65010, "provenance": "RETROSPECTIVE"},
  "expected_representations": {"hex_upper": "FDF2", "unicode_codepoint_label": "U+FDF2"},
  "external_snapshots": [
    {
      "registry_id": "unicode",
      "query_key": "U+FDF2",
      "query_key_type": "unicode-codepoint",
      "result_kind": "assigned-codepoint-record",
      "canonical_result": {
        "codepoint": "U+FDF2",
        "name": "ARABIC LIGATURE ALLAH ISOLATED FORM"
      }
    },
    {
      "registry_id": "ncbi-gene",
      "query_key": "65010",
      "query_key_type": "gene-id",
      "result_kind": "gene-record",
      "canonical_result": {
        "gene_id": 65010,
        "symbol": "SLC26A6"
      }
    }
  ],
  "local_derivations": [
    {
      "derivation_id": "INTEGER_FACTORISATION_V1",
      "canonical_result": {"prime_factors": [2, 3, 5, 11, 197], "square_free": true}
    }
  ]
}
```

Before committing, populate the snapshot metadata fields required by `RegistrySnapshotV1` (`registry_version_or_release`, `source_locator`, `source_observed_at`, `ingestion_producer_id`) from the authoritative capture actually used. Do not invent a release version; if the source only exposes observation time, use an explicit value such as `observed-2026-08-25` and retain the source locator.

- [ ] **Step 2: Add fixture replay test**

The test MUST load the committed fixture without network access, reconstruct the subject/snapshots/observations, and assert:

```python
self.assertEqual(subject.hex_upper, "FDF2")
self.assertEqual(subject.unicode_codepoint_label, "U+FDF2")
self.assertTrue(collision.cross_registry_collision)
self.assertEqual(collision.independent_external_domain_count, 2)
self.assertEqual(collision.provenance, cdc.SelectionProvenance.RETROSPECTIVE)
```

- [ ] **Step 3: Prove status ceiling**

Create a collision-specific `StatusJournalV1` sequence:

`OBSERVED -> EXACT_MAPPING -> CROSS_REGISTRY_COLLISION`

Use the collision/evidence receipt hashes. Attempting `NULL_SURVIVED` without a promotion-eligible prospective `NullModelReceiptV1` MUST raise `PermissionError` in the collision status transition helper.

- [ ] **Step 4: Add offline determinism test**

Replay the fixture twice in separate object constructions and assert equality of subject digest, snapshot digests, observation digests, collision receipt digest, and status-transition digests.

- [ ] **Step 5: Run tests + commit**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
```

Then commit fixture and code.

---

### Task 6: Add offline CI and explicit evidence boundary documentation

**Files:**
- Create: `.github/workflows/cross-domain-collision.yml`
- Create: `docs/research/cross-domain-collision-v1.md`
- Modify: `.aegis/repo-cognition-v1.json` only through the repository's canonical cognition refresh path, never by hand.

**Interfaces:**
- Consumes: all completed V1 modules/tests/fixture.
- Produces: exact-head hosted verification with no live-source dependency.

- [ ] **Step 1: Create deterministic workflow**

Use:

```yaml
name: AEGIS Cross-Domain Collision V1

on:
  pull_request:
    paths:
      - "sovereign-omega-v2/python/cross_domain_collision.py"
      - "sovereign-omega-v2/python/cross_domain_ingest.py"
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
      - name: Run collision regressions
        run: python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
      - name: Run ingestion boundary regressions
        run: python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
      - name: Run inherited research-gate regressions
        run: python sovereign-omega-v2/python/tests/test_research_invariants.py
```

No `curl`, `wget`, registry API, or live lookup step is allowed in this admission workflow.

- [ ] **Step 2: Document exact epistemic statuses**

The research doc MUST state:

- `65010` exact hexadecimal/code-point-label transform: deterministic fact;
- Unicode/NCBI records: frozen external snapshot evidence;
- collision: observed cross-registry collision under V1 criterion;
- significance for the known seed: not prospectively established;
- structural/causal relation: `NOT_ESTABLISHED`;
- live connectors: evidence producers only.

- [ ] **Step 3: Run local full equivalent**

```bash
python -m py_compile \
  sovereign-omega-v2/python/research_invariants.py \
  sovereign-omega-v2/python/cross_domain_collision.py \
  sovereign-omega-v2/python/cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
```

Expected: all PASS, fully offline.

- [ ] **Step 4: Refresh repository cognition using the canonical existing refresh path**

First inspect the repository's current cognition workflow/command on the implementation head. Run that exact path; do not manually edit generated cognition hashes. Commit only generated changes produced by the canonical refresh.

- [ ] **Step 5: Push and exact-head verify**

Resolve the final SHA after cognition refresh. Inspect `AEGIS Cross-Domain Collision V1`, inherited `AEGIS Zero-Discretion Type Gates`, `Kernel One`, and any repository-native mandatory checks that actually trigger on the final head. Report each by exact SHA and distinguish skipped/not-triggered from success.

- [ ] **Step 6: Do not overclaim completion**

The final evidence statement may say `CrossDomainCollisionV1 offline vertical slice = ESTABLISHED` only if the exact-head tests prove the specified contracts. It MUST still say `non-random cross-domain mechanism = NOT_ESTABLISHED` unless separate prospective evidence exists.
