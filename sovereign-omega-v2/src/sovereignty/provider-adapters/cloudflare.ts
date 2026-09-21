// ============================================================
// Cloudflare Worker evidence -> Sovereign Provider Mesh V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export interface CloudflareWorkerHealthEvidenceV1 {
  status_code: number
  source_semantics_match: boolean
}

export interface CloudflareAnthropicSecretEvidenceV1 {
  status_code: number
  secret_configured: boolean
  malformed_request_reached_model: false
}

export async function observeCloudflareWorkerV1(
  evidence: CloudflareWorkerHealthEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_CLOUDFLARE_WORKER_HEALTH_V1',
    evidence,
  })) as SHA256Hex

  const healthy = evidence.status_code === 200
  const sourceBound = healthy && evidence.source_semantics_match

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'cloudflare-worker',
    state: sourceBound
      ? 'OBSERVED_AVAILABLE'
      : healthy
        ? 'NETWORK_REACHABLE'
        : 'UNKNOWN',
    observed_capabilities: healthy ? ['SERVERLESS_FUNCTION', 'HTTP_EGRESS'] : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}

export async function observeCloudflareAnthropicV1(
  evidence: CloudflareAnthropicSecretEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_CLOUDFLARE_ANTHROPIC_SECRET_V1',
    evidence,
  })) as SHA256Hex

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'cloudflare-anthropic',
    state: evidence.secret_configured ? 'CONFIGURED' : 'CREDENTIAL_MISSING',
    observed_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
