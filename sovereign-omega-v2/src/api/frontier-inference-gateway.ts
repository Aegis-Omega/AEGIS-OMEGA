import { sha256Hex } from '../core/hashing.js'

export type FrontierInferenceProvider =
  | 'openai'
  | 'anthropic'
  | 'google-vertex'
  | 'microsoft-foundry'
  | 'aws-bedrock'
  | 'vercel-ai-gateway'
  | 'xai'
  | 'mistral'
  | 'deepseek'
  | 'qwen-dashscope'
  | 'nvidia-nim'
  | 'huggingface'

export type FrontierProductTier = 'starter' | 'professional' | 'enterprise'
export type ConsequenceClass = 'D0' | 'D1' | 'D2' | 'D3' | 'D4'
export type FrontierRequestStatus = 'succeeded' | 'rejected' | 'failed'

export interface ProofCarryingWorkOrder {
  readonly schemaVersion: '1.0.0'
  readonly workOrderId: string
  readonly requestId: string
  readonly provider: FrontierInferenceProvider
  readonly capability: 'inference.run'
  readonly consequenceClass: ConsequenceClass
  readonly argumentsDigest: string
  readonly expectedParentStateRoot: string
  readonly idempotencyKey: string
  readonly maxCostMicroUsd: number
  readonly maxInputTokens: number
  readonly maxOutputTokens: number
  readonly evidenceReferences: readonly string[]
  readonly operatorApprovalReference?: string | undefined
  readonly issuedSequence: number
}

export interface VerifiedWorkOrder {
  readonly valid: boolean
  readonly digest: string
}

/**
 * The runtime never self-attests a proof-carrying work order. A verifier bound to
 * Automaton-3 / receipt evidence must be injected by the server-side composition.
 */
export interface WorkOrderVerifier {
  verify(workOrder: ProofCarryingWorkOrder): Promise<VerifiedWorkOrder>
}

export interface FrontierStreamContext {
  readonly executionId: string
  readonly ownerIdentity: string
  readonly generation: number
  readonly fencingToken: string
  readonly lastSequence: number
}

export interface StreamLeaseVerifier {
  verify(context: FrontierStreamContext): Promise<boolean>
}

export interface FrontierInferenceRequest<T = unknown> {
  readonly tenantId: string
  readonly productTier: FrontierProductTier
  readonly requestId: string
  readonly correlationId: string
  readonly idempotencyKey: string
  readonly provider: FrontierInferenceProvider
  readonly deployment: string
  readonly consequenceClass: ConsequenceClass
  readonly inputTokens: number
  readonly maxOutputTokens: number
  readonly tokenCeiling: number
  readonly budgetMicroUsd: number
  readonly payload: T
  readonly payloadDigest: string
  readonly expectedParentStateRoot: string
  readonly workOrder: ProofCarryingWorkOrder
  readonly stream: boolean
  readonly streamContext?: FrontierStreamContext | undefined
}

export interface FrontierDeployment {
  readonly provider: FrontierInferenceProvider
  readonly name: string
  readonly model: string
  readonly inputMicroUsdPerMillion: number
  readonly outputMicroUsdPerMillion: number
}

export interface FrontierProviderResult<T = unknown> {
  readonly value: T
  readonly providerOperationId: string
  readonly responseDigest: string
  readonly inputTokens: number
  readonly outputTokens: number
  readonly grantsAuthority: boolean
}

export interface FrontierInferenceTransport {
  readonly provider: FrontierInferenceProvider
  invoke(payload: unknown, deployment: FrontierDeployment, request: FrontierInferenceRequest): Promise<FrontierProviderResult>
}

export interface FrontierEntitlement {
  readonly allowedDeployments: readonly string[]
  readonly monthlyHardLimitMicroUsd: number
  readonly maxInputTokens: number
  readonly maxOutputTokens: number
  readonly maxConcurrent: number
}

export interface FrontierAuthorizer {
  authorize(tenantId: string, tier: FrontierProductTier): Promise<FrontierEntitlement>
}

export interface FrontierUsageRecord {
  readonly tenantId: string
  readonly provider: FrontierInferenceProvider
  readonly deployment: string
  readonly model: string
  readonly inputTokens: number
  readonly outputTokens: number
  readonly costEstimateMicroUsd: number
  readonly status: FrontierRequestStatus
  readonly correlationId: string
  readonly requestId: string
  readonly workOrderDigest: string
  readonly providerOperationId?: string | undefined
  readonly responseDigest?: string | undefined
  readonly grantsAuthority: false
}

export interface FrontierMeter {
  monthlySpendMicroUsd(tenantId: string): Promise<number>
  record(usage: FrontierUsageRecord): Promise<void>
}

export class InMemoryFrontierUsageMeter implements FrontierMeter {
  readonly records: FrontierUsageRecord[] = []

  async monthlySpendMicroUsd(tenantId: string): Promise<number> {
    return this.records
      .filter(record => record.tenantId === tenantId && record.status === 'succeeded')
      .reduce((total, record) => total + record.costEstimateMicroUsd, 0)
  }

  async record(usage: FrontierUsageRecord): Promise<void> {
    this.records.push(Object.freeze({ ...usage }))
  }
}

export class FrontierGatewayError extends Error {
  constructor(
    readonly code:
      | 'INVALID_REQUEST'
      | 'PAYLOAD_MISMATCH'
      | 'WORK_ORDER_INVALID'
      | 'WORK_ORDER_MISMATCH'
      | 'CONSEQUENCE_DENIED'
      | 'STREAM_LEASE_INVALID'
      | 'ADMISSION_UNAVAILABLE'
      | 'UNAUTHORIZED'
      | 'LIMIT_EXCEEDED'
      | 'IDEMPOTENCY_CONFLICT'
      | 'PROVIDER_FAILURE'
      | 'PROVIDER_AUTHORITY_VIOLATION',
    message: string,
  ) {
    super(message)
    this.name = 'FrontierGatewayError'
  }
}

interface IdempotentExecution {
  readonly fingerprint: string
  readonly promise: Promise<FrontierProviderResult>
}

interface ValidatedRequest {
  readonly workOrderDigest: string
  readonly fingerprint: string
}

const SHA256_HEX = /^[a-f0-9]{64}$/

/**
 * Binds the exact JSON payload bytes used by this runtime. This is deliberately
 * not described as RFC 8785/JCS canonicalisation: cross-runtime canonicalisation
 * remains a separate admission concern until the canonicalisation repair is
 * independently admitted.
 */
export async function runtimeJsonPayloadDigest(payload: unknown): Promise<string> {
  let serialized: string | undefined
  try {
    serialized = JSON.stringify(payload)
  } catch {
    throw new FrontierGatewayError('INVALID_REQUEST', 'payload is not JSON serializable')
  }
  if (serialized === undefined) {
    throw new FrontierGatewayError('INVALID_REQUEST', 'payload is not JSON serializable')
  }
  return sha256Hex(new TextEncoder().encode(serialized))
}

export class FrontierInferenceGateway {
  private readonly inFlight = new Map<string, number>()
  private readonly idempotent = new Map<string, IdempotentExecution>()

  constructor(
    private readonly deployments: readonly FrontierDeployment[],
    private readonly transports: readonly FrontierInferenceTransport[],
    private readonly authorizer: FrontierAuthorizer,
    private readonly meter: FrontierMeter,
    private readonly workOrderVerifier: WorkOrderVerifier,
    private readonly streamLeaseVerifier: StreamLeaseVerifier,
  ) {}

  async infer<T>(request: FrontierInferenceRequest): Promise<FrontierProviderResult<T>> {
    const validated = await this.validateRequest(request)
    const cacheKey = `${request.tenantId}:${request.idempotencyKey}`
    const existing = this.idempotent.get(cacheKey)
    if (existing !== undefined) {
      if (existing.fingerprint !== validated.fingerprint) {
        throw new FrontierGatewayError('IDEMPOTENCY_CONFLICT', 'idempotency key is already bound to a different request')
      }
      return existing.promise as Promise<FrontierProviderResult<T>>
    }

    const execution = this.admitAndInvoke(request, validated.workOrderDigest)
    this.idempotent.set(cacheKey, { fingerprint: validated.fingerprint, promise: execution })
    try {
      return await execution as FrontierProviderResult<T>
    } catch (error) {
      this.idempotent.delete(cacheKey)
      throw error
    }
  }

  async inferBatch<T>(requests: readonly FrontierInferenceRequest[]): Promise<readonly FrontierProviderResult<T>[]> {
    const results: FrontierProviderResult<T>[] = []
    for (const request of requests) {
      results.push(await this.infer<T>(request))
    }
    return results
  }

  private async validateRequest(request: FrontierInferenceRequest): Promise<ValidatedRequest> {
    if (
      !request.tenantId ||
      !request.requestId ||
      !request.correlationId ||
      request.idempotencyKey.length < 8 ||
      !request.deployment ||
      request.inputTokens < 0 ||
      request.maxOutputTokens <= 0 ||
      request.tokenCeiling <= 0 ||
      request.budgetMicroUsd < 0 ||
      request.maxOutputTokens > request.tokenCeiling ||
      !SHA256_HEX.test(request.payloadDigest) ||
      !SHA256_HEX.test(request.expectedParentStateRoot)
    ) {
      throw new FrontierGatewayError('INVALID_REQUEST', 'request metadata is incomplete or malformed')
    }

    if (request.consequenceClass === 'D4') {
      throw new FrontierGatewayError('CONSEQUENCE_DENIED', 'D4 provider execution is denied')
    }

    const actualPayloadDigest = await runtimeJsonPayloadDigest(request.payload)
    if (actualPayloadDigest !== request.payloadDigest) {
      throw new FrontierGatewayError('PAYLOAD_MISMATCH', 'runtime payload does not match admitted payload digest')
    }

    this.validateWorkOrderStructure(request.workOrder)
    const verified = await this.verifyWorkOrder(request.workOrder)
    this.assertWorkOrderMatches(request, verified.digest)

    if (request.stream) {
      if (request.streamContext === undefined) {
        throw new FrontierGatewayError('STREAM_LEASE_INVALID', 'streaming request has no fenced stream context')
      }
      let streamValid = false
      try {
        streamValid = await this.streamLeaseVerifier.verify(request.streamContext)
      } catch {
        streamValid = false
      }
      if (!streamValid) {
        throw new FrontierGatewayError('STREAM_LEASE_INVALID', 'stream lease verification failed')
      }
    }

    const fingerprint = [
      request.requestId,
      request.provider,
      request.deployment,
      request.consequenceClass,
      request.payloadDigest,
      request.expectedParentStateRoot,
      request.workOrder.workOrderId,
      verified.digest,
    ].join('|')
    return { workOrderDigest: verified.digest, fingerprint }
  }

  private validateWorkOrderStructure(workOrder: ProofCarryingWorkOrder): void {
    if (
      workOrder.schemaVersion !== '1.0.0' ||
      !workOrder.workOrderId ||
      !workOrder.requestId ||
      workOrder.capability !== 'inference.run' ||
      workOrder.idempotencyKey.length < 8 ||
      !SHA256_HEX.test(workOrder.argumentsDigest) ||
      !SHA256_HEX.test(workOrder.expectedParentStateRoot) ||
      workOrder.maxCostMicroUsd < 0 ||
      workOrder.maxInputTokens < 0 ||
      workOrder.maxOutputTokens < 0 ||
      workOrder.issuedSequence < 0
    ) {
      throw new FrontierGatewayError('WORK_ORDER_INVALID', 'proof-carrying work order is malformed')
    }
    if (workOrder.consequenceClass === 'D4') {
      throw new FrontierGatewayError('CONSEQUENCE_DENIED', 'D4 work order is denied')
    }
    if ((workOrder.consequenceClass === 'D2' || workOrder.consequenceClass === 'D3') && workOrder.evidenceReferences.length === 0) {
      throw new FrontierGatewayError('WORK_ORDER_INVALID', 'D2/D3 work order requires evidence references')
    }
    if (workOrder.consequenceClass === 'D3' && !workOrder.operatorApprovalReference) {
      throw new FrontierGatewayError('WORK_ORDER_INVALID', 'D3 work order requires explicit operator approval')
    }
  }

  private async verifyWorkOrder(workOrder: ProofCarryingWorkOrder): Promise<VerifiedWorkOrder> {
    let verified: VerifiedWorkOrder
    try {
      verified = await this.workOrderVerifier.verify(workOrder)
    } catch {
      throw new FrontierGatewayError('WORK_ORDER_INVALID', 'proof-carrying work order verifier is unavailable')
    }
    if (!verified.valid || !SHA256_HEX.test(verified.digest)) {
      throw new FrontierGatewayError('WORK_ORDER_INVALID', 'proof-carrying work order verification failed')
    }
    return verified
  }

  private assertWorkOrderMatches(request: FrontierInferenceRequest, workOrderDigest: string): void {
    const order = request.workOrder
    if (
      order.provider !== request.provider ||
      order.requestId !== request.requestId ||
      order.capability !== 'inference.run' ||
      order.consequenceClass !== request.consequenceClass ||
      order.argumentsDigest !== request.payloadDigest ||
      order.expectedParentStateRoot !== request.expectedParentStateRoot ||
      order.idempotencyKey !== request.idempotencyKey ||
      order.maxCostMicroUsd < request.budgetMicroUsd ||
      order.maxInputTokens < request.inputTokens ||
      order.maxOutputTokens < request.maxOutputTokens ||
      !SHA256_HEX.test(workOrderDigest)
    ) {
      throw new FrontierGatewayError('WORK_ORDER_MISMATCH', 'work order does not bind the complete inference request')
    }
  }

  private async admitAndInvoke(request: FrontierInferenceRequest, workOrderDigest: string): Promise<FrontierProviderResult> {
    let entitlement: FrontierEntitlement
    let deployment: FrontierDeployment
    try {
      entitlement = await this.authorizer.authorize(request.tenantId, request.productTier)
      const matchedDeployment = this.deployments.find(item => item.provider === request.provider && item.name === request.deployment)
      if (matchedDeployment === undefined) {
        throw new FrontierGatewayError('UNAUTHORIZED', 'deployment is not allowlisted')
      }
      deployment = matchedDeployment
      const spend = await this.meter.monthlySpendMicroUsd(request.tenantId)
      this.checkLimits(request, entitlement, deployment, spend)
    } catch (error) {
      if (error instanceof FrontierGatewayError) throw error
      throw new FrontierGatewayError('ADMISSION_UNAVAILABLE', 'authorization or metering is unavailable; request denied')
    }

    const active = this.inFlight.get(request.tenantId) ?? 0
    if (active >= entitlement.maxConcurrent) {
      throw new FrontierGatewayError('LIMIT_EXCEEDED', 'tenant concurrency limit reached')
    }
    this.inFlight.set(request.tenantId, active + 1)

    try {
      const transport = this.transports.find(item => item.provider === request.provider)
      if (transport === undefined) {
        throw new FrontierGatewayError('UNAUTHORIZED', 'provider transport is not registered')
      }
      const result = await transport.invoke(request.payload, deployment, request)
      if (result.grantsAuthority) {
        throw new FrontierGatewayError('PROVIDER_AUTHORITY_VIOLATION', 'provider result attempted to grant AEGIS authority')
      }
      if (!result.providerOperationId || !SHA256_HEX.test(result.responseDigest)) {
        throw new FrontierGatewayError('PROVIDER_FAILURE', 'provider result is not receipt-bindable')
      }
      if (result.inputTokens > request.inputTokens || result.outputTokens > request.maxOutputTokens) {
        throw new FrontierGatewayError('LIMIT_EXCEEDED', 'provider exceeded the admitted token limit')
      }
      const cost = this.cost(deployment, result.inputTokens, result.outputTokens)
      if (cost > request.budgetMicroUsd || cost > request.workOrder.maxCostMicroUsd) {
        throw new FrontierGatewayError('LIMIT_EXCEEDED', 'provider cost exceeded the admitted budget')
      }
      await this.record(request, deployment, result, cost, 'succeeded', workOrderDigest)
      return { ...result, grantsAuthority: false }
    } catch (error) {
      const status: FrontierRequestStatus = error instanceof FrontierGatewayError && error.code === 'LIMIT_EXCEEDED' ? 'rejected' : 'failed'
      try {
        await this.record(request, deployment, undefined, 0, status, workOrderDigest)
      } catch {
        throw new FrontierGatewayError('ADMISSION_UNAVAILABLE', 'usage persistence is unavailable; request denied')
      }
      throw error instanceof FrontierGatewayError
        ? error
        : new FrontierGatewayError('PROVIDER_FAILURE', 'provider invocation failed')
    } finally {
      this.inFlight.set(request.tenantId, active)
    }
  }

  private checkLimits(
    request: FrontierInferenceRequest,
    entitlement: FrontierEntitlement,
    deployment: FrontierDeployment,
    spend: number,
  ): void {
    if (!entitlement.allowedDeployments.includes(deployment.name)) {
      throw new FrontierGatewayError('UNAUTHORIZED', 'deployment is not entitled for tenant')
    }
    if (request.inputTokens > entitlement.maxInputTokens || request.maxOutputTokens > entitlement.maxOutputTokens) {
      throw new FrontierGatewayError('LIMIT_EXCEEDED', 'request token limit exceeds entitlement')
    }
    const worstCase = this.cost(deployment, request.inputTokens, request.maxOutputTokens)
    if (
      worstCase > request.budgetMicroUsd ||
      worstCase > request.workOrder.maxCostMicroUsd ||
      spend + worstCase > entitlement.monthlyHardLimitMicroUsd
    ) {
      throw new FrontierGatewayError('LIMIT_EXCEEDED', 'budget or monthly hard limit would be exceeded')
    }
  }

  private async record(
    request: FrontierInferenceRequest,
    deployment: FrontierDeployment,
    result: FrontierProviderResult | undefined,
    costEstimateMicroUsd: number,
    status: FrontierRequestStatus,
    workOrderDigest: string,
  ): Promise<void> {
    await this.meter.record({
      tenantId: request.tenantId,
      provider: request.provider,
      deployment: deployment.name,
      model: deployment.model,
      inputTokens: result?.inputTokens ?? 0,
      outputTokens: result?.outputTokens ?? 0,
      costEstimateMicroUsd,
      status,
      correlationId: request.correlationId,
      requestId: request.requestId,
      workOrderDigest,
      providerOperationId: result?.providerOperationId,
      responseDigest: result?.responseDigest,
      grantsAuthority: false,
    })
  }

  private cost(deployment: FrontierDeployment, input: number, output: number): number {
    return Math.ceil((
      input * deployment.inputMicroUsdPerMillion +
      output * deployment.outputMicroUsdPerMillion
    ) / 1_000_000)
  }
}
