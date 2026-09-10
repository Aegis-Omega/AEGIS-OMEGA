# AEGIS Ω OpenAI Navier–Stokes Research Workflow V1 — Design

Status: DESIGN ONLY — NOT IMPLEMENTED
Date: 2026-09-11
Branch: `research/openai-navier-workflow-v1`
Authority effect: NONE
Merge status: NOT REQUESTED

## 1. Purpose

Build an AEGIS-native research orchestration loop modeled on the published OpenAI Navier–Stokes workflow pattern: diversify candidate approaches, search related stepping-stone problems, dynamically reallocate compute toward productive lanes, cross-pollinate intermediate results, then formalize and independently verify candidate proofs.

The subsystem is a research and verification engine. It MUST NOT treat model confidence, consensus, numerical evidence, symbolic manipulation, or a successful synthesis step as proof of the Navier–Stokes Millennium problem.

## 2. Constitutional boundary

The governing invariant is:

`admitted_authority <= weakest_verified_transition`

Capability growth does not grant authority growth. A candidate mathematical argument may progress through the research graph while its final claim remains blocked.

Default terminal state for incomplete candidates:

```text
decision = HOLD_RESEARCH_ONLY
claim_promotion = BLOCKED
execution_release = BLOCKED
authority_effect = NONE
```

No workflow step may merge code, modify protected governance state, publish a theorem claim, or mutate `.claude.json` or `INTEGRATION_LEDGER.md`.

## 3. Target claim boundary

The target is the standard 3D incompressible Navier–Stokes global regularity / breakdown problem. The workflow MUST preserve the distinction among:

- reformulations and conditional implications;
- auxiliary Euler or simplified-model results;
- numerical or symbolic falsification evidence;
- machine-checked local lemmas;
- complete closure of the standard Millennium problem.

A result on an auxiliary or surrogate problem MUST NOT inherit the authority of the target claim.

## 4. Architecture

### 4.1 Portfolio controller

Maintains a typed portfolio of research lanes. Each lane records:

```text
lane_id
problem_statement_digest
problem_class = TARGET | SURROGATE | ATTACK | COUNTEREXAMPLE
parent_lane_ids[]
assumptions[]
claim_scope
budget_cap
status
latest_receipt_digest
```

The initial portfolio contains at least:

1. positive regularity/proof search;
2. counterexample/blow-up search;
3. Euler or reduced-model stepping-stone search;
4. inequality / a-priori-estimate search;
5. formalization and assumption-audit lane.

### 4.2 Divergent research workers

Workers receive different research objectives and MUST preserve approach diversity. Workers may emit only structured candidate artifacts, not promoted conclusions.

Each candidate artifact includes:

```text
candidate_id
lane_id
claim
assumptions
new_lemma_or_bridge
source_coordinates[]
dependencies[]
known_failure_modes[]
falsification_attempts[]
confidence_label
artifact_digest
```

`confidence_label` is advisory and has no authority effect.

### 4.3 Evidence evaluator

Scores artifacts for routing, not truth. Suggested routing features:

- novelty;
- dependency depth;
- number and severity of open obligations;
- successful independent checks;
- falsification survival;
- transfer utility to other lanes;
- formalizability;
- reproducibility cost.

The evaluator MUST NOT convert a high score into claim admission.

### 4.4 Stepping-stone detector

Detects auxiliary results that could reduce target uncertainty. A stepping-stone transition requires an explicit bridge record:

```text
source_candidate_digest
target_lane
transfer_claim
required_assumptions
bridge_status = OPEN | VERIFIED_WITHIN_SCOPE | FALSIFIED
```

No semantic similarity alone is sufficient for transfer.

### 4.5 Dynamic allocator

Reallocates bounded compute to lanes with the best evidence-adjusted expected information gain while preserving a minimum diversity floor.

Conceptual policy:

```text
priority(lane) =
  progress_signal
  + transfer_utility
  + verification_density
  - open_obligation_penalty
  - correlated_failure_penalty
```

The exact weights are configuration, not theorem semantics. A lane MUST retain a minimum exploration budget unless explicitly retired by a falsification receipt.

### 4.6 Cross-pollination synthesizer

Periodically builds a canonical shared research state from selected artifacts. It may transfer lemmas, counterexamples, failed paths, or proof obligations between lanes.

Cross-pollination MUST preserve provenance. Every imported idea carries its originating artifact digest and assumption set. The synthesizer may not flatten contradictory assumptions into one narrative.

### 4.7 Independent attacker

For every candidate promoted to `CANDIDATE_PROOF`, an independent adversarial lane attempts to break it by checking:

- hidden smoothness or decay assumptions;
- circular dependence;
- invalid limit/interchange steps;
- dimension/scaling mistakes;
- incorrect Sobolev embeddings or endpoint estimates;
- unjustified compactness / convergence steps;
- dependence on an unproved external statement;
- mismatch between surrogate and target problem.

A surviving candidate remains `CANDIDATE_PROOF`; survival alone is not final proof.

### 4.8 Formalization lane

Formalization is a separate verifier phase. The first implementation target is a proof-obligation graph and machine-checkable local lemmas. Lean or Coq may be used, but the workflow MUST record precisely which theorem statement was checked and under which assumptions.

Possible statuses:

```text
UNFORMALIZED
PARTIAL_FORMALIZATION
LOCAL_LEMMA_CLOSED
CONDITIONAL_CHAIN_CLOSED
TARGET_THEOREM_CLOSED
```

Only `TARGET_THEOREM_CLOSED`, combined with independent replay and exact statement binding, may make the target eligible for a stronger admission review. The workflow itself does not automatically grant that authority.

## 5. State machine

```text
PROPOSED
  -> TRIAGED
  -> ACTIVE_RESEARCH
  -> CANDIDATE_RESULT
  -> ADVERSARIAL_REVIEW
  -> FORMALIZATION
  -> INDEPENDENT_REPLAY
  -> ADMISSION_REVIEW
```

Failure states are first-class:

```text
FALSIFIED
STALE
DEPENDENCY_OPEN
SURROGATE_ONLY
FORMALIZATION_FAILED
REPLAY_FAILED
```

No failure state is silently discarded; it becomes reusable negative evidence.

## 6. Receipt model

Every state transition emits a canonical receipt compatible with the existing AEGIS evidence-chain philosophy. Minimum fields:

```text
schema
transition_id
candidate_id
from_state
to_state
exact_head_sha
input_artifact_digests[]
output_artifact_digest
assumptions[]
open_obligations[]
checks[]
verifier_identity
verifier_independence_class
decision
claim_promotion
authority_effect
previous_receipt_digest
receipt_digest
```

Canonical serialization MUST reject floats for authority-bearing numeric policy fields. Hashing uses SHA-256 and deterministic canonical JSON consistent with repository conventions.

## 7. OpenAI / Codex integration boundary

OpenAI/Codex is one research-worker and synthesis implementation, not the source of truth.

Initial integration MUST be read-only:

- manual `workflow_dispatch` first;
- exact checkout bound to `github.sha`;
- least-privilege GitHub permissions;
- no push, merge, release, deployment, issue mutation, or PR mutation;
- API credential only through GitHub Secrets / execution-time environment;
- structured output validated against an AEGIS schema;
- model output is `CANDIDATE_ONLY` until downstream checks pass.

Untrusted PR/issue text MUST NOT be allowed to invoke a privileged research run without trusted-actor authorization.

## 8. First implementation slice

The smallest useful implementation is deliberately narrower than the complete architecture:

1. `navier_workflow/schema_v1.py` — typed candidate/receipt validation and canonical hashing.
2. `navier_workflow/portfolio_v1.py` — deterministic lane registry and bounded priority calculation.
3. `navier_workflow/crosspollination_v1.py` — provenance-preserving synthesis of selected artifacts.
4. `navier_workflow/test_*.py` — RED-first tests for authority leakage, assumption loss, hash instability, and invalid state transitions.
5. `.github/workflows/navier-openai-research.yml` — manual, read-only hosted execution with no write authority.

The first slice MUST NOT contain an autonomous long-running swarm or claim to reproduce OpenAI-scale compute. It establishes the governed orchestration primitive that can later scale.

## 9. Required falsification tests

At minimum:

- a surrogate result cannot promote the target claim;
- a candidate with one open dependency cannot become `TARGET_THEOREM_CLOSED`;
- cross-pollination cannot drop assumptions or provenance;
- conflicting assumptions remain explicit;
- identical canonical inputs produce identical digests;
- caller-authored `VERIFIED` strings have no authority;
- a verifier cannot independently verify its own artifact;
- stale exact-head binding blocks admission;
- failed formalization blocks promotion;
- missing receipt link blocks promotion;
- compute-priority score cannot alter epistemic status;
- numerical evidence cannot close a theorem.

## 10. Success criteria for V1

V1 is successful only when:

```text
portfolio_orchestration = IMPLEMENTED_AND_TESTED
cross_pollination = PROVENANCE_PRESERVING_IN_TESTED_SCOPE
receipt_chain = DETERMINISTIC_AND_TAMPER_EVIDENT
openai_worker = READ_ONLY_CANDIDATE_PRODUCER
formal_proof_claim = NOT_MADE
navier_stokes_status = OPEN_UNLESS_TARGET_CLOSURE_EVIDENCE_EXISTS
authority_effect = NONE
```

## 11. Explicit non-goals

V1 does not:

- claim a new Navier–Stokes proof;
- reproduce OpenAI's unpublished internal orchestration code;
- infer private OpenAI implementation details;
- equate many-agent consensus with truth;
- treat numerical simulation as proof;
- grant merge or deployment authority;
- modify AEGIS constitutional state.

## 12. Promotion gate

Any future target-level promotion requires all of the following:

```text
exact_problem_statement_bound
all_dependencies_closed
formal_artifact_verified
independent_replay_passed
assumption_audit_passed
provenance_chain_complete
exact_head_fresh
constitutional_admission_passed
```

If any predicate is missing or false:

```text
decision = DENY_PROMOTION
claim_promotion = BLOCKED
authority_effect = NONE
```

This fail-closed boundary is invariant under model capability, agent count, compute budget, numerical performance, or external prestige.