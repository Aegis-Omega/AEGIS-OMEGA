import { createHash } from 'node:crypto'
import { describe, expect, it, vi } from 'vitest'
import {
  FrontierGatewayError,
  FrontierInferenceGateway,
  InMemoryFrontierUsageMeter,
  type FrontierAuthorizer,
  type FrontierDeployment,
  type FrontierInferenceProvider,
  type FrontierInferenceRequest,
  type FrontierInferenceTransport,
  type FrontierProviderResult,
  type ProofCarryingWorkOrder,
  type StreamLeaseVerifier,
  type WorkOrderVerifier,
} from '../../src/api/frontier-inference-gateway.js'

const PROVIDERS: readonly FrontierInferenceProvider[] = [
  'openai',
  'anthropic',
  'google-vertex',
  'microsoft-foundry',
  'aws-bedrock',
  'vercel-ai-gateway',
  'xai',
  'mistral',
  'deepseek',
  'qwen-dashscope',
  'nvidia-nim',
  'huggingface',
]

const hex = (digit: string): string => digit.repeat(64)
const payload = { messages: [{ role: 'user', content: 'hello' }] }
const payloadDigest = createHash('sha256').update(JSON.stringify(payload)).digest('hex')

const entitlement = {
  allowedDeployments: PROVIDERS.map(provider => `${provider}-prod`),
  monthlyHardLimitMicroUsd: 10_000_000,
  maxInputTokens: 4_000,
  maxOutputTokens: 2_000,
  maxConcurrent: 2,
}
const authorizer: FrontierAuthorizer = { authorize: vi.fn(async () => entitlement) }

const workOrder = (
  provider: FrontierInferenceProvider,
  overrides: Partial<ProofCarryingWorkOrder> = {},
): ProofCarryingWorkOrder => ({
  schemaVersion: '1.0.0',
  workOrderId: `wo-${provider}`,
  requestId: `request-${provider}`,
  provider,
  capability: 'inference.run',
  target: `${provider}-prod`,
  consequenceClass: 'D3',
  argumentsDigest: payloadDigest,
  expectedParentStateRoot: hex('1'),
  idempotencyKey: `idem-${provider}-0001`,
  maxCostMicroUsd: 1_000_000,
  maxInputTokens: 1_000,
  maxOutputTokens: 500,
  evidenceReferences: ['receipt://admission/1'],
  operatorApprovalReference: 'approval://operator/1',
  secretReferences: [`secret://${provider}/aegisomega`],
  issuedSequence: 1,
  ...overrides,
})

const request = (
  provider: FrontierInferenceProvider,
  overrides: Partial<FrontierInferenceRequest> = {},
): FrontierInferenceRequest => ({
  tenantId: 'tenant-a',
  productTier: 'enterprise',
  requestId: `request-${provider}`,
  correlationId: 'trace-1',
  idempotencyKey: `idem-${provider}-0001`,
  provider,
  deployment: `${provider}-prod`,
  consequenceClass: 'D3',
  inputTokens: 100,
  maxOutputTokens: 200,
  tokenCeiling: 300,
  budgetMicroUsd: 500_000,
  payload,
  payloadDigest,
  expectedParentStateRoot: hex('1'),
  workOrder: workOrder(provider),
  stream: false,
  ...overrides,
})

const deployments: FrontierDeployment[] = PROVIDERS.map(provider => ({
  provider,
  name: `${provider}-prod`,
  model: `${provider}-configured-model`,
  inputMicroUsdPerMillion: 100_000,
  outputMicroUsdPerMillion: 200_000,
}))

const result = (provider: FrontierInferenceProvider, overrides: Partial<FrontierProviderResult> = {}): FrontierProviderResult => ({
  value: { ok: true },
  providerOperationId: `op-${provider}`,
  responseDigest: hex('2'),
  inputTokens: 100,
  outputTokens: 50,
  grantsAuthority: false,
  ...overrides,
})

const transport = (
  provider: FrontierInferenceProvider,
  invoke: FrontierInferenceTransport['invoke'] = vi.fn(async () => result(provider)),
): FrontierInferenceTransport => ({ provider, invoke })

const workOrderVerifier: WorkOrderVerifier = {
  verify: vi.fn(async () => ({ valid: true, digest: hex('3'), authorityReceiptRoot: hex('4') })),
}

const streamVerifier: StreamLeaseVerifier = {
  verify: vi.fn(async () => true),
}

describe('FrontierInferenceGateway proof-carrying contract', () => {
  it.each(PROVIDERS)('routes %s through the same work-order, entitlement and budget boundary', async provider => {
    const mocked = transport(provider)
    const meter = new InMemoryFrontierUsageMeter()
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, meter, workOrderVerifier, streamVerifier)

    const evidence = await gateway.infer(request(provider))

    expect(mocked.invoke).toHaveBeenCalledOnce()
    expect(evidence.grantsAuthority).toBe(false)
    expect(meter.records[0]).toMatchObject({
      tenantId: 'tenant-a',
      provider,
      deployment: `${provider}-prod`,
      status: 'succeeded',
      workOrderDigest: hex('3'),
      authorityReceiptRoot: hex('4'),
    })
  })

  it('denies execution when the proof-carrying work order cannot be verified', async () => {
    const mocked = transport('openai')
    const verifier: WorkOrderVerifier = { verify: async () => ({ valid: false, digest: hex('3') }) }
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), verifier, streamVerifier)

    await expect(gateway.infer(request('openai'))).rejects.toMatchObject({ code: 'WORK_ORDER_INVALID' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('denies a nominally valid work order when the authority receipt root is missing', async () => {
    const mocked = transport('openai')
    const verifier: WorkOrderVerifier = { verify: async () => ({ valid: true, digest: hex('3') }) }
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), verifier, streamVerifier)

    await expect(gateway.infer(request('openai'))).rejects.toMatchObject({ code: 'WORK_ORDER_INVALID' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it.each([
    ['provider', { workOrder: workOrder('anthropic') }],
    ['request', { workOrder: workOrder('openai', { requestId: 'wrong' }) }],
    ['target', { workOrder: workOrder('openai', { target: 'openai-other' }) }],
    ['arguments', { workOrder: workOrder('openai', { argumentsDigest: hex('9') }) }],
    ['parent', { workOrder: workOrder('openai', { expectedParentStateRoot: hex('9') }) }],
    ['idempotency', { workOrder: workOrder('openai', { idempotencyKey: 'wrong-idempotency' }) }],
    ['budget', { workOrder: workOrder('openai', { maxCostMicroUsd: 1 }) }],
    ['tokens', { workOrder: workOrder('openai', { maxOutputTokens: 1 }) }],
  ] as const)('rejects work-order %s mismatch before provider invocation', async (_name, overrides) => {
    const mocked = transport('openai')
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai', overrides))).rejects.toMatchObject({ code: 'WORK_ORDER_MISMATCH' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('requires explicit operator approval for D3', async () => {
    const mocked = transport('openai')
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai', {
      workOrder: workOrder('openai', { operatorApprovalReference: undefined }),
    }))).rejects.toMatchObject({ code: 'WORK_ORDER_INVALID' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('rejects inline credential material in the proof-carrying work order', async () => {
    const mocked = transport('openai')
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai', {
      workOrder: workOrder('openai', { secretReferences: ['sk-inline-forbidden'] }),
    }))).rejects.toMatchObject({ code: 'WORK_ORDER_INVALID' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('hard-denies D4 even if a verifier says the work order is valid', async () => {
    const mocked = transport('openai')
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai', {
      consequenceClass: 'D4',
      workOrder: workOrder('openai', { consequenceClass: 'D4' }),
    }))).rejects.toMatchObject({ code: 'CONSEQUENCE_DENIED' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('binds the runtime payload to the admitted SHA-256 arguments digest', async () => {
    const mocked = transport('openai')
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai', { payloadDigest: hex('8') }))).rejects.toMatchObject({ code: 'PAYLOAD_MISMATCH' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('requires a current fenced stream lease before a streaming provider call', async () => {
    const mocked = transport('openai')
    const verifier: StreamLeaseVerifier = { verify: vi.fn(async () => false) }
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, verifier)

    await expect(gateway.infer(request('openai', {
      stream: true,
      streamContext: {
        executionId: 'exec-1',
        ownerIdentity: 'operator:tarik',
        generation: 3,
        fencingToken: hex('4'),
        lastSequence: -1,
      },
    }))).rejects.toMatchObject({ code: 'STREAM_LEASE_INVALID' })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('rejects a provider result that attempts to grant authority', async () => {
    const mocked = transport('openai', vi.fn(async () => result('openai', { grantsAuthority: true })))
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai'))).rejects.toMatchObject({ code: 'PROVIDER_AUTHORITY_VIOLATION' })
  })

  it('fails closed when authorization is unavailable', async () => {
    const mocked = transport('openai')
    const unavailable: FrontierAuthorizer = { authorize: async () => { throw new Error('offline') } }
    const gateway = new FrontierInferenceGateway(deployments, [mocked], unavailable, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai'))).rejects.toMatchObject({ code: 'ADMISSION_UNAVAILABLE' satisfies FrontierGatewayError['code'] })
    expect(mocked.invoke).not.toHaveBeenCalled()
  })

  it('enforces idempotency and tenant concurrency before duplicate/excess provider work', async () => {
    let release: (() => void) | undefined
    const blocked = new Promise<void>(resolve => { release = resolve })
    const mocked = transport('openai', vi.fn(async () => { await blocked; return result('openai') }))
    const oneAtATime: FrontierAuthorizer = { authorize: async () => ({ ...entitlement, maxConcurrent: 1 }) }
    const gateway = new FrontierInferenceGateway(deployments, [mocked], oneAtATime, new InMemoryFrontierUsageMeter(), workOrderVerifier, streamVerifier)

    const first = gateway.infer(request('openai'))
    await expect(gateway.infer(request('openai', {
      requestId: 'request-openai-2',
      idempotencyKey: 'idem-openai-0002',
      workOrder: workOrder('openai', { requestId: 'request-openai-2', idempotencyKey: 'idem-openai-0002' }),
    }))).rejects.toMatchObject({ code: 'LIMIT_EXCEEDED' })
    const duplicate = gateway.infer(request('openai'))
    release?.()
    await Promise.all([first, duplicate])
    expect(mocked.invoke).toHaveBeenCalledOnce()
  })

  it('rejects provider token/cost overrun and records the rejected execution', async () => {
    const mocked = transport('openai', vi.fn(async () => result('openai', { outputTokens: 900 })))
    const meter = new InMemoryFrontierUsageMeter()
    const gateway = new FrontierInferenceGateway(deployments, [mocked], authorizer, meter, workOrderVerifier, streamVerifier)

    await expect(gateway.infer(request('openai'))).rejects.toMatchObject({ code: 'LIMIT_EXCEEDED' })
    expect(meter.records.at(-1)?.status).toBe('rejected')
    expect(meter.records.at(-1)?.authorityReceiptRoot).toBe(hex('4'))
  })
})
