import { describe, expect, it, vi } from 'vitest'
import {
  FrontierHttpInferenceTransport,
  FrontierManagedInferenceTransport,
  FrontierTransportError,
  type FrontierCredentialHeaderResolver,
  type FrontierFetch,
  type FrontierManagedInvoker,
} from '../../src/api/frontier-provider-transports.js'
import type {
  FrontierDeployment,
  FrontierInferenceProvider,
  FrontierInferenceRequest,
  ProofCarryingWorkOrder,
} from '../../src/api/frontier-inference-gateway.js'
import { runtimeJsonPayloadDigest } from '../../src/api/frontier-inference-gateway.js'

const hex = (digit: string): string => digit.repeat(64)

const order = async (provider: FrontierInferenceProvider, deployment: string, payload: unknown): Promise<ProofCarryingWorkOrder> => ({
  schemaVersion: '1.0.0',
  workOrderId: `wo-${provider}`,
  requestId: `req-${provider}`,
  provider,
  capability: 'inference.run',
  target: deployment,
  consequenceClass: 'D3',
  argumentsDigest: await runtimeJsonPayloadDigest(payload),
  expectedParentStateRoot: hex('1'),
  idempotencyKey: `idem-${provider}-0001`,
  maxCostMicroUsd: 1_000_000,
  maxInputTokens: 1_000,
  maxOutputTokens: 500,
  evidenceReferences: ['receipt://admission/1'],
  operatorApprovalReference: 'approval://operator/1',
  issuedSequence: 1,
})

const request = async (provider: FrontierInferenceProvider, deployment: string): Promise<FrontierInferenceRequest> => {
  const payload = { messages: [{ role: 'user', content: 'hello' }] }
  return {
    tenantId: 'tenant-a',
    productTier: 'enterprise',
    requestId: `req-${provider}`,
    correlationId: 'trace-1',
    idempotencyKey: `idem-${provider}-0001`,
    provider,
    deployment,
    consequenceClass: 'D3',
    inputTokens: 100,
    maxOutputTokens: 200,
    tokenCeiling: 300,
    budgetMicroUsd: 500_000,
    payload,
    payloadDigest: await runtimeJsonPayloadDigest(payload),
    expectedParentStateRoot: hex('1'),
    workOrder: await order(provider, deployment, payload),
    stream: false,
  }
}

const deployment = (provider: FrontierInferenceProvider): FrontierDeployment => ({
  provider,
  name: `${provider}-prod`,
  model: `${provider}-configured-model`,
  inputMicroUsdPerMillion: 1,
  outputMicroUsdPerMillion: 1,
})

class FakeHeaders implements FrontierCredentialHeaderResolver {
  async resolve(_provider: FrontierInferenceProvider, _reference: string): Promise<Record<string, string>> {
    return { authorization: 'Bearer runtime-only-secret' }
  }
}

const response = (body: object, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: (name: string) => name.toLowerCase() === 'x-request-id' ? 'header-request-1' : null },
  text: async () => JSON.stringify(body),
})

describe('Frontier HTTP provider transports', () => {
  it.each([
    ['openai', 'openai-responses', 'https://api.openai.com', '/v1/responses'],
    ['vercel-ai-gateway', 'openai-responses', 'https://ai-gateway.vercel.sh', '/v1/responses'],
    ['xai', 'openai-responses', 'https://api.x.ai', '/v1/responses'],
    ['nvidia-nim', 'openai-responses', 'https://integrate.api.nvidia.com', '/v1/responses'],
    ['anthropic', 'anthropic-messages', 'https://api.anthropic.com', '/v1/messages'],
    ['mistral', 'openai-compatible-chat', 'https://api.mistral.ai/v1', '/chat/completions'],
    ['deepseek', 'openai-compatible-chat', 'https://api.deepseek.com', '/chat/completions'],
    ['qwen-dashscope', 'openai-compatible-chat', 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1', '/chat/completions'],
    ['huggingface', 'openai-compatible-chat', 'https://router.huggingface.co/v1', '/chat/completions'],
  ] as const)('executes %s through its declared HTTP protocol without granting authority', async (provider, protocol, baseUrl, path) => {
    const calls: Array<{ url: string, init: { headers: Record<string, string>, body: string } }> = []
    const fetcher: FrontierFetch = vi.fn(async (url, init) => {
      calls.push({ url, init })
      return response({ id: `op-${provider}`, usage: { input_tokens: 10, output_tokens: 5 } })
    })
    const transport = new FrontierHttpInferenceTransport({
      provider,
      protocol,
      baseUrl,
      authReference: `secret://${provider}/aegisomega`,
    }, new FakeHeaders(), fetcher)
    const req = await request(provider, `${provider}-prod`)

    const evidence = await transport.invoke(req.payload, deployment(provider), req)

    expect(calls[0]?.url).toBe(`${baseUrl}${path}`)
    expect(JSON.parse(calls[0]!.init.body)).toMatchObject({ model: `${provider}-configured-model` })
    expect(evidence.providerOperationId).toBe(`op-${provider}`)
    expect(evidence.grantsAuthority).toBe(false)
    expect(JSON.stringify(evidence)).not.toContain('runtime-only-secret')
  })

  it('uses Anthropic API-key header supplied only by the runtime credential resolver', async () => {
    const headers: FrontierCredentialHeaderResolver = {
      resolve: async () => ({ 'x-api-key': 'runtime-anthropic-secret', 'anthropic-version': '2023-06-01' }),
    }
    const calls: Array<{ headers: Record<string, string> }> = []
    const fetcher: FrontierFetch = vi.fn(async (_url, init) => {
      calls.push({ headers: init.headers })
      return response({ id: 'msg-1', usage: { input_tokens: 3, output_tokens: 4 } })
    })
    const transport = new FrontierHttpInferenceTransport({
      provider: 'anthropic',
      protocol: 'anthropic-messages',
      baseUrl: 'https://api.anthropic.com',
      authReference: 'secret://anthropic/aegisomega',
    }, headers, fetcher)
    const req = await request('anthropic', 'anthropic-prod')

    await transport.invoke(req.payload, deployment('anthropic'), req)

    expect(calls[0]?.headers['x-api-key']).toBe('runtime-anthropic-secret')
  })

  it('rejects a protocol/provider combination outside the frontier registry', () => {
    expect(() => new FrontierHttpInferenceTransport({
      provider: 'anthropic',
      protocol: 'openai-responses',
      baseUrl: 'https://api.anthropic.com',
      authReference: 'secret://anthropic/aegisomega',
    }, new FakeHeaders(), vi.fn())).toThrow(FrontierTransportError)
  })

  it('fails closed on non-success provider response', async () => {
    const fetcher: FrontierFetch = vi.fn(async () => response({ error: { message: 'nope' } }, 429))
    const transport = new FrontierHttpInferenceTransport({
      provider: 'openai',
      protocol: 'openai-responses',
      baseUrl: 'https://api.openai.com',
      authReference: 'secret://openai/aegisomega',
    }, new FakeHeaders(), fetcher)
    const req = await request('openai', 'openai-prod')

    await expect(transport.invoke(req.payload, deployment('openai'), req)).rejects.toMatchObject({ code: 'PROVIDER_HTTP_ERROR' })
  })
})

describe('Frontier managed provider transports', () => {
  it.each(['google-vertex', 'microsoft-foundry', 'aws-bedrock'] as const)('executes %s only through an injected managed identity/SDK invoker', async provider => {
    const invoker: FrontierManagedInvoker = {
      invoke: vi.fn(async () => ({
        value: { ok: true },
        providerOperationId: `op-${provider}`,
        responseDigest: hex('4'),
        inputTokens: 12,
        outputTokens: 7,
        grantsAuthority: false,
      })),
    }
    const transport = new FrontierManagedInferenceTransport(provider, invoker)
    const req = await request(provider, `${provider}-prod`)

    const evidence = await transport.invoke(req.payload, deployment(provider), req)

    expect(invoker.invoke).toHaveBeenCalledOnce()
    expect(evidence.grantsAuthority).toBe(false)
  })

  it('rejects non-managed provider construction', () => {
    const invoker: FrontierManagedInvoker = { invoke: vi.fn() }
    expect(() => new FrontierManagedInferenceTransport('openai', invoker)).toThrow(FrontierTransportError)
  })
})
