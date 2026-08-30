// ============================================================
// SOVEREIGN OMEGA — E1 Ambiguity Routing Interface
// EPISTEMIC TIER: T2 (engineering hypothesis, heuristic)
// Mutual legibility: 5 measurable dimensions.
// Does NOT model intent, consciousness, or theory of mind.
// Common ground = referential consistency + constraint tracking.
// Clarification policy: cost-benefit routing, NOT semantic understanding.
// ============================================================

import type {
  DialogueState, AmbiguityFlag, AmbiguityType,
  UUIDv7, SequenceNumber
} from '../core/types.js'
import { AmbiguityType as AT } from '../core/types.js'
import { createInitialState, deepFreeze } from '../core/immutable.js'
import { generateUUIDv7 } from '../event/uuid.js'

// Configuration thresholds (T2 — empirically unvalidated defaults)
const DIVERGENCE_CLARIFICATION_THRESHOLD = 0.65
const GROUNDING_CONFIDENCE_FLOOR = 0.40
const MAX_CLARIFICATION_RATE = 1 / 3  // at most 1 per 3 turns
const MAX_UNRESOLVED_BEFORE_ESCALATION = 3

export function createInitialDialogueState(sessionId: UUIDv7): Readonly<DialogueState> {
  return createInitialState<DialogueState>({
    session_id: sessionId,
    resolved_referents: {},
    active_constraints: [],
    unresolved_ambiguities: [],
    grounding_confidence: 1.0,
    turn_count: 0,
    last_updated_sequence: BigInt(0) as SequenceNumber,
  })
}

export interface AmbiguityAssessment {
  readonly requires_clarification: boolean
  readonly divergence_score: number
  readonly detected_types: readonly AmbiguityType[]
  readonly cost_of_proceeding: number
  readonly cost_of_clarifying: number
  readonly escalate_to_structured_form: boolean
}

/**
 * Assess whether a new user input requires clarification.
 *
 * Policy: clarify when expected_cost(false_assumption) > expected_cost(interruption).
 * This is a cost-benefit heuristic, not semantic intent modelling.
 *
 * LONG-HORIZON NOTE: Degradation curves for sessions > 50 turns are an
 * open empirical measurement problem. These thresholds are T2 defaults.
 */
export function assessAmbiguity(
  input: string,
  state: Readonly<DialogueState>,
  _embeddingModelVersion: string
): AmbiguityAssessment {
  const detectedTypes: AmbiguityType[] = []
  let divergenceScore = 0

  // Referential ambiguity: unresolved pronouns or definite references
  if (hasUnresolvedReference(input, state)) {
    detectedTypes.push(AT.REFERENTIAL)
    divergenceScore += 0.3
  }

  // Constraint conflict: input implies a constraint contradicting active constraints
  if (hasConstraintConflict(input, state)) {
    detectedTypes.push(AT.CONSTRAINT_CONFLICT)
    divergenceScore += 0.4
  }

  // Domain shift: technical term without prior grounding
  if (hasDomainShift(input, state)) {
    detectedTypes.push(AT.DOMAIN_SHIFT)
    divergenceScore += 0.2
  }

  // Intent underspecification: request admits multiple materially different responses
  if (hasIntentUnderspecification(input)) {
    detectedTypes.push(AT.INTENT_UNDERSPECIFICATION)
    divergenceScore += 0.25
  }

  // Normalise to [0, 1]
  divergenceScore = Math.min(1, divergenceScore)

  // Cost-benefit decision
  const costOfProceeding = divergenceScore * 2.0  // proceeding on wrong assumption is 2x costly
  const costOfClarifying = 0.5 / (state.turn_count + 1)  // clarification cost decreases with rapport
  const requiresClarification =
    divergenceScore > DIVERGENCE_CLARIFICATION_THRESHOLD ||
    state.grounding_confidence < GROUNDING_CONFIDENCE_FLOOR ||
    detectedTypes.includes(AT.CONSTRAINT_CONFLICT) ||
    (detectedTypes.includes(AT.REFERENTIAL) && state.unresolved_ambiguities.length > 1)

  // Rate limiting: no more than 1 clarification per 3 turns
  const recentClarifications = Math.min(state.unresolved_ambiguities.length, state.turn_count)
  const clarificationRateOk = recentClarifications / Math.max(state.turn_count, 1) < MAX_CLARIFICATION_RATE

  const escalateToStructuredForm =
    state.unresolved_ambiguities.filter(a => !a.resolved).length >= MAX_UNRESOLVED_BEFORE_ESCALATION

  return Object.freeze({
    requires_clarification: requiresClarification && clarificationRateOk,
    divergence_score: divergenceScore,
    detected_types: Object.freeze(detectedTypes),
    cost_of_proceeding: costOfProceeding,
    cost_of_clarifying: costOfClarifying,
    escalate_to_structured_form: escalateToStructuredForm,
  })
}

/**
 * Update dialogue state after a turn.
 * Returns a new frozen state — never mutates the input.
 */
export function updateDialogueState(
  state: Readonly<DialogueState>,
  _input: string,
  assessment: AmbiguityAssessment,
  sequence: SequenceNumber
): Readonly<DialogueState> {
  const newAmbiguities: AmbiguityFlag[] = assessment.detected_types.map(t => ({
    id: generateUUIDv7(),
    ambiguity_type: t,
    divergence_score: assessment.divergence_score,
    introduced_at_sequence: sequence,
    resolved: false,
  }))

  const updatedGroundingConfidence = Math.max(
    0,
    state.grounding_confidence - (assessment.divergence_score * 0.1)
  )

  return deepFreeze({
    ...state,
    unresolved_ambiguities: Object.freeze([
      ...state.unresolved_ambiguities.filter(a => !a.resolved).slice(-10),
      ...newAmbiguities,
    ]),
    grounding_confidence: updatedGroundingConfidence,
    turn_count: state.turn_count + 1,
    last_updated_sequence: sequence,
  })
}

// ─── Detection Heuristics ──────────────────────────────────
// These are T2 engineering heuristics, not formal NLP.
// Replace with proper NLP models for production use.

function hasUnresolvedReference(input: string, state: Readonly<DialogueState>): boolean {
  const pronouns = /\b(it|this|that|they|them|he|she|the one|the same)\b/i
  if (!pronouns.test(input)) return false
  return Object.keys(state.resolved_referents).length === 0
}

function hasConstraintConflict(input: string, state: Readonly<DialogueState>): boolean {
  if (state.active_constraints.length === 0) return false
  const negationPattern = /\b(not|don't|never|except|but not|without)\b/i
  return negationPattern.test(input) && state.active_constraints.some(c => {
    const words = c.description.toLowerCase().split(' ')
    return words.some(w => input.toLowerCase().includes(w))
  })
}

function hasDomainShift(input: string, state: Readonly<DialogueState>): boolean {
  const technicalPattern = /\b([A-Z]{2,}|[a-z]+-[a-z]+|[a-z]+_[a-z]+)\b/g
  const terms = input.match(technicalPattern) ?? []
  if (terms.length === 0) return false
  const knownReferents = Object.keys(state.resolved_referents)
  return terms.some(t => !knownReferents.some(r => r.toLowerCase().includes(t.toLowerCase())))
}

function hasIntentUnderspecification(input: string): boolean {
  const vague = /\b(something|anything|whatever|some kind of|a thing|it|somehow)\b/i
  const shortInput = input.trim().split(' ').length < 4
  return vague.test(input) || shortInput
}
