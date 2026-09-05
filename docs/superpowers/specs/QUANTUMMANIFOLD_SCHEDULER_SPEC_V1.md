# QUANTUMMANIFOLD_SCHEDULER_SPEC_V1

Status: **DESIGN_SPEC / IMPLEMENTATION_OPEN**  
Architecture: **AEGIS Thread-as-QuantumManifold Core v0.1**  
Repository: `Aegis-Omega/AEGIS-OMEGA`  
Design base: `6eb2ac201bbe60ebaa9cebad714b8696683772e8`  
AEGIS Master Notebook v0.4 baseline digest: `457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404`

## 0. Epistemic status and authority boundary

This document is a normative design specification. It does **not** claim that the QuantumManifold Scheduler, role-isolation envelopes, replay protections, durable M1 persistence, or repository-wide merge enforcement are active on `main`.

At the design base, the bounded implementation status is:

```text
MATHEMATICAL ARCHITECTURE       = INTERNALLY_CONSISTENT_AND_DERIVED
PR #407 CLAIM GATE              = MACHINE_TESTED_ON_EXACT_HEAD
QUANTUMMANIFOLD SCHEDULER       = SPECIFIED_DESIGN_ONLY / IMPLEMENTATION_OPEN
ROLE ISOLATION ENVELOPES        = SPECIFIED_DESIGN_ONLY / RUNTIME_UNPROVEN
REPLAY SAFETY & STATE JOIN      = FORMALLY_SPECIFIED / IMPLEMENTATION_OPEN
DURABLE PERSISTENCE (M1-M4)     = NOT_ESTABLISHED
REPOSITORY MERGE ENFORCEMENT    = NOT_ACTIVE
GLOBAL FAIL-CLOSED SYSTEM       = NOT_YET_ESTABLISHED
```

The scheduler is never an authority source:

```text
SchedulerScore(A) != Authority(A)
SchedulingReceipt.authority_effect = NONE
RoleResultReceipt.authority_effect = NONE
Final positive execution authority = Automaton-3 only
```

No semantic similarity, model agreement, scheduler score, prose confidence, role consensus, memory continuity, graph centrality, or number of agreeing agents may transport or increase epistemic authority.

### 0.1 Authority is typed, not a scalar total order

Authority classes are domain-qualified. `MACHINE_BOUND` mathematics and `EXTERNAL_ESTABLISHED` empirical evidence are not automatically comparable as points on one scalar ladder.

The v0.1 authority classes are:

```text
MACHINE_BOUND
EXTERNAL_ESTABLISHED
TARGET_OPEN
NOT_ESTABLISHED
ADMITTED
```

`ADMITTED` means the applicable admission policy has accepted the claim for the declared domain and scope. It does not erase the source authority class or expand its domain.

The weakest-link rule is therefore expressed as a promotion predicate rather than as an unjustified total ordering:

\[
\operatorname{ADMIT}(C)
\Rightarrow
\forall T_i\in\operatorname{Required}(C),\;
\operatorname{ClosedForPolicy}(T_i)=\mathrm{true}.
\]

If any mandatory transition is `OPEN`, `TARGET_OPEN`, `NOT_ESTABLISHED`, missing, invalid, stale without verified rebase, or otherwise fails its domain policy, `ADMIT(C)` is forbidden.

Within a single authority domain where a partial order is defined, the compact notation remains:

\[
A(C) \preceq \bigwedge_i A(T_i).
\]

## 1. Plane Architecture M1-M4

The manifold architecture uses **Plane** terminology to avoid collision with the existing Tier 1-4 persistence/compaction architecture.

### M1 — History Plane

`M1` is append-only historical state. It preserves events, claim versions, evidence roots, scheduling receipts, execution/denial receipts, falsified threads, stale results, invalid attempts, rebase records, and admission outcomes.

Falsification never erases history.

### M2 — Reality Plane

`M2` is the currently admissible projection of `M1` under active evidence and policy:

\[
G_t=P_{\mathrm{admissible}}(G_{\mathrm{history}}).
\]

`M2` contains the active typed graph `G_t`, active threads `Γ_t^active`, and open obligations `O_t`.

### M3 — Verification Plane

`M3` contains deterministic verification and scheduling operators. It may include projectors such as `P_hat_not_C`, observability matrices `O`, graph verification operators, and the QuantumManifold scheduler. The v0.1 scheduler:

1. validates exact-head coordinates and digests;
2. validates the typed DAG;
3. computes obligation centrality;
4. computes information gain, closure leverage, falsification value, and cost;
5. ranks candidate actions deterministically;
6. emits only `SCHEDULING_RECOMMENDATION`.

`M3` cannot authorize execution.

### M4 — Execution Plane

`M4` contains action execution and agent dispatch. Every proposed action must pass the existing positive authority boundary. Automaton-3 returns exactly one execution decision:

```text
DENY | ADMIT
```

No direct `M4 -> M2` promotion is allowed.

## 2. Typed Reality Graph G_t

### 2.1 Node types

The only v0.1 node types are:

```text
CLAIM
OBLIGATION
EVIDENCE
THREAD
ACTION_CANDIDATE
```

Unknown node types fail closed.

### 2.2 Edge types

The only v0.1 edge types are:

```text
DEPENDS_ON
SUPPORTED_BY
FALSIFIED_BY
BLOCKS
CLOSES
DERIVED_FROM
BELONGS_TO_THREAD
```

Unknown edge types, dangling endpoints, identifier collisions with non-identical content, and cycles in the declared DAG are invalid.

### 2.3 Historical preservation

For any thread `γ`:

\[
\gamma\in\Gamma_{\mathrm{history}}
\]

may remain true while:

\[
\gamma\notin\Gamma_t^{\mathrm{active}}.
\]

A valid falsification changes the admissible projection, not the historical record.

## 3. Coordinate fixation and canonical digests

Every scheduling computation is bound to:

\[
(H_t,D_B,D_{G_t},D_{O_t},D_{A_t},D_{\Pi}),
\]

where:

- `H_t` = exact `source_head_sha`;
- `D_B` = immutable v0.4 `baseline_digest`;
- `D_Gt` = `reality_snapshot_digest`;
- `D_Ot` = `obligation_set_digest`;
- `D_At` = `candidate_set_digest`;
- `D_Π` = `scheduler_policy_digest`.

The baseline digest and reality snapshot digest are semantically distinct:

```text
baseline_digest         = immutable research-control baseline identity
reality_snapshot_digest = digest of the concrete active G_t snapshot
```

The `source_head_sha` must be the actual commit coordinate from which the relevant graph/evidence state was constructed. A historical proof head such as `99d3700c2d5a2aab73a756109dda80de439d1baa` is valid only when the scheduler is explicitly operating on evidence bound to that head.

### 3.1 Claim-by-claim morphism binding

A morphism may preserve a claim and its authority only through a claim-specific evidence binding. Semantic similarity is never sufficient.

Each transported claim binding must include at least:

```json
{
  "claim_id": "<claim-id>",
  "source_evidence_root": "<content-bound evidence root>",
  "source_authority": "<domain-qualified authority class>",
  "preservation_proof_root": "<content-bound preservation proof/receipt>",
  "destination_claim_digest": "<canonical claim digest>",
  "transported_authority": "<domain-qualified authority class>"
}
```

Invariants:

```text
CLAIM_BY_CLAIM_EVIDENCE_BINDING_REQUIRED
SEMANTIC_SIMILARITY != AUTHORITY_TRANSPORT
NO_CROSS_CLAIM_AUTHORITY_INFERENCE
TRANSPORTED_AUTHORITY MUST REMAIN WITHIN SOURCE DOMAIN/SCOPE
```

A morphism may be structurally valid while its global weakest-link status remains `OPEN`; such a morphism cannot be used to promote unrelated or downstream claims across that open edge.

## 4. Deterministic fixed-point scheduler

### 4.1 Canonical integer domain

Define:

```text
PPM = 1_000_000
MAX_SAFE_CANONICAL_INT = 9_007_199_254_740_991
```

All serialized scheduler metrics and policy coefficients are non-negative integers. Floating-point values are forbidden in canonical scheduling inputs and receipts.

Probabilities such as `p_close_ppm` and `p_falsify_ppm` are restricted to:

```text
0 <= p_ppm <= PPM
```

Other scaled metrics may exceed `PPM` but may not exceed `MAX_SAFE_CANONICAL_INT` when serialized.

Internal arithmetic must use exact arbitrary-precision integers. Intermediate products may exceed the serialized domain; they are range-checked only when converted to a canonical serialized metric.

Any negative value in a non-negative field, non-integer value, overflow at serialization, or lossy conversion fails closed.

### 4.2 Normative arithmetic primitives

All runtimes must implement the same integer operations:

\[
\operatorname{mul\_ppm}(x,y)
=
\left\lfloor\frac{x\,y}{10^6}\right\rfloor.
\]

All division in the scheduler uses mathematical floor division over non-negative integers. No runtime-native floating division is permitted.

The final score is computed by:

```text
weighted_ig_ppm = mul_ppm(alpha_ppm, information_gain_ppm)
weighted_l_ppm  = mul_ppm(beta_ppm, closure_leverage_ppm)
weighted_f_ppm  = mul_ppm(gamma_ppm, falsification_value_ppm)

numerator_ppm   = weighted_ig_ppm + weighted_l_ppm + weighted_f_ppm
denominator_ppm = epsilon_ppm + cost_ppm
ranking_score_ppm = floor(numerator_ppm * PPM / denominator_ppm)
```

`epsilon_ppm` must be strictly positive. `denominator_ppm` must be strictly positive. The serialized result is range-checked after exact integer evaluation.

This arithmetic definition is part of the canonical policy and is not implementation discretion.

### 4.3 Obligation centrality

For open obligation `o_k`, define reachable downstream priority mass:

\[
M(o_k)=\sum_{c\in D(o_k)} w_c,
\]

where `D(o_k)` is the set of active downstream terminal/claim nodes that depend on `o_k`, and `w_c` is a non-negative policy-bound integer priority.

Let:

\[
M_{\mathrm{total}}=\sum_{c\in C_t^{\mathrm{terminal}}}w_c.
\]

Then:

\[
\operatorname{centrality}_{ppm}(o_k)=
\begin{cases}
0,&M_{\mathrm{total}}=0,\\
\left\lfloor\dfrac{M(o_k)\,PPM}{M_{\mathrm{total}}}\right\rfloor,&M_{\mathrm{total}}>0.
\end{cases}
\]

This is an optimization quantity, not authority.

### 4.4 Closure leverage

For candidate action `A`:

\[
L_{ppm}(A)=
\sum_{o_k\in O_t}
\operatorname{mul\_ppm}
\left(
p_{\mathrm{close},ppm}(o_k\mid A),
\operatorname{centrality}_{ppm}(o_k)
\right).
\]

`p_close_ppm` is a policy-bound scheduling prior and must be auditable. It is not a truth probability and cannot promote a claim.

### 4.5 Falsification value

\[
F_{ppm}(A)=
\sum_{\gamma\in\Gamma_t^{\mathrm{active}}}
\operatorname{mul\_ppm}
\left(
p_{\mathrm{falsify},ppm}(\gamma\mid A),
V_{\mathrm{pruned},ppm}(\gamma)
\right).
\]

`V_pruned_ppm` estimates avoidable future compute/evidence work if a thread is legitimately falsified. It is an optimization quantity, not a scientific truth value.

### 4.6 Information gain and cost

The v0.1 model is:

\[
S(A)=
\frac{\alpha IG(A)+\beta L(A)+\gamma F(A)}{\varepsilon+C(A)},
\]

with:

\[
C(A)=C_{\mathrm{compute}}+\mu C_{\mathrm{evidence}}+\eta C_{\mathrm{latency}}.
\]

Canonical fixed-point cost is computed using the same `mul_ppm` primitive:

```text
cost_ppm = compute_cost_ppm
         + mul_ppm(mu_ppm, evidence_cost_ppm)
         + mul_ppm(eta_ppm, latency_cost_ppm)
```

Constraints:

```text
alpha_ppm, beta_ppm, gamma_ppm, mu_ppm, eta_ppm >= 0
epsilon_ppm > 0
```

All coefficients and arithmetic rules are covered by `scheduler_policy_digest`.

### 4.7 Deterministic tie-breaking

For equal `ranking_score_ppm`, actions are ordered by:

1. larger `closure_leverage_ppm`;
2. larger `falsification_value_ppm`;
3. smaller `cost_ppm`;
4. lexicographically smaller lowercase `candidate_action_digest` using ASCII order.

Equivalent ordering key:

```text
(-S, -L, -F, C, candidate_action_digest)
```

The candidate action digest is required to be unique within a canonical candidate set. Identical digests with non-identical canonical action content are a collision and fail closed.

For identical canonical input tuples, the selected action and serialized receipt must be byte-identical across supported runtimes.

## 5. Scheduling receipt

Normative v0.1 shape:

```json
{
  "receipt_kind": "AEGIS_QUANTUMMANIFOLD_SCHEDULING_RECEIPT_V1",
  "baseline_digest": "<64-lowercase-hex>",
  "source_head_sha": "<40-lowercase-hex>",
  "reality_snapshot_digest": "<64-lowercase-hex>",
  "obligation_set_digest": "<64-lowercase-hex>",
  "candidate_set_digest": "<64-lowercase-hex>",
  "scheduler_policy_digest": "<64-lowercase-hex>",
  "selected_action_digest": "<64-lowercase-hex>",
  "score_components_fixed_point": {
    "information_gain_ppm": 0,
    "closure_leverage_ppm": 0,
    "falsification_value_ppm": 0,
    "cost_ppm": 0,
    "ranking_score_ppm": 0
  },
  "recommended_role": "BUILDER",
  "authority_effect": "NONE"
}
```

`recommended_role` is one of:

```text
BUILDER | FALSIFIER | REVIEWER
```

Any receipt with `authority_effect != NONE` is invalid.

## 6. Role-state isolation

### 6.1 Builder — PRESERVE

Builder may inherit constructive continuity needed to continue the active branch: exact head, baseline/reality digests, active thread lineage, admitted evidence, previous Builder continuation state, implementation/proof artifacts, and open obligations.

Builder prose confidence, model self-assessment, and scheduler ranking do not carry authority. Builder output is a candidate delta only.

### 6.2 Falsifier — RAW_EVIDENCE_ONLY

Falsifier receives only:

- canonical claim statement;
- exact-head coordinate;
- locked RED/falsification contract;
- raw evidence roots;
- machine-readable artifacts;
- relevant measurement/test inputs;
- declared assumptions.

Falsifier does not receive Builder reasoning narrative, Builder confidence, Builder continuation memory, or Reviewer conclusions.

Allowed outcomes:

```text
FALSIFIED
SURVIVED_CURRENT_FALSIFIER
INCONCLUSIVE
INVALID_TEST
```

Invariant:

```text
SURVIVED_CURRENT_FALSIFIER != PROVEN
```

### 6.3 Reviewer — CLEAN_ROOM

Reviewer receives reconstructed machine evidence only: canonical claim AST/statement, dependency DAG, exact source head, compiler/Coq/test outputs, verification receipts, raw-data digests where relevant, assumptions inventory, falsifier outcome receipt, and applicable policy digest.

Reviewer does not receive Builder prose, Falsifier prose, prior reviewer opinions, hidden model continuation state, or scheduler persuasion.

Allowed outcomes:

```text
RECOMMEND_ACCEPT
RECOMMEND_REJECT
INCONCLUSIVE
```

### 6.4 Cross-role state join

The only authoritative cross-role state join is:

```text
EVIDENCE DIGESTS
RECEIPT DIGESTS
EXACT-HEAD COORDINATES
```

Prose-to-prose authority transport is forbidden.

## 7. Role context envelope

Normative v0.1 shape:

```json
{
  "receipt_kind": "AEGIS_ROLE_CONTEXT_ENVELOPE_V1",
  "role": "BUILDER",
  "inheritance_policy": "PRESERVE",
  "baseline_digest": "<64-lowercase-hex>",
  "source_head_sha": "<40-lowercase-hex>",
  "reality_snapshot_digest": "<64-lowercase-hex>",
  "selected_action_digest": "<64-lowercase-hex>",
  "obligation_digest": "<64-lowercase-hex>",
  "scheduler_receipt_digest": "<64-lowercase-hex>",
  "role_policy_digest": "<64-lowercase-hex>",
  "input_evidence_roots": [],
  "continuation_state_digest": null,
  "authority_effect": "NONE"
}
```

Role policy constraints:

```text
BUILDER   -> PRESERVE
FALSIFIER -> RAW_EVIDENCE_ONLY and continuation_state_digest = null
REVIEWER  -> CLEAN_ROOM and continuation_state_digest = null
```

A machine-reconstructed evidence index is not model continuation memory and may be referenced separately by digest.

## 8. Role output receipts

The role-specific receipt kinds are:

```text
AEGIS_BUILDER_RESULT_RECEIPT_V1
AEGIS_FALSIFICATION_RECEIPT_V1
AEGIS_CLEAN_ROOM_REVIEW_RECEIPT_V1
```

All role output receipts carry:

```text
authority_effect = NONE
```

No role may issue `ADMIT`.

## 9. Runtime lifecycle

The canonical runtime transition system is:

```text
M1 HISTORY
  -> deterministic admissibility projection
M2 REALITY
  -> deterministic scheduling/verification
M3 VERIFICATION
  -> Automaton-3 authorization
M4 EXECUTION
  -> append-only result/denial/receipt
M1 HISTORY
```

Formally:

\[
M_1
\xrightarrow{P_{\mathrm{admissible}}}
M_2
\xrightarrow{S_{\Pi}}
M_3
\xrightarrow{\mathrm{Automaton\text{-}3}}
M_4
\xrightarrow{\mathrm{append}}
M_1.
\]

Forbidden transition:

\[
M_4\not\rightarrow M_2.
\]

An executed Builder task is not automatically new reality. It becomes an `M1` historical artifact and must pass the relevant verification/admission chain before it can affect a later `M2` projection.

## 10. Concurrency and stale-result handling

Every dispatched role envelope is bound to at least:

```text
source_head_sha
reality_snapshot_digest
obligation_digest
selected_action_digest
```

If the source head, active reality snapshot, or obligation coordinate changes before the result returns, that result is classified:

```text
STALE_RESULT_REQUIRES_REBASE
```

The result remains preserved in `M1` but is blocked from automatic inclusion in `M2`.

```text
STALE != INVALID
```

## 11. Failure semantics

### 11.1 FAIL_CLOSED

Use `FAIL_CLOSED` for invalid evidence, invalid graph structure, invalid canonical bindings, impossible numeric state, authority tunneling, or replay divergence.

Representative reason codes:

```text
BASELINE_BINDING_MISMATCH
SOURCE_HEAD_INVALID
REALITY_DIGEST_MISMATCH
UNKNOWN_NODE_TYPE
UNKNOWN_EDGE_TYPE
GRAPH_CYCLE_DETECTED
NODE_ID_COLLISION
DANGLING_EDGE
SCHEDULER_POLICY_MISMATCH
FIXED_POINT_DOMAIN_ERROR
SCORE_RANGE_EXCEEDED
INVALID_STABILIZER
AUTHORITY_TUNNELING_ATTEMPT
ROLE_ISOLATION_VIOLATION
CLEAN_ROOM_VIOLATION
REPLAY_STATE_DIVERGENCE
STATE_RESET_EXPOSURE
DIRECT_M4_TO_M2_PROMOTION_FORBIDDEN
EPISTEMIC_INFLATION_FORBIDDEN
```

### 11.2 DEFER

`DEFER` means the state is structurally valid but insufficiently closed for the requested promotion or recommendation.

```text
DEFER != DENY
```

### 11.3 REBASE_REQUIRED

Use `REBASE_REQUIRED` for valid historical results whose coordinate is stale relative to current `M2`.

### 11.4 DENY / ADMIT

Only the Automaton-3 authority boundary may issue execution `DENY` or `ADMIT`.

## 12. Replay and side-effect safety

### 12.1 Evidence reconstruction replay

Replay may deterministically reconstruct:

\[
M_1\rightarrow G_t\rightarrow\mathcal A_t\rightarrow\text{SchedulingReceipt}.
\]

For identical canonical inputs, the reconstructed scheduling receipt must be byte-identical.

### 12.2 Execution intent

Each M4 attempt is bound to a canonical execution intent digest derived from at least:

```text
source_head_sha
reality_snapshot_digest
selected_action_digest
role_context_digest
attempt_sequence
```

Conceptually:

\[
D_{\mathrm{intent}}=H(\operatorname{JCS}(H_t,D_{G_t},D_A,D_{role},n_{attempt})).
\]

A previously consumed execution intent may not execute again:

```text
EXECUTION_INTENT_REPLAY -> BLOCK
```

A legitimate repeated experiment/test requires a new monotonic `attempt_sequence` and a new Automaton-3 authorization decision.

```text
EVIDENCE_RECONSTRUCTION_REPLAY = ALLOWED
SIDE_EFFECT_AUTO_REPLAY        = FORBIDDEN
```

## 13. Persistence and recovery boundary

The repository already contains a deterministic ledger serialization/reconstruction seam, but that seam is not itself a durable database backend. QuantumManifold v0.1 must not claim durable crash-safe runtime persistence until a storage backend and restart recovery path are separately implemented and verified.

Recovery invariants are:

\[
D_{G_t}^{\mathrm{replayed}}=D_{G_t}^{\mathrm{recorded}}
\]

and

\[
D_{sched}^{\mathrm{replayed}}=D_{sched}^{\mathrm{recorded}}.
\]

Any mismatch fails closed with `REPLAY_STATE_DIVERGENCE`.

Restart without a valid persisted authoritative root must not silently create a fresh genesis state:

```text
STATE_RESET_EXPOSURE -> FAIL_CLOSED
```

## 14. Seven design-level derived theorems

These are **theorems of the specified transition system**, conditional on an implementation conforming to this specification. They are not claims that the runtime implementation already exists.

### T1 — Authority Boundary Safety

Because the scheduler emits only `authority_effect=NONE` recommendations and no scheduler transition targets `ADMIT`, scheduler ranking cannot itself grant execution authority.

\[
\mathrm{SchedulerScore}(A)\not\Rightarrow\mathrm{Authorized}(A).
\]

### T2 — Deterministic Scheduling Reproducibility

Given identical canonical `(G_t, policy, candidate set)` inputs, the exact integer arithmetic in §4, and the total deterministic tie-break order, the selected action is unique. With deterministic canonical serialization, the scheduling receipt is byte-identical.

### T3 — Stale-Result Isolation

If a result returns bound to an old `(source_head_sha, reality_snapshot_digest, obligation_digest)` coordinate, it remains historical in `M1` and is excluded from current `M2` until a verified rebase occurs.

### T4 — Falsification Preservation

Removing a falsified thread from `Γ_t^active` does not remove it from historical lineage. Therefore falsification reduces active search support without destroying provenance.

### T5 — Replay Effect Safety

A consumed `execution_intent_digest` cannot execute twice under the same attempt identity, while deterministic evidence replay remains allowed. Therefore evidence replayability and effect non-replayability can coexist.

### T6 — Role Prose Isolation

Because the Falsifier and Reviewer input domains exclude Builder continuation/prose and cross-role authoritative joins are digest-only, Builder persuasive prose cannot be an authorized cross-role state-transition carrier.

### T7 — Weakest-Link Admission Bound

For any claim `C`, admission requires every mandatory transition to satisfy the applicable domain policy. Therefore any mandatory `OPEN`, `TARGET_OPEN`, `NOT_ESTABLISHED`, invalid, missing, or unreconciled stale transition blocks admission, regardless of how many other upstream transitions are machine-bound.

## 15. RED falsification matrix

The first implementation cycle must establish RED evidence before any GREEN scheduler implementation is admitted.

| RED ID | Falsifier | Expected failure / invariant |
|---|---|---|
| `QM-RED-001` | Production QuantumManifold module absent | expected RED anchor: module/import failure |
| `QM-RED-002` | Wrong `baseline_digest` | `BASELINE_BINDING_MISMATCH` |
| `QM-RED-003` | Invalid/non-ancestor exact-head coordinate | `SOURCE_HEAD_INVALID` |
| `QM-RED-004` | `reality_snapshot_digest` mismatch | `REALITY_DIGEST_MISMATCH` |
| `QM-RED-005` | Unknown node type | `UNKNOWN_NODE_TYPE` |
| `QM-RED-006` | Unknown edge type | `UNKNOWN_EDGE_TYPE` |
| `QM-RED-007` | Cycle in declared DAG | `GRAPH_CYCLE_DETECTED` |
| `QM-RED-008` | Same node ID, different content | `NODE_ID_COLLISION` |
| `QM-RED-009` | Dangling graph edge | `DANGLING_EDGE` |
| `QM-RED-010` | Scheduler policy digest mismatch | `SCHEDULER_POLICY_MISMATCH` |
| `QM-RED-011` | Negative/non-integer/overflow canonical numeric value | `FIXED_POINT_DOMAIN_ERROR` or `SCORE_RANGE_EXCEEDED` |
| `QM-RED-012` | `epsilon_ppm <= 0` | `INVALID_STABILIZER` |
| `QM-RED-013` | Equal score actions | deterministic canonical tie-break |
| `QM-RED-014` | Same input executed 3+ times | byte-identical SchedulingReceipt |
| `QM-RED-015` | Scheduler sets `authority_effect != NONE` | `AUTHORITY_TUNNELING_ATTEMPT` |
| `QM-RED-016` | Falsifier receives Builder continuation | `ROLE_ISOLATION_VIOLATION` |
| `QM-RED-017` | Reviewer receives prose continuation | `CLEAN_ROOM_VIOLATION` |
| `QM-RED-018` | Result returns after reality/head drift | `STALE_RESULT_REQUIRES_REBASE` |
| `QM-RED-019` | Same execution intent repeated | `EXECUTION_INTENT_REPLAY` |
| `QM-RED-020` | Replay reconstructs different `G_t` digest | `REPLAY_STATE_DIVERGENCE` |
| `QM-RED-021` | Restart without persisted authoritative root | `STATE_RESET_EXPOSURE` |
| `QM-RED-022` | Automaton-3 returns `DENY` | zero agent side effects |
| `QM-RED-023` | Builder result directly changes `M2` | `DIRECT_M4_TO_M2_PROMOTION_FORBIDDEN` |
| `QM-RED-024` | `SURVIVED_CURRENT_FALSIFIER` maps to `PROVEN` | `EPISTEMIC_INFLATION_FORBIDDEN` |

`QM-RED-013` and `QM-RED-014` are determinism falsifiers: the test fails if the deterministic property is violated.

## 16. Implementation boundaries and expected surfaces

The implementation plan may introduce focused modules for:

1. typed graph validation and canonical snapshot construction;
2. exact fixed-point arithmetic, scoring, and deterministic ranking;
3. scheduling receipt creation/verification;
4. claim-level morphism binding validation;
5. role context envelope creation/verification;
6. stale/rebase validation;
7. replay intent protection;
8. coordinator integration that preserves Automaton-3 as the only positive authority source;
9. RED/GREEN test and CI lanes.

The implementation must follow existing repository patterns and must not replace the coordinator authority boundary. Existing `agents/coordinator.py` remains the positive-authority choke point unless a separately approved architecture change replaces it.

## 17. Explicit non-goals for v0.1

The following are out of scope and must not be implied by this specification:

- physical quantum computation or physical quantum superposition;
- proof that human/agent cognition is quantum mechanical;
- repository-wide merge protection activation;
- durable production database persistence;
- automatic scientific truth admission from model outputs;
- direct claim promotion from scheduling score;
- replacement of Automaton-3 authority;
- proof of RH or any other open mathematical conjecture;
- empirical validation of biological nonclassicality;
- production-grade calibration of `IG`, `L`, `F`, `C`, `p_close`, or `p_falsify` priors.

## 18. Repository enforcement status

At the design base:

```text
MAIN HEAD                        = 6eb2ac201bbe60ebaa9cebad714b8696683772e8
MAIN BRANCH PROTECTION           = FALSE
MAIN REQUIRED STATUS CHECKS      = OFF
VISIBLE REPOSITORY RULESET       = DISABLED
FAIL_CLOSED_VERIFIER_LOGIC       = EXISTS IN BOUNDED SURFACES
EXACT_HEAD_PROOF GATES           = EXISTS IN BOUNDED SURFACES
PR407 CLAIM PROMOTION GATE       = MACHINE_TESTED ON ITS EXACT HEAD
REPOSITORY_MERGE_ENFORCEMENT     = NOT_ACTIVE
GLOBAL_FAIL_CLOSED_ADMISSION     = NOT_ESTABLISHED
```

No future document or implementation may promote this status without fresh repository evidence.

## 19. Canonical v0.1 invariant summary

```text
AEGIS THREAD-AS-QUANTUMMANIFOLD CORE v0.1

M1:
  APPEND_ONLY_HISTORY
  FALSIFICATION_DOES_NOT_ERASE_HISTORY

M2:
  DETERMINISTIC_ADMISSIBLE_PROJECTION
  CANONICAL_REALITY_DIGEST

M3:
  TYPED_DAG
  EXACT_INTEGER_FIXED_POINT_SCORING
  SCHEDULING_AUTHORITY_EFFECT = NONE

M4:
  AUTOMATON_3_ONLY_POSITIVE_AUTHORITY
  ROLE_ISOLATION_ENFORCED_BY_CONTRACT
  NO_DIRECT_M4_TO_M2_PROMOTION

ROLE STATE:
  BUILDER   = PRESERVE
  FALSIFIER = RAW_EVIDENCE_ONLY
  REVIEWER  = CLEAN_ROOM

STATE JOIN:
  EVIDENCE_DIGESTS + RECEIPT_DIGESTS + EXACT_HEAD_COORDINATES ONLY

MORPHISM:
  CLAIM_BY_CLAIM_EVIDENCE_BINDING_REQUIRED
  SEMANTIC_SIMILARITY != AUTHORITY_TRANSPORT

REPLAY:
  EVIDENCE_RECONSTRUCTION = ALLOWED
  SIDE_EFFECT_AUTO_REPLAY = FORBIDDEN
  DUPLICATE_INTENT        = BLOCKED

STALE:
  PRESERVE_IN_M1
  BLOCK_FROM_M2
  REBASE_REQUIRED

PERSISTENCE:
  SERIALIZATION/RECONSTRUCTION_SEAM = EXISTS
  DURABLE_BACKEND                   = NOT_ESTABLISHED
  STATE_RESET_WITHOUT_ROOT          = FAIL_CLOSED

REPOSITORY MERGE ENFORCEMENT:
  NOT_ACTIVE
```

## 20. Acceptance criteria for implementation planning

This design is ready for implementation planning only after human review confirms:

1. Plane semantics M1-M4 are correct and non-overlapping with Tier 1-4 persistence semantics.
2. Scheduler has no positive authority path.
3. Exact integer fixed-point arithmetic, normalization, floor division, and tie-break are deterministic and canonical.
4. Baseline and reality snapshot digests are semantically distinct.
5. Claim-level morphism transport is evidence-bound and cannot use semantic similarity as authority.
6. Builder/Falsifier/Reviewer state isolation is correctly captured.
7. No direct `M4 -> M2` promotion exists.
8. Replay preserves evidence but never automatically repeats an already consumed side effect.
9. Durable persistence remains explicitly unestablished.
10. Repository-wide merge enforcement remains explicitly inactive until independently verified otherwise.
11. The 24 RED falsifiers are sufficient as the first implementation contract.
