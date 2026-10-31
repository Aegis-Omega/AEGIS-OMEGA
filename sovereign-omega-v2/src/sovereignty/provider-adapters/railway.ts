// ============================================================
// Railway connector -> Sovereign Provider Mesh adapter V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export type RailwayConnectorOutcomeV1 =
  | 'DEPLOYMENT_SUCCEEDED'
  | 'TRIAL_EXPIRED'
  | 'DEPLOYMENT_FAILED'
  | 'UNKNOWN'

export interface RailwayConnectorEvidenceV1 {
  outcome: RailwayConnectorOutcomeV1
  project_present: boolean
  service_count: number
  deployment_count: number
}

export async function observeRailwayConnectorV1(
  evidence: RailwayConnectorEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!Number.isSafeInteger(evidence.service_count) || evidence.service_count < 0) {
    throw new TypeError('service_count must be a non-negative safe integer')
  }
  if (!Number.isSafeInteger(evidence.deployment_count) || evidence.deployment_count < 0) {
    throw new TypeError('deployment_count must be a non-negative safe integer')
  }
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_RAILWAY_CONNECTOR_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  const available = evidence.outcome === 'DEPLOYMENT_SUCCEEDED'
  const billingBlocked = evidence.outcome === 'TRIAL_EXPIRED'

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'railway',
    state: available
      ? 'OBSERVED_AVAILABLE'
      : billingBlocked
        ? 'BILLING_BLOCKED'
        : 'UNKNOWN',
    observed_capabilities: available || billingBlocked
      ? ['CONTAINER_RUNTIME', 'DURABLE_RUNNER']
      : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
