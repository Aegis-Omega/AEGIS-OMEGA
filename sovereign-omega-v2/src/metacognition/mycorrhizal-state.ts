import { hashValue } from '../core/hashing.js'
import {
  MCM_AUTHORITY_EFFECT,
  MCM_AUTHORITY_WEIGHT,
  MCM_MAY_GROUND_STATE_TRANSITION,
  MCM_OBSERVATION_TIER,
  MCM_SCHEMA_VERSION,
  McmContractError,
  assertMcmBps,
  assertMcmDigest,
  verifyMcmNodeObservation,
  type McmNodeObservationV1,
} from './mycorrhizal-contracts.js'

export interface MycorrhizalCollectiveStateV1 {
  readonly schemaVersion: typeof MCM_SCHEMA_VERSION
  readonly authorityEffect: typeof MCM_AUTHORITY_EFFECT
  readonly observationTier: typeof MCM_OBSERVATION_TIER
  readonly authorityWeight: typeof MCM_AUTHORITY_WEIGHT
  readonly mayGroundStateTransition: typeof MCM_MAY_GROUND_STATE_TRANSITION
  readonly stateRoot: string
  readonly parentStateRoot: string
  readonly topologyDigest: string
  readonly nodeCount: number
  readonly observationCount: number
  readonly collectiveCalibrationBps: number
  readonly collectiveEvidenceSupportBps: number
  readonly collectiveEvidenceFreshnessBps: number
  readonly collectiveResourcePressureBps: number
  readonly collectiveContradictionPressureBps: number
  readonly collectiveVerificationDemandBps: number
  readonly nodeObservationDigests: readonly string[]
}

type MycorrhizalCollectiveStatePayloadV1 = Omit<MycorrhizalCollectiveStateV1, 'stateRoot'>

function compareObservations(a: McmNodeObservationV1, b: McmNodeObservationV1): number {
  const node = a.nodeIdentityDigest.localeCompare(b.nodeIdentityDigest)
  if (node !== 0) return node
  if (a.observationSequence !== b.observationSequence) {
    return a.observationSequence - b.observationSequence
  }
  return a.observationDigest.localeCompare(b.observationDigest)
}

function checkedMean(values: readonly number[]): number {
  let sum = 0
  for (const value of values) {
    const next = sum + value
    if (!Number.isSafeInteger(next)) {
      throw new McmContractError('MCM aggregate sum exceeds safe integer range')
    }
    sum = next
  }
  return Math.floor(sum / values.length)
}

async function canonicalObservationSet(
  observations: readonly McmNodeObservationV1[],
): Promise<readonly McmNodeObservationV1[]> {
  if (observations.length === 0) {
    throw new McmContractError('MCM observation set must not be empty')
  }

  let parentStateRoot: string | undefined
  let topologyDigest: string | undefined
  const seen = new Map<string, string>()
  const canonical: McmNodeObservationV1[] = []

  for (const observation of observations) {
    await verifyMcmNodeObservation(observation)
    if (parentStateRoot === undefined) {
      parentStateRoot = observation.expectedParentStateRoot
      topologyDigest = observation.topologyDigest
    } else {
      if (observation.expectedParentStateRoot !== parentStateRoot) {
        throw new McmContractError('MCM observations must share expectedParentStateRoot')
      }
      if (observation.topologyDigest !== topologyDigest) {
        throw new McmContractError('MCM observations must share topologyDigest')
      }
    }

    const key = `${observation.nodeIdentityDigest}:${observation.observationSequence}`
    const priorDigest = seen.get(key)
    if (priorDigest !== undefined) {
      if (priorDigest !== observation.observationDigest) {
        throw new McmContractError('conflicting duplicate MCM node observation sequence')
      }
      continue
    }
    seen.set(key, observation.observationDigest)
    canonical.push(observation)
  }

  canonical.sort(compareObservations)
  return Object.freeze(canonical)
}

function stateHashPayload(
  state: MycorrhizalCollectiveStatePayloadV1,
): MycorrhizalCollectiveStatePayloadV1 {
  return Object.freeze({
    schemaVersion: state.schemaVersion,
    authorityEffect: state.authorityEffect,
    observationTier: state.observationTier,
    authorityWeight: state.authorityWeight,
    mayGroundStateTransition: state.mayGroundStateTransition,
    parentStateRoot: state.parentStateRoot,
    topologyDigest: state.topologyDigest,
    nodeCount: state.nodeCount,
    observationCount: state.observationCount,
    collectiveCalibrationBps: state.collectiveCalibrationBps,
    collectiveEvidenceSupportBps: state.collectiveEvidenceSupportBps,
    collectiveEvidenceFreshnessBps: state.collectiveEvidenceFreshnessBps,
    collectiveResourcePressureBps: state.collectiveResourcePressureBps,
    collectiveContradictionPressureBps: state.collectiveContradictionPressureBps,
    collectiveVerificationDemandBps: state.collectiveVerificationDemandBps,
    nodeObservationDigests: Object.freeze([...state.nodeObservationDigests]),
  })
}

export function assertMycorrhizalCollectiveState(state: MycorrhizalCollectiveStateV1): void {
  if (state.schemaVersion !== MCM_SCHEMA_VERSION ||
      state.authorityEffect !== MCM_AUTHORITY_EFFECT ||
      state.observationTier !== MCM_OBSERVATION_TIER ||
      state.authorityWeight !== MCM_AUTHORITY_WEIGHT ||
      state.mayGroundStateTransition !== MCM_MAY_GROUND_STATE_TRANSITION) {
    throw new McmContractError('MCM collective-state constitutional boundary mismatch')
  }

  assertMcmDigest('stateRoot', state.stateRoot)
  assertMcmDigest('parentStateRoot', state.parentStateRoot)
  assertMcmDigest('topologyDigest', state.topologyDigest)
  if (!Number.isSafeInteger(state.nodeCount) || state.nodeCount < 1) {
    throw new McmContractError('MCM state nodeCount must be a positive safe integer')
  }
  if (!Number.isSafeInteger(state.observationCount) || state.observationCount < 1) {
    throw new McmContractError('MCM state observationCount must be a positive safe integer')
  }
  if (state.nodeCount > state.observationCount) {
    throw new McmContractError('MCM state nodeCount cannot exceed observationCount')
  }

  assertMcmBps('collectiveCalibrationBps', state.collectiveCalibrationBps)
  assertMcmBps('collectiveEvidenceSupportBps', state.collectiveEvidenceSupportBps)
  assertMcmBps('collectiveEvidenceFreshnessBps', state.collectiveEvidenceFreshnessBps)
  assertMcmBps('collectiveResourcePressureBps', state.collectiveResourcePressureBps)
  assertMcmBps('collectiveContradictionPressureBps', state.collectiveContradictionPressureBps)
  assertMcmBps('collectiveVerificationDemandBps', state.collectiveVerificationDemandBps)

  if (state.nodeObservationDigests.length !== state.observationCount) {
    throw new McmContractError('MCM state observation digest cardinality mismatch')
  }
  const seen = new Set<string>()
  for (const digest of state.nodeObservationDigests) {
    assertMcmDigest('nodeObservationDigest', digest)
    if (seen.has(digest)) {
      throw new McmContractError('MCM state observation digests must be unique')
    }
    seen.add(digest)
  }
}

export async function verifyMycorrhizalCollectiveState(
  state: MycorrhizalCollectiveStateV1,
): Promise<void> {
  assertMycorrhizalCollectiveState(state)
  const expectedRoot = await hashValue(stateHashPayload(state))
  if (expectedRoot !== state.stateRoot) {
    throw new McmContractError('MCM collective state root does not match canonical payload')
  }
}

export async function reduceMycorrhizalCollectiveState(
  observations: readonly McmNodeObservationV1[],
): Promise<MycorrhizalCollectiveStateV1> {
  const canonical = await canonicalObservationSet(observations)
  const parentStateRoot = canonical[0]!.expectedParentStateRoot
  const topologyDigest = canonical[0]!.topologyDigest
  const nodeObservationDigests = Object.freeze(canonical.map(observation => observation.observationDigest))
  const nodeCount = new Set(canonical.map(observation => observation.nodeIdentityDigest)).size

  const payload: MycorrhizalCollectiveStatePayloadV1 = stateHashPayload({
    schemaVersion: MCM_SCHEMA_VERSION,
    authorityEffect: MCM_AUTHORITY_EFFECT,
    observationTier: MCM_OBSERVATION_TIER,
    authorityWeight: MCM_AUTHORITY_WEIGHT,
    mayGroundStateTransition: MCM_MAY_GROUND_STATE_TRANSITION,
    parentStateRoot,
    topologyDigest,
    nodeCount,
    observationCount: canonical.length,
    collectiveCalibrationBps: checkedMean(canonical.map(observation => observation.calibrationBps)),
    collectiveEvidenceSupportBps: checkedMean(canonical.map(observation => observation.evidenceSupportBps)),
    collectiveEvidenceFreshnessBps: checkedMean(canonical.map(observation => observation.evidenceFreshnessBps)),
    collectiveResourcePressureBps: checkedMean(canonical.map(observation => observation.resourcePressureBps)),
    collectiveContradictionPressureBps: checkedMean(canonical.map(observation => observation.contradictionPressureBps)),
    collectiveVerificationDemandBps: checkedMean(canonical.map(observation => observation.verificationDemandBps)),
    nodeObservationDigests,
  })

  const stateRoot = await hashValue(payload)
  return Object.freeze({ ...payload, stateRoot })
}
