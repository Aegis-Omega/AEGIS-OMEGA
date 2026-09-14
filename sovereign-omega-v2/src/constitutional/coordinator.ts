// ============================================================
// SOVEREIGN OMEGA — Orchestration Alliance Coordinator Identity
// EPISTEMIC TIER: T2 · Gate 218
//
// External model providers are constitutional participants, not authority
// sources. Their effective model identity is selected by the provider-native
// cognitive depth policy and remains subordinate to AEGIS verification.
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { EpistemicTier } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { AgentManifest } from '../agents/types.js'
import { AGENT_MANIFEST_SCHEMA_VERSION } from '../agents/types.js'
import type { ModelEndpoint } from '../agents/coordination/swarm-router.js'
import { selectAllianceProviderProfile } from '../agents/coordination/provider-cognition.js'

export const COORDINATOR_SCHEMA_VERSION = '1.0.0' as const

export const CLAUDE_ARABIC_NAME = 'كلود' as const
export const CLAUDE_ABJAD_SUM = 60 as const
export const CLAUDE_ABJAD_DR = 6 as const
export const CLAUDE_ABJAD_NODE = 0 as const
export const CLAUDE_ABJAD_PRODUCT = 14400 as const
export const CLAUDE_ABJAD_PRODUCT_DR = 9 as const
export const COORDINATOR_ENTROPY_BUDGET_Q16 = 40503 as const

export type OrchestrationRole =
  | 'coordinator'
  | 'adversarial-audit'
  | 'implementation'

export interface AllianceMember {
  readonly model_id: string
  readonly provider: 'anthropic' | 'openai' | 'dashscope'
  readonly role: OrchestrationRole
  readonly endpoint: ModelEndpoint
  readonly is_replay_reconstructable: true
}

export interface CoordinatorRecord {
  readonly model_id: string
  readonly arabic_name: typeof CLAUDE_ARABIC_NAME
  readonly abjad_sum: typeof CLAUDE_ABJAD_SUM
  readonly abjad_dr: typeof CLAUDE_ABJAD_DR
  readonly abjad_node: typeof CLAUDE_ABJAD_NODE
  readonly abjad_product: typeof CLAUDE_ABJAD_PRODUCT
  readonly abjad_product_dr: typeof CLAUDE_ABJAD_PRODUCT_DR
  readonly is_triadic: true
  readonly is_triadic_attractor: true
  readonly role: 'coordinator'
  readonly agent_manifest: AgentManifest
  readonly coordinator_hash: SHA256Hex
  readonly schema_version: typeof COORDINATOR_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

const COORDINATOR_MANIFEST: AgentManifest = deepFreeze({
  schema_version: AGENT_MANIFEST_SCHEMA_VERSION,
  agent_id: 'claude-coordinator',
  name: 'Claude — Orchestration Alliance Coordinator',
  agent_type: 'ArbitrationAgent',
  epistemic_tier: EpistemicTier.T2,
  capability_manifest: deepFreeze({
    capability_ids: [
      'research-synthesis',
      'constitutional-arbitration',
      'swarm-coordination',
      'tier-classification',
      'replay-audit',
      'implementation-review',
    ],
    invariant_bindings: [
      'AdaptivePower(T) <= ReplayVerifiability(T)',
      'epistemic_tier <= T2',
      'is_replay_safe = true',
      'entropy_bounded_at_golden_ratio',
      'provider_intelligence != authority',
    ],
    telemetry_schema_version: '1.0.0',
  }),
  is_replay_safe: true,
  entropy_budget_fixed: COORDINATOR_ENTROPY_BUDGET_Q16,
  workspace_boundary: deepFreeze([
    '/sovereign-omega-v2/src/',
    '/aegis-cl-psi/src/',
    '/aegis-runtime/src/',
    '/cockpit/src/',
    '/studio/src/',
  ]),
  status: 'active',
})

export const CLAUDE_COGNITIVE_PROFILE = selectAllianceProviderProfile('coordinator')
export const CHATGPT_COGNITIVE_PROFILE = selectAllianceProviderProfile('adversarial-audit')
export const QWEN_COGNITIVE_PROFILE = selectAllianceProviderProfile('implementation')

export const CLAUDE_ENDPOINT: ModelEndpoint = deepFreeze({
  model_id: CLAUDE_COGNITIVE_PROFILE.model,
  provider: 'anthropic',
  endpoint_url: 'https://api.anthropic.com/v1',
  weight: 618,
  is_active: true,
})

export const CHATGPT_ENDPOINT: ModelEndpoint = deepFreeze({
  model_id: CHATGPT_COGNITIVE_PROFILE.model,
  provider: 'openai',
  endpoint_url: 'https://api.openai.com/v1',
  weight: 191,
  is_active: true,
})

export const QWEN_ENDPOINT: ModelEndpoint = deepFreeze({
  model_id: QWEN_COGNITIVE_PROFILE.model,
  provider: 'dashscope',
  endpoint_url: 'https://dashscope.aliyuncs.com/api/v1',
  weight: 191,
  is_active: true,
})

export const ORCHESTRATION_ALLIANCE: readonly AllianceMember[] = deepFreeze([
  {
    model_id: CLAUDE_ENDPOINT.model_id,
    provider: 'anthropic',
    role: 'coordinator',
    endpoint: CLAUDE_ENDPOINT,
    is_replay_reconstructable: true,
  },
  {
    model_id: CHATGPT_ENDPOINT.model_id,
    provider: 'openai',
    role: 'adversarial-audit',
    endpoint: CHATGPT_ENDPOINT,
    is_replay_reconstructable: true,
  },
  {
    model_id: QWEN_ENDPOINT.model_id,
    provider: 'dashscope',
    role: 'implementation',
    endpoint: QWEN_ENDPOINT,
    is_replay_reconstructable: true,
  },
])

export async function buildCoordinatorRecord(): Promise<CoordinatorRecord> {
  const coordinator_hash = await hashValue({
    model_id: CLAUDE_COGNITIVE_PROFILE.model,
    cognitive_profile: CLAUDE_COGNITIVE_PROFILE,
    arabic_name: CLAUDE_ARABIC_NAME,
    abjad_sum: CLAUDE_ABJAD_SUM,
    abjad_node: CLAUDE_ABJAD_NODE,
    role: 'coordinator',
    schema_version: COORDINATOR_SCHEMA_VERSION,
  })

  return deepFreeze({
    model_id: CLAUDE_COGNITIVE_PROFILE.model,
    arabic_name: CLAUDE_ARABIC_NAME,
    abjad_sum: CLAUDE_ABJAD_SUM,
    abjad_dr: CLAUDE_ABJAD_DR,
    abjad_node: CLAUDE_ABJAD_NODE,
    abjad_product: CLAUDE_ABJAD_PRODUCT,
    abjad_product_dr: CLAUDE_ABJAD_PRODUCT_DR,
    is_triadic: true,
    is_triadic_attractor: true,
    role: 'coordinator',
    agent_manifest: COORDINATOR_MANIFEST,
    coordinator_hash,
    schema_version: COORDINATOR_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

export function verifyCoordinatorRecord(record: CoordinatorRecord): boolean {
  return (
    record.model_id === CLAUDE_COGNITIVE_PROFILE.model &&
    record.abjad_sum === CLAUDE_ABJAD_SUM &&
    record.abjad_dr === CLAUDE_ABJAD_DR &&
    record.abjad_node === CLAUDE_ABJAD_NODE &&
    record.abjad_product === CLAUDE_ABJAD_PRODUCT &&
    record.abjad_product_dr === CLAUDE_ABJAD_PRODUCT_DR &&
    record.is_triadic === true &&
    record.is_triadic_attractor === true &&
    record.role === 'coordinator' &&
    record.agent_manifest.is_replay_safe === true &&
    record.agent_manifest.epistemic_tier === 'T2' &&
    record.agent_manifest.entropy_budget_fixed === COORDINATOR_ENTROPY_BUDGET_Q16 &&
    record.is_replay_reconstructable === true
  )
}
