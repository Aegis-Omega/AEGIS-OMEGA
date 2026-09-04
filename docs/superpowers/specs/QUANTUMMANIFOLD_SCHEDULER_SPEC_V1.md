# QUANTUMMANIFOLD_SCHEDULER_SPEC_V1

Status: **DESIGN_SPEC / IMPLEMENTATION_OPEN**  
Architecture: **AEGIS Thread-as-QuantumManifold Core v0.1**  
Repository: `Aegis-Omega/AEGIS-OMEGA`  
Design base: `6eb2ac201bbe60ebaa9cebad714b8696683772e8`  
AEGIS Master Notebook v0.4 baseline digest: `457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404`

## 0. Epistemic status and authority boundary

This document is a normative design specification. It does **not** claim that the QuantumManifold Scheduler, role-isolation envelopes, replay protections, durable M1 persistence, or repository-wide merge enforcement are currently active on `main`.

At the design base, the authoritative implementation status is:

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

The scheduler is never an authority source.

```text
SchedulerScore(A) != Authority(A)
SchedulingReceipt.authority_effect = NONE
RoleResultReceipt.authority_effect = NONE
Final positive execution authority = Automaton-3 only
```

No semantic similarity, model agreement, scheduler score, prose confidence, role consensus, memory continuity, or graph centrality may transport or increase epistemic authority.

The system-wide weakest-link invariant is:

\[
A(C) \le \inf_i A(T_i),
\]

where `C` is a claim and `T_i` are all mandatory verified transitions required to establish it. If any mandatory transition is `OPEN`, `NOT_ESTABLISHED`, invalid, stale, or missing, the downstream claim cannot be promoted across that gap.

## 1. Plane Architecture M1-M4

The manifold architecture uses **Plane** terminology to avoid collision with the existing Tier 1-4 persistence/compaction architecture.

### M1 — History Plane

`M1` is append-only historical state. It preserves:

- events;
- claim versions;
- evidence roots;
- scheduling receipts;
- execution/denial receipts;
- falsified threads;
- stale results;
- invalid attempts;
- rebase records;
- admission outcomes.

Falsification never erases history.

### M2 — Reality Plane

`M2` is the currently admissible projection of `M1` under the active evidence and policy state.

\[
G_t = P_{\mathrm{admissible}}(G_{\mathrm{history}}).
\]

`M2` contains the active typed graph `G_t`, active threads `Γ_t^active`, and open obligations `O_t`.

### M3 — Verification Plane

`M3` contains deterministic verification and scheduling operators. It:

1. validates exact-head coordinates and digests;
2. validates the typed DAG;
3. computes obligation centrality;
4. computes information gain, closure leverage, falsification value, and cost;
5. ranks candidate actions deterministically;
6. emits a `SCHEDULING_RECOMMENDATION` only.

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

Unknown node types are invalid and fail closed.

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
\gamma \in \Gamma_{\mathrm{history}}
\]

may remain true while:

\[
\gamma \notin \Gamma_t^{\mathrm{active}}.
\]

A valid falsification changes the admissible projection, not the historical record.

## 3. Coordinate fixation and canonical digests

Every scheduling computation is bound to a concrete tuple:

\[
(H_t, D_B, D_{G_t}, D_{O_t}, D_{A_t}, D_{\Pi}),
\]

where:

- `H_t` = exact `source_head_sha`;
- `D_B` = immutable v0.4 `baseline_digest`;
- `D_Gt` = `reality_snapshot_digest`;
- `D_Ot` = `obligation_set_digest`;
- `D_At` = `candidate_set_digest`;
- `D_Π` = `scheduler_policy_digest`.

The baseline digest and reality snapshot digest are distinct concepts and must never be conflated.

```text
baseline_digest         = immutable research-control baseline identity
reality_snapshot_digest = digest of the concrete active G_t snapshot
```

The `source_head_sha` must be the actual commit coordinate from which the relevant graph/evidence state was constructed. A historical proof head such as `99d3700c2d5a2aab73a756109dda80de439d1baa` is valid only when the scheduler is explicitly operating on evidence bound to that head.

## 4. Deterministic fixed-point scheduler

### 4.1 Numeric representation

All serialized scheduler metrics and policy coefficients use integer fixed-point representation with scale `10^6` (`ppm`). Floating-point values are forbidden in canonical scheduling receipts.

The serialized safe domain is:

\[
0 \le x \le 9{,}007{,}199{,}254{,}740{,}991.
\]

Any underflow into forbidden negative domains, overflow, non-integer value, NaN-equivalent source, or loss of exact integer representation fails closed.

### 4.2 Obligation centrality

For open obligation `o_k`, define downstream terminal influence:

\[
\operatorname{centrality}(o_k)
=
\sum_{c \in D(o_k)} w_c\,\mathbf 1[c\text{ depends on }o_k],
\]

where `D(o_k)` is the set of active downstream claim/terminal nodes and `w_c` is a policy-bound claim priority.

The canonical implementation must use a deterministic normalized integer representation.

### 4.3 Closure leverage

For candidate action `A`:

\[
L(A)=
\sum_{o_k \in O_t}
p_{\mathrm{close}}(o_k\mid A)\,
\widehat{\operatorname{centrality}}(o_k).
\]

`p_close` is not epistemic authority. It is a scheduling prior encoded in the policy-bound scoring input and must be auditable as such.

### 4.4 Falsification value

\[
F(A)=
\sum_{\gamma\in\Gamma_t^{\mathrm{active}}}
p_{\mathrm{falsify}}(\gamma\mid A)\,
V_{\mathrm{pruned}}(\gamma).
\]

`V_pruned` estimates avoidable future compute/evidence work if a thread is legitimately falsified. It is an optimization quantity, not a scientific truth value.

### 4.5 Information gain and cost

The v0.1 scoring function is:

\[
S(A)=
\frac{
\alpha\,IG(A)+\beta\,L(A)+\gamma\,F(A)
}{
\varepsilon+C(A)
},
\]

with:

\[
C(A)=
C_{\mathrm{compute}}
+\mu C_{\mathrm{evidence}}
+\eta C_{\mathrm{latency}}.
\]

Constraints:

```text
alpha, beta, gamma, mu, eta >= 0
epsilon > 0
```

All coefficients are part of the canonical scheduler policy and therefore covered by `scheduler_policy_digest`.

### 4.6 Deterministic tie-breaking

For equal `ranking_score_ppm`, actions are ordered by:

1. larger `closure_leverage_ppm`;
2. larger `falsification_value_ppm`;
3. smaller `cost_ppm`;
4. lexicographically smaller lowercase `candidate_action_digest` using ASCII order.

Equivalent ordering key:

```text
(-S, -L, -F, C, candidate_action_digest)
```

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

Builder may inherit constructive continuity needed to continue the active branch:

- exact head;
- baseline/reality digests;
- active thread lineage;
- admitted evidence;
- previous Builder continuation state;
- implementation/proof artifacts;
- open obligations.

Builder prose confidence, model self-assessment, and scheduler ranking do not carry authority.

Builder output is a candidate delta only.

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

Reviewer receives reconstructed machine evidence only:

- canonical claim AST/statement;
- dependency DAG;
- exact source head;
- compiler/Coq/test outputs;
- verification receipts;
- raw-data digests where relevant;
- assumptions inventory;
- falsifier outcome receipt;
- applicable policy digest.

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
M_4 \not\rightarrow M_2.
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

`STALE` is not equivalent to `INVALID`.

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

```text
STALE != INVALID
```

### 11.4 DENY / ADMIT

Only the Automaton-3 authority boundary may issue execution `DENY` or `ADMIT`.

## 12. Replay and side-effect safety

### 12.1 Evidence reconstruction replay

Replay may deterministically reconstruct:

\[
M_1 \rightarrow G_t \rightarrow \mathcal A_t \rightarrow \text{SchedulingReceipt}.
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
D_{\mathrm{intent}}
=H(\operatorname{JCS}(H_t,D_{G_t},D_A,D_{role},n_{attempt})).
\]

A previously consumed execution intent may not execute again.

```text
EXECUTION_INTENT_REPLAY -> BLOCK
```

A legitimate repeated experiment/test requires a new monotonic `attempt_sequence` and a new Automaton-3 authorization decision.

Invariant:

```text
EVIDENCE_RECONSTRUCTION_REPLAY = ALLOWED
SIDE_EFFECT_AUTO_REPLAY        = FORBIDDEN
```

## 13. Persistence and recovery boundary

The repository already contains a deterministic ledger serialization/reconstruction seam, but that seam is not itself a durable database backend. QuantumManifold v0.1 must not claim durable crash-safe runtime persistence until a storage backend and restart recovery path are separately implemented and verified.

Recovery invariants are:

\[
D_{G_t}^{\mathrm{replayed}} = D_{G_t}^{\mathrm{recorded}}
\]

and

\[
D_{sched}^{\mathrm{replayed}} = D_{sched}^{\mathrm{recorded}}.
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
\mathrm{SchedulerScore}(A) \not\Rightarrow \mathrm{Authorized}(A).
\]

### T2 — Deterministic Scheduling Reproducibility

Given identical canonical `(G_t, policy, candidate set)` inputs, integer fixed-point arithmetic, and a total deterministic tie-break order, the selected action is unique. With deterministic canonical serialization, the scheduling receipt is byte-identical.

### T3 — Stale-Result Isolation

If a result returns bound to an old `(source_head_sha, reality_snapshot_digest, obligation_digest)` coordinate, it remains historical in `M1` and is excluded from current `M2` until a verified rebase occurs.

### T4 — Falsification Preservation

Removing a falsified thread from `Γ_t^active` does not remove it from historical lineage. Therefore falsification reduces active search support without destroying provenance.

### T5 — Replay Effect Safety

A consumed `execution_intent_digest` cannot execute twice under the same attempt identity, while deterministic evidence replay remains allowed. Therefore evidence replayability and effect non-replayability can coexist.

### T6 — Role Prose Isolation

Because the Falsifier and Reviewer input domains exclude Builder continuation/prose and cross-role authoritative joins are digest-only, Builder persuasive prose cannot be an authorized cross-role state-transition carrier.

### T7 — Weakest-Link Authority Bound

If any mandatory transition required for claim `C` remains `OPEN`, `NOT_ESTABLISHED`, invalid, or missing, `C` cannot be promoted above that weakest required transition.

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
| `QM-RED-011` | Negative/non-integer/overflow ppm value | `FIXED_POINT_DOMAIN_ERROR` or `SCORE_RANGE_EXCEEDED` |
| `QM-RED-012` | `epsilon <= 0` | `INVALID_STABILIZER` |
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
2. fixed-point scoring and deterministic ranking;
3. scheduling receipt creation/verification;
4. role context envelope creation/verification;
5. stale/rebase validation;
6. replay intent protection;
7. coordinator integration that preserves Automaton-3 as the only positive authority source;
8. RED/GREEN test and CI lanes.

The implementation should follow existing repository patterns and avoid replacing the coordinator authority boundary. Existing `agents/coordinator.py` remains the positive-authority choke point unless a separately approved architecture change replaces it.

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
- production-grade cost calibration for `IG`, `L`, `F`, or `C` priors.

## 18. Repository enforcement status

At the design base:

```text
FAIL_CLOSED_VERIFIER_LOGIC    = EXISTS IN BOUNDED SURFACES
EXACT_HEAD_PROOF_GATES        = EXISTS IN BOUNDED SURFACES
PR407 CLAIM PROMOTION GATE    = MACHINE_TESTED ON ITS EXACT HEAD
REPOSITORY_MERGE_ENFORCEMENT  = NOT_ACTIVE
GLOBAL_FAIL_CLOSED_ADMISSION  = NOT_ESTABLISHED
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
  FIXED_POINT_DETERMINISTIC_SCORING
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
3. Fixed-point scoring and tie-break are deterministic and canonical.
4. Baseline and reality snapshot digests are semantically distinct.
5. Builder/Falsifier/Reviewer state isolation is correctly captured.
6. No direct `M4 -> M2` promotion exists.
7. Replay preserves evidence but never repeats an already consumed side effect automatically.
8. Durable persistence remains explicitly unestablished.
9. Repository-wide merge enforcement remains explicitly inactive until independently verified otherwise.
10. The 24 RED falsifiers are sufficient as the first implementation contract.
