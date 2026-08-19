import { sha256Hex } from '../core/hashing.js'
import type {
  FrontierDeployment,
  FrontierInferenceProvider,
  FrontierInferenceRequest,
  FrontierInferenceTransport,
  FrontierProviderResult,
} from './frontier-inference-gateway.js'

export type FrontierHttpProtocol = 'openai-responses' | 'anthropic-messages' | 'openai-compatible-chat'

export interface FrontierHttpConnection {
  readonly provider: FrontierInferenceProvider
  readonly protocol: FrontierHttpProtocol
  readonly baseUrl: string
  readonly authReference: string
}

export interface FrontierCredentialHeaderResolver {
  resolve(provider: FrontierInferenceProvider, authReference: string): Promise<Record<string, string>>
}

export interface FrontierFetchResponse {
  readonly ok: boolean
  readonly status: number
  readonly headers: { get(name: string): string | null }
  text(): Promise<string>
}

export type FrontierFetch = (
  url: string,
  init: { readonly method: 'POST', readonly headers: Record<string, string>, readonly body: string },
) => Promise<FrontierFetchResponse>

export interface FrontierManagedInvoker {
  invoke(
    provider: FrontierInferenceProvider,
    payload: unknown,
    deployment: FrontierDeployment,
    request: FrontierInferenceRequest,
  ): Promise<FrontierProviderResult>
}

export class FrontierTransportError extends Error {
  constructor(
    readonly code:
      | 'INVALID_CONNECTION'
      | 'PROTOCOL_MISMATCH'
      | 'CREDENTIAL_RESOLUTION_FAILED'
      | 'PAYLOAD_INVALID'
      | 'MODEL_MISMATCH'
      | 'PROVIDER_HTTP_ERROR'
      | 'PROVIDER_RESPONSE_INVALID'
      | 'MANAGED_PROVIDER_INVALID',
    message: string,
  ) {
    super(message)
    this.name = 'FrontierTransportError'
  }
}

const AUTH_REFERENCE_PREFIXES = [
  'secret://',
  'env://',
  'vault://',
  'keyref://',
  'identity://',
  'oidc://',
  'oauth://',
] as const

const PROTOCOL_PROVIDERS: Readonly<Record<FrontierHttpProtocol, readonly FrontierInferenceProvider[]>> = {
  'openai-responses': ['openai', 'vercel-ai-gateway', 'xai', 'nvidia-nim'],
  'anthropic-messages': ['anthropic'],
  'openai-compatible-chat': [
    'vercel-ai-gateway',
    'xai',
    'mistral',
    'deepseek',
    'qwen-dashscope',
    'nvidia-nim',
    'huggingface',
  ],
}

const MANAGED_PROVIDERS: readonly FrontierInferenceProvider[] = [
  'google-vertex',
  'microsoft-foundry',
  'aws-bedrock',
]

const SHA256_HEX = /^[a-f0-9]{64}$/

export class FrontierHttpInferenceTransport implements FrontierInferenceTransport {
  readonly provider: FrontierInferenceProvider

  constructor(
    private readonly connection: FrontierHttpConnection,
    private readonly credentialHeaders: FrontierCredentialHeaderResolver,
    private readonly fetcher: FrontierFetch,
  ) {
    this.verifyConnection(connection)
    this.provider = connection.provider
  }

  async invoke(
    payload: unknown,
    deployment: FrontierDeployment,
    request: FrontierInferenceRequest,
  ): Promise<FrontierProviderResult> {
    if (deployment.provider !== this.provider || request.provider !== this.provider) {
      throw new FrontierTransportError('PROTOCOL_MISMATCH', 'provider/deployment does not match transport')
    }
    if (request.stream) {
      throw new FrontierTransportError('PROTOCOL_MISMATCH', 'streaming requests require the fenced SSE transport')
    }

    const body = this.buildBody(payload, deployment, request)
    let runtimeHeaders: Record<string, string>
    try {
      runtimeHeaders = await this.credentialHeaders.resolve(this.provider, this.connection.authReference)
    } catch {
      throw new FrontierTransportError('CREDENTIAL_RESOLUTION_FAILED', 'runtime credential resolution failed')
    }
    if (!runtimeHeaders || Object.keys(runtimeHeaders).length === 0) {
      throw new FrontierTransportError('CREDENTIAL_RESOLUTION_FAILED', 'runtime credential headers are empty')
    }

    const response = await this.fetcher(this.endpoint(), {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        accept: 'application/json',
        'x-aegis-request-id': request.requestId,
        'x-aegis-idempotency-key': request.idempotencyKey,
        ...runtimeHeaders,
      },
      body: JSON.stringify(body),
    })
    const responseText = await response.text()
    if (!response.ok) {
      throw new FrontierTransportError('PROVIDER_HTTP_ERROR', `provider returned HTTP ${response.status}`)
    }

    let decoded: unknown
    try {
      decoded = JSON.parse(responseText)
    } catch {
      throw new FrontierTransportError('PROVIDER_RESPONSE_INVALID', 'provider returned invalid JSON')
    }
    if (!isRecord(decoded)) {
      throw new FrontierTransportError('PROVIDER_RESPONSE_INVALID', 'provider response must be an object')
    }

    const providerOperationId = readString(decoded, 'id')
      ?? response.headers.get('x-request-id')
      ?? response.headers.get('request-id')
    if (!providerOperationId) {
      throw new FrontierTransportError('PROVIDER_RESPONSE_INVALID', 'provider response has no operation/request id')
    }
    const usage = isRecord(decoded.usage) ? decoded.usage : {}
    const inputTokens = readNonNegativeInteger(usage, 'input_tokens')
      ?? readNonNegativeInteger(usage, 'prompt_tokens')
      ?? 0
    const outputTokens = readNonNegativeInteger(usage, 'output_tokens')
      ?? readNonNegativeInteger(usage, 'completion_tokens')
      ?? 0
    const responseDigest = await sha256Hex(new TextEncoder().encode(responseText))

    return {
      value: decoded,
      providerOperationId,
      responseDigest,
      inputTokens,
      outputTokens,
      grantsAuthority: false,
    }
  }

  private verifyConnection(connection: FrontierHttpConnection): void {
    if (!PROTOCOL_PROVIDERS[connection.protocol].includes(connection.provider)) {
      throw new FrontierTransportError('PROTOCOL_MISMATCH', 'provider is not admitted for the selected protocol')
    }
    let parsed: URL
    try {
      parsed = new URL(connection.baseUrl)
    } catch {
      throw new FrontierTransportError('INVALID_CONNECTION', 'provider base URL is invalid')
    }
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password) {
      throw new FrontierTransportError('INVALID_CONNECTION', 'provider base URL must be HTTPS without embedded credentials')
    }
    if (!AUTH_REFERENCE_PREFIXES.some(prefix => connection.authReference.startsWith(prefix))) {
      throw new FrontierTransportError('INVALID_CONNECTION', 'provider auth must be an opaque runtime reference')
    }
  }

  private endpoint(): string {
    const base = this.connection.baseUrl.replace(/\/$/, '')
    if (this.connection.protocol === 'openai-responses') {
      return base.endsWith('/v1') ? `${base}/responses` : `${base}/v1/responses`
    }
    if (this.connection.protocol === 'anthropic-messages') {
      return base.endsWith('/v1') ? `${base}/messages` : `${base}/v1/messages`
    }
    return `${base}/chat/completions`
  }

  private buildBody(
    payload: unknown,
    deployment: FrontierDeployment,
    request: FrontierInferenceRequest,
  ): Record<string, unknown> {
    if (!isRecord(payload)) {
      throw new FrontierTransportError('PAYLOAD_INVALID', 'frontier HTTP payload must be a JSON object')
    }
    const requestedModel = readString(payload, 'model')
    if (requestedModel !== undefined && requestedModel !== deployment.model) {
      throw new FrontierTransportError('MODEL_MISMATCH', 'payload model does not match admitted deployment')
    }
    const body: Record<string, unknown> = { ...payload, model: deployment.model }
    if (this.connection.protocol === 'openai-responses') {
      body.max_output_tokens = request.maxOutputTokens
    } else {
      body.max_tokens = request.maxOutputTokens
    }
    body.stream = false
    return body
  }
}

export class FrontierManagedInferenceTransport implements FrontierInferenceTransport {
  readonly provider: FrontierInferenceProvider

  constructor(provider: FrontierInferenceProvider, private readonly invoker: FrontierManagedInvoker) {
    if (!MANAGED_PROVIDERS.includes(provider)) {
      throw new FrontierTransportError('MANAGED_PROVIDER_INVALID', 'provider is not admitted on the managed SDK seam')
    }
    this.provider = provider
  }

  async invoke(
    payload: unknown,
    deployment: FrontierDeployment,
    request: FrontierInferenceRequest,
  ): Promise<FrontierProviderResult> {
    if (request.provider !== this.provider || deployment.provider !== this.provider) {
      throw new FrontierTransportError('MANAGED_PROVIDER_INVALID', 'managed provider/deployment mismatch')
    }
    const result = await this.invoker.invoke(this.provider, payload, deployment, request)
    if (
      !result.providerOperationId ||
      !SHA256_HEX.test(result.responseDigest) ||
      result.inputTokens < 0 ||
      result.outputTokens < 0 ||
      result.grantsAuthority
    ) {
      throw new FrontierTransportError('PROVIDER_RESPONSE_INVALID', 'managed provider returned invalid or authority-bearing evidence')
    }
    return { ...result, grantsAuthority: false }
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readString(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key]
  return typeof value === 'string' && value.length > 0 ? value : undefined
}

function readNonNegativeInteger(record: Record<string, unknown>, key: string): number | undefined {
  const value = record[key]
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : undefined
}
