// ============================================================
// SOVEREIGN OMEGA — Constitutional Directive Registry
// EPISTEMIC TIER: T2 · Gate 200
//
// Formalizes the Sovereign Cognition Protocol's four directives
// as hash-linked constitutional records. Each directive is a
// declaration of an existing AEGIS module's governing constraint —
// not new code, but the explicit mapping from intent to mechanism.
//
// T5 shell:  "Sovereign Constitutional Cognition Engine"
// T2 record: SovereignDirective[] — engineering hypothesis, typed
// T0 proof:  directive_hash = hashValue(canonical) — identity-stable
//
// Constitutional invariants:
// - All 4 directives have epistemic_tier: 'T2' (hypothesis, not proof)
// - CANONICAL_DIRECTIVES is deepFreeze'd — immutable at runtime
// - buildConstitutionHash() is deterministic ×3 (same input → same output)
// - Directive ordering is alphabetical by directive_class (deterministic)
// - No new constraint is introduced — each directive points to the
//   existing module that already implements it
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const DIRECTIVES_SCHEMA_VERSION = '1.0.0' as const

// ─── Directive taxonomy ───────────────────────────────────

// The four constitutional directives. Alphabetical order → deterministic
// iteration when used as BTreeMap keys.
export type DirectiveClass =
  | 'ADVERSARIAL_SELF_CORRECTION' // Internal audit + drift detection
  | 'CAUSAL_ARCHITECTURE'         // Mechanism over metaphor + anti-hallucination
  | 'EPISTEMIC_SOVEREIGNTY'       // Truth over flow + uncertainty preservation
  | 'OPERATIONAL_REALISM'         // Feasibility as constraint + failure topology

// The four execution phases. Maps onto RALPH READ/ASSESS/LOCK/HARMONIZE.
export type ExecutionPhase =
  | 'DECONSTRUCT' // READ:      isolate core variables, strip rhetorical noise
  | 'MODEL'       // ASSESS:    build causal dependency map
  | 'STRESS_TEST' // LOCK:      adversarial pressure, identify weakest assumption
  | 'SYNTHESIZE'  // HARMONIZE: reconstruct from stress-test survivors only

// ─── Core directive record ────────────────────────────────

export interface SovereignDirective {
  readonly directive_class: DirectiveClass
  readonly description: string
  readonly aegis_grounding: string         // the AEGIS module implementing this constraint
  readonly aegis_grounding_file: string    // canonical file path for traceability
  readonly failure_mode_prevented: string  // explicit mechanism, not rhetorical
  readonly epistemic_tier: 'T2'            // engineering hypothesis — not mechanically proven
  readonly directive_hash: SHA256Hex       // hashValue({directive_class, description, aegis_grounding})
  readonly schema_version: typeof DIRECTIVES_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Directive factory ────────────────────────────────────

export async function buildDirective(input: {
  directive_class: DirectiveClass
  description: string
  aegis_grounding: string
  aegis_grounding_file: string
  failure_mode_prevented: string
}): Promise<SovereignDirective> {
  const directive_hash = await hashValue({
    directive_class: input.directive_class,
    description: input.description,
    aegis_grounding: input.aegis_grounding,
  })
  return deepFreeze<SovereignDirective>({
    ...input,
    epistemic_tier: 'T2',
    directive_hash,
    schema_version: DIRECTIVES_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// ─── Constitution fingerprint ─────────────────────────────
//
// SHA-256 over all 4 directive hashes in DirectiveClass alphabetical order.
// Changing any directive text invalidates this hash — tamper-evident.

export async function buildConstitutionHash(
  directives: readonly SovereignDirective[],
): Promise<SHA256Hex> {
  const sorted = [...directives].sort((a, b) =>
    a.directive_class < b.directive_class ? -1 : a.directive_class > b.directive_class ? 1 : 0,
  )
  return hashValue({
    directive_hashes: sorted.map(d => d.directive_hash),
    schema_version: DIRECTIVES_SCHEMA_VERSION,
  })
}

// ─── Canonical registry ───────────────────────────────────
//
// Initialized lazily on first call to getCanonicalDirectives().
// All four directives are declared here with their exact AEGIS grounding.

let _canonicalDirectives: readonly SovereignDirective[] | null = null

export async function getCanonicalDirectives(): Promise<readonly SovereignDirective[]> {
  if (_canonicalDirectives !== null) return _canonicalDirectives

  const [adversarial, causal, epistemic, operational] = await Promise.all([
    buildDirective({
      directive_class: 'ADVERSARIAL_SELF_CORRECTION',
      description:
        'Internal audit loop simulates a critic attacking the builder\'s logic before output is finalized. ' +
        'Drift detection re-anchors reasoning to original axioms when context expands.',
      aegis_grounding:
        'BFT quorum at 1/φ via tallyVotes(). No single model response is authoritative. ' +
        'HysteresisFilter penalizes deviating peers. routeSwarmResponses() requires ' +
        'valid_count * 1_000_000 >= total_count * 618_034 for consensus_response_hash to be emitted.',
      aegis_grounding_file:
        'src/agents/coordination/swarm-router.ts, src/consensus/swarm.ts, aegis-runtime/src/hysteresis.rs',
      failure_mode_prevented:
        'Contradiction accumulation, abstraction spirals, context-window drift, sycophantic agreement.',
    }),
    buildDirective({
      directive_class: 'CAUSAL_ARCHITECTURE',
      description:
        'Mechanism over metaphor: every system is expressed as Inputs → Constraints → Transformations → Outputs. ' +
        'First-principles decomposition to foundational invariants before synthesis. ' +
        'Anti-hallucination: unverified causal links are quarantined as Speculative or Unknown.',
      aegis_grounding:
        'Hash-chained lineage (is_replay_reconstructable: true on every record). ' +
        'admitAbstraction() requires primitive_mapping, replay_mapping, topology_mapping — ' +
        'no abstraction admitted without explicit causal grounding. ' +
        'T4/T5 language blocked at ARBITRATION phase of processDocument().',
      aegis_grounding_file:
        'src/constitutional/reduction.ts, src/corpus-engine/pipeline.ts, src/frame/lineage.ts',
      failure_mode_prevented:
        'Pseudo-depth, associative leaps, narrative causality, fabricated operational states.',
    }),
    buildDirective({
      directive_class: 'EPISTEMIC_SOVEREIGNTY',
      description:
        'Truth over flow: logical correctness is never sacrificed for linguistic elegance. ' +
        'Uncertainty preservation: confidence is explicitly quantified, not collapsed. ' +
        'Source validation: all inputs treated as unverified until structurally validated.',
      aegis_grounding:
        'Epistemic tier taxonomy T0/T1/T2/T3 enforced on every admission. ' +
        'admitAbstraction() blocks T4/T5 — no claim may exceed its evidence class. ' +
        'RALPH corpus pipeline classifies documents at ARBITRATION phase before propagation. ' +
        'Structural Decomposition\'s A/B/C/D/E classification is isomorphic to T0/T1/T2/T3/unknown.',
      aegis_grounding_file:
        'src/constitutional/reduction.ts, src/corpus-engine/pipeline.ts, src/agents/types.ts',
      failure_mode_prevented:
        'Sycophancy, confidence collapse, propagation of unverified premises, T4/T5 speculation in T0 paths.',
    }),
    buildDirective({
      directive_class: 'OPERATIONAL_REALISM',
      description:
        'Feasibility as constraint: every output evaluated against cost, maintenance, scaling limits, failure modes. ' +
        'Failure topology: pre-mortem analysis of single points of failure and cascading errors. ' +
        'Constraint hierarchy: hard constraints (logic, law, physics) veto soft constraints (aesthetics, preference).',
      aegis_grounding:
        'AdaptivePower(T) ≤ ReplayVerifiability(T) — no capability may exceed what replay can certify. ' +
        'certifyMartingale() suspends mutation authority when entropy_bounded=false. ' +
        'aegis-runtime StateAnchor corruption_count=0 required for T0 pass. ' +
        'MAXIMUM_SWARM_NODES=1024 bounds ecology growth.',
      aegis_grounding_file:
        'src/constitutional/martingale.ts, aegis-runtime/src/state_anchor.rs, aegis-runtime/src/lib.rs',
      failure_mode_prevented:
        'Paper architecture (elegant in theory, fails in production), unbounded scaling assumptions, naive optimization.',
    }),
  ])

  _canonicalDirectives = deepFreeze([adversarial, causal, epistemic, operational])
  return _canonicalDirectives
}
