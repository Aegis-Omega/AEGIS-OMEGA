// ============================================================
// SOVEREIGN OMEGA — T3 Resource-Aware Routing Falsifier
// EPISTEMIC TIER: T3 (research conjecture)
//
// Chooses only among candidates already admitted by an external authority
// boundary. This module cannot create authority and may always abstain.
// ============================================================

import { T3_RESEARCH_ONLY, WRITE_BACK_AUTHORITY } from './types.js'

export const RAR_SCHEMA_VERSION = '1.0.0' as const
export const RAR_AUTHORITY_EFFECT = 'NONE' as const
export const PPM = 1_000_000

export interface ResourceStateV1 {
  readonly uncertainty_ppm: number
  readonly criticality: 0 | 1 | 2 | 3
  readonly max_latency_ms: number
  readonly max_cost_units: number
}

export interface RouteCandidateV1 {
  readonly candidate_id: string
  readonly authority_admitted: boolean
  readonly predicted_correct_ppm: number
  readonly calibration_error_ppm: number
  readonly latency_ms: number
  readonly cost_units: number
}

export interface ResourceRouteDecisionV1 {
  readonly schema_version: typeof RAR_SCHEMA_VERSION
  readonly outcome: 'ROUTED' | 'ABSTAIN'
  readonly selected_candidate_id: string | null
  readonly considered_candidate_ids: readonly string[]
  readonly reason: 'SELECTED' | 'NO_AUTHORITY_ADMITTED_CANDIDATE' | 'NO_CANDIDATE_WITHIN_BUDGET' | 'INSUFFICIENT_RELIABILITY'
  readonly required_reliability_ppm: number
  readonly selected_score: number | null
  readonly t3_research_only: typeof T3_RESEARCH_ONLY
  readonly write_back_authority: typeof WRITE_BACK_AUTHORITY
  readonly authority_effect: typeof RAR_AUTHORITY_EFFECT
}

function assertBoundedInt(value: number, min: number, max: number, field: string): void {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new TypeError(`${field} must be an integer in [${min}, ${max}]`)
  }
}

function assertResourceState(state: ResourceStateV1): void {
  assertBoundedInt(state.uncertainty_ppm, 0, PPM, 'uncertainty_ppm')
  assertBoundedInt(state.criticality, 0, 3, 'criticality')
  assertBoundedInt(state.max_latency_ms, 1, Number.MAX_SAFE_INTEGER, 'max_latency_ms')
  assertBoundedInt(state.max_cost_units, 1, Number.MAX_SAFE_INTEGER, 'max_cost_units')
}

function assertCandidate(candidate: RouteCandidateV1): void {
  if (!/^[A-Za-z0-9][A-Za-z0-9._:@/+-]{0,127}$/.test(candidate.candidate_id)) {
    throw new TypeError('candidate_id is not canonical')
  }
  assertBoundedInt(candidate.predicted_correct_ppm, 0, PPM, 'predicted_correct_ppm')
  assertBoundedInt(candidate.calibration_error_ppm, 0, PPM, 'calibration_error_ppm')
  assertBoundedInt(candidate.latency_ms, 0, Number.MAX_SAFE_INTEGER, 'latency_ms')
  assertBoundedInt(candidate.cost_units, 0, Number.MAX_SAFE_INTEGER, 'cost_units')
}

function requiredReliability(state: ResourceStateV1): number {
  const base = 500_000
  const criticalityPremium = state.criticality * 100_000
  const uncertaintyPremium = Math.floor(state.uncertainty_ppm / 5)
  return Math.min(950_000, base + criticalityPremium + uncertaintyPremium)
}

function normalizedPenalty(value: number, max: number): number {
  const scaled = Number((BigInt(value) * BigInt(PPM)) / BigInt(max))
  return Math.min(PPM, scaled)
}

function candidateReliability(candidate: RouteCandidateV1): number {
  return Math.max(0, candidate.predicted_correct_ppm - candidate.calibration_error_ppm)
}

function candidateScore(candidate: RouteCandidateV1, state: ResourceStateV1): number {
  const reliability = candidateReliability(candidate)
  const latencyPenalty = normalizedPenalty(candidate.latency_ms, state.max_latency_ms)
  const costPenalty = normalizedPenalty(candidate.cost_units, state.max_cost_units)
  const resourcePenalty = Math.floor(
    (latencyPenalty + costPenalty) / (state.criticality + 1),
  )
  return reliability - resourcePenalty
}

function baseDecision(
  state: ResourceStateV1,
  outcome: ResourceRouteDecisionV1['outcome'],
  selectedCandidateId: string | null,
  considered: readonly string[],
  reason: ResourceRouteDecisionV1['reason'],
  selectedScore: number | null,
): ResourceRouteDecisionV1 {
  return Object.freeze({
    schema_version: RAR_SCHEMA_VERSION,
    outcome,
    selected_candidate_id: selectedCandidateId,
    considered_candidate_ids: Object.freeze([...considered]),
    reason,
    required_reliability_ppm: requiredReliability(state),
    selected_score: selectedScore,
    t3_research_only: T3_RESEARCH_ONLY,
    write_back_authority: WRITE_BACK_AUTHORITY,
    authority_effect: RAR_AUTHORITY_EFFECT,
  })
}

export function selectResourceAwareRouteV1(
  state: ResourceStateV1,
  candidates: readonly RouteCandidateV1[],
): ResourceRouteDecisionV1 {
  assertResourceState(state)
  candidates.forEach(assertCandidate)

  const authorityAdmitted = candidates.filter(candidate => candidate.authority_admitted)
  if (authorityAdmitted.length === 0) {
    return baseDecision(
      state, 'ABSTAIN', null, [], 'NO_AUTHORITY_ADMITTED_CANDIDATE', null,
    )
  }

  const withinBudget = authorityAdmitted.filter(candidate =>
    candidate.latency_ms <= state.max_latency_ms
    && candidate.cost_units <= state.max_cost_units
  )
  if (withinBudget.length === 0) {
    return baseDecision(
      state,
      'ABSTAIN',
      null,
      authorityAdmitted.map(candidate => candidate.candidate_id),
      'NO_CANDIDATE_WITHIN_BUDGET',
      null,
    )
  }

  const required = requiredReliability(state)
  const reliable = withinBudget.filter(candidate => candidateReliability(candidate) >= required)
  if (reliable.length === 0) {
    return baseDecision(
      state,
      'ABSTAIN',
      null,
      withinBudget.map(candidate => candidate.candidate_id),
      'INSUFFICIENT_RELIABILITY',
      null,
    )
  }

  const ranked = reliable
    .map(candidate => ({ candidate, score: candidateScore(candidate, state) }))
    .sort((a, b) =>
      b.score - a.score
      || a.candidate.cost_units - b.candidate.cost_units
      || a.candidate.latency_ms - b.candidate.latency_ms
      || a.candidate.candidate_id.localeCompare(b.candidate.candidate_id)
    )

  const selected = ranked[0]
  if (!selected) {
    return baseDecision(state, 'ABSTAIN', null, [], 'INSUFFICIENT_RELIABILITY', null)
  }

  return baseDecision(
    state,
    'ROUTED',
    selected.candidate.candidate_id,
    reliable.map(candidate => candidate.candidate_id),
    'SELECTED',
    selected.score,
  )
}

export function selectStaticAdmittedRouteV1(
  state: ResourceStateV1,
  candidates: readonly RouteCandidateV1[],
): ResourceRouteDecisionV1 {
  assertResourceState(state)
  candidates.forEach(assertCandidate)
  const selected = candidates.find(candidate => candidate.authority_admitted)
  if (!selected) {
    return baseDecision(
      state, 'ABSTAIN', null, [], 'NO_AUTHORITY_ADMITTED_CANDIDATE', null,
    )
  }
  if (selected.latency_ms > state.max_latency_ms || selected.cost_units > state.max_cost_units) {
    return baseDecision(
      state,
      'ABSTAIN',
      null,
      [selected.candidate_id],
      'NO_CANDIDATE_WITHIN_BUDGET',
      null,
    )
  }
  return baseDecision(
    state,
    'ROUTED',
    selected.candidate_id,
    [selected.candidate_id],
    'SELECTED',
    candidateScore(selected, state),
  )
}
