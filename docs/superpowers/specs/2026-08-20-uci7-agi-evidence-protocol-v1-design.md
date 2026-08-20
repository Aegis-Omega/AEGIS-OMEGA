# UCI-7 — AGI Evidence Protocol v1

Date: 2026-08-20
Parent: `#278@156062855a91b77133d8999ce34883432435b167`
Status: PREREGISTERED DESIGN / NO AGI CLAIM

## Purpose

UCI-7 turns `AGI = NOT_ESTABLISHED` into a falsifiable evaluation program. It does **not** define a magic scalar whose passage proves AGI. It defines a preregistered, multi-axis evidence contract whose outputs can strengthen, weaken, or reject an AGI hypothesis while preserving AEGIS authority/evidence separation.

## External calibration anchors

The protocol is aligned to public evaluation ideas rather than invented only for AEGIS:

- ARC-AGI-2: novel abstraction/reasoning on private evaluation tasks and explicit efficiency constraints.
- GAIA: general-assistant tasks requiring reasoning, multimodality, browsing and tool use.
- METR task-completion time horizon: reliability as a function of human-equivalent task difficulty/duration.

These are reference anchors, not imported claims that AEGIS has passed them.

## Required evidence axes

Every admitted evaluation suite MUST contain all required axes. No weighted average may compensate for a missing or failed required axis.

1. `NOVEL_ABSTRACTION_TRANSFER` — solve held-out tasks whose rule is not supplied directly.
2. `CROSS_DOMAIN_GENERALITY` — competence across preregistered unrelated domains.
3. `TOOL_AND_ENVIRONMENT_AGENCY` — multi-step tool/environment work with deterministic end-state checking.
4. `LONG_HORIZON_RELIABILITY` — task difficulty/horizon measured against a human reference, with repeated trials.
5. `SAFE_ADAPTATION` — use admitted memory/feedback to improve later performance without violating UCI-4/UCI-5/UCI-6 invariants.
6. `METACOGNITIVE_CALIBRATION` — predicted correctness vs actual correctness, inheriting the historical Hallucination Delta idea without treating historical Kaggle outputs as current proof.

## Anti-gaming / contamination contract

A suite is invalid for AGI evidence unless all of the following are preregistered before execution:

- immutable suite identifier and manifest digest;
- task IDs, axis membership, scoring/checker identities, budgets and trial counts;
- hidden-case or answer commitments whose plaintext answers are unavailable to the evaluated agent;
- fixed thresholds and minimum task counts;
- provider/model/runtime/configuration identity;
- strongest constituent baseline protocol under the same task and budget manifest;
- deterministic checker outputs; self-reported or LLM-judge-only correctness is forbidden;
- explicit contamination declaration per task family;
- no threshold, task-weight or exclusion change after result observation.

## Evidence objects

### `CapabilityTaskSpecV1`

Binds one task to:

- `task_id`
- `axis`
- `domain`
- `hidden_case_commitment`
- `checker_commitment`
- `budget_commitment`
- `human_reference_commitment`
- `trial_count`
- `contamination_class`

### `CapabilityTrialResultV1`

Binds actual execution evidence to a task spec:

- task-spec root;
- trial index;
- deterministic checker verdict/score;
- output digest;
- execution/effect/admission roots when available;
- actual resource expenditure;
- model/provider/runtime identity.

The result MUST NOT accept caller-declared correctness as authority.

### `CapabilityAxisAssessmentV1`

Aggregates only preregistered task results belonging to one axis. Missing required trials fail closed.

### `AGIEvidenceAssessmentV1`

Produces one of:

- `NOT_EVALUATED`
- `INSUFFICIENT_EVIDENCE`
- `PARTIAL_EVIDENCE`
- `PREREGISTERED_THRESHOLD_MET`
- `HYPOTHESIS_REJECTED`

`AGI_PROVEN` is intentionally not a runtime status in v1. A preregistered threshold crossing is evidence, not an ontological theorem. Stronger public claims require independent replication and external benchmark receipts.

## Conjunctive gate

Let required axes be `A`. For preregistered axis thresholds `theta_a`:

`ThresholdMet => forall a in A: Complete(a) AND Score(a) >= theta_a`

Additionally:

- no hidden-answer exposure may be detected;
- all checker roots must match the preregistered manifest;
- all task/trial cardinalities must match exactly;
- system and constituent baseline manifests must be budget-comparable;
- metacognitive calibration must be computed from predictions made before checker revelation;
- safety invariant violations force `HYPOTHESIS_REJECTED` for that run regardless of capability score.

## Collective-intelligence attribution

AEGIS-level capability and AGI evidence are distinct from provider capability. UCI-7 therefore records the strongest constituent baseline under the same manifest and computes system-vs-baseline deltas per axis. A positive delta is evidence for collective-system contribution; it is not required to call a constituent model intelligent, but it is required for any claim that AEGIS coordination itself adds capability.

## Explicit non-claims

```text
AGI = NOT_ESTABLISHED
ARC_AGI_2_PASS = NOT_ESTABLISHED
GAIA_PASS = NOT_ESTABLISHED
METR_TIME_HORIZON_RESULT = NOT_ESTABLISHED
INDEPENDENT_EXTERNAL_REPLICATION = NOT_ESTABLISHED
CURRENT_UCI7_STATUS = PROTOCOL_ONLY_UNTIL_TESTED
```

## Implementation sequence

1. RED: preregister falsifiers for missing-axis compensation, post-hoc threshold mutation, fabricated correctness, hidden-answer exposure, task-cardinality drift, baseline budget mismatch, unsafe-run override and pre-checker calibration binding.
2. GREEN: implement pure deterministic protocol objects/evaluator only; no model calls.
3. Serialization: closed Draft 2020-12 schemas with required `*_kind` discriminators and separate hash domains.
4. Native CI: exact frozen-parent binding to `#278@156062855...`, schema checks, exact test cardinality and evidence artifact.
5. Evaluation adapters: ARC/GAIA/METR-compatible result ingestion only after protocol core is green.
6. Actual capability campaign: run external/public + held-out suites; no AGI status promotion from unit tests of the evaluator itself.
