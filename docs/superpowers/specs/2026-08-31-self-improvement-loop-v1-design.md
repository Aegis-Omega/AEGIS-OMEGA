# Self-Improvement Loop V1 Design

Status: implemented / evidence-only / exact-head verification required.

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
→ bounded `CandidateObservationV1`
→ independently issued `EvaluationReceiptV1`
→ trusted evaluation receipt store
→ `ImprovementVerifierV1`
→ provenance / anti-splicing / anti-cheating / metric gates
→ `ImprovementReceiptV1(authority_class="NONE")`

## Deterministic representations

All authority-adjacent roots use `harness.sdk.sovereign_execution.canonical_hash` with explicit domain separation.

Metric values are signed integer micro-units (`int`), not floating-point. Python `bool` is rejected despite being an `int` subclass. Metric direction must be an actual `MetricDirection` enum member, not an untyped string that happens to contain `MAXIMIZE` or `MINIMIZE`. This keeps the verification boundary deterministic and typed rather than relying on permissive runtime coercion.

Exploratory numeric code may use faster floating-point paths elsewhere, but values entering this verifier are frozen integer observations.

Every authority-adjacent root is an exact lowercase 64-hex SHA-256 digest.

Canonical roots sort set-like tuple inputs before hashing, including metric rules, metric observations, and access-root collections. Logical order therefore cannot alter the receipt identity where ordering has no semantic meaning.

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
- typed `MetricDirection` (`MAXIMIZE` or `MINIMIZE`);
- non-negative `minimum_improvement_micros` integer threshold.

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
- frozen evaluator-policy root;
- frozen verifier root;
- frozen verifier-policy root;
- bounded positive `max_trials`;
- exact unique metric rules.

Candidate code cannot select its verifier, evaluator, or either policy because those roots are committed before candidate observation.

### `CandidateObservationV1`

Binds:

- exact contract and hypothesis roots;
- exact baseline and candidate artifact roots;
- trial index;
- builder root;
- environment root;
- sorted unique roots the candidate process reports it accessed.

The candidate access list is **not** sufficient proof of non-contamination by itself. It is one side of a later equality check against an independently observed access trace committed by the trusted evaluator.

### `EvaluationReceiptV1`

An independently issued evidence artifact binding:

- exact contract root;
- exact baseline and candidate roots;
- exact evaluation input root;
- exact environment root;
- evaluator root;
- evaluator-policy root;
- sorted unique `observed_candidate_access_roots` produced by the independent evaluation boundary;
- exact baseline metric observations;
- exact candidate metric observations;
- contamination flag;
- status;
- `authority_class = NONE`.

A well-formed receipt is not trusted by itself. `ImprovementVerifierV1` requires it to resolve through a `TrustedEvaluationReceiptStore` and requires the fetched receipt root to equal the referenced root.

The trust claim is therefore deliberately narrow: this kernel verifies a receipt that the configured trusted store has authenticated. It does not prove that arbitrary evaluator processes are honest, nor does a candidate-authored object become trusted merely by hashing it.

### `ImprovementReceiptV1`

Issued only after all gates pass. Binds:

- hypothesis root;
- experiment contract root;
- candidate observation root;
- trusted evaluation receipt root;
- baseline and candidate artifact roots;
- exact signed metric improvements;
- verifier root;
- policy root;
- verification root;
- `authority_class = NONE`.

## Independent access-trace boundary

Evaluation gaming is treated as a first-class threat.

Two access observations are required:

1. `CandidateObservationV1.accessed_roots` — candidate-side declared trace;
2. `EvaluationReceiptV1.observed_candidate_access_roots` — independently observed trace authenticated through the trusted evaluation receipt store.

The verifier canonicalizes both and requires exact equality. A mismatch yields `ACCESS_OBSERVATION_BINDING_FAILURE`.

The frozen `withheld_labels_root` is checked against both traces. If either trace contains it, verification fails with `WITHHELD_LABEL_ACCESS_DETECTED`.

This prevents a candidate from passing the anti-cheating gate merely by omitting a forbidden access from its own self-report. The remaining trust assumption is explicit: the independently observed trace must originate from the authenticated evaluation boundary represented by the trusted store.

## Fail-closed gates

The verifier denies on any of the following:

1. verifier root mismatch with the frozen contract;
2. verifier-policy root mismatch with the frozen contract;
3. hypothesis root or baseline mismatch;
4. candidate observation ↔ contract / hypothesis / baseline mismatch;
5. candidate environment mismatch;
6. trial index outside `[0, max_trials)`;
7. candidate-declared access to withheld labels;
8. missing trusted evaluation receipt;
9. fetched evaluation receipt root mismatch;
10. evaluation receipt ↔ contract / candidate / baseline / evaluation-input / environment mismatch;
11. evaluator root mismatch;
12. evaluator-policy root mismatch;
13. candidate-declared access trace mismatch with independently observed access trace;
14. independently observed access to withheld labels;
15. explicit contamination detected;
16. non-PASS independent evaluation status;
17. duplicate or missing metric observations;
18. metric set mismatch with preregistered rules;
19. any metric below its preregistered improvement threshold;
20. malformed roots, non-integer metric values, boolean-as-integer values, or an untyped metric direction.

Errors returned from verification are deterministic, deduplicated, and sorted.

## Anti-vacuity and adversarial requirements

The adversarial suite proves both directions:

- forged, spliced, contaminated, self-report-hidden, policy-swapped, environment-swapped, out-of-bound, untrusted, incomplete, untyped, or regressing evidence is denied;
- a correctly bound independent evaluation with matching access traces and threshold-satisfying metrics passes and produces an evidence-only receipt.

The focused suite also checks that changing evaluator/candidate/access bindings changes the corresponding receipt root where applicable, and that canonical roots are invariant under permutation of semantically set-like tuple fields.

A verifier that merely rejects everything therefore cannot satisfy the positive control.

## Workflow contract

`.github/workflows/self-improvement-loop.yml` is scoped to the new kernel, focused tests, workflow, and this spec/plan. It must:

1. checkout the exact candidate SHA;
2. assert `git rev-parse HEAD == CANDIDATE_SHA`;
3. use Python 3.12;
4. install pinned `pytest==8.3.5`;
5. compile the kernel and focused tests;
6. run the complete focused adversarial suite.

A workflow success establishes only this bounded verification slice at that exact head. It does not establish recursive self-improvement, autonomous admission, AGI, mathematical theorem authority, Weil positivity, or RH.