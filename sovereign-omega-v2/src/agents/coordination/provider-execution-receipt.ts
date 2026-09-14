import type { SHA256Hex } from '../../core/types.js'
import { hashValue } from '../../core/hashing.js'
import type { ProviderCognitiveProfile, ProviderReasoningProfile } from './provider-cognition.js'

export interface ProviderExecutionReceiptV1 {
  readonly receipt_kind: 'AEGIS_PROVIDER_EXECUTION_RECEIPT_V1'
  readonly schema_version: '1.0.0'
  readonly provider: ProviderCognitiveProfile['provider']
  readonly work_class: ProviderCognitiveProfile['work_class']
  readonly model: string
  readonly reasoning: ProviderReasoningProfile
  readonly storage: 'stateless'
  readonly tool_policy: 'AEGIS_CAPABILITY_GATED'
  readonly task_digest: SHA256Hex
  readonly output_digest: SHA256Hex
  readonly tool_policy_digest: SHA256Hex
  readonly authority_class: 'NONE'
  readonly receipt_hash: SHA256Hex
}

export interface BuildProviderExecutionReceiptV1Input {
  readonly profile: ProviderCognitiveProfile
  readonly task_digest: SHA256Hex
  readonly output_digest: SHA256Hex
  readonly tool_policy_digest: SHA256Hex
}

export async function buildProviderExecutionReceiptV1(
  input: BuildProviderExecutionReceiptV1Input,
): Promise<ProviderExecutionReceiptV1> {
  const payload = Object.freeze({
    receipt_kind: 'AEGIS_PROVIDER_EXECUTION_RECEIPT_V1' as const,
    schema_version: '1.0.0' as const,
    provider: input.profile.provider,
    work_class: input.profile.work_class,
    model: input.profile.model,
    reasoning: input.profile.reasoning,
    storage: input.profile.storage,
    tool_policy: input.profile.tool_policy,
    task_digest: input.task_digest,
    output_digest: input.output_digest,
    tool_policy_digest: input.tool_policy_digest,
    authority_class: 'NONE' as const,
  })
  const receipt_hash = await hashValue(payload)
  return Object.freeze({ ...payload, receipt_hash })
}
