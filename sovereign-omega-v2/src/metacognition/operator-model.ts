// ============================================================
// SOVEREIGN OMEGA — Evidence-Bounded Operator Meta-Model
// EPISTEMIC TIER: T2
//
// Purpose:
//   Keep latent inferences about the operator/user separate from
//   content-risk routing and from claims that may be stated as fact.
//
// Root law:
//   HYPOTHESIS != AUTHORITY
//   ROUTING_BASIS != RESPONSE_CLAIM
//   CONTENT_RISK != USER_STATE
//
// A safety route may be selected from content-risk evidence without
// asserting an unsupported psychological/user-state claim.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const OPERATOR_META_MODEL_SCHEMA_VERSION = '1.0.0' as const

export type MetaEvidenceKind =
  | 'USER_UTTERANCE'
  | 'EXPLICIT_USER_CONFIRMATION'
  | 'BEHAVIORAL_OBSERVATION'
  | 'SYSTEM_SIGNAL'
  | 'EXTERNAL_RECORD'

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

export interface MetaEvidence {
  readonly id: string
  readonly kind: MetaEvidenceKind
  readonly summary: string
  readonly source_ref: string
  readonly content_hash?: SHA256Hex
}

export interface MetaHypothesis {
  readonly id: string
  readonly domain: MetaHypothesisDomain
  readonly proposition: string
  readonly status: MetaEpistemicStatus
  readonly evidence_refs: readonly string[]
  /** Advisory model score only. Never elevates authority by itself. */
  readonly model_confidence_bps?: number
}

export interface MetaModelDecision {
  readonly route: MetaRoute
  /** Hypotheses used to choose a route. */
  readonly route_hypothesis_ids: readonly string[]
  /** Hypotheses whose propositions may be surfaced as factual claims. */
  readonly response_claim_hypothesis_ids: readonly string[]
}

export interface MetaModelCertificate {
  readonly is_valid: boolean
  readonly violations: readonly string[]
  readonly hypothesis_authority: Readonly<Record<string, MetaAuthority>>
  readonly decision_hash: SHA256Hex
  readonly schema_version: typeof OPERATOR_META_MODEL_SCHEMA_VERSION
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
    // Content risk may govern routing, but is never evidence of user state.
    return hypothesis.status === 'SUPPORTED' ? 'ROUTING_ONLY' : 'ADVISORY'
  }

  if (hypothesis.domain === 'USER_STATE') {
    // Fail closed: a model may hypothesize user state, but may not assert it
    // as fact unless the user explicitly confirmed that state.
    return hypothesis.status === 'SUPPORTED' && hasExplicitConfirmation(hypothesis, evidenceById)
      ? 'ASSERTABLE'
      : 'ADVISORY'
  }

  if (hypothesis.domain === 'USER_INTENT' || hypothesis.domain === 'USER_PREFERENCE') {
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

/**
 * Certifies that a routing decision does not silently promote a latent
 * operator/user hypothesis into factual authority.
 */
export async function certifyMetaModelDecision(
  evidence: readonly MetaEvidence[],
  hypotheses: readonly MetaHypothesis[],
  decision: MetaModelDecision,
): Promise<MetaModelCertificate> {
  const violations: string[] = []

  const duplicateEvidence = duplicateIds(evidence.map(e => e.id))
  const duplicateHypotheses = duplicateIds(hypotheses.map(h => h.id))
  if (duplicateEvidence.length) violations.push(`duplicate evidence ids: ${duplicateEvidence.join(',')}`)
  if (duplicateHypotheses.length) violations.push(`duplicate hypothesis ids: ${duplicateHypotheses.join(',')}`)

  const evidenceById = new Map(evidence.map(e => [e.id, e] as const))
  const hypothesisById = new Map(hypotheses.map(h => [h.id, h] as const))
  const authority: Record<string, MetaAuthority> = {}

  for (const hypothesis of hypotheses) {
    for (const ref of hypothesis.evidence_refs) {
      if (!evidenceById.has(ref)) {
        violations.push(`hypothesis ${hypothesis.id} references missing evidence ${ref}`)
      }
    }

    if (
      hypothesis.model_confidence_bps !== undefined &&
      (!Number.isInteger(hypothesis.model_confidence_bps) ||
        hypothesis.model_confidence_bps < 0 ||
        hypothesis.model_confidence_bps > 10_000)
    ) {
      violations.push(`hypothesis ${hypothesis.id} has invalid model_confidence_bps`)
    }

    authority[hypothesis.id] = deriveMetaAuthority(hypothesis, evidenceById)
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
      // Clarification is the permitted response to unresolved/advisory hypotheses.
      if (a === 'NONE') violations.push(`clarify route ${id} has no evidential basis`)
    } else if (decision.route === 'DEFAULT' && a === 'NONE') {
      violations.push(`default route ${id} has no evidential basis`)
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

  const decision_hash = await hashValue({
    schema_version: OPERATOR_META_MODEL_SCHEMA_VERSION,
    evidence,
    hypotheses,
    decision,
    hypothesis_authority: authority,
    violations,
  })

  return deepFreeze<MetaModelCertificate>({
    is_valid: violations.length === 0,
    violations: Object.freeze([...violations]),
    hypothesis_authority: deepFreeze({ ...authority }),
    decision_hash,
    schema_version: OPERATOR_META_MODEL_SCHEMA_VERSION,
  })
}
