import { hashValue } from '../core/hashing.js'

export const MCM_SCHEMA_VERSION = '1.0.0' as const
export const MCM_AUTHORITY_EFFECT = 'OBSERVATION_ONLY' as const
export const MCM_OBSERVATION_TIER = 'T2' as const
export const MCM_AUTHORITY_WEIGHT = 0 as const
export const MCM_MAY_GROUND_STATE_TRANSITION = false as const

export interface McmNodeObservationInputV1 {
  readonly nodeIdentityDigest: string
  readonly sensoriumObservationDigest: string
  readonly observationSequence: number
  readonly expectedParentStateRoot: string
  readonly topologyDigest: string
  readonly calibrationBps: number
  readonly evidenceSupportBps: number
  readonly evidenceFreshnessBps: number
  readonly resourcePressureBps: number
  readonly contradictionPressureBps: number
  readonly verificationDemandBps: number
  readonly evidenceReferences: readonly string[]
}

export interface McmNodeObservationV1 extends McmNodeObservationInputV1 {
  readonly schemaVersion: typeof MCM_SCHEMA_VERSION
  readonly authorityEffect: typeof MCM_AUTHORITY_EFFECT
  readonly observationTier: typeof MCM_OBSERVATION_TIER
  readonly authorityWeight: typeof MCM_AUTHORITY_WEIGHT
  readonly mayGroundStateTransition: typeof MCM_MAY_GROUND_STATE_TRANSITION
  readonly observationDigest: string
}

export type McmVerificationReason =
  | 'LOW_CALIBRATION'
  | 'LOW_EVIDENCE_SUPPORT'
  | 'STALE_EVIDENCE'
  | 'RESOURCE_PRESSURE'
  | 'CONTRADICTION_PRESSURE'
  | 'EXPLICIT_VERIFICATION_DEMAND'

export interface McmVerificationRequestV1 {
  readonly schemaVersion: typeof MCM_SCHEMA_VERSION
  readonly authorityEffect: typeof MCM_AUTHORITY_EFFECT
  readonly observationTier: typeof MCM_OBSERVATION_TIER
  readonly authorityWeight: typeof MCM_AUTHORITY_WEIGHT
  readonly mayGroundStateTransition: typeof MCM_MAY_GROUND_STATE_TRANSITION
  readonly collectiveStateRoot: string
  readonly subjectNodeDigest: string
  readonly priorityBps: number
  readonly reasonCodes: readonly McmVerificationReason[]
  readonly evidenceReferences: readonly string[]
}

export class McmContractError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'McmContractError'
  }
}

const SHA256_HEX = /^[a-f0-9]{64}$/
const AUTHORITY_KEYS = [
  'authorityEffect',
  'observationTier',
  'authorityWeight',
  'mayGroundStateTransition',
] as const

export function assertMcmDigest(name: string, value: string): void {
  if (!SHA256_HEX.test(value)) {
    throw new McmContractError(`${name} must be lowercase SHA-256 hex`)
  }
}

export function assertMcmBps(name: string, value: number): void {
  if (!Number.isSafeInteger(value) || value < 0 || value > 10_000) {
    throw new McmContractError(`${name} must be a safe integer in [0,10000]`)
  }
}

function rejectAuthorityOverrides(input: McmNodeObservationInputV1): void {
  const record = input as unknown as Record<string, unknown>
  for (const key of AUTHORITY_KEYS) {
    if (Object.prototype.hasOwnProperty.call(record, key)) {
      throw new McmContractError(`caller-supplied ${key} is forbidden`)
    }
  }
}

export function canonicalMcmEvidenceReferences(references: readonly string[]): readonly string[] {
  if (references.some(reference => typeof reference !== 'string' || reference.length === 0)) {
    throw new McmContractError('evidence references must be non-empty strings')
  }
  const sorted = [...references].sort()
  for (let index = 1; index < sorted.length; index += 1) {
    if (sorted[index] === sorted[index - 1]) {
      throw new McmContractError('evidence references must be unique')
    }
  }
  return Object.freeze(sorted)
}

function validateObservationCore(input: McmNodeObservationInputV1): readonly string[] {
  assertMcmDigest('nodeIdentityDigest', input.nodeIdentityDigest)
  assertMcmDigest('sensoriumObservationDigest', input.sensoriumObservationDigest)
  assertMcmDigest('expectedParentStateRoot', input.expectedParentStateRoot)
  assertMcmDigest('topologyDigest', input.topologyDigest)
  if (!Number.isSafeInteger(input.observationSequence) || input.observationSequence < 0) {
    throw new McmContractError('observationSequence must be a non-negative safe integer')
  }
  assertMcmBps('calibrationBps', input.calibrationBps)
  assertMcmBps('evidenceSupportBps', input.evidenceSupportBps)
  assertMcmBps('evidenceFreshnessBps', input.evidenceFreshnessBps)
  assertMcmBps('resourcePressureBps', input.resourcePressureBps)
  assertMcmBps('contradictionPressureBps', input.contradictionPressureBps)
  assertMcmBps('verificationDemandBps', input.verificationDemandBps)
  return canonicalMcmEvidenceReferences(input.evidenceReferences)
}

function observationHashPayload(
  input: McmNodeObservationInputV1,
  evidenceReferences: readonly string[],
) {
  return Object.freeze({
    schemaVersion: MCM_SCHEMA_VERSION,
    authorityEffect: MCM_AUTHORITY_EFFECT,
    observationTier: MCM_OBSERVATION_TIER,
    authorityWeight: MCM_AUTHORITY_WEIGHT,
    mayGroundStateTransition: MCM_MAY_GROUND_STATE_TRANSITION,
    nodeIdentityDigest: input.nodeIdentityDigest,
    sensoriumObservationDigest: input.sensoriumObservationDigest,
    observationSequence: input.observationSequence,
    expectedParentStateRoot: input.expectedParentStateRoot,
    topologyDigest: input.topologyDigest,
    calibrationBps: input.calibrationBps,
    evidenceSupportBps: input.evidenceSupportBps,
    evidenceFreshnessBps: input.evidenceFreshnessBps,
    resourcePressureBps: input.resourcePressureBps,
    contradictionPressureBps: input.contradictionPressureBps,
    verificationDemandBps: input.verificationDemandBps,
    evidenceReferences,
  })
}

export function assertMcmObservation(observation: McmNodeObservationV1): void {
  if (observation.schemaVersion !== MCM_SCHEMA_VERSION ||
      observation.authorityEffect !== MCM_AUTHORITY_EFFECT ||
      observation.observationTier !== MCM_OBSERVATION_TIER ||
      observation.authorityWeight !== MCM_AUTHORITY_WEIGHT ||
      observation.mayGroundStateTransition !== MCM_MAY_GROUND_STATE_TRANSITION) {
    throw new McmContractError('MCM constitutional constants mismatch')
  }
  assertMcmDigest('observationDigest', observation.observationDigest)
  validateObservationCore(observation)
}

export async function verifyMcmNodeObservation(observation: McmNodeObservationV1): Promise<void> {
  assertMcmObservation(observation)
  const evidenceReferences = canonicalMcmEvidenceReferences(observation.evidenceReferences)
  const expectedDigest = await hashValue(observationHashPayload(observation, evidenceReferences))
  if (expectedDigest !== observation.observationDigest) {
    throw new McmContractError('MCM observation digest does not match canonical payload')
  }
}

export async function createMcmNodeObservation(
  input: McmNodeObservationInputV1,
): Promise<McmNodeObservationV1> {
  rejectAuthorityOverrides(input)
  const evidenceReferences = validateObservationCore(input)
  const payload = observationHashPayload(input, evidenceReferences)
  const observationDigest = await hashValue(payload)
  return Object.freeze({ ...payload, observationDigest })
}
