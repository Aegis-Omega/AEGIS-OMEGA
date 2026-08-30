// ============================================================
// SOVEREIGN OMEGA — Core Types
// EPISTEMIC TIER: T0 (mechanically enforced contracts)
// ============================================================
// NOTE: No Date.now() anywhere in this file.
// NOTE: All temporal semantics derive from event.timestamp_ms.
// NOTE: These types are the single source of truth for the
//       entire runtime's type system.
// ============================================================

// ─── Branded Primitives ────────────────────────────────────

export type UUIDv7 = string & { readonly __brand: 'UUIDv7' }
export type SHA256Hex = string & { readonly __brand: 'SHA256Hex' }
export type BoundedDelta = number & { readonly __brand: 'bounded_delta_in_-1_to_1' }
export type SequenceNumber = bigint & { readonly __brand: 'SequenceNumber' }

export function normalizeDelta(x: number): BoundedDelta {
  return Math.max(-1, Math.min(1, x)) as BoundedDelta
}

export function assertBoundedDelta(x: number): asserts x is BoundedDelta {
  if (x < -1 || x > 1) throw new RangeError(`Delta ${x} outside [-1,1]`)
}

// ─── Enumerations ──────────────────────────────────────────

export enum EventType {
  // E3 substrate
  SYSTEM_INIT = 'SYSTEM_INIT',
  SCHEMA_MIGRATED = 'SCHEMA_MIGRATED',
  TOMBSTONE_CREATED = 'TOMBSTONE_CREATED',
  VERSION_MISMATCH_ABORT = 'VERSION_MISMATCH_ABORT',
  BUDGET_RESET = 'BUDGET_RESET',

  // E1 ambiguity routing
  INTERACTION_STARTED = 'INTERACTION_STARTED',
  INTENT_RESOLVED = 'INTENT_RESOLVED',
  AMBIGUITY_DETECTED = 'AMBIGUITY_DETECTED',
  AMBIGUITY_ROUTED = 'AMBIGUITY_ROUTED',
  CLARIFICATION_REQUESTED = 'CLARIFICATION_REQUESTED',
  CLARIFICATION_RECEIVED = 'CLARIFICATION_RECEIVED',

  // E2 calibration
  CONFIDENCE_CLAIMED = 'CONFIDENCE_CLAIMED',
  VERIFIER_INVOKED = 'VERIFIER_INVOKED',
  VERIFIER_EVALUATED = 'VERIFIER_EVALUATED',
  VCG_COMPUTED = 'VCG_COMPUTED',
  CALIBRATION_STALE = 'CALIBRATION_STALE',
  CALIBRATION_ALERT = 'CALIBRATION_ALERT',
  VERIFIER_CORRELATION_ALERT = 'VERIFIER_CORRELATION_ALERT',

  // E4 gate
  MODIFICATION_PROPOSED = 'MODIFICATION_PROPOSED',
  GATE_EVALUATED = 'GATE_EVALUATED',
  MODIFICATION_ACCEPTED = 'MODIFICATION_ACCEPTED',
  MODIFICATION_REJECTED = 'MODIFICATION_REJECTED',
  GATE_REJECTED_CAPACITY = 'GATE_REJECTED_CAPACITY',
  BUDGET_UPDATED = 'BUDGET_UPDATED',
  GATE_SUSPENDED = 'GATE_SUSPENDED',
  GATE_FROZEN = 'GATE_FROZEN',

  // Component registration
  COMPONENT_REGISTERED = 'COMPONENT_REGISTERED',

  // Pipeline
  RESPONSE_GENERATED = 'RESPONSE_GENERATED',
  SYSTEM_OUTPUT = 'SYSTEM_OUTPUT',
  HUMAN_OVERRIDE = 'HUMAN_OVERRIDE',

  // Backpressure
  BACKPRESSURE_ENGAGED = 'BACKPRESSURE_ENGAGED',
  BACKPRESSURE_RELEASED = 'BACKPRESSURE_RELEASED',

  // E5 — Cognitive Workflow (AI-mediated development substrate)
  // These make the development process itself a first-class replayable event stream.
  AGENT_PATCH_PROPOSED = 'AGENT_PATCH_PROPOSED',
  GATE_RESULT_RECORDED = 'GATE_RESULT_RECORDED',
  CORPUS_NODE_ACCESSED = 'CORPUS_NODE_ACCESSED',
  SUBAGENT_DELEGATED = 'SUBAGENT_DELEGATED',
  SUBAGENT_RESULT_RECEIVED = 'SUBAGENT_RESULT_RECEIVED',
  GUARDIAN_INVOKED = 'GUARDIAN_INVOKED',
  GUARDIAN_VERDICT_ISSUED = 'GUARDIAN_VERDICT_ISSUED',
  SEMANTIC_NODE_QUERIED = 'SEMANTIC_NODE_QUERIED',
}

export enum RetentionClass {
  EPHEMERAL = 'ephemeral',         // session-scoped, 90 days
  STANDARD = 'standard',           // calibration, 3 years
  REGULATED = 'regulated',         // Art.12 scope, 6 months minimum
  LEGAL_HOLD = 'legal_hold',       // gate decisions + audit, 10 years
}

export enum TombstoneStatus {
  ACTIVE = 'active',
  PAYLOAD_DESTROYED = 'payload_destroyed',
  SUPERSEDED = 'superseded',
}

export enum CapabilityClass {
  SCHEMA_ONLY = 'SCHEMA_ONLY',         // K=0 equivalent
  INFERENCE = 'INFERENCE',             // read-only inference
  ORCHESTRATION = 'ORCHESTRATION',     // can route, cannot mutate
  SELF_MODIFYING = 'SELF_MODIFYING',   // requires gate approval
}

export enum CalibrationDomain {
  GROUND_TRUTH = 'GROUND_TRUTH',               // V1/V2 — full weight in VCG
  RETRIEVAL_ASSISTED = 'RETRIEVAL_ASSISTED',   // V3   — 0.5 weight in VCG
  ADVISORY_EXCLUDED = 'ADVISORY_EXCLUDED',     // V4/V5 — never in VCG
}

export enum VerifierClass {
  V1_DETERMINISTIC = 'V1',    // compilers, theorem provers, execution
  V2_SCHEMA = 'V2',           // JSON Schema, SQL, type checkers
  V3_RETRIEVAL = 'V3',        // KB lookups, RAG grounding
  V4_STATISTICAL = 'V4',      // LLM judges, ensembles
  V5_HUMAN = 'V5',            // human review — audit only
}

export enum AmbiguityType {
  REFERENTIAL = 'REFERENTIAL',
  CONSTRAINT_CONFLICT = 'CONSTRAINT_CONFLICT',
  DOMAIN_SHIFT = 'DOMAIN_SHIFT',
  INTENT_UNDERSPECIFICATION = 'INTENT_UNDERSPECIFICATION',
  SCOPE_AMBIGUITY = 'SCOPE_AMBIGUITY',
}

// ─── Event Envelope ────────────────────────────────────────

export interface EventEnvelope<TPayload = unknown> {
  readonly event_id: UUIDv7
  readonly stream_id: UUIDv7
  readonly event_type: EventType
  readonly timestamp_ms: number        // event-derived; never Date.now() in core
  readonly sequence: SequenceNumber    // assigned atomically by store; never derived from length
  readonly producer_id: string
  readonly producer_version: string
  readonly payload_schema_version: string
  readonly payload: TPayload
  readonly prev_hash: SHA256Hex        // SHA-256 of previous event (RFC 8785 canonical)
  readonly self_hash: SHA256Hex        // SHA-256 of this envelope
  readonly retention_class: RetentionClass
  readonly tombstone_status?: TombstoneStatus
}

// ─── Checkpoint and Segment ────────────────────────────────

export interface Checkpoint {
  readonly checkpoint_id: UUIDv7
  readonly event_index: SequenceNumber
  readonly segment_root: SHA256Hex     // Merkle root of segment
  readonly signature: string           // Ed25519 over (event_index, segment_root)
  readonly public_key_id: string
  readonly timestamp_ms: number
}

export interface EventSegment {
  readonly segment_id: UUIDv7
  readonly stream_id: UUIDv7
  readonly start_sequence: SequenceNumber
  readonly end_sequence: SequenceNumber
  readonly event_count: number
  readonly merkle_root: SHA256Hex
  readonly compressed_blob_ref: string
  readonly compression_codec: 'zstd-v1.5.5' | 'lz4-v1.9.4' | 'none'
  readonly codec_config_hash: SHA256Hex
  readonly merkle_encoding: 'byte-concat-arity-2-v1'
  readonly checkpoint_signature?: string
}

// ─── Runtime Version Pin ───────────────────────────────────

export interface RuntimeVersionPin {
  readonly schema_version: string
  readonly verifier_versions: Readonly<Record<string, string>>
  readonly calibration_model_version: string
  readonly embedding_model_version?: string
  readonly projection_compiler_version: string
  readonly k_measurement_version: string
}

// ─── Verifier Types ────────────────────────────────────────

export interface VerifierResultPayload {
  readonly verifier_id: string
  readonly verifier_class: VerifierClass
  readonly trust_class: CalibrationDomain
  readonly artifact_hash: SHA256Hex
  readonly passed: boolean
  readonly raw_confidence: number | null
  readonly evidence_refs: readonly string[]
  readonly determinism_flag: boolean
  readonly latency_ms: number
  readonly verifier_version: string
}

// ─── Calibration Types ─────────────────────────────────────

export interface VCGMetric {
  readonly domain_id: string
  readonly weighted_error: number
  readonly bootstrap_ci_95: readonly [number, number]
  readonly effective_sample_size: number
  readonly decay_factor: number
  readonly sample_count: number
  readonly last_reset_reason?: 'drift' | 'manual' | 'low_sample'
  readonly epoch_start_ms: number      // from event substrate, never Date.now()
}

export type Confidence =
  | { readonly type: 'verified'; readonly value: number; readonly verifier_ids: readonly string[]; readonly vcg_epoch: string }
  | { readonly type: 'heuristic'; readonly value: number; readonly disclaimer: true; readonly source: string }

// ─── Gate Types ────────────────────────────────────────────

export interface GateDecisionPayload {
  readonly proposal_id: string
  readonly component_id: string
  readonly lcb_value: number
  readonly e_value: number
  readonly delta_metric: number
  readonly sample_size: number
  readonly accepted: boolean
  readonly risk_spent: number
  readonly budget_remaining: number
  readonly freeze_triggered: boolean
  readonly method: 'anytime_valid_bernstein'
  readonly rejection_reason?: 'LCB_FAIL' | 'BUDGET_EXHAUSTED' | 'CAPACITY_EXCEEDED' | 'VERIFIER_INTEGRITY'
}

export interface RiskBudget {
  readonly global_budget: number       // Δ_global default 1.0
  readonly decay_lambda: number        // λ = 0.05 per hour; applied to event-derived timestamps
  readonly epoch_start_ms: number      // sourced from event substrate
  readonly spent: number
  readonly round_number: number
  readonly max_rounds: number
}

// ─── Capacity Declaration ──────────────────────────────────

export interface CapacityDeclaration {
  readonly component_id: string
  readonly k_bound: number             // finite positive integer; 0 = immutable
  readonly mutation_operators: readonly string[]   // from MutationOperatorRegistry
  readonly dependency_graph_hash: SHA256Hex
  readonly capability_class: CapabilityClass
  readonly epoch_duration_ms: number
  readonly k_measurement_version: string
}

export interface MutationOperatorMetadata {
  readonly operator_id: string
  readonly operator_version: string
  readonly max_branching_factor: number  // maximum fan-out per application
  readonly is_compositionally_closed: boolean
  readonly description: string
}

// ─── Projection State ──────────────────────────────────────

export interface ProjectionState {
  readonly score_accumulator: readonly number[]
  readonly strengths: readonly string[]
  readonly risks: readonly string[]
  readonly positioning_candidates: readonly (readonly [string, number])[]
  readonly ground_truth_refs: readonly string[]
  readonly retrieval_context_hashes: readonly string[]
  readonly vcg_epoch_id?: string
  readonly confidence_type: 'verified' | 'heuristic'
  readonly projection_version: string
  readonly last_updated_sequence: SequenceNumber
  readonly freeze_reason?: string
  readonly freeze_timestamp_ms?: number
}

// ─── Decision Schema (pipeline output) ────────────────────

export interface DecisionSchema {
  readonly score: number               // 0–100
  readonly strengths: readonly [string, string, string]
  readonly risks: readonly [string, string, string]
  readonly positioning: string
  readonly actions: readonly [string, string, string]
  readonly confidence: Confidence
  readonly audit_trace_id: UUIDv7
  readonly vcg_at_emission: number
  readonly schema_version: string
}

// ─── Dialogue State (E1) ───────────────────────────────────

export interface Referent {
  readonly id: string
  readonly label: string
  readonly introduced_at_sequence: SequenceNumber
  readonly last_referenced_at_sequence: SequenceNumber
}

export interface DialogueConstraint {
  readonly id: string
  readonly description: string
  readonly introduced_at_sequence: SequenceNumber
  readonly is_active: boolean
}

export interface DialogueState {
  readonly session_id: UUIDv7
  readonly resolved_referents: Readonly<Record<string, Referent>>
  readonly active_constraints: readonly DialogueConstraint[]
  readonly unresolved_ambiguities: readonly AmbiguityFlag[]
  readonly grounding_confidence: number
  readonly turn_count: number
  readonly last_updated_sequence: SequenceNumber
}

export interface AmbiguityFlag {
  readonly id: string
  readonly ambiguity_type: AmbiguityType
  readonly divergence_score: number
  readonly introduced_at_sequence: SequenceNumber
  readonly resolved: boolean
}

// ─── Holonic Hierarchy Types ──────────────────────────────────
// Each component is simultaneously a whole and a part — a recursively nested holon
// governed by invariant-preserving feedback loops.
// A T0 violation at SUBATOMIC propagates upward and invalidates all scales above it.

export enum HolonicScale {
  SUBATOMIC = 'subatomic',   // byte ordering, hash invariants, fixed-point arithmetic
  ATOMIC    = 'atomic',      // files, functions, proof units — elementary holons
  MOLECULAR = 'molecular',   // modules (core/, event/, gate/, calibration/)
  CELLULAR  = 'cellular',    // subsystems: E3 substrate, VCG, Python Core Matrix
  ORGANISM  = 'organism',    // full sovereign-omega-v2 governance runtime
  FIELD     = 'field',       // Claude + ChatGPT + Qwen + operators + Drive corpus
}

export enum EpistemicTier {
  T0 = 'T0',  // mechanically proven
  T1 = 'T1',  // empirically validated
  T2 = 'T2',  // engineering hypothesis
  T3 = 'T3',  // research conjecture
  T4 = 'T4',  // speculative systems vision
  T5 = 'T5',  // creative/worldbuilding
}

export interface HolonMetadata {
  readonly holon_id: string
  readonly scale: HolonicScale
  readonly tier: EpistemicTier
  readonly part_of: readonly string[]     // parent holon IDs
  readonly composed_of: readonly string[] // child holon IDs
  readonly invariants: readonly string[]  // human-readable invariant descriptions
  readonly interaction_surface: readonly string[] // exported API / event types
  // Provenance: Drive document IDs that epistemically ground this holon.
  // Every T0–T2 holon must have at least one T0–T2 source document.
  // Absence of provenance at T0–T2 is a migration rule violation.
  readonly provenance: readonly string[]  // Drive file IDs from the research corpus
  readonly ontology_term: string          // canonical term from docs/ONTOLOGY.md
}

// ─── Ralph Loop State Machine (Cycles 26–30) ──────────────
// The Ralph Loop (Review → Analyze → Link → Patch → Harmonize)
// is the primary iterative improvement protocol for AEGIS.
// Each cycle operates at one holonic scale and elevates it.

export enum RalphPhase {
  REVIEW    = 'REVIEW',    // R: read all relevant state at the target scale
  ANALYZE   = 'ANALYZE',   // A: identify gaps, violations, and opportunities
  LINK      = 'LINK',      // L: establish couplings between holons that need them
  PATCH     = 'PATCH',     // P: apply the minimal correct transformation
  HARMONIZE = 'HARMONIZE', // H: verify the result is coherent with all parent holons
}

export interface RalphCycle {
  readonly cycle_id: UUIDv7
  readonly cycle_number: number
  readonly target_scale: HolonicScale
  readonly phase: RalphPhase
  readonly findings: readonly string[]       // what the Review phase found
  readonly analysis_notes: readonly string[] // what the Analyze phase concluded
  readonly links_established: readonly string[] // what the Link phase coupled
  readonly patches_applied: readonly string[]   // what the Patch phase changed
  readonly harmonization_result: 'COHERENT' | 'INCOHERENT' | 'PENDING'
  readonly gate_result?: 'PASS' | 'FAIL'
  readonly sequence: SequenceNumber
}

export interface RalphLoopState {
  readonly total_cycles: number
  readonly completed_cycles: readonly RalphCycle[]
  readonly current_cycle?: Omit<RalphCycle, 'harmonization_result' | 'gate_result'>
  readonly entropy_at_start: number   // Shannon entropy of system state before this loop
  readonly entropy_at_end?: number    // Shannon entropy after — should decrease
  readonly convergence_depth: number  // consecutive cycles with zero findings
}

// ─── Cycle Archive (replay persistence) ───────────────────────
// Schema version is a first-class field — schema evolution must
// bump CYCLE_ARCHIVE_SCHEMA_VERSION before changing RalphCycle shape.
// Deserializers must reject archives with unknown schema versions.

export const CYCLE_ARCHIVE_SCHEMA_VERSION = '1.0.0' as const

export interface CycleArchive {
  readonly schema_version: typeof CYCLE_ARCHIVE_SCHEMA_VERSION
  readonly archived_at_sequence: number   // sequence number at export time
  readonly cycles: readonly RalphCycle[]
  readonly total_cycles: number
  readonly convergence_depth: number
  readonly entropy_at_start: number
  readonly entropy_at_end?: number
}
