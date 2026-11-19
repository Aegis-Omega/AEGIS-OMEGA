import {
  PLATFORM_CONTRACT_VERSION,
  type PlatformEnvelope,
} from '../../../packages/shared/lib/platform-contract.js'

export class PlatformEnvelopeError extends Error {}

export function parsePlatformEnvelope<T>(value: unknown): PlatformEnvelope<T> {
  if (typeof value !== 'object' || value === null) {
    throw new PlatformEnvelopeError('PLATFORM_ENVELOPE_NOT_OBJECT')
  }

  const candidate = value as Partial<PlatformEnvelope<T>>
  if (candidate.contract_version !== PLATFORM_CONTRACT_VERSION) {
    throw new PlatformEnvelopeError('PLATFORM_CONTRACT_VERSION_MISMATCH')
  }
  if (typeof candidate.execution_id !== 'string' || !candidate.execution_id) {
    throw new PlatformEnvelopeError('PLATFORM_EXECUTION_ID_INVALID')
  }
  if (typeof candidate.timestamp !== 'string' || !candidate.timestamp) {
    throw new PlatformEnvelopeError('PLATFORM_TIMESTAMP_INVALID')
  }
  if (candidate.is_replay_reconstructable !== true) {
    throw new PlatformEnvelopeError('PLATFORM_REPLAY_FLAG_INVALID')
  }
  if (!('data' in candidate)) {
    throw new PlatformEnvelopeError('PLATFORM_DATA_MISSING')
  }

  return candidate as PlatformEnvelope<T>
}
