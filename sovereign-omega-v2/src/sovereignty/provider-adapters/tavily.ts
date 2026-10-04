// ============================================================
// Tavily MCP -> Sovereign Provider Mesh adapter V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export interface TavilyMcpEvidenceV1 {
  request_id: string
  auth_mode: string
  outcome: 'SUCCESS' | 'FAILURE'
  result_count: number
}

export async function observeTavilyMcpV1(
  evidence: TavilyMcpEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!evidence.request_id.trim()) throw new TypeError('request_id must be non-empty')
  if (!evidence.auth_mode.trim()) throw new TypeError('auth_mode must be non-empty')
  if (!Number.isSafeInteger(evidence.result_count) || evidence.result_count < 0) {
    throw new TypeError('result_count must be a non-negative safe integer')
  }
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_TAVILY_MCP_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'tavily',
    state: evidence.outcome === 'SUCCESS' ? 'OBSERVED_AVAILABLE' : 'UNKNOWN',
    observed_capabilities: evidence.outcome === 'SUCCESS' ? ['WEB_RESEARCH'] : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
