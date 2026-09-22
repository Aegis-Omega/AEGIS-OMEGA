// ============================================================
// AEGIS OpenAI Provider-Native Agent Adapter V1
// EPISTEMIC TIER: T1 — injected native execution, zero granted authority
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

export const OPENAI_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION = '1.0.0' as const
export interface OpenAIAgentRunnerInputV1 { readonly agent_name: 'AEGIS OpenAI Provider Agent'; readonly instructions: string; readonly task: string }
export interface OpenAIAgentRunnerOutputV1 { readonly final_output: string; readonly run_id: string; readonly model: string }
export interface OpenAIAgentRunnerV1 { run(input: OpenAIAgentRunnerInputV1): Promise<OpenAIAgentRunnerOutputV1> }

export function createOpenAINativeAgentAdapterV1(options: { readonly runner: OpenAIAgentRunnerV1 }) {
  return {
    async execute(input: { readonly snapshot: ProviderMeshSnapshotV1; readonly registry: ProviderNativeAgentRegistryV1; readonly task: string; readonly current_generation: string; readonly max_observation_age_generations: string }): Promise<{ selection: ProviderNativeAgentSelectionReceiptV1; output: OpenAIAgentRunnerOutputV1 | null; receipt: any | null }> {
      if (!input.task.trim()) throw new TypeError('task must be non-empty')
      const selection = await selectProviderNativeAgentV1(input.snapshot, input.registry, {
        required_capabilities: ['AGENT_EXECUTION','MODEL_INFERENCE'], allowed_providers: ['openai'], preferred_provider_order: ['openai'],
        current_generation: input.current_generation, max_observation_age_generations: input.max_observation_age_generations,
      })
      if (selection.outcome !== 'SELECTED' || selection.provider_id !== 'openai') return { selection, output: null, receipt: null }
      const task_hash = await sha256Hex(canonicalizeJCS({ domain:'AEGIS_OPENAI_NATIVE_AGENT_TASK_V1', task:input.task })) as SHA256Hex
      const output = await options.runner.run({ agent_name:'AEGIS OpenAI Provider Agent', instructions:'You are the OpenAI provider-native agent inside AEGIS Omega. Return evidence only. You have no external mutation authority.', task:input.task })
      if (!output.run_id.trim() || !output.model.trim()) throw new TypeError('native OpenAI run/model must be non-empty')
      const output_hash = await sha256Hex(canonicalizeJCS({ domain:'AEGIS_OPENAI_NATIVE_AGENT_OUTPUT_V1', native_run_id:output.run_id, model:output.model, final_output:output.final_output })) as SHA256Hex
      const body = { schema_version:OPENAI_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION, provider_id:'openai' as const, agent_id:'provider-agent:openai' as const, provider_selection_receipt_root:selection.receipt_root, native_run_id:output.run_id, model:output.model, task_hash, output_hash, write_authority:'NOT_GRANTED' as const, merge_authority:'NOT_GRANTED' as const, deploy_authority:'NOT_GRANTED' as const, financial_authority:'NOT_GRANTED' as const, authority_effect:'NONE' as const }
      const receipt_root = await sha256Hex(canonicalizeJCS({ domain:'AEGIS_OPENAI_NATIVE_AGENT_EXECUTION_RECEIPT_V1', receipt:body })) as SHA256Hex
      return { selection, output, receipt:{...body,receipt_root} }
    },
  }
}
