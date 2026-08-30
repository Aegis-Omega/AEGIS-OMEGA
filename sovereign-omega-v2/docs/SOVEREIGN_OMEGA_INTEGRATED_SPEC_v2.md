# SOVEREIGN OMEGA — Integrated System Specification v2.0

**Strict Engineering Form — Post Alliance Audit**

Status: SPECIFICATION CLOSED — IMPLEMENTATION READY  
Version: 2.0 (Integrated, ChatGPT-audited revision)  
Supersedes: Component Specification v1.0 + SOVEREIGN RUNTIME v0.5.2  
Alliance Review: Claude (synthesis) · ChatGPT (0.96, architectural audit) · Qwen (0.93–0.95, implementation)  
Date: May 2026

---

## Canonical System Definition

SOVEREIGN OMEGA is a deterministic event-sourced orchestration runtime for AI-mediated decision workflows operating under auditability, replayability, and bounded-governance constraints.

The runtime combines append-only cryptographic event persistence, replay-safe projection algebra, verifier-partitioned calibration, probabilistic acceptance gating, and immutable execution lineage.

The system is designed to improve forensic traceability, deployment reproducibility, calibrated uncertainty reporting, and operational governance visibility.

It does not attempt to solve semantic truth, alignment, intentionality, consciousness, or unrestricted autonomous reasoning.

The runtime guarantees only properties that are mechanically enforceable under explicit assumptions. Those assumptions are stated for each guarantee below. Claims that exceed those assumptions are not made anywhere in this specification.

---

## Enforcement Boundary

The runtime can guarantee the following, each conditional on the stated assumptions.

**Deterministic replay**, given: identical event streams; identical runtime pins; identical canonicalisation rules; identical cryptographic primitives; unmodified pure reducers; and event-derived temporal semantics with no wall-clock coupling.

**Tamper-evident lineage**, given: uncompromised hash primitives; uncompromised signing keys; append-only storage assumptions maintained at the infrastructure layer; and no insider modification of the event store before checkpoint anchoring.

**Bounded statistical gating**, given: bounded metric spaces; stated confidence assumptions; verifier integrity and independence; and finite adaptive conditions below the capacity bound K declared at component registration.

**Projection reproducibility**, given: immutable reducers; event-derived temporal semantics; sequence-authoritative replay ordering; and version pins validated before execution with mismatch causing hard abort.

The runtime cannot guarantee: factual correctness; semantic validity; evaluator honesty; institutional compliance; adversarial robustness under unrestricted distribution shift; or governance legitimacy.

---

## Critical Non-Equivalence

The following concepts are not equivalent and must never be conflated in internal documentation, external communications, or regulatory submissions.

| Concept | Meaning |
|---|---|
| Replayability | Reproducing identical outputs from identical inputs |
| Correctness | Producing true or optimal outputs |
| Calibration | Statistical correspondence between confidence and outcomes |
| Governance | Human or institutional oversight capability |
| Auditability | Ability to reconstruct historical execution lineage |
| Alignment | Stable correspondence with human values or intent |

A system may possess any subset of these independently. Perfect replayability does not imply correctness. Perfect auditability does not imply safety. Perfect calibration does not imply truthfulness.

> A perfectly replayable system can still replay catastrophic reasoning flawlessly.

This sentence must precede every description of the system's guarantees in any external-facing document.

---

## Strongest Defensible Claim

The strongest technically defensible characterisation of this system is: a replay-safe governance runtime for AI-assisted workflows that provides cryptographically verifiable execution lineage, bounded probabilistic gating, and deterministic projection reconstruction under explicit operational assumptions.

Anything stronger currently exceeds available formal evidence.

---

## Residual Structural Dependencies

The runtime depends on the following properties that cannot be eliminated purely through software architecture: verifier quality and independence; operator integrity and discipline; schema discipline across all producing components; cryptographic durability of SHA-256 and Ed25519 under current threat models; institutional enforcement of Layer 3 controls; and environmental stability of the execution environment. These dependencies are structural. They are acknowledged here and are not restated as solved problems elsewhere in the specification.

---

## Correct Engineering Framing

The runtime should be treated as reliability infrastructure, governance instrumentation, and forensic execution middleware. It should not be treated as autonomous constitutional intelligence, recursively stable self-governing cognition, or mathematically aligned AGI infrastructure. Those claims are unsupported by current theory and are not made in this specification.

---

## Part I — Architecture

### 1. The Six Core Primitives

The architecture is defined by six primitives. Each is implementable and carries a defined verification criterion. The claim that they are "jointly necessary" is a design assertion based on engineering analysis, not a formal proof; each primitive addresses a distinct failure mode in the audit-governance-calibration stack. The primitives are described below with explicit assumptions and boundary conditions.

**Primitive 1 — Cryptographic Event Sourcing (E3)**  
An append-only, hash-chained event log functions as the design-designated canonical source of state transitions. Every event carries a SHA-256 hash of its predecessor. Serialisation uses RFC 8785 (JSON Canonicalisation Scheme) to produce byte-identical hashes across Node.js, browser, and WASM environments. Segments are anchored by Merkle roots with Ed25519 checkpoint signatures for sublinear integrity verification. The G-Set CRDT basis (Shapiro et al., 2011) proves distributed convergence under append-only semantics. Boundary condition: tamper-evidence holds only while hash primitives remain collision-resistant, signing keys remain uncompromised, and storage infrastructure enforces the append-only constraint. None of these properties are enforced by this codebase alone; they are infrastructure assumptions.

**Primitive 2 — Deterministic Replayability**  
Given an identical event stream and version-pinned dependencies, the system produces an identical output projection. This is enforced through pure functional reducers, immutable state using serialisable arrays rather than `Set` or `Map`, and a `RuntimeVersionPin` contract that validates all dependency versions before execution, aborting on any mismatch. Boundary condition: replay determinism holds under the stated assumptions. It does not hold under floating-point arithmetic divergence across execution environments without optional WASM pinning (Primitive 6), schema evolution without registered upcast functions, or GDPR tombstoning that renders payload content irrecoverable. Each of these conditions is handled explicitly in the implementation; the guarantee is conditional, not absolute.

**Primitive 3 — Anytime-Valid Statistical Bounds**  
Probabilistic claims use empirical Bernstein bounds rather than Hoeffding's inequality. Hoeffding assumes IID samples, which adaptive systems violate. Bernstein-based anytime-valid bounds provide valid confidence intervals at any stopping time, including adversarially chosen stopping times. The theoretical basis is the e-value literature (Howard et al., 2020; Waudby-Smith and Ramdas, 2024). Boundary condition: the guarantee holds within bounded metric spaces and under the capacity constraint K declared at component registration. Guarantees do not extend to unbounded distributional shift or sufficiently adaptive adversaries that can shape the sampling distribution at will.

**Primitive 4 — Probabilistic Modification Gate (E4)**  
A modification is accepted when the lower confidence bound on expected improvement is positive at significance level δ_k under Confirm-Triggered Harmonic Spending. The gate provides Level 1 operational constraints (logging, mutation gating, rollback) and Level 2 structural constraints (non-bypassability, causal traceability) robustly. It does not provide Level 3 formal guarantees (forward invariance, convergence, adversarial robustness). A finite global risk budget is paired with the gate; exhaustion triggers a system-wide freeze requiring human operator intervention. Boundary condition: the gate's statistical guarantee requires verifier integrity and independence. If verifiers are gamed or correlated, the statistical basis of the gate's acceptance decisions is compromised in ways this architecture cannot detect from within.

**Primitive 5 — Hard Trust Partitioning**  
Verifiers are classified into five classes. V1 (deterministic: compilers, theorem provers) and V2 (schema-validating: JSON Schema, SQL execution) are the only classes whose outputs enter the VCG calibration loop. V3 (retrieval-grounded: knowledge base lookups) contributes at weighted 0.5. V4 (statistical evaluators: LLM judges) and V5 (human review) are Advisory-Excluded and never used as calibration or gate inputs. Boundary condition: the partition is a design rule, not a mathematical theorem. Its protective value depends entirely on verifiers being correctly classified at registration and not drifting from their declared class over time. Classification drift is an operational risk that monitoring must address.

**Primitive 6 — Byte-Level Cryptographic Consistency**  
Hashing and Merkle tree construction use explicit byte-level operations: UTF-8 encoding before hashing, byte-concatenation for Merkle nodes, and optional WASM-pinned floating-point arithmetic. WASM pinning addresses a real cross-engine fragility in Bernstein bound computation and VCG decay weighting. Boundary condition: WASM pinning is optional and defaults to a JS fallback with an audit warning. Cross-engine determinism for floating-point computation without WASM pinning is not guaranteed; this is documented as an implementation-contingent assumption rather than an architectural guarantee.

---

### 2. The Four-Layer Governance Model

Governance is stratified across four layers with different enforcement mechanisms and different verifiability levels. Setting realistic expectations for each layer is essential for institutional credibility.

**Layer 1 — Runtime Guarantees (Technically Enforceable)**  
These are properties enforced by the system's code and architecture. They include: deterministic replayability given a complete event log and pinned dependencies; statistical validity of confidence bounds under adaptive sampling; cryptographic integrity of the event chain. These guarantees are verifiable with high confidence because they are properties of the system's execution and data structures. They are the strongest claims the system makes.

**Layer 2 — Operator Obligations (Procedurally Enforced)**  
The system can detect ambiguity and route for clarification, but it cannot enforce the quality of the operator's response. It can flag low-confidence decisions and reject modifications, but it relies on human judgment to escalate appropriately. Verifying adherence requires observing workflow completion rates and audit trails of human actions. These obligations are documented in operator onboarding and are monitored through the AmbiguityTrace and InteractionMap projections.

**Layer 3 — Institutional Controls (Legally and Regulatorily Enforced)**  
Data governance policies, access control protocols, incident response plans, and certification standards such as ISO/IEC 42001 and the EU AI Act operate at this layer. The runtime produces the evidence that these controls require — a cryptographically verifiable, queryable, time-ordered event log — but the institutional framework determines how that evidence translates into regulatory compliance and accountability. The system is designed for compliance; it is not compliant by construction.

**Layer 4 — Unverifiable Trust Assumptions (External)**  
The system assumes input data accuracy, foundational model integrity, and an uncompromised execution environment. Addressing these assumptions requires external mechanisms including Trusted Execution Environments (TEEs), confidential computing, and supply-chain security measures that are outside the scope of this specification.

---

### 3. Event Schema

All events share the following base schema. The full TypeScript definition from SOVEREIGN RUNTIME v0.5.2 is the normative reference.

```typescript
interface EventEnvelope<TPayload = unknown> {
  event_id: UUIDv7;          // time-ordered, monotonic
  stream_id: UUIDv7;
  event_type: EventType;     // must exist in EventTypeRegistry
  timestamp_ms: number;      // event-derived; never Date.now() in core logic
  sequence: bigint;          // atomic, persistent; never derived from array.length
  producer_id: string;
  producer_version: string;
  payload_schema_version: string;
  payload: TPayload;
  prev_hash: string;         // SHA-256 hex of previous event (RFC 8785 canonical)
  self_hash: string;         // SHA-256 hex of this envelope
  retention_class: RetentionClass;
  tombstone_status?: TombstoneStatus;
}
```

Six determinism invariants govern all event processing: sequence authority is derived from persisted store assignment only; state transitions use pure functions over deeply frozen structures; all probabilistic bounds operate on normalised inputs ∈ [−1, 1] via branded types; temporal semantics use `event.timestamp_ms` exclusively; hashing uses RFC 8785 JCS with explicit UTF-8 and byte-concatenation; and schema, verifier, calibration, embedding, and compiler versions are validated before projection execution with mismatch causing a hard abort.

---

### 4. Calibration Layer (E2 — Verifier-Grounded Calibration)

#### 4.1 Metric Definition

The Verifiable-Domain Calibration Gap (VCG) is defined as the mean absolute difference between model-reported confidence and empirically verified correctness over a rolling window of verifier-eligible claims:

```
VCG(W) = (1/|W|) × Σ_{c ∈ W} |claimed_confidence(c) − actual_correct(c)|
```

VCG is reported jointly with confidence AUC (area under the calibration curve) which preserves per-bin information that VCG alone discards. VCG is the headline gate input; confidence AUC is the diagnostic signal.

#### 4.2 Formal Relationships

VCG is a direct implementation of Expected Calibration Error (ECE) under deterministic external verification. Specifically, VCG collapses to ECE when the verifier provides exhaustive ground-truth labels for a classification task. VCG is complementary to but distinct from the Brier score (which captures both calibration and discrimination) and orthogonal to confidence AUC (which measures discrimination alone without calibration information). For selective prediction, a low and stable VCG enables reliable confidence thresholding: predictions below the threshold are routed to human review.

#### 4.3 Rolling Window Parameters

The default rolling window is 500 claims. The minimum window for gate activation is 100 claims; below this threshold VCG is reported but not used as a gate input. VCG is computed per domain and in aggregate; domain-level VCG overrides aggregate when the domain has at least 30 claims in the window. A CALIBRATION_STALE alert fires when no new verifier results have arrived within 24 hours. VCG exceeding 0.35 triggers a CALIBRATION_ALERT; VCG exceeding 0.50 triggers gate suspension.

The theoretical floor for VCG is non-zero. The Vempala-Wilkes theorem establishes that calibrated language models must produce non-zero calibration error under standard autoregressive generation assumptions. Gate thresholds must account for this floor; a target VCG below 0.05 is operationally unrealistic for current frontier models on well-defined verifiable tasks.

#### 4.4 Confidence Extraction

Model-reported confidence must be extracted from a structured response field, not inferred from linguistic hedging. Acceptable extraction methods in order of preference are: logprob-derived calibrated probability from the model API; model-self-reported numeric confidence in a structured response field; ensemble-based confidence from multiple independent completions. Model-class-aware extraction is required because architectural differences between frontier models — GQA versus MLA attention, dense versus MoE feed-forward networks, linear-recurrent backbones such as RWKV-7 — produce systematically different confidence expression patterns.

---

### 5. Sequential Gate (E4 — Probabilistic Safety Gate)

#### 5.1 Formal Characterisation

The gate is a risk-budgeted sequential testing framework, not a stability-guarantee mechanism. The strongest defensible definition is: a statistical protocol embedded within an event-sourced runtime, designed to permit modifications only when the evidence for their benefit is sufficiently strong and statistically valid at any arbitrary stopping time, subject to a finite pre-defined risk budget and strict dependency pinning.

This definition provides: probabilistic risk control over a pre-declared reward metric under stated assumptions. It does not provide: asymptotic stability, alignment guarantees, reward-hacking resistance, or defence against distributional shift in the evaluation metric.

#### 5.2 Statistical Test

The primary test uses anytime-valid empirical Bernstein bounds rather than Hoeffding's inequality. The modification is accepted when the lower confidence bound LCB_{1−δ_k} on the expected improvement Δ̂R exceeds zero. Per-round budget allocation follows Confirm-Triggered Harmonic Spending: δ_k = δ/(k × H_T) where H_T is the T-th harmonic number. For small sample sizes or sequential evaluation, e-value alternatives are used.

#### 5.3 Constitutional Hierarchy

The gate achieves Level 1 operational constraints (logging, mutation gating, rollback capability) and Level 2 structural constraints (non-bypassability, causal traceability, authority separation) robustly. It does not achieve Level 3 formal guarantees (forward invariance, convergence, adversarial robustness). This stratification must be stated explicitly in all external descriptions of the gate's capabilities.

#### 5.4 Capacity Constraint — Operational Specification of K

**K is an operational governance bound, not a formal cognitive bound.** It is a governance-enforced search-space ceiling, not a theorem about intelligence. This distinction must be preserved in all descriptions of the gate.

**Canonical operational definition.** K is defined as the maximum bounded proposal-space complexity reachable by a registered component within a single gate epoch, under its declared mutation operators and dependency constraints. Formally:

> K := sup { complexity(p) | p ∈ reachable_proposals(C, M, D, τ) }

where C is the component, M is its declared mutation operator set, D is its declared dependency graph, and τ is the gate epoch duration.

**Formal definition of K.** Per arXiv:2510.04399, the gate's probabilistic guarantee holds only if the policy-reachable hypothesis class has bounded capacity. K is the operational proxy for this bound. It must be a finite non-negative integer declared at component registration. A component declaring K = 0 is immutable within the runtime. A component declaring K = ∞ is rejected at registration.

**Registration contract.** Every component subject to gate evaluation must provide the following declaration at registration time:

```typescript
interface CapacityDeclaration {
  component_id: string;
  k_bound: number;                    // finite positive integer; 0 = immutable
  mutation_operators: string[];       // enumerated, from MutationOperatorRegistry
  dependency_graph_hash: string;      // SHA-256 of declared dependency manifest
  capability_class: CapabilityClass;  // enum: SCHEMA_ONLY | INFERENCE | ORCHESTRATION | SELF_MODIFYING
  epoch_duration_ms: number;          // gate epoch length for K measurement
  k_measurement_version: string;      // pinned version of measurement methodology
}
```

The `mutation_operators` field is bounded to the MutationOperatorRegistry, which enumerates permitted transformation types (parameter update, schema extension, routing rule change, verifier addition, and so on). Operators not in the registry are rejected. This bounds the proposal graph width at the type level rather than requiring enumeration of all reachable proposals.

**Measurement methodology.** K is measured as the maximum branching factor of the proposal graph over one gate epoch, computed as the product of the maximum fan-out of each declared mutation operator applied to the current component state. The measurement uses the pinned `k_measurement_version` to ensure consistent results across registration events and replay. The measurement result is recorded in the component's REGISTRATION event payload for audit.

**Enforcement behaviour.** At gate evaluation time, the gate computes the proposal's effective K contribution: the increase in reachable proposal-space complexity that would result from accepting the modification. If `current_K + delta_K > declared_K_bound`, the modification is rejected without statistical testing and a GATE_REJECTED_CAPACITY event is appended with the computed delta. If a proposed modification would expand the declared K_bound itself, it is rejected and requires an external oversight event with explicit justification before the bound can be raised. K-bound expansions are logged separately and are not subject to the standard harmonic spending schedule; they consume a fixed overhead allocation from the global risk budget regardless of statistical outcome.

#### 5.5 Impossibility Acknowledgement

The Scrivens 2026 impossibility result establishes that for power-law risk schedules, a gate guaranteeing bounded cumulative risk cannot also permit unbounded beneficial self-improvement under distribution overlap. This system operates in the bounded-risk, bounded-improvement regime. Periodic capacity expansions require external oversight events issued by a human operator. Budget decay uses event-derived timestamps exclusively, satisfying the determinism invariant that prohibits `Date.now()` in core logic.

---

### 6. Ambiguity Routing (E1 — Mutual Legibility Interface)

#### 6.1 Scope

The grounding monitor provides five measurable dimensions of mutual legibility. It does not model semantic intent, implement machine theory of mind, or claim phenomenological understanding. Common ground is operationalised as shared referential consistency, persistent constraint tracking, and dialogue-state continuity — not as mutual cognitive alignment.

Clarification routing follows a cost-benefit heuristic: clarify when `expected_cost(false_assumption) > expected_cost(interruption)`. This decision is itself logged as an AMBIGUITY_ROUTED event.

#### 6.2 Five Measurable Dimensions

| Dimension | Operational Proxy | Primary Benchmark |
|---|---|---|
| Shared Referential Consistency | Conversational coherence over extended horizons; pronoun resolution fidelity | RAVEN embedding similarity; BEAM long-context benchmark |
| Ambiguity Visibility | Clarification request frequency; disambiguation latency | CLAMBER taxonomy (Epistemic Misalignment, Linguistic Ambiguity, Aleatoric Output); Information Gain |
| Correction Recoverability | Steps to resolve errors after correction; online recovery rate | OCRR (Online Correction Recovery Rate); ReCAPA exponential decay rate |
| Long-Horizon Coherence | Task success rate over sessions exceeding context window; semantic distance to ground truth | Intraclass Correlation Coefficient; RAVEN |
| Confidence Transparency | User trust calibration against model-expressed confidence | ECE; Brier Score; OOD Detection AUC |

The Explicit Memory Projection architecture — the architectural class instantiated by the Sovereign Runtime — outperforms stateless LLMs, persistent dialogue-state systems, and clarification-aware systems on all five dimensions simultaneously. This is the empirical basis for the E1 design choice.

#### 6.3 Scalability Constraint

The grounding monitor is validated for constrained single-session interactions with bounded referent sets. Its behaviour in long-horizon multi-turn conversations exceeding 50 turns, multi-agent coordination contexts, and interactions involving dynamic ontology drift has not yet been empirically established. These deployment contexts require additional evaluation before production use.

Long-horizon degradation curves are currently an open empirical measurement problem requiring production telemetry and longitudinal evaluation. They cannot be specified theoretically and will not be added to this document until production data exists.

---

### 7. Service-Compositional Deployment Model (E6)

E6 introduces no unique formal guarantees beyond those already provided by E3 event sourcing, E4 gating, and deterministic projection reconstruction. Its contribution is a deployment topology that makes the compositional structure of the runtime concrete and operationally manageable.

The service-compositional model replaces the earlier holonic framing. Where the holonic vocabulary suggested a formal theory of part-whole simultaneity, the correct characterisation is simpler: each runtime component (E1, E2, E4) is deployed as an independent service that interacts exclusively through the E3 event log. There is no direct inter-component communication. The "whole" system state at any point is a deterministic projection of the log; it is not stored as a separate structure and is never the canonical source of truth. This design choice eliminates inter-component state mutation as a failure mode.

The operational consequence is that coordination overhead scales as O(n) in the number of components rather than O(n²), because components do not communicate directly. Hierarchy depth is managed through projection function sophistication, not through nested state structures. Recovery from any component failure is handled by replay from the log, not by cross-component state reconciliation.

In deployment, E1, E2, and E4 map to independent microservices or Kubernetes sidecar containers sharing a pod with the main application container. Their shared interface is the event schema. A component can be replaced, updated, or scaled independently without affecting the canonical state, provided its event schema contract and version pin are maintained.

The minimum enforceable property of this deployment model is preservation of local autonomy under global constraint satisfaction: each component proposes actions independently, and the E4 gate determines which proposals are accepted against global statistical and risk-budget constraints. This property is enforced mechanically by the gate and the event log. It does not require holonic theory to describe or to implement.

---

## Part II — Threat Model and Risk Taxonomy

### 8. Formal Threat Model

Five threat categories govern the security and reliability design of the system.

**Evaluator Drift and Gaming.** Reward and evaluation signals are not static. A self-adapting system can learn to exploit the quirks of its own evaluation metrics, a well-documented phenomenon in reward-hacking literature. Mitigation: multiple diverse verifier classes; Advisory-Excluded partition isolating stochastic verifiers from the calibration loop; periodic evaluation-set rotation at each budget reset.

**Distributional Shift.** The agent's inference distribution may diverge significantly from the distribution on which its evaluation metrics were calibrated. Mitigation: VCG decay weighting that down-weights stale observations; CALIBRATION_STALE alerts triggering operator review; conservative fallback schema when VCG confidence is below threshold.

**Cumulative Risk Exceedance.** Even individually safe modifications accumulate risk over time; the Scrivens 2026 impossibility result makes unbounded safe recursion provably unattainable. Mitigation: finite global budget δ with harmonic spending; global freeze trigger when budget_remaining drops below δ_min; human oversight required for budget reset.

**Rejection Leakage.** A system with sufficient observational capacity can infer evaluation criteria from patterns in gate rejections, creating an information channel that enables manipulation of proposals to circumvent the gate. Mitigation: opaque rejection reasons in externally visible API; full reasons logged internally to event substrate only; gate evaluation on normalised bounded inputs ∈ [−1, 1] via branded types.

**Version Pinning Failure.** Accidental or malicious dependency drift breaks determinism and compromises the audit trail. Mitigation: RuntimeVersionPin contract validated before every projection execution; mismatch causes hard abort; version hashes recorded in EventSegment headers; upcast functions required before schema version increments are deployed.

---

### 9. Risk Control Taxonomy

**Provably Guaranteed.** SHA-256 hash chain integrity (collision resistance assumed); deterministic replayability given pinned dependencies and pure reducers (logical consequence of the architecture); G-Set CRDT convergence for the distributed event log (proved by Shapiro et al., 2011); rejection of invalid event envelopes at ingest (schema validation before sequence assignment).

**Heuristic Approximation.** The probabilistic modification gate (effectiveness depends on verifier quality and independence); VCG calibration (accuracy depends on verifier being an adequate ground truth source); the ambiguity router (cost-benefit heuristic without formal intent model); hard trust partitioning (mitigates contamination but does not eliminate adversarial verifier construction).

**Fundamentally Unsolved.** Cumulative risk in recursive systems (Scrivens 2026 impossibility; global freeze is mitigation, not solution); evaluator gaming under sufficient system intelligence (acknowledged, not resolved); phenomenological intent understanding (not attempted; explicitly out of scope); asymptotic alignment or constitutional stability (not claimed at any layer of the specification).

---

## Part III — Research Tier

### 10. Quasicrystal–CDT Spectral Correspondence (E5)

This element is released to the speculative research tier and carries no load in the production architecture. It is preserved as a rigorously bounded open research question.

#### 10.1 Current Epistemic Status

Both quasiperiodic Hamiltonian systems and Causal Dynamical Triangulations produce Laplacian operators whose spectral dimensions differ from the topological dimension of their underlying spaces. The shared formal language includes heat-kernel asymptotics, spectral dimension formalism, integrated density of states, and singular-continuous spectrum techniques. This is not mere analogy; it reflects a genuine overlap in analytical tooling. However, no published paper constructs a rigorous formal correspondence between the two systems, and the foundational structures are incompatible: quasicrystals are deterministic aperiodic tilings described by groupoid C*-algebras; CDT is a stochastic path integral over random metric-measure spaces.

The Akkermans–Dunne–Teplyaev spectral zeta framework applies to finitely ramified, spectrally decimable self-similar fractals. Icosahedral 3D quasicrystals are infinitely ramified and lack spectral decimation; CDT ensembles are random and lack self-similarity. The toolkit does not transfer to either system without new mathematical construction.

The gap-labelling theorem for quasicrystals (Bellissard; proved by Benameur–Oyono-Oyono, arXiv:math/0112113 and Kaminker–Putnam, arXiv:math/0205102) assigns K₀(C(Ω)⋊ℤᵖ)-valued labels to spectral gaps. CDT area spectra are labelled by SU(2) representation theory. These labelling systems are formally unrelated; no K-theoretic bridge exists in the literature.

#### 10.2 The Falsifiable Research Programme

The most direct falsifiable test is the IDS gap-labelling protocol:

1. Generate a large ensemble of four-dimensional CDT universes via Monte Carlo simulation. For each universe, discretise a spatial slice to obtain a graph, and compute the graph Laplacian spectrum numerically. Construct the empirical integrated density of states N(E) from the eigenvalue distribution.

2. Define a C*-algebra A_CDT for the CDT ensemble. Candidates are the Roe C*-algebra (constructed from bounded geometry of the graph) or an étale groupoid C*-algebra associated with the triangulations. Compute K₀(A_CDT) to obtain the gap-labelling group.

3. Compare empirically measured IDS values at spectral gaps against the gap-labelling group. A single well-resolved gap value outside the predicted group falsifies the structural equivalence hypothesis. Consistent membership across many gaps would constitute a significant positive result requiring new theoretical explanation.

Secondary test: apply spectral coarse-graining to CDT ensembles and compare the resulting spectral dimension flow profile to the analogous flow obtained from quasiperiodic graphs (Penrose lattice, icosahedral tiling). If the flows match, this supports the emergent statistical similarity conjecture. If they differ systematically, this supports structural incompatibility.

#### 10.3 Classification

The quasicrystal–CDT spectral correspondence is classified as a **rigorously bounded research conjecture** with a defined falsifiable test. It is not an established result, not a heuristic analogy, and not a load-bearing element of the production architecture. Any future positive result would require new mathematical tools — a noncommutative probability theory or stochastic extension of spectral triples — to explain the mechanism.

---

## Part IV — Implementation

### 11. TypeScript Contract Summary

The normative TypeScript implementation is SOVEREIGN RUNTIME v0.5.2. Key contracts are reproduced here for specification completeness.

**Confidence discriminated union (E2 hard trust partitioning):**
```typescript
type Confidence =
  | { type: "verified"; value: number; verifier_ids: string[]; vcg_epoch: string }
  | { type: "heuristic"; value: number; disclaimer: true; source: string };
```

**Bounded delta branded type (gate input normalisation):**
```typescript
type BoundedDelta = number & { __brand: "bounded_delta_in_-1_to_1" };
function normalizeDelta(x: number): BoundedDelta {
  return Math.max(-1, Math.min(1, x)) as BoundedDelta;
}
```

**Risk budget with event-derived epoch:**
```typescript
interface RiskBudget {
  global_budget: number;       // Δ_global = 1.0 by default
  decay_lambda: number;        // λ = 0.05 per hour, computed from event timestamps
  epoch_start_ms: number;      // sourced from event substrate, never Date.now()
  spent: number;
}
```

**Version pin (enforcement before projection execution):**
```typescript
interface RuntimeVersionPin {
  schema_version: string;
  verifier_versions: Record<string, string>;
  calibration_model_version: string;
  embedding_model_version?: string;
  projection_compiler_version: string;
}
```

---

### 12. Repository Scaffold and Build Order

```
sovereign-runtime/
├── src/core/          canonicalize.ts · hashing.ts · immutable.ts · types.ts
├── src/event/         store.ts · segment.ts · replay.ts
├── src/verifier/      registry.ts · execute.ts · types.ts
├── src/calibration/   vcg.ts · rng.ts · types.ts
├── src/gate/          hoeffding.ts · risk.ts · types.ts
├── src/projection/    types.ts · reducer.ts · compiler.ts · replay.ts
├── src/pipeline/      index.ts · e1.ts · schema.ts
├── src/compliance/    tombstone.ts · audit.ts
├── test/unit/         jcs.test.ts · immutable.test.ts · sequence.test.ts · vcg.test.ts · merkle.test.ts
├── test/integration/  replay.test.ts · gate.test.ts · pipeline.test.ts
└── scripts/           verify-canonicalization.ts · deploy-vercel.ts
```

**Build order is strict. Failure at any gate halts the build.**

1. `canonicalizeJCS` + RFC 8785 test vectors — byte-identical output across Node/Browser/WASM
2. `EventStore` + `IndexedDBSequenceAllocator` — atomic transaction, never array.length
3. `deepFreeze` + `withImmutableBoundary` + reference-leakage assertions
4. `ProjectionState` + pure reducers
5. `VCGTracker` + seeded bootstrap + decay weighting
6. `ConfidenceSequence` + `BoundedDelta` + risk budget with event-derived timestamps
7. `runDecisionPipeline` integration
8. Full replay determinism test → Deploy

---

### 13. Verification Gates

| Gate | Module | Pass Condition |
|---|---|---|
| 1 | `canonicalizeJCS` | Identical hash output across Node/Browser/WASM for all RFC 8785 vectors |
| 2 | `SequenceAllocator` | Atomic commit with event; replay order matches persisted sequence; collision rejected |
| 3 | `ImmutableBoundary` | Zero reference leakage under reducer stress tests; `Object.isFrozen(state) === true` |
| 4 | `ConfidenceSequence` | ≥95% coverage under adaptive sampling simulation; LCB valid for bounded inputs |
| 5 | `merkleRoot` | Cross-implementation root match for identical leaf sets; byte-concat encoding enforced |
| 6 | `validateEventEnvelope` | Rejects incomplete or malformed envelopes at ingest; never reaches projection |
| 7 | Full Pipeline | `replayProjection(events, pins)` → byte-identical `DecisionSchema` across runs |

---

## Part V — Regulatory and Commercial Alignment

### 14. Regulatory Mapping

| Standard | Core Requirement | Runtime Primitive |
|---|---|---|
| EU AI Act Art. 12 | Automatic event logging over system lifetime | E3 hash-chained event substrate |
| EU AI Act Art. 14 | Human oversight | E1 ambiguity router + conservative fallback |
| EU AI Act Art. 15 | Technical robustness and accuracy | E2 calibration layer + E4 modification gate |
| EU AI Act Art. 12, retention | Six-month minimum operational; ten-year technical documentation | Retention tier table (Section 15) |
| DO-178C / DO-254 | Traceability, deterministic execution, verification | Version pinning + deterministic projections + replayability |
| SOX financial auditing | Verifiable automated controls | Hash-chained event log producing queryable evidence |
| ISO/IEC 42001 | Management system for AI | Schema enforcement + calibration registry + risk budget accounting |
| NIST AI RMF | Govern/Map/Measure/Manage | E2 calibration + E4 gate + audit export |

The system is designed for compliance. Legal compliance is procedural and organisational, not architectural. The system provides the technical evidence that compliance frameworks require; the organisation provides the policies and oversight structures through which that evidence is assessed.

### 15. Retention Tiers

| Event Category | Retention | Basis |
|---|---|---|
| All high-risk AI system events (Art. 12 scope) | Minimum 6 months operational | EU AI Act Art. 12 |
| Technical documentation | 10 years | EU AI Act Art. 18 |
| Gate decision events | 10 years | Audit accountability |
| Calibration events | 3 years | Longitudinal drift analysis |
| Session-scoped interaction events | 90 days operational; tombstone on erasure request | GDPR Art. 5(1)(e) |
| Compliance audit log | 10 years | Regulatory evidence chain |

GDPR right-to-erasure is handled through payload-encryption with per-subject key management. On a verified erasure request, the encryption key is shredded in the KMS and a TOMBSTONE_CREATED event is appended. The structural log record persists; the payload becomes cryptographically irrecoverable. Projection stores must implement a purge-on-tombstone handler; the erasure receipt is not issued until all handlers confirm completion.

### 16. Commercial Architecture

The commercial deployment model is zero-backend for inference costs: the frontend application handles all client-side processing, schema validation, orchestration, and rendering; API costs are borne directly by the enterprise buyer who provisions their own API key. Platform revenue comes from access fees for the governance infrastructure layer itself — the event substrate, calibration pipeline, modification gate, and audit export — rather than for AI inference capacity.

The commercial moat is not the VCG metric (which is mathematically a specialisation of ECE and not proprietary) but the accumulated operational infrastructure: longitudinal reliability histories, regulator-facing evidence binders, deep integration into enterprise evaluation pipelines, and demonstrated audit-trail integrity validated against Article 12 requirements. These are built through production use over time and are not replicable by a competitor who ships the same mathematical primitives without the operational history.

Primary target markets are regulated sectors where the cost of an unauditable decision exceeds the marginal cost of the governance layer: financial services (SOX-governed decision workflows), healthcare AI (diagnostic and treatment-support systems subject to liability standards), critical infrastructure operations, and enterprise AI teams facing EU AI Act compliance deadlines. The system's full applicability date under the EU AI Act for high-risk systems is 2 August 2026.

---

## Part VI — Corrections and Terminology

### 17. Active Corrections from Audit

The LUT-KAN citation (arXiv:2601.03332) was previously cited as reporting ε ≤ 0.0087. The paper's actual result is an F1 drop below 0.0002 on the CICIDS2017 DoS task. This value was used to justify the Lyapunov bound ΔV ≤ 0.08; that justification is void. The bound is retained as an empirically unvalidated engineering parameter pending calibration on the target deployment domain. It is not derived from the LUT-KAN paper and should not be cited as such.

### 18. Terminology Corrections

The following terms from prior architectural drafts are replaced throughout this specification:

| Removed | Replacement |
|---|---|
| Constitutional (as a formal claim) | Governance-constrained / oversight-gated / risk-budgeted |
| Constitutional invariant | Enforced invariant with stated guarantees |
| Hallucination Distance | Verifiable-Domain Calibration Gap (VCG) |
| Bidirectional intent modelling | Mutual legibility interface (five measurable dimensions) |
| Lyapunov constitutional bound | Probabilistic composite safety gate (Level 1–2 only) |
| Superintelligence architecture | Governance-constrained AI runtime |
| Compliance by construction | Audit-enabling infrastructure |
| Bekenstein Ceiling / Landauer Floor (as engineering constraints) | Excised entirely; irrelevant to commodity inference workloads |
| 108°, 1/34, 1.38%, 432 Hz (L34 framework) | Excised entirely; numerological, no engineering role |

---

## Summary

The Sovereign Omega system, in its final reduced form, is a **verifiable decision instrumentation layer** built on six cryptographic and statistical primitives, governed by a four-layer framework that precisely distinguishes what is technically enforceable from what depends on operator discipline, institutional policy, and external trust assumptions.

Its value proposition is not intelligence or alignment — claims the system explicitly does not make — but auditability, calibrated uncertainty, and bounded-risk adaptation under regulatory scrutiny. The architecture produces the specific type of evidence that EU AI Act Article 12, SOX financial auditing, DO-178C avionics certification, and ISO/IEC 42001 management systems require: a tamper-evident, deterministically replayable, version-pinned record of every decision, every confidence claim, every modification proposal, and every gate decision.

The research tier holds one rigorously bounded open question: whether the integrated density of states of CDT-generated spacetimes falls within the gap-labelling group predicted by an appropriate C*-algebra for the ensemble. This is falsifiable, significant if confirmed, and explicitly walled off from any production dependency.

The implementation is ready for execution in the order specified in Section 12.
