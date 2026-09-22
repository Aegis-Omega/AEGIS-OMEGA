import type { SHA256Hex } from '../../core/types.js'
import { canonicalizeJCS } from '../../core/canonicalize.js'
import { sha256Hex } from '../../core/hashing.js'
import type { ProviderMeshSnapshotV1 } from '../provider-mesh.js'
import { selectProviderNativeAgentV1, type ProviderNativeAgentRegistryV1 } from '../provider-native-agents.js'
export const ANTHROPIC_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION='1.0.0' as const
export interface AnthropicAgentRunnerOutputV1 {readonly final_output:string;readonly session_id:string;readonly model:string}
export interface AnthropicAgentRunnerV1 {run(input:{readonly task:string;readonly system_prompt:string;readonly allowed_tools:readonly []}):Promise<AnthropicAgentRunnerOutputV1>}
export function createAnthropicNativeAgentAdapterV1(options:{readonly runner:AnthropicAgentRunnerV1}) {
 return {async execute(input:{readonly snapshot:ProviderMeshSnapshotV1;readonly registry:ProviderNativeAgentRegistryV1;readonly task:string;readonly current_generation:string;readonly max_observation_age_generations:string}) {
  if(!input.task.trim()) throw new TypeError('task must be non-empty')
  const selection=await selectProviderNativeAgentV1(input.snapshot,input.registry,{required_capabilities:['AGENT_EXECUTION','MODEL_INFERENCE'],allowed_providers:['anthropic'],preferred_provider_order:['anthropic'],current_generation:input.current_generation,max_observation_age_generations:input.max_observation_age_generations})
  if(selection.outcome!=='SELECTED'||selection.provider_id!=='anthropic') return {selection,output:null,receipt:null}
  const task_hash=await sha256Hex(canonicalizeJCS({domain:'AEGIS_ANTHROPIC_NATIVE_AGENT_TASK_V1',task:input.task})) as SHA256Hex
  const output=await options.runner.run({task:input.task,system_prompt:'You are the Anthropic provider-native agent inside AEGIS Omega. Return evidence only. You have no external mutation authority.',allowed_tools:[]})
  if(!output.session_id.trim()||!output.model.trim()) throw new TypeError('Anthropic native session/model must be non-empty')
  const output_hash=await sha256Hex(canonicalizeJCS({domain:'AEGIS_ANTHROPIC_NATIVE_AGENT_OUTPUT_V1',session_id:output.session_id,model:output.model,final_output:output.final_output})) as SHA256Hex
  const body={schema_version:ANTHROPIC_NATIVE_AGENT_ADAPTER_SCHEMA_VERSION,provider_id:'anthropic' as const,agent_id:'provider-agent:anthropic' as const,provider_selection_receipt_root:selection.receipt_root,native_session_id:output.session_id,model:output.model,task_hash,output_hash,write_authority:'NOT_GRANTED' as const,merge_authority:'NOT_GRANTED' as const,deploy_authority:'NOT_GRANTED' as const,financial_authority:'NOT_GRANTED' as const,authority_effect:'NONE' as const}
  const receipt_root=await sha256Hex(canonicalizeJCS({domain:'AEGIS_ANTHROPIC_NATIVE_AGENT_EXECUTION_RECEIPT_V1',receipt:body})) as SHA256Hex
  return {selection,output,receipt:{...body,receipt_root}}
 }}
}
