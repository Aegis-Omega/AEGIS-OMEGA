# Prospective Epoch V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a preregistered deterministic 1000-draw integer epoch whose only scored external domains are Unicode 17.0.0 General_Category and NCBI Gene UID existence, with live bytes captured non-authoritatively and all classification replayed offline.

**Architecture:** Add an epoch/generation layer above the existing Cross-Domain Collision + ControlCoverage spine. Add exact-byte capture receipts to `cross_domain_ingest.py`, source-specific offline adapters in a new module, and epoch-level draw/summary receipts that accept only source-replayable probe evidence. Existing `65010` fixture behavior remains untouched and retrospective.

**Tech Stack:** Python 3.11+ stdlib only, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-prospective-epoch-v1-design.md`

## Global Constraints

- Scored registries are exactly `("unicode", "ncbi-gene")`.
- Integer universe is exactly `[0, 100000]`.
- First operational `subject_count` is `1000`.
- Generator is `PY_RANDOM_UNIFORM_INT_V1`, positional draws with replacement.
- Epoch 1 `promotion_threshold` is `None`; epoch summary cannot mint `NULL_SURVIVED`.
- Unicode authority source is exact versioned Unicode 17.0.0 `DerivedGeneralCategory.txt`.
- NCBI authority source is Gene ESearch exact `[UID]` query semantics with at most 100 unique UIDs per deterministic batch.
- Live I/O is evidence acquisition only; authoritative CI performs no network calls.
- `NOT_ESTABLISHED` never becomes `NO_MATCH`.
- Incomplete draws remain in the generated denominator and prevent `COMPLETE` status.
- Integer `65010` has no special-case path.
- No third scored domain is introduced.

---

### Task 1: Freeze epoch and prove positional generation lineage

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_epoch.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_epoch.py`
- Modify: `.github/workflows/cross-domain-collision.yml`

**Interfaces:**
- Consumes: `cross_domain_collision.IntegerSubjectV1`, `CollisionCriterionV1`, `generate_controls`; `research_invariants.sha256_hex`, `_check_digest`.
- Produces: `ProspectiveEpochV1`, `SubjectGenerationReceiptV1`, `make_epoch_v1`, `epoch_collision_criterion`, `generate_subject_receipts`, `verify_subject_generation_receipt`.

- [ ] **Step 1: Write RED tests and wire only the epoch test into CI**

Create `test_cross_domain_epoch.py`:

```python
import pathlib
import sys
import unittest
from dataclasses import replace

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_epoch as epoch


class ProspectiveEpochTests(unittest.TestCase):
    def test_epoch_is_exactly_unicode_plus_ncbi(self):
        e = epoch.make_epoch_v1(seed=123456789, subject_count=8)
        self.assertEqual(e.registry_ids, ("unicode", "ncbi-gene"))
        self.assertEqual((e.universe_min, e.universe_max), (0, 100000))
        self.assertIsNone(e.promotion_threshold)

    def test_epoch_digest_changes_when_seed_changes(self):
        self.assertNotEqual(
            epoch.make_epoch_v1(seed=1, subject_count=8).epoch_sha256,
            epoch.make_epoch_v1(seed=2, subject_count=8).epoch_sha256,
        )

    def test_generation_replays_identically(self):
        e = epoch.make_epoch_v1(seed=1234, subject_count=16)
        a = epoch.generate_subject_receipts(e)
        b = epoch.generate_subject_receipts(e)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)
        self.assertEqual(len({r.generated_sequence_sha256 for r in a}), 1)

    def test_generation_receipt_wrong_index_fails(self):
        e = epoch.make_epoch_v1(seed=1234, subject_count=16)
        r = epoch.generate_subject_receipts(e)[0]
        with self.assertRaises(ValueError):
            epoch.verify_subject_generation_receipt(e, replace(r, draw_index=1))

    def test_generation_receipt_cross_epoch_splice_fails(self):
        a = epoch.make_epoch_v1(seed=1234, subject_count=16)
        b = epoch.make_epoch_v1(seed=1235, subject_count=16)
        with self.assertRaises(ValueError):
            epoch.verify_subject_generation_receipt(b, epoch.generate_subject_receipts(a)[0])

    def test_known_duplicate_seed_preserves_two_draw_positions(self):
        e = epoch.make_epoch_v1(seed=27, subject_count=64)
        draws = epoch.generate_subject_receipts(e)
        self.assertEqual(draws[40].value, 85237)
        self.assertEqual(draws[62].value, 85237)
        self.assertEqual(draws[40].subject_sha256, draws[62].subject_sha256)
        self.assertNotEqual(draws[40].draw_index, draws[62].draw_index)


if __name__ == "__main__":
    unittest.main()
```

Extend the workflow path trigger with `cross_domain_epoch.py` and `test_cross_domain_epoch.py`; add a single `Run prospective epoch regressions` step after collision regressions. Do not yet reference the future adapter module/test.

- [ ] **Step 2: Confirm RED on the PR merge ref**

Expected epoch step failure: import/module missing because `cross_domain_epoch.py` does not exist. Existing collision/coverage code must remain unaffected.

- [ ] **Step 3: Implement minimal deterministic epoch/generation types**

`ProspectiveEpochV1` fields are exactly those frozen by the spec. `make_epoch_v1(*, seed, subject_count=1000)` rejects bool-as-int seed/count and non-positive counts, hard-codes the two registries and V1 policies, and hashes all fields. `epoch_collision_criterion` maps the epoch to the existing criterion with transform set `("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",)` and threshold `None`. `generate_subject_receipts` hashes the full ordered generated tuple once and mints one positional receipt per draw. Verification regenerates the sequence, checks index/value/subject/sequence/generator/epoch bindings, and recomputes the receipt digest.

- [ ] **Step 4: Require GREEN**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
```

Expected: PASS; exact-head hosted Cross-Domain workflow must also be terminal SUCCESS before Task 2.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_epoch.py sovereign-omega-v2/python/tests/test_cross_domain_epoch.py .github/workflows/cross-domain-collision.yml
git commit -m "feat(research): add prospective epoch generation lineage"
```

---

### Task 2: Add immutable raw-byte source capture receipts

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_ingest.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_ingest.py`

**Interfaces:**
- Produces: `SourceCaptureReceiptV1`, `VerifiedSourceCaptureV1`, `capture_source_bytes`, `verify_source_capture`.

- [ ] **Step 1: Add RED capture tests**

Append:

```python
from dataclasses import replace

class SourceCaptureReceiptTests(unittest.TestCase):
    def test_raw_byte_tampering_breaks_capture_replay(self):
        bundle = ingest.capture_source_bytes(
            source_id="unicode-ucd", source_contract_sha256="a" * 64,
            request_identity="unicode://17.0.0/DerivedGeneralCategory.txt",
            request_subject_sha256s=(), source_version_or_release="17.0.0",
            response_status=200, media_type="text/plain",
            raw_content=b"0041 ; Lu\n0378 ; Cn\n",
            observed_at="2026-08-25T00:00:00Z", producer_id="test", attempt_index=0,
        )
        ingest.verify_source_capture(bundle)
        with self.assertRaises(ValueError):
            ingest.verify_source_capture(replace(bundle, raw_content=b"tampered"))

    def test_retry_requires_previous_attempt_digest(self):
        first = ingest.capture_source_bytes(
            source_id="ncbi-gene-esearch", source_contract_sha256="b" * 64,
            request_identity="batch:1", request_subject_sha256s=("c" * 64,),
            source_version_or_release="observed-2026-08-25", response_status=503,
            media_type="application/json", raw_content=b"{}",
            observed_at="2026-08-25T00:00:00Z", producer_id="test", attempt_index=0,
        )
        second = ingest.capture_source_bytes(
            source_id="ncbi-gene-esearch", source_contract_sha256="b" * 64,
            request_identity="batch:1", request_subject_sha256s=("c" * 64,),
            source_version_or_release="observed-2026-08-25", response_status=200,
            media_type="application/json", raw_content=b"{}",
            observed_at="2026-08-25T00:01:00Z", producer_id="test", attempt_index=1,
            previous_attempt_sha256=first.receipt.receipt_sha256,
        )
        ingest.verify_source_capture(second)
        with self.assertRaises(ValueError):
            ingest.capture_source_bytes(
                source_id="ncbi-gene-esearch", source_contract_sha256="b" * 64,
                request_identity="batch:1", request_subject_sha256s=("c" * 64,),
                source_version_or_release="observed-2026-08-25", response_status=200,
                media_type="application/json", raw_content=b"{}",
                observed_at="2026-08-25T00:01:00Z", producer_id="test", attempt_index=1,
                previous_attempt_sha256=None,
            )
```

- [ ] **Step 2: Confirm RED**

Existing four ingest tests must still pass; new cases must fail only because capture APIs do not exist.

- [ ] **Step 3: Implement receipt/bundle**

Receipt fields exactly follow the spec. Hash `raw_content` as exact bytes with SHA-256; never put bytes into canonical JSON. Copy subject-digest input to tuple. `attempt_index == 0` requires no previous digest; `attempt_index > 0` requires a valid digest. `verify_source_capture` recomputes byte hash, byte length, receipt hash, digest syntax, and retry shape.

- [ ] **Step 4: Require GREEN**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_cross_domain_hardening.py
```

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_ingest.py sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
git commit -m "feat(research): add immutable source capture receipts"
```

---

### Task 3: Add Unicode 17.0 and NCBI Gene ESearch offline adapters

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_registry_adapters.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py`
- Modify: `sovereign-omega-v2/python/cross_domain_coverage.py`
- Modify: `.github/workflows/cross-domain-collision.yml`

**Interfaces:**
- Produces source contract types, `SourceVerifiedProbeV1`, source contract/adapter factories, `make_ncbi_batch_request`, `probe_unicode_general_category`, `probe_ncbi_gene_esearch`, `verify_source_verified_probe`.

- [ ] **Step 1: Write concrete RED adapter tests**

Use this exact fixture skeleton:

```python
import pathlib
import sys
import unittest

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))
import cross_domain_collision as cdc
import cross_domain_coverage as cov
import cross_domain_ingest as ingest
import cross_domain_registry_adapters as adapters

UNICODE_FIXTURE = b"# DerivedGeneralCategory-17.0.0.txt\n0041 ; Lu\n0378..0379 ; Cn\n"
NCBI_MATCH = b'{"esearchresult":{"count":"1","retmax":"2","retstart":"0","idlist":["42"],"querytranslation":"42[UID] OR 43[UID]"}}'


def criterion():
    return cdc.CollisionCriterionV1(
        universe_min=0, universe_max=100000,
        registry_set=("unicode", "ncbi-gene"),
        transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
        independence_rule_id="UNIQUE_DOMAIN_ID_V1",
        score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
        control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
        control_seed=1234, control_count=8,
        promotion_threshold=None,
        criterion_text="prospective-adapter-test-v1",
    )


def unicode_capture(raw):
    contract = adapters.unicode_source_contract_v1()
    return ingest.capture_source_bytes(
        source_id=contract.source_id, source_contract_sha256=contract.contract_sha256,
        request_identity=contract.source_locator, request_subject_sha256s=(),
        source_version_or_release=contract.release, response_status=200,
        media_type="text/plain", raw_content=raw,
        observed_at="2026-08-25T00:00:00Z", producer_id="test", attempt_index=0,
    )


def ncbi_fixture(raw):
    subjects = (cdc.IntegerSubjectV1(42), cdc.IntegerSubjectV1(43))
    request_identity, ordered = adapters.make_ncbi_batch_request(subjects)
    contract = adapters.ncbi_gene_source_contract_v1()
    capture = ingest.capture_source_bytes(
        source_id=contract.source_id, source_contract_sha256=contract.contract_sha256,
        request_identity=request_identity,
        request_subject_sha256s=tuple(s.subject_sha256 for s in ordered),
        source_version_or_release="observed-2026-08-25", response_status=200,
        media_type="application/json", raw_content=raw,
        observed_at="2026-08-25T00:00:00Z", producer_id="test", attempt_index=0,
    )
    return subjects, ordered, capture


class RegistryAdapterTests(unittest.TestCase):
    def test_unicode_non_cn_is_match_and_cn_is_no_match(self):
        c = criterion()
        a = adapters.probe_unicode_general_category(cdc.IntegerSubjectV1(0x41), c, unicode_capture(UNICODE_FIXTURE))
        b = adapters.probe_unicode_general_category(cdc.IntegerSubjectV1(0x378), c, unicode_capture(UNICODE_FIXTURE))
        self.assertEqual(a.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(b.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)
        adapters.verify_source_verified_probe(a)
        adapters.verify_source_verified_probe(b)

    def test_unicode_overlap_fails_closed(self):
        with self.assertRaises(ValueError):
            adapters.probe_unicode_general_category(
                cdc.IntegerSubjectV1(0x41), criterion(),
                unicode_capture(b"0040..0042 ; Lu\n0041 ; Cn\n"),
            )

    def test_ncbi_uid_presence_and_absence_are_distinct(self):
        subjects, ordered, capture = ncbi_fixture(NCBI_MATCH)
        match = adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)
        no_match = adapters.probe_ncbi_gene_esearch(subjects[1], criterion(), ordered, capture)
        self.assertEqual(match.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.MATCH)
        self.assertEqual(no_match.probe.receipt.outcome, cov.RegistryProbeOutcomeV1.NO_MATCH)

    def test_ncbi_unexpected_uid_fails_closed(self):
        raw = b'{"esearchresult":{"count":"1","retmax":"2","retstart":"0","idlist":["999"],"querytranslation":"42[UID] OR 43[UID]"}}'
        subjects, ordered, capture = ncbi_fixture(raw)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)

    def test_ncbi_warning_or_truncation_fails_closed(self):
        warning = b'{"esearchresult":{"count":"0","retmax":"2","retstart":"0","idlist":[],"warninglist":{"phrasesignored":["42[UID]"]},"querytranslation":"42[UID] OR 43[UID]"}}'
        subjects, ordered, capture = ncbi_fixture(warning)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)
        truncated = b'{"esearchresult":{"count":"1","retmax":"0","retstart":"0","idlist":["42"],"querytranslation":"42[UID] OR 43[UID]"}}'
        subjects, ordered, capture = ncbi_fixture(truncated)
        with self.assertRaises(ValueError):
            adapters.probe_ncbi_gene_esearch(subjects[0], criterion(), ordered, capture)


if __name__ == "__main__":
    unittest.main()
```

Add adapter source/test paths and the adapter test step to the workflow in this same RED commit so hosted CI proves the missing module/API failure.

- [ ] **Step 2: Confirm RED**

Expected: adapter test import failure only; inherited tests remain unaffected.

- [ ] **Step 3: Extend only the source-specific adapter rule registries**

Add exactly:

```python
SUPPORTED_POSITIVE_RULES |= {"UNICODE_GENERAL_CATEGORY_NOT_CN_V1", "NCBI_ESEARCH_UID_PRESENT_V1"}
SUPPORTED_NEGATIVE_RULES |= {"UNICODE_GENERAL_CATEGORY_CN_V1", "NCBI_ESEARCH_UID_ABSENT_V1"}
SUPPORTED_AMBIGUOUS_RULES |= {"UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1", "NCBI_ESEARCH_NOT_ESTABLISHED_V1"}
```

Do not weaken generic fixture adapter verification.

- [ ] **Step 4: Implement Unicode source parser/replay**

Parse semantic non-comment lines as one hex point or inclusive range plus exactly one two-letter General_Category token. Reject malformed hex, reversed ranges, any overlapping explicit ranges, malformed tokens, wrong source contract/release, non-200 capture, or undecodable bytes. The fixture must explicitly establish the queried point. Build the inner immutable `RegistrySnapshotV1` with `match = category != "Cn"`, category, and source capture digest, then use the existing generic probe machinery. `verify_source_verified_probe` reparses the exact bytes and must reproduce the inner probe receipt.

- [ ] **Step 5: Implement deterministic NCBI UID batching/ESearch parser**

Sort unique integer subjects numerically; reject empty or more than 100 unique values. Canonical request identity binds `db=gene`, exact OR-composed `[UID]` term, `retmode=json`, and `retmax=k`, excluding credentials. On replay require response status 200, JSON object, mapping `esearchresult`, list of canonical decimal `idlist` values, no duplicate/unexpected UID, `count == len(idlist)`, frozen `retmax == k` and `retmax >= count`, exact request identity/digest set, and no non-empty warning/error state. Only then may absence of `x` mint `NO_MATCH`.

- [ ] **Step 6: Require GREEN**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py
python sovereign-omega-v2/python/tests/test_cross_domain_coverage.py
python sovereign-omega-v2/python/tests/test_cross_domain_fixture.py
```

- [ ] **Step 7: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_registry_adapters.py sovereign-omega-v2/python/cross_domain_coverage.py sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py .github/workflows/cross-domain-collision.yml
git commit -m "feat(research): add Unicode and NCBI offline adapters"
```

---

### Task 4: Bind source-authoritative probes into draw receipts and epoch summary

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_epoch.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_epoch.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_hardening.py`

**Interfaces:**
- Produces: `EpochDrawEvidenceV1`, `EpochDrawReceiptV1`, `ProspectiveEpochSummaryReceiptV1`, `evaluate_epoch_draw`, `summarize_epoch`, `verify_epoch_summary`.

- [ ] **Step 1: Add RED integration tests**

Add a test helper that uses Task 3 source-backed fixture probes and verifies these exact cases:

```python
def test_incomplete_draw_stays_in_summary_denominator(self):
    e = epoch.make_epoch_v1(seed=1234, subject_count=3)
    generation = epoch.generate_subject_receipts(e)
    complete = make_source_backed_draw(e, generation[0], unicode_match=True, ncbi_match=True)
    summary = epoch.summarize_epoch(e, generation, {0: complete})
    self.assertEqual(summary.generated_count, 3)
    self.assertEqual(summary.fully_covered_count, 1)
    self.assertEqual(summary.incomplete_count, 2)
    self.assertEqual(sum(summary.score_histogram), 1)
    self.assertFalse(summary.epoch_complete)


def test_duplicate_draw_positions_do_not_collapse_denominator(self):
    e = epoch.make_epoch_v1(seed=27, subject_count=64)
    generation = epoch.generate_subject_receipts(e)
    self.assertEqual(generation[40].value, generation[62].value)
    summary = epoch.summarize_epoch(e, generation, {})
    self.assertEqual(summary.generated_count, 64)
    self.assertEqual(summary.incomplete_count, 64)
    self.assertNotEqual(generation[40].receipt_sha256, generation[62].receipt_sha256)


def test_summary_rejects_cross_epoch_draw_splice(self):
    a = epoch.make_epoch_v1(seed=1234, subject_count=3)
    b = epoch.make_epoch_v1(seed=1235, subject_count=3)
    ga = epoch.generate_subject_receipts(a)
    gb = epoch.generate_subject_receipts(b)
    draw_a = make_source_backed_draw(a, ga[0], unicode_match=True, ncbi_match=True)
    with self.assertRaises(ValueError):
        epoch.summarize_epoch(b, gb, {0: draw_a})
```

Add one hardening test constructing a generic `cov.probe_registry_snapshot` bool-backed probe and asserting `evaluate_epoch_draw` raises `TypeError`: only Task 3 `SourceVerifiedProbeV1` can enter epoch authority.

- [ ] **Step 2: Confirm RED only on new draw/summary APIs**

- [ ] **Step 3: Implement epoch draw receipt**

Verify exact generation receipt, require exactly two source-verified probe bundles, replay both source bundles, require generated subject and criterion equality, require source/adapter contract digests equal epoch-frozen values by registry order, then pass only verified inner probes to existing `cov.evaluate_control_from_probes`. Bind generation, source probe, coverage, and collision digests into the draw receipt. No caller score/coverage/collision boolean exists.

- [ ] **Step 4: Implement incomplete-aware summary**

Reverify all generation receipts and exact draw-index mapping. Build positional tuples of length `subject_count` with `None` for incomplete draw/coverage/collision entries. Score histogram is exactly `(score0_count, score1_count, score2_count)` and registry match histogram exactly `(unicode_match_count, ncbi_match_count)`. Derive `epoch_complete = fully_covered_count == generated_count == subject_count`.

- [ ] **Step 5: Implement summary verifier**

Recompute hash and reject histogram inconsistencies, collision indices whose draw score is not 2, collision subject misalignment, cross-epoch digest lineage, or `epoch_complete=True` with any incomplete positional evidence.

- [ ] **Step 6: Require full cross-domain GREEN**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
python sovereign-omega-v2/python/tests/test_cross_domain_coverage.py
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py
python sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
python sovereign-omega-v2/python/tests/test_cross_domain_fixture.py
python sovereign-omega-v2/python/tests/test_cross_domain_hardening.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

- [ ] **Step 7: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_epoch.py sovereign-omega-v2/python/tests/test_cross_domain_epoch.py sovereign-omega-v2/python/tests/test_cross_domain_hardening.py
git commit -m "feat(research): bind prospective epoch evidence and summary"
```

---

### Task 5: Documentation, stacked DRAFT PR, and exact-head admission evidence

**Files:**
- Modify: `.github/workflows/cross-domain-collision.yml`
- Create: `docs/research/prospective-epoch-v1.md`

- [ ] **Step 1: Finalize offline workflow compile list**

Compile `research_invariants.py`, `cross_domain_collision.py`, `cross_domain_coverage.py`, `cross_domain_ingest.py`, `cross_domain_registry_adapters.py`, and `cross_domain_epoch.py`. Workflow must contain no live Unicode/NCBI call, curl/wget, or secret use.

- [ ] **Step 2: Write evidence-bound research status doc**

State implemented offline authority semantics, exact Unicode/NCBI source contracts, operational 1000-draw live run `NOT_ESTABLISHED` until complete artifact manifest exists, collision-rate significance `NOT_ESTABLISHED`, external human seed-shopping not disproven, 65010 retrospective boundary, and no structural/causal claim.

- [ ] **Step 3: Open stacked DRAFT PR**

Base `research/cross-domain-collision-v1`; head `research/prospective-epoch-v1`; title `feat(research): prospective Unicode + NCBI epoch v1`. Body explicitly states no merge, deployment, or live 1000-draw execution is authorized by the PR.

- [ ] **Step 4: Obtain exact-head terminal checks**

Require on the exact final branch SHA:

```text
AEGIS Cross-Domain Collision V1 = SUCCESS
AEGIS Zero-Discretion Type Gates = SUCCESS
Kernel One = SUCCESS
```

If repository cognition advances the branch, do not cite the green parent. Wait for fixed point and use the established content-empty commit technique to trigger checks on the exact final tree.

- [ ] **Step 5: Verification-before-completion review**

Fresh-resolve PR head, test counts, workflow conclusions, and bot-generated tree changes. Report only machine-established authority semantics. Real Epoch 1 execution/collision rate/significance remain `NOT_ESTABLISHED` until live artifacts are actually captured and 1000/1000 coverage verifies.
