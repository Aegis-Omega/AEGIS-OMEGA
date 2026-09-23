// AEGIS Enterprise Mail Ingestion V1
// Pure evidence mapping: observed mail can propose pipeline transitions and metrics.
// This module cannot send mail, mutate CRM/DB state, infer payment, or grant authority.

import type {
  EnterpriseOpportunityEvidenceKindV1,
  EnterpriseOpportunityStageV1,
  OpportunityEvidenceAuthorityV1,
} from './company-enterprise-opportunity.js'

export type EnterpriseMailDirectionV1 = 'INBOUND' | 'OUTBOUND'
export type EnterpriseMailStateV1 = 'SENT' | 'DRAFT' | 'RECEIVED'
export type EnterpriseMailClassificationV1 =
  | 'OUTREACH'
  | 'QUALIFYING_REPLY'
  | 'NONQUALIFYING_REPLY'
  | 'OTHER'

export interface EnterpriseMailObservationV1 {
  readonly provider: 'GMAIL' | 'OUTLOOK'
  readonly message_id: string
  readonly thread_id: string
  readonly direction: EnterpriseMailDirectionV1
  readonly mail_state: EnterpriseMailStateV1
  readonly classification: EnterpriseMailClassificationV1
  readonly observed_generation: string
}

export interface EnterpriseMailTransitionProposalV1 {
  readonly from_stage: EnterpriseOpportunityStageV1
  readonly target_stage: EnterpriseOpportunityStageV1
  readonly evidence_kind: EnterpriseOpportunityEvidenceKindV1
  readonly evidence_authority: OpportunityEvidenceAuthorityV1
  readonly evidence_ref: string
  readonly source_system: 'gmail' | 'outlook'
  readonly source_object_id: string
  readonly observed_generation: string
  readonly external_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

export interface EnterpriseOutboundMetricV1 {
  readonly metric: 'outbound_to_qualified_reply'
  readonly outbound_sent: number
  readonly qualified_replies: number
  readonly rate: number | null
  readonly measurement_state: 'MEASURED'
  readonly denominator_source: 'OBSERVED_SENT_LOG'
  readonly landing_page_visits_used: false
  readonly authority_effect: 'NONE'
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function generation(value: unknown): string {
  const parsed = BigInt(text(value, 'observed_generation'))
  if (parsed < 0n) throw new TypeError('observed_generation must be non-negative')
  return parsed.toString()
}

function validateObservation(raw: EnterpriseMailObservationV1): EnterpriseMailObservationV1 {
  if (!['GMAIL','OUTLOOK'].includes(raw?.provider)) throw new TypeError('invalid mail provider')
  if (!['INBOUND','OUTBOUND'].includes(raw?.direction)) throw new TypeError('invalid mail direction')
  if (!['SENT','DRAFT','RECEIVED'].includes(raw?.mail_state)) throw new TypeError('invalid mail_state')
  if (!['OUTREACH','QUALIFYING_REPLY','NONQUALIFYING_REPLY','OTHER'].includes(raw?.classification)) {
    throw new TypeError('invalid mail classification')
  }
  return Object.freeze({
    ...structuredClone(raw),
    message_id: text(raw.message_id, 'message_id'),
    thread_id: text(raw.thread_id, 'thread_id'),
    observed_generation: generation(raw.observed_generation),
  })
}

function sourceSystem(provider: EnterpriseMailObservationV1['provider']): 'gmail' | 'outlook' {
  return provider === 'GMAIL' ? 'gmail' : 'outlook'
}

export function proposeEnterpriseTransitionFromMailV1(
  currentStage: EnterpriseOpportunityStageV1,
  raw: EnterpriseMailObservationV1,
): EnterpriseMailTransitionProposalV1 | null {
  const observation = validateObservation(raw)
  const source_system = sourceSystem(observation.provider)
  const evidence_ref = `${source_system}:${observation.message_id}`

  if (
    currentStage === 'DISCOVERED' &&
    observation.direction === 'OUTBOUND' &&
    observation.mail_state === 'SENT' &&
    observation.classification === 'OUTREACH'
  ) {
    return Object.freeze({
      from_stage: currentStage,
      target_stage: 'CONTACTED',
      evidence_kind: 'OUTBOUND_SENT',
      evidence_authority: 'DIRECT_OBSERVATION',
      evidence_ref,
      source_system,
      source_object_id: observation.message_id,
      observed_generation: observation.observed_generation,
      external_authority: 'NOT_GRANTED',
      authority_effect: 'NONE',
    })
  }

  if (
    currentStage === 'CONTACTED' &&
    observation.direction === 'INBOUND' &&
    observation.mail_state === 'RECEIVED' &&
    observation.classification === 'QUALIFYING_REPLY'
  ) {
    return Object.freeze({
      from_stage: currentStage,
      target_stage: 'QUALIFIED_REPLY',
      evidence_kind: 'QUALIFYING_REPLY',
      evidence_authority: 'DERIVED_FROM_VERIFIED',
      evidence_ref,
      source_system,
      source_object_id: observation.message_id,
      observed_generation: observation.observed_generation,
      external_authority: 'NOT_GRANTED',
      authority_effect: 'NONE',
    })
  }

  return null
}

export function deriveEnterpriseOutboundMetricV1(
  raw: readonly EnterpriseMailObservationV1[],
): EnterpriseOutboundMetricV1 {
  if (!Array.isArray(raw)) throw new TypeError('mail observations must be an array')
  const observations = raw.map(validateObservation)
  const messageIds = new Set<string>()
  for (const item of observations) {
    const key = `${item.provider}:${item.message_id}`
    if (messageIds.has(key)) throw new Error('DUPLICATE_MAIL_OBSERVATION')
    messageIds.add(key)
  }

  const sentThreads = new Set(
    observations
      .filter((item) =>
        item.direction === 'OUTBOUND' &&
        item.mail_state === 'SENT' &&
        item.classification === 'OUTREACH')
      .map((item) => `${item.provider}:${item.thread_id}`),
  )

  const qualifyingReplyThreads = new Set(
    observations
      .filter((item) =>
        item.direction === 'INBOUND' &&
        item.mail_state === 'RECEIVED' &&
        item.classification === 'QUALIFYING_REPLY')
      .map((item) => `${item.provider}:${item.thread_id}`)
      .filter((thread) => sentThreads.has(thread)),
  )

  const outbound_sent = sentThreads.size
  const qualified_replies = qualifyingReplyThreads.size
  return Object.freeze({
    metric: 'outbound_to_qualified_reply',
    outbound_sent,
    qualified_replies,
    rate: outbound_sent === 0 ? null : qualified_replies / outbound_sent,
    measurement_state: 'MEASURED',
    denominator_source: 'OBSERVED_SENT_LOG',
    landing_page_visits_used: false,
    authority_effect: 'NONE',
  })
}
