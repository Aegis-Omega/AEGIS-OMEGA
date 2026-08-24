// ============================================================
// SOVEREIGN OMEGA — Evidence-Bounded Operator Meta-Model
// EPISTEMIC TIER: T2
//
// Lineage:
//   Obsidian Sovereign Brain (2026-04-11) supplied two precursor laws:
//   - HD = |claimed_correctness - actual_correctness|
//   - NO GUESSING: ambiguity must block/clarify rather than be invented away.
//
// This module translates those knowledge artifacts into a typed operator-model
// boundary. The historical documents remain KNOWLEDGE, not runtime authority;
// the rules below become authority only through this implementation + tests.
//
// Root laws:
//   HYPOTHESIS != AUTHORITY
//   ROUTING_BASIS != RESPONSE_CLAIM
//   CONTENT_RISK != USER_STATE
//   EXTERNAL_BEHAVIOR != INTERNAL_STATE
//   MODEL_CONFIDENCE != EVIDENCE
//   AMBIGUITY != PERMISSION_TO_GUESS
//
// A safety route may be selected from content-risk evidence without asserting
// an unsupported psychological/user-state claim. A persistent policy change
// derived from an operator-state hypothesis requires explicit, repeated,
// independent and calibrated evidence under caller-supplied thresholds.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const OPERATOR_META_MODEL_SCHEMA_VERSION = '1.1.0' as const

export type MetaEvidenceKind =
  | 'USER_UTTERANCE'
  | 'EXPLICIT_USER_CONFIRMATION'
  | 'BEHAVIORAL_OBSERVATION'
  | 'SYSTEM_SIGNAL'
  | 'EXTERNAL_RECORD'

export type MetaEvidenceSurface =
  | 'EXTERNAL'
  | 'INTERNAL'
  | 'USER_REPORTED'

export type MetaHypothesisDomain =
  | 'USER_STATE'
  | 'USER_INTENT'
  | 'USER_PREFERENCE'
  | 'CONTENT_RISK'
  | 'TASK_CONTEXT'

export type MetaEpistemicStatus =
  | 'PROPOSED'
  | 'SUPPORTED'
  | 'CONTRADICTED'
  | 'UNKNOWN'

export type MetaAuthority =
  | 'NONE'
  | 'ADVISORY'
  | 'ROUTING_ONLY'
  | 'ASSERTABLE'

export type MetaRoute =
  | 'DEFAULT'
  | 'CLARIFY'
  | 'SAFETY_CONSERVATIVE'
  | 'BLOCKED'

export interface MetaEvidence {
  readonly id: string
  readonly kind: MetaEvidenceKind
  readonly surface: MetaEvidenceSurface
  readonly summary: string
  readonly source_ref: string
  /**
   * Explicit independence label. Two observations are not independent merely
   * because they are two rows. Omit when independence is not established.
   */
  readonly independence_key?: string
  readonly content_hash?: SHA256Hex
}

export interface MetaCalibration {
  /** Number of independently scored posterior predictions in the calibration set. */
  readonly sample_count: number
  /**
   * Mean Hallucination Delta in basis points:
   * mean(|predicted_correctness_bps - actual_correctness_bps|).
   */
  readonly mean_hd_bps: number
}

export interface MetaCalibrationSample {
  readonly predicted_correctness_bps: number
  readonly actual_correctness_bps: number
}

export interface MetaHypothesis {
  readonly id: string
  readonly domain: MetaHypothesisDomain
  readonly proposition: string
  readonly status: MetaEpistemicStatus
  readonly evidence_refs: readonly string[]
  /** Advisory model score only. Never elevates authority by itself. */
  readonly model_confidence_bps?: number
  /** Empirical calibration of this inference family, if measured. */
  readonly calibration?: MetaCalibration
}

export interface MetaPolicyThresholds {
  /** Caller-selected threshold; deliberately no universal magic number. */
  readonly min_evidence_count: number
  /** Number of explicitly independent signal groups required. */
  readonly min_independent_signal_count: number
  /** Maximum admissible calibration error in basis points. */
  readonly max_mean_hd_bps: number
}

export interface MetaModelDecision {
  readonly route: MetaRoute
  /** Hypotheses used to choose a route. */
  readonly route_hypothesis_ids: readonly string[]
  /** Hypotheses whose propositions may be surfaced as factual claims. */
  readonly response_claim_hypothesis_ids: readonly string[]
  /**
   * Hypotheses proposed as a basis for persistent policy/mode changes. This is
   * intentionally separate from one-turn routing.
   */
  readonly policy_change_hypothesis_ids?: readonly string[]
}

export interface MetaModelCertificate {
  readonly is_valid: boolean
  readonly violations: readonly string[]
  readonly hypothesis_authority: Readonly<Record<string, MetaAuthority>>
  readonly policy_admissible: Readonly<Record<string, boolean>>
  readonly decision_hash: SHA256Hex
  readonly schema_version: typeof OPERATOR_META_MODEL_SCHEMA_VERSION
}

function validBps(value: number): boolean {
  return Number.isInteger(value) && value >= 0 && value <= 10_000
}

/**
 * Obsidian HD generalized to posterior calibration. This is still T2: it is a
 * measurable engineering adaptation, not a claim that one scalar captures all
 * operator-model error.
 */
export function computeMetaModelHallucinationDelta(
  samples: readonly MetaCalibrationSample[],
): MetaCalibration {
  if (samples.length === 0) {
    throw new Error('Meta-model HD requires at least one calibration sample')
  }

  let total = 0
  for (const [i, sample] of samples.entries()) {
    if (!validBps(sample.predicted_correctness_bps) || !validBps(sample.actual_correctness_bps)) {
      throw new Error(`Invalid calibration sample at index ${i}`)
    }
    total += Math.abs(sample.predicted_correctness_bps - sample.actual_correctness_bps)
  }

  return deepFreeze({
    sample_count: samples.length,
    mean_hd_bps: Math.round(total / samples.length),
  })
}

function hasExplicitConfirmation(
  hypothesis: MetaHypothesis,
  evidenceById: ReadonlyMap<string, MetaEvidence>,
): boolean {
  return hypothesis.evidence_refs.some(ref =>
    evidenceById.get(ref)?.kind === 'EXPLICIT_USER_CONFIRMATION',
  )
}

function hasAnyResolvedEvidence(
  hypothesis: MetaHypothesis,
  evidenceById: ReadonlyMap<string, MetaEvidence>,
): boolean {
  return hypothesis.evidence_refs.some(ref => evidenceById.has(ref))
}

function isLatentOperatorDomain(domain: MetaHypothesisDomain): boolean {
  return domain === 'USER_STATE' || domain === 'USER_INTENT' || domain === 'USER_PREFERENCE'
}

/**
 * Authority is derived from evidence class + epistemic status, never from
 * model confidence alone.
 */
export function deriveMetaAuthority(
  hypothesis: MetaHypothesis,
  evidenceById: ReadonlyMap<string, MetaEvidence>,
): MetaAuthority {
  if (hypothesis.status === 'CONTRADICTED' || hypothesis.status === 'UNKNOWN') {
    return 'NONE'
  }

  const hasEvidence = hasAnyResolvedEvidence(hypothesis, evidenceById)
  if (!hasEvidence) return 'NONE'

  if (hypothesis.domain === 'CONTENT_RISK') {
    // Content risk may govern one-turn routing, but is never evidence of user state.
    return hypothesis.status === 'SUPPORTED' ? 'ROUTING_ONLY' : 'ADVISORY'
  }

  if (isLatentOperatorDomain(hypothesis.domain)) {
    // Fail closed: external behavior can motivate a hypothesis but cannot by
    // itself convert that hidden-state hypothesis into an assertable fact.
    return hypothesis.status === 'SUPPORTED' && hasExplicitConfirmation(hypothesis, evidenceById)
      ? 'ASSERTABLE'
      : 'ADVISORY'
  }

  // TASK_CONTEXT may be established from the task itself without converting
  // that context into a claim about the operator's latent state.
  if (hypothesis.domain === 'TASK_CONTEXT') {
    return hypothesis.status === 'SUPPORTED' ? 'ASSERTABLE' : 'ADVISORY'
  }

  return 'NONE'
}

function duplicateIds(values: readonly string[]): string[] {
  const seen = new Set<string>()
  const duplicates = new Set<string>()
  for (const value of values) {
    if (seen.has(value)) duplicates.add(value)
    seen.add(value)
  }
  return [...duplicates].sort()
}

function validatePolicyThresholds(thresholds: MetaPolicyThresholds): string[] {
  const violations: string[] = []
  if (!Number.isInteger(thresholds.min_evidence_count) || thresholds.min_evidence_count < 1) {
    violations.push('policy threshold min_evidence_count must be >= 1')
  }
  if (!Number.isInteger(thresholds.min_independent_signal_count) || thresholds.min_independent_signal_count < 1) {
    violations.push('policy threshold min_independent_signal_count must be >= 1')
  }
  if (!validBps(thresholds.max_mean_hd_bps)) {
    violations.push('policy threshold max_mean_hd_bps must be within 0..10000')
  }
  return violations
}

function resolvedEvidenceFor(
  hypothesis: MetaHypothesis,
  evidenceById: ReadonlyMap<string, MetaEvidence>,
): MetaEvidence[] {
  return hypothesis.evidence_refs
    .map(ref => evidenceById.get(ref))
    .filter((item): item is MetaEvidence => item !== undefined)
}

/**
 * Certifies that a routing decision does not silently promote a latent
 * operator/user hypothesis into factual or policy authority.
 */
export async function certifyMetaModelDecision(
  evidence: readonly MetaEvidence[],
  hypotheses: readonly MetaHypothesis[],
  decision: MetaModelDecision,
  policyThresholds?: MetaPolicyThresholds,
): Promise<MetaModelCertificate> {
  const violations: string[] = []

  const duplicateEvidence = duplicateIds(evidence.map(e => e.id))
  const duplicateHypotheses = duplicateIds(hypotheses.map(h => h.id))
  if (duplicateEvidence.length) violations.push(`duplicate evidence ids: ${duplicateEvidence.join(',')}`)
  if (duplicateHypotheses.length) violations.push(`duplicate hypothesis ids: ${duplicateHypotheses.join(',')}`)

  const evidenceById = new Map(evidence.map(e => [e.id, e] as const))
  const hypothesisById = new Map(hypotheses.map(h => [h.id, h] as const))
  const authority: Record<string, MetaAuthority> = {}
  const policyAdmissible: Record<string, boolean> = {}

  for (const hypothesis of hypotheses) {
    for (const ref of hypothesis.evidence_refs) {
      if (!evidenceById.has(ref)) {
        violations.push(`hypothesis ${hypothesis.id} references missing evidence ${ref}`)
      }
    }

    if (
      hypothesis.model_confidence_bps !== undefined &&
      !validBps(hypothesis.model_confidence_bps)
    ) {
      violations.push(`hypothesis ${hypothesis.id} has invalid model_confidence_bps`)
    }

    if (hypothesis.calibration !== undefined) {
      if (!Number.isInteger(hypothesis.calibration.sample_count) || hypothesis.calibration.sample_count < 1) {
        violations.push(`hypothesis ${hypothesis.id} has invalid calibration sample_count`)
      }
      if (!validBps(hypothesis.calibration.mean_hd_bps)) {
        violations.push(`hypothesis ${hypothesis.id} has invalid calibration mean_hd_bps`)
      }
    }

    authority[hypothesis.id] = deriveMetaAuthority(hypothesis, evidenceById)
    policyAdmissible[hypothesis.id] = false
  }

  for (const id of decision.route_hypothesis_ids) {
    const hypothesis = hypothesisById.get(id)
    if (!hypothesis) {
      violations.push(`route references unknown hypothesis ${id}`)
      continue
    }

    const a = authority[id] ?? 'NONE'

    if (decision.route === 'SAFETY_CONSERVATIVE') {
      if (hypothesis.domain !== 'CONTENT_RISK') {
        violations.push(
          `safety route ${id} uses ${hypothesis.domain}; safety routing must be based on CONTENT_RISK, not latent user state`,
        )
      }
      if (a !== 'ROUTING_ONLY' && a !== 'ASSERTABLE') {
        violations.push(`safety route ${id} lacks routing authority (${a})`)
      }
    } else if (decision.route === 'CLARIFY') {
      // Modern conversational equivalent of the Obsidian NO GUESSING law.
      if (a === 'NONE') violations.push(`clarify route ${id} has no evidential basis`)
    } else if (decision.route === 'BLOCKED') {
      // Consequential execution may stop on ambiguity without pretending the
      // latent hypothesis is true.
      if (!isLatentOperatorDomain(hypothesis.domain) && hypothesis.domain !== 'TASK_CONTEXT') {
        violations.push(`blocked route ${id} is not an ambiguity-bearing hypothesis`)
      }
    } else if (decision.route === 'DEFAULT') {
      if (a === 'NONE') {
        violations.push(`default route ${id} has no evidential basis`)
      }
      if (isLatentOperatorDomain(hypothesis.domain) && a !== 'ASSERTABLE') {
        violations.push(`NO_GUESSING: default route ${id} cannot rely on unresolved ${hypothesis.domain}; CLARIFY or BLOCK`)
      }
    }
  }

  for (const id of decision.response_claim_hypothesis_ids) {
    if (!hypothesisById.has(id)) {
      violations.push(`response claim references unknown hypothesis ${id}`)
      continue
    }
    const a = authority[id] ?? 'NONE'
    if (a !== 'ASSERTABLE') {
      violations.push(`response claim ${id} is not assertable (${a})`)
    }
  }

  const policyIds = decision.policy_change_hypothesis_ids ?? []
  if (policyIds.length > 0 && policyThresholds === undefined) {
    violations.push('policy change requested without explicit policy thresholds')
  }

  if (policyThresholds !== undefined) {
    violations.push(...validatePolicyThresholds(policyThresholds))
  }

  for (const id of policyIds) {
    const hypothesis = hypothesisById.get(id)
    if (!hypothesis) {
      violations.push(`policy change references unknown hypothesis ${id}`)
      continue
    }

    if (!isLatentOperatorDomain(hypothesis.domain)) {
      violations.push(`policy change ${id} must reference a latent operator domain`)
      continue
    }

    const thresholds = policyThresholds
    if (thresholds === undefined) continue

    let admissible = true
    const a = authority[id] ?? 'NONE'
    if (a !== 'ASSERTABLE') {
      violations.push(`policy change ${id} is not assertable (${a})`)
      admissible = false
    }

    const resolved = resolvedEvidenceFor(hypothesis, evidenceById)
    if (resolved.length < thresholds.min_evidence_count) {
      violations.push(
        `policy change ${id} has ${resolved.length} evidence items; requires ${thresholds.min_evidence_count}`,
      )
      admissible = false
    }

    const independentSignals = new Set(
      resolved
        .map(item => item.independence_key)
        .filter((key): key is string => key !== undefined && key.length > 0),
    )
    if (independentSignals.size < thresholds.min_independent_signal_count) {
      violations.push(
        `policy change ${id} has ${independentSignals.size} established independent signals; requires ${thresholds.min_independent_signal_count}`,
      )
      admissible = false
    }

    if (hypothesis.calibration === undefined) {
      violations.push(`policy change ${id} lacks calibration evidence`)
      admissible = false
    } else if (hypothesis.calibration.mean_hd_bps > thresholds.max_mean_hd_bps) {
      violations.push(
        `policy change ${id} calibration HD ${hypothesis.calibration.mean_hd_bps} exceeds ${thresholds.max_mean_hd_bps}`,
      )
      admissible = false
    }

    policyAdmissible[id] = admissible
  }

  const decision_hash = await hashValue({
    schema_version: OPERATOR_META_MODEL_SCHEMA_VERSION,
    evidence,
    hypotheses,
    decision,
    policy_thresholds: policyThresholds ?? null,
    hypothesis_authority: authority,
    policy_admissible: policyAdmissible,
    violations,
  })

  return deepFreeze<MetaModelCertificate>({
    is_valid: violations.length === 0,
    violations: Object.freeze([...violations]),
    hypothesis_authority: deepFreeze({ ...authority }),
    policy_admissible: deepFreeze({ ...policyAdmissible }),
    decision_hash,
    schema_version: OPERATOR_META_MODEL_SCHEMA_VERSION,
  })
}
