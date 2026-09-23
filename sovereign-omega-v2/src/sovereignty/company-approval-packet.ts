// AEGIS Company Consequential Action Approval Packet V1
// Approval is exact-packet authority, never a conversational boolean.

export type ConsequenceRiskV1 = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type ConsequenceCostV1 = 'NONE' | 'BOUNDED' | 'VARIABLE'
export type ConsequentialActionClassV1 =
  | 'EXTERNAL_MESSAGE'
  | 'REPOSITORY_MUTATION'
  | 'MERGE'
  | 'DEPLOY'
  | 'PRODUCTION_CONFIG'
  | 'FINANCIAL'
  | 'LEGAL_COMMITMENT'
  | 'DELETE_DATA'
  | 'IDENTITY_OR_CREDENTIAL'

export interface ConsequentialActionPacketV1 {
  readonly packet_id: string
  readonly task_id: string
  readonly action_class: ConsequentialActionClassV1
  readonly target: string
  readonly action: string
  readonly reason: string
  readonly evidence_refs: readonly string[]
  readonly risk_class: ConsequenceRiskV1
  readonly cost_class: ConsequenceCostV1
  readonly max_cost_minor_units: number | null
  readonly currency: string | null
  readonly rollback: string
  readonly created_generation: string
  readonly expires_generation: string
  readonly authority_effect: 'NONE'
}

export interface ConsequentialActionGrantV1 {
  readonly packet_digest: string
  readonly decision: 'APPROVED'
  readonly grant_id: string
  readonly granted_generation: string
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new TypeError(`${label} must be non-empty`)
  }
  return value
}

function digest(value: unknown, label: string): string {
  if (typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value)) {
    throw new TypeError(`${label} must be lowercase SHA-256 hex`)
  }
  return value
}

function generation(value: unknown, label: string): bigint {
  const parsed = BigInt(text(value, label))
  if (parsed < 0n) throw new TypeError(`${label} must be non-negative`)
  return parsed
}

export async function createConsequentialActionPacketV1(
  input: Omit<ConsequentialActionPacketV1, 'authority_effect'>,
  hash: (domain: string, value: unknown) => Promise<string>,
): Promise<{
  readonly packet: ConsequentialActionPacketV1
  readonly packet_digest: string
}> {
  text(input?.packet_id, 'packet_id')
  text(input?.task_id, 'task_id')
  text(input?.action_class, 'action_class')
  if (![
    'EXTERNAL_MESSAGE',
    'REPOSITORY_MUTATION',
    'MERGE',
    'DEPLOY',
    'PRODUCTION_CONFIG',
    'FINANCIAL',
    'LEGAL_COMMITMENT',
    'DELETE_DATA',
    'IDENTITY_OR_CREDENTIAL',
  ].includes(input.action_class)) {
    throw new TypeError('invalid consequential action_class')
  }
  text(input?.target, 'target')
  text(input?.action, 'action')
  text(input?.reason, 'reason')
  text(input?.rollback, 'rollback')
  const createdGeneration = generation(
    input?.created_generation,
    'created_generation',
  )
  const expiresGeneration = generation(
    input?.expires_generation,
    'expires_generation',
  )
  if (expiresGeneration < createdGeneration) {
    throw new TypeError('expires_generation precedes created_generation')
  }

  if (!Array.isArray(input.evidence_refs) || input.evidence_refs.length === 0) {
    throw new TypeError('evidence_refs must be non-empty')
  }
  const evidence = Object.freeze(
    [...input.evidence_refs].map((value) => text(value, 'evidence_ref')),
  )
  if (new Set(evidence).size !== evidence.length) {
    throw new TypeError('duplicate evidence_ref')
  }

  if (!['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(input.risk_class)) {
    throw new TypeError('invalid risk_class')
  }
  if (!['NONE', 'BOUNDED', 'VARIABLE'].includes(input.cost_class)) {
    throw new TypeError('invalid cost_class')
  }

  if (input.cost_class === 'NONE') {
    if (input.max_cost_minor_units !== null || input.currency !== null) {
      throw new TypeError('cost-free packet must not carry currency or cost')
    }
  } else {
    if (
      typeof input.max_cost_minor_units !== 'number' ||
      !Number.isSafeInteger(input.max_cost_minor_units) ||
      input.max_cost_minor_units < 0
    ) {
      throw new TypeError('cost-bearing packet requires bounded minor units')
    }
    text(input.currency, 'currency')
  }

  const packet = Object.freeze({
    ...structuredClone(input),
    evidence_refs: evidence,
    authority_effect: 'NONE' as const,
  })
  const packet_digest = digest(
    await hash('AEGIS_CONSEQUENTIAL_ACTION_PACKET_V1', packet),
    'packet_digest',
  )
  return Object.freeze({ packet, packet_digest })
}

export async function verifyConsequentialActionGrantV1(
  packetDigest: string,
  packet: ConsequentialActionPacketV1,
  grant: ConsequentialActionGrantV1 | null,
  currentGeneration: string,
  hash: (domain: string, value: unknown) => Promise<string>,
): Promise<boolean> {
  const expected = digest(packetDigest, 'packet_digest')
  const recomputed = digest(
    await hash('AEGIS_CONSEQUENTIAL_ACTION_PACKET_V1', packet),
    'recomputed packet_digest',
  )
  if (recomputed !== expected) return false

  const now = generation(currentGeneration, 'current_generation')
  const created = generation(packet.created_generation, 'created_generation')
  const expires = generation(packet.expires_generation, 'expires_generation')

  if (now < created || now > expires) return false
  if (!grant || grant.decision !== 'APPROVED') return false
  text(grant.grant_id, 'grant_id')
  const granted = generation(grant.granted_generation, 'granted_generation')
  if (granted < created || granted > now || granted > expires) return false
  return digest(grant.packet_digest, 'grant packet_digest') === expected
}
