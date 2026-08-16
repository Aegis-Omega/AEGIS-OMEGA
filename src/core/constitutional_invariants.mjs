import { createHash } from 'node:crypto'

const SHA256_HEX = /^[a-f0-9]{64}$/

export class ConstitutionalInvariantError extends Error {
  constructor(code, message = code) {
    super(message)
    this.name = 'ConstitutionalInvariantError'
    this.code = code
  }
}

export class ConstitutionalEnforcer {
  evaluateUsefulAutonomy({ capabilities, authorityEnvelope, hasRecoveryPath }) {
    if (hasRecoveryPath !== true) {
      throw new ConstitutionalInvariantError('RECOVERY_PATH_UNVERIFIED')
    }
    if (!Array.isArray(capabilities) || !Array.isArray(authorityEnvelope)) {
      throw new ConstitutionalInvariantError('AUTONOMY_INPUT_INVALID')
    }
    const authority = new Set(authorityEnvelope)
    const admittedCapabilities = [...new Set(capabilities)]
      .filter(capability => authority.has(capability))
      .sort()
    return Object.freeze({
      status: admittedCapabilities.length === 0 ? 'EMPTY_AUTONOMY_INTERSECTION' : 'USEFUL_AUTONOMY_ADMITTED',
      admittedCapabilities: Object.freeze(admittedCapabilities),
    })
  }

  assertBlastRadius({ effect, envelope }) {
    if (!effect || !envelope || typeof effect !== 'object' || typeof envelope !== 'object') {
      throw new ConstitutionalInvariantError('BLAST_RADIUS_EXCEEDED')
    }

    if (effect.networkTarget !== undefined) {
      if (envelope.networkPolicy === 'DENY_ALL') {
        throw new ConstitutionalInvariantError('BLAST_RADIUS_EXCEEDED')
      }
      if (envelope.networkPolicy === 'ALLOW_LIST' && !envelope.allowedNetworkTargets?.includes(effect.networkTarget)) {
        throw new ConstitutionalInvariantError('BLAST_RADIUS_EXCEEDED')
      }
    }

    if (effect.tool !== undefined && !envelope.allowedTools?.includes(effect.tool)) {
      throw new ConstitutionalInvariantError('BLAST_RADIUS_EXCEEDED')
    }

    if (effect.financialMutationMicroUsd !== undefined) {
      const amount = effect.financialMutationMicroUsd
      const ceiling = envelope.maxFinancialMutationMicroUsd
      if (!Number.isSafeInteger(amount) || amount < 0 || !Number.isSafeInteger(ceiling) || ceiling < 0 || amount > ceiling) {
        throw new ConstitutionalInvariantError('BLAST_RADIUS_EXCEEDED')
      }
    }

    return true
  }

  processSensoriumIngestion({ observation, requestedMutation, authorityToken }) {
    validateObservation(observation)

    if (requestedMutation !== undefined && !isExternalAuthorityToken(authorityToken)) {
      throw new ConstitutionalInvariantError('MUTATION_BLOCKED_PERCEPTION_CANNOT_PRODUCE_AUTHORITY')
    }

    const digestPayload = {
      source: observation.source,
      observedAtSequence: observation.observedAtSequence,
      parentStateRoot: observation.parentStateRoot,
      topologyDigest: observation.topologyDigest,
      evidenceReferences: [...observation.evidenceReferences],
      payload: observation.payload,
    }
    const observationDigest = digestCanonical(digestPayload)

    return Object.freeze({
      schemaVersion: '1.0.0',
      observationDigest,
      source: observation.source,
      observedAtSequence: observation.observedAtSequence,
      parentStateRoot: observation.parentStateRoot,
      topologyDigest: observation.topologyDigest,
      evidenceReferences: Object.freeze([...observation.evidenceReferences]),
      payload: deepFreezeClone(observation.payload),
      authorityEffect: 'OBSERVATION_ONLY',
      observationTier: 'T2',
      authorityWeight: 0,
      mayGroundStateTransition: false,
      mutationDisposition: requestedMutation === undefined
        ? 'NO_MUTATION_REQUESTED'
        : 'REQUIRES_EXTERNAL_AUTHORITY_EVALUATION',
    })
  }
}

function validateObservation(observation) {
  if (!observation || typeof observation !== 'object') {
    throw new ConstitutionalInvariantError('SENSORIUM_OBSERVATION_INVALID')
  }
  if (typeof observation.source !== 'string' || observation.source.length === 0) {
    throw new ConstitutionalInvariantError('SENSORIUM_OBSERVATION_INVALID')
  }
  if (!Number.isSafeInteger(observation.observedAtSequence) || observation.observedAtSequence < 0) {
    throw new ConstitutionalInvariantError('SENSORIUM_OBSERVATION_INVALID')
  }
  if (!SHA256_HEX.test(observation.parentStateRoot ?? '') || !SHA256_HEX.test(observation.topologyDigest ?? '')) {
    throw new ConstitutionalInvariantError('SENSORIUM_OBSERVATION_INVALID')
  }
  if (!Array.isArray(observation.evidenceReferences) || observation.evidenceReferences.length === 0 ||
      observation.evidenceReferences.some(ref => typeof ref !== 'string' || ref.length === 0)) {
    throw new ConstitutionalInvariantError('SENSORIUM_OBSERVATION_INVALID')
  }
}

function isExternalAuthorityToken(token) {
  return typeof token === 'string' && /^(pcwo|aap):\/\/\S+$/.test(token)
}

function digestCanonical(value) {
  return createHash('sha256').update(JSON.stringify(sortRecursively(value)), 'utf8').digest('hex')
}

function sortRecursively(value) {
  if (Array.isArray(value)) return value.map(sortRecursively)
  if (value === null || typeof value !== 'object') return value
  const out = {}
  for (const key of Object.keys(value).sort()) {
    if (value[key] !== undefined) out[key] = sortRecursively(value[key])
  }
  return out
}

function deepFreezeClone(value) {
  if (value === undefined) return undefined
  const cloned = structuredClone(value)
  return deepFreeze(cloned)
}

function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) deepFreeze(child)
    Object.freeze(value)
  }
  return value
}
