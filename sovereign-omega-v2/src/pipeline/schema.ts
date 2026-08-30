// ============================================================
// SOVEREIGN OMEGA — Decision Schema Construction
// EPISTEMIC TIER: T0/T2
// The DecisionSchema is the sole output contract of the pipeline.
// Constructed from projection state — never from raw LLM output.
// ============================================================

import type { DecisionSchema, ProjectionState, Confidence, UUIDv7 } from '../core/types.js'
import { generateUUIDv7 } from '../event/uuid.js'

const SCHEMA_VERSION = '1.0.0'

/**
 * Construct a DecisionSchema from projection state and confidence.
 * This is the terminal operation of the pipeline.
 * The schema is the only artifact the frontend renders.
 */
export function buildDecisionSchema(
  state: Readonly<ProjectionState>,
  confidence: Confidence,
  vcgAtEmission: number
): DecisionSchema {
  const score = computeScore(state)
  const strengths = extractTopN(state.strengths, 3)
  const risks = extractTopN(state.risks, 3)
  const positioning = extractBestPositioning(state.positioning_candidates)
  const actions = deriveActions(state, score)

  return Object.freeze({
    score,
    strengths: Object.freeze(strengths) as DecisionSchema['strengths'],
    risks: Object.freeze(risks) as DecisionSchema['risks'],
    positioning,
    actions: Object.freeze(actions) as DecisionSchema['actions'],
    confidence,
    audit_trace_id: generateUUIDv7() as UUIDv7,
    vcg_at_emission: vcgAtEmission,
    schema_version: SCHEMA_VERSION,
  })
}

/**
 * Build a conservative fallback schema when the pipeline cannot proceed.
 * Used when: LCB < 0, budget exhausted, clarification required.
 */
export function buildConservativeSchema(confidence: Confidence, reason = 'CONSERVATIVE_FALLBACK'): DecisionSchema {
  return Object.freeze({
    score: 0,
    strengths: Object.freeze(['Insufficient data', 'Awaiting verification', 'Calibration pending']) as DecisionSchema['strengths'],
    risks: Object.freeze(['Cannot assess', 'Verification required', 'Low confidence']) as DecisionSchema['risks'],
    positioning: `${reason}: This output requires additional context or verification before use.`,
    actions: Object.freeze(['Provide more context', 'Retry with verified inputs', 'Contact support']) as DecisionSchema['actions'],
    confidence,
    audit_trace_id: generateUUIDv7() as UUIDv7,
    vcg_at_emission: 1.0,
    schema_version: SCHEMA_VERSION,
  })
}

// ─── Private helpers ───────────────────────────────────────

function computeScore(state: Readonly<ProjectionState>): number {
  if (state.score_accumulator.length === 0) return 0
  const avg = state.score_accumulator.reduce((a, b) => a + b, 0) / state.score_accumulator.length
  return Math.round(Math.max(0, Math.min(100, avg)))
}

function extractTopN(items: readonly string[], n: number): [string, string, string] {
  const deduplicated = [...new Set(items)]
  const padded: string[] = []
  for (let i = 0; i < n; i++) {
    padded.push(deduplicated[i] ?? `Item ${i + 1} pending`)
  }
  return [padded[0]!, padded[1]!, padded[2]!]
}

function extractBestPositioning(candidates: readonly (readonly [string, number])[]): string {
  if (candidates.length === 0) return 'Positioning analysis pending.'
  const best = [...candidates].sort((a, b) => b[1] - a[1])[0]
  /* c8 ignore next -- noUncheckedIndexedAccess artifact; candidates.length>0 (guarded line above) guarantees best is defined */
  return best?.[0] ?? 'Positioning analysis pending.'
}

function deriveActions(_state: Readonly<ProjectionState>, score: number): [string, string, string] {
  if (score >= 70) return ['Proceed with primary strategy', 'Monitor key risk indicators', 'Review at 30-day checkpoint']
  if (score >= 40) return ['Validate assumptions before proceeding', 'Address top risk factor first', 'Schedule follow-up assessment']
  return ['Pause and gather additional data', 'Consult domain expert', 'Reassess after addressing risks']
}
