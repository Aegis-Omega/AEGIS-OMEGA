import { describe, expect, it, vi } from 'vitest'
import { GatewayError, InMemoryUsageMeter, InferenceGateway, type Authorizer, type InferenceProvider, type InferenceRequest, type InferenceTransport } from '../../src/api/inference-gateway.js'

const entitlement = { allowedDeployments: ['claude-prod', 'vertex-prod', 'foundry-prod'], monthlyHardLimitUsd: 10, maxInputTokens: 1000, maxOutputTokens: 500, maxConcurrent: 1 }
const authorizer: Authorizer = { authorize: vi.fn(async () => entitlement) }
const request = (provider: InferenceProvider, deployment: string, overrides: Partial<InferenceRequest> = {}): InferenceRequest => ({ tenantId: 'tenant-a', productTier: 'enterprise', requestId: 'request-1', correlationId: 'trace-1', idempotencyKey: 'idem-1', provider, deployment, inputTokens: 20, maxOutputTokens: 40, tokenCeiling: 40, budgetUsd: 1, payload: { messages: [] }, ...overrides })
const deployments = [
  { provider: 'anthropic' as const, name: 'claude-prod', model: 'claude-test', inputUsdPerMillion: 1, outputUsdPerMillion: 2 },
  { provider: 'vertex-ai' as const, name: 'vertex-prod', model: 'gemini-test', inputUsdPerMillion: 1, outputUsdPerMillion: 2 },
  { provider: 'microsoft-foundry' as const, name: 'foundry-prod', model: 'gpt-test', inputUsdPerMillion: 1, outputUsdPerMillion: 2 },
]
function transport(provider: InferenceProvider, invoke: InferenceTransport['invoke'] = vi.fn(async () => ({ value: { ok: true }, inputTokens: 20, outputTokens: 10 }))): InferenceTransport { return { provider, invoke } }

describe('InferenceGateway provider contract', () => {
  it.each([['anthropic', 'claude-prod'], ['vertex-ai', 'vertex-prod'], ['microsoft-foundry', 'foundry-prod']] as const)('admits %s only after entitlement and budget checks', async (provider, deployment) => {
    const mocked = transport(provider)
    const meter = new InMemoryUsageMeter()
    const gateway = new InferenceGateway(deployments, [mocked], authorizer, meter)
    await gateway.infer(request(provider, deployment))
    expect(mocked.invoke).toHaveBeenCalledOnce()
    expect(meter.records[0]).toMatchObject({ tenantId: 'tenant-a', provider, deployment, inputTokens: 20, outputTokens: 10, status: 'succeeded', correlationId: 'trace-1' })
  })

  it.each([['anthropic', 'claude-prod'], ['vertex-ai', 'vertex-prod'], ['microsoft-foundry', 'foundry-prod']] as const)('never invokes %s when authorization is unavailable', async (provider, deployment) => {
    const mocked = transport(provider)
    const unavailable: Authorizer = { authorize: async () => { throw new Error('offline') } }
    const gateway = new InferenceGateway(deployments, [mocked], unavailable, new InMemoryUsageMeter())
    await expect(gateway.infer(request(provider, deployment))).rejects.toMatchObject({ code: 'METERING_UNAVAILABLE' satisfies GatewayError['code'] })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('fails closed for metering failure, disallowed deployment, and monthly hard limit', async () => {
    const mocked = transport('anthropic')
    const unavailableMeter = { monthlySpendUsd: async () => { throw new Error('offline') }, record: async () => {} }
    await expect(new InferenceGateway(deployments, [mocked], authorizer, unavailableMeter).infer(request('anthropic', 'claude-prod'))).rejects.toMatchObject({ code: 'METERING_UNAVAILABLE' })
    await expect(new InferenceGateway(deployments, [mocked], authorizer, new InMemoryUsageMeter()).infer(request('anthropic', 'not-allowlisted'))).rejects.toMatchObject({ code: 'UNAUTHORIZED' })
    const overLimit: Authorizer = { authorize: async () => ({ ...entitlement, monthlyHardLimitUsd: 0.000001 }) }
    await expect(new InferenceGateway(deployments, [mocked], overLimit, new InMemoryUsageMeter()).infer(request('anthropic', 'claude-prod'))).rejects.toMatchObject({ code: 'LIMIT_EXCEEDED' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('enforces idempotency and concurrency before a provider receives a duplicate or excess request', async () => {
    let release: (() => void) | undefined
    const blocked = new Promise<void>(resolve => { release = resolve })
    const mocked = transport('anthropic', vi.fn(async () => { await blocked; return { value: {}, inputTokens: 20, outputTokens: 10 } }))
    const gateway = new InferenceGateway(deployments, [mocked], authorizer, new InMemoryUsageMeter())
    const first = gateway.infer(request('anthropic', 'claude-prod'))
    await expect(gateway.infer(request('anthropic', 'claude-prod', { idempotencyKey: 'idem-2', requestId: 'request-2' }))).rejects.toMatchObject({ code: 'LIMIT_EXCEEDED' })
    const duplicate = gateway.infer(request('anthropic', 'claude-prod'))
    release?.()
    await Promise.all([first, duplicate])
    expect(mocked.invoke).toHaveBeenCalledOnce()
  })

  it('routes batch items through the same entitlement boundary', async () => {
    const mocked = transport('anthropic')
    const gateway = new InferenceGateway(deployments, [mocked], authorizer, new InMemoryUsageMeter())
    await expect(gateway.inferBatch([request('anthropic', 'claude-prod'), request('anthropic', 'not-allowlisted', { idempotencyKey: 'idem-3', requestId: 'request-3' })])).rejects.toMatchObject({ code: 'UNAUTHORIZED' })
    expect(mocked.invoke).toHaveBeenCalledOnce()
  })
})
