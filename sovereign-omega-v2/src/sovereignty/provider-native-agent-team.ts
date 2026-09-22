// Compose the existing #596 native adapters and #595 conductor; no new selector.
import {createProviderNativeConductorV1} from './provider-native-conductor.js'
import {createOpenAINativeAgentAdapterV1, type OpenAINativeAgentExecuteInputV1} from './provider-adapters/openai-native-agent.js'
import {createAnthropicNativeAgentAdapterV1} from './provider-adapters/anthropic-native-agent.js'
import {createGoogleAdkNativeAgentAdapterV1} from './provider-adapters/google-adk-native-agent.js'
import {createProviderNativeSdkRunnersV1, type ProviderNativeSdkRuntimeOptionsV1} from './provider-adapters/provider-native-sdk-runtime.js'

export interface ProviderNativeAgentTeamTaskV1 extends OpenAINativeAgentExecuteInputV1 {
  readonly preferred_provider_order?: readonly string[]
}

/** Host composition only. Models and invocation authorization are never task fields. */
export function createProviderNativeAgentTeamV1(options: ProviderNativeSdkRuntimeOptionsV1) {
  const runners = createProviderNativeSdkRunnersV1(options)
  const nativeAdapters = [
    ['openai', createOpenAINativeAgentAdapterV1({runner: runners.openai})],
    ['anthropic', createAnthropicNativeAgentAdapterV1({runner: runners.anthropic})],
    ['google-cloud', createGoogleAdkNativeAgentAdapterV1({runner: runners.google_cloud})],
  ] as const

  return Object.freeze({
    agent_ids: Object.freeze(nativeAdapters.map(([provider]) => `provider-agent:${provider}`)),
    async execute(input: ProviderNativeAgentTeamTaskV1) {
      // Keep each invocation isolated across awaits and concurrent callers.
      const captured = structuredClone(input)
      const conductor = createProviderNativeConductorV1({
        adapters: nativeAdapters.map(([provider_id, adapter]) => ({
          provider_id,
          async execute(task: string) {
            const result = await adapter.execute({...captured, task})
            if (result.selection.outcome !== 'SELECTED' ||
                result.selection.provider_id !== provider_id ||
                result.output === null || result.receipt === null) {
              throw new Error('native adapter did not return a selected execution receipt')
            }
            return {
              output: result.output.final_output,
              native_receipt_root: result.receipt.receipt_root,
            }
          },
        })),
      })
      return conductor.execute({
        ...captured,
        required_capabilities: ['AGENT_EXECUTION', 'MODEL_INFERENCE'],
      })
    },
  })
}
