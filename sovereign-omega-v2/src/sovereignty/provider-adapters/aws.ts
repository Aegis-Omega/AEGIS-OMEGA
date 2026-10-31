/**
 * AWS account observation -> AEGIS Provider Mesh V1, read-only and fail-closed.
 * AWS account/billing observations never imply runnable cloud capability.
 */
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import type { ConnectedResourceInventoryV1 } from '../connected-resource-intake.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

const HASH = /^[0-9a-f]{64}$/

/** Verify a local inventory checksum, never AWS source authenticity. */
export async function observeAwsAccountForProviderMeshV1(
  inventory: ConnectedResourceInventoryV1,
): Promise<ProviderObservationV1> {
  if (!inventory || inventory.schema !== 'AEGIS_CONNECTED_RESOURCE_INVENTORY_V1'
      || inventory.authority_effect !== 'NONE'
      || inventory.zero_spend_admission !== 'HOLD'
      || !inventory.aws
      || !HASH.test(inventory.integrity_root)) {
    throw new TypeError('invalid or non-HOLD AWS inventory')
  }
  const { integrity_root, ...body } = inventory
  const actual = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_CONNECTED_RESOURCE_INVENTORY_V1', body,
  }))
  if (actual !== integrity_root) throw new TypeError('AWS inventory checksum mismatch')
  if (inventory.aws.paid_aws_workloads !== 'HOLD'
      || inventory.aws.provider_attestation !== 'NOT_ESTABLISHED'
      || inventory.aws.remaining_credit_verified !== 'UNKNOWN'
      || inventory.aws.effective_hard_budget_stop !== 'UNKNOWN') {
    throw new TypeError('AWS inventory claims unsupported authority or credit')
  }
  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'aws',
    // Source-derived account observation, NOT execution availability.
    state: inventory.aws.identity === 'OBSERVED' && inventory.aws.principal_kind !== 'ROOT'
      ? 'ACCOUNT_CONFIGURED' : 'UNKNOWN',
    observed_capabilities: [],
    evidence_hash: integrity_root,
    observation_generation: inventory.observation_generation,
    authority_effect: 'NONE',
  }
}
