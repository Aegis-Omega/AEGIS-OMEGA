# UCI-8 Evaluation Campaign v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, preregistered campaign contract that turns UCI-7 into a reproducible real-benchmark evidence pipeline without converting benchmark scores into AGI or authority claims.

**Architecture:** Add a standard-library Python reference contract beside `harness/sdk/agi_evidence.py`, closed JSON schemas, preregistered falsifiers, and an exact-head hosted workflow stacked on #279. UCI-8 consumes UCI-7 result roots; it does not replace UCI-7 scoring and does not execute external benchmarks in this slice.

**Tech Stack:** Python 3.12, dataclasses/enums, existing `canonical_hash`, pytest 8.3.5, JSON Schema Draft 2020-12, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-20-uci-8-evaluation-campaign-v1-design.md`

## Global Constraints

- Exact parent is `#279@1aa405975e2b3f3c1b1c0022a6b75e0b21d395ec`.
- Provider/model/benchmark outputs remain evidence only.
- No `AGI_PROVEN` status may exist.
- UCI-8 v1 statistical mode is exactly `PAIRED_DESCRIPTIVE_V1`.
- Public development data never satisfies held-out evidence.
- `SUSPECTED` or `EXPOSED` contamination blocks held-out completion.
- System and strongest-constituent baseline use the same preregistered task/trial manifest, scorer, and budget policy.
- No external benchmark execution is claimed by this slice.

---

### Task 1: Preregister campaign falsifiers

**Files:**
- Create: `sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign.py`
- Create: `sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign_schemas.py`

**Interfaces:**
- Consumes: UCI-7 `ContaminationClass`, `CapabilityTrialResultV1`, canonical hashing conventions.
- Produces: required API names `BenchmarkFamily`, `SplitPrivacy`, `MetricKind`, `StatisticalMode`, `CampaignEvidenceStatus`, `BenchmarkTrackSpecV1`, `EvaluationCampaignManifestV1`, `PairedBenchmarkTrialV1`, `CampaignEvidenceBundleV1`, `EvaluationCampaignError`.

- [ ] **Step 1: Write failing behavioral tests** for root binding, public-vs-held-out semantics, suspected/exposed contamination, fixed `PAIRED_DESCRIPTIVE_V1`, ARC metric constraints, GAIA private-answer boundary, METR human-reference semantics, missing baseline, runtime/scorer/budget mismatch, and exact paired cardinality.
- [ ] **Step 2: Run** `python -m pytest sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign.py -q`.
  **Expected:** collection/import RED because `harness.sdk.evaluation_campaign` does not exist.
- [ ] **Step 3: Write failing schema tests** requiring four closed schemas with nominal `const` discriminators.
- [ ] **Step 4: Run** `python -m pytest sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign_schemas.py -q`.
  **Expected:** RED because UCI-8 schemas do not exist.
- [ ] **Step 5: Commit** only tests.

### Task 2: Implement campaign manifest reference contract

**Files:**
- Create: `harness/sdk/evaluation_campaign.py`
- Test: `sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign.py`

**Interfaces:**
- `BenchmarkTrackSpecV1(...).root -> str`
- `EvaluationCampaignManifestV1.create(...).root -> str`
- `PairedBenchmarkTrialV1.create(...) -> PairedBenchmarkTrialV1`
- `CampaignEvidenceBundleV1.create(...) -> CampaignEvidenceBundleV1`

- [ ] **Step 1:** Implement enums and strict validation for benchmark family, split privacy, metric kind, statistical mode, and evidence status.
- [ ] **Step 2:** Implement `BenchmarkTrackSpecV1` with all preregistered commitments in its domain-separated root.
- [ ] **Step 3:** Implement family-specific invariants: ARC exact-match + budget, GAIA tool-QA + private/gated answer handling, METR human-equivalent horizon + nonzero human reference.
- [ ] **Step 4:** Implement campaign manifest with immutable ordered track roots and exact system/baseline commitments.
- [ ] **Step 5:** Run behavioral tests and verify GREEN.
- [ ] **Step 6:** Commit implementation.

### Task 3: Implement paired evidence and anti-splicing

**Files:**
- Modify: `harness/sdk/evaluation_campaign.py`
- Test: `sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign.py`

**Interfaces:**
- Pairing consumes UCI-7 result roots plus explicit task/trial/scorer/budget/runtime commitments.
- Bundle consumes only pair roots and executable/environment/receipt commitments.

- [ ] **Step 1:** Preregister any missing anti-splicing tests before implementation.
- [ ] **Step 2:** Run tests and confirm targeted RED only.
- [ ] **Step 3:** Implement exact campaign/track/task/trial membership, system runtime, baseline runtime, scorer, and budget binding.
- [ ] **Step 4:** Implement evidence status so public/suspected/exposed data cannot become `HELD_OUT_EVIDENCE_COMPLETE` and absent baseline cannot become `COLLECTIVE_CONTRIBUTION_EVALUABLE`.
- [ ] **Step 5:** Run all UCI-8 behavioral tests and verify GREEN.
- [ ] **Step 6:** Commit.

### Task 4: Close serialization boundary

**Files:**
- Create: `schemas/benchmark-track-spec.v1.schema.json`
- Create: `schemas/evaluation-campaign-manifest.v1.schema.json`
- Create: `schemas/paired-benchmark-trial.v1.schema.json`
- Create: `schemas/campaign-evidence-bundle.v1.schema.json`
- Test: `sovereign-omega-v2/python/tests/test_uci8_evaluation_campaign_schemas.py`

**Interfaces:**
- Each serialized type has an obligatory nominal kind discriminator with JSON Schema `const`.
- Every schema has `additionalProperties: false`.

- [ ] **Step 1:** Add minimal closed Draft 2020-12 schemas matching Python serialization exactly.
- [ ] **Step 2:** Run schema tests and verify GREEN.
- [ ] **Step 3:** Commit.

### Task 5: Exact-head hosted proofline

**Files:**
- Create: `.github/workflows/uci-8-evaluation-campaign.yml`
- Create: `sovereign-omega-v2/python/tests/test_uci8_ci_contract.py`

**Interfaces:**
- Workflow base/parent: `feat/uci-7-agi-evidence-protocol-v1@1aa405975e2b3f3c1b1c0022a6b75e0b21d395ec`.
- Workflow emits exact-head witness artifact; `PUBLIC_BENCHMARK_CAMPAIGN=NOT_RUN` remains explicit.

- [ ] **Step 1:** Preregister CI guards requiring exact parent/base, trigger scope, literal UCI-8 test cardinalities, and inherited UCI-7 proofline invocation.
- [ ] **Step 2:** Run CI guards and observe RED before workflow exists.
- [ ] **Step 3:** Implement workflow that validates UCI-8 schemas/tests and reruns inherited UCI-7 + critical UCI-4/5/6 checks.
- [ ] **Step 4:** Run hosted exact-head workflow.
- [ ] **Step 5:** Read raw job output and artifact digest; do not infer success from UI state alone.
- [ ] **Step 6:** Commit/publish exact-head evidence in PR body.

### Task 6: Adversarial review and promotion gate

**Files:**
- Review all UCI-8 changed files; add regression tests before fixes.

- [ ] **Step 1:** Attempt score fabrication, benchmark-family reinterpretation, public-to-private promotion, baseline splicing, task/trial swapping, runtime swapping, scorer swapping, budget swapping, contamination downgrading, and unsupported inferential labels.
- [ ] **Step 2:** For each discovered gap, add RED falsifier first, then minimal fix, then exact-head GREEN.
- [ ] **Step 3:** Re-run UCI-8 hosted workflow plus Kernel One, Coordinator Authority, and Coq sibling gates at the final head.
- [ ] **Step 4:** Only after fresh evidence, mark the UCI-8 PR READY FOR REVIEW; do not merge without operator authority.
