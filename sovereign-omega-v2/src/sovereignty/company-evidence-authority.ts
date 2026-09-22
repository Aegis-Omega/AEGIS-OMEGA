// AEGIS Company Evidence Authority V1
// Prevents provider attestations and missing instrumentation from being promoted
// into direct observations or numeric KPI claims.

export type EvidenceAuthorityV1 =
  | 'DIRECT_OBSERVATION'
  | 'PROVIDER_ATTESTATION'
  | 'DERIVED_FROM_VERIFIED'
  | 'UNVERIFIED'

export type MeasurementStateV1 =
  | 'MEASURED'
  | 'NOT_MEASURED'
  | 'NOT_VERIFIED'

export interface MetricEvidenceInputV1 {
  readonly metric: string
  readonly source_authority: EvidenceAuthorityV1
  readonly instrumentation_state: 'VERIFIED' | 'ABSENT' | 'UNKNOWN'
  readonly collection_state: 'VERIFIED' | 'ABSENT' | 'UNKNOWN'
  readonly observed_value?: number | null
}

export interface MetricEvidenceDecisionV1 {
  readonly metric: string
  readonly measurement_state: MeasurementStateV1
  readonly admitted_value: number | null
  readonly source_authority: EvidenceAuthorityV1
  readonly numeric_claim_admitted: boolean
  readonly reason: string
  readonly authority_effect: 'NONE'
}

function nonEmpty(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new TypeError(`${label} must be non-empty`)
  }
  return value
}

export function admitMetricEvidenceV1(
  input: MetricEvidenceInputV1,
): MetricEvidenceDecisionV1 {
  const metric = nonEmpty(input?.metric, 'metric')
  const authorities: readonly EvidenceAuthorityV1[] = [
    'DIRECT_OBSERVATION',
    'PROVIDER_ATTESTATION',
    'DERIVED_FROM_VERIFIED',
    'UNVERIFIED',
  ]
  if (!authorities.includes(input.source_authority)) {
    throw new TypeError('invalid source_authority')
  }

  for (const [name, state] of [
    ['instrumentation_state', input.instrumentation_state],
    ['collection_state', input.collection_state],
  ] as const) {
    if (!['VERIFIED', 'ABSENT', 'UNKNOWN'].includes(state)) {
      throw new TypeError(`invalid ${name}`)
    }
  }

  const raw = input.observed_value
  if (raw !== undefined && raw !== null && (
    typeof raw !== 'number' || !Number.isFinite(raw)
  )) {
    throw new TypeError('observed_value must be finite number or null')
  }

  if (
    input.instrumentation_state === 'ABSENT' ||
    input.collection_state === 'ABSENT'
  ) {
    return Object.freeze({
      metric,
      measurement_state: 'NOT_MEASURED',
      admitted_value: null,
      source_authority: input.source_authority,
      numeric_claim_admitted: false,
      reason: 'measurement path absent; numeric value is not evidence',
      authority_effect: 'NONE',
    })
  }

  if (
    input.instrumentation_state !== 'VERIFIED' ||
    input.collection_state !== 'VERIFIED'
  ) {
    return Object.freeze({
      metric,
      measurement_state: 'NOT_VERIFIED',
      admitted_value: null,
      source_authority: input.source_authority,
      numeric_claim_admitted: false,
      reason: 'measurement path not independently verified',
      authority_effect: 'NONE',
    })
  }

  if (input.source_authority === 'UNVERIFIED') {
    return Object.freeze({
      metric,
      measurement_state: 'NOT_VERIFIED',
      admitted_value: null,
      source_authority: input.source_authority,
      numeric_claim_admitted: false,
      reason: 'source has no admitted evidence authority',
      authority_effect: 'NONE',
    })
  }

  if (raw === undefined || raw === null) {
    return Object.freeze({
      metric,
      measurement_state: 'MEASURED',
      admitted_value: null,
      source_authority: input.source_authority,
      numeric_claim_admitted: false,
      reason: 'measurement path verified but no numeric observation supplied',
      authority_effect: 'NONE',
    })
  }

  return Object.freeze({
    metric,
    measurement_state: 'MEASURED',
    admitted_value: raw,
    source_authority: input.source_authority,
    numeric_claim_admitted: true,
    reason: input.source_authority === 'PROVIDER_ATTESTATION'
      ? 'numeric value admitted as provider-attested measurement, not direct observation'
      : 'numeric value admitted within verified measurement path',
    authority_effect: 'NONE',
  })
}

export interface EvidenceClaimV1 {
  readonly claim: string
  readonly authority: EvidenceAuthorityV1
  readonly source_ref: string
}

export function preserveEvidenceAuthorityV1(
  claim: EvidenceClaimV1,
): Readonly<EvidenceClaimV1 & { readonly authority_effect: 'NONE' }> {
  nonEmpty(claim?.claim, 'claim')
  nonEmpty(claim?.source_ref, 'source_ref')
  if (![
    'DIRECT_OBSERVATION',
    'PROVIDER_ATTESTATION',
    'DERIVED_FROM_VERIFIED',
    'UNVERIFIED',
  ].includes(claim.authority)) {
    throw new TypeError('invalid evidence authority')
  }
  return Object.freeze({ ...claim, authority_effect: 'NONE' as const })
}
