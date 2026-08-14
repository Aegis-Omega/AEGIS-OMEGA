import { describe, expect, it, vi } from 'vitest'
import {
  InMemoryFrontierUsageMeter,
  type FrontierAuthorizer,
  type FrontierDeployment,
  type FrontierInferenceProvider,
  type StreamLeaseVerifier,
  type WorkOrderVerifier,
} from '../../src/api/frontier-inference-gateway.js'
import {
  buildFrontierRuntime,
  FrontierRuntimeError,
  type FrontierRuntimeConnection,
} from '../../src/api/frontier-runtime.js'
import type {
  FrontierCredentialHeaderResolver,
  FrontierFetch,
  FrontierManagedInvoker,
} from '../../src/api/frontier-provider-transports.js'

const PROVIDERS: readonly FrontierInferenceProvider[] = [
  'openai', 'anthropic', 'google-vertex', 'microsoft-foundry', 'aws-bedrock', 'vercel-ai-gateway',
  'xai', 'mistral', 'deepseek', 'qwen-dashscope', 'nvidia-nim', 'huggingface',
]

const deployments: FrontierDeployment[] = PROVIDERS.map(provider => ({
  provider,
  name: `${provider}-prod`,
  model: `${provider}-configured-model`,
  inputMicroUsdPerMillion: 1,
  outputMicroUsdPerMillion: 1,
}))

const connections: FrontierRuntimeConnection[] = [
  { kind: 'http', provider: 'openai', protocol: 'openai-responses', baseUrl: 'https://api.openai.com', authReference: 'secret://openai/aegisomega' },
  { kind: 'http', provider: 'anthropic', protocol: 'anthropic-messages', baseUrl: 'https://api.anthropic.com', authReference: 'secret://anthropic/aegisomega' },
  { kind: 'managed', provider: 'google-vertex' },
  { kind: 'managed', provider: 'microsoft-foundry' },
  { kind: 'managed', provider: 'aws-bedrock' },
  { kind: 'http', provider: 'vercel-ai-gateway', protocol: 'openai-responses', baseUrl: 'https://ai-gateway.vercel.sh', authReference: 'secret://vercel/aegisomega' },
  { kind: 'http', provider: 'xai', protocol: 'openai-responses', baseUrl: 'https://api.x.ai', authReference: 'secret://xai/aegisomega' },
  { kind: 'http', provider: 'mistral', protocol: 'openai-compatible-chat', baseUrl: 'https://api.mistral.ai/v1', authReference: 'secret://mistral/aegisomega' },
  { kind: 'http', provider: 'deepseek', protocol: 'openai-compatible-chat', baseUrl: 'https://api.deepseek.com', authReference: 'secret://deepseek/aegisomega' },
  { kind: 'http', provider: 'qwen-dashscope', protocol: 'openai-compatible-chat', baseUrl: 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', authReference: 'secret://qwen/aegisomega' },
  { kind: 'http', provider: 'nvidia-nim', protocol: 'openai-responses', baseUrl: 'https://integrate.api.nvidia.com', authReference: 'secret://nvidia/aegisomega' },
  { kind: 'http', provider: 'huggingface', protocol: 'openai-compatible-chat', baseUrl: 'https://router.huggingface.co/v1', authReference: 'secret://huggingface/aegisomega' },
]

const authorizer: FrontierAuthorizer = {
  authorize: async () => ({
    allowedDeployments: deployments.map(item => item.name),
    monthlyHardLimitMicroUsd: 10_000_000,
    maxInputTokens: 10_000,
    maxOutputTokens: 5_000,
    maxConcurrent: 4,
  }),
}
const workOrderVerifier: WorkOrderVerifier = { verify: async () => ({ valid: true, digest: 'a'.repeat(64) }) }
const streamLeaseVerifier: StreamLeaseVerifier = { verify: async () => true }
const credentialHeaders: FrontierCredentialHeaderResolver = { resolve: async () => ({ authorization: 'Bearer runtime-only' }) }
const fetcher: FrontierFetch = vi.fn()
const managedInvoker: FrontierManagedInvoker = { invoke: vi.fn() }

const dependencies = () => ({
  authorizer,
  meter: new InMemoryFrontierUsageMeter(),
  workOrderVerifier,
  streamLeaseVerifier,
  credentialHeaders,
  fetcher,
  managedInvokers: {
    'google-vertex': managedInvoker,
    'microsoft-foundry': managedInvoker,
    'aws-bedrock': managedInvoker,
  } as const,
})

describe('buildFrontierRuntime', () => {
  it('composes all 12 frontier providers behind one gateway', () => {
    const runtime = buildFrontierRuntime({ deployments, connections }, dependencies())

    expect(runtime.configuredProviders).toEqual([...PROVIDERS].sort())
    expect(runtime.gateway).toBeDefined()
  })

  it('rejects duplicate provider connection definitions', () => {
    expect(() => buildFrontierRuntime({ deployments, connections: [...connections, connections[0]!] }, dependencies())).toThrow(FrontierRuntimeError)
  })

  it('rejects a connection without an admitted deployment', () => {
    expect(() => buildFrontierRuntime({ deployments: deployments.filter(item => item.provider !== 'openai'), connections }, dependencies())).toThrow(FrontierRuntimeError)
  })

  it('rejects managed providers without an injected managed runtime', () => {
    const deps = dependencies()
    expect(() => buildFrontierRuntime(
      { deployments, connections },
      { ...deps, managedInvokers: { 'google-vertex': managedInvoker } },
    )).toThrow(FrontierRuntimeError)
  })

  it('rejects HTTP provider composition when fetch transport is unavailable', () => {
    const deps = dependencies()
    expect(() => buildFrontierRuntime(
      { deployments, connections },
      { ...deps, fetcher: undefined },
    )).toThrow(FrontierRuntimeError)
  })
})
