// ============================================================
// AEGIS Scale OS — Metacognitive Ecosystem Contract V1
// EPISTEMIC TIER: T1 — deterministic authority and evidence rules
// ============================================================

export const METACOGNITIVE_ECOSYSTEM_SCHEMA_VERSION = '1.0.0' as const

export type EcosystemAdapterKindV1 =
  | 'MODEL'
  | 'TOOL'
  | 'CONNECTOR'
  | 'RUNTIME'
  | 'VERIFIER'
  | 'HUMAN_OPERATOR'

export type EcosystemAuthorityV1 =
  | 'OBSERVE'
  | 'PROPOSE'
  | 'VERIFY'
  | 'EXECUTE_REVERSIBLE'
  | 'EXECUTE_CONSEQUENTIAL'

export type EcosystemEvidenceStateV1 =
  | 'UNKNOWN'
  | 'DISCOVERED'
  | 'CONTENT_READ'
  | 'WIRED'
  | 'EXECUTED'
  | 'VERIFIED'
  | 'REJECTED'

export interface EcosystemCapabilityV1 {
  capability_id: string
  description: string
  maximum_authority: EcosystemAuthorityV1
  reversible: boolean
  requires_operator_approval: boolean
  requires_independent_verification: boolean
}

export interface EcosystemAdapterManifestV1 {
  schema_version: typeof METACOGNITIVE_ECOSYSTEM_SCHEMA_VERSION
  adapter_id: string
  adapter_kind: EcosystemAdapterKindV1
  provider: string
  version: string
  capabilities: readonly EcosystemCapabilityV1[]
  evidence_state: EcosystemEvidenceStateV1
  source_locator: string
  content_digest: string | null
  observed_at: string
}

export interface EcosystemIntentV1 {
  intent_id: string
  requester_adapter_id: string
  capability_id: string
  requested_authority: EcosystemAuthorityV1
  target: string
  evidence_refs: readonly string[]
  operator_approval_ref: string | null
  independent_verification_ref: string | null
}

export interface EcosystemAdmissionDecisionV1 {
  admitted: boolean
  reason:
    | 'ADMITTED'
    | 'ADAPTER_NOT_FOUND'
    | 'CAPABILITY_NOT_DECLARED'
    | 'AUTHORITY_EXCEEDS_CAPABILITY'
    | 'EVIDENCE_INSUFFICIENT'
    | 'OPERATOR_APPROVAL_REQUIRED'
    | 'INDEPENDENT_VERIFICATION_REQUIRED'
  effective_authority: EcosystemAuthorityV1 | null
}

const AUTHORITY_RANK: Readonly<Record<EcosystemAuthorityV1, number>> = {
  OBSERVE: 0,
  PROPOSE: 1,
  VERIFY: 2,
  EXECUTE_REVERSIBLE: 3,
  EXECUTE_CONSEQUENTIAL: 4,
}

const EVIDENCE_RANK: Readonly<Record<EcosystemEvidenceStateV1, number>> = {
  UNKNOWN: 0,
  DISCOVERED: 1,
  CONTENT_READ: 2,
  WIRED: 3,
  EXECUTED: 4,
  VERIFIED: 5,
  REJECTED: -1,
}

function isNonEmpty(value: string): boolean {
  return value.trim().length > 0
}

export function assertEcosystemAdapterManifestV1(
  manifest: EcosystemAdapterManifestV1,
): void {
  if (manifest.schema_version !== METACOGNITIVE_ECOSYSTEM_SCHEMA_VERSION) {
    throw new TypeError(`unsupported ecosystem schema: ${manifest.schema_version}`)
  }
  for (const [field, value] of [
    ['adapter_id', manifest.adapter_id],
    ['provider', manifest.provider],
    ['version', manifest.version],
    ['source_locator', manifest.source_locator],
    ['observed_at', manifest.observed_at],
  ] as const) {
    if (!isNonEmpty(value)) throw new TypeError(`${field} must be non-empty`)
  }
  if (Number.isNaN(Date.parse(manifest.observed_at))) {
    throw new TypeError('observed_at must be a valid timestamp')
  }
  const seen = new Set<string>()
  for (const capability of manifest.capabilities) {
    if (!isNonEmpty(capability.capability_id)) {
      throw new TypeError('capability_id must be non-empty')
    }
    if (!isNonEmpty(capability.description)) {
      throw new TypeError('capability description must be non-empty')
    }
    if (seen.has(capability.capability_id)) {
      throw new TypeError(`duplicate capability_id: ${capability.capability_id}`)
    }
    seen.add(capability.capability_id)
    if (
      capability.maximum_authority === 'EXECUTE_CONSEQUENTIAL'
      && !capability.requires_operator_approval
    ) {
      throw new TypeError('consequential capability must require operator approval')
    }
  }
}

export function admitEcosystemIntentV1(
  manifests: readonly EcosystemAdapterManifestV1[],
  intent: EcosystemIntentV1,
): EcosystemAdmissionDecisionV1 {
  const adapter = manifests.find(item => item.adapter_id === intent.requester_adapter_id)
  if (!adapter) {
    return { admitted: false, reason: 'ADAPTER_NOT_FOUND', effective_authority: null }
  }
  assertEcosystemAdapterManifestV1(adapter)

  const capability = adapter.capabilities.find(
    item => item.capability_id === intent.capability_id,
  )
  if (!capability) {
    return { admitted: false, reason: 'CAPABILITY_NOT_DECLARED', effective_authority: null }
  }

  if (AUTHORITY_RANK[intent.requested_authority] > AUTHORITY_RANK[capability.maximum_authority]) {
    return { admitted: false, reason: 'AUTHORITY_EXCEEDS_CAPABILITY', effective_authority: null }
  }

  const requiredEvidence = intent.requested_authority === 'OBSERVE' ? 1 : 2
  if (
    EVIDENCE_RANK[adapter.evidence_state] < requiredEvidence
    || (intent.requested_authority !== 'OBSERVE' && intent.evidence_refs.length === 0)
  ) {
    return { admitted: false, reason: 'EVIDENCE_INSUFFICIENT', effective_authority: null }
  }

  if (capability.requires_operator_approval && intent.operator_approval_ref === null) {
    return { admitted: false, reason: 'OPERATOR_APPROVAL_REQUIRED', effective_authority: null }
  }

  if (
    capability.requires_independent_verification
    && intent.independent_verification_ref === null
  ) {
    return {
      admitted: false,
      reason: 'INDEPENDENT_VERIFICATION_REQUIRED',
      effective_authority: null,
    }
  }

  return {
    admitted: true,
    reason: 'ADMITTED',
    effective_authority: intent.requested_authority,
  }
}

export function reconcileEcosystemEvidenceStateV1(
  states: readonly EcosystemEvidenceStateV1[],
): EcosystemEvidenceStateV1 {
  if (states.length === 0) return 'UNKNOWN'
  if (states.includes('REJECTED')) return 'REJECTED'
  return states.reduce((lowest, state) => (
    EVIDENCE_RANK[state] < EVIDENCE_RANK[lowest] ? state : lowest
  ))
}
