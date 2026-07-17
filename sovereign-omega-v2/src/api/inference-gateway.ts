// Provider-neutral, server-side inference admission boundary. Provider SDKs must
// only be used by an InferenceTransport registered with this gateway.

export type InferenceProvider = 'anthropic' | 'vertex-ai' | 'microsoft-foundry'
export type ProductTier = 'starter' | 'professional' | 'enterprise'
export type RequestStatus = 'succeeded' | 'rejected' | 'failed'

export interface InferenceRequest<T = unknown> {
  readonly tenantId: string
  readonly productTier: ProductTier
  readonly requestId: string
  readonly correlationId: string
  readonly idempotencyKey: string
  readonly provider: InferenceProvider
  readonly deployment: string
  readonly inputTokens: number
  readonly maxOutputTokens: number
  readonly tokenCeiling: number
  readonly budgetUsd: number
  readonly payload: T
}

export interface Deployment { readonly provider: InferenceProvider; readonly name: string; readonly model: string; readonly inputUsdPerMillion: number; readonly outputUsdPerMillion: number }
export interface ProviderResult<T> { readonly value: T; readonly inputTokens: number; readonly outputTokens: number }
export interface InferenceTransport { readonly provider: InferenceProvider; invoke(payload: unknown, deployment: Deployment): Promise<ProviderResult<unknown>> }
export interface Entitlement { readonly allowedDeployments: readonly string[]; readonly monthlyHardLimitUsd: number; readonly maxInputTokens: number; readonly maxOutputTokens: number; readonly maxConcurrent: number }
export interface Authorizer { authorize(tenantId: string, tier: ProductTier): Promise<Entitlement> }
export interface Meter { monthlySpendUsd(tenantId: string): Promise<number>; record(usage: UsageRecord): Promise<void> }
export interface UsageRecord { readonly tenantId: string; readonly provider: InferenceProvider; readonly deployment: string; readonly model: string; readonly inputTokens: number; readonly outputTokens: number; readonly costEstimateUsd: number; readonly status: RequestStatus; readonly correlationId: string; readonly requestId: string }

export class GatewayError extends Error { constructor(readonly code: 'UNAUTHORIZED' | 'METERING_UNAVAILABLE' | 'LIMIT_EXCEEDED' | 'INVALID_REQUEST' | 'PROVIDER_FAILURE', message: string) { super(message); this.name = 'GatewayError' } }

/** A deliberately simple persistence implementation for application composition and tests. */
export class InMemoryUsageMeter implements Meter {
  readonly records: UsageRecord[] = []
  async monthlySpendUsd(tenantId: string): Promise<number> { return this.records.filter(record => record.tenantId === tenantId && record.status === 'succeeded').reduce((total, record) => total + record.costEstimateUsd, 0) }
  async record(usage: UsageRecord): Promise<void> { this.records.push(Object.freeze({ ...usage })) }
}

export class InferenceGateway {
  private readonly inFlight = new Map<string, number>()
  private readonly idempotent = new Map<string, Promise<ProviderResult<unknown>>>()

  constructor(private readonly deployments: readonly Deployment[], private readonly transports: readonly InferenceTransport[], private readonly authorizer: Authorizer, private readonly meter: Meter) {}

  async infer<T>(request: InferenceRequest): Promise<ProviderResult<T>> {
    this.validate(request)
    const cacheKey = `${request.tenantId}:${request.idempotencyKey}`
    const existing = this.idempotent.get(cacheKey)
    if (existing) return existing as Promise<ProviderResult<T>>
    const execution = this.admitAndInvoke(request)
    this.idempotent.set(cacheKey, execution)
    try { return await execution as ProviderResult<T> } catch (error) { this.idempotent.delete(cacheKey); throw error }
  }

  /** Batch work is deliberately a sequence of normal admissions; it has no provider-side bypass. */
  async inferBatch<T>(requests: readonly InferenceRequest[]): Promise<readonly ProviderResult<T>[]> {
    const results: ProviderResult<T>[] = []
    for (const request of requests) results.push(await this.infer<T>(request))
    return results
  }

  private async admitAndInvoke(request: InferenceRequest): Promise<ProviderResult<unknown>> {
    let entitlement: Entitlement
    let deployment: Deployment
    try {
      entitlement = await this.authorizer.authorize(request.tenantId, request.productTier)
      deployment = this.deployments.find(item => item.provider === request.provider && item.name === request.deployment) ?? this.reject('UNAUTHORIZED', 'deployment is not allowlisted')
      const spend = await this.meter.monthlySpendUsd(request.tenantId)
      this.checkLimits(request, entitlement, deployment, spend)
    } catch (error) {
      if (error instanceof GatewayError) throw error
      throw new GatewayError('METERING_UNAVAILABLE', 'authorization or metering is unavailable; request denied')
    }
    const active = this.inFlight.get(request.tenantId) ?? 0
    if (active >= entitlement.maxConcurrent) throw new GatewayError('LIMIT_EXCEEDED', 'tenant concurrency limit reached')
    this.inFlight.set(request.tenantId, active + 1)
    try {
      const transport = this.transports.find(item => item.provider === request.provider)
      if (!transport) throw new GatewayError('UNAUTHORIZED', 'provider transport is not registered')
      const result = await transport.invoke(request.payload, deployment)
      if (result.inputTokens > request.inputTokens || result.outputTokens > request.maxOutputTokens) throw new GatewayError('LIMIT_EXCEEDED', 'provider exceeded the admitted token limit')
      const cost = this.cost(deployment, result.inputTokens, result.outputTokens)
      if (cost > request.budgetUsd) throw new GatewayError('LIMIT_EXCEEDED', 'actual request cost exceeded budget')
      await this.record(request, deployment, result, cost, 'succeeded')
      return result
    } catch (error) {
      if (!(error instanceof GatewayError && error.code === 'METERING_UNAVAILABLE')) {
        try { await this.record(request, deployment, { inputTokens: 0, outputTokens: 0 }, 0, error instanceof GatewayError && error.code === 'LIMIT_EXCEEDED' ? 'rejected' : 'failed') } catch { throw new GatewayError('METERING_UNAVAILABLE', 'usage persistence is unavailable; request denied') }
      }
      throw error instanceof GatewayError ? error : new GatewayError('PROVIDER_FAILURE', 'provider invocation failed')
    } finally { this.inFlight.set(request.tenantId, active) }
  }

  private validate(request: InferenceRequest): void {
    if (!request.tenantId || !request.requestId || !request.correlationId || !request.idempotencyKey || request.tokenCeiling <= 0 || request.budgetUsd <= 0 || request.inputTokens < 0 || request.maxOutputTokens <= 0) this.reject('INVALID_REQUEST', 'authenticated request metadata is incomplete')
    if (request.maxOutputTokens > request.tokenCeiling) this.reject('LIMIT_EXCEEDED', 'output limit exceeds request token ceiling')
  }
  private checkLimits(request: InferenceRequest, entitlement: Entitlement, deployment: Deployment, spend: number): void {
    if (!entitlement.allowedDeployments.includes(deployment.name)) this.reject('UNAUTHORIZED', 'deployment is not entitled for tenant')
    if (request.inputTokens > entitlement.maxInputTokens || request.maxOutputTokens > entitlement.maxOutputTokens) this.reject('LIMIT_EXCEEDED', 'request token limit exceeds entitlement')
    const worstCase = this.cost(deployment, request.inputTokens, request.maxOutputTokens)
    if (worstCase > request.budgetUsd || spend + worstCase > entitlement.monthlyHardLimitUsd) this.reject('LIMIT_EXCEEDED', 'budget or monthly hard limit would be exceeded')
  }
  private async record(request: InferenceRequest, deployment: Deployment, result: Pick<ProviderResult<unknown>, 'inputTokens' | 'outputTokens'>, costEstimateUsd: number, status: RequestStatus): Promise<void> { await this.meter.record({ tenantId: request.tenantId, provider: request.provider, deployment: deployment.name, model: deployment.model, inputTokens: result.inputTokens, outputTokens: result.outputTokens, costEstimateUsd, status, correlationId: request.correlationId, requestId: request.requestId }) }
  private cost(deployment: Deployment, input: number, output: number): number { return (input * deployment.inputUsdPerMillion + output * deployment.outputUsdPerMillion) / 1_000_000 }
  private reject(code: GatewayError['code'], message: string): never { throw new GatewayError(code, message) }
}
