// AEGIS Enterprise Opportunity Pipeline V1
// Commercial state is evidence-derived. Drafts, provider claims, or missing
// instrumentation cannot silently advance an opportunity or grant authority.

export type EnterpriseOpportunityStageV1 =
  | 'DISCOVERED'
  | 'CONTACTED'
  | 'QUALIFIED_REPLY'
  | 'SCOPING_CALL_HELD'
  | 'WRITTEN_SCOPE_AGREED'
  | 'PAYMENT_RECEIVED'
  | 'AUDIT_STARTED'
  | 'CLOSED_LOST'

export type EnterpriseOpportunityEvidenceKindV1 =
  | 'DISCOVERY'
  | 'OUTBOUND_SENT'
  | 'QUALIFYING_REPLY'
  | 'SCOPING_CALL'
  | 'SCOPE_AGREEMENT'
  | 'PAYMENT_RECORD'
  | 'AUDIT_START'
  | 'LOSS_REASON'

export type OpportunityEvidenceAuthorityV1 =
  | 'DIRECT_OBSERVATION'
  | 'PROVIDER_ATTESTATION'
  | 'DERIVED_FROM_VERIFIED'
  | 'UNVERIFIED'

export type EnterpriseCommercialActionV1 =
  | 'DRAFT_OUTREACH'
  | 'SEND_OUTREACH'
  | 'DRAFT_SCOPE'
  | 'SEND_SCOPE_WITH_TERMS'
  | 'REQUEST_PAYMENT'
  | 'START_AUDIT'
  | 'ANALYZE_PIPELINE'

export type EnterpriseCommercialActionClassV1 =
  | 'DRAFT'
  | 'ANALYZE'
  | 'EXTERNAL_MESSAGE'
  | 'LEGAL_COMMITMENT'
  | 'FINANCIAL'
  | 'PROPOSE'

export interface EnterpriseOpportunityEvidenceV1 {
  readonly evidence_id: string
  readonly kind: EnterpriseOpportunityEvidenceKindV1
  readonly authority: OpportunityEvidenceAuthorityV1
  readonly source_ref: string
  readonly observed_generation: string
}

export interface EnterpriseOpportunityV1 {
  readonly schema_version: '1.0.0'
  readonly opportunity_id: string
  readonly account_name: string
  readonly stage: EnterpriseOpportunityStageV1
  readonly evidence_refs: readonly string[]
  readonly external_authority: 'NOT_GRANTED'
  readonly authority_effect: 'NONE'
}

const STAGE_ORDER: readonly EnterpriseOpportunityStageV1[] = [
  'DISCOVERED',
  'CONTACTED',
  'QUALIFIED_REPLY',
  'SCOPING_CALL_HELD',
  'WRITTEN_SCOPE_AGREED',
  'PAYMENT_RECEIVED',
  'AUDIT_STARTED',
]

const REQUIRED_EVIDENCE: Readonly<Record<Exclude<EnterpriseOpportunityStageV1, 'CLOSED_LOST'>, EnterpriseOpportunityEvidenceKindV1>> = {
  DISCOVERED: 'DISCOVERY',
  CONTACTED: 'OUTBOUND_SENT',
  QUALIFIED_REPLY: 'QUALIFYING_REPLY',
  SCOPING_CALL_HELD: 'SCOPING_CALL',
  WRITTEN_SCOPE_AGREED: 'SCOPE_AGREEMENT',
  PAYMENT_RECEIVED: 'PAYMENT_RECORD',
  AUDIT_STARTED: 'AUDIT_START',
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty`)
  return value
}

function generation(value: unknown, label: string): bigint {
  const parsed = BigInt(text(value, label))
  if (parsed < 0n) throw new TypeError(`${label} must be non-negative`)
  return parsed
}

function validateEvidence(raw: readonly EnterpriseOpportunityEvidenceV1[]): readonly EnterpriseOpportunityEvidenceV1[] {
  if (!Array.isArray(raw)) throw new TypeError('evidence must be an array')
  const seen = new Set<string>()
  return Object.freeze(raw.map((item) => {
    const evidence_id = text(item?.evidence_id, 'evidence_id')
    if (seen.has(evidence_id)) throw new TypeError('duplicate evidence_id')
    seen.add(evidence_id)
    if (!['DISCOVERY','OUTBOUND_SENT','QUALIFYING_REPLY','SCOPING_CALL','SCOPE_AGREEMENT','PAYMENT_RECORD','AUDIT_START','LOSS_REASON'].includes(item.kind)) {
      throw new TypeError('invalid evidence kind')
    }
    if (!['DIRECT_OBSERVATION','PROVIDER_ATTESTATION','DERIVED_FROM_VERIFIED','UNVERIFIED'].includes(item.authority)) {
      throw new TypeError('invalid evidence authority')
    }
    const source_ref = text(item.source_ref, 'source_ref')
    const observed_generation = generation(item.observed_generation, 'observed_generation').toString()
    return Object.freeze({ ...structuredClone(item), evidence_id, source_ref, observed_generation })
  }))
}

function admissibleForStage(kind: EnterpriseOpportunityEvidenceKindV1, authority: OpportunityEvidenceAuthorityV1): boolean {
  if (kind === 'PAYMENT_RECORD' || kind === 'AUDIT_START' || kind === 'OUTBOUND_SENT') {
    return authority === 'DIRECT_OBSERVATION'
  }
  return authority === 'DIRECT_OBSERVATION' || authority === 'DERIVED_FROM_VERIFIED'
}

export function createEnterpriseOpportunityV1(input: {
  readonly opportunity_id: string
  readonly account_name: string
  readonly discovery_evidence: EnterpriseOpportunityEvidenceV1
}): EnterpriseOpportunityV1 {
  const evidence = validateEvidence([input.discovery_evidence])
  const first = evidence[0]
  if (first.kind !== 'DISCOVERY' || !admissibleForStage(first.kind, first.authority)) {
    throw new Error('DISCOVERY_EVIDENCE_NOT_ADMISSIBLE')
  }
  return Object.freeze({
    schema_version: '1.0.0',
    opportunity_id: text(input.opportunity_id, 'opportunity_id'),
    account_name: text(input.account_name, 'account_name'),
    stage: 'DISCOVERED',
    evidence_refs: Object.freeze([first.evidence_id]),
    external_authority: 'NOT_GRANTED',
    authority_effect: 'NONE',
  })
}

export function advanceEnterpriseOpportunityV1(
  current: EnterpriseOpportunityV1,
  target: EnterpriseOpportunityStageV1,
  evidenceInput: readonly EnterpriseOpportunityEvidenceV1[],
): EnterpriseOpportunityV1 {
  if (current?.schema_version !== '1.0.0' || current.external_authority !== 'NOT_GRANTED' || current.authority_effect !== 'NONE') {
    throw new TypeError('opportunity authority invariant violated')
  }
  const opportunity_id = text(current.opportunity_id, 'opportunity_id')
  const account_name = text(current.account_name, 'account_name')
  const evidence = validateEvidence(evidenceInput)

  if (target === 'CLOSED_LOST') {
    const loss = evidence.find((item) => item.kind === 'LOSS_REASON' && admissibleForStage(item.kind, item.authority))
    if (!loss) throw new Error('LOSS_REASON_EVIDENCE_REQUIRED')
    return Object.freeze({
      ...structuredClone(current),
      opportunity_id,
      account_name,
      stage: target,
      evidence_refs: Object.freeze([...current.evidence_refs, loss.evidence_id]),
      external_authority: 'NOT_GRANTED',
      authority_effect: 'NONE',
    })
  }

  const from = STAGE_ORDER.indexOf(current.stage)
  const to = STAGE_ORDER.indexOf(target)
  if (from < 0 || to < 0 || to !== from + 1) throw new Error('OPPORTUNITY_STAGE_SKIP_DENIED')

  const requiredKind = REQUIRED_EVIDENCE[target]
  const admitted = evidence.find((item) => item.kind === requiredKind && admissibleForStage(item.kind, item.authority))
  if (!admitted) throw new Error(`REQUIRED_EVIDENCE_MISSING:${requiredKind}`)
  if (current.evidence_refs.includes(admitted.evidence_id)) throw new Error('EVIDENCE_REUSE_DENIED')

  return Object.freeze({
    ...structuredClone(current),
    opportunity_id,
    account_name,
    stage: target,
    evidence_refs: Object.freeze([...current.evidence_refs, admitted.evidence_id]),
    external_authority: 'NOT_GRANTED',
    authority_effect: 'NONE',
  })
}

export function classifyEnterpriseCommercialActionV1(
  action: EnterpriseCommercialActionV1,
): Readonly<{
  action: EnterpriseCommercialActionV1
  action_class: EnterpriseCommercialActionClassV1
  operator_grant_required: boolean
  authority_effect: 'NONE'
}> {
  const classes: Readonly<Record<EnterpriseCommercialActionV1, EnterpriseCommercialActionClassV1>> = {
    DRAFT_OUTREACH: 'DRAFT',
    SEND_OUTREACH: 'EXTERNAL_MESSAGE',
    DRAFT_SCOPE: 'DRAFT',
    SEND_SCOPE_WITH_TERMS: 'LEGAL_COMMITMENT',
    REQUEST_PAYMENT: 'FINANCIAL',
    START_AUDIT: 'PROPOSE',
    ANALYZE_PIPELINE: 'ANALYZE',
  }
  if (!(action in classes)) throw new TypeError('invalid enterprise commercial action')
  const action_class = classes[action]
  return Object.freeze({
    action,
    action_class,
    operator_grant_required: ['EXTERNAL_MESSAGE','LEGAL_COMMITMENT','FINANCIAL'].includes(action_class),
    authority_effect: 'NONE',
  })
}
