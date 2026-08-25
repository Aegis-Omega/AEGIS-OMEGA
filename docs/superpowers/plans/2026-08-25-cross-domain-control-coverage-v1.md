# Cross-Domain Control Coverage V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add proof-carrying registry coverage so prospective null-model promotion is possible only when every generated control subject has complete, hash-valid MATCH/NO_MATCH evidence across the frozen registry set.

**Architecture:** Keep collision/statistical authority in `cross_domain_collision.py` and add a focused `cross_domain_coverage.py` module for adapter contracts, probe receipts, coverage aggregation, and control construction. Live/network ingestion remains non-authoritative; the authoritative CI path stays fully offline and uses deterministic immutable source artifacts. `evaluate_null_model(...)` is strengthened to bind exact control coverage lineage while preserving retrospective descriptive behavior.

**Tech Stack:** Python 3.11 standard library, `dataclasses`, `enum`, `typing`, existing `research_invariants`, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-cross-domain-control-coverage-v1-design.md`

## Global Constraints

- `65010` remains permanently `RETROSPECTIVE`; this work cannot promote it to prospective significance.
- `MATCH`, `NO_MATCH`, and `NOT_ESTABLISHED` are distinct typed outcomes.
- `NO_MATCH` requires explicit immutable negative source evidence under a frozen adapter contract; timeout/missing evidence/error never means no match.
- `coverage_complete` is derived only; no caller-supplied boolean has authority.
- Duplicate, missing, extra, reordered, cross-subject, cross-criterion, or tampered coverage evidence fails closed.
- The authoritative CI path performs no live Unicode/NCBI/network lookup.
- `STRUCTURAL_RELATION` remains unreachable from collision statistics.
- No merge or deployment is authorized by this plan.

---

### Task 1: Adapter contracts and probe receipts

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_coverage.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_coverage.py`
- Modify: `.github/workflows/cross-domain-collision.yml`

**Interfaces:**
- Consumes: `cross_domain_collision.IntegerSubjectV1`, `CollisionCriterionV1`, `RegistrySnapshotV1`, `TransformSpecV1`; `research_invariants.sha256_hex`, `_check_digest`, `freeze_hash_material`.
- Produces: `RegistryProbeOutcomeV1`, `RegistryAdapterContractV1`, `ProbeFailureEvidenceV1`, `RegistryProbeReceiptV1`, `verify_registry_probe_receipt(...)`, `probe_registry_snapshot(...)`, `probe_not_established(...)`.

- [ ] **Step 1: Add RED tests and wire them into CI**

Create `test_cross_domain_coverage.py` with helpers and these tests:

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


def criterion():
    return cdc.CollisionCriterionV1(
        universe_min=0,
        universe_max=100000,
        registry_set=("fixture-a", "fixture-b"),
        transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234,
        control_count=4,
        promotion_threshold=0.05,
        criterion_text="coverage-v1-test-criterion",
    )


def adapter(registry_id):
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


def snapshot(subject, registry_id, matched):
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
    def test_no_match_requires_explicit_negative_source_evidence(self):
        subject = cdc.IntegerSubjectV1(42)
        with self.assertRaises(ValueError):
            cov.RegistryProbeReceiptV1.create_unverified(
                subject_sha256=subject.subject_sha256,
                registry_id="fixture-a",
                query_key="42",
                query_key_type="integer-decimal",
                transform_id="INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",
                transform_criterion_sha256=adapter("fixture-a").transform_criterion_sha256,
                registry_version_or_release="fixture-v1",
                adapter_contract_sha256=adapter("fixture-a").contract_sha256,
                source_evidence_sha256=None,
                outcome=cov.RegistryProbeOutcomeV1.NO_MATCH,
                criterion_sha256=criterion().criterion_sha256,
            )

    def test_exact_match_and_no_match_are_distinct_probe_receipts(self):
        subject = cdc.IntegerSubjectV1(42)
        c = criterion()
        a = adapter("fixture-a")
        match = cov.probe_registry_snapshot(subject, c, a, snapshot(subject, "fixture-a", True))
        no_match = cov.probe_registry_snapshot(subject, c, a, snapshot(subject, "fixture-a", False))
        self.assertEqual(match.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(no_match.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)
        self.assertNotEqual(match.receipt_sha256, no_match.receipt_sha256)

    def test_unsupported_adapter_rule_fails_closed(self):
        subject = cdc.IntegerSubjectV1(42)
        c = criterion()
        bad = replace(adapter("fixture-a"), positive_result_rule_id="UNKNOWN_RULE")
        with self.assertRaises(ValueError):
            cov.probe_registry_snapshot(subject, c, bad, snapshot(subject, "fixture-a", True))

    def test_probe_digest_tampering_is_detected(self):
        subject = cdc.IntegerSubjectV1(42)
        receipt = cov.probe_registry_snapshot(subject, criterion(), adapter("fixture-a"), snapshot(subject, "fixture-a", True))
        with self.assertRaises(ValueError):
            cov.verify_registry_probe_receipt(replace(receipt, receipt_sha256="f" * 64))
```

Modify `.github/workflows/cross-domain-collision.yml` to run:

```yaml
- name: Run control-coverage regressions
  run: python sovereign-omega-v2/python/tests/test_cross_domain_coverage.py
```

- [ ] **Step 2: Run hosted CI and verify RED**

Expected: `AEGIS Cross-Domain Collision V1` fails specifically because `cross_domain_coverage` does not exist; inherited gates remain independently reported.

- [ ] **Step 3: Implement the minimal probe contract**

In `cross_domain_coverage.py` define:

```python
class RegistryProbeOutcomeV1(str, Enum):
    MATCH = "MATCH"
    NO_MATCH = "NO_MATCH"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
```

`RegistryAdapterContractV1` is frozen and hashes every field from the approved spec. Support exactly these V1 rule IDs:

```python
SUPPORTED_POSITIVE_RULES = {"MATCH_BOOL_TRUE_V1"}
SUPPORTED_NEGATIVE_RULES = {"MATCH_BOOL_FALSE_V1"}
SUPPORTED_AMBIGUOUS_RULES = {"STATUS_NOT_ESTABLISHED_V1"}
SUPPORTED_CANONICALIZATION_RULES = {"CANONICAL_JSON_V1"}
SUPPORTED_TRANSFORMS = {"INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"}
```

`RegistryProbeReceiptV1` must require a valid 64-hex `source_evidence_sha256` for every outcome. Do not expose a public constructor that can mint a semantically authoritative receipt from flags alone; use an internal `_mint_probe_receipt(...)` and a test-only `create_unverified(...)` that always rejects `source_evidence_sha256=None` before hashing.

`probe_registry_snapshot(subject, criterion, adapter, snapshot)` validates registry, criterion, query key/type, transform, adapter digest/rules, and requires `snapshot.canonical_result` to be a mapping containing a literal boolean `match`. `True -> MATCH`; `False -> NO_MATCH`; missing/non-bool `match` fails closed.

`ProbeFailureEvidenceV1` freezes failure class/message/source locator and hashes it. `probe_not_established(...)` binds such an artifact to a `NOT_ESTABLISHED` probe receipt.

- [ ] **Step 4: Run CI and verify GREEN for Task 1**

Expected: coverage probe tests pass; existing collision, fixture, hardening, zero-discretion and Kernel One checks remain green on the exact implementation commit.

- [ ] **Step 5: Commit boundary**

Commit message: `feat(research): add proof-carrying registry probe receipts`.

---

### Task 2: Coverage aggregation and control construction

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_coverage.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_coverage.py`

**Interfaces:**
- Consumes: Task 1 probe receipts and existing collision evaluator.
- Produces: `ControlCoverageReceiptV1`, `verify_control_coverage_receipt(...)`, `evaluate_control_from_probes(...) -> tuple[CollisionReceiptV1, ControlCoverageReceiptV1]`.

- [ ] **Step 1: Add RED coverage tests**

Add tests:

```python
def complete_probe_set(subject, c):
    return [
        cov.probe_registry_snapshot(subject, c, adapter("fixture-a"), snapshot(subject, "fixture-a", False)),
        cov.probe_registry_snapshot(subject, c, adapter("fixture-b"), snapshot(subject, "fixture-b", False)),
    ]


def test_missing_registry_cannot_establish_complete_coverage(self):
    subject = cdc.IntegerSubjectV1(42)
    c = criterion()
    one = complete_probe_set(subject, c)[:1]
    coverage = cov.aggregate_control_coverage(subject, c, one)
    self.assertFalse(coverage.coverage_complete)
    self.assertEqual(coverage.missing_registry_ids, ("fixture-b",))


def test_not_established_registry_blocks_complete_coverage(self):
    subject = cdc.IntegerSubjectV1(42)
    c = criterion()
    failure = cov.ProbeFailureEvidenceV1("TimeoutError", "offline fixture timeout", "fixture://failure", "2026-08-25T00:00:00Z", "coverage-test")
    probes = [
        cov.probe_registry_snapshot(subject, c, adapter("fixture-a"), snapshot(subject, "fixture-a", False)),
        cov.probe_not_established(subject, c, adapter("fixture-b"), "fixture-v1", failure),
    ]
    coverage = cov.aggregate_control_coverage(subject, c, probes)
    self.assertFalse(coverage.coverage_complete)
    self.assertEqual(coverage.unestablished_registry_ids, ("fixture-b",))


def test_duplicate_registry_probe_fails_closed(self):
    subject = cdc.IntegerSubjectV1(42)
    c = criterion()
    probe = complete_probe_set(subject, c)[0]
    with self.assertRaises(ValueError):
        cov.aggregate_control_coverage(subject, c, [probe, probe])


def test_complete_negative_coverage_mints_zero_score_control(self):
    subject = cdc.IntegerSubjectV1(42)
    c = criterion()
    collision, coverage = cov.evaluate_control_from_probes(subject, c, complete_probe_set(subject, c))
    self.assertTrue(coverage.coverage_complete)
    self.assertEqual(collision.score, 0)
    self.assertEqual(collision.provenance, cdc.SelectionProvenance.PROSPECTIVE)


def test_caller_order_does_not_change_coverage_digest(self):
    subject = cdc.IntegerSubjectV1(42)
    c = criterion()
    probes = complete_probe_set(subject, c)
    a = cov.aggregate_control_coverage(subject, c, probes)
    b = cov.aggregate_control_coverage(subject, c, list(reversed(probes)))
    self.assertEqual(a.receipt_sha256, b.receipt_sha256)
```

- [ ] **Step 2: Verify RED**

Expected: tests fail because coverage aggregation/control construction functions are absent.

- [ ] **Step 3: Implement aggregation**

`ControlCoverageReceiptV1` fields match the spec exactly. `aggregate_control_coverage(...)` validates every probe digest and subject/criterion binding, rejects duplicate/extra registries, canonicalizes probe order by `criterion.registry_set`, derives covered/missing/unestablished sets, derives `coverage_complete`, and hashes all semantic fields.

`verify_control_coverage_receipt(...)` recomputes the receipt hash and validates canonical order, counts, uniqueness, and the derived invariant:

```python
coverage_complete == (
    not missing_registry_ids
    and not unestablished_registry_ids
    and covered_registry_ids == required_registry_ids
)
```

- [ ] **Step 4: Implement control construction**

`evaluate_control_from_probes(...)` first aggregates coverage, then mints collision observations only from `MATCH` probes. Each MATCH observation uses the probe receipt digest as its evidence artifact digest and the adapter transform binding already verified by the probe. `NO_MATCH` produces no observation. The returned collision is always `PROSPECTIVE` and uses existing `cdc.evaluate_collision(...)`.

- [ ] **Step 5: Verify GREEN and commit**

Run the complete cross-domain workflow. Commit message: `feat(research): add complete control coverage receipts`.

---

### Task 3: Null-model coverage lineage

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_collision.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_coverage.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_hardening.py`

**Interfaces:**
- Consumes: `ControlCoverageReceiptV1`, `verify_control_coverage_receipt(...)` from Task 2.
- Produces: strengthened `NullModelReceiptV1` with `control_coverage_receipt_sha256s`; strengthened `evaluate_null_model(..., control_coverages=...)`.

- [ ] **Step 1: Add RED null-lineage tests**

Add a helper that constructs the exact generated controls using `cdc.generate_controls(c)` and `cov.evaluate_control_from_probes(...)` with complete negative fixture probes.

Add tests:

```python
def test_prospective_null_model_rejects_missing_coverage(self):
    c = criterion_with(control_count=4)
    observed = observed_two_domain_collision(c)
    collisions, coverages = generated_complete_controls(c)
    with self.assertRaises(PermissionError):
        cdc.evaluate_null_model(observed, c, collisions)


def test_prospective_null_model_rejects_reordered_coverage(self):
    c = criterion_with(control_count=4)
    observed = observed_two_domain_collision(c)
    collisions, coverages = generated_complete_controls(c)
    with self.assertRaises(ValueError):
        cdc.evaluate_null_model(observed, c, collisions, control_coverages=list(reversed(coverages)))


def test_complete_generated_control_coverage_is_bound_into_null_receipt(self):
    c = criterion_with(control_count=100)
    observed = observed_two_domain_collision(c)
    collisions, coverages = generated_complete_controls(c)
    receipt = cdc.evaluate_null_model(observed, c, collisions, control_coverages=coverages)
    self.assertEqual(receipt.control_coverage_receipt_sha256s, tuple(x.receipt_sha256 for x in coverages))
    self.assertTrue(receipt.promotion_eligible)
```

Retain a regression proving `RETROSPECTIVE + allow_retrospective_descriptive=True` can still emit a non-promoting descriptive receipt without promotion-grade coverage.

- [ ] **Step 2: Verify RED**

Expected: current signature either rejects `control_coverages` or still permits prospective evaluation without it.

- [ ] **Step 3: Extend `NullModelReceiptV1`**

Add:

```python
control_coverage_receipt_sha256s: tuple[str, ...]
```

Include it in `_null_model_receipt_material(...)` and digest verification. For `promotion_eligible=True`, require its length to equal `control_count`; for non-promoting retrospective descriptive receipts, allow the empty tuple.

- [ ] **Step 4: Strengthen `evaluate_null_model(...)`**

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

Use `TYPE_CHECKING` for the annotation and a local runtime import from `cross_domain_coverage` to avoid module-cycle initialization.

For a prospective observed receipt: missing `control_coverages` raises `PermissionError`. Verify count and exact position; each coverage must be hash-valid, `coverage_complete=True`, same subject as the collision control at that index, same criterion, and correspond to the exact generated subject at that index. Bind coverage receipt digests into the null receipt in generated-control order.

For retrospective descriptive evaluation: keep existing explicit opt-in; coverage is not required because the receipt is never promotion-eligible and carries no survival verdict.

- [ ] **Step 5: Verify GREEN and commit**

Run collision, coverage, fixture, hardening, zero-discretion, Kernel One. Commit message: `feat(research): bind null promotion to complete control coverage`.

---

### Task 4: Status-lineage hardening and documentation

**Files:**
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_hardening.py`
- Modify: `docs/research/cross-domain-collision-v1.md`

**Interfaces:**
- Consumes: strengthened null receipt from Task 3.
- Produces: adversarial proof that `NULL_SURVIVED` cannot be minted from incomplete/spliced coverage lineage; explicit research boundary documentation.

- [ ] **Step 1: Add RED/positive status lineage tests**

Add tests that construct a valid prospective surviving null receipt with complete coverage and then verify:

```python
with self.assertRaises(PermissionError):
    cdc.append_collision_status(..., null_receipt=replace(valid_null, control_coverage_receipt_sha256s=()))
```

and a positive test that exact collision + criterion + null digest + intact coverage lineage permits `NULL_SURVIVED`.

- [ ] **Step 2: Verify RED if status verifier does not yet reject tampered coverage lineage**

Expected: tampered null receipt either fails `verify_null_model_receipt(...)` or status promotion; if it already fails because Task 3 digest verification covers the field, record that as immediate GREEN and do not add redundant production code.

- [ ] **Step 3: Update research boundary doc**

Document exactly:

- empty observations are not absence evidence;
- promotion-grade controls require one exact probe per frozen registry;
- `NO_MATCH` requires registry-adapter negative semantics and immutable evidence;
- `NOT_ESTABLISHED` blocks complete coverage;
- null receipts bind exact ordered coverage lineage;
- synthetic fixture adapters prove authority semantics only, not real Unicode/NCBI prospective coverage;
- `65010` prospective significance remains `NOT_ESTABLISHED`.

- [ ] **Step 4: Verify and commit**

Commit message: `docs(research): define proof-carrying control coverage boundary`.

---

### Task 5: Exact-head verification and cognition convergence

**Files:**
- Generated only: `.aegis/repo-cognition-v1.json`, `.claude.json`, `skill-hashes.sha256` through the canonical refresh workflow when triggered.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: exact-head hosted evidence and final bounded implementation status.

- [ ] **Step 1: Wait for canonical cognitive-manifest refresh fixed point**

Do not hand-edit generated cognition files. Resolve the branch head after the bot refresh has converged.

- [ ] **Step 2: Run/fetch exact-head hosted checks**

Require terminal status on the exact final head for:

- `AEGIS Cross-Domain Collision V1`
- `AEGIS Zero-Discretion Type Gates`
- `Kernel One`
- repository cognition if it triggers on that exact head
- every other repository-native check that actually triggers for the changed paths

Report `SUCCESS`, `SKIPPED`, `ACTION_REQUIRED`, and `FAILURE` separately; ancestor GREEN never substitutes for descendant evidence.

- [ ] **Step 3: Completion boundary**

Only if the exact final head has authoritative terminal GREEN evidence, report:

`ControlCoverageV1 offline authority semantics = ESTABLISHED`.

Continue to report:

- `65010 prospective significance = NOT_ESTABLISHED`
- `real Unicode/NCBI promotion-grade control coverage = NOT_ESTABLISHED` unless separately implemented and verified
- `non-random cross-domain mechanism = NOT_ESTABLISHED`
- `structural/causal relation = NOT_ESTABLISHED`
