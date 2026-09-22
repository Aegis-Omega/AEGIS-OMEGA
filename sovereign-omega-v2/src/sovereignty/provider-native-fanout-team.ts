// Connect #598's real SDK-runtime source and native adapters to #597's fanout.
// No SDK is imported at construction. No default authorizer or verifier exists.
// SDK installation, credentials, cost admission and process isolation are external.
import type {SHA256Hex} from '../core/types.js'
import {canonicalizeJCSString} from '../core/canonicalize.js'
import {createOpenAINativeAgentAdapterV1} from './provider-adapters/openai-native-agent.js'
import {createAnthropicNativeAgentAdapterV1} from './provider-adapters/anthropic-native-agent.js'
import {createGoogleAdkNativeAgentAdapterV1} from './provider-adapters/google-adk-native-agent.js'
import {
  createProviderNativeSdkRunnersV1,
  type ProviderNativeSdkRuntimeOptionsV1, type NativeSdkPackageV1,
} from './provider-adapters/provider-native-sdk-runtime.js'
import {
  createProviderNativeFanoutV1, certifyProviderNativeFanoutV1,
  type FanoutAdapterV1, type FanoutInputV1, type FanoutResultV1, type FanoutVerifierV1,
} from './provider-native-fanout.js'

const PROVIDERS = ['anthropic', 'google-cloud', 'openai'] as const
export interface NativeFanoutTeamConfigurationV1 {
  readonly schema_version: '1.0.0'
  readonly authorization_policy_hash: SHA256Hex
  readonly models: ProviderNativeSdkRuntimeOptionsV1['models']
  readonly maxTurns: number
  readonly maxOutputTokens: number
  readonly maxEvents: number
  readonly maxTaskChars: number
}
export interface NativeFanoutTeamOptionsV1 {
  readonly runtime: ProviderNativeSdkRuntimeOptionsV1
  readonly authorization_policy_hash: SHA256Hex
  readonly verifier: FanoutVerifierV1
}
function configurationFrom(options: Omit<NativeFanoutTeamOptionsV1, 'verifier'>): NativeFanoutTeamConfigurationV1 {
  const r = options.runtime
  if (typeof options.authorization_policy_hash !== 'string' || !/^[0-9a-f]{64}$/.test(options.authorization_policy_hash)) {
    throw new TypeError('authorization_policy_hash must be lowercase SHA-256 hex')
  }
  // These are the existing #598 defaults, now explicit in the task commitment.
  const configuration: NativeFanoutTeamConfigurationV1 = Object.freeze({
    schema_version: '1.0.0',
    authorization_policy_hash: options.authorization_policy_hash,
    models: Object.freeze({openai:r.models.openai, anthropic:r.models.anthropic, google_cloud:r.models.google_cloud}),
    maxTurns: r.maxTurns === undefined ? 2 : r.maxTurns,
    maxOutputTokens: r.maxOutputTokens === undefined ? 2048 : r.maxOutputTokens,
    maxEvents: r.maxEvents === undefined ? 64 : r.maxEvents,
    maxTaskChars: r.maxTaskChars === undefined ? 64000 : r.maxTaskChars,
  })
  for (const model of Object.values(configuration.models)) {
    if (typeof model !== 'string' || !model.trim() || new TextEncoder().encode(model).length > 256) {
      throw new TypeError('explicit bounded model labels are required')
    }
  }
  // Reuse the existing runtime's validation. This constructs closures only.
  createProviderNativeSdkRunnersV1({...configuration, authorize:r.authorize, ...(r.loadSdk === undefined ? {} : {loadSdk:r.loadSdk})})
  return configuration
}
function bindInput(input: FanoutInputV1, configuration: NativeFanoutTeamConfigurationV1): FanoutInputV1 {
  if (typeof input.task !== 'string' || !input.task.trim()) throw new TypeError('task must be non-empty')
  const captured = structuredClone(input)
  return {
    ...captured,
    task: canonicalizeJCSString({
      domain:'AEGIS_PROVIDER_NATIVE_FANOUT_TEAM_TASK_V1',
      runtime_configuration:configuration,
      task:captured.task,
    }),
  }
}

/** One persistent fanout per team: batch IDs and outstanding-work slots are not
 * reset on execute(). The host policy hash is a commitment, not a signature or
 * a grant. Native model labels remain configuration labels, not attestations. */
export function createProviderNativeFanoutTeamV1(options: NativeFanoutTeamOptionsV1) {
  const configuration = configurationFrom(options)
  const authorize = options.runtime.authorize
  const load = options.runtime.loadSdk ?? ((specifier: NativeSdkPackageV1) => import(specifier) as Promise<unknown>)
  const adapters: FanoutAdapterV1[] = PROVIDERS.map(provider_id => ({
    provider_id,
    async execute(input) {
      input.signal.throwIfAborted()
      // Guards stop late admission/import from starting a new provider call.
      // Once an SDK call has started, #598 does not promise cooperative abort:
      // #597 retains the slot until settlement and never confirms cancellation.
      const runners = createProviderNativeSdkRunnersV1({
        ...configuration,
        async authorize(request) {
          if (input.signal.aborted) return false
          const allowed = await authorize(request)
          return !input.signal.aborted && allowed === true
        },
        async loadSdk(specifier) {
          input.signal.throwIfAborted()
          const module = await load(specifier)
          input.signal.throwIfAborted()
          return module
        },
      })
      if (provider_id === 'openai') {
        return createOpenAINativeAgentAdapterV1({runner:runners.openai}).execute(input)
      }
      if (provider_id === 'anthropic') {
        return createAnthropicNativeAgentAdapterV1({runner:runners.anthropic}).execute(input)
      }
      return createGoogleAdkNativeAgentAdapterV1({runner:runners.google_cloud}).execute(input)
    },
  }))
  const fanout = createProviderNativeFanoutV1({adapters, verifier:options.verifier})
  return Object.freeze({
    configuration,
    agent_ids:Object.freeze(PROVIDERS.map(provider=>`provider-agent:${provider}`)),
    async execute(input: FanoutInputV1): Promise<FanoutResultV1> {
      // No await before capture and the existing fanout admission/locking path.
      return fanout.execute(bindInput(input, configuration))
    },
  })
}

/** Structural replay against an independently supplied, trusted configuration.
 * Does not call the authorizer, verifier or SDK and does not assert world truth. */
export async function certifyProviderNativeFanoutTeamV1(
  input: FanoutInputV1, result: FanoutResultV1, configuration: NativeFanoutTeamConfigurationV1,
): Promise<boolean> {
  try {
    const expected = configurationFrom({
      runtime:{...configuration, authorize:()=>false},
      authorization_policy_hash:configuration.authorization_policy_hash,
    })
    if (canonicalizeJCSString(configuration) !== canonicalizeJCSString(expected)) return false
    return await certifyProviderNativeFanoutV1(bindInput(input, expected), result)
  } catch {return false}
}
