// ============================================================
// Hugging Face Jobs -> Sovereign Provider Mesh adapter V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export type HuggingFaceJobsOutcomeV1 =
  | 'JOB_ACCEPTED'
  | 'JOB_SUCCEEDED'
  | 'PAYMENT_REQUIRED'
  | 'AUTH_DENIED'
  | 'GENERIC_FAILURE'

export interface HuggingFaceJobsEvidenceV1 {
  operation: 'run' | 'uv'
  outcome: HuggingFaceJobsOutcomeV1
  flavor: string
  job_id: string | null
}

export async function observeHuggingFaceJobsV1(
  evidence: HuggingFaceJobsEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!evidence.flavor.trim()) throw new TypeError('flavor must be non-empty')
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_HUGGING_FACE_JOBS_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  const available = evidence.outcome === 'JOB_ACCEPTED' || evidence.outcome === 'JOB_SUCCEEDED'
  const unavailable = evidence.outcome === 'PAYMENT_REQUIRED' || evidence.outcome === 'AUTH_DENIED'

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'hugging-face-jobs',
    state: available ? 'OBSERVED_AVAILABLE' : unavailable ? 'OBSERVED_UNAVAILABLE' : 'UNKNOWN',
    observed_capabilities: available || unavailable
      ? ['CONTAINER_RUNTIME', 'DURABLE_RUNNER', 'GPU_COMPUTE']
      : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
