// ============================================================
// DashScope auth probe -> Sovereign Provider Mesh adapter V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export type DashScopeAuthOutcomeV1 =
  | 'AUTHENTICATED'
  | 'INVALID_API_KEY'
  | 'NETWORK_FAILURE'
  | 'UNKNOWN_FAILURE'

export interface DashScopeAuthEvidenceV1 {
  outcome: DashScopeAuthOutcomeV1
  status_code: number | null
  request_id: string | null
}

export async function observeDashScopeAuthV1(
  evidence: DashScopeAuthEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }
  if (
    evidence.status_code !== null &&
    (!Number.isSafeInteger(evidence.status_code) || evidence.status_code < 100 || evidence.status_code > 599)
  ) {
    throw new TypeError('status_code must be null or a valid HTTP status')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_DASHSCOPE_AUTH_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  const available = evidence.outcome === 'AUTHENTICATED'
  const unavailable = evidence.outcome === 'INVALID_API_KEY'

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'dashscope',
    state: available
      ? 'OBSERVED_AVAILABLE'
      : unavailable
        ? 'OBSERVED_UNAVAILABLE'
        : 'UNKNOWN',
    observed_capabilities: available || unavailable ? ['MODEL_INFERENCE'] : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
