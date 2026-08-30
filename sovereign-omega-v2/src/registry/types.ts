// ============================================================
// SOVEREIGN OMEGA — Semantic Particle Registry Types
// EPISTEMIC TIER: T0
// Machine-readable classification of every artifact in the runtime.
// Every node simultaneously: coherent whole + dependent participant.
// ============================================================

export { EpistemicTier } from '../core/tier.js'

export enum HolonicScale {
  SUBATOMIC = 'SUBATOMIC',   // byte ordering, hash invariants, fixed-point arithmetic
  ATOMIC = 'ATOMIC',         // individual files, reducers, interfaces, proof units
  MOLECULAR = 'MOLECULAR',   // modules (core/, event/, gate/, calibration/)
  CELLULAR = 'CELLULAR',     // subsystems (E3 substrate, VCG, Core Matrix)
  ORGANISM = 'ORGANISM',     // full sovereign-omega-v2 governance runtime
  FIELD = 'FIELD',           // Claude + ChatGPT + Qwen + corpus + operators
}

export enum MutationAuthority {
  /** Constitutional file — guardian approval required before any modification */
  GUARDIAN_ONLY = 'GUARDIAN_ONLY',
  /** Must pass its designated gate before modification is permitted */
  GATE_GUARDED = 'GATE_GUARDED',
  /** Follows standard gate protocol — no additional restrictions */
  STANDARD = 'STANDARD',
  /** Never modified by agents — Drive documents, external proofs, corpus */
  ADVISORY_READ_ONLY = 'ADVISORY_READ_ONLY',
}

export enum ProofCoverage {
  COQ_THEOREM = 'COQ_THEOREM',       // covered by a Coq formal proof
  TLA_SPEC = 'TLA_SPEC',             // covered by TLA+ temporal specification
  GATE_VERIFIED = 'GATE_VERIFIED',   // validated by a named build gate
  TEST_COVERED = 'TEST_COVERED',     // covered by integration or unit tests
  UNCOVERED = 'UNCOVERED',           // no formal or test coverage — known gap
}

export type AncestryRelationship =
  | 'implements'   // this file implements a spec claim
  | 'grounds'      // this file provides the basis for another
  | 'depends_on'   // this file imports from / requires the target
  | 'tested_by'    // this file's behaviour is validated by the target
  | 'verified_by'  // this file's properties are formally proved by the target

export interface AncestryEdge {
  readonly target_path: string
  readonly relationship: AncestryRelationship
}

export interface SemanticNode {
  readonly path: string                              // relative to sovereign-omega-v2/
  readonly tier: 0 | 1 | 2 | 3 | 4 | 5             // EpistemicTier numeric value
  readonly module: string                            // module name (e.g. 'core', 'event')
  readonly gate: number | null                       // build gate that validates this file
  readonly mutation_authority: MutationAuthority
  readonly proof_coverage: readonly ProofCoverage[]
  readonly ancestry_edges: readonly AncestryEdge[]
  readonly holonic_scale: HolonicScale
  readonly is_constitutional: boolean               // true = frozen, hash-verified
  readonly description: string
}
