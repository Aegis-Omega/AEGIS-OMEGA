# UCI-8 Evaluation Campaign v1 — Design

## Status

PREREGISTERED DESIGN. This document is evidence-program architecture, not evidence that AEGIS is AGI or that any benchmark has been run.

Exact parent: `#279@1aa405975e2b3f3c1b1c0022a6b75e0b21d395ec`.

## Goal

Turn UCI-7's evaluator contract into a reproducible real-evaluation campaign boundary. UCI-8 binds benchmark identity, dataset/split provenance, scorer identity, budgets, runtime identity, paired strongest-constituent baselines, repetition cardinality, contamination state, and raw evidence roots before any benchmark result can be interpreted.

UCI-8 does not create an `AGI_PROVEN` status. It does not convert a benchmark score into authority, state admission, or an AGI claim.

## External calibration

The initial campaign surface is designed to accommodate three distinct measurement families without pretending they are interchangeable:

1. **ARC-AGI-2-like abstraction/transfer** — exact task scoring, held-out/private evaluation, and explicit efficiency constraints.
2. **GAIA-like general assistant/tool use** — real-world questions, tool use, private/gated answers, and contamination-sensitive evaluation.
3. **METR-like long-horizon capability** — task difficulty grounded in human expert completion time; the human-equivalent task horizon is not the elapsed wall-clock duration of an agent run.

These families provide evidence for different UCI-7 axes. No single benchmark may satisfy all six axes by declaration.

## Epistemic boundary

The campaign pipeline is:

`CampaignManifest -> BenchmarkTrackSpec[] -> exact task/trial manifest -> system run + strongest-constituent run -> deterministic scorer -> paired trial evidence -> campaign evidence bundle -> UCI-7 assessment`

At every stage:

- provider/model output is evidence only;
- benchmark score is evidence only;
- public development data cannot masquerade as held-out evidence;
- contamination is a hard evidence-quality boundary, not a score adjustment;
- system and baseline comparisons use the same preregistered task/trial manifest and budget policy;
- v1 paired deltas are descriptive only;
- no confidence interval, p-value, significance claim, or causal attribution is emitted by v1;
- benchmark execution must never authorize world effects.

## Contract types

### `BenchmarkTrackSpecV1`

Required fields:

- `track_id`
- `benchmark_family`: `ARC_AGI_2`, `GAIA`, `METR_TIME_HORIZON`, or `OTHER_PREREGISTERED`
- `benchmark_version`
- `benchmark_source_commitment`
- `split_id`
- `split_privacy`: `PUBLIC_DEV`, `SEMI_PRIVATE`, `PRIVATE`, `GATED_PRIVATE`
- `metric_kind`: `EXACT_MATCH_ACCURACY`, `TOOL_ASSISTED_QA_ACCURACY`, `HUMAN_EQUIVALENT_TASK_HORIZON`, `OTHER_DETERMINISTIC`
- `task_manifest_commitment`
- `scorer_commitment`
- `budget_commitment`
- `human_reference_commitment`
- `contamination_class`: reuse UCI-7 values `HELD_OUT`, `PUBLIC`, `SUSPECTED`, `EXPOSED`
- `repetition_count >= 1`
- `statistical_mode = PAIRED_DESCRIPTIVE_V1`

The root must change if any of these fields change.

### `EvaluationCampaignManifestV1`

Required fields:

- `campaign_id`
- `uci7_suite_root`
- `evaluated_system_commitment`
- `strongest_constituent_baseline_commitment`
- one or more `BenchmarkTrackSpecV1`
- `campaign_policy_commitment`
- `campaign_kind = EVALUATION_CAMPAIGN_MANIFEST_V1`

The manifest is immutable after results exist. Rebinding a track or threshold requires a new campaign root.

### `PairedBenchmarkTrialV1`

Binds one preregistered unit of comparison:

- campaign root
- track root
- task commitment
- trial index
- system `CapabilityTrialResultV1` root
- baseline `CapabilityTrialResultV1` root
- system runtime commitment
- baseline runtime commitment
- budget commitment
- scorer commitment

System and baseline must refer to the same task/trial unit and the exact preregistered budget/scorer policy.

### `CampaignEvidenceBundleV1`

Contains only evidence references:

- campaign root
- ordered paired-trial roots
- benchmark adapter executable commitment
- runner environment commitment
- execution receipt bundle commitment
- effect/admission roots when the evaluated task itself legitimately exercises the UCI effect/admission path
- contamination summary
- evidence status

The bundle is not an `AdmissionRecord`, not an `EffectReceipt`, and not authority.

## Fail-closed invariants

1. `PUBLIC_DEV` or UCI-7 `PUBLIC` data cannot satisfy a held-out promotion claim.
2. `SUSPECTED` or `EXPOSED` contamination blocks `HELD_OUT_EVIDENCE_COMPLETE`.
3. Missing baseline evidence blocks `COLLECTIVE_CONTRIBUTION_EVALUABLE`.
4. System and baseline result cardinality must equal the preregistered task/trial cardinality.
5. Runtime identity mismatch fails closed.
6. Scorer commitment mismatch fails closed.
7. Budget commitment mismatch fails closed.
8. `statistical_mode` is fixed to `PAIRED_DESCRIPTIVE_V1`; inferential labels such as `SIGNIFICANT_IMPROVEMENT` are invalid in v1.
9. A benchmark family cannot silently redefine its metric semantics after preregistration.
10. `AGI_PROVEN` is not a valid campaign status.

## Benchmark-specific minimum semantics

### ARC-AGI-2

- metric kind must be `EXACT_MATCH_ACCURACY`;
- efficiency/budget commitment is mandatory;
- private/semi-private evidence may be held-out; public development data is not held-out evidence.

### GAIA

- metric kind must be `TOOL_ASSISTED_QA_ACCURACY`;
- scorer commitment must bind private/gated answer handling;
- gated/private answer material must not be copied into public evidence artifacts.

### METR-style time horizon

- metric kind must be `HUMAN_EQUIVALENT_TASK_HORIZON`;
- `human_reference_commitment` is mandatory and nonzero;
- the metric is explicitly human-equivalent task difficulty, not agent elapsed runtime.

## Statistical policy v1

UCI-8 v1 deliberately avoids inferential statistics. A paired mean delta can be reported only as a deterministic descriptive statistic. Real uncertainty claims require a future preregistered protocol with enough independent/repeated evaluation units, a fixed resampling/modeling procedure, and multiplicity handling where applicable.

This prevents unit fixtures or tiny benchmark samples from acquiring false statistical authority.

## Completion evidence

UCI-8 v1 is implementation-established only when:

- RED falsifiers are observed on the exact stacked branch before production implementation;
- closed schemas validate;
- all UCI-8 contract tests pass at exact head;
- inherited UCI-4/5/6/7 proofline remains green;
- hosted CI emits a content-addressed witness artifact;
- the witness states `PUBLIC_BENCHMARK_CAMPAIGN = NOT_RUN` until real external evaluation occurs.
