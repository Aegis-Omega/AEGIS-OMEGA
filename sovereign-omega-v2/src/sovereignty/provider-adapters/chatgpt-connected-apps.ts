// ============================================================
// ChatGPT connected-app surface -> Sovereign Provider Mesh adapter V1
// EPISTEMIC TIER: T1 observation adapter
// authority_effect = NONE
// ============================================================
//
// A connected/installed app is not execution authority and is not enough to
// become routable. Only a successful read probe can mint OBSERVED_AVAILABLE.
// Evidence deliberately excludes account identifiers and retrieved content.

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import {
  PROVIDER_MESH_SCHEMA_VERSION,
  type ProviderCapabilityV1,
  type ProviderObservationV1,
} from '../provider-mesh.js'

export const CHATGPT_CONNECTED_APP_CAPABILITIES_V1 = {
  'chatgpt-github': ['REPOSITORY_READ'],
  'chatgpt-google-drive': ['DOCUMENT_RETRIEVAL'],
  'chatgpt-gmail': ['EMAIL_RETRIEVAL'],
  'chatgpt-google-calendar': ['CALENDAR_READ'],
  'chatgpt-slack': ['COLLABORATION_READ'],
  'chatgpt-notion': ['KNOWLEDGE_BASE_READ'],
  'chatgpt-linear': ['WORK_TRACKING_READ'],
  'chatgpt-hubspot': ['CRM_READ'],
  'chatgpt-ads-manager': ['ADS_MANAGER_READ'],
  'chatgpt-legalquants-transactional': ['LEGAL_TRANSACTIONAL_GUIDANCE'],
  'chatgpt-semrush': ['SEO_INTELLIGENCE'],
  'chatgpt-linkedin': ['PROFESSIONAL_PROFILE_SEARCH'],
  'chatgpt-blockscout': ['BLOCKCHAIN_DATA_READ'],
  'chatgpt-sofa': ['AGENT_KNOWLEDGE_READ'],
  'chatgpt-dropbox': ['DOCUMENT_RETRIEVAL'],
  'chatgpt-sharepoint': ['DOCUMENT_RETRIEVAL'],
  'chatgpt-outlook-email': ['EMAIL_RETRIEVAL'],
  'chatgpt-outlook-calendar': ['CALENDAR_READ'],
  'chatgpt-scite': ['SCIENTIFIC_LITERATURE_READ'],
  'chatgpt-hugging-face': ['MODEL_HUB_READ'],
  'chatgpt-gitlab': ['REPOSITORY_READ'],
  'chatgpt-vercel': ['DEPLOYMENT_PLATFORM_READ'],
} as const satisfies Readonly<Record<string, readonly ProviderCapabilityV1[]>>

export type ChatGptConnectedAppIdV1 = keyof typeof CHATGPT_CONNECTED_APP_CAPABILITIES_V1

export type ChatGptConnectedAppOutcomeV1 =
  | 'READ_SUCCESS'
  | 'READ_FAILURE'
  | 'CONNECTED_NOT_PROBED'
  | 'NOT_CONNECTED'
  | 'ACCOUNT_UNAVAILABLE'
  | 'BILLING_BLOCKED'
  | 'NETWORK_REACHABLE'
  | 'QUOTA_EXHAUSTED'

export interface ChatGptConnectedAppEvidenceV1 {
  connector_id: ChatGptConnectedAppIdV1
  operation: string
  outcome: ChatGptConnectedAppOutcomeV1
  result_count: number
}

function isKnownConnector(value: string): value is ChatGptConnectedAppIdV1 {
  return Object.prototype.hasOwnProperty.call(CHATGPT_CONNECTED_APP_CAPABILITIES_V1, value)
}

export async function observeChatGptConnectedAppV1(
  evidence: ChatGptConnectedAppEvidenceV1,
  observation_generation: string,
): Promise<ProviderObservationV1> {
  if (!isKnownConnector(evidence.connector_id)) {
    throw new TypeError(`unsupported ChatGPT connected app: ${evidence.connector_id}`)
  }
  if (!evidence.operation.trim()) throw new TypeError('operation must be non-empty')
  if (!Number.isSafeInteger(evidence.result_count) || evidence.result_count < 0) {
    throw new TypeError('result_count must be a non-negative safe integer')
  }
  if (!/^(0|[1-9][0-9]*)$/.test(observation_generation)) {
    throw new TypeError('observation_generation must be canonical unsigned decimal')
  }

  const evidence_hash = await sha256Hex(canonicalizeJCS({
    domain: 'AEGIS_CHATGPT_CONNECTED_APP_EVIDENCE_V1',
    evidence,
  })) as SHA256Hex

  const successfulRead = evidence.outcome === 'READ_SUCCESS'
  const state = successfulRead
    ? 'OBSERVED_AVAILABLE'
    : evidence.outcome === 'ACCOUNT_UNAVAILABLE' || evidence.outcome === 'NOT_CONNECTED' || evidence.outcome === 'QUOTA_EXHAUSTED'
      ? 'OBSERVED_UNAVAILABLE'
      : evidence.outcome === 'BILLING_BLOCKED'
        ? 'BILLING_BLOCKED'
        : evidence.outcome === 'NETWORK_REACHABLE'
          ? 'NETWORK_REACHABLE'
          : evidence.outcome === 'CONNECTED_NOT_PROBED'
            ? 'ACCOUNT_CONFIGURED'
            : 'UNKNOWN'

  const observed_capabilities =
    successfulRead ||
    evidence.outcome === 'BILLING_BLOCKED' ||
    evidence.outcome === 'NETWORK_REACHABLE' ||
    evidence.outcome === 'QUOTA_EXHAUSTED'
      ? [...CHATGPT_CONNECTED_APP_CAPABILITIES_V1[evidence.connector_id]]
      : []

  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id: evidence.connector_id,
    state,
    observed_capabilities,
    evidence_hash,
    observation_generation,
    authority_effect: 'NONE',
  }
}
