# Prospective Epoch V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a preregistered, deterministic 1000-draw integer epoch whose only scored external domains are Unicode 17.0.0 General_Category and NCBI Gene UID existence, with live bytes captured non-authoritatively and all classification replayed offline.

**Architecture:** Add an epoch/generation layer above the existing Cross-Domain Collision + ControlCoverage spine. Add a generic raw-byte capture receipt to `cross_domain_ingest.py`, source-specific offline adapters in a new module, and epoch-level draw/summary receipts that only accept source-replayable probe evidence. Existing `65010` fixture behavior remains untouched and retrospective.

**Tech Stack:** Python 3.11+ stdlib only (`dataclasses`, `enum`, `hashlib` through existing `research_invariants`, `json`, `random`, `urllib.parse`), `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-25-prospective-epoch-v1-design.md`

## Global Constraints

- Exact scored registries: `("unicode", "ncbi-gene")`.
- Integer universe: `[0, 100000]`.
- First operational `subject_count`: `1000`.
- Generator: `PY_RANDOM_UNIFORM_INT_V1`, positional draws with replacement.
- Epoch 1 promotion threshold is `None`; no `NULL_SURVIVED` is minted by the epoch summary.
- Unicode source: exact versioned Unicode 17.0.0 `DerivedGeneralCategory.txt` contract.
- NCBI source: Entrez Gene ESearch exact `[UID]` query contract, max 100 unique UIDs per deterministic batch.
- Live I/O is evidence acquisition only; authoritative CI performs no network calls.
- `NOT_ESTABLISHED` never becomes `NO_MATCH`.
- Incomplete draws stay in the generated denominator and prevent `COMPLETE` epoch status.
- No special-case behavior for integer `65010`.
- No new third scored domain.

---

### Task 1: Freeze epoch and prove positional generation lineage

**Files:**
- Create: `sovereign-omega-v2/python/cross_domain_epoch.py`
- Create: `sovereign-omega-v2/python/tests/test_cross_domain_epoch.py`

**Interfaces:**
- Consumes: `cross_domain_collision.IntegerSubjectV1`, `CollisionCriterionV1`, `generate_controls`; `research_invariants.sha256_hex`, `_check_digest`.
- Produces:
  - `ProspectiveEpochV1`
  - `SubjectGenerationReceiptV1`
  - `make_epoch_v1(*, seed: int, subject_count: int = 1000) -> ProspectiveEpochV1`
  - `epoch_collision_criterion(epoch: ProspectiveEpochV1) -> CollisionCriterionV1`
  - `generate_subject_receipts(epoch: ProspectiveEpochV1) -> tuple[SubjectGenerationReceiptV1, ...]`
  - `verify_subject_generation_receipt(epoch, receipt) -> None`

- [ ] **Step 1: Write failing epoch/generation tests**

Create `test_cross_domain_epoch.py` with these load-bearing cases:

```python
import pathlib, sys, unittest
from dataclasses import replace

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_DIR))

import cross_domain_epoch as epoch


class ProspectiveEpochTests(unittest.TestCase):
    def test_epoch_is_exactly_unicode_plus_ncbi(self):
        e = epoch.make_epoch_v1(seed=123456789, subject_count=8)
        self.assertEqual(e.registry_ids, ("unicode", "ncbi-gene"))
        self.assertEqual(e.universe_min, 0)
        self.assertEqual(e.universe_max, 100000)
        self.assertIsNone(e.promotion_threshold)

    def test_epoch_digest_changes_when_seed_changes(self):
        a = epoch.make_epoch_v1(seed=1, subject_count=8)
        b = epoch.make_epoch_v1(seed=2, subject_count=8)
        self.assertNotEqual(a.epoch_sha256, b.epoch_sha256)

    def test_generation_replays_identically(self):
        e = epoch.make_epoch_v1(seed=1234, subject_count=16)
        a = epoch.generate_subject_receipts(e)
        b = epoch.generate_subject_receipts(e)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 16)
        self.assertEqual({r.generated_sequence_sha256 for r in a}, {a[0].generated_sequence_sha256})

    def test_generation_receipt_wrong_index_fails(self):
        e = epoch.make_epoch_v1(seed=1234, subject_count=16)
        r = epoch.generate_subject_receipts(e)[0]
        with self.assertRaises(ValueError):
            epoch.verify_subject_generation_receipt(e, replace(r, draw_index=1))

    def test_generation_receipt_cross_epoch_splice_fails(self):
        a = epoch.make_epoch_v1(seed=1234, subject_count=16)
        b = epoch.make_epoch_v1(seed=1235, subject_count=16)
        r = epoch.generate_subject_receipts(a)[0]
        with self.assertRaises(ValueError):
            epoch.verify_subject_generation_receipt(b, r)
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
```

Expected: `ModuleNotFoundError: No module named 'cross_domain_epoch'`.

- [ ] **Step 3: Implement minimal epoch types and deterministic generation**

In `cross_domain_epoch.py`, define frozen dataclasses and canonical material helpers. `make_epoch_v1` must reject any non-positive `subject_count`, boolean-as-int seed/count, and must hard-code the V1 registry/score/generator/coverage semantics rather than accepting caller overrides.

`epoch_collision_criterion` must return:

```python
cdc.CollisionCriterionV1(
    universe_min=epoch.universe_min,
    universe_max=epoch.universe_max,
    registry_set=epoch.registry_ids,
    transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",),
    independence_rule_id="UNIQUE_DOMAIN_ID_V1",
    score_function_id="UNIQUE_EXTERNAL_DOMAINS_V1",
    control_generator_id="PY_RANDOM_UNIFORM_INT_V1",
    control_seed=epoch.seed,
    control_count=epoch.subject_count,
    promotion_threshold=None,
    criterion_text=f"prospective-epoch-v1:{epoch.epoch_id}",
)
```

`generate_subject_receipts` must call the existing `cdc.generate_controls(criterion)`, hash the full ordered integer tuple once, and issue one receipt per index. Verification regenerates the sequence and checks all fields plus receipt hash.

- [ ] **Step 4: Run task tests and inherited collision tests**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
python sovereign-omega-v2/python/tests/test_cross_domain_collision.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_epoch.py sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
git commit -m "feat(research): add prospective epoch generation lineage"
```

---

### Task 2: Add immutable raw-byte source capture receipts

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_ingest.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_ingest.py`

**Interfaces:**
- Produces:
  - `SourceCaptureReceiptV1`
  - `VerifiedSourceCaptureV1`
  - `capture_source_bytes(...) -> VerifiedSourceCaptureV1`
  - `verify_source_capture(bundle: VerifiedSourceCaptureV1) -> None`

`SourceCaptureReceiptV1` fields exactly:

```text
source_id
source_contract_sha256
request_identity
request_subject_sha256s
source_version_or_release
response_status
media_type
raw_content_sha256
raw_content_length
observed_at
producer_id
attempt_index
previous_attempt_sha256 | None
receipt_sha256
```

- [ ] **Step 1: Add failing capture tests**

Append to `test_cross_domain_ingest.py`:

```python
from dataclasses import replace
import research_invariants as ri

class SourceCaptureReceiptTests(unittest.TestCase):
    def test_raw_byte_tampering_breaks_capture_replay(self):
        bundle = ingest.capture_source_bytes(
            source_id="unicode-ucd",
            source_contract_sha256="a" * 64,
            request_identity="unicode://17.0.0/DerivedGeneralCategory.txt",
            request_subject_sha256s=(),
            source_version_or_release="17.0.0",
            response_status=200,
            media_type="text/plain",
            raw_content=b"0041 ; Lu\n0378 ; Cn\n",
            observed_at="2026-08-25T00:00:00Z",
            producer_id="test",
            attempt_index=0,
        )
        ingest.verify_source_capture(bundle)
        with self.assertRaises(ValueError):
            ingest.verify_source_capture(replace(bundle, raw_content=b"tampered"))

    def test_retry_must_bind_previous_attempt(self):
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
            media_type="application/json", raw_content=b'{"esearchresult":{"count":"0","retmax":"1","idlist":[]}}',
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

- [ ] **Step 2: Run ingest tests and confirm RED only on new APIs**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
```

Expected: existing 4 tests PASS; new tests ERROR because `capture_source_bytes` does not exist.

- [ ] **Step 3: Implement capture receipt/bundle without changing old JSON snapshot API**

Add canonical receipt hashing. Hash bytes with `hashlib.sha256(raw_content).hexdigest()` or a dedicated exact-byte helper; do not feed bytes into JSON canonicalization. `attempt_index == 0` requires `previous_attempt_sha256 is None`; `attempt_index > 0` requires a valid previous digest. Require non-empty source ids/contracts/request identity/version/media type/observed_at/producer id, integer HTTP status, non-negative content length, tuple-copied subject digest sequence, and immutable `bytes(raw_content)` in the bundle.

- [ ] **Step 4: Run ingest + hardening tests**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_ingest.py
python sovereign-omega-v2/python/tests/test_cross_domain_hardening.py
```

Expected: PASS.

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

**Interfaces:**
- Produces:
  - `UnicodeSourceContractV1`
  - `NCBIGeneSourceContractV1`
  - `SourceVerifiedProbeV1`
  - `unicode_source_contract_v1()`
  - `ncbi_gene_source_contract_v1()`
  - `unicode_adapter_contract_v1()`
  - `ncbi_gene_adapter_contract_v1()`
  - `make_ncbi_batch_request(subjects) -> tuple[str, tuple[IntegerSubjectV1, ...]]`
  - `probe_unicode_general_category(subject, criterion, capture) -> SourceVerifiedProbeV1`
  - `probe_ncbi_gene_esearch(subject, criterion, request_subjects, capture) -> SourceVerifiedProbeV1`
  - `verify_source_verified_probe(bundle) -> None`

- [ ] **Step 1: Add failing source-adapter tests**

Create fixtures entirely as local bytes. Required tests include:

```python
UNICODE_FIXTURE = b"""# DerivedGeneralCategory-17.0.0.txt\n0000..007F ; Cc\n0041 ; Lu\n0378..0379 ; Cn\n"""

NCBI_MATCH = b'{"header":{"type":"esearch","version":"0.3"},"esearchresult":{"count":"1","retmax":"2","retstart":"0","idlist":["42"],"translationset":[],"querytranslation":"42[UID] OR 43[UID]"}}'

class RegistryAdapterTests(unittest.TestCase):
    def test_unicode_non_cn_is_match_and_cn_is_no_match(self):
        # use a fixture whose effective ranges are non-overlapping; 0x41 -> Lu, 0x378 -> Cn
        ...

    def test_unicode_overlap_fails_closed(self):
        bad = b"0040..0042 ; Lu\n0041 ; Cn\n"
        ...

    def test_ncbi_uid_presence_and_absence_are_distinct(self):
        # exact batch {42, 43}; idlist contains only 42
        # 42 => MATCH, 43 => NO_MATCH
        ...

    def test_ncbi_unexpected_uid_fails_closed(self):
        bad = b'{"esearchresult":{"count":"1","retmax":"2","retstart":"0","idlist":["999"],"querytranslation":"42[UID] OR 43[UID]"}}'
        ...

    def test_ncbi_warning_or_truncation_is_not_negative(self):
        ...
```

The actual test file must construct a `CollisionCriterionV1` with `registry_set=("unicode", "ncbi-gene")`, `transform_set=("INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1",)`, use `ingest.capture_source_bytes(...)`, and assert `cov.RegistryProbeOutcomeV1` values.

- [ ] **Step 2: Run adapter tests and confirm RED**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py
```

Expected: `ModuleNotFoundError: No module named 'cross_domain_registry_adapters'`.

- [ ] **Step 3: Extend supported adapter rule ids**

In `cross_domain_coverage.py`, add only these rule ids to the existing supported sets:

```python
SUPPORTED_POSITIVE_RULES |= {
    "UNICODE_GENERAL_CATEGORY_NOT_CN_V1",
    "NCBI_ESEARCH_UID_PRESENT_V1",
}
SUPPORTED_NEGATIVE_RULES |= {
    "UNICODE_GENERAL_CATEGORY_CN_V1",
    "NCBI_ESEARCH_UID_ABSENT_V1",
}
SUPPORTED_AMBIGUOUS_RULES |= {
    "UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1",
    "NCBI_ESEARCH_NOT_ESTABLISHED_V1",
}
```

Do not weaken `probe_registry_snapshot` or existing fixture contracts.

- [ ] **Step 4: Implement Unicode parser and source-verified probe replay**

Parse each non-comment line by stripping `#...`, then splitting the semantic part on `;`. Accept exactly one hex code point or inclusive `start..end` range and a two-letter General_Category token. Reject invalid hex, reversed ranges, overlapping ranges with contradictory/equal assignments, and malformed lines.

For a queried subject, determine exactly one effective category. The committed fixture tests must explicitly cover the queried code points; production parser may use a contract-proven `Cn` default only when the UCD source header/contract version establishes that default. If effective category cannot be established, return/raise an unestablished verification result rather than minting `NO_MATCH`.

Construct an internal `RegistrySnapshotV1` whose `canonical_result` includes at least:

```python
{
    "match": category != "Cn",
    "general_category": category,
    "source_capture_receipt_sha256": capture.receipt.receipt_sha256,
}
```

Then call existing `cov.probe_registry_snapshot(...)`. Wrap it with source contract/capture in `SourceVerifiedProbeV1`. Verification reparses exact bytes and must reproduce the inner generic probe receipt exactly.

- [ ] **Step 5: Implement deterministic NCBI UID batches and ESearch parser**

`make_ncbi_batch_request` sorts unique integer subjects numerically, rejects empty or >100 unique subjects, and returns canonical request identity plus ordered unique subjects. Request identity must deterministically encode `db=gene`, each `x[UID]` OR term, `retmode=json`, and `retmax=k`; credentials/email/api-key are not included.

Parser requirements:

- HTTP status must be 200;
- valid UTF-8 JSON object;
- `esearchresult` must be a mapping;
- `idlist` must be a list of canonical decimal strings;
- every returned UID must be in requested set;
- no duplicate returned UID;
- `count` must parse to integer equal to `len(idlist)` for this exact UID-only query;
- `retmax` must parse to integer >= `count` and equal frozen request retmax;
- `errorlist` or `warninglist` with non-empty semantic content fails closed;
- capture request identity and subject digest set must exactly match the recomputed batch.

For subject `x`, match is `str(x) in idlist`; absence is exact `NO_MATCH` only after all checks above pass.

- [ ] **Step 6: Run adapter, coverage, and fixture tests**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py
python sovereign-omega-v2/python/tests/test_cross_domain_coverage.py
python sovereign-omega-v2/python/tests/test_cross_domain_fixture.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_registry_adapters.py sovereign-omega-v2/python/cross_domain_coverage.py sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py
git commit -m "feat(research): add Unicode and NCBI offline adapters"
```

---

### Task 4: Bind source-authoritative probes into draw receipts and epoch summary

**Files:**
- Modify: `sovereign-omega-v2/python/cross_domain_epoch.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_epoch.py`
- Modify: `sovereign-omega-v2/python/tests/test_cross_domain_hardening.py`

**Interfaces:**
- Produces:
  - `EpochDrawEvidenceV1`
  - `EpochDrawReceiptV1`
  - `ProspectiveEpochSummaryReceiptV1`
  - `evaluate_epoch_draw(epoch, generation_receipt, source_probes) -> EpochDrawEvidenceV1`
  - `summarize_epoch(epoch, generation_receipts, draw_evidence_by_index) -> ProspectiveEpochSummaryReceiptV1`
  - `verify_epoch_summary(...) -> None`

- [ ] **Step 1: Add failing integration tests**

Add tests that construct a small `subject_count=3` epoch and source-backed probes from Task 3 fixtures.

Required behavior:

```python
def test_complete_match_match_draw_scores_two():
    # both source-authoritative probes MATCH
    evidence = epoch.evaluate_epoch_draw(e, generation[0], [unicode_probe, ncbi_probe])
    self.assertTrue(evidence.coverage.receipt.coverage_complete)
    self.assertEqual(evidence.collision.score, 2)
    self.assertTrue(evidence.collision.cross_registry_collision)


def test_incomplete_draw_stays_in_summary_denominator():
    summary = epoch.summarize_epoch(e, generation, {0: complete_draw})
    self.assertEqual(summary.generated_count, 3)
    self.assertEqual(summary.fully_covered_count, 1)
    self.assertEqual(summary.incomplete_count, 2)
    self.assertEqual(sum(summary.score_histogram), 1)
    self.assertFalse(summary.epoch_complete)


def test_duplicate_draw_positions_do_not_collapse_denominator():
    # build an epoch/seed fixture known to generate a duplicate, or construct receipt validation around duplicate values
    # assert two positions remain two generation receipt digests even if subject_sha256 matches
    ...


def test_summary_cross_epoch_splice_fails():
    ...
```

Also add an adversarial test that a generic hash-valid `VerifiedRegistryProbeV1` produced from an arbitrary bool snapshot cannot satisfy `evaluate_epoch_draw`; only `SourceVerifiedProbeV1` accepted from Task 3 can enter epoch authority.

- [ ] **Step 2: Run epoch tests and confirm RED**

```bash
python sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
```

Expected: failures/errors only for the new draw/summary APIs.

- [ ] **Step 3: Implement epoch draw receipt**

`evaluate_epoch_draw` must:

1. verify generation receipt against exact epoch;
2. require exactly the two frozen source-specific probe bundle types;
3. call `adapters.verify_source_verified_probe` on both;
4. require probe subject digest equals generated subject;
5. require probe criterion digest equals `epoch_collision_criterion(epoch).criterion_sha256`;
6. require source/adapter contract digests equal the epoch-frozen digests by registry order;
7. pass only verified inner probes into `cov.evaluate_control_from_probes`;
8. re-evaluate/replay coverage and collision before minting `EpochDrawReceiptV1`;
9. bind generation + source probe + coverage + collision digests into the draw receipt.

No caller-supplied score, `coverage_complete`, or collision boolean is accepted.

- [ ] **Step 4: Implement incomplete-aware epoch summary**

`summarize_epoch` receives all generation receipts and a mapping from draw index to completed `EpochDrawEvidenceV1`.

It must reverify every generation receipt, reject missing/duplicate/wrong indices in the generation list, reject draw evidence not matching the receipt at its position, and construct positional digest tuples of length `subject_count` using `None` for incomplete draw coverage/collision/draw receipt entries.

Represent score histogram canonically as `(count_score_0, count_score_1, count_score_2)`. Represent registry match histogram as `(unicode_match_count, ncbi_gene_match_count)`.

`epoch_complete` is derived and true iff `fully_covered_count == generated_count == epoch.subject_count`.

- [ ] **Step 5: Add tamper/splice verification**

`verify_epoch_summary` recomputes summary material and invariants. It must reject:

- histogram totals inconsistent with fully covered count;
- collision index not score 2;
- collision subject vector misaligned with collision indices;
- cross-epoch generation/draw digest splicing;
- `epoch_complete=True` with any `None` positional evidence;
- changed summary digest.

- [ ] **Step 6: Run all cross-domain tests**

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

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add sovereign-omega-v2/python/cross_domain_epoch.py sovereign-omega-v2/python/tests/test_cross_domain_epoch.py sovereign-omega-v2/python/tests/test_cross_domain_hardening.py
git commit -m "feat(research): bind prospective epoch evidence and summary"
```

---

### Task 5: CI admission and exact-head evidence

**Files:**
- Modify: `.github/workflows/cross-domain-collision.yml`
- Create: `docs/research/prospective-epoch-v1.md`

**Interfaces:** none; this task makes the already-implemented authority path visible and executable in hosted CI.

- [ ] **Step 1: Extend offline workflow path triggers and compile list**

Add:

```yaml
- "sovereign-omega-v2/python/cross_domain_epoch.py"
- "sovereign-omega-v2/python/cross_domain_registry_adapters.py"
- "sovereign-omega-v2/python/tests/test_cross_domain_epoch.py"
- "sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py"
- "docs/research/prospective-epoch-v1.md"
```

Compile both new modules. Add two steps before frozen fixture replay:

```yaml
- name: Run registry adapter regressions
  run: python sovereign-omega-v2/python/tests/test_cross_domain_registry_adapters.py
- name: Run prospective epoch regressions
  run: python sovereign-omega-v2/python/tests/test_cross_domain_epoch.py
```

No network command, curl, wget, NCBI call, Unicode call, or secret is allowed in this workflow.

- [ ] **Step 2: Write evidence-bound research doc**

`docs/research/prospective-epoch-v1.md` must state:

- authority semantics implemented offline;
- exact scored registries Unicode 17.0.0 + NCBI Gene ESearch;
- operational live 1000-draw run not yet established until a complete artifact manifest exists;
- collision-rate significance remains `NOT_ESTABLISHED`;
- seed-shopping outside system lineage is not disproven;
- `65010` remains retrospective unless independently drawn by frozen generator;
- no structural/causal claim.

- [ ] **Step 3: Run/fetch exact-head CI and require terminal outcomes**

Authoritative required outcomes on the exact final branch SHA:

```text
AEGIS Cross-Domain Collision V1 = SUCCESS
AEGIS Zero-Discretion Type Gates = SUCCESS
Kernel One = SUCCESS
```

Repository cognition/bot commits must not be treated as equivalent to the green parent. If cognition advances the branch, obtain terminal checks on the new exact head using the existing fixed-point/empty-commit technique rather than citing an ancestor.

- [ ] **Step 4: Open a stacked DRAFT PR**

Base: `research/cross-domain-collision-v1`  
Head: `research/prospective-epoch-v1`  
Title: `feat(research): prospective Unicode + NCBI epoch v1`

PR body must explicitly state no merge/deployment/live 1000-draw execution is authorized by the PR itself.

- [ ] **Step 5: Final verification-before-completion review**

Fresh-resolve PR head and workflow conclusions after all bots settle. Report exact SHA, test counts, failures/skips, and explicit `NOT_ESTABLISHED` boundaries. Do not claim a real prospective empirical result before live artifacts exist.
