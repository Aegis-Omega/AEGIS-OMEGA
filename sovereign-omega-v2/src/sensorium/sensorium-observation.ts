import { sha256Hex } from '../core/hashing.js'
import { capacityPressureBps, nextLogisticLoad, nextRetentionBps } from './vcm-bridge.js'

export type SensoriumSourceKind = 'runtime' | 'telemetry' | 'operator' | 'replay'
export type SensoriumModelStatus = 'MODEL_DEFINED'
export type SensoriumEmpiricalStatus = 'NOT_ESTABLISHED' | 'EMPIRICALLY_VALIDATED'

export interface SensoriumObservationInputV1 {
  readonly sourceKind: SensoriumSourceKind
  readonly sourceIdentityDigest: string
  readonly subjectResourceDigest: string
  readonly observationSequence: number
  readonly expectedParentStateRoot: string
  readonly topologyDigest: string
  readonly activeLoad: bigint
  readonly carryingCapacity: bigint
  readonly growthRateBps: number
  readonly retentionBps: number
  readonly decayBps: number
  readonly reinforcementBps: number
  readonly observationQualityBps: number
  readonly evidenceReferences: readonly string[]
  readonly auditObservedAt?: string | undefined
}

export interface SensoriumObservationPayloadV1 {
  readonly schemaVersion: '1.0.0'
  readonly authorityEffect: 'OBSERVATION_ONLY'
  readonly observationTier: 'T2'
  readonly authorityWeight: 0
  readonly mayGroundStateTransition: false
  readonly sourceKind: SensoriumSourceKind
  readonly sourceIdentityDigest: string
  readonly subjectResourceDigest: string
  readonly observationSequence: number
  readonly expectedParentStateRoot: string
  readonly topologyDigest: string
  readonly activeLoad: bigint
  readonly carryingCapacity: bigint
  readonly growthRateBps: number
  readonly retentionBps: number
  readonly decayBps: number
  readonly reinforcementBps: number
  readonly observationQualityBps: number
  readonly predictedNextLoad: bigint
  readonly capacityPressureBps: number
  readonly predictedNextRetentionBps: number
  readonly evidenceReferences: readonly string[]
  readonly modelStatus: SensoriumModelStatus
  readonly empiricalStatus: SensoriumEmpiricalStatus
}

export interface SensoriumObservationV1 extends SensoriumObservationPayloadV1 {
  readonly observationId: string
  readonly observationDigest: string
  readonly auditObservedAt?: string | undefined
}

export class SensoriumObservationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SensoriumObservationError'
  }
}

const SHA256_HEX = /^[a-f0-9]{64}$/
const SOURCE_KINDS = new Set<SensoriumSourceKind>(['runtime', 'telemetry', 'operator', 'replay'])
const encoder = new TextEncoder()

function assertBps(name: string, value: number): void {
  if (!Number.isSafeInteger(value) || value < 0 || value > 10_000) {
    throw new SensoriumObservationError(`${name} must be an integer in [0,10000]`)
  }
}

function assertDigest(name: string, value: string): void {
  if (!SHA256_HEX.test(value)) {
    throw new SensoriumObservationError(`${name} must be lowercase SHA-256 hex`)
  }
}

function canonicalScalar(value: string | number | bigint): string {
  if (typeof value === 'bigint') return value.toString(10)
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new SensoriumObservationError('canonical integer must be a non-negative safe integer')
    }
    return value.toString(10)
  }
  return value
}

function frame(name: string, value: string | number | bigint): string {
  const nameBytes = encoder.encode(name).byteLength
  const canonical = canonicalScalar(value)
  const valueBytes = encoder.encode(canonical).byteLength
  return `${nameBytes}:${name}${valueBytes}:${canonical}`
}

export function encodeSensoriumObservationPayload(payload: SensoriumObservationPayloadV1): Uint8Array {
  const evidence = [...payload.evidenceReferences].sort()
  const parts = [
    frame('schemaVersion', payload.schemaVersion),
    frame('authorityEffect', payload.authorityEffect),
    frame('observationTier', payload.observationTier),
    frame('authorityWeight', payload.authorityWeight),
    frame('mayGroundStateTransition', payload.mayGroundStateTransition ? 1 : 0),
    frame('sourceKind', payload.sourceKind),
    frame('sourceIdentityDigest', payload.sourceIdentityDigest),
    frame('subjectResourceDigest', payload.subjectResourceDigest),
    frame('observationSequence', payload.observationSequence),
    frame('expectedParentStateRoot', payload.expectedParentStateRoot),
    frame('topologyDigest', payload.topologyDigest),
    frame('activeLoad', payload.activeLoad),
    frame('carryingCapacity', payload.carryingCapacity),
    frame('growthRateBps', payload.growthRateBps),
    frame('retentionBps', payload.retentionBps),
    frame('decayBps', payload.decayBps),
    frame('reinforcementBps', payload.reinforcementBps),
    frame('observationQualityBps', payload.observationQualityBps),
    frame('predictedNextLoad', payload.predictedNextLoad),
    frame('capacityPressureBps', payload.capacityPressureBps),
    frame('predictedNextRetentionBps', payload.predictedNextRetentionBps),
    frame('modelStatus', payload.modelStatus),
    frame('empiricalStatus', payload.empiricalStatus),
    frame('evidenceReferenceCount', evidence.length),
    ...evidence.map(reference => frame('evidenceReference', reference)),
  ]
  return encoder.encode(parts.join(''))
}

function validateInput(input: SensoriumObservationInputV1): readonly string[] {
  if (!SOURCE_KINDS.has(input.sourceKind)) throw new SensoriumObservationError('unsupported source kind')
  assertDigest('sourceIdentityDigest', input.sourceIdentityDigest)
  assertDigest('subjectResourceDigest', input.subjectResourceDigest)
  assertDigest('expectedParentStateRoot', input.expectedParentStateRoot)
  assertDigest('topologyDigest', input.topologyDigest)
  if (!Number.isSafeInteger(input.observationSequence) || input.observationSequence < 0) {
    throw new SensoriumObservationError('observationSequence must be a non-negative safe integer')
  }
  if (input.carryingCapacity <= 0n) throw new SensoriumObservationError('carryingCapacity must be positive')
  if (input.activeLoad < 0n || input.activeLoad > input.carryingCapacity) {
    throw new SensoriumObservationError('activeLoad must be within carrying capacity')
  }
  assertBps('growthRateBps', input.growthRateBps)
  assertBps('retentionBps', input.retentionBps)
  assertBps('decayBps', input.decayBps)
  assertBps('reinforcementBps', input.reinforcementBps)
  assertBps('observationQualityBps', input.observationQualityBps)
  if (input.evidenceReferences.some(reference => reference.length === 0)) {
    throw new SensoriumObservationError('evidence references must be non-empty')
  }
  const evidence = [...input.evidenceReferences].sort()
  if (new Set(evidence).size !== evidence.length) {
    throw new SensoriumObservationError('evidence references must be unique')
  }
  return Object.freeze(evidence)
}

export async function createSensoriumObservation(input: SensoriumObservationInputV1): Promise<SensoriumObservationV1> {
  const evidenceReferences = validateInput(input)
  const payload: SensoriumObservationPayloadV1 = Object.freeze({
    schemaVersion: '1.0.0',
    authorityEffect: 'OBSERVATION_ONLY',
    observationTier: 'T2',
    authorityWeight: 0,
    mayGroundStateTransition: false,
    sourceKind: input.sourceKind,
    sourceIdentityDigest: input.sourceIdentityDigest,
    subjectResourceDigest: input.subjectResourceDigest,
    observationSequence: input.observationSequence,
    expectedParentStateRoot: input.expectedParentStateRoot,
    topologyDigest: input.topologyDigest,
    activeLoad: input.activeLoad,
    carryingCapacity: input.carryingCapacity,
    growthRateBps: input.growthRateBps,
    retentionBps: input.retentionBps,
    decayBps: input.decayBps,
    reinforcementBps: input.reinforcementBps,
    observationQualityBps: input.observationQualityBps,
    predictedNextLoad: nextLogisticLoad(input.activeLoad, input.carryingCapacity, input.growthRateBps),
    capacityPressureBps: capacityPressureBps(input.activeLoad, input.carryingCapacity),
    predictedNextRetentionBps: nextRetentionBps(input.retentionBps, input.decayBps, input.reinforcementBps),
    evidenceReferences,
    modelStatus: 'MODEL_DEFINED',
    empiricalStatus: 'NOT_ESTABLISHED',
  })
  const observationDigest = await sha256Hex(encodeSensoriumObservationPayload(payload))
  return Object.freeze({
    ...payload,
    observationId: observationDigest,
    observationDigest,
    ...(input.auditObservedAt === undefined ? {} : { auditObservedAt: input.auditObservedAt }),
  })
}
