# Self-Improvement Loop V1 Design

Status: approved design / implementation target / evidence-only.

## Objective

Build the smallest repository-native self-improvement vertical slice that can verify a bounded capability-improvement experiment without allowing the candidate, builder, evaluator, or improvement kernel to mint authority.

The slice is not recursive self-improvement and is not an autonomous admission system. It is a deterministic evidence kernel that turns a preregistered hypothesis, frozen experiment contract, candidate observation, and independently authenticated evaluation receipt into either a fail-closed denial or an `ImprovementReceiptV1` with `authority_class == "NONE"`.

## Authority boundary

`harness/sdk/sovereign_execution.py` remains the single authority-decision path for consequential AEGIS work.

This module MUST NOT:

- grant execution permission;
- mutate canonical control state;
- issue `AuthorityRequest` or `PolicyDecision` objects;
- merge, deploy, or promote a candidate;
- infer authority from capability gain;
- treat evaluator output as trusted merely because its digest is well formed.

A successful improvement receipt is evidence only. Any later admission is external and independently governed.

## Vertical slice

`HypothesisEnvelopeV1`
→ `ExperimentContractV1`
→ bounded candidate observation
→ independently issued `EvaluationReceiptV1`
→ trusted evaluation receipt store
→ `ImprovementVerifierV1`
→ anti-splicing / anti-cheating / metric gates
→ `ImprovementReceiptV1(authority_class="NONE")`

## Deterministic representations

All authority-adjacent roots use `harness.sdk.sovereign_execution.canonical_hash` with explicit domain separation.

Metric values are signed integer micro-units (`int`), not floating-point. This keeps the verification boundary deterministic and avoids compiler/runtime reassociation ambiguity. Exploratory numeric code may use faster floating-point paths elsewhere, but values entering this verifier are frozen integer observations.

Every root is an exact lowercase 64-hex SHA-256 digest.

## Core types

### `HypothesisEnvelopeV1`

Binds:

- `hypothesis_id`;
- `baseline_artifact_root`;
- `proposal_root`;
- `search_policy_root`;
- `declared_objective_root`.

### `MetricRuleV1`

Binds:

- `metric_id`;
- `direction` (`MAXIMIZE` or `MINIMIZE`);
- `minimum_improvement_micros`.

The signed improvement is:

- MAXIMIZE: `candidate - baseline`;
- MINIMIZE: `baseline - candidate`.

The gate passes only when signed improvement is at least the preregistered threshold.

### `ExperimentContractV1`

Binds before candidate evaluation:

- exact `hypothesis_root`;
- exact `baseline_artifact_root`;
- frozen public evaluation input root;
- frozen withheld-label root;
- frozen environment root;
- frozen evaluator root;
- frozen verifier root;
- frozen policy root;
- bounded `max_trials`;
- exact metric rules.

Candidate code cannot select its verifier or evaluator because those roots are committed before candidate observation.

### `CandidateObservationV1`

Binds:

- exact contract and hypothesis roots;
- exact baseline and candidate artifact roots;
- trial index;
- builder root;
- environment root;
- sorted unique roots the candidate process accessed.

The verifier fails closed if the withheld-label root appears in the declared candidate access set.

### `EvaluationReceiptV1`

An independent evidence artifact binding:

- exact contract root;
- exact baseline and candidate roots;
- exact evaluation input root;
- exact environment root;
- evaluator root;
- evaluator policy root;
- baseline metric observations;
- candidate metric observations;
- contamination flag;
- status.

A well-formed receipt is not trusted by itself. `ImprovementVerifierV1` requires it to resolve through a `TrustedEvaluationReceiptStore` and requires the fetched receipt root to equal the referenced root.

### `ImprovementReceiptV1`

Issued only after all gates pass. Binds:

- hypothesis root;
- experiment contract root;
- candidate observation root;
- evaluation receipt root;
- baseline and candidate artifact roots;
- exact signed metric improvements;
- verifier root;
- policy root;
- verification root;
- `authority_class = NONE`.

## Fail-closed gates

The verifier denies on any of the following:

1. hypothesis ↔ contract mismatch;
2. baseline mismatch;
3. candidate observation ↔ contract/hypothesis mismatch;
4. candidate environment mismatch;
5. trial index outside `[0, max_trials)`;
6. candidate access to withheld labels;
7. missing trusted evaluation receipt;
8. fetched evaluation receipt root mismatch;
9. evaluation receipt ↔ contract/candidate/baseline/evaluation/environment mismatch;
10. evaluator root mismatch;
11. evaluator policy root mismatch;
12. contamination detected;
13. non-PASS independent evaluation status;
14. duplicate or missing metric observations;
15. metric set mismatch with preregistered rules;
16. any metric below its preregistered improvement threshold;
17. verifier root or policy root mismatch with the frozen contract.

Errors are deterministic, deduplicated, and sorted.

## Anti-vacuity requirements

The adversarial suite must prove both directions:

- forged/spliced/contaminated/regressing evidence is denied;
- a correctly bound independent evaluation with threshold-satisfying metrics passes and produces an evidence-only receipt.

At least one test must prove that changing a candidate or evaluator binding changes the relevant receipt/root, so the verifier cannot pass by rejecting every candidate or by ignoring the new fields.

## Workflow contract

Create `.github/workflows/self-improvement-loop.yml` scoped to the new module, focused tests, workflow, and this spec/plan. It must:

1. checkout the exact candidate SHA;
2. assert `git rev-parse HEAD == CANDIDATE_SHA`;
3. use Python 3.12;
4. install pinned `pytest==8.3.5`;
5. compile the kernel and tests;
6. run the complete focused adversarial suite.

A workflow success establishes only this bounded verification slice at that exact head. It does not establish AGI, recursive self-improvement, canonical admission, or RH.