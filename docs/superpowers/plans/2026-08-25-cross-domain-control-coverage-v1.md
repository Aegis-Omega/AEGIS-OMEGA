# Cross-Domain Control Coverage V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add proof-carrying registry coverage so prospective null-model promotion is possible only when every generated control subject has complete, re-verifiable MATCH/NO_MATCH evidence across the frozen registry set.

**Architecture:** Keep collision/statistical authority in `cross_domain_collision.py` and add `cross_domain_coverage.py` for frozen adapter contracts, source-bound probe bundles, coverage aggregation, and prospective control construction. A raw probe receipt is never sufficient for promotion-grade coverage: the verifier consumes `VerifiedRegistryProbeV1`, which carries the receipt plus the exact adapter and immutable source artifact needed to replay the classification. `evaluate_null_model(...)` then binds exact ordered coverage-receipt lineage. The authoritative CI path remains network-free.

**Tech Stack:** Python 3.11 standard library, `dataclasses`, `enum`, `typing`, existing `research_invariants`, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-cross-domain-control-coverage-v1-design.md`

## Global Constraints

- `65010` remains permanently `RETROSPECTIVE`; this work cannot promote it to prospective significance.
- `MATCH`, `NO_MATCH`, and `NOT_ESTABLISHED` are distinct typed outcomes.
- `NO_MATCH` requires explicit immutable negative source evidence under a frozen adapter contract; timeout/missing evidence/error never means no match.
- `coverage_complete` is derived only; no caller-supplied boolean has authority.
- Raw `RegistryProbeReceiptV1` objects are evidence records, not sufficient promotion authority without their replayable source+adapter bundle.
- Duplicate, missing, extra, reordered, cross-subject, cross-criterion, or tampered coverage evidence fails closed.
- The authoritative CI path performs no live Unicode/NCBI/network lookup.
- `STRUCTURAL_RELATION` remains unreachable from collision statistics.
- No merge or deployment is authorized by this plan.

---

### Task 1: Frozen adapter contracts and source-bound probe bundles

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_coverage.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_coverage.py`
- Modify: `.github/workflows/cross-domain-collision.yml`

**Interfaces:**
- Consumes: `cross_domain_collision.IntegerSubjectV1`, `CollisionCriterionV1`, `RegistrySnapshotV1`; `research_invariants.sha256_hex`, `_check_digest`, `freeze_hash_material`.
- Produces: `RegistryProbeOutcomeV1`, `RegistryAdapterContractV1`, `ProbeFailureEvidenceV1`, `RegistryProbeReceiptV1`, `VerifiedRegistryProbeV1`, `verify_registry_probe_receipt(...)`, `verify_verified_probe(...)`, `probe_registry_snapshot(...)`, `probe_not_established(...)`.

- [ ] **Step 1: Write the RED probe tests**

Create `test_cross_domain_coverage.py`:

```python
import pathlib
import sys
import unittest
from dataclasses import replace

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

import cross_domain_collision as cdc
import cross_domain_coverage as cov
import research_invariants as ri


def make_criterion(control_count=4, threshold=0.05):
    return cdc.CollisionCriterionV1(
        universe_min=0,
        universe_max=100000,
        registry_set=("fixture-a", "fixture-b"),
        transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=control_count,
        promotion_threshold=threshold,
        criterion_text=f"coverage-v1-test-criterion:{control_count}:{threshold}",
    )


def make_adapter(registry_id):
    return cov.RegistryAdapterContractV1(
        registry_id=registry_id,
        adapter_version="1",
        query_key_type="integer-decimal",
        transform_id="INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",
        transform_criterion_sha256=ri.literal_sha256("integer identity external lookup key v1"),
        positive_result_rule_id="MATCH_BOOL_TRUE_V1",
        negative_result_rule_id="MATCH_BOOL_FALSE_V1",
        ambiguous_result_rule_id="STATUS_NOT_ESTABLISHED_V1",
        canonicalization_rule_id="CANONICAL_JSON_V1",
        contract_text=f"fixture adapter {registry_id} v1",
    )


def make_snapshot(subject, registry_id, matched):
    return cdc.RegistrySnapshotV1(
        registry_id=registry_id,
        registry_version_or_release="fixture-v1",
        query_key=str(subject.value),
        query_key_type="integer-decimal",
        result_kind="fixture-registry-result",
        canonical_result={"match": matched},
        source_locator=f"fixture://{registry_id}/{subject.value}",
        source_observed_at="2026-08-25T00:00:00Z",
        ingestion_producer_id="coverage-test",
    )


class CoverageProbeTests(unittest.TestCase):
    def test_match_and_no_match_are_source_replayable_and_distinct(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        adapter = make_adapter("fixture-a")
        match = cov.probe_registry_snapshot(subject, c, adapter, make_snapshot(subject, "fixture-a", True))
        no_match = cov.probe_registry_snapshot(subject, c, adapter, make_snapshot(subject, "fixture-a", False))
        self.assertEqual(match.receipt.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(no_match.receipt.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)
        self.assertNotEqual(match.receipt.receipt_sha256, no_match.receipt.receipt_sha256)
        cov.verify_verified_probe(match)
        cov.verify_verified_probe(no_match)

    def test_unsupported_adapter_rule_fails_closed(self):
        subject = cdc.IntegerSubjectV1(42)
        c = make_criterion()
        bad = replace(make_adapter("fixture-a"), positive_result_rule_id="UNKNOWN_RULE")
        with self.assertRaises(ValueError):
            cov.probe_registry_snapshot(subject, c, bad, make_snapshot(subject, "fixture-a", True))

    def test_probe_receipt_digest_tampering_is_detected(self):
        subject = cdc.IntegerSubjectV1(42)
        probe = cov.probe_registry_snapshot(subject, make_criterion(), make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", True))
        tampered_receipt = replace(probe.receipt, receipt_sha256="f" * 64)
        with self.assertRaises(ValueError):
            cov.verify_verified_probe(replace(probe, receipt=tampered_receipt))

    def test_source_payload_tampering_breaks_replay(self):
        subject = cdc.IntegerSubjectV1(42)
        probe = cov.probe_registry_snapshot(subject, make_criterion(), make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False))
        wrong_source = make_snapshot(subject, "fixture-a", True)
        with self.assertRaises(ValueError):
            cov.verify_verified_probe(replace(probe, source_snapshot=wrong_source))
```

Wire the new test into `.github/workflows/cross-domain-collision.yml`:

```yaml
- name: Run control-coverage regressions
  run: python sovereign-omega-v2/python/tests/test_cross_domain_coverage.py
```

- [ ] **Step 2: Verify RED on hosted CI**

Expected: `AEGIS Cross-Domain Collision V1` fails specifically because `cross_domain_coverage` is absent; report inherited checks separately.

- [ ] **Step 3: Implement the minimal source-bound probe model**

`cross_domain_coverage.py` defines:

```python
class RegistryProbeOutcomeV1(str, Enum):
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"

SUPPORTED_POSITIVE_RULES = {"MATCH_BOOL_TRUE_V1"}
SUPPORTED_NEGATIVE_RULES = {"MATCH_BOOL_FALSE_V1"}
SUPPORTED_AMBIGUOUS_RULES = {"STATUS_NOT_ESTABLISHED_V1"}
SUPPORTED_CANONICALIZATION_RULES = {"CANONICAL_JSON_V1"}
SUPPORTED_TRANSFORMS = {"INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"}
```

`RegistryAdapterContractV1` has every field from the approved spec and computes `contract_sha256` from all semantic fields. Unsupported rule IDs fail validation.

`RegistryProbeReceiptV1` contains exactly the approved receipt fields and validates all digest/string/enum types. Its hash is recomputed by `verify_registry_probe_receipt(...)`.

`ProbeFailureEvidenceV1` freezes `failure_class`, `failure_message`, `source_locator`, `source_observed_at`, `producer_id`, and hashes them as `evidence_sha256`.

`VerifiedRegistryProbeV1` is:

```python
@dataclass(frozen=True)
class VerifiedRegistryProbeV1:
    receipt: RegistryProbeReceiptV1
    adapter: RegistryAdapterContractV1
    source_snapshot: cdc.RegistrySnapshotV1 | None = None
    failure_evidence: ProbeFailureEvidenceV1 | None = None
```

Exactly one source carrier is present. `MATCH`/`NO_MATCH` require `source_snapshot`; `NOT_ESTABLISHED` requires `failure_evidence`.

`probe_registry_snapshot(...)` validates subject range, criterion registry/transform membership, registry identity, query key `str(subject.value)`, query-key type, adapter digest/rules, immutable snapshot digest, and literal boolean `canonical_result["match"]`. It mints `MATCH` for `True` and `NO_MATCH` for `False`.

`probe_not_established(...)` requires `ProbeFailureEvidenceV1` and mints only `NOT_ESTABLISHED`.

`verify_verified_probe(...)` replays all of the above and checks that the recomputed receipt equals the carried receipt; therefore a raw fabricated receipt cannot become promotion-grade coverage.

- [ ] **Step 4: Verify GREEN and commit**

Run the full cross-domain workflow. Commit message: `feat(research): add source-bound registry probe evidence`.

---

### Task 2: Coverage aggregation and prospective control construction

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_coverage.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_coverage.py`

**Interfaces:**
- Consumes: `VerifiedRegistryProbeV1` from Task 1.
- Produces: `ControlCoverageReceiptV1`, `verify_control_coverage_receipt(...)`, `aggregate_control_coverage(...)`, `evaluate_control_from_probes(...) -> tuple[cdc.CollisionReceiptV1, ControlCoverageReceiptV1]`.

- [ ] **Step 1: Add RED coverage tests**

Append:

```python
def complete_negative_probes(subject, c):
    return [
        cov.probe_registry_snapshot(subject, c, make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False)),
        cov.probe_registry_snapshot(subject, c, make_adapter("fixture-b"), make_snapshot(subject, "fixture-b", False)),
    ]


def test_missing_registry_cannot_establish_complete_coverage(self):
    subject = cdc.IntegerSubjectV1(42)
    c = make_criterion()
    coverage = cov.aggregate_control_coverage(subject, c, complete_negative_probes(subject, c)[:1])
    self.assertFalse(coverage.coverage_complete)
    self.assertEqual(coverage.missing_registry_ids, ("fixture-b",))


def test_not_established_registry_blocks_complete_coverage(self):
    subject = cdc.IntegerSubjectV1(42)
    c = make_criterion()
    failure = cov.ProbeFailureEvidenceV1(
        "TimeoutError", "offline fixture timeout", "fixture://failure",
        "2026-08-25T00:00:00Z", "coverage-test"
    )
    probes = [
        cov.probe_registry_snapshot(subject, c, make_adapter("fixture-a"), make_snapshot(subject, "fixture-a", False)),
        cov.probe_not_established(subject, c, make_adapter("fixture-b"), "fixture-v1", failure),
    ]
    coverage = cov.aggregate_control_coverage(subject, c, probes)
    self.assertFalse(coverage.coverage_complete)
    self.assertEqual(coverage.unestablished_registry_ids, ("fixture-b",))


def test_duplicate_registry_probe_fails_closed(self):
    subject = cdc.IntegerSubjectV1(42)
    c = make_criterion()
    probe = complete_negative_probes(subject, c)[0]
    with self.assertRaises(ValueError):
        cov.aggregate_control_coverage(subject, c, [probe, probe])


def test_complete_negative_coverage_mints_zero_score_control(self):
    subject = cdc.IntegerSubjectV1(42)
    c = make_criterion()
    collision, coverage = cov.evaluate_control_from_probes(subject, c, complete_negative_probes(subject, c))
    self.assertTrue(coverage.coverage_complete)
    self.assertEqual(collision.score, 0)
    self.assertEqual(collision.provenance, cdc.SelectionProvenance.PROSPECTIVE)


def test_caller_probe_order_does_not_change_coverage_digest(self):
    subject = cdc.IntegerSubjectV1(42)
    c = make_criterion()
    probes = complete_negative_probes(subject, c)
    a = cov.aggregate_control_coverage(subject, c, probes)
    b = cov.aggregate_control_coverage(subject, c, list(reversed(probes)))
    self.assertEqual(a.receipt_sha256, b.receipt_sha256)
```

- [ ] **Step 2: Verify RED**

Expected: missing aggregation/control APIs.

- [ ] **Step 3: Implement `ControlCoverageReceiptV1` and aggregation**

Fields are exactly:

```python
subject_sha256: str
criterion_sha256: str
required_registry_ids: tuple[str, ...]
probe_receipt_sha256s: tuple[str, ...]
covered_registry_ids: tuple[str, ...]
missing_registry_ids: tuple[str, ...]
unestablished_registry_ids: tuple[str, ...]
coverage_complete: bool
receipt_sha256: str
```

`aggregate_control_coverage(...)` first calls `verify_verified_probe(...)` for every bundle, rejects duplicate/extra registries, canonicalizes probe order by `criterion.registry_set`, derives all registry sets and `coverage_complete`, and hashes all fields. Missing registries return an incomplete receipt; duplicate/extra/mismatched/tampered probes raise.

`verify_control_coverage_receipt(...)` recomputes the hash, checks canonical ordering and uniqueness, and enforces:

```python
receipt.coverage_complete == (
    not receipt.missing_registry_ids
    and not receipt.unestablished_registry_ids
    and receipt.covered_registry_ids == receipt.required_registry_ids
)
```

- [ ] **Step 4: Implement `evaluate_control_from_probes(...)`**

Re-verify every bundle. Build `DomainObservationV1` only for `MATCH` probes, using the probe receipt digest as `evidence_artifact_sha256`; `NO_MATCH` contributes coverage only; `NOT_ESTABLISHED` contributes neither collision observation nor complete coverage. Call existing `cdc.evaluate_collision(..., PROSPECTIVE, ...)` and return the collision plus coverage receipt.

- [ ] **Step 5: Verify GREEN and commit**

Commit message: `feat(research): add complete control coverage receipts`.

---

### Task 3: Bind null-model promotion to exact coverage lineage

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_coverage.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_hardening.py`

**Interfaces:**
- Consumes: `ControlCoverageReceiptV1`, `verify_control_coverage_receipt(...)`.
- Produces: `NullModelReceiptV1.control_coverage_receipt_sha256s`; strengthened `evaluate_null_model(..., control_coverages=...)`.

- [ ] **Step 1: Add concrete test helpers**

In `test_cross_domain_coverage.py` add:

```python
def observed_collision(c):
    subject = cdc.IntegerSubjectV1(65010)
    observations = [
        cdc.DomainObservationV1(subject.subject_sha256, "fixture-a", cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
                                "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1", "a" * 64, "b" * 64, "fixture-a match"),
        cdc.DomainObservationV1(subject.subject_sha256, "fixture-b", cdc.EvidenceClass.EXTERNAL_IDENTIFIER_MATCH,
                                "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1", "c" * 64, "d" * 64, "fixture-b match"),
    ]
    return cdc.evaluate_collision(subject, cdc.SelectionProvenance.PROSPECTIVE, observations, c)


def generated_complete_controls(c):
    collisions = []
    coverages = []
    for value in cdc.generate_controls(c):
        subject = cdc.IntegerSubjectV1(value)
        collision, coverage = cov.evaluate_control_from_probes(subject, c, complete_negative_probes(subject, c))
        collisions.append(collision)
        coverages.append(coverage)
    return tuple(collisions), tuple(coverages)
```

- [ ] **Step 2: Add RED null-lineage tests**

```python
def test_prospective_null_model_rejects_missing_coverage(self):
    c = make_criterion(control_count=4)
    collisions, _ = generated_complete_controls(c)
    with self.assertRaises(PermissionError):
        cdc.evaluate_null_model(observed_collision(c), c, collisions)


def test_prospective_null_model_rejects_reordered_coverage(self):
    c = make_criterion(control_count=4)
    collisions, coverages = generated_complete_controls(c)
    with self.assertRaises(ValueError):
        cdc.evaluate_null_model(observed_collision(c), c, collisions, control_coverages=tuple(reversed(coverages)))


def test_complete_coverage_is_bound_into_null_receipt(self):
    c = make_criterion(control_count=100)
    collisions, coverages = generated_complete_controls(c)
    receipt = cdc.evaluate_null_model(observed_collision(c), c, collisions, control_coverages=coverages)
    self.assertEqual(receipt.control_coverage_receipt_sha256s, tuple(x.receipt_sha256 for x in coverages))
    self.assertTrue(receipt.promotion_eligible)
```

Also retain existing retrospective descriptive tests and update them only as needed for the new receipt field.

- [ ] **Step 3: Verify RED**

Expected: current prospective null evaluator still accepts collision receipts without coverage and does not bind coverage digests.

- [ ] **Step 4: Extend `NullModelReceiptV1`**

Add:

```python
control_coverage_receipt_sha256s: tuple[str, ...]
```

Add the field to `_null_model_receipt_material(...)` and `verify_null_model_receipt(...)`. For `promotion_eligible=True`, its length must equal `control_count`; for a non-promoting retrospective descriptive receipt, the empty tuple is permitted.

- [ ] **Step 5: Strengthen `evaluate_null_model(...)`**

Use:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cross_domain_coverage import ControlCoverageReceiptV1
```

Signature:

```python
def evaluate_null_model(
    observed: CollisionReceiptV1,
    criterion: CollisionCriterionV1,
    control_receipts: Sequence[CollisionReceiptV1],
    *,
    control_coverages: Sequence["ControlCoverageReceiptV1"] | None = None,
    allow_retrospective_descriptive: bool = False,
) -> NullModelReceiptV1:
```

For `PROSPECTIVE`, `control_coverages=None` raises `PermissionError`. Runtime-import `cross_domain_coverage` inside the function, verify each coverage receipt, require `coverage_complete=True`, require exact subject/criterion equality with the collision at the same index, require exact generated-subject equality at that index, and bind coverage receipt digests in generated-control order. Reordering/splicing fails.

For `RETROSPECTIVE + allow_retrospective_descriptive=True`, preserve the existing non-promoting behavior and allow no coverage lineage, because the receipt cannot carry a survival verdict.

- [ ] **Step 6: Verify GREEN and commit**

Commit message: `feat(research): bind null promotion to control coverage`.

---

### Task 4: Adversarial status-lineage hardening and research boundary

**Files:**
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_hardening.py`
- Modify: `docs/research/cross-domain-collision-v1.md`

**Interfaces:**
- Consumes: Task 3 null receipt.
- Produces: tamper/splicing regressions for coverage lineage and updated epistemic boundary.

- [ ] **Step 1: Add status-lineage regressions**

Construct a valid prospective surviving null receipt using complete generated coverage. Add:

```python
with self.assertRaises(PermissionError):
    cdc.append_collision_status(
        journal,
        "NULL_SURVIVED",
        [tampered.receipt_sha256],
        c.criterion_sha256,
        "coverage lineage tampering must not promote",
        null_receipt=tampered,
    )
```

where `tampered = replace(valid_null, control_coverage_receipt_sha256s=())`.

Add a positive test showing the exact untouched null receipt, exact criterion, exact prior collision lineage, and null receipt digest permit the existing `NULL_SURVIVED` transition.

- [ ] **Step 2: Run tests**

If Task 3 hash verification already rejects the tampered lineage, record immediate GREEN; do not add redundant production branches. If it does not, minimally tighten `verify_null_model_receipt(...)` or `append_collision_status(...)` until the falsifier passes.

- [ ] **Step 3: Update `docs/research/cross-domain-collision-v1.md`**

Add explicit statements that:

- empty observations are not absence evidence;
- promotion-grade controls require one replayable probe bundle per frozen registry;
- `NO_MATCH` requires frozen adapter negative semantics and immutable source evidence;
- `NOT_ESTABLISHED` blocks complete coverage;
- null receipts bind exact ordered coverage lineage;
- local fixture adapters prove authority semantics only, not real Unicode/NCBI prospective coverage;
- `65010 prospective significance = NOT_ESTABLISHED`.

- [ ] **Step 4: Verify and commit**

Commit message: `docs(research): define proof-carrying control coverage boundary`.

---

### Task 5: Exact-head verification and cognition convergence

**Files:**
- Generated only through canonical automation: `.aegis/repo-cognition-v1.json`, `.claude.json`, `skill-hashes.sha256`.

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: exact-head hosted evidence and bounded implementation status.

- [ ] **Step 1: Let canonical cognition refresh reach a fixed point**

Do not hand-edit generated cognition files. Resolve the branch head only after the bot-generated commits stop moving it.

- [ ] **Step 2: Fetch terminal exact-head checks**

Require terminal results on the exact final head for:

- `AEGIS Cross-Domain Collision V1`
- `AEGIS Zero-Discretion Type Gates`
- `Kernel One`
- repository cognition if triggered on that exact head
- every other repository-native check triggered by changed paths

Report `SUCCESS`, `SKIPPED`, `ACTION_REQUIRED`, and `FAILURE` separately. Ancestor GREEN never substitutes for descendant evidence.

- [ ] **Step 3: Apply the completion boundary**

Only with terminal exact-head GREEN authority evidence may the implementation be reported as:

`ControlCoverageV1 offline authority semantics = ESTABLISHED`.

Continue to report:

- `65010 prospective significance = NOT_ESTABLISHED`
- `real Unicode/NCBI promotion-grade control coverage = NOT_ESTABLISHED` unless separately built and verified
- `non-random cross-domain mechanism = NOT_ESTABLISHED`
- `structural/causal relation = NOT_ESTABLISHED`
