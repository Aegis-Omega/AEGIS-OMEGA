// ============================================================
// SOVEREIGN OMEGA — Projection State & Pure Reducers
// EPISTEMIC TIER: T0
// Arrays only — no Set, no Map. Serialisable, deterministic.
// All reducers are pure functions. withImmutableBoundary wraps.
// ============================================================

import type {
  ProjectionState, EventEnvelope, EventType, SequenceNumber
} from '../core/types.js'
import { EventType as ET } from '../core/types.js'
import { withImmutableBoundary, createInitialState } from '../core/immutable.js'

/** Deep-clone all array fields so the output state shares no references with input. */
function cloneArrays(state: Readonly<ProjectionState>): ProjectionState {
  return {
    ...state,
    score_accumulator: [...state.score_accumulator],
    strengths: [...state.strengths],
    risks: [...state.risks],
    positioning_candidates: state.positioning_candidates.map(p => [p[0], p[1]] as [string, number]),
    ground_truth_refs: [...state.ground_truth_refs],
    retrieval_context_hashes: [...state.retrieval_context_hashes],
  }
}

export const INITIAL_PROJECTION_STATE: ProjectionState = {
  score_accumulator: [],
  strengths: [],
  risks: [],
  positioning_candidates: [],
  ground_truth_refs: [],
  retrieval_context_hashes: [],
  confidence_type: 'heuristic',
  projection_version: '1.0.0',
  last_updated_sequence: BigInt(0) as SequenceNumber,
}

const rawApplyEvent = (
  state: Readonly<ProjectionState>,
  event: EventEnvelope
): ProjectionState => {
  // Frozen states cannot be further modified
  if (state.freeze_reason !== undefined) return state

  const next = cloneArrays(state)

  switch (event.event_type as EventType) {
    case ET.VCG_COMPUTED: {
      const p = event.payload as { vcg_epoch_id: string }
      return { ...next, vcg_epoch_id: p.vcg_epoch_id, last_updated_sequence: event.sequence }
    }
    case ET.CONFIDENCE_CLAIMED: {
      const p = event.payload as { confidence_type: 'verified' | 'heuristic' }
      return { ...next, confidence_type: p.confidence_type, last_updated_sequence: event.sequence }
    }
    case ET.SYSTEM_OUTPUT: {
      const p = event.payload as {
        score?: number
        strengths?: string[]
        risks?: string[]
        positioning?: string
        output_hash?: string
      }
      if (p.score !== undefined) (next.score_accumulator as number[]).push(p.score)
      if (p.strengths) (next.strengths as string[]).push(...p.strengths)
      if (p.risks) (next.risks as string[]).push(...p.risks)
      if (p.positioning) (next.positioning_candidates as [string, number][]).push([p.positioning, 1.0])
      if (p.output_hash) (next.ground_truth_refs as string[]).push(p.output_hash)
      return { ...next, last_updated_sequence: event.sequence }
    }
    case ET.GATE_FROZEN: {
      return {
        ...next,
        freeze_reason: 'gate_frozen',
        freeze_timestamp_ms: event.timestamp_ms,
        last_updated_sequence: event.sequence,
      }
    }
    case ET.VERIFIER_EVALUATED: {
      const p = event.payload as { artifact_hash?: string }
      if (p.artifact_hash) (next.retrieval_context_hashes as string[]).push(p.artifact_hash)
      return { ...next, last_updated_sequence: event.sequence }
    }
    default:
      return { ...next, last_updated_sequence: event.sequence }
  }
}

export const applyEvent = withImmutableBoundary(rawApplyEvent)

export function createProjectionState(version: string): Readonly<ProjectionState> {
  return createInitialState({ ...INITIAL_PROJECTION_STATE, projection_version: version })
}
