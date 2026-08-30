// ============================================================
// CorpusEngine — RALPH Pipeline Types
// EPISTEMIC TIER: T2 · Gate 144
// Addendum corpus processing directive: all knowledge enters
// through 5-phase RALPH loop; raw narrative must NOT propagate.
// Only replay-certifiable abstractions propagate (Corpus Sovereignty).
// ============================================================

import type { SHA256Hex } from '../core/types.js'

export const CORPUS_SCHEMA_VERSION = '1.0.0' as const

export type RalphPhase =
  | 'OBSERVATION'    // READ  — structural hash, byte count only
  | 'INTERPRETATION' // ASSESS — domain signal extraction
  | 'ARBITRATION'    // LOCK  — tier classification; T4/T5 → admitted=false
  | 'MUTATION'       // PROPAGATE — semantic compression to primitive_mapping
  | 'PROPAGATION'    // HARMONIZE — emit CorpusLineageRecord (if admitted)

// T4/T5 downgraded to docs/ only at ARBITRATION
export type DocumentTier = 'T0' | 'T1' | 'T2' | 'T3'

export interface CorpusDocument {
  readonly document_id: string
  readonly source: string           // Drive file ID or GitHub URL
  readonly content_hash: SHA256Hex  // hashValue(raw content)
  readonly byte_length: number
  readonly schema_version: typeof CORPUS_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface RalphPhaseRecord {
  readonly document_id: string
  readonly phase: RalphPhase
  readonly fibonacci_depth: number       // fibonacciInterval(phase_index 1-5) = [1,1,2,3,5]
  readonly phase_input_hash: SHA256Hex   // hash of input to this phase
  readonly phase_output_hash: SHA256Hex  // hash of output from this phase
  readonly phase_hash: SHA256Hex         // hashValue({document_id, phase, phase_input_hash, phase_output_hash})
  readonly admitted: boolean             // ARBITRATION result
  readonly downgrade_reason?: string     // set when !admitted
  readonly is_replay_reconstructable: true
}

export interface CorpusLineageRecord {
  readonly document_id: string
  readonly phases: readonly RalphPhaseRecord[]  // always length 5
  readonly corpus_lineage_hash: SHA256Hex        // hashValue(all phase_hashes in order)
  readonly final_tier: DocumentTier | 'DOWNGRADED'
  readonly is_replay_reconstructable: true
}

export class CorpusEngineError extends Error {
  override readonly name = 'CorpusEngineError'
}
