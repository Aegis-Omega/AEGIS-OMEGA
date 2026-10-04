// ============================================================
// Wolfram kernel -> Sovereign Provider Mesh adapter V1
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export type WolframKernelOutcomeV1 = 'KERNEL_SUCCESS' | 'KERNEL_FAILURE'

export interface WolframKernelEvidenceV1 {
  outcome: WolframKernelOutcomeV1
  verifier_root: SHA256Hex | null
  computation_kind: string
}

export async function observeWolframKernelV1(
  evidence: WolframKernelEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!evidence.computation_kind.trim()) throw new TypeError('computation_kind must be non-empty')
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }
  if (evidence.outcome === 'KERNEL_SUCCESS') {
    if (evidence.verifier_root === null || !/^[0-9a-f]{64}$/.test(evidence.verifier_root)) {
      throw new TypeError('successful Wolfram evidence requires verifier_root')
    }
  }

  const evidence_hash = evidence.verifier_root ?? await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_WOLFRAM_KERNEL_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: 'wolfram',
    state: evidence.outcome === 'KERNEL_SUCCESS' ? 'OBSERVED_AVAILABLE' : 'UNKNOWN',
    observed_capabilities: evidence.outcome === 'KERNEL_SUCCESS' ? ['SYMBOLIC_COMPUTE'] : [],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
