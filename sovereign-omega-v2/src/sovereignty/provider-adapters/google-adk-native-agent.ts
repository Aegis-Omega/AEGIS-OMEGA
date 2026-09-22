// ============================================================
// AEGIS Google Cloud ADK Provider-Native Agent Adapter V1
// EPISTEMIC TIER: T1 — injected ADK execution, zero granted authority
// authority_effect = NONE
// ============================================================

import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import type { ProviderMeshSnapshotV1 } from '../provider-mesh.js'
import {
  selectProviderNativeAgentV1,
  type ProviderNativeAgentRegistryV1,
  type ProviderNativeAgentSelectionReceiptV1,
} from '../provider-native-agents.js'

export const GOOGLE_ADK_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION = '1.0.0' as const

export interface GoogleAdkAgentRunnerOutputV1 {
  readonly final_output: string
  readonly session_id: string
  readonly model: string
}

export interface GoogleAdkAgentRunnerV1 {
  run(input: {
    readonly agent_name: 'aegis_google_provider_agent'
    readonly instruction: string
    readonly task: string
    readonly tools: readonly []
  }): Promise<GoogleAdkAgentRunnerOutputV1>
}

export function createGoogleAdkNativeAgentAdapterV1(options: {
  readonly runner: GoogleAdkAgentRunnerV1
}): {
  execute(input: {
    readonly snapshot: ProviderMeshSnapshotV1
    readonly registry: ProviderNativeAgentRegistryV1
    readonly task: string
    readonly current_generation: string
    readonly max_observation_age_generations: string
  }): Promise<{
    readonly selection: ProviderNativeAgentSelectionReceiptV1
    readonly output: GoogleAdkAgentRunnerOutputV1 | null
    readonly receipt: null | {
      readonly schema_version: typeof GOOGLE_ADK_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION
      readonly provider_id: 'google-cloud'
      readonly agent_id: 'provider-agent:google-cloud'
      readonly provider_selection_receipt_root: SHA256Hex
      readonly native_session_id: string
      readonly model: string
      readonly task_hash: SHA256Hex
      readonly output_hash: SHA256Hex
      readonly write_authority: 'NOT_GRANTED'
      readonly merge_authority: 'NOT_GRANTED'
      readonly deploy_authority: 'NOT_GRANTED'
      readonly financial_authority: 'NOT_GRANTED'
      readonly authority_effect: 'NONE'
      readonly receipt_root: SHA256Hex
    }
  }>
} {
  return {
    async execute(input) {
      if (!input.task.trim()) throw new TypeError('task must be non-empty')
      const selection = await selectProviderNativeAgentV1(input.snapshot, input.registry, {
        required_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
        allowed_providers: ['google-cloud'],
        preferred_provider_order: ['google-cloud'],
        current_generation: input.current_generation,
        max_observation_age_generations: input.max_observation_age_generations,
      })
      if (selection.outcome !== 'SELECTED' || selection.provider_id !== 'google-cloud') {
        return { selection, output: null, receipt: null }
      }

      const task_hash = await sha256Hex(canonicalizeJCS({
        domain: 'AEGIS_GOOGLE_ADK_NATIVE_AGENT_TASK_V1',
        task: input.task,
      })) as SHA256Hex

      const output = await options.runner.run({
        agent_name: 'aegis_google_provider_agent',
        instruction: 'You are the Google Cloud ADK provider-native agent inside AEGIS Omega. Return evidence only. You have no external mutation authority.',
        task: input.task,
        tools: [],
      })
      if (!output.session_id.trim()) throw new TypeError('Google ADK session_id must be non-empty')
      if (!output.model.trim()) throw new TypeError('Google ADK model must be non-empty')

      const output_hash = await sha256Hex(canonicalizeJCS({
        domain: 'AEGIS_GOOGLE_ADK_NATIVE_AGENT_OUTPUT_V1',
        session_id: output.session_id,
        model: output.model,
        final_output: output.final_output,
      })) as SHA256Hex

      const body = {
        schema_version: GOOGLE_ADK_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION,
        provider_id: 'google-cloud' as const,
        agent_id: 'provider-agent:google-cloud' as const,
        provider_selection_receipt_root: selection.receipt_root,
        native_session_id: output.session_id,
        model: output.model,
        task_hash,
        output_hash,
        write_authority: 'NOT_GRANTED' as const,
        merge_authority: 'NOT_GRANTED' as const,
        deploy_authority: 'NOT_GRANTED' as const,
        financial_authority: 'NOT_GRANTED' as const,
        authority_effect: 'NONE' as const,
      }
      const receipt_root = await sha256Hex(canonicalizeJCS({
        domain: 'AEGIS_GOOGLE_ADK_NATIVE_AGENT_EXECUTION_RECEIPT_V1',
        receipt: body,
      })) as SHA256Hex
      return { selection, output, receipt: { ...body, receipt_root } }
    },
  }
}
