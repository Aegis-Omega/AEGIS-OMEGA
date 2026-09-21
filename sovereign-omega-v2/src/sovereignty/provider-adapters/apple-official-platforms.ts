// ============================================================
// Apple official public platform evidence -> Sovereign Provider Mesh V1
// EPISTEMIC TIER: T1 public-source observation adapter
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderCapabilityV1,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export const APPLE_OFFICIAL_PLATFORM_SOURCES_V1 = {
  'apple-developer-intelligence': {
    capability: 'APPLE_INTELLIGENCE_DEVELOPER_READ',
    official_url: 'https://developer.apple.com/apple-intelligence/',
    source_class: 'OFFICIAL_DEVELOPER_DOCS',
  },
  'apple-business-ai': {
    capability: 'APPLE_BUSINESS_DEPLOYMENT_READ',
    official_url: 'https://developer.apple.com/business/ai/',
    source_class: 'OFFICIAL_BUSINESS_DOCS',
  },
} as const satisfies Readonly<Record<string, {
  capability: ProviderCapabilityV1
  official_url: string
  source_class: 'OFFICIAL_DEVELOPER_DOCS' | 'OFFICIAL_BUSINESS_DOCS'
}>>

export type AppleOfficialProviderIdV1 = keyof typeof APPLE_OFFICIAL_PLATFORM_SOURCES_V1

export interface AppleOfficialPlatformEvidenceV1 {
  provider_id: AppleOfficialProviderIdV1
  official_url: string
  source_class: 'OFFICIAL_DEVELOPER_DOCS' | 'OFFICIAL_BUSINESS_DOCS'
  outcome: 'READ_SUCCESS'
}

export async function observeAppleOfficialPlatformV1(
  evidence: AppleOfficialPlatformEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  const source = APPLE_OFFICIAL_PLATFORM_SOURCES_V1[evidence.provider_id]
  if (!source) throw new TypeError(`unsupported Apple official provider: ${evidence.provider_id}`)
  if (evidence.official_url !== source.official_url) {
    throw new TypeError('official_url does not match declared Apple source')
  }
  if (evidence.source_class !== source.source_class) {
    throw new TypeError('source_class does not match declared Apple source')
  }
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_APPLE_OFFICIAL_PLATFORM_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: evidence.provider_id,
    state: 'OBSERVED_AVAILABLE',
    observed_capabilities: [source.capability],
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
