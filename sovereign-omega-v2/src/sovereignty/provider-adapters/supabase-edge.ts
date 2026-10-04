// ============================================================
// Supabase runtime -> Sovereign Provider Mesh adapter V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export interface SupabaseRuntimeEvidenceV1 {
  project_status: string
  database_health_ok: boolean
  edge_function_reachable: boolean
  outbound_http_observed: boolean
}

export async function observeSupabaseRuntimeV1(
  evidence: SupabaseRuntimeEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!evidence.project_status.trim()) throw new TypeError('project_status must be non-empty')
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_SUPABASE_RUNTIME_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  const available =
    evidence.project_status === 'ACTIVE_HEALTHY' &&
    evidence.database_health_ok &&
    evidence.edge_function_reachable &&
    evidence.outbound_http_observed

  const explicitlyUnavailable =
    evidence.project_status === 'INACTIVE' ||
    evidence.project_status === 'PAUSED'

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'supabase-edge',
    state: available
      ? 'OBSERVED_AVAILABLE'
      : explicitlyUnavailable
        ? 'OBSERVED_UNAVAILABLE'
        : 'UNKNOWN',
    observed_capabilities: available
      ? ['SERVERLESS_FUNCTION', 'DATABASE', 'HTTP_EGRESS']
      : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
