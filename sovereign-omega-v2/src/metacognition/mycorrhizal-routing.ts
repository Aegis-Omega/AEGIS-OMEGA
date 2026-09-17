import {
  MCM_AUTHORITY_EFFECT,
  MCM_AUTHORITY_WEIGHT,
  MCM_MAY_GROUND_STATE_TRANSITION,
  MCM_OBSERVATION_TIER,
  MCM_SCHEMA_VERSION,
  McmContractError,
  canonicalMcmEvidenceReferences,
  type McmNodeObservationV1,
  type McmVerificationReason,
  type McmVerificationRequestV1,
} from './mycorrhizal-contracts.js'
import {
  reduceMycorrhizalCollectiveState,
  verifyMycorrhizalCollectiveState,
  type MycorrhizalCollectiveStateV1,
} from './mycorrhizal-state.js'

function compareObservations(a: McmNodeObservationV1, b: McmNodeObservationV1): number {
  const node = a.nodeIdentityDigest.localeCompare(b.nodeIdentityDigest)
  if (node !== 0) return node
  if (a.observationSequence !== b.observationSequence) {
    return a.observationSequence - b.observationSequence
  }
  return a.observationDigest.localeCompare(b.observationDigest)
}

async function verifiedStateObservationBinding(
  state: MycorrhizalCollectiveStateV1,
  observations: readonly McmNodeObservationV1[],
): Promise<readonly McmNodeObservationV1[]> {
  await verifyMycorrhizalCollectiveState(state)
  if (observations.length !== state.observationCount) {
    throw new McmContractError('MCM routing observation count does not match collective state')
  }

  const recomputed = await reduceMycorrhizalCollectiveState(observations)
  if (recomputed.stateRoot !== state.stateRoot) {
    throw new McmContractError('MCM routing collective state root does not match bound observations')
  }

  const canonical = [...observations]
  canonical.sort(compareObservations)
  if (canonical.length !== state.nodeObservationDigests.length) {
    throw new McmContractError('MCM routing digest cardinality mismatch')
  }
  for (let index = 0; index < canonical.length; index += 1) {
    if (canonical[index]!.observationDigest !== state.nodeObservationDigests[index]) {
      throw new McmContractError('MCM routing observation is not represented by collective state')
    }
  }
  return Object.freeze(canonical)
}

function deriveReasons(observation: McmNodeObservationV1): readonly McmVerificationReason[] {
  const reasons: McmVerificationReason[] = []
  if (observation.calibrationBps < 7000) reasons.push('LOW_CALIBRATION')
  if (observation.evidenceSupportBps < 7000) reasons.push('LOW_EVIDENCE_SUPPORT')
  if (observation.evidenceFreshnessBps < 7000) reasons.push('STALE_EVIDENCE')
  if (observation.resourcePressureBps >= 8000) reasons.push('RESOURCE_PRESSURE')
  if (observation.contradictionPressureBps >= 6000) reasons.push('CONTRADICTION_PRESSURE')
  if (observation.verificationDemandBps >= 7000) reasons.push('EXPLICIT_VERIFICATION_DEMAND')
  reasons.sort()
  return Object.freeze(reasons)
}

function priorityBps(observation: McmNodeObservationV1): number {
  return Math.max(
    10_000 - observation.calibrationBps,
    10_000 - observation.evidenceSupportBps,
    10_000 - observation.evidenceFreshnessBps,
    observation.resourcePressureBps,
    observation.contradictionPressureBps,
    observation.verificationDemandBps,
  )
}

export async function deriveMcmVerificationRequests(
  state: MycorrhizalCollectiveStateV1,
  observations: readonly McmNodeObservationV1[],
): Promise<readonly McmVerificationRequestV1[]> {
  const canonical = await verifiedStateObservationBinding(state, observations)
  const requests: McmVerificationRequestV1[] = []

  for (const observation of canonical) {
    const reasonCodes = deriveReasons(observation)
    if (reasonCodes.length === 0) continue
    const evidenceReferences = canonicalMcmEvidenceReferences(observation.evidenceReferences)
    requests.push(Object.freeze({
      schemaVersion: MCM_SCHEMA_VERSION,
      authorityEffect: MCM_AUTHORITY_EFFECT,
      observationTier: MCM_OBSERVATION_TIER,
      authorityWeight: MCM_AUTHORITY_WEIGHT,
      mayGroundStateTransition: MCM_MAY_GROUND_STATE_TRANSITION,
      collectiveStateRoot: state.stateRoot,
      subjectNodeDigest: observation.nodeIdentityDigest,
      priorityBps: priorityBps(observation),
      reasonCodes,
      evidenceReferences,
    }))
  }

  return Object.freeze(requests)
}
